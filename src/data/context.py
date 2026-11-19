"""Source complémentaire et audit de jointure - E1 avec E2/E3.

Produit, pour un instantané, `data/processed/<snapshot_id>/context.csv` (colonnes
exactes de `doc/templates/context.csv`, format long : une ligne par source, lieu,
validité et variable), une fiche par source (`context_sources.json`) et un audit
de jointure avec `counts.csv` (`context_join_audit.json`). Les bruts sont déposés
intacts dans `data/history/<snapshot_id>/context/` et décrits dans le manifeste.

Calendrier sur une seule ligne (`e1-context/0.2.0`, 18/11/2026) : un jour férié ou de
vacances tient en une ligne, `variable = is_holiday`, `value = true`, et son nom dans la
colonne `label` (ex. « Toussaint ») ; un jour ordinaire a `value = false` et `label`
vide. Avant, le nom occupait une deuxième ligne (`holiday_name`). `label` est vide pour
la météo. `--migrer` convertit un context.csv de l'ancien format sans rien retélécharger.

Grèves (`e1-context/0.3.0`, 19/11/2026, tâche B4) : référentiel de Zeineb
(`data/reference/greves_transport_idf.csv`, un jour par ligne du 01/01/2023 au
17/11/2026, liste faite à la main, sources dans `greves_transport_idf_sources.csv`).
`variable = is_strike`, `value = true` si les transports en commun d'Île-de-France sont
annoncés perturbés ce jour-là ; `label` = portée, intensité et réseaux. Connu au plus tard
24 h avant (notice `data/reference/README.md`, Code des transports art. L1222-8) :
`available_at` = minuit (Paris) du jour - 24 h. Hors de la période recensée : pas de
ligne (valeur inconnue). `--greves` ajoute ces lignes à un context.csv existant, sans
rien retélécharger.

Sources et rôles (doc/CONTRATS.md §4)
-------------------------------------
| context_source_id    | Variables (nom dans `label`)                | Rôle              |
| -------------------- | ------------------------------------------- | ----------------- |
| `jours_feries`       | is_holiday                                  | known_calendar    |
| `vacances_zone_c`    | is_school_holiday                           | known_calendar    |
| `greves_idf`         | is_strike (connu 24 h avant)                | known_calendar    |
| `meteo_prevue`       | temp_prev, rain_prev, wind_prev             | forecast_bulletin |
| `meteo_observee`     | temp_obs, rain_obs, wind_obs                | past_observation  |

Règles de temps
---------------
- Calendrier : une ligne par date locale (Europe/Paris) ; jointure sur la date
  locale du DÉBUT de l'heure comptée. Connu à l'avance : `available_at` vide, sauf
  pour les grèves (24 h avant).
- Météo : `valid_time` = fin de l'heure décrite, en UTC (pluie = cumul de l'heure
  qui se termine à `valid_time` ; température et vent = valeur à `valid_time`).
  Jointure sur `interval_end` du comptage, pour décrire la même heure.
- Disponibilité (hypothèses versionnées, voir `AVAILABILITY`) :
  * prévision Open-Meteo « previous_day N » : issue d'un run initialisé au plus
    tard `valid_time - N×24 h`, publié au plus `RUN_PUBLICATION_DELAY_H` après ;
    `available_at = valid_time - N×24 h + RUN_PUBLICATION_DELAY_H`.
    Avec N = 2, toute l'heure J+1 23:00 est disponible avant une origine J 00:00 ;
    avec N = 1, les dernières heures ne le sont pas (test automatique).
  * observation Météo-France : `available_at = valid_time + OBS_PUBLICATION_LAG_H`.
- Les trois hypothèses (J-N, délai de publication d'un run, latence des observations) se
  règlent dans la section `context` de config/project.yaml ; valeurs par défaut ci-dessus.
- Une entrée n'est admissible pour une origine que si `available_at <= origin`
  (`admissible_context`). Les observations futures servent à l'analyse seulement.

Usage, depuis la racine du dépôt :
  uv run python -m src.data.context --snapshot flux-20261114
  uv run python -m src.data.context --snapshot flux-20261114 --sans-meteo
  uv run python -m src.data.context --snapshot ID --debut 2025-10-11 --fin 2026-11-14
  uv run python -m src.data.context --snapshot flux-20261115 --migrer
  uv run python -m src.data.context --snapshot hist-20261117 --greves
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import re
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from src.common.config import data_path, load_config, relative_to_root
from src.data import acquire

TZ_LOCAL = "Europe/Paris"
CONTEXT_VERSION = "e1-context/0.3.0"
HTTP_TIMEOUT = httpx.Timeout(30.0, read=300.0)

CONTEXT_COLUMNS = [
    "context_source_id",
    "location_id",
    "valid_time",
    "local_date",
    "variable",
    "value",
    "label",
    "unit",
    "role",
    "issued_at",
    "available_at",
    "context_version",
]
# Ancien format (e1-context/0.1.0) : le nom sur une deuxième ligne -> colonne `label`
OLD_NAME_VARIABLES = {"holiday_name": "is_holiday", "school_holiday_name": "is_school_holiday"}
CONTEXT_KEY = ["context_source_id", "location_id", "valid_time", "local_date", "variable"]

ROLE_CALENDAR = "known_calendar"
ROLE_FORECAST = "forecast_bulletin"
ROLE_OBSERVATION = "past_observation"

SRC_HOLIDAYS = "jours_feries"
SRC_SCHOOL = "vacances_zone_c"
SRC_FORECAST = "meteo_prevue"
SRC_OBSERVED = "meteo_observee"
SRC_STRIKES = "greves_idf"

# Référentiel des grèves (Zeineb, versionné dans Git) et délai d'annonce
REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"
STRIKES_FILE = REFERENCE_DIR / "greves_transport_idf.csv"
STRIKES_SOURCES_FILE = REFERENCE_DIR / "greves_transport_idf_sources.csv"
STRIKE_NOTICE_HOURS = 24
LOC_IDF = "IDF-transports"

# Lieux
LOC_FRANCE = "FR-metropole"
LOC_ZONE_C = "zone-C"
PARIS_CENTER = (48.8566, 2.3522)  # Hôtel de Ville
LOC_FORECAST = "openmeteo-48.8566-2.3522"
STATION_MONTSOURIS = "75114001"
LOC_OBSERVED = f"meteofrance-{STATION_MONTSOURIS}"

# Hypothèses de disponibilité : valeurs par défaut. Les valeurs utilisées sont lues dans
# la section `context` de config/project.yaml (à valider avec E4), voir availability_settings().
FORECAST_LEAD_DAYS = 2
RUN_PUBLICATION_DELAY_H = 6
OBS_PUBLICATION_LAG_H = 24

# URL
URL_HOLIDAYS = "https://calendrier.api.gouv.fr/jours-feries/metropole.json"
URL_SCHOOL = (
    "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "fr-en-calendrier-scolaire/exports/csv?delimiter=%3B"
)
URL_FORECAST = "https://previous-runs-api.open-meteo.com/v1/forecast"
# Archive des anciens runs d'Open-Meteo : « Most models are archived from January 2024 »
# (open-meteo.com/en/docs/previous-runs-api). Avant cette date, décision E1 du
# 17/11/2026 : modèle JMA GSM (archivé depuis 2018), puis le modèle par défaut.
FORECAST_ARCHIVE_START = dt.date(2024, 1, 1)
FORECAST_FALLBACK_MODEL = "jma_gsm"
LOC_FORECAST_FALLBACK = f"openmeteo-{FORECAST_FALLBACK_MODEL}-48.8566-2.3522"
# Le modèle par défaut n'a de prévision J-2 qu'à partir du 20/01/2024 12:00 UTC (constaté
# sur hist-20261117) : le repli est demandé un peu au-delà, et la bascule se fait à la
# première heure où le modèle par défaut a une valeur (une seule bascule, pas de mélange).
FORECAST_FALLBACK_OVERLAP_DAYS = 60
URL_METEOFRANCE_DATASET = (
    "https://www.data.gouv.fr/api/1/datasets/donnees-climatologiques-de-base-horaires/"
)

SOURCES = {
    SRC_HOLIDAYS: {
        "name": "Jours fériés officiels, métropole",
        "url": URL_HOLIDAYS,
        "license": "Licence Ouverte 2.0 (Etalab) - à confirmer sur api.gouv.fr",
        "geography": "France métropolitaine",
        "timezone": "dates civiles locales",
        "units": {"is_holiday": "bool", "label": "nom du jour férié (texte), vide sinon"},
        "join": "date locale du début de l'heure comptée",
        "role": ROLE_CALENDAR,
    },
    SRC_SCHOOL: {
        "name": "Calendrier scolaire officiel, zone C (académie de Paris si disponible)",
        "url": URL_SCHOOL,
        "license": "Licence Ouverte 2.0 (Etalab) - à confirmer sur data.education.gouv.fr",
        "geography": "Zone C",
        "timezone": "début et fin convertis en Europe/Paris ; jours [début, fin[",
        "units": {"is_school_holiday": "bool", "label": "nom des vacances (texte), vide sinon"},
        "join": "date locale du début de l'heure comptée",
        "role": ROLE_CALENDAR,
    },
    SRC_STRIKES: {
        "name": "Référentiel des grèves des transports franciliens (E1, Zeineb, liste manuelle)",
        "url": "data/reference/greves_transport_idf.csv (sources : greves_transport_idf_sources.csv)",
        "license": "liste constituée par E1 à partir de pages datées (RATP, Transilien, presse)",
        "geography": "transports en commun d'Île-de-France (RATP, RER, Transilien)",
        "timezone": "dates civiles locales (Europe/Paris)",
        "units": {"is_strike": "bool", "label": "portée, intensité et réseaux, vide sinon"},
        "join": "date locale du début de l'heure comptée",
        "role": ROLE_CALENDAR,
    },
    SRC_FORECAST: {
        "name": "Open-Meteo Previous Runs API, prévision de J-N (Météo-France et autres modèles)",
        "url": URL_FORECAST,
        "license": "CC BY 4.0, attribution Open-Meteo",
        "geography": f"point {PARIS_CENTER[0]}, {PARIS_CENTER[1]} (Hôtel de Ville)",
        "timezone": "UTC (timezone=GMT)",
        "units": {"temp_prev": "degC", "rain_prev": "mm", "wind_prev": "m/s"},
        "join": "interval_end du comptage = valid_time",
        "role": ROLE_FORECAST,
    },
    SRC_OBSERVED: {
        "name": "Météo-France, données climatologiques de base horaires, Paris-Montsouris",
        "url": URL_METEOFRANCE_DATASET,
        "license": "Licence Ouverte 2.0 (Etalab)",
        "geography": f"station {STATION_MONTSOURIS} (Paris-Montsouris)",
        "timezone": "UTC (AAAAMMJJHH)",
        "units": {"temp_obs": "degC", "rain_obs": "mm", "wind_obs": "m/s"},
        "join": "interval_end du comptage = valid_time",
        "role": ROLE_OBSERVATION,
    },
}


def availability_settings() -> dict:
    """Hypothèses de disponibilité lues dans `context` de config/project.yaml (défauts sinon)."""
    cfg = load_config().get("context") or {}
    return {
        "forecast_lead_days": int(cfg.get("forecast_lead_days") or FORECAST_LEAD_DAYS),
        "run_publication_delay_hours": int(
            cfg.get("run_publication_delay_hours", RUN_PUBLICATION_DELAY_H)
        ),
        "obs_publication_lag_hours": int(
            cfg.get("obs_publication_lag_hours", OBS_PUBLICATION_LAG_H)
        ),
        "source": "config/project.yaml (context)" if cfg else "valeurs par défaut de context.py",
    }


def availability_text(source_id: str, s: dict) -> str:
    """Règle de disponibilité d'une source, écrite avec les hypothèses en vigueur."""
    texts = {
        SRC_HOLIDAYS: "Connu à l'avance (fixé par la loi) : admissible pour toute origine.",
        SRC_SCHOOL: "Connu à l'avance (arrêté publié plus d'un an avant) : admissible.",
        SRC_STRIKES: (
            f"Connu au plus tard {STRIKE_NOTICE_HOURS} h avant (prévision de trafic, Code des "
            "transports art. L1222-8 ; notice data/reference/README.md) : available_at = "
            f"minuit (Paris) du jour - {STRIKE_NOTICE_HOURS} h. Recensement manuel, "
            "possiblement incomplet (bus 2023-2025, janvier-avril 2025, février-mai 2026)."
        ),
        SRC_FORECAST: (
            f"Hypothèse : prévision de J-{s['forecast_lead_days']} ; available_at = valid_time - "
            f"{s['forecast_lead_days']}×24 h + {s['run_publication_delay_hours']} h (délai de "
            "publication d'un run). L'heure exacte d'émission n'est pas fournie par l'API ; "
            "issued_at laissé vide."
        ),
        SRC_OBSERVED: (
            f"Hypothèse : available_at = valid_time + {s['obs_publication_lag_hours']} h "
            "(publication quotidienne des données horaires)."
        ),
    }
    return texts[source_id]


# ----------------------------------------------------------------- formats
def fmt_ts(ts: pd.Series) -> pd.Series:
    """Datetime -> texte UTC ISO 8601 ; vide si absent."""
    out = pd.to_datetime(ts, utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return out.fillna("")


def fmt_value(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "true" if v else "false"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return repr(float(v))
    return str(v)


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=CONTEXT_COLUMNS)
    df["value"] = df["value"].map(fmt_value)
    df["context_version"] = CONTEXT_VERSION
    return df.fillna("")


def local_dates(start: dt.date, end: dt.date) -> list[dt.date]:
    return list(pd.date_range(start, end, freq="D").date)


# ----------------------------------------------------------------- calendrier
def parse_holidays(raw: bytes) -> dict[dt.date, str]:
    """JSON {"AAAA-MM-JJ": "nom"} -> {date: nom}."""
    data = json.loads(raw.decode("utf-8"))
    return {dt.date.fromisoformat(k): v for k, v in data.items()}


def holiday_rows(holidays: dict[dt.date, str], days: list[dt.date]) -> list[dict]:
    rows = []
    for d in days:
        name = holidays.get(d)
        base = {
            "context_source_id": SRC_HOLIDAYS,
            "location_id": LOC_FRANCE,
            "valid_time": "",
            "local_date": d.isoformat(),
            "unit": "",
            "role": ROLE_CALENDAR,
            "issued_at": "",
            "available_at": "",
        }
        rows.append(
            {
                **base,
                "variable": "is_holiday",
                "value": name is not None,
                "label": name or "",
                "unit": "bool",
            }
        )
    return rows


def parse_strikes(daily: bytes, sources: bytes) -> dict[dt.date, tuple[bool, str]]:
    """Référentiel des grèves -> {date: (grève, label)} ; label vide un jour sans grève."""
    days = pd.read_csv(io.BytesIO(daily), dtype=str, keep_default_na=False)
    src = pd.read_csv(io.BytesIO(sources), dtype=str, keep_default_na=False)
    labels = {
        r.date: f"{r.scope}, {r.severity} ({r.networks})" for r in src.itertuples(index=False)
    }
    bad = ~days["greve"].isin(["true", "false"])
    if bad.any():
        raise ValueError(f"greve hors true/false : {days.loc[bad, 'date'].tolist()[:5]}")
    return {
        dt.date.fromisoformat(d): (g == "true", labels.get(d, "") if g == "true" else "")
        for d, g in zip(days["date"], days["greve"])
    }


def strike_rows(strikes: dict[dt.date, tuple[bool, str]], days: list[dt.date]) -> list[dict]:
    """Une ligne par jour recensé ; available_at = minuit (Paris) du jour - 24 h."""
    rows = []
    for d in days:
        if d not in strikes:
            continue  # hors de la période recensée : valeur inconnue, pas de ligne
        strike, label = strikes[d]
        midnight = pd.Timestamp(d).tz_localize(TZ_LOCAL).tz_convert("UTC")
        available = midnight - pd.Timedelta(hours=STRIKE_NOTICE_HOURS)
        rows.append(
            {
                "context_source_id": SRC_STRIKES,
                "location_id": LOC_IDF,
                "valid_time": "",
                "local_date": d.isoformat(),
                "variable": "is_strike",
                "value": strike,
                "label": label,
                "unit": "bool",
                "role": ROLE_CALENDAR,
                "issued_at": "",
                "available_at": available.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            }
        )
    return rows


def parse_school(raw: bytes) -> tuple[pd.DataFrame, list[str]]:
    """CSV du calendrier scolaire -> périodes de vacances zone C (Europe/Paris).

    Garde la population élèves (« - » ou « Élèves »), la zone C, l'académie de Paris
    quand elle existe pour l'année scolaire, et supprime les doublons de dates.
    Retourne (start_date, end_date, name) et les alertes.
    """
    alerts: list[str] = []
    df = pd.read_csv(io.BytesIO(raw), sep=";", dtype=str, keep_default_na=False)
    df.columns = [c.strip().lstrip("﻿") for c in df.columns]
    need = {"description", "population", "start_date", "end_date", "location", "zones"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes du calendrier scolaire introuvables : {sorted(missing)}")
    df = df[df["zones"].str.strip().eq("Zone C")]
    df = df[~df["population"].str.contains("Enseignant", case=False)]
    if "annee_scolaire" in df.columns:
        paris = df["location"].str.strip().eq("Paris")
        keep = paris | ~df["annee_scolaire"].isin(set(df.loc[paris, "annee_scolaire"]))
        df = df[keep]
    start = pd.to_datetime(df["start_date"], utc=True, errors="coerce").dt.tz_convert(TZ_LOCAL)
    end = pd.to_datetime(df["end_date"], utc=True, errors="coerce").dt.tz_convert(TZ_LOCAL)
    out = pd.DataFrame(
        {"start": start.dt.date, "end": end.dt.date, "name": df["description"].str.strip()}
    )
    bad = out["start"].isna() | out["end"].isna()
    if bad.any():
        alerts.append(
            f"{int(bad.sum())} périodes de vacances sans date de début ou de fin ignorées."
        )
    out = out[~bad].drop_duplicates(["start", "end"]).sort_values("start").reset_index(drop=True)
    return out, alerts


def school_rows(periods: pd.DataFrame, days: list[dt.date]) -> list[dict]:
    """Un jour est en vacances si start <= jour < end (end = jour de reprise)."""
    name_of: dict[dt.date, str] = {}
    for p in periods.itertuples():
        for d in local_dates(p.start, p.end - dt.timedelta(days=1)) if p.end > p.start else []:
            name_of.setdefault(d, p.name)
    rows = []
    for d in days:
        name = name_of.get(d)
        base = {
            "context_source_id": SRC_SCHOOL,
            "location_id": LOC_ZONE_C,
            "valid_time": "",
            "local_date": d.isoformat(),
            "role": ROLE_CALENDAR,
            "issued_at": "",
            "available_at": "",
        }
        rows.append(
            {
                **base,
                "variable": "is_school_holiday",
                "value": name is not None,
                "label": name or "",
                "unit": "bool",
            }
        )
    return rows


# ----------------------------------------------------------------- météo prévue
def forecast_segments(first_day: dt.date, last_day: dt.date) -> list[dict]:
    """Requêtes de prévision : modèle de repli avant l'archive, modèle par défaut ensuite.

    La veille du premier jour est demandée pour couvrir la première nuit en UTC.
    Chaque segment : model (None = défaut), location_id, start, end (dates incluses).
    """
    wanted = first_day - dt.timedelta(days=1)
    segments = []
    if wanted < FORECAST_ARCHIVE_START:
        segments.append(
            {
                "model": FORECAST_FALLBACK_MODEL,
                "location_id": LOC_FORECAST_FALLBACK,
                "start": wanted,
                "end": min(
                    last_day,
                    FORECAST_ARCHIVE_START + dt.timedelta(days=FORECAST_FALLBACK_OVERLAP_DAYS),
                ),
            }
        )
    if last_day >= FORECAST_ARCHIVE_START:
        segments.append(
            {
                "model": None,
                "location_id": LOC_FORECAST,
                "start": max(wanted, FORECAST_ARCHIVE_START),
                "end": last_day,
            }
        )
    return segments


def merge_forecast_segments(
    fallback: list[dict], default: list[dict]
) -> tuple[list[dict], str | None]:
    """Repli jusqu'à la première heure du modèle par défaut, puis le défaut seul.

    Une seule bascule : aucune heure ne mélange les deux modèles. Retourne (lignes,
    heure de bascule ou None si le défaut est vide).
    """
    switch = min((r["valid_time"] for r in default), default=None)
    if switch is None:
        return fallback, None
    return [r for r in fallback if r["valid_time"] < switch] + default, switch


def forecast_params(start: dt.date, end: dt.date, lead_days: int, model: str | None = None) -> dict:
    hourly = ",".join(
        f"{v}_previous_day{lead_days}"
        for v in ("temperature_2m", "precipitation", "wind_speed_10m")
    )
    extra = {"models": model} if model else {}
    return {
        **extra,
        "latitude": PARIS_CENTER[0],
        "longitude": PARIS_CENTER[1],
        "hourly": hourly,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }


def parse_forecast(
    raw: bytes,
    lead_days: int,
    run_delay_h: int = RUN_PUBLICATION_DELAY_H,
    location_id: str = LOC_FORECAST,
    model: str | None = None,
) -> tuple[list[dict], dict, list[str]]:
    data = json.loads(raw.decode("utf-8"))
    hourly, units = data["hourly"], data.get("hourly_units", {})
    if model:  # avec `models=`, certaines réponses suffixent les clés par le modèle
        suffix = f"_{model}"
        hourly = {k.removesuffix(suffix): v for k, v in hourly.items()}
        units = {k.removesuffix(suffix): v for k, v in units.items()}
    alerts: list[str] = []
    wind_key = f"wind_speed_10m_previous_day{lead_days}"
    if units.get(wind_key) not in (None, "m/s"):
        raise ValueError(f"Unité du vent inattendue : {units.get(wind_key)} (m/s attendu)")
    time = pd.to_datetime(pd.Series(hourly["time"]), utc=True)
    available = time - pd.Timedelta(hours=24 * lead_days - run_delay_h)
    mapping = {
        "temp_prev": (f"temperature_2m_previous_day{lead_days}", "degC"),
        "rain_prev": (f"precipitation_previous_day{lead_days}", "mm"),
        "wind_prev": (wind_key, "m/s"),
    }
    fill = {}
    rows = []
    for variable, (key, unit) in mapping.items():
        values = pd.to_numeric(pd.Series(hourly.get(key, [None] * len(time))), errors="coerce")
        fill[variable] = round(float(values.notna().mean()), 4) if len(values) else 0.0
        if fill[variable] < 0.99:
            alerts.append(f"{variable} renseigné à {fill[variable]:.1%} seulement.")
        for t, a, v in zip(fmt_ts(time), fmt_ts(available), values):
            if pd.isna(v):
                continue
            rows.append(
                {
                    "context_source_id": SRC_FORECAST,
                    "location_id": location_id,
                    "valid_time": t,
                    "local_date": "",
                    "variable": variable,
                    "value": float(v),
                    "unit": unit,
                    "role": ROLE_FORECAST,
                    "issued_at": "",
                    "available_at": a,
                }
            )
    return rows, {"lead_days": lead_days, "fill_rate": fill, "units": units}, alerts


# ----------------------------------------------------------------- météo observée
def _period_years(title: str) -> tuple[int, int] | None:
    m = re.search(r"(\d{4})-(\d{4})", title)
    return (int(m.group(1)), int(m.group(2))) if m else None


def meteofrance_resources(dataset_json: dict, start: dt.date, end: dt.date) -> list[dict]:
    """Fichiers horaires du département 75 dont la période recouvre [start, end]."""
    out = []
    for r in dataset_json.get("resources", []):
        label = f"{r.get('title', '')} {r.get('url', '')}"
        if not re.search(r"(?:departement_75|H_75_)", label):
            continue
        years = _period_years(label)
        if years and years[0] <= end.year and years[1] >= start.year:
            out.append(r)
    return out


def parse_observed(
    raw: bytes, station: str = STATION_MONTSOURIS, lag_h: int = OBS_PUBLICATION_LAG_H
) -> tuple[list[dict], dict]:
    text = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    df = pd.read_csv(io.BytesIO(text), sep=";", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    df = df[df["NUM_POSTE"].str.strip() == station]
    time = pd.to_datetime(df["AAAAMMJJHH"].str.strip(), format="%Y%m%d%H", utc=True)
    available = time + pd.Timedelta(hours=lag_h)
    mapping = {"temp_obs": ("T", "degC"), "rain_obs": ("RR1", "mm"), "wind_obs": ("FF", "m/s")}
    fill, rows = {}, []
    for variable, (col, unit) in mapping.items():
        if col not in df.columns:
            fill[variable] = 0.0
            continue
        values = pd.to_numeric(df[col].str.strip().str.replace(",", "."), errors="coerce")
        fill[variable] = round(float(values.notna().mean()), 4) if len(values) else 0.0
        for t, a, v in zip(fmt_ts(time), fmt_ts(available), values):
            if pd.isna(v):
                continue
            rows.append(
                {
                    "context_source_id": SRC_OBSERVED,
                    "location_id": LOC_OBSERVED,
                    "valid_time": t,
                    "local_date": "",
                    "variable": variable,
                    "value": float(v),
                    "unit": unit,
                    "role": ROLE_OBSERVATION,
                    "issued_at": "",
                    "available_at": a,
                }
            )
    return rows, {"station": station, "n_station_rows": int(len(df)), "fill_rate": fill}


def keep_period(rows: list[dict], start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """Garde les lignes météo dont valid_time est dans [start, end]."""
    out = []
    for r in rows:
        t = pd.Timestamp(r["valid_time"])
        if start <= t <= end:
            out.append(r)
    return out


# ----------------------------------------------------------------- validation et jointure
def validate_context(ctx: pd.DataFrame) -> None:
    if list(ctx.columns) != CONTEXT_COLUMNS:
        raise ValueError(f"Colonnes de context.csv non conformes : {list(ctx.columns)}")
    dup = ctx.duplicated(CONTEXT_KEY)
    if dup.any():
        raise ValueError(f"{int(dup.sum())} lignes de contexte en double sur {CONTEXT_KEY}")
    bad_bool = ctx["unit"].eq("bool") & ~ctx["value"].isin(["true", "false"])
    if bad_bool.any():
        raise ValueError("Booléens hors true/false dans context.csv")


def admissible_context(ctx: pd.DataFrame, origin: pd.Timestamp) -> pd.DataFrame:
    """Lignes utilisables comme entrées pour une origine.

    Calendrier sans `available_at` (connu à l'avance) : toujours ; toute ligne qui a un
    `available_at` (météo, grèves) : seulement si `available_at <= origin`.
    """
    origin = pd.Timestamp(origin).tz_convert("UTC")
    avail = pd.to_datetime(ctx["available_at"].replace("", np.nan), utc=True)
    ok = (ctx["role"].eq(ROLE_CALENDAR) & avail.isna()) | (avail <= origin)
    return ctx[ok.fillna(False)]


def wide_calendar(ctx: pd.DataFrame) -> pd.DataFrame:
    """Une colonne par variable du calendrier, et son nom dans `<variable>_label`."""
    cal = ctx[ctx["role"] == ROLE_CALENDAR]
    if cal.empty:
        return pd.DataFrame(columns=["local_date"])
    values = cal.pivot(index="local_date", columns="variable", values="value")
    labels = cal.pivot(index="local_date", columns="variable", values="label")
    labels.columns = [f"{v}_label" for v in labels.columns]
    return values.join(labels).reset_index()


def migrate_calendar(old: pd.DataFrame) -> pd.DataFrame:
    """Ancien context.csv (nom sur une 2e ligne, sans `label`) -> format à une ligne.

    Aucune valeur n'est recalculée : le nom de la ligne `holiday_name` (ou
    `school_holiday_name`) passe dans `label` de la ligne `is_holiday` (ou
    `is_school_holiday`) du même jour, puis la ligne du nom est retirée.
    """
    if "label" in old.columns:
        return old.copy()
    df = old.copy()
    df["label"] = ""
    for name_var, flag_var in OLD_NAME_VARIABLES.items():
        names = df[df["variable"] == name_var]
        key = ["context_source_id", "location_id", "local_date"]
        lookup = names.set_index(key)["value"]
        flags = df["variable"] == flag_var
        idx = pd.MultiIndex.from_frame(df.loc[flags, key])
        df.loc[flags, "label"] = lookup.reindex(idx).fillna("").to_numpy()
        df = df[df["variable"] != name_var]
    df["context_version"] = CONTEXT_VERSION
    return df[CONTEXT_COLUMNS].reset_index(drop=True)


def wide_weather(ctx: pd.DataFrame) -> pd.DataFrame:
    w = ctx[ctx["role"].isin([ROLE_FORECAST, ROLE_OBSERVATION])]
    if w.empty:
        return pd.DataFrame(columns=["valid_time"])
    out = w.pivot(index="valid_time", columns="variable", values="value").reset_index()
    return out


def join_context(counts: pd.DataFrame, ctx: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Joint le contexte (format large) aux comptages et audite la cardinalité.

    `counts` doit contenir `timestamp` et `interval_end` (texte UTC ISO, comme
    counts.csv). Lève une erreur si la jointure crée ou perd des lignes.
    """
    n_before = len(counts)
    key_dup = int(counts.duplicated(["counter_id", "timestamp"]).sum())
    out = counts.copy()
    start = pd.to_datetime(out["timestamp"], utc=True)
    out["local_date"] = start.dt.tz_convert(TZ_LOCAL).dt.date.astype(str)

    cal = wide_calendar(ctx)
    out = out.merge(cal, on="local_date", how="left", validate="many_to_one")
    weather = wide_weather(ctx)
    out = out.merge(
        weather.rename(columns={"valid_time": "interval_end"}),
        on="interval_end",
        how="left",
        validate="many_to_one",
    )
    if len(out) != n_before:
        raise ValueError(f"La jointure a changé le nombre de lignes : {n_before} -> {len(out)}")

    audit = {"n_rows_before": n_before, "n_rows_after": len(out), "duplicate_keys": key_dup}
    for col in [c for c in out.columns if c not in counts.columns and c != "local_date"]:
        missing = out[col].isna()
        audit[col] = {
            "n_unmatched": int(missing.sum()),
            "unmatched_share": round(float(missing.mean()), 4),
            "first_unmatched": None
            if not missing.any()
            else str(out.loc[missing, "timestamp"].iloc[0]),
        }
    return out, audit


# ----------------------------------------------------------------- acquisition des bruts
def context_dir(snapshot_id: str) -> Path:
    return data_path("history") / snapshot_id / "context"


def fetch(url: str, dest: Path, params: dict | None = None, force: bool = False) -> bytes:
    """Télécharge une fois et conserve le brut intact ; relit le fichier ensuite."""
    if dest.exists() and not force:
        return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = httpx.get(url, params=params, timeout=HTTP_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return resp.content


def period_from_counts(snapshot_id: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    path = data_path("processed") / snapshot_id / "counts.csv"
    if not path.exists():
        return None
    ts = pd.read_csv(path, usecols=["timestamp"], dtype=str)["timestamp"]
    ts = pd.to_datetime(ts, utc=True)
    return ts.min(), ts.max() + pd.Timedelta(hours=1)


# ----------------------------------------------------------------- orchestration
def strikes_for(days: list[dt.date]) -> tuple[list[dict], dict]:
    """Lignes de grève des jours donnés, et fiche de la source."""
    strikes = parse_strikes(STRIKES_FILE.read_bytes(), STRIKES_SOURCES_FILE.read_bytes())
    rows = strike_rows(strikes, days)
    covered = {dt.date.fromisoformat(r["local_date"]) for r in rows}
    missing = [d for d in days if d not in covered]
    alerts = []
    if missing:
        alerts.append(
            f"{len(missing)} jour(s) hors du référentiel (du {min(missing)} au {max(missing)}) : "
            "pas de ligne, valeur inconnue."
        )
    sheet = {
        "raw_file": [relative_to_root(STRIKES_FILE), relative_to_root(STRIKES_SOURCES_FILE)],
        "n_days": len(rows),
        "n_strike_days": sum(1 for r in rows if r["value"] is True),
        "alerts": alerts,
    }
    return rows, sheet


def build_context(
    snapshot_id: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    meteo: bool = True,
    lead_days: int | None = None,
    force: bool = False,
) -> tuple[pd.DataFrame, dict, list[Path]]:
    settings = availability_settings()
    if lead_days is not None:
        settings["forecast_lead_days"] = lead_days
        settings["source"] += " ; J-N remplacé par --lead"
    lead_days = settings["forecast_lead_days"]
    raw_dir = context_dir(snapshot_id)
    first_day = start.tz_convert(TZ_LOCAL).date()
    last_day = end.tz_convert(TZ_LOCAL).date()
    days = local_dates(first_day, last_day)
    sheets: dict[str, dict] = {}
    raw_files: list[Path] = []
    rows: list[dict] = []
    retrieved = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    path = raw_dir / "jours_feries_metropole.json"
    rows += holiday_rows(parse_holidays(fetch(URL_HOLIDAYS, path, force=force)), days)
    raw_files.append(path)
    sheets[SRC_HOLIDAYS] = {"raw_file": relative_to_root(path)}

    path = raw_dir / "calendrier_scolaire.csv"
    periods, alerts = parse_school(fetch(URL_SCHOOL, path, force=force))
    rows += school_rows(periods, days)
    raw_files.append(path)
    sheets[SRC_SCHOOL] = {
        "raw_file": relative_to_root(path),
        "alerts": alerts,
        "n_periods": int(len(periods)),
    }
    covered = periods[(periods["end"] > first_day) & (periods["start"] <= last_day)]
    if covered.empty:
        sheets[SRC_SCHOOL]["alerts"].append("Aucune période de vacances sur la période.")

    s_rows, s_sheet = strikes_for(days)
    rows += s_rows
    sheets[SRC_STRIKES] = s_sheet
    raw_files += [STRIKES_FILE, STRIKES_SOURCES_FILE]

    if meteo:
        f_alerts, segments, seg_rows = [], [], []
        for seg in forecast_segments(first_day, last_day):
            params = forecast_params(seg["start"], seg["end"], lead_days, seg["model"])
            name = f"openmeteo_previous_day{lead_days}"
            if seg["model"]:
                name += f"_{seg['model']}"
            path = raw_dir / f"{name}.json"
            rows_seg, info, alerts_seg = parse_forecast(
                fetch(URL_FORECAST, path, params=params, force=force),
                lead_days,
                settings["run_publication_delay_hours"],
                location_id=seg["location_id"],
                model=seg["model"],
            )
            seg_start = pd.Timestamp(seg["start"], tz="UTC")
            seg_end = pd.Timestamp(seg["end"] + dt.timedelta(days=1), tz="UTC")
            seg_rows.append(keep_period(rows_seg, seg_start, seg_end))
            f_alerts += [f"{seg['model'] or 'défaut'} : {x}" for x in alerts_seg]
            raw_files.append(path)
            segments.append(
                {
                    "model": seg["model"] or "défaut (best_match)",
                    "location_id": seg["location_id"],
                    "from": seg["start"].isoformat(),
                    "to": seg["end"].isoformat(),
                    "raw_file": relative_to_root(path),
                    "request": params,
                    **info,
                }
            )
        if len(segments) > 1:
            f_rows, switch = merge_forecast_segments(*seg_rows)
            if switch is not None:
                segments[0]["to_valid_time_excluded"] = switch
                segments[1]["from_valid_time"] = switch
            f_alerts.append(
                f"Prévision du modèle {FORECAST_FALLBACK_MODEL} jusqu'à {switch} (exclu), "
                "puis du modèle par défaut : deux sources, une seule bascule (voir segments "
                "et location_id)."
            )
        else:
            f_rows = seg_rows[0] if seg_rows else []
        rows += keep_period(f_rows, start, end + pd.Timedelta(hours=1))
        sheets[SRC_FORECAST] = {"segments": segments, "lead_days": lead_days, "alerts": f_alerts}

        listing = json.loads(
            fetch(URL_METEOFRANCE_DATASET, raw_dir / "meteofrance_ressources.json", force=force)
        )
        resources = meteofrance_resources(listing, first_day, last_day)
        o_rows, o_info = [], {}
        for r in resources:
            name = re.sub(r"[^\w.-]", "_", r.get("title") or Path(r["url"]).name)
            path = raw_dir / f"{name}.csv.gz"
            part, o_info = parse_observed(
                fetch(r["url"], path, force=force),
                lag_h=settings["obs_publication_lag_hours"],
            )
            o_rows += part
            raw_files.append(path)
        obs = pd.DataFrame(o_rows).drop_duplicates(["valid_time", "variable"]).to_dict("records")
        rows += keep_period(obs, start, end + pd.Timedelta(hours=1))
        sheets[SRC_OBSERVED] = {"files": [r.get("title") for r in resources], **o_info}

    for sid, sheet in sheets.items():
        sheet.update(
            {
                **SOURCES[sid],
                "context_source_id": sid,
                "retrieved_at": retrieved,
                "availability": availability_text(sid, settings),
                "assumptions": settings,
                "context_version": CONTEXT_VERSION,
            }
        )
    ctx = _frame(rows)
    validate_context(ctx)
    return ctx, sheets, raw_files


def update_manifest(
    snapshot_id: str, paths: dict[str, Path], raw_files: list[Path], sheets: dict
) -> Path:
    manifest = acquire.load_manifest(snapshot_id)
    for p in raw_files:
        acquire.upsert(manifest["files"], acquire.file_entry(p, "context_raw"), "path")
    for role, p in paths.items():
        if p.exists():
            acquire.upsert(manifest["files"], acquire.file_entry(p, role), "path")
    for sid, sheet in sheets.items():
        source = {
            "source_id": sid,
            "url": sheet.get("url"),
            "license": sheet.get("license"),
            "retrieved_at": sheet.get("retrieved_at"),
            "role": sheet.get("role"),
        }
        acquire.upsert(manifest["sources"], source, "source_id")
    manifest["context_version"] = CONTEXT_VERSION
    first = next(iter(sheets.values()), {})
    manifest["context_assumptions"] = first.get("assumptions")
    return acquire.write_manifest(manifest)


def run(
    snapshot_id: str,
    debut: str | None = None,
    fin: str | None = None,
    meteo: bool = True,
    lead_days: int | None = None,
    force: bool = False,
) -> dict:
    period = period_from_counts(snapshot_id)
    if debut and fin:
        start = pd.Timestamp(debut, tz=TZ_LOCAL).tz_convert("UTC")
        end = (pd.Timestamp(fin, tz=TZ_LOCAL) + pd.Timedelta(days=1)).tz_convert("UTC")
    elif period:
        start, end = period
    else:
        raise SystemExit("counts.csv absent : préciser --debut et --fin (dates locales).")

    ctx, sheets, raw_files = build_context(snapshot_id, start, end, meteo, lead_days, force)
    out_dir = data_path("processed") / snapshot_id
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "context": out_dir / "context.csv",
        "context_sources": out_dir / "context_sources.json",
        "context_join_audit": out_dir / "context_join_audit.json",
    }
    ctx.to_csv(paths["context"], index=False)
    paths["context_sources"].write_text(
        json.dumps(sheets, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )

    counts_path = out_dir / "counts.csv"
    audit = {"status": "counts.csv absent : jointure non auditée"}
    if counts_path.exists():
        counts = pd.read_csv(
            counts_path,
            dtype=str,
            keep_default_na=False,
            usecols=["counter_id", "timestamp", "interval_end"],
        )
        _, audit = join_context(counts, ctx)
        audit["status"] = "ok"
    paths["context_join_audit"].write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = update_manifest(snapshot_id, paths, raw_files, sheets)

    print(f"Contexte {CONTEXT_VERSION} : {len(ctx)} lignes")
    print(f"Hypothèses de disponibilité : {next(iter(sheets.values()))['assumptions']}")
    print(ctx.groupby(["context_source_id", "variable"]).size().to_string())
    print("\nAudit de jointure :")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    for sid, sheet in sheets.items():
        for a in sheet.get("alerts", []):
            print(f"Alerte {sid} : {a}")
    print("\nFichiers :")
    for p in [*paths.values(), manifest]:
        print(f"- {relative_to_root(p)}")
    return {"context": ctx, "audit": audit, "sheets": sheets}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané, ex. flux-20261114")
    ap.add_argument("--debut", help="date locale de début (sinon : bornes de counts.csv)")
    ap.add_argument("--fin", help="date locale de fin, incluse")
    ap.add_argument("--sans-meteo", action="store_true", help="calendrier seulement")
    ap.add_argument(
        "--lead",
        type=int,
        default=None,
        help="prévision de J-N (défaut : config/project.yaml, sinon 2)",
    )
    ap.add_argument("--force", action="store_true", help="retélécharger les bruts")
    ap.add_argument(
        "--migrer",
        action="store_true",
        help="convertir context.csv existant au format à une ligne (sans téléchargement)",
    )
    ap.add_argument(
        "--greves",
        action="store_true",
        help="ajouter les grèves (référentiel E1) à context.csv existant (sans téléchargement)",
    )
    args = ap.parse_args(argv)
    if args.migrer:
        migrate(args.snapshot)
        return 0
    if args.greves:
        add_strikes(args.snapshot)
        return 0
    run(args.snapshot, args.debut, args.fin, not args.sans_meteo, args.lead, args.force)
    return 0


def migrate(snapshot_id: str) -> None:
    """Réécrit context.csv au format à une ligne, met à jour la fiche et le manifeste."""
    out_dir = data_path("processed") / snapshot_id
    path = out_dir / "context.csv"
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    new = migrate_calendar(old)
    validate_context(new)
    new.to_csv(path, index=False)
    sheets_path = out_dir / "context_sources.json"
    if sheets_path.exists():
        sheets = json.loads(sheets_path.read_text(encoding="utf-8"))
        for sid in (SRC_HOLIDAYS, SRC_SCHOOL):
            if sid in sheets:
                sheets[sid]["units"] = SOURCES[sid]["units"]
                sheets[sid]["context_version"] = CONTEXT_VERSION
        sheets_path.write_text(
            json.dumps(sheets, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
        )
    audit_path = out_dir / "context_join_audit.json"
    counts_path = out_dir / "counts.csv"
    if counts_path.exists():
        counts = pd.read_csv(
            counts_path,
            dtype=str,
            keep_default_na=False,
            usecols=["counter_id", "timestamp", "interval_end"],
        )
        _, audit = join_context(counts, new)
        audit["status"] = "ok"
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    manifest = acquire.load_manifest(snapshot_id)
    files = (
        ("context", path),
        ("context_sources", sheets_path),
        ("context_join_audit", audit_path),
    )
    for role, p in files:
        if p.exists():
            acquire.upsert(manifest["files"], acquire.file_entry(p, role), "path")
    manifest["context_version"] = CONTEXT_VERSION
    acquire.write_manifest(manifest)
    print(f"context.csv : {len(old)} -> {len(new)} lignes ({CONTEXT_VERSION})")
    print(new.groupby(["context_source_id", "variable"]).size().to_string())


def with_strikes(ctx: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """context.csv avec les lignes de grève des jours de son calendrier (remplacées si présentes)."""
    base = migrate_calendar(ctx)
    base = base[base["context_source_id"] != SRC_STRIKES]
    days = sorted(
        {dt.date.fromisoformat(d) for d in base.loc[base["role"] == ROLE_CALENDAR, "local_date"]}
    )
    rows, sheet = strikes_for(days)
    out = pd.concat([base, _frame(rows)], ignore_index=True)
    out["context_version"] = CONTEXT_VERSION
    validate_context(out)
    return out[CONTEXT_COLUMNS], sheet


def add_strikes(snapshot_id: str) -> None:
    """Ajoute les grèves à context.csv, met à jour la fiche, l'audit et le manifeste."""
    out_dir = data_path("processed") / snapshot_id
    path = out_dir / "context.csv"
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    new, sheet = with_strikes(old)
    new.to_csv(path, index=False)
    sheets_path = out_dir / "context_sources.json"
    sheets = json.loads(sheets_path.read_text(encoding="utf-8")) if sheets_path.exists() else {}
    first = next(iter(sheets.values()), {})
    settings = first.get("assumptions") or availability_settings()
    sheets[SRC_STRIKES] = {
        **sheet,
        **SOURCES[SRC_STRIKES],
        "context_source_id": SRC_STRIKES,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "availability": availability_text(SRC_STRIKES, settings),
        "assumptions": settings,
        "context_version": CONTEXT_VERSION,
    }
    for s in sheets.values():
        s["context_version"] = CONTEXT_VERSION
    sheets_path.write_text(
        json.dumps(sheets, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    audit_path = out_dir / "context_join_audit.json"
    counts_path = out_dir / "counts.csv"
    if counts_path.exists():
        counts = pd.read_csv(
            counts_path,
            dtype=str,
            keep_default_na=False,
            usecols=["counter_id", "timestamp", "interval_end"],
        )
        _, audit = join_context(counts, new)
        audit["status"] = "ok"
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    paths = {"context": path, "context_sources": sheets_path, "context_join_audit": audit_path}
    update_manifest(
        snapshot_id, paths, [STRIKES_FILE, STRIKES_SOURCES_FILE], {SRC_STRIKES: sheets[SRC_STRIKES]}
    )
    print(f"context.csv : {len(old)} -> {len(new)} lignes ({CONTEXT_VERSION})")
    print(f"Grèves : {sheet['n_days']} jours, dont {sheet['n_strike_days']} de grève")
    for a in sheet["alerts"]:
        print(f"Alerte : {a}")


if __name__ == "__main__":
    sys.exit(main())

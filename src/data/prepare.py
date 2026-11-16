"""Construction de la vérité terrain horaire partagée - E1.

Lit un brut de `data/history/<snapshot_id>/`, produit
`data/processed/<snapshot_id>/counts.csv` et `counters.csv` (colonnes exactes
de `doc/templates/`), affiche les contrôles et complète le manifeste.

Conventions (doc/CONTRATS.md §1 et §3) :
- `timestamp` = début de l'heure en UTC ISO 8601, `interval_end` = +1 h ;
- grille horaire complète : heure absente -> `is_observed=false`, `count` vide ;
- un zéro observé reste un zéro ;
- `quality_flags` = liste JSON ; drapeaux définis dans `FLAG_DEFINITIONS` ;
- `is_scoreable` = mesure présente, valeur non négative et non conflictuelle.
  Règle structurelle, indépendante de la méthode ; un zéro prolongé reste
  évaluable.

Grille commune (décision E1, étape 2) : avec `--tout`, chaque compteur a les
mêmes heures, du début à la fin de l'instantané. Une heure où le compteur ne
mesure pas (avant son installation, après son arrêt) est une ligne avec
`is_observed=false` et le drapeau `missing`, jamais une ligne absente.

Usage, depuis la racine du dépôt (normalement enchaîné par acquire) :
  uv run python -m src.data.prepare --snapshot flux-20261115 --tout
  uv run python -m src.data.prepare --snapshot flux-20261112 --compteur ID

Logique reprise de l'ancien script de l'équipe (parispulse-equipe01,
commit 5488590, src/phase0.py), avec trois corrections : heures ambiguës du
changement d'heure signalées au lieu d'être supprimées, doublons en conflit
signalés au lieu d'un keep="first" silencieux, `in_zero_run` remplacé par le
drapeau rétrospectif `long_zero_run`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path, relative_to_root
from src.data import acquire
from src.data.quality import (
    SITE_GROUP_RULE,
    SelectionCriteria,
    candidate_site_groups,
    network_gap_hours,
)

TZ_LOCAL = "Europe/Paris"
LONG_ZERO_RUN_HOURS = 24  # seuil d'une suite de zéros « longue » (heures consécutives)
NORMALIZATION_VERSION = "e1-prepare/0.2.2"
# Seuil défini une seule fois, dans quality.SelectionCriteria
NETWORK_GAP_SHARE = SelectionCriteria.network_gap_share

COUNTS_COLUMNS = [
    "counter_id",
    "timestamp",
    "interval_end",
    "count_raw",
    "count",
    "is_observed",
    "is_scoreable",
    "quality_flags",
    "source_file_id",
    "snapshot_id",
]
COUNTERS_COLUMNS = [
    "counter_id",
    "site_id",
    "site_group_id",
    "counter_name",
    "site_name",
    "latitude",
    "longitude",
    "direction",
    "installation_date",
    "snapshot_id",
]

# Drapeaux de qualité (vocabulaire partagé avec E2-E5)
FLAG_MISSING = "missing"
FLAG_EMPTY_VALUE = "empty_value"
FLAG_INVALID_VALUE = "invalid_value"
FLAG_NEGATIVE = "negative"
FLAG_DUPLICATE = "duplicate"
FLAG_CONFLICT = "conflict"
FLAG_LONG_ZERO_RUN = "long_zero_run"
FLAG_DST_AMBIGUOUS = "dst_ambiguous"
FLAG_DST_NONEXISTENT = "dst_nonexistent"
FLAG_NETWORK_GAP = "network_gap"

FLAG_DEFINITIONS = {
    FLAG_MISSING: "Heure de grille absente de la source ; count vide, non évaluable.",
    FLAG_EMPTY_VALUE: "Ligne source présente mais valeur vide ; traitée comme non observée.",
    FLAG_INVALID_VALUE: "Valeur source non numérique ; count_raw et count vides.",
    FLAG_NEGATIVE: "Valeur négative ; count_raw conservé, count vide, non évaluable.",
    FLAG_DUPLICATE: "Plusieurs lignes source pour la même heure, valeurs identiques ; "
    "une seule valeur conservée.",
    FLAG_CONFLICT: "Plusieurs lignes source pour la même heure, valeurs différentes ; "
    "count_raw et count vides, non évaluable, valeurs dans audit_duplicates.csv.",
    FLAG_LONG_ZERO_RUN: f"Zéro observé dans une suite d'au moins {LONG_ZERO_RUN_HOURS} h "
    "consécutives de zéros. Diagnostic RÉTROSPECTIF (utilise des heures postérieures) : "
    "ne pas l'utiliser comme variable de prévision. Le zéro reste évaluable.",
    FLAG_DST_AMBIGUOUS: "Heure locale sans décalage répétée au passage à l'heure d'hiver ; "
    "1re occurrence = heure d'été, 2e = heure d'hiver (ordre du fichier).",
    FLAG_DST_NONEXISTENT: "Heure locale sans décalage inexistante au passage à l'heure "
    "d'été ; décalée à l'heure suivante.",
    FLAG_NETWORK_GAP: f"Heure non observée pendant laquelle au moins {NETWORK_GAP_SHARE:.0%} "
    "des compteurs actifs sont sans mesure (panne ou publication, pas le compteur). "
    "Posé seulement sur un compteur actif à cette heure (entre sa première et sa dernière "
    "mesure), jamais avant son installation ni après son arrêt. Toujours avec 'missing' "
    "ou 'empty_value'. Posé seulement par la préparation de tout le flux (--tout).",
}

# Sens en fin de nom : « ... S-N », « ... SO-NE » (points cardinaux en français)
DIRECTION_PATTERN = r"^(N|S|E|O|NE|NO|SE|SO)-(N|S|E|O|NE|NO|SE|SO)$"


def direction_from_name(name) -> str | None:
    """Sens tiré de la fin du nom (`S-N`, `SO-NE`...), ou None s'il n'y en a pas."""
    text = str(name or "").strip()
    tail = text.rsplit(" ", 1)[-1] if " " in text else ""
    return tail if re.fullmatch(DIRECTION_PATTERN, tail) else None


def opposite(direction: str) -> str:
    a, b = direction.split("-")
    return f"{b}-{a}"

# Noms techniques (API) et libellés (exports du site / archives) -> noms internes
COLUMN_MAP = {
    "id_compteur": "counter_id",
    "Identifiant du compteur": "counter_id",
    "nom_compteur": "counter_name",
    "Nom du compteur": "counter_name",
    "id": "site_id",
    "Identifiant du site de comptage": "site_id",
    "name": "site_name",
    "Nom du site de comptage": "site_name",
    "sum_counts": "count",
    "Comptage horaire": "count",
    "date": "date_source",
    "Date et heure de comptage": "date_source",
    "installation_date": "installation_date",
    "Date d'installation du site de comptage": "installation_date",
    "coordinates": "coordinates",
    "Coordonnées géographiques": "coordinates",
}
REQUIRED_COLUMNS = {"counter_id", "count", "date_source"}


@dataclass
class Prepared:
    """Résultat de la normalisation d'un compteur."""

    counts: pd.DataFrame  # ts (UTC), count_raw, count, is_observed, is_scoreable, flags
    counter: dict
    report: dict
    audit: pd.DataFrame
    alerts: list[str] = field(default_factory=list)


# ----------------------------------------------------------------- horodatage
def parse_timestamps(dates: pd.Series) -> tuple[pd.Series, pd.Series, list[str]]:
    """Convertit en UTC. Retourne (ts, drapeaux par ligne, alertes).

    Avec décalage explicite : conversion directe. Sans décalage : heure de Paris
    supposée, heures ambiguës et inexistantes conservées et signalées.
    """
    s = dates.astype(str).str.strip()
    alerts: list[str] = []
    ts = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns, UTC]")
    flags = pd.Series([[] for _ in range(len(s))], index=s.index, dtype=object)

    has_offset = s.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
    if has_offset.any():
        ts[has_offset] = pd.to_datetime(s[has_offset], utc=True, format="ISO8601", errors="coerce")

    naive = ~has_offset & s.ne("")
    if naive.any():
        alerts.append(
            f"{int(naive.sum())} dates SANS fuseau : interprétées en heure de Paris (à confirmer)."
        )
        loc = pd.to_datetime(s[naive], format="ISO8601", errors="coerce")
        first = loc.dt.tz_localize(TZ_LOCAL, ambiguous="NaT", nonexistent="NaT")
        ts[naive] = first.dt.tz_convert("UTC")
        problem = loc[first.isna() & loc.notna()]
        if len(problem):
            probe = problem.dt.tz_localize(
                TZ_LOCAL, ambiguous=np.ones(len(problem), dtype=bool), nonexistent="NaT"
            )
            amb = problem[probe.notna()]
            nonex = problem[probe.isna()]
            if len(amb):
                is_dst = (amb.groupby(amb).cumcount() == 0).to_numpy()
                ts[amb.index] = amb.dt.tz_localize(TZ_LOCAL, ambiguous=is_dst).dt.tz_convert("UTC")
                for i in amb.index:
                    flags[i] = flags[i] + [FLAG_DST_AMBIGUOUS]
                alerts.append(
                    f"{len(amb)} lignes à heure locale ambiguë (passage à l'heure d'hiver) "
                    "conservées et signalées."
                )
            if len(nonex):
                ts[nonex.index] = nonex.dt.tz_localize(
                    TZ_LOCAL, nonexistent="shift_forward"
                ).dt.tz_convert("UTC")
                for i in nonex.index:
                    flags[i] = flags[i] + [FLAG_DST_NONEXISTENT]
                alerts.append(
                    f"{len(nonex)} lignes à heure locale inexistante (passage à l'heure d'été) "
                    "décalées et signalées."
                )
    return ts, flags, alerts


# ----------------------------------------------------------------- normalisation
def _run_lengths(mask: pd.Series) -> pd.Series:
    """Longueur de la suite de True contenant chaque position (0 ailleurs)."""
    block = (mask != mask.shift()).cumsum()
    return mask.groupby(block).transform("sum").where(mask, 0).astype(int)


def _parse_coordinates(value) -> tuple[float, float]:
    if isinstance(value, str) and "," in value:
        try:
            lat, lon = (float(x) for x in value.split(",")[:2])
            return lat, lon
        except ValueError:
            pass
    return np.nan, np.nan


def normalize(
    raw: pd.DataFrame,
    counter_id: str,
    grid_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> Prepared:
    """Normalise le brut d'un compteur sur une grille horaire UTC complète.

    `grid_range` = (première, dernière heure UTC de l'instantané) : grille
    commune à tous les compteurs. Sans elle, la grille va de la première à la
    dernière heure du compteur (usage compteur par compteur).
    """
    df = raw.rename(columns=lambda c: COLUMN_MAP.get(str(c).lstrip("﻿"), c))
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Colonnes introuvables : {sorted(missing_cols)} ; lues : {list(raw.columns)}"
        )
    df = df[df["counter_id"].astype(str) == str(counter_id)].reset_index(drop=True)
    if df.empty:
        raise ValueError(f"Aucune ligne pour le compteur {counter_id}.")

    alerts: list[str] = []
    ts, row_flags, ts_alerts = parse_timestamps(df["date_source"])
    alerts += ts_alerts
    df["ts"] = ts
    df["row_flags"] = row_flags

    raw_values = df["count"].astype(str).str.strip()
    df["value"] = pd.to_numeric(raw_values.replace("", np.nan), errors="coerce")
    df["is_empty"] = raw_values.eq("")
    df["is_invalid"] = ~df["is_empty"] & df["value"].isna()

    bad_ts = df["ts"].isna()
    off_hour = df["ts"].notna() & ((df["ts"].dt.minute != 0) | (df["ts"].dt.second != 0))
    if bad_ts.any():
        alerts.append(f"{int(bad_ts.sum())} lignes à date illisible, non placées sur la grille.")
    if off_hour.any():
        alerts.append(
            f"{int(off_hour.sum())} lignes hors de l'heure pile : granularité à vérifier, "
            "non placées sur la grille."
        )
    rows = df[~bad_ts & ~off_hour]

    # Agrégation par heure : doublons explicites, jamais de keep="first" silencieux
    g = rows.groupby("ts", sort=True)
    hours = pd.DataFrame(
        {
            "n_rows": g.size(),
            "n_values": g["value"].nunique(dropna=False),
            "value": g["value"].first(),
            "all_empty": g["is_empty"].all(),
            "any_invalid": g["is_invalid"].any(),
        }
    )
    hours["row_flags"] = pd.Series(
        {k: sorted(set(chain.from_iterable(v))) for k, v in g["row_flags"]}, dtype=object
    )
    is_dup = hours["n_rows"] > 1
    is_conflict = is_dup & (hours["n_values"] > 1)
    audit = rows[rows["ts"].isin(hours.index[is_dup])][["ts", "date_source", "count"]].copy()
    audit = audit.rename(columns={"count": "count_source"})
    audit.insert(0, "counter_id", str(counter_id))
    audit["resolution"] = np.where(
        audit["ts"].isin(hours.index[is_conflict]), FLAG_CONFLICT, FLAG_DUPLICATE
    )

    # Grille horaire complète
    first, last = hours.index.min(), hours.index.max()
    if grid_range is not None:
        # Jamais plus courte que les heures du compteur : aucune mesure n'est perdue.
        first, last = min(first, grid_range[0]), max(last, grid_range[1])
    grid = pd.date_range(first, last, freq="h", tz="UTC", name="ts")
    h = hours.reindex(grid)
    present = h["n_rows"].notna()
    conflict = is_conflict.reindex(grid, fill_value=False)
    duplicate = is_dup.reindex(grid, fill_value=False) & ~conflict
    empty = present & h["all_empty"].eq(True) & ~conflict
    invalid = present & h["any_invalid"].eq(True) & ~conflict & ~empty

    count_raw = h["value"].where(~conflict & ~invalid)
    negative = count_raw < 0
    count = count_raw.where(~negative)
    is_observed = present & ~empty
    is_scoreable = is_observed & count.notna()

    zero_run = _run_lengths(count.eq(0))
    long_zero = zero_run >= LONG_ZERO_RUN_HOURS

    masks = {
        FLAG_MISSING: ~present,
        FLAG_EMPTY_VALUE: empty,
        FLAG_INVALID_VALUE: invalid,
        FLAG_NEGATIVE: negative,
        FLAG_DUPLICATE: duplicate,
        FLAG_CONFLICT: conflict,
        FLAG_LONG_ZERO_RUN: long_zero,
    }
    flags = [list(f) if isinstance(f, list) else [] for f in h["row_flags"]]
    for name, mask in masks.items():
        for i in np.flatnonzero(mask.to_numpy()):
            flags[i].append(name)
    flags = [sorted(set(f)) for f in flags]

    counts = pd.DataFrame(
        {
            "ts": grid,
            "count_raw": count_raw.to_numpy(),
            "count": count.to_numpy(),
            "is_observed": is_observed.to_numpy(),
            "is_scoreable": is_scoreable.to_numpy(),
            "flags": flags,
        }
    )

    # Métadonnées : ligne la plus récente, variantes signalées
    meta_rows = rows.sort_values("ts", kind="stable")
    last = meta_rows.iloc[-1] if len(meta_rows) else df.iloc[-1]
    variants = {
        c: int(df[c].nunique())
        for c in ("counter_name", "site_id", "site_name", "coordinates", "installation_date")
        if c in df.columns
    }
    for c, n in variants.items():
        if n > 1:
            alerts.append(
                f"{n} valeurs distinctes de {c} pour ce compteur : métadonnées à vérifier."
            )
    lat, lon = _parse_coordinates(last.get("coordinates"))
    site_id = str(last.get("site_id", "") or "")
    counter = {
        "counter_id": str(counter_id),
        "site_id": site_id,
        "site_group_id": site_id,  # par défaut ; groupe physique À VÉRIFIER (E1/E3/E4)
        "counter_name": last.get("counter_name", ""),
        "site_name": last.get("site_name", ""),
        "latitude": lat,
        "longitude": lon,
        # Tirée du nom (décision E1, étape 3 bis), non vérifiée sur place.
        "direction": direction_from_name(last.get("counter_name", "")),
        "installation_date": last.get("installation_date", ""),
    }

    name = str(counter["counter_name"])
    tail = name.rsplit(" ", 1)[-1] if " " in name else ""
    longest = int(zero_run.max()) if len(zero_run) else 0
    observed_ts = grid[is_observed.to_numpy()]
    report = {
        "n_source_rows": int(len(df)),
        "n_rows_unplaced": int((bad_ts | off_hour).sum()),
        "n_grid_hours": int(len(grid)),
        "n_observed": int(is_observed.sum()),
        "n_missing": int((~present).sum()),
        "n_empty_value": int(empty.sum()),
        "n_invalid_value": int(invalid.sum()),
        "n_negative": int(negative.sum()),
        "n_duplicate_hours": int(duplicate.sum()),
        "n_conflict_hours": int(conflict.sum()),
        "n_dst_ambiguous_rows": int(sum(FLAG_DST_AMBIGUOUS in f for f in df["row_flags"])),
        "n_dst_nonexistent_rows": int(sum(FLAG_DST_NONEXISTENT in f for f in df["row_flags"])),
        "n_zero_hours": int(count.eq(0).sum()),
        "n_long_zero_run_hours": int(long_zero.sum()),
        "longest_zero_run_hours": longest,
        "n_scoreable": int(is_scoreable.sum()),
        "coverage": round(float(is_observed.mean()), 4),
        "first_timestamp": grid.min().isoformat(),
        "last_timestamp": grid.max().isoformat(),
        "first_observed": observed_ts.min().isoformat() if len(observed_ts) else None,
        "last_observed": observed_ts.max().isoformat() if len(observed_ts) else None,
        "grid": "commune à l'instantané" if grid_range is not None else "propre au compteur",
        "metadata_variants": variants,
        "direction_candidate": tail if "-" in tail else None,
        "direction_source": "fin du nom" if counter["direction"] else "aucun sens dans le nom",
        "site_group_id_status": "par défaut = site_id, à vérifier",
    }
    if conflict.any():
        alerts.append(
            f"{int(conflict.sum())} heures en conflit (valeurs différentes) : count vide."
        )
    if negative.any():
        alerts.append(f"{int(negative.sum())} valeurs négatives : count vide.")
    return Prepared(counts=counts, counter=counter, report=report, audit=audit, alerts=alerts)


# ----------------------------------------------------------------- contrôles
def local_frame(counts: pd.DataFrame) -> pd.DataFrame:
    out = counts[["ts", "count", "is_observed"]].copy()
    out["ts_local"] = out["ts"].dt.tz_convert(TZ_LOCAL)
    return out


def hourly_profile(counts: pd.DataFrame) -> pd.DataFrame:
    s = local_frame(counts).dropna(subset=["count"])
    s["heure"] = s["ts_local"].dt.hour
    s["type_jour"] = np.where(s["ts_local"].dt.dayofweek < 5, "semaine", "week-end")
    return s.pivot_table(index="heure", columns="type_jour", values="count", aggfunc="mean")


def gaps(counts: pd.DataFrame) -> pd.DataFrame:
    s = local_frame(counts)
    m = ~s["is_observed"]
    if not m.any():
        return pd.DataFrame(columns=["debut", "fin", "heures"])
    block = (m != m.shift()).cumsum()
    g = s[m].groupby(block[m])["ts_local"].agg(["min", "max", "size"])
    g.columns = ["debut", "fin", "heures"]
    return g.sort_values("heures", ascending=False).reset_index(drop=True)


def dst_days(counts: pd.DataFrame) -> dict:
    """Jours locaux complets de 23 ou 25 h : {date: (heures observées, attendues)}.

    Seulement les jours où le compteur est actif (entre sa première et sa dernière
    mesure) : avec la grille commune, un compteur arrêté a encore des lignes, mais
    l'absence de mesure n'y dit rien du changement d'heure.
    """
    s = local_frame(counts)
    day = s["ts_local"].dt.date
    seen = day[s["is_observed"]]
    if seen.empty:
        return {}
    active_days = sorted(d for d in set(day) if seen.min() <= d <= seen.max())
    full_days = active_days[1:-1]  # le premier et le dernier jour peuvent être partiels
    expected = s.groupby(day).size()
    observed = s[s["is_observed"]].groupby(day[s["is_observed"]]).size()
    return {d: (int(observed.get(d, 0)), int(expected[d])) for d in full_days if expected[d] != 24}


def check_peaks(profile: pd.DataFrame) -> tuple[int | None, int | None, str | None]:
    """Pics de semaine attendus vers 8 h et 18 h (heure de Paris)."""
    if "semaine" not in profile or profile["semaine"].dropna().empty:
        return None, None, "Profil de semaine indisponible : convention horaire non contrôlée."
    week = profile["semaine"]
    am, pm = week.loc[5:12].dropna(), week.loc[14:21].dropna()
    if am.empty or pm.empty:  # compteur avec très peu d'heures (arrêté tôt, installé tard)
        return None, None, "Trop peu d'heures de semaine : convention horaire non contrôlée."
    morning = int(am.idxmax())
    evening = int(pm.idxmax())
    if 7 <= morning <= 9 and 16 <= evening <= 19:
        return morning, evening, None
    return (
        morning,
        evening,
        (
            f"Pics en semaine à {morning} h et {evening} h (attendu ~8 h et ~18 h) : "
            "vérifier le fuseau et la convention de l'heure."
        ),
    )


# ----------------------------------------------------------------- sorties CSV
def _fmt_ts(ts: pd.Series) -> pd.Series:
    return ts.dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _fmt_bool(s: pd.Series) -> pd.Series:
    return s.map({True: "true", False: "false"})


def _fmt_float(s: pd.Series) -> pd.Series:
    return s.map(lambda v: "" if pd.isna(v) else repr(float(v)))


def counts_table(prepared: Prepared, snapshot_id: str, source_id: str) -> pd.DataFrame:
    """Table counts.csv en texte, colonnes exactes du gabarit."""
    c = prepared.counts
    out = pd.DataFrame(
        {
            "counter_id": prepared.counter["counter_id"],
            "timestamp": _fmt_ts(c["ts"]),
            "interval_end": _fmt_ts(c["ts"] + pd.Timedelta(hours=1)),
            "count_raw": _fmt_float(c["count_raw"]),
            "count": _fmt_float(c["count"]),
            "is_observed": _fmt_bool(c["is_observed"]),
            "is_scoreable": _fmt_bool(c["is_scoreable"]),
            "quality_flags": c["flags"].map(json.dumps),
            "source_file_id": source_id,
            "snapshot_id": snapshot_id,
        }
    )
    return out[COUNTS_COLUMNS]


def counters_table(prepared: Prepared, snapshot_id: str) -> pd.DataFrame:
    row = {k: prepared.counter.get(k) for k in COUNTERS_COLUMNS}
    row["snapshot_id"] = snapshot_id
    out = pd.DataFrame([row])
    for col in ("latitude", "longitude"):
        out[col] = _fmt_float(out[col])
    return out[COUNTERS_COLUMNS].fillna("")


def merge_table(path: Path, new: pd.DataFrame, counter_id: str, sort_by: list[str]) -> pd.DataFrame:
    """Remplace les lignes du compteur dans un CSV existant de l'instantané."""
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False)
        new = pd.concat([old[old["counter_id"] != counter_id], new], ignore_index=True)
    return new.sort_values(sort_by, kind="stable").reset_index(drop=True)


def write_outputs(prepared: Prepared, snapshot_id: str, source_id: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cid = prepared.counter["counter_id"]
    paths = {
        "counts": out_dir / "counts.csv",
        "counters": out_dir / "counters.csv",
        "audit": out_dir / "audit_duplicates.csv",
    }
    counts = merge_table(
        paths["counts"],
        counts_table(prepared, snapshot_id, source_id),
        cid,
        ["counter_id", "timestamp"],
    )
    counts.to_csv(paths["counts"], index=False)
    counters = merge_table(
        paths["counters"], counters_table(prepared, snapshot_id), cid, ["counter_id"]
    )
    counters.to_csv(paths["counters"], index=False)
    audit = prepared.audit.copy()
    audit["ts"] = _fmt_ts(audit["ts"]) if len(audit) else audit["ts"]
    audit = audit.rename(columns={"ts": "timestamp"})
    audit = merge_table(paths["audit"], audit.astype(str), cid, ["counter_id", "timestamp"])
    audit.to_csv(paths["audit"], index=False)
    return {"paths": paths, "counts": counts, "counters": counters}


# ----------------------------------------------------------------- manifeste
DUPLICATE_RULE = (
    "Clé (counter_id, timestamp UTC). Lignes multiples à valeurs identiques : une valeur "
    "conservée, drapeau 'duplicate'. Valeurs différentes : count_raw et count vides, "
    "is_observed=true, is_scoreable=false, drapeau 'conflict' ; toutes les lignes source "
    "sont recopiées dans audit_duplicates.csv. Aucune sélection keep='first'."
)
KNOWN_LIMITATIONS = [
    f"quality_flags 'long_zero_run' (seuil {LONG_ZERO_RUN_HOURS} h) est un diagnostic "
    "RÉTROSPECTIF calculé sur toute la série : il utilise des heures postérieures et ne doit "
    "PAS servir de variable de prévision (E2/E3). Un zéro reste un zéro et reste évaluable.",
    "site_group_id = site_id par défaut ; le regroupement physique (directions, alias) n'est "
    "pas encore vérifié.",
    "direction tirée de la fin du nom (ex. 'S-N', 'SO-NE'), non vérifiée sur place ; vide si "
    "le nom ne se termine pas par un sens.",
    "Hypothèse : le champ 'date' marque le DÉBUT de l'intervalle horaire ; le profil horaire "
    "est cohérent avec cette lecture mais ne la prouve pas à l'heure près.",
    "Flux courant uniquement (13 mois glissants) : pas d'archives annuelles ni de contexte.",
    "Avec --tout, grille commune : chaque compteur a toutes les heures de l'instantané ; "
    "avant l'installation et après l'arrêt, is_observed=false. Compteur par compteur "
    "(--compteur), la grille va de la première à la dernière heure du compteur.",
    "Une suite de zéros est interrompue par une heure absente ou invalide.",
]


def update_manifest(
    snapshot_id: str,
    prepared: Prepared | list[Prepared],
    written: dict,
    peaks_ok: bool | str,
    extra: dict | None = None,
    raw_used: str | None = None,
) -> Path:
    """Complète le manifeste ; `prepared` = un compteur ou tous (--tout).

    `raw_used` : brut lu par la préparation ; les autres bruts de l'instantané sont
    marqués comme non utilisés (ex. un premier essai sur un seul compteur).

    `peaks_ok` : booléen (un compteur) ou texte déjà rédigé (tout le flux).
    """
    items = prepared if isinstance(prepared, list) else [prepared]
    manifest = acquire.load_manifest(snapshot_id)
    counts, counters = written["counts"], written["counters"]
    p = written["paths"]
    acquire.upsert(
        manifest["files"],
        acquire.file_entry(
            p["counts"],
            "counts",
            **(
                written.get("counts_stats")
                or {
                    "n_rows": int(len(counts)),
                    "n_counters": int(counts["counter_id"].nunique()),
                    "first_timestamp": counts["timestamp"].min(),
                    "last_timestamp": counts["timestamp"].max(),
                }
            ),
            columns=COUNTS_COLUMNS,
        ),
        "path",
    )
    acquire.upsert(
        manifest["files"],
        acquire.file_entry(
            p["counters"], "counters", n_rows=int(len(counters)), columns=COUNTERS_COLUMNS
        ),
        "path",
    )
    acquire.upsert(manifest["files"], acquire.file_entry(p["audit"], "duplicates_audit"), "path")
    manifest["source_time_semantics"] = {
        "source_field": "date (datetime ODS, précision horaire)",
        "export_parameter": "timezone=UTC",
        "interpretation": "début de l'intervalle horaire, converti en UTC",
        "status": peaks_ok
        if isinstance(peaks_ok, str)
        else "cohérent avec le profil horaire (pics ~8 h / ~18 h, heure de Paris)"
        if peaks_ok
        else "incertain : profil horaire inattendu",
        "naive_timestamps": "interprétés en Europe/Paris ; heures ambiguës/inexistantes "
        "signalées (dst_ambiguous / dst_nonexistent), jamais supprimées",
    }
    manifest["normalization_version"] = NORMALIZATION_VERSION
    manifest["duplicate_resolution"] = DUPLICATE_RULE
    manifest["known_limitations"] = KNOWN_LIMITATIONS
    manifest["quality_flags"] = FLAG_DEFINITIONS
    manifest["is_scoreable_rule"] = (
        "is_observed et count non vide (pas de conflit, valeur numérique non négative)."
    )
    for item in items:
        manifest.setdefault("counters", {})[item.counter["counter_id"]] = {
            **item.report,
            "alerts": item.alerts,
        }
    manifest.update(extra or {})
    if raw_used is not None:
        manifest["raw_used_by_prepare"] = raw_used
        for f in manifest.get("files", []):
            if f.get("role") == "raw":
                f["used_by_prepare"] = f.get("path") == raw_used
    return acquire.write_manifest(manifest)


# ----------------------------------------------------------------- console
def print_report(prepared: Prepared, profile: pd.DataFrame, dst: dict, holes: pd.DataFrame) -> None:
    r, c = prepared.report, prepared.counter
    print(f"\n=== Compteur {c['counter_id']} : {c['counter_name']}")
    print(
        f"site_id {c['site_id']} ({c['site_name']}) ; coordonnées {c['latitude']}, {c['longitude']}"
    )
    print(f"Période UTC : {r['first_timestamp']} -> {r['last_timestamp']} ({r['n_grid_hours']} h)")
    print(
        f"Observées {r['n_observed']} ({r['coverage']:.2%}), absentes {r['n_missing']}, "
        f"évaluables {r['n_scoreable']}"
    )
    print(
        f"Doublons identiques {r['n_duplicate_hours']}, conflits {r['n_conflict_hours']}, "
        f"négatifs {r['n_negative']}, invalides {r['n_invalid_value']}"
    )
    print(
        f"Zéros {r['n_zero_hours']} h ; plus longue suite {r['longest_zero_run_hours']} h ; "
        f"heures 'long_zero_run' (>= {LONG_ZERO_RUN_HOURS} h) : {r['n_long_zero_run_hours']}"
    )
    print(
        "Changements d'heure (heures observées / attendues) : "
        + (", ".join(f"{d} : {a}/{b}" for d, (a, b) in dst.items()) or "aucun jour complet")
    )
    print(f"Trous : {len(holes)} (les 5 plus longs, heure de Paris)")
    if len(holes):
        print(holes.head(5).to_string(index=False))
    print("Profil horaire moyen (heure de Paris) :")
    print(profile.round(1).T.to_string())
    print("Alertes :", *(prepared.alerts or ["aucune"]), sep="\n- ")


def _source_column(raw: pd.DataFrame, internal: str) -> str:
    for c in raw.columns:
        if COLUMN_MAP.get(str(c).lstrip("﻿")) == internal:
            return c
    raise ValueError(f"Colonne « {internal} » introuvable ; lues : {list(raw.columns)}")


def snapshot_range(raw: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Première et dernière heure pile (UTC) de tout le brut : la grille commune.

    Dates lues comme dans `normalize` (sans fuseau = heure de Paris), pour que la
    grille commune et les heures de chaque compteur soient dans la même référence.
    """
    ts = parse_timestamps(raw[_source_column(raw, "date_source")])[0]
    ts = ts[ts.notna() & (ts.dt.minute == 0) & (ts.dt.second == 0)]
    if ts.empty:
        raise ValueError("Aucune date lisible dans le brut.")
    return ts.min(), ts.max()


def split_by_counter(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Lignes du brut par compteur, dans l'ordre des identifiants."""
    col = _source_column(raw, "counter_id")
    return {
        str(cid): part.reset_index(drop=True)
        for cid, part in raw.groupby(raw[col].astype(str), sort=True)
    }


def mark_network_gaps(items: list[Prepared], share: float = NETWORK_GAP_SHARE) -> pd.DatetimeIndex:
    """Ajoute `network_gap` aux heures non observées où presque tout le réseau manque.

    Seulement sur les compteurs actifs à cette heure (même définition que
    `quality.network_gap_hours`) : avant l'installation ou après l'arrêt, l'heure
    manque à cause du compteur, pas du réseau.
    """
    frame = pd.concat(
        [p.counts[["ts", "is_observed"]].assign(counter_id=p.counter["counter_id"]) for p in items],
        ignore_index=True,
    )
    hours = network_gap_hours(frame, share).index
    for p in items:
        ts, observed = p.counts["ts"], p.counts["is_observed"]
        seen = ts[observed]
        active = (ts >= seen.min()) & (ts <= seen.max()) if len(seen) else ts.isna()
        hit = (ts.isin(hours) & ~observed & active).to_numpy()
        flags = p.counts["flags"].tolist()
        for i in np.flatnonzero(hit):
            flags[i] = sorted(set(flags[i]) | {FLAG_NETWORK_GAP})
        p.counts["flags"] = flags
        p.report["n_network_gap_hours"] = int(hit.sum())
    return pd.DatetimeIndex(hours)


def direction_checks(items: list[Prepared]) -> dict:
    """Sens manquants, et sites à plusieurs compteurs dont les sens ne sont pas opposés.

    Regroupement par `site_id` (même site déclaré par la source) ; un compteur sans
    `site_id` n'est rattaché à aucun site. Un site dont un compteur n'a pas de sens
    est signalé (sens `None`), au lieu d'être compté comme un site à un compteur.
    """
    df = pd.DataFrame([p.counter for p in items])
    without = sorted(df.loc[df["direction"].isna(), "counter_id"].tolist())
    sited = df[df["site_id"].fillna("").astype(str).str.strip() != ""]
    two, not_opposite = 0, []
    for site, g in sited.groupby("site_id"):
        if len(g) == 1:
            continue
        two += 1
        dirs = [d if isinstance(d, str) else None for d in g["direction"]]
        if len(g) != 2 or None in dirs or dirs[1] != opposite(dirs[0]):
            not_opposite.append({"site_id": site, "directions": dirs})
    return {
        "rule": "fin du nom (ex. 'S-N'), non vérifiée sur place",
        "n_counters": int(len(df)),
        "n_with_direction": int(df["direction"].notna().sum()),
        "without_direction": without,
        "n_sites_with_several_counters": two,
        "sites_not_opposite": not_opposite,
    }


def add_controls(
    prepared: Prepared, site_group_alert: bool = True
) -> tuple[pd.DataFrame, dict, pd.DataFrame, str | None]:
    """Profil horaire, jours de changement d'heure et trous ; complète le rapport."""
    profile = hourly_profile(prepared.counts)
    morning, evening, peak_alert = check_peaks(profile)
    if peak_alert:
        prepared.alerts.append(peak_alert)
    prepared.report["weekday_peaks_local"] = [morning, evening]
    dst = dst_days(prepared.counts)
    prepared.report["dst_days"] = {
        str(d): {"observed": a, "expected": b} for d, (a, b) in dst.items()
    }
    for d, (a, b) in dst.items():
        if a < b:
            prepared.alerts.append(
                f"Jour de changement d'heure {d} : {a}/{b} heures observées "
                "(perte possible en amont de l'heure répétée ou du jour)."
            )
    holes = gaps(prepared.counts)
    prepared.report["n_gaps"] = int(len(holes))
    if site_group_alert:  # compteur par compteur : groupes écrits ensuite par quality.py
        prepared.alerts.append(
            "site_group_id = site_id ici : relancer quality.py pour écrire les groupes candidats."
        )
    return profile, dst, holes, peak_alert


def write_all(items: list[Prepared], snapshot_id: str, source_id: str, out_dir: Path) -> dict:
    """Écrit les sorties de tout le flux en remplaçant les fichiers de l'instantané.

    counts.csv est écrit compteur par compteur (ordre counter_id, timestamp),
    sans tout garder en mémoire.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "counts": out_dir / "counts.csv",
        "counters": out_dir / "counters.csv",
        "audit": out_dir / "audit_duplicates.csv",
    }
    items = sorted(items, key=lambda p: str(p.counter["counter_id"]))
    n_rows, first, last = 0, None, None
    with paths["counts"].open("w", encoding="utf-8", newline="") as fh:
        for i, p in enumerate(items):
            table = counts_table(p, snapshot_id, source_id)
            table.to_csv(fh, index=False, header=i == 0)
            n_rows += len(table)
            if len(table):
                first = min(first or table["timestamp"].iloc[0], table["timestamp"].iloc[0])
                last = max(last or table["timestamp"].iloc[-1], table["timestamp"].iloc[-1])
    counters = pd.concat([counters_table(p, snapshot_id) for p in items], ignore_index=True)
    counters.to_csv(paths["counters"], index=False)
    audits = []
    for p in items:
        a = p.audit.copy()
        a["ts"] = _fmt_ts(a["ts"]) if len(a) else a["ts"]
        audits.append(a.rename(columns={"ts": "timestamp"}).astype(str))
    audit = pd.concat(audits, ignore_index=True)
    audit.sort_values(["counter_id", "timestamp"], kind="stable").to_csv(
        paths["audit"], index=False
    )
    stats = {
        "n_rows": n_rows,
        "n_counters": len(items),
        "first_timestamp": first,
        "last_timestamp": last,
    }
    return {"paths": paths, "counts": None, "counts_stats": stats, "counters": counters}


def prepare_all(snapshot_id: str) -> list[Prepared]:
    """Prépare tout le flux d'un instantané sur une grille commune (décisions E1)."""
    raw_path = data_path("history") / snapshot_id / acquire.RAW_ALL_FILENAME
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Brut complet introuvable : {relative_to_root(raw_path)} (lancer acquire --tout)"
        )
    raw = acquire.read_raw(raw_path)
    grid_range = snapshot_range(raw)
    items, peaks_ok = [], 0
    for cid, part in split_by_counter(raw).items():
        p = normalize(part, cid, grid_range)
        peaks_ok += add_controls(p, site_group_alert=False)[3] is None
        items.append(p)
    gap_hours = mark_network_gaps(items)
    checks = direction_checks(items)
    # Groupes candidats écrits dès ici (même règle que quality.py) : counters.csv ne
    # dépend plus de l'ordre des commandes.
    groups = candidate_site_groups(pd.DataFrame([p.counter for p in items]))
    for p in items:
        p.counter["site_group_id"] = groups[str(p.counter["counter_id"])]

    out_dir = data_path("processed") / snapshot_id
    written = write_all(items, snapshot_id, acquire.source_file_id(raw_path), out_dir)
    status = (
        f"cohérent avec le profil horaire (pics ~8 h / ~18 h, heure de Paris) pour "
        f"{peaks_ok}/{len(items)} compteurs"
    )
    extra = {
        "grid": {
            "rule": "commune à tous les compteurs (décision E1, étape 2)",
            "first_timestamp": grid_range[0].isoformat(),
            "last_timestamp": grid_range[1].isoformat(),
            "n_hours": int((grid_range[1] - grid_range[0]) / pd.Timedelta(hours=1)) + 1,
        },
        "network_gap": {
            "share": NETWORK_GAP_SHARE,
            "n_hours": int(len(gap_hours)),
            "rule": FLAG_DEFINITIONS[FLAG_NETWORK_GAP],
        },
        "direction_checks": checks,
        "site_groups": {"rule": SITE_GROUP_RULE, "n_groups": int(groups.nunique())},
        "known_limitations": [
            SITE_GROUP_RULE if x.startswith("site_group_id = site_id") else x
            for x in KNOWN_LIMITATIONS
        ],
    }
    manifest = update_manifest(
        snapshot_id, items, written, status, extra, raw_used=relative_to_root(raw_path)
    )
    print_all_report(snapshot_id, items, extra, written, manifest)
    return items


def print_all_report(snapshot_id, items, extra, written, manifest) -> None:
    lengths = {len(p.counts) for p in items}
    g, d = extra["grid"], extra["direction_checks"]
    observed = sum(int(p.counts["is_observed"].sum()) for p in items)
    total = sum(len(p.counts) for p in items)
    print(f"\n=== Instantané {snapshot_id} : {len(items)} compteurs")
    print(f"Grille commune UTC : {g['first_timestamp']} -> {g['last_timestamp']} ({g['n_hours']} h)")
    print(
        "Même nombre d'heures pour tous : "
        + ("oui" if len(lengths) == 1 else f"NON ({sorted(lengths)})")
    )
    print(f"Heures observées : {observed}/{total} ({observed / total:.1%})")
    print(f"Heures 'network_gap' : {extra['network_gap']['n_hours']}")
    print(f"Groupes de sites (candidats, à moins de 100 m) : {extra['site_groups']['n_groups']}")
    print(
        f"Direction : {d['n_with_direction']}/{d['n_counters']} compteurs ; "
        f"sites à plusieurs compteurs : {d['n_sites_with_several_counters']} ; "
        f"sens non opposés : {len(d['sites_not_opposite'])}"
    )
    for s in d["sites_not_opposite"]:
        print(f"  - site {s['site_id']} : {s['directions']}")
    if d["without_direction"]:
        print("  Sans direction :", ", ".join(d["without_direction"]))
    n_alerts = sum(len(p.alerts) for p in items)
    print(f"Alertes par compteur : {n_alerts} (détail dans le manifeste, « counters »)")
    print("\nFichiers :")
    for p in [*written["paths"].values(), manifest]:
        print(f"- {relative_to_root(p)}")
    print(
        "\nÉtape suivante : uv run python -m src.data.quality --snapshot "
        f"{snapshot_id}  (inventaire et sélection ; groupes déjà écrits)"
    )


def prepare_counter(snapshot_id: str, counter_id: str) -> Prepared:
    raw_path = data_path("history") / snapshot_id / acquire.raw_filename(counter_id)
    if not raw_path.exists():
        raise FileNotFoundError(f"Brut introuvable : {relative_to_root(raw_path)}")
    prepared = normalize(acquire.read_raw(raw_path), counter_id)
    profile, dst, holes, peak_alert = add_controls(prepared)

    out_dir = data_path("processed") / snapshot_id
    written = write_outputs(prepared, snapshot_id, acquire.source_file_id(raw_path), out_dir)
    manifest = update_manifest(snapshot_id, prepared, written, peak_alert is None)
    print_report(prepared, profile, dst, holes)
    print("\nFichiers :")
    for p in [*written["paths"].values(), manifest]:
        print(f"- {relative_to_root(p)}")
    return prepared


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané, ex. flux-20261112")
    ap.add_argument("--compteur", help="id_compteur (un seul compteur)")
    ap.add_argument(
        "--tout", action="store_true", help="tout le flux, grille commune (brut de acquire --tout)"
    )
    args = ap.parse_args(argv)
    if args.tout == bool(args.compteur):
        ap.error("indiquer --tout ou --compteur ID (l'un des deux)")
    if args.tout:
        prepare_all(args.snapshot)
    else:
        prepare_counter(args.snapshot, args.compteur)
    return 0


if __name__ == "__main__":
    sys.exit(main())

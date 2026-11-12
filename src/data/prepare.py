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

Usage, depuis la racine du dépôt (normalement enchaîné par acquire) :
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
import sys
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path, relative_to_root
from src.data import acquire

TZ_LOCAL = "Europe/Paris"
LONG_ZERO_RUN_HOURS = 24  # seuil d'une suite de zéros « longue » (heures consécutives)
NORMALIZATION_VERSION = "e1-prepare/0.1.0"

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
}

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


def normalize(raw: pd.DataFrame, counter_id: str) -> Prepared:
    """Normalise le brut d'un compteur sur une grille horaire UTC complète."""
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
    grid = pd.date_range(hours.index.min(), hours.index.max(), freq="h", tz="UTC", name="ts")
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
        "direction": None,  # non validée ; voir report["direction_candidate"]
        "installation_date": last.get("installation_date", ""),
    }

    name = str(counter["counter_name"])
    tail = name.rsplit(" ", 1)[-1] if " " in name else ""
    longest = int(zero_run.max()) if len(zero_run) else 0
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
        "metadata_variants": variants,
        "direction_candidate": tail if "-" in tail else None,
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
    """Jours locaux complets de 23 ou 25 h : {date: (heures observées, attendues)}."""
    s = local_frame(counts)
    day = s["ts_local"].dt.date
    full_days = sorted(set(day))[1:-1]  # le premier et le dernier jour peuvent être partiels
    expected = s.groupby(day).size()
    observed = s[s["is_observed"]].groupby(day[s["is_observed"]]).size()
    return {d: (int(observed.get(d, 0)), int(expected[d])) for d in full_days if expected[d] != 24}


def check_peaks(profile: pd.DataFrame) -> tuple[int | None, int | None, str | None]:
    """Pics de semaine attendus vers 8 h et 18 h (heure de Paris)."""
    if "semaine" not in profile or profile["semaine"].dropna().empty:
        return None, None, "Profil de semaine indisponible : convention horaire non contrôlée."
    week = profile["semaine"]
    morning = int(week.loc[5:12].idxmax())
    evening = int(week.loc[14:21].idxmax())
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
    "direction laissée vide : le suffixe du nom (ex. 'S-N') est un candidat non validé.",
    "Hypothèse : le champ 'date' marque le DÉBUT de l'intervalle horaire ; le profil horaire "
    "est cohérent avec cette lecture mais ne la prouve pas à l'heure près.",
    "Flux courant uniquement (13 mois glissants) : pas d'archives annuelles ni de contexte.",
    "Les heures absentes sont détectées entre la première et la dernière heure présentes ; "
    "les manques avant/après ces bornes ne sont pas représentés.",
    "Une suite de zéros est interrompue par une heure absente ou invalide.",
]


def update_manifest(snapshot_id: str, prepared: Prepared, written: dict, peaks_ok: bool) -> Path:
    manifest = acquire.load_manifest(snapshot_id)
    counts, counters = written["counts"], written["counters"]
    p = written["paths"]
    acquire.upsert(
        manifest["files"],
        acquire.file_entry(
            p["counts"],
            "counts",
            n_rows=int(len(counts)),
            n_counters=int(counts["counter_id"].nunique()),
            first_timestamp=counts["timestamp"].min(),
            last_timestamp=counts["timestamp"].max(),
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
        "status": "cohérent avec le profil horaire (pics ~8 h / ~18 h, heure de Paris)"
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
    manifest.setdefault("counters", {})[prepared.counter["counter_id"]] = {
        **prepared.report,
        "alerts": prepared.alerts,
    }
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


def prepare_counter(snapshot_id: str, counter_id: str) -> Prepared:
    raw_path = data_path("history") / snapshot_id / acquire.raw_filename(counter_id)
    if not raw_path.exists():
        raise FileNotFoundError(f"Brut introuvable : {relative_to_root(raw_path)}")
    prepared = normalize(acquire.read_raw(raw_path), counter_id)
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
    prepared.alerts.append(
        "site_group_id = site_id par défaut : regroupement physique à vérifier avec E3/E4."
    )

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
    ap.add_argument("--compteur", required=True, help="id_compteur")
    args = ap.parse_args(argv)
    prepare_counter(args.snapshot, args.compteur)
    return 0


if __name__ == "__main__":
    sys.exit(main())

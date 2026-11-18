"""Remplacement des heures sans mesure par la même heure une semaine avant (J-7) - E1, Sabrina.

Demande de l'équipe (Nihed, 17/11/2026, tâche B2 de la passation) : remplacer les
heures sans mesure (`missing` et `empty_value`) par la valeur de J-7, « valeur dans une
nouvelle colonne, jamais en évaluation ».

Règle (décisions de Sabrina, 17/11/2026) :
- heure visée : sans mesure (`count` vide), pendant la période active du compteur,
  c'est-à-dire entre sa première et sa dernière heure observée ; rien avant
  l'installation ni après l'arrêt ;
- une heure absente du fichier (ligne non reçue) dans cette période est d'abord créée,
  avec le drapeau `missing` ;
- valeur : `count` de la même heure de Paris sept jours avant, si cette heure a une
  mesure (`is_scoreable`) ; jamais une valeur elle-même remplacée ;
- si J-7 n'a pas de mesure, ou n'existe pas (heure sautée ou répétée au changement
  d'heure), l'heure reste vide.

Sortie : une nouvelle colonne `count_filled_j7` = `count` pour une heure mesurée, la
valeur de J-7 pour une heure remplacée, vide sinon. `count`, `count_raw`,
`is_observed`, `is_scoreable` et `quality_flags` sont inchangés : une valeur remplacée
n'est ni une observation ni une cible évaluable (`doc/CONTRATS.md` §3 : « Les cibles ne
sont jamais imputées »). Une heure remplacée se reconnaît à `count` vide et
`count_filled_j7` rempli.

counts.csv n'est pas modifié (fichier commun, empreinte SHA-256 dans le manifeste) :
le résultat est écrit à côté, dans filled_j7.csv (colonnes de counts.csv, puis
`count_filled_j7`). Fonctionne pour tout instantané (`flux-…`, `hist-…`).

Usage :
  uv run python -m src.data.fill_j7 --snapshot flux-20261115
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.data.quality import TZ_LOCAL

FILLED_COLUMN = "count_filled_j7"
MISSING_FLAG = "missing"
FILL_VERSION = "e1-fill-j7/0.2.0"
OUTPUT_NAME = "filled_j7.csv"
REPORT_NAME = "filled_j7_report.json"


def j7_timestamps(ts: pd.Series) -> pd.Series:
    """Même heure de Paris sept jours avant, en UTC ; NaT si elle n'existe pas ou est double."""
    wall = ts.dt.tz_convert(TZ_LOCAL).dt.tz_localize(None) - pd.Timedelta(days=7)
    local = wall.dt.tz_localize(TZ_LOCAL, ambiguous="NaT", nonexistent="NaT")
    return local.dt.tz_convert("UTC")


def _flags(value) -> list[str]:
    if isinstance(value, list):
        return list(value)
    if value is None or (isinstance(value, float) and np.isnan(value)) or value == "":
        return []
    return list(json.loads(value))


def complete_active_grid(counts: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les heures absentes de la période active de chaque compteur (drapeau `missing`).

    `counts` : colonnes `counter_id`, `ts` (UTC), `count`, `is_observed`, `is_scoreable`,
    `quality_flags` (liste). Les autres colonnes des lignes créées sont vides.
    """
    parts = []
    for cid, g in counts.groupby("counter_id", sort=False):
        seen = g.loc[g["is_observed"], "ts"]
        if seen.empty:
            parts.append(g)
            continue
        grid = pd.date_range(seen.min(), seen.max(), freq="h", tz="UTC")
        absent = grid.difference(pd.DatetimeIndex(g["ts"]))
        if len(absent):
            new = pd.DataFrame(
                {
                    "counter_id": cid,
                    "ts": absent,
                    "count": np.nan,
                    "is_observed": False,
                    "is_scoreable": False,
                    "quality_flags": [[MISSING_FLAG] for _ in absent],
                }
            )
            g = pd.concat([g, new], ignore_index=True)
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["counter_id", "ts"], kind="stable").reset_index(drop=True)


def fill_j7(counts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Ajoute `count_filled_j7` (J-7 pour les heures sans mesure actives). Retourne (copie, bilan)."""
    df = counts.copy()
    df["quality_flags"] = df["quality_flags"].map(_flags)
    n_before = len(df)
    df = complete_active_grid(df)
    n_created = len(df) - n_before

    seen = df.loc[df["is_observed"]].groupby("counter_id")["ts"].agg(["min", "max"])
    bounds = df[["counter_id"]].join(seen, on="counter_id")
    active = (df["ts"] >= bounds["min"]) & (df["ts"] <= bounds["max"])
    target = active & df["count"].isna()

    measured = df.loc[df["is_scoreable"] & df["count"].notna(), ["counter_id", "ts", "count"]]
    lookup = df.loc[target, ["counter_id"]].assign(ts=j7_timestamps(df.loc[target, "ts"]))
    value = lookup.merge(measured, on=["counter_id", "ts"], how="left")["count"].to_numpy()
    df[FILLED_COLUMN] = df["count"]
    idx = df.index[target]
    filled = idx[~np.isnan(value)]
    df.loc[filled, FILLED_COLUMN] = value[~np.isnan(value)]

    report = {
        "fill_version": FILL_VERSION,
        "rule": "même heure de Paris J-7, si mesurée ; période active seulement ; "
        f"valeur dans {FILLED_COLUMN}, count inchangé, jamais en évaluation",
        "n_rows_created": int(n_created),
        "n_hours_without_value_active": int(target.sum()),
        "n_hours_filled": int(len(filled)),
        "n_hours_left_empty": int(target.sum() - len(filled)),
        "n_hours_without_value_outside_active": int((~active & df["count"].isna()).sum()),
    }
    return df, report


def _number(v) -> str:
    return "" if pd.isna(v) else repr(float(v))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané")
    args = ap.parse_args(argv)
    folder = data_path("processed") / args.snapshot
    raw = pd.read_csv(folder / "counts.csv", dtype=str, keep_default_na=False)
    columns = list(raw.columns)

    df = raw.rename(columns={"timestamp": "ts"})
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    df["count_text"] = df["count"]
    df["count"] = pd.to_numeric(df["count"].replace("", np.nan), errors="coerce")
    for col in ("is_observed", "is_scoreable"):
        df[col] = df[col].str.lower().eq("true")

    out, report = fill_j7(df)

    # Colonnes de counts.csv recopiées telles quelles ; lignes créées complétées
    out["interval_end"] = (out["ts"] + pd.Timedelta(hours=1)).map(pd.Timestamp.isoformat)
    out["timestamp"] = out["ts"].map(pd.Timestamp.isoformat)
    for col in ("source_file_id", "snapshot_id"):
        out[col] = out.groupby("counter_id")[col].transform("first")
    out["count_raw"] = out["count_raw"].fillna("")
    out["count"] = out["count_text"].fillna("")
    for col in ("is_observed", "is_scoreable"):
        out[col] = out[col].map(lambda b: "true" if b else "false")
    out["quality_flags"] = out["quality_flags"].map(json.dumps)
    out[FILLED_COLUMN] = out[FILLED_COLUMN].map(_number)
    out[columns + [FILLED_COLUMN]].to_csv(folder / OUTPUT_NAME, index=False)

    report["snapshot_id"] = args.snapshot
    report["input"] = "counts.csv"
    report["output"] = OUTPUT_NAME
    (folder / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for k, v in report.items():
        print(f"{k} : {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

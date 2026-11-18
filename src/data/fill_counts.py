"""Comptages remplis : J-7 pour les heures sans mesure, année d'avant pour les zéros - E1, Sabrina.

Décision E1 (Sabrina, 18/11/2026), un seul fichier final, en deux étapes :
1. sites réservés à E3 rendus « nouveaux » (`new_sites.py` : installés 1, 3 ou 7 jours
   avant la fin de l'instantané, historique antérieur vidé ; counters_filled.csv porte
   leur date d'installation fictive) ;
2. remplacements, calculés sur le résultat de l'étape 1 :
- heures marquées `missing` ou `empty_value` -> même heure de Paris J-7
  (`fill_j7.fill_j7`) ;
- heures d'une suite d'au moins 24 h de zéros mesurés -> même date et heure de Paris
  un an avant, recopiée telle quelle (`fill_zeros_year.fill_zero_runs`).

Les deux ensembles d'heures sont disjoints (une heure sans mesure n'est pas un zéro
mesuré), et chaque remplacement lit ses valeurs dans les données d'origine : J-7 ne
prend jamais une valeur venue de l'année d'avant, et inversement. L'ordre est donc
sans effet.

Trace : `count_raw` n'est jamais modifié (vide pour J-7, 0 pour l'année d'avant).
counts.csv et counters.csv ne sont pas modifiés : sorties dans counts_filled.csv et
counters_filled.csv, mêmes colonnes ; le brut permet de tout recalculer.

Usage (sur l'historique, qui contient l'année d'avant) :
  uv run python -m src.data.fill_counts --snapshot hist-20261117
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.data.fill_j7 import fill_j7
from src.data.fill_zeros_year import fill_zero_runs
from src.data.new_sites import assign_budgets, make_new_sites, update_counters

OUTPUT_NAME = "counts_filled.csv"
COUNTERS_OUTPUT_NAME = "counters_filled.csv"
REPORT_NAME = "counts_filled_report.json"


def fill_counts(counts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """J-7 puis année d'avant, chacun calculé sur les données d'origine. Retourne (copie, bilan).

    `counts` : colonnes `counter_id`, `ts` (UTC), `count`, `is_observed`, `is_scoreable`,
    `quality_flags`.
    """
    out, rep_j7 = fill_j7(counts)
    zeros, rep_zeros = fill_zero_runs(counts)
    key = ["counter_id", "ts"]
    changed = zeros["count"].ne(counts["count"]) & ~(zeros["count"].isna() & counts["count"].isna())
    new = zeros.loc[changed, key + ["count", "is_scoreable"]]
    pos = out.reset_index().merge(new, on=key, suffixes=("", "_year"))
    out.loc[pos["index"].to_numpy(), "count"] = pos["count_year"].to_numpy()
    out.loc[pos["index"].to_numpy(), "is_scoreable"] = pos["is_scoreable_year"].to_numpy()
    return out, {"j7": rep_j7, "zero_runs_year_before": rep_zeros}


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

    inventory = pd.read_csv(folder / "inventory_quality.csv", dtype=str, keep_default_na=False)
    df, plan, rep_new = make_new_sites(df, assign_budgets(inventory))
    out, report = fill_counts(df)
    report = {"new_sites": rep_new, **report}
    report["new_sites"]["counters"] = [
        {**r, "installed_at": r["installed_at"].isoformat()}
        for r in plan.to_dict("records")
    ]
    counters = pd.read_csv(folder / "counters.csv", dtype=str, keep_default_na=False)
    update_counters(counters, plan).to_csv(folder / COUNTERS_OUTPUT_NAME, index=False)

    original = out["count_text"].fillna("")
    before = pd.to_numeric(original.replace("", np.nan), errors="coerce")
    same = (before == out["count"]) | (before.isna() & out["count"].isna())
    as_text = out["count"].map(lambda v: "" if pd.isna(v) else repr(float(v)))
    out["count"] = original.where(same, as_text)
    out["interval_end"] = (out["ts"] + pd.Timedelta(hours=1)).map(pd.Timestamp.isoformat)
    out["timestamp"] = out["ts"].map(pd.Timestamp.isoformat)
    for col in ("source_file_id", "snapshot_id"):
        out[col] = out.groupby("counter_id")[col].transform("first")
    out["count_raw"] = out["count_raw"].fillna("")
    for col in ("is_observed", "is_scoreable"):
        out[col] = out[col].map(lambda b: "true" if b else "false")
    out["quality_flags"] = out["quality_flags"].map(json.dumps)
    out[columns].to_csv(folder / OUTPUT_NAME, index=False)

    report.update(
        {
            "snapshot_id": args.snapshot,
            "input": ["counts.csv", "counters.csv", "inventory_quality.csv"],
            "output": [OUTPUT_NAME, COUNTERS_OUTPUT_NAME],
        }
    )
    (folder / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

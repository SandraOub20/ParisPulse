"""Comptages remplis : J-7 pour les heures sans mesure, année d'avant pour les zéros - E1, Sabrina.

Décisions E1 (Sabrina, 18/11/2026). Une version par budget d'historique local des sites
réservés à E3 (1, 3 et 7 jours), chacune en deux étapes :
1. sites réservés à E3 rendus « nouveaux » (`new_sites.py` : installés au début du
   support local de la première origine d'évaluation, historique antérieur vidé ;
   counters_filled_<budget>j.csv porte leur date d'installation fictive) ;
2. remplacements, calculés sur le résultat de l'étape 1 :
- heures marquées `missing` ou `empty_value` -> même heure de Paris J-7
  (`fill_j7.fill_j7`) ;
- heures d'une suite d'au moins 24 h de zéros mesurés -> même date et heure de Paris
  un an avant, si elle est > 0 (`fill_zeros_year.fill_zero_runs`) ; sinon le 0 reste.

Une valeur remplacée n'est jamais une cible : `is_scoreable` est faux (`doc/CONTRATS.md`
§3). Les deux ensembles d'heures sont disjoints (une heure sans mesure n'est pas un zéro
mesuré), et chaque remplacement lit ses valeurs dans les données d'origine : J-7 ne
prend jamais une valeur venue de l'année d'avant, et inversement. L'ordre est donc
sans effet.

Seuls les 21 compteurs réservés diffèrent d'une version à l'autre : pour les autres, les
trois fichiers sont identiques.

Trace : `count_raw` n'est jamais modifié (vide pour J-7, 0 pour l'année d'avant).
counts.csv et counters.csv ne sont pas modifiés : sorties dans counts_filled_<budget>j.csv
et counters_filled_<budget>j.csv, mêmes colonnes ; le brut permet de tout recalculer.

Usage (sur l'historique, qui contient l'année d'avant) :
  uv run python -m src.data.fill_counts --snapshot hist-20261117
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.data.fill_j7 import fill_j7
from src.data.fill_zeros_year import fill_zero_runs
from src.data.new_sites import BUDGET_DAYS, make_new_sites, reserved_counters, update_counters

OUTPUT_NAME = "counts_filled_{days}j.csv"
COUNTERS_OUTPUT_NAME = "counters_filled_{days}j.csv"
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


def write_counts(out: pd.DataFrame, columns: list[str], path: Path) -> None:
    """Écrit les comptages remplis avec les colonnes de counts.csv."""
    out = out.copy()
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
    out[columns].to_csv(path, index=False)


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
    reserved = reserved_counters(inventory)
    counters = pd.read_csv(folder / "counters.csv", dtype=str, keep_default_na=False)
    report = {
        "snapshot_id": args.snapshot,
        "input": ["counts.csv", "counters.csv", "inventory_quality.csv"],
        "versions": {},
    }
    for days in BUDGET_DAYS:
        new, plan, rep_new = make_new_sites(df, reserved, days)
        out, rep = fill_counts(new)
        rep_new["counters"] = [
            {**r, "installed_at": r["installed_at"].isoformat()} for r in plan.to_dict("records")
        ]
        names = [OUTPUT_NAME.format(days=days), COUNTERS_OUTPUT_NAME.format(days=days)]
        write_counts(out, columns, folder / names[0])
        update_counters(counters, plan).to_csv(folder / names[1], index=False)
        report["versions"][f"{days}j"] = {"output": names, "new_sites": rep_new, **rep}
        print(f"{days} j : {names[0]}, {names[1]} écrits")

    (folder / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

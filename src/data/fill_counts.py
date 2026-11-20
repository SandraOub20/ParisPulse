"""Comptages remplis directement dans counts.csv : sites nouveaux, J-7, année d'avant - E1, Sabrina.

Décisions E1 (Sabrina, 18 et 19/11/2026) : `count` est remplacé directement dans
counts.csv ; `count_raw` et les drapeaux gardent la trace et permettent de revenir aux
valeurs d'origine (`original.py`). Deux étapes :
1. sites réservés à E3 rendus « nouveaux » (`new_sites.py` : 7 jours d'historique local
   pour tous, installés au début du support local de la première origine d'évaluation,
   historique antérieur vidé ; counters.csv porte leur date d'installation fictive) ;
2. remplacements, calculés sur le résultat de l'étape 1 :
- heures marquées `missing` ou `empty_value` -> même heure de Paris J-7
  (`fill_j7.fill_j7`) ; `count_raw` reste vide, `is_observed` faux ;
- heures marquées `long_zero_run` -> même date et heure de Paris un an avant, si elle
  est > 0 (`fill_zeros_year.fill_zero_runs`) ; sinon le 0 reste ;
  `count_raw` garde le 0.

Une valeur remplacée n'est jamais une cible : `is_scoreable` est faux (`doc/CONTRATS.md`
§3). Les deux ensembles d'heures sont disjoints, et chaque remplacement lit ses valeurs
dans les données d'origine : l'ordre est sans effet.

À lancer une seule fois par instantané, APRÈS quality.py, context.py et l'examen des
alertes (ils lisent les données d'origine) : le manifeste reçoit un bloc `fill`, et un
second passage est refusé. Ne pas relancer quality.py sur un counts.csv rempli (les sites
réservés y paraîtraient installés tard) : repartir du counts.csv d'origine (zip de
l'instantané) ou du brut.

Usage :
  uv run python -m src.data.fill_counts --snapshot hist-20261117
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.data import acquire
from src.data.fill_j7 import fill_j7
from src.data.fill_zeros_year import fill_zero_runs
from src.data.new_sites import assign_budgets, make_new_sites, update_counters

REPORT_NAME = "fill_report.json"


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
    tmp = path.with_suffix(".tmp")
    out[columns].to_csv(tmp, index=False)
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané")
    args = ap.parse_args(argv)
    folder = data_path("processed") / args.snapshot
    manifest = acquire.load_manifest(args.snapshot)
    if manifest.get("fill"):
        raise SystemExit(
            f"{args.snapshot} est déjà rempli ({manifest['fill'].get('filled_at')}) : "
            "repartir du counts.csv d'origine (zip de l'instantané) ou du brut."
        )
    raw = pd.read_csv(folder / "counts.csv", dtype=str, keep_default_na=False)
    columns = list(raw.columns)
    df = raw.rename(columns={"timestamp": "ts"})
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    df["count_text"] = df["count"]
    df["count"] = pd.to_numeric(df["count"].replace("", np.nan), errors="coerce")
    for col in ("is_observed", "is_scoreable"):
        df[col] = df[col].str.lower().eq("true")

    inventory = pd.read_csv(folder / "inventory_quality.csv", dtype=str, keep_default_na=False)
    counters = pd.read_csv(folder / "counters.csv", dtype=str, keep_default_na=False)
    new, plan, rep_new = make_new_sites(df, assign_budgets(inventory))
    out, rep = fill_counts(new)
    rep_new["counters"] = [
        {**r, "installed_at": r["installed_at"].isoformat()} for r in plan.to_dict("records")
    ]
    report = {
        "filled_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rule": "count remplacé directement ; count_raw et drapeaux gardent la trace "
        "(src/data/original.py) ; valeurs remplacées jamais cibles (is_scoreable faux)",
        "new_sites": rep_new,
        **rep,
    }

    write_counts(out, columns, folder / "counts.csv")
    update_counters(counters, plan).to_csv(folder / "counters.csv", index=False)
    (folder / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for role, name in (("counts", "counts.csv"), ("counters", "counters.csv"), ("fill_report", REPORT_NAME)):
        acquire.upsert(manifest["files"], acquire.file_entry(folder / name, role), "path")
    manifest["fill"] = {k: report[k] for k in ("filled_at", "rule")} | {
        "report": REPORT_NAME,
        "warning": "inventory_quality.csv et selection_summary.json décrivent les données "
        "d'origine ; ne pas relancer quality.py sur ce counts.csv",
    }
    acquire.write_manifest(manifest)
    print(json.dumps({k: v for k, v in report.items() if k != "new_sites"}, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in rep_new.items() if k != "counters"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

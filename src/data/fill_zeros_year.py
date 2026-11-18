"""Longues suites de zéros remplacées par les mêmes dates de l'année d'avant - E1, Sabrina.

Décision E1 (Sabrina, 18/11/2026) : chaque heure d'une suite d'au moins 24 h de zéros
mesurés reçoit la valeur du même compteur, à la même date et à la même heure de Paris
un an avant :
- la valeur est recopiée telle quelle, y compris un 0 ou une case vide ;
- `count` est remplacé directement ; `count_raw` garde la valeur d'origine (0), ce qui
  sert de trace : une heure remplacée a `count` différent de `count_raw` ;
- `is_scoreable` suit la règle de prepare (observée et `count` non vide) ;
- si les mêmes dates un an avant sont avant le début de l'instantané ou avant la
  première mesure du compteur (pas encore installé), l'heure n'est pas modifiée
  (valeur inconnue) et elle est comptée à part.

À savoir : la détection des suites est rétrospective (elle lit toute la série), et
`doc/CONTRATS.md` §3 dit que les cibles ne sont jamais imputées ; une valeur remplacée
peut donc servir de cible. Décision à présenter aux autres équipes à la livraison.

À lancer sur l'historique (`hist-…`), qui contient l'année d'avant. counts.csv n'est pas
modifié : le résultat est écrit dans filled_zeros_year.csv, avec les mêmes colonnes.

Usage :
  uv run python -m src.data.fill_zeros_year --snapshot hist-20261117
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.data.zeros_years import MIN_RUN_HOURS, long_runs, shift_years

FILL_VERSION = "e1-fill-zeros-year/0.1.0"
OUTPUT_NAME = "filled_zeros_year.csv"
REPORT_NAME = "filled_zeros_year_report.json"


def run_hours(runs: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par heure des suites : counter_id, ts (UTC)."""
    parts = [
        pd.DataFrame({"counter_id": r.counter_id, "ts": pd.date_range(r.start, r.end, freq="h")})
        for r in runs.itertuples()
    ]
    if not parts:
        return pd.DataFrame(
            {"counter_id": pd.Series(dtype=str), "ts": pd.Series(dtype="datetime64[ns, UTC]")}
        )
    return pd.concat(parts, ignore_index=True)


def fill_zero_runs(counts: pd.DataFrame, min_run: int = MIN_RUN_HOURS) -> tuple[pd.DataFrame, dict]:
    """Remplace `count` des suites de zéros par l'année d'avant. Retourne (copie, bilan).

    `counts` : colonnes `counter_id`, `ts` (UTC), `count`, `is_observed`, `is_scoreable`.
    """
    df = counts.copy()
    runs = long_runs(df, min_run)
    hours = run_hours(runs)
    first = df["ts"].min()
    report = {
        "fill_version": FILL_VERSION,
        "rule": "suites >= 24 h de zéros mesurés ; même date et heure de Paris un an avant, "
        "recopiée telle quelle (0 et vide compris) ; count remplacé, count_raw inchangé",
        "n_runs": int(len(runs)),
        "n_counters": int(runs["counter_id"].nunique()) if len(runs) else 0,
        "n_hours_in_runs": int(len(hours)),
    }
    if hours.empty:
        report.update({"n_hours_replaced": 0, "n_hours_before_snapshot": 0, "replaced_by": {}})
        return df, report

    hours["prev"] = [shift_years(t, 1) for t in hours["ts"]]
    # Inconnu : avant le début de l'instantané, ou avant la première mesure du compteur
    # (compteur pas encore installé : ce n'est pas une case vide)
    installed = df.loc[df["is_observed"].astype(bool)].groupby("counter_id")["ts"].min()
    since = hours["counter_id"].map(installed)
    known = (hours["prev"] >= first) & (hours["prev"] >= since)
    key = df.set_index(["counter_id", "ts"])
    prev_idx = pd.MultiIndex.from_frame(hours.loc[known, ["counter_id", "prev"]])
    prev = key["count"].reindex(prev_idx).to_numpy()  # NaN : vide ou ligne absente

    target = pd.MultiIndex.from_frame(hours.loc[known, ["counter_id", "ts"]])
    pos = df.reset_index().set_index(["counter_id", "ts"]).loc[target, "index"].to_numpy()
    df.loc[pos, "count"] = prev
    df.loc[pos, "is_scoreable"] = df.loc[pos, "is_observed"].astype(bool) & ~np.isnan(prev)

    replaced_by = {
        "valeur > 0": int((prev > 0).sum()),
        "0": int((prev == 0).sum()),
        "vide": int(np.isnan(prev).sum()),
    }
    report.update(
        {
            "n_hours_replaced": int(known.sum()),
            "n_hours_before_snapshot": int((~known).sum()),
            "replaced_by": replaced_by,
        }
    )
    return df, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané (hist-…)")
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

    out, report = fill_zero_runs(df)

    changed = out["count"].ne(df["count"]) & ~(out["count"].isna() & df["count"].isna())
    out["count"] = np.where(
        changed, out["count"].map(lambda v: "" if pd.isna(v) else repr(float(v))), out["count_text"]
    )
    out["is_scoreable"] = out["is_scoreable"].map(lambda b: "true" if b else "false")
    out["is_observed"] = out["is_observed"].map(lambda b: "true" if b else "false")
    out["timestamp"] = out["ts"].map(pd.Timestamp.isoformat)
    out[columns].to_csv(folder / OUTPUT_NAME, index=False)

    report.update({"snapshot_id": args.snapshot, "input": "counts.csv", "output": OUTPUT_NAME})
    (folder / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for k, v in report.items():
        print(f"{k} : {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

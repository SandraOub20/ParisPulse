"""Longues suites de zéros remplacées par les mêmes dates de l'année d'avant - E1, Sabrina.

Décisions E1 (Sabrina, 18/11/2026) : chaque heure d'une suite d'au moins 24 h de zéros
mesurés est comparée au même compteur, à la même date et à la même heure de Paris un an
avant :
- valeur > 0 un an avant : `count` reçoit cette valeur ; `count_raw` garde le 0 d'origine
  (trace : une heure remplacée a `count` différent de `count_raw`) ; `is_scoreable`
  devient faux : la valeur remplacée sert d'entrée, jamais de cible (`doc/CONTRATS.md`
  §3 : « Les cibles ne sont jamais imputées ») ; `is_observed` reste vrai (un 0 a bien
  été mesuré) ;
- 0 un an avant : rien ne change ;
- case vide un an avant : le 0 est gardé (sujet : « ne remplacez pas automatiquement les
  zéros par des valeurs manquantes ») ;
- un an avant inconnu (avant le début de l'instantané, ou avant la première mesure du
  compteur, pas encore installé) : rien ne change.

À savoir : ici, la détection des suites est rétrospective (elle lit toute la série). Dans
l'étude A/C (`zeros.py`), la même règle est appliquée avec une détection sans fuite, à la
coupure d'apprentissage.

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

FILL_VERSION = "e1-fill-zeros-year/0.2.0"
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


def year_before(
    counts: pd.DataFrame, counter_id: pd.Series, ts: pd.Series
) -> tuple[np.ndarray, np.ndarray]:
    """Même compteur, mêmes date et heure de Paris un an avant. Retourne (connue, valeur).

    `connue` est faux avant le début de `counts` ou avant la première mesure du compteur ;
    `valeur` est NaN pour une case vide ou une ligne absente.
    """
    prev = pd.Series([shift_years(t, 1) for t in ts], dtype="datetime64[ns, UTC]")
    cid = counter_id.reset_index(drop=True)
    installed = counts.loc[counts["is_observed"].astype(bool)].groupby("counter_id")["ts"].min()
    known = (prev >= counts["ts"].min()) & (prev >= cid.map(installed))
    idx = pd.MultiIndex.from_frame(pd.DataFrame({"counter_id": cid, "ts": prev}))
    value = counts.set_index(["counter_id", "ts"])["count"].reindex(idx)
    return known.to_numpy(), value.to_numpy(dtype=float)


def fill_zero_runs(counts: pd.DataFrame, min_run: int = MIN_RUN_HOURS) -> tuple[pd.DataFrame, dict]:
    """Remplace `count` des suites de zéros par l'année d'avant si elle est > 0. Retourne (copie, bilan).

    `counts` : colonnes `counter_id`, `ts` (UTC), `count`, `is_observed`, `is_scoreable`.
    """
    df = counts.copy()
    runs = long_runs(df, min_run)
    hours = run_hours(runs)
    report = {
        "fill_version": FILL_VERSION,
        "rule": "suites >= 24 h de zéros mesurés ; même date et heure de Paris un an avant ; "
        "valeur > 0 : count remplacé, is_scoreable faux, count_raw inchangé ; "
        "0, vide ou inconnu un an avant : le 0 est gardé",
        "n_runs": int(len(runs)),
        "n_counters": int(runs["counter_id"].nunique()) if len(runs) else 0,
        "n_hours_in_runs": int(len(hours)),
    }
    if hours.empty:
        kept = {"0 un an avant": 0, "vide un an avant": 0, "un an avant inconnu": 0}
        report.update({"n_hours_replaced": 0, "n_hours_kept": kept})
        return df, report

    known, value = year_before(df, hours["counter_id"], hours["ts"])
    replace = known & (value > 0)  # NaN (vide) n'est jamais > 0 : le 0 est gardé
    target = pd.MultiIndex.from_frame(hours.loc[replace, ["counter_id", "ts"]])
    pos = df.reset_index().set_index(["counter_id", "ts"]).loc[target, "index"].to_numpy()
    df.loc[pos, "count"] = value[replace]
    df.loc[pos, "is_scoreable"] = False  # entrée seulement, jamais une cible

    report.update(
        {
            "n_hours_replaced": int(replace.sum()),
            "n_hours_kept": {
                "0 un an avant": int((known & (value == 0)).sum()),
                "vide un an avant": int((known & np.isnan(value)).sum()),
                "un an avant inconnu": int((~known).sum()),
            },
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

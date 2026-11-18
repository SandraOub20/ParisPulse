"""Longues suites de zéros : reviennent-elles aux mêmes dates d'une année à l'autre ? - E1, Sabrina.

Tâche B1 de la passation de Nihed (17/11/2026), question Q5 : comparer les suites de
2023, 2024 et 2025 avec l'année précédente.

Interprétation de « year - 1 » retenue ici, **à confirmer avec Nihed** : pour chaque
suite d'au moins 24 h de zéros d'un compteur, on regarde le **même compteur** aux
**mêmes dates de Paris un an avant** (et, avec `--annees 1 2`, deux ans avant), et l'on
compte :
- les heures mesurées dans cette fenêtre (0 = non comparable : compteur pas encore
  installé, ou fenêtre avant le début de l'instantané) ;
- parmi elles, celles qui sont dans une suite d'au moins 24 h de zéros.

Analyse descriptive et rétrospective (elle lit toute la série) : elle ne sert jamais de
variable de prévision. Un zéro n'est compté que s'il est mesuré (`is_scoreable`) ; une
heure sans mesure coupe une suite, comme dans `prepare.py` et `zeros.py`.

Usage :
  uv run python -m src.data.zeros_years --snapshot hist-20261117 --annees 1 2
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.data.quality import TZ_LOCAL, load_counts

MIN_RUN_HOURS = 24


def long_runs(counts: pd.DataFrame, min_run: int = MIN_RUN_HOURS) -> pd.DataFrame:
    """Suites d'au moins `min_run` h de zéros mesurés : counter_id, start, end (UTC), n_hours."""
    rows = []
    for cid, g in counts.groupby("counter_id", sort=False):
        g = g.sort_values("ts")
        is_zero = (g["count"].eq(0) & g["is_scoreable"].eq(True)).to_numpy()
        step = g["ts"].diff().ne(pd.Timedelta(hours=1)).to_numpy()
        block = np.cumsum(step | np.r_[True, is_zero[1:] != is_zero[:-1]])
        ts = g["ts"].to_numpy()
        for b in np.unique(block[is_zero]):
            sel = (block == b) & is_zero
            n = int(sel.sum())
            if n >= min_run:
                t = ts[sel]
                rows.append({"counter_id": cid, "start": t.min(), "end": t.max(), "n_hours": n})
    out = pd.DataFrame(rows, columns=["counter_id", "start", "end", "n_hours"])
    for col in ("start", "end"):
        out[col] = pd.to_datetime(out[col], utc=True)
    return out


def shift_years(ts: pd.Timestamp, years: int) -> pd.Timestamp:
    """Même date et même heure de Paris, `years` ans avant, en UTC."""
    wall = ts.tz_convert(TZ_LOCAL).tz_localize(None) - pd.DateOffset(years=years)
    local = wall.tz_localize(TZ_LOCAL, ambiguous=True, nonexistent="shift_forward")
    return local.tz_convert("UTC")


def compare_years(counts: pd.DataFrame, runs: pd.DataFrame, years=(1,)) -> pd.DataFrame:
    """Pour chaque suite, heures mesurées et heures en suite longue aux mêmes dates N ans avant."""
    in_run = {}
    for cid, g in runs.groupby("counter_id"):
        hours = [pd.date_range(r.start, r.end, freq="h") for r in g.itertuples()]
        in_run[cid] = pd.DatetimeIndex(np.concatenate([h.values for h in hours])).tz_localize("UTC")
    measured = {
        cid: pd.DatetimeIndex(g.loc[g["is_scoreable"].eq(True), "ts"])
        for cid, g in counts.groupby("counter_id", sort=False)
    }
    out = runs.copy()
    for k in years:
        obs, hit = [], []
        for r in runs.itertuples():
            window = pd.date_range(shift_years(r.start, k), shift_years(r.end, k), freq="h")
            seen = window.intersection(measured.get(r.counter_id, pd.DatetimeIndex([], tz="UTC")))
            obs.append(len(seen))
            hit.append(len(seen.intersection(in_run.get(r.counter_id, seen[:0]))))
        out[f"measured_hours_y-{k}"] = obs
        out[f"zero_run_hours_y-{k}"] = hit
        share = pd.Series(hit, dtype=float) / pd.Series(obs, dtype=float).replace(0, np.nan)
        out[f"share_y-{k}"] = share.round(3).to_numpy()  # vide = non comparable
    out["start_local"] = out["start"].dt.tz_convert(TZ_LOCAL)
    out["end_local"] = out["end"].dt.tz_convert(TZ_LOCAL)
    return out.drop(columns=["start", "end"]).sort_values(["counter_id", "start_local"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané")
    ap.add_argument("--annees", type=int, nargs="+", default=[1], help="décalages en années")
    ap.add_argument("--seuil", type=int, default=MIN_RUN_HOURS, help="longueur minimale (h)")
    args = ap.parse_args(argv)
    counts = load_counts(data_path("processed") / args.snapshot / "counts.csv")
    runs = long_runs(counts, args.seuil)
    res = compare_years(counts, runs, args.annees)
    pd.set_option("display.width", 250)
    print(f"Instantané {args.snapshot} : {len(runs)} suites >= {args.seuil} h de zéros mesurés")
    print(res.to_string(index=False))
    for k in args.annees:
        comparable = res[f"measured_hours_y-{k}"] > 0
        again = res[f"zero_run_hours_y-{k}"] > 0
        print(
            f"Un an x {k} avant : {int(comparable.sum())} suites comparables, dont "
            f"{int((again & comparable).sum())} avec au moins une heure en suite de zéros "
            f"aux mêmes dates ; {int((~comparable).sum())} non comparables."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

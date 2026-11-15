"""Longues suites de zéros dans l'apprentissage - E1 (approfondissement, Sabrina).

Fiche : reports/experiments/E1-zeros-apprentissage.md (EXP-E1-04).

Deux traitements des heures d'apprentissage, l'évaluation restant identique :
- A (`keep`) : toutes les heures évaluables disponibles à la coupure ;
- B (`drop`) : les mêmes, sauf les heures d'une suite d'au moins 24 h de zéros.

Pas de fuite : à la coupure `F`, seules les heures disponibles à `F` sont lues,
c'est-à-dire `interval_end + délai de publication <= F` (PROTOCOLE_EVALUATION.md §2,
`protocol.publication_lag_hours` de la configuration). Le drapeau `long_zero_run` de
counts.csv, rétrospectif, n'est pas utilisé. Une heure absente (ligne manquante ou
`count` vide) interrompt une suite, comme dans prepare.py. `count` n'est jamais modifié.

Usage (description des heures retirées, aucun modèle) :
  uv run python -m src.data.zeros --snapshot flux-20261115 --coupure 2026-07-01
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from src.common.config import data_path, load_config
from src.data.quality import TZ_LOCAL, load_counts

MIN_RUN_HOURS = 24  # même seuil que prepare.LONG_ZERO_RUN_HOURS
DEFAULT_LAG_HOURS = 24  # protocol.publication_lag_hours du gabarit de configuration
ZEROS_VERSION = "e1-zeros/0.1.0"
TREATMENTS = ("keep", "drop")  # A, B


def publication_lag_hours() -> int:
    """Délai de publication des comptages, lu dans la configuration commune."""
    value = (load_config().get("protocol") or {}).get("publication_lag_hours")
    return DEFAULT_LAG_HOURS if value is None else int(value)


def local_midnight(day: str) -> pd.Timestamp:
    """Minuit heure de Paris d'une date AAAA-MM-JJ, en UTC."""
    return pd.Timestamp(day).tz_localize(TZ_LOCAL).tz_convert("UTC")


def available_at_cutoff(ts: pd.Series, cutoff: pd.Timestamp, lag_hours: int) -> pd.Series:
    """Vrai si l'heure commençant à `ts` est publiée à la coupure."""
    return ts + pd.Timedelta(hours=1 + lag_hours) <= cutoff


def long_zero_mask(
    counts: pd.DataFrame,
    cutoff: pd.Timestamp,
    lag_hours: int | None = None,
    min_run: int = MIN_RUN_HOURS,
) -> pd.Series:
    """Heures disponibles à la coupure appartenant à une suite >= `min_run` h de zéros.

    `counts` : colonnes `counter_id`, `ts` (UTC), `count` (NaN = absent).
    Retour aligné sur `counts.index` ; Faux pour toute heure non disponible.
    """
    lag = publication_lag_hours() if lag_hours is None else lag_hours
    out = pd.Series(False, index=counts.index)
    avail = counts[available_at_cutoff(counts["ts"], cutoff, lag)]
    for _, g in avail.groupby("counter_id", sort=False):
        g = g.sort_values("ts")
        is_zero = g["count"].eq(0).to_numpy()
        # Une heure manquante dans la grille (écart > 1 h) coupe aussi la suite
        step = g["ts"].diff().ne(pd.Timedelta(hours=1)).to_numpy()
        new_block = step | np.r_[True, is_zero[1:] != is_zero[:-1]]
        block = np.cumsum(new_block)
        length = pd.Series(is_zero.astype(int)).groupby(block).transform("sum").to_numpy()
        out.loc[g.index[is_zero & (length >= min_run)]] = True
    return out


def training_mask(
    counts: pd.DataFrame,
    cutoff: pd.Timestamp,
    treatment: str,
    lag_hours: int | None = None,
    min_run: int = MIN_RUN_HOURS,
) -> pd.Series:
    """Heures utilisables pour apprendre à la coupure, selon le traitement A ou B."""
    if treatment not in TREATMENTS:
        raise ValueError(f"Traitement inconnu : {treatment} (attendu : {TREATMENTS})")
    lag = publication_lag_hours() if lag_hours is None else lag_hours
    mask = available_at_cutoff(counts["ts"], cutoff, lag) & counts["is_scoreable"]
    if treatment == "drop":
        mask &= ~long_zero_mask(counts, cutoff, lag, min_run)
    return mask


def excluded_summary(
    counts: pd.DataFrame,
    cutoff: pd.Timestamp,
    lag_hours: int | None = None,
    min_run: int = MIN_RUN_HOURS,
) -> pd.DataFrame:
    """Par compteur : suites retirées par B, heures, dates, part des heures observées."""
    lag = publication_lag_hours() if lag_hours is None else lag_hours
    long = long_zero_mask(counts, cutoff, lag, min_run)
    avail = available_at_cutoff(counts["ts"], cutoff, lag)
    rows = []
    for cid, g in counts[long].sort_values("ts").groupby("counter_id"):
        new_run = g["ts"].diff().ne(pd.Timedelta(hours=1))
        observed = int((avail & counts["is_scoreable"] & counts["counter_id"].eq(cid)).sum())
        rows.append(
            {
                "counter_id": cid,
                "n_runs": int(new_run.sum()),
                "n_hours_dropped": len(g),
                "first_local": g["ts"].min().tz_convert(TZ_LOCAL),
                "last_local": g["ts"].max().tz_convert(TZ_LOCAL),
                "share_of_training_hours": round(len(g) / observed, 4) if observed else np.nan,
            }
        )
    cols = [
        "counter_id",
        "n_runs",
        "n_hours_dropped",
        "first_local",
        "last_local",
        "share_of_training_hours",
    ]
    return pd.DataFrame(rows, columns=cols).sort_values("n_hours_dropped", ascending=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané")
    ap.add_argument("--coupure", required=True, help="date locale de coupure AAAA-MM-JJ")
    args = ap.parse_args(argv)
    counts = load_counts(data_path("processed") / args.snapshot / "counts.csv")
    cutoff = local_midnight(args.coupure)
    summary = excluded_summary(counts, cutoff)
    print(f"Coupure {args.coupure} 00:00 (Paris), délai {publication_lag_hours()} h")
    print(summary.to_string(index=False))
    print(f"Total : {summary['n_hours_dropped'].sum()} heures, {len(summary)} compteurs")
    return 0


if __name__ == "__main__":
    sys.exit(main())

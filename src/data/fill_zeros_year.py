"""Longues suites de zéros remplacées par les mêmes dates de l'année d'avant - E1, Sabrina.

Décisions E1 (Sabrina, 18 et 19/11/2026) : chaque heure marquée `long_zero_run` dans
`quality_flags` (suite d'au moins 24 h de zéros mesurés, drapeau de prepare.py) est
comparée au même compteur, à la même date et à la même heure de Paris un an avant :
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

Sans colonne `quality_flags` (jeux de test), les suites sont recalculées avec la même
règle (`zeros_years.long_runs`) ; sur `hist-20261117`, les deux donnent exactement les
mêmes 51 789 heures (vérifié le 19/11/2026).

À savoir : le drapeau `long_zero_run` est rétrospectif (il lit toute la série). Dans
l'étude A/C (`zeros.py`), la même règle est appliquée avec une détection sans fuite, à la
coupure d'apprentissage.

Appelé par `fill_counts.py` (une seule commande, qui remplit directement counts.csv) ;
à lancer sur l'historique (`hist-…`), qui contient l'année d'avant.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.data.zeros_years import MIN_RUN_HOURS, long_runs, shift_years

FILL_VERSION = "e1-fill-zeros-year/0.3.0"


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


def _has_long_zero_run(flags) -> bool:
    if isinstance(flags, list):
        return "long_zero_run" in flags
    return isinstance(flags, str) and "long_zero_run" in json.loads(flags or "[]")


def flagged_hours(counts: pd.DataFrame, min_run: int = MIN_RUN_HOURS) -> pd.DataFrame:
    """Heures à traiter : drapeau `long_zero_run` (ou suites recalculées sans drapeaux)."""
    if "quality_flags" not in counts.columns:
        return run_hours(long_runs(counts, min_run))
    flagged = counts["quality_flags"].map(_has_long_zero_run)
    out = counts.loc[flagged, ["counter_id", "ts"]].sort_values(["counter_id", "ts"])
    return out.reset_index(drop=True)


def count_runs(hours: pd.DataFrame) -> int:
    """Nombre de suites : heures consécutives d'un même compteur."""
    if hours.empty:
        return 0
    new = hours["counter_id"].ne(hours["counter_id"].shift()) | hours["ts"].diff().ne(
        pd.Timedelta(hours=1)
    )
    return int(new.sum())


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
    hours = flagged_hours(df, min_run)
    report = {
        "fill_version": FILL_VERSION,
        "rule": "heures marquées long_zero_run ; même date et heure de Paris un an avant ; "
        "valeur > 0 : count remplacé, is_scoreable faux, count_raw inchangé ; "
        "0, vide ou inconnu un an avant : le 0 est gardé",
        "n_runs": count_runs(hours),
        "n_counters": int(hours["counter_id"].nunique()),
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

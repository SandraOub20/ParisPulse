"""Suites de zéros d'une année à l'autre (src/data/zeros_years.py), sur données synthétiques."""

import numpy as np
import pandas as pd

from src.data.zeros_years import compare_years, long_runs, shift_years


def series(start: str, end: str, cid: str = "c1", zeros=(), missing=()):
    ts = pd.date_range(start, end, freq="h", tz="UTC")
    count = pd.Series(10.0, index=ts)
    for a, b in zeros:
        count[a:b] = 0.0
    for a, b in missing:
        count[a:b] = np.nan
    return pd.DataFrame(
        {
            "counter_id": cid,
            "ts": ts,
            "count": count.to_numpy(),
            "is_observed": count.notna().to_numpy(),
            "is_scoreable": count.notna().to_numpy(),
        }
    )


def test_suite_qui_revient_aux_memes_dates():
    z = [("2024-03-10 00:00", "2024-03-11 23:00"), ("2025-03-10 00:00", "2025-03-11 23:00")]
    c = series("2024-01-01", "2025-12-31", zeros=z)
    runs = long_runs(c)
    assert list(runs["n_hours"]) == [48, 48]
    res = compare_years(c, runs).set_index("start_local")
    last = res.iloc[-1]
    assert last["measured_hours_y-1"] == 48 and last["zero_run_hours_y-1"] == 48
    assert last["share_y-1"] == 1.0
    assert np.isnan(res.iloc[0]["share_y-1"])  # 2023 hors de l'instantané : non comparable


def test_suite_qui_ne_revient_pas():
    c = series("2024-01-01", "2025-12-31", zeros=[("2025-06-01 00:00", "2025-06-02 23:00")])
    res = compare_years(c, long_runs(c))
    assert res.iloc[0]["measured_hours_y-1"] == 48
    assert res.iloc[0]["zero_run_hours_y-1"] == 0


def test_heure_sans_mesure_coupe_la_suite():
    c = series(
        "2025-01-01",
        "2025-01-10",
        zeros=[("2025-01-03 00:00", "2025-01-04 23:00")],
        missing=[("2025-01-04 00:00", "2025-01-04 00:00")],
    )
    # 48 h de zéros coupées par une heure vide : 24 h puis 23 h, une seule suite >= 24 h
    assert list(long_runs(c)["n_hours"]) == [24]


def test_meme_heure_de_paris_un_an_avant():
    t = pd.Timestamp("2025-07-14 06:00", tz="UTC")  # 8 h à Paris (heure d'été)
    assert shift_years(t, 1) == pd.Timestamp("2024-07-14 06:00", tz="UTC")
    t = pd.Timestamp("2025-01-14 07:00", tz="UTC")  # 8 h à Paris (heure d'hiver)
    assert shift_years(t, 2) == pd.Timestamp("2023-01-14 07:00", tz="UTC")

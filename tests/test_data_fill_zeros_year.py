"""Suites de zéros remplacées par l'année d'avant (src/data/fill_zeros_year.py)."""

import numpy as np
import pandas as pd

from src.data.fill_zeros_year import fill_zero_runs


def series(start: str, end: str, value=10.0, zeros=(), missing=(), override=None):
    ts = pd.date_range(start, end, freq="h", tz="UTC")
    count = pd.Series(value, index=ts, dtype=float)
    for a, b in zeros:
        count[a:b] = 0.0
    for a, b in missing:
        count[a:b] = np.nan
    for t, v in (override or {}).items():
        count[t] = v
    observed = count.notna().to_numpy()
    return pd.DataFrame(
        {
            "counter_id": "c1",
            "ts": ts,
            "count": count.to_numpy(),
            "is_observed": observed,
            "is_scoreable": observed,
        }
    )


RUN = ("2025-03-10 00:00", "2025-03-11 23:00")  # 48 h de zéros


def test_suite_remplacee_par_l_annee_d_avant():
    c = series("2024-01-01", "2025-12-31", zeros=[RUN], override={"2024-03-10 05:00": 77.0})
    out, rep = fill_zero_runs(c)
    run = out.set_index("ts").loc[RUN[0] : RUN[1]]
    assert (run["count"] > 0).all()
    assert run.loc["2025-03-10 05:00", "count"] == 77.0  # même heure, un an avant
    assert rep["n_hours_replaced"] == 48 and rep["replaced_by"]["valeur > 0"] == 48


def test_zero_et_vide_recopies_tels_quels():
    c = series(
        "2024-01-01",
        "2025-12-31",
        zeros=[RUN, ("2024-03-10 00:00", "2024-03-10 03:00")],
        missing=[("2024-03-11 10:00", "2024-03-11 11:00")],
    )
    out, rep = fill_zero_runs(c)
    run = out.set_index("ts").loc[RUN[0] : RUN[1]]
    assert (run.loc["2025-03-10 00:00":"2025-03-10 03:00", "count"] == 0).all()
    assert run.loc["2025-03-11 10:00":"2025-03-11 11:00", "count"].isna().all()
    assert not run.loc["2025-03-11 10:00", "is_scoreable"]  # vide : non évaluable
    assert rep["replaced_by"] == {"valeur > 0": 42, "0": 4, "vide": 2}


def test_annee_d_avant_hors_instantane_inchangee():
    c = series("2025-01-01", "2025-12-31", zeros=[RUN])
    out, rep = fill_zero_runs(c)
    assert (out.set_index("ts").loc[RUN[0] : RUN[1], "count"] == 0).all()
    assert rep["n_hours_replaced"] == 0 and rep["n_hours_before_snapshot"] == 48


def test_suite_courte_et_heures_hors_suite_inchangees():
    c = series("2024-01-01", "2025-12-31", zeros=[("2025-05-01 00:00", "2025-05-01 22:00")])
    out, rep = fill_zero_runs(c)
    assert rep["n_runs"] == 0
    assert out["count"].equals(c["count"])


def test_meme_heure_de_paris_en_ete_et_en_hiver():
    # 10/03/2025 06:00 UTC = 7 h Paris (hiver) ; un an avant : 10/03/2024 06:00 UTC
    # 10/07/2025 05:00 UTC = 7 h Paris (été) ; un an avant : 10/07/2024 05:00 UTC
    run_ete = ("2025-07-10 00:00", "2025-07-11 23:00")
    c = series(
        "2024-01-01",
        "2025-12-31",
        zeros=[RUN, run_ete],
        override={"2024-03-10 06:00": 11.0, "2024-07-10 05:00": 22.0},
    )
    out, _ = fill_zero_runs(c)
    o = out.set_index("ts")["count"]
    assert o["2025-03-10 06:00"] == 11.0 and o["2025-07-10 05:00"] == 22.0

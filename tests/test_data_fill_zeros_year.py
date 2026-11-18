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


def test_suite_remplacee_par_l_annee_d_avant_et_plus_une_cible():
    c = series("2024-01-01", "2025-12-31", zeros=[RUN], override={"2024-03-10 05:00": 77.0})
    out, rep = fill_zero_runs(c)
    run = out.set_index("ts").loc[RUN[0] : RUN[1]]
    assert (run["count"] > 0).all()
    assert run.loc["2025-03-10 05:00", "count"] == 77.0  # même heure, un an avant
    assert not run["is_scoreable"].any()  # valeur remplacée : entrée, jamais cible
    assert run["is_observed"].all()  # le 0 a bien été mesuré
    assert rep["n_hours_replaced"] == 48
    hors = out.set_index("ts").drop(index=run.index)
    assert hors["is_scoreable"].all()  # les autres heures ne changent pas


def test_zero_ou_vide_un_an_avant_le_zero_est_garde():
    c = series(
        "2024-01-01",
        "2025-12-31",
        zeros=[RUN, ("2024-03-10 00:00", "2024-03-10 03:00")],
        missing=[("2024-03-11 10:00", "2024-03-11 11:00")],
    )
    out, rep = fill_zero_runs(c)
    run = out.set_index("ts").loc[RUN[0] : RUN[1]]
    gardes = run.loc["2025-03-10 00:00":"2025-03-10 03:00"]
    vides = run.loc["2025-03-11 10:00":"2025-03-11 11:00"]
    for kept in (gardes, vides):
        assert (kept["count"] == 0).all()  # jamais un zéro remplacé par une case vide
        assert kept["is_scoreable"].all()  # rien n'est remplacé : le zéro reste une cible
    assert rep["n_hours_replaced"] == 42
    assert rep["n_hours_kept"] == {
        "0 un an avant": 4,
        "vide un an avant": 2,
        "un an avant inconnu": 0,
    }


def test_annee_d_avant_hors_instantane_inchangee():
    c = series("2025-01-01", "2025-12-31", zeros=[RUN])
    out, rep = fill_zero_runs(c)
    assert (out.set_index("ts").loc[RUN[0] : RUN[1], "count"] == 0).all()
    assert rep["n_hours_replaced"] == 0 and rep["n_hours_kept"]["un an avant inconnu"] == 48


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

"""J-7 et année d'avant appliqués ensemble (src/data/fill_counts.py)."""

import numpy as np
import pandas as pd

from src.data.fill_counts import fill_counts

RUN = ("2025-03-10 00:00", "2025-03-11 23:00")  # 48 h de zéros mesurés


def frame(missing=(), override=None):
    ts = pd.date_range("2024-01-01", "2025-12-31", freq="h", tz="UTC")
    count = pd.Series(10.0, index=ts)
    count[RUN[0] : RUN[1]] = 0.0
    for t, v in (override or {}).items():
        count[t] = v
    flags = pd.Series([[] for _ in ts], index=ts, dtype=object)
    for t in missing:
        count[t] = np.nan
        flags[t] = ["missing"]
    observed = count.notna()
    return pd.DataFrame(
        {
            "counter_id": "c1",
            "ts": ts,
            "count": count.to_numpy(),
            "is_observed": observed.to_numpy(),
            "is_scoreable": observed.to_numpy(),
            "quality_flags": flags.to_list(),
        }
    )


def test_j7_pour_les_heures_sans_mesure_et_annee_d_avant_pour_les_zeros():
    df = frame(
        missing=["2025-06-10 08:00"],
        override={"2025-06-03 08:00": 55.0, "2024-03-10 05:00": 77.0},
    )
    out, rep = fill_counts(df)
    o = out.set_index("ts")
    assert o.loc["2025-06-10 08:00", "count"] == 55.0  # J-7
    assert not o.loc["2025-06-10 08:00", "is_scoreable"]
    assert o.loc["2025-03-10 05:00", "count"] == 77.0  # année d'avant
    assert not o.loc["2025-03-10 05:00", "is_scoreable"]  # jamais une cible
    assert (o.loc[RUN[0] : RUN[1], "count"] > 0).all()
    assert rep["j7"]["n_hours_filled"] == 1
    assert rep["zero_runs_year_before"]["n_hours_replaced"] == 48


def test_vide_un_an_avant_le_zero_est_garde():
    # un an avant la 1re heure de la suite : heure sans mesure -> le 0 reste
    df = frame(missing=["2024-03-10 00:00"])
    out, _ = fill_counts(df)
    o = out.set_index("ts")
    assert o.loc["2025-03-10 00:00", "count"] == 0.0  # pas une case vide, pas de J-7
    assert o.loc["2025-03-10 00:00", "is_scoreable"]  # zéro observé : reste une cible


def test_chaque_remplacement_lit_les_donnees_d_origine():
    # J-7 d'une heure manquante tombe dans la suite de zéros : J-7 = 0 d'origine
    df = frame(missing=["2025-03-17 05:00"], override={"2024-03-10 05:00": 77.0})
    out, _ = fill_counts(df)
    assert out.set_index("ts").loc["2025-03-17 05:00", "count"] == 0.0

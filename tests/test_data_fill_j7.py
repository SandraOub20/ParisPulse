"""Remplacement J-7 des heures sans mesure (src/data/fill_j7.py), sur données synthétiques."""

import numpy as np
import pandas as pd

from src.data.fill_j7 import fill_j7, j7_timestamps
from src.data.zeros import long_zero_mask


def frame(start: str, values, cid: str = "c1") -> pd.DataFrame:
    ts = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    count = pd.Series(values, dtype=float)
    observed = count.notna()
    return pd.DataFrame(
        {
            "counter_id": cid,
            "ts": ts,
            "count": count,
            "is_observed": observed,
            "is_scoreable": observed,
            "quality_flags": [[] if o else ["missing"] for o in observed],
        }
    )


def test_heure_vide_remplacee_directement_dans_count():
    values = list(range(1, 24 * 8 + 1))
    values[24 * 7 + 5] = None  # même heure J-7 : values[5] = 6
    out, rep = fill_j7(frame("2026-03-02", values))
    row = out.iloc[24 * 7 + 5]
    assert row["count"] == 6
    assert row["quality_flags"] == ["missing"]  # aucun drapeau ajouté
    assert not row["is_observed"] and not row["is_scoreable"]  # jamais en évaluation
    assert rep["n_hours_filled"] == 1 and rep["n_hours_left_empty"] == 0
    assert "count_filled_j7" not in out.columns


def test_heure_mesuree_inchangee():
    values = [float(i % 24) for i in range(24 * 8)]
    values[24 * 7 + 2] = None
    df = frame("2026-03-02", values)
    out, _ = fill_j7(df)
    mesure = df["is_scoreable"]
    assert out.loc[mesure, "count"].equals(df.loc[mesure, "count"])
    assert out["is_scoreable"].equals(df["is_scoreable"])


def test_j7_sans_mesure_reste_vide():
    values = list(range(1, 24 * 15 + 1))
    values[7] = None  # aucune heure J-7 dans le fichier
    values[24 * 7 + 5] = None  # J-7 = values[5] = 6, mesurée
    values[24 * 14 + 5] = None  # J-7 elle-même remplacée, donc non mesurée ; J-14 non utilisée
    out, rep = fill_j7(frame("2026-03-02", values))
    assert np.isnan(out.iloc[7]["count"])
    assert out.iloc[24 * 7 + 5]["count"] == 6
    assert np.isnan(out.iloc[24 * 14 + 5]["count"])
    assert rep["n_hours_filled"] == 1 and rep["n_hours_left_empty"] == 2


def test_rien_hors_periode_active():
    values = [None] * 24 * 7 + [5.0] * 24 + [None] * 24 * 8
    out, rep = fill_j7(frame("2026-03-02", values))
    assert out["count"].notna().sum() == 24  # avant la 1re et après la dernière mesure
    assert rep["n_hours_filled"] == 0


def test_ligne_non_recue_creee_puis_remplie():
    df = frame("2026-03-02", [float(i) for i in range(24 * 8)])
    df = df.drop(index=24 * 7 + 3).reset_index(drop=True)
    out, rep = fill_j7(df)
    assert rep["n_rows_created"] == 1
    assert len(out) == 24 * 8
    row = out[out["ts"] == pd.Timestamp("2026-03-09 03:00", tz="UTC")].iloc[0]
    assert row["count"] == 3 and not row["is_observed"]
    assert row["quality_flags"] == ["missing"]


def test_j7_heure_de_paris_au_changement_d_heure():
    # 29/03/2026 : passage à l'heure d'été. Lundi 30/03 8 h Paris = 06:00 UTC ;
    # J-7 = lundi 23/03 8 h Paris = 07:00 UTC (et non 168 h avant).
    ts = pd.Series([pd.Timestamp("2026-03-30 06:00", tz="UTC")])
    assert j7_timestamps(ts).iloc[0] == pd.Timestamp("2026-03-23 07:00", tz="UTC")
    # 05/04 2 h Paris : le 29/03 à 2 h n'existe pas -> pas de J-7
    ts = pd.Series([pd.Timestamp("2026-04-05 00:00", tz="UTC")])
    assert pd.isna(j7_timestamps(ts).iloc[0])


def test_zero_remplace_ne_rallonge_pas_une_suite():
    # 20 zéros, 1 heure vide remplacée par un 0 de J-7, 20 zéros : pas de suite >= 24 h
    values = [1.0] * 24 * 7 + [0.0] * 20 + [None] + [0.0] * 20 + [1.0] * 30
    values[24 * 7 + 20 - 168] = 0.0
    out, rep = fill_j7(frame("2026-01-05", values))
    assert rep["n_hours_filled"] == 1
    assert out.iloc[24 * 7 + 20]["count"] == 0
    mask = long_zero_mask(out, pd.Timestamp("2027-01-01", tz="UTC"), lag_hours=24)
    assert not mask.any()

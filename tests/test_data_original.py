"""Retour aux valeurs d'origine d'un counts.csv rempli (src/data/original.py)."""

import pandas as pd

from src.data.original import load_original_counts


def test_valeurs_d_origine_retrouvees(tmp_path):
    rows = [
        # counter_id, timestamp, count, count_raw, is_observed, is_scoreable
        ("c", "2026-01-01T00:00:00+00:00", "12.0", "12", "true", "true"),  # mesure normale
        ("c", "2026-01-01T01:00:00+00:00", "7.0", "", "false", "false"),  # J-7
        ("c", "2026-01-01T02:00:00+00:00", "4.0", "0", "true", "false"),  # année d'avant
        ("c", "2026-01-01T03:00:00+00:00", "0", "0", "true", "true"),  # zéro gardé
        ("c", "2026-01-01T04:00:00+00:00", "", "", "false", "false"),  # vide restée vide
        ("c", "2026-01-01T05:00:00+00:00", "", "-3", "true", "false"),  # invalide d'origine
    ]
    cols = ["counter_id", "timestamp", "count", "count_raw", "is_observed", "is_scoreable"]
    path = tmp_path / "counts.csv"
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    out = load_original_counts(path)
    assert out["count"].iloc[0] == 12.0  # mesure normale inchangée
    assert pd.isna(out["count"].iloc[1])  # J-7 : redevient vide
    assert out["count"].iloc[2] == 0.0 and out["is_scoreable"].iloc[2]  # le 0 mesuré revient
    assert out["count"].iloc[3] == 0.0 and out["is_scoreable"].iloc[3]
    assert pd.isna(out["count"].iloc[4]) and pd.isna(out["count"].iloc[5])
    assert not out["is_scoreable"].iloc[5]

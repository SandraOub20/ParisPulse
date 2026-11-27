"""Solidité d'un gain (robustness.py), sur un petit exemple calculé à la main."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.known import robustness as R

PARIS = "Europe/Paris"


def _data(n_days=10, model_err=1.0, ref_err=2.0):
    """2 compteurs, n_days jours ; erreur constante : modèle 1, référence 2 (gain 50 %)."""
    fc, obs = [], []
    for k in range(n_days):
        origin = pd.Timestamp("2026-07-01", tz=PARIS).tz_convert("UTC") + pd.Timedelta(days=k)
        for counter in ("A", "B"):
            case = f"{counter}_{origin.strftime('%Y%m%dT%H')}_known_site"
            for h in range(24):
                t = origin + pd.Timedelta(hours=h)
                obs.append(
                    {"counter_id": counter, "timestamp": t, "count_raw": 10.0, "is_scoreable": True}
                )
                for m, e in (("mod", model_err), ("ref", ref_err)):
                    fc.append(
                        {
                            "case_id": case,
                            "counter_id": counter,
                            "target_timestamp": t,
                            "y_pred": 10.0 + e,
                            "method_run_id": m,
                        }
                    )
    return pd.DataFrame(fc), pd.DataFrame(obs)


def test_heures_communes_et_jour_local():
    fc, obs = _data(n_days=2)
    obs.loc[0, "is_scoreable"] = False  # une vérité non évaluable : heure retirée
    fc = fc.drop(index=fc[(fc.method_run_id == "ref")].index[5])  # une prévision manquante
    wide = R.paired_hours(fc, obs, ["mod", "ref"])
    assert len(wide) == 2 * 2 * 24 - 2
    assert set(wide["day"]) == {"2026-07-01", "2026-07-02"}  # origine 22:00Z = minuit à Paris


def test_tranches_et_wape():
    fc, obs = _data(n_days=1)
    table = R.by_band(R.paired_hours(fc, obs, ["mod", "ref"]), ["mod", "ref"])
    assert table.loc["toutes les heures", "heures"] == 48
    assert table.loc["pointe matin 7-9 h", "heures"] == 4  # 7 h et 8 h, 2 compteurs
    assert table.loc["toutes les heures", "MAE ref"] == pytest.approx(2.0)
    assert table.loc["nuit 0-6 h", "WAPE mod"] == pytest.approx(0.1)  # 1 / 10


def test_mois_et_bootstrap():
    fc, obs = _data(n_days=10)
    wide = R.paired_hours(fc, obs, ["mod", "ref"])
    assert R.macro_mae(wide, "ref") == pytest.approx(2.0)
    month = R.by_month(wide, "mod", "ref")
    assert month.loc["2026-07", "gain"] == pytest.approx(0.5)
    out = R.bootstrap_gain(wide, "mod", "ref", n_boot=200)
    # erreurs constantes : tous les tirages donnent 50 %, intervalle réduit à un point
    assert out["gain"] == pytest.approx(0.5) and out["low"] == pytest.approx(0.5)
    assert out["days"] == 10


def test_bootstrap_elargit_quand_le_gain_varie_selon_les_jours():
    fc, obs = _data(n_days=20)
    day = pd.to_datetime(fc.target_timestamp, utc=True).dt.tz_convert(PARIS).dt.day
    noisy = (fc.method_run_id == "mod") & (day % 2 == 0)
    fc.loc[noisy, "y_pred"] = 10.0 + 3.0  # un jour sur deux, le modèle est pire
    out = R.bootstrap_gain(R.paired_hours(fc, obs, ["mod", "ref"]), "mod", "ref", n_boot=500)
    assert out["low"] < out["gain"] < out["high"]
    assert np.isfinite([out["low"], out["high"]]).all()

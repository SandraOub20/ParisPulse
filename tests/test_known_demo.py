"""Démonstration d'un cas (demo.py), sur une petite série inventée."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from src.models.known import demo as D

PARIS = "Europe/Paris"


def _history() -> pd.DataFrame:
    hours = pd.date_range(
        pd.Timestamp("2026-06-01", tz=PARIS).tz_convert("UTC"), periods=24 * 50, freq="h"
    )
    value = (np.arange(len(hours)) % 24).astype(float)
    return pd.DataFrame(
        {
            "counter_id": "C-1",
            "timestamp": hours,
            "interval_end": hours + pd.Timedelta(hours=1),
            "count": value,
            "count_raw": value,
            "is_observed": True,
        }
    )


def _cases() -> pd.DataFrame:
    origin = pd.Timestamp("2026-07-10", tz=PARIS).tz_convert("UTC")
    return pd.DataFrame(
        {
            "case_id": ["C-1_case"],
            "counter_id": ["C-1"],
            "site_group_id": ["G"],
            "origin": [origin.isoformat()],
            "scenario": ["known_site"],
            "temporal_split": ["validation"],
            "spatial_role": ["S_train"],
            "local_budget_hours": [""],
            "support_start": [""],
            "support_end": [""],
            "protocol_id": ["test"],
            "snapshot_id": ["synthetic"],
        }
    )


def test_find_case_par_jour_local():
    case = D.find_case(_cases(), "C-1", "2026-07-10")
    assert case.origin == pd.Timestamp("2026-07-09T22:00Z")
    with pytest.raises(ValueError, match="aucun cas"):
        D.find_case(_cases(), "C-1", "2026-07-11")


def test_case_view_semaine_visible_et_verite():
    case = D.find_case(_cases(), "C-1", "2026-07-10")
    view = D.case_view(case, _history(), publication_lag_hours=24)
    assert len(view["visible"]) == 168 and len(view["truth"]) == 24
    assert view["visible"]["timestamp"].max() == case.origin - pd.Timedelta(hours=25)
    assert view["truth"]["timestamp"].min() == case.origin


def test_forecast_case_et_graphique():
    case = D.find_case(_cases(), "C-1", "2026-07-10")
    variants = {
        "7 jours avant": {"variant": "reference"},
        "Médiane": {"variant": "reference_profile"},
    }
    out = D.forecast_case(case, _history(), variants, publication_lag_hours=24)
    assert out.groupby("method").size().to_dict() == {"7 jours avant": 24, "Médiane": 24}
    assert (out["prediction_status"] == "ok").all()
    # série périodique sur 24 h : la référence redonne la vérité
    truth = D.case_view(case, _history(), publication_lag_hours=24)["truth"]
    ref = out[out["method"] == "7 jours avant"]
    np.testing.assert_allclose(ref["y_pred"].to_numpy(), truth["count"].to_numpy())
    ax = D.plot_case(D.case_view(case, _history(), 24), out, title="test")
    assert len(ax.get_lines()) == 4


def test_jours_de_pluie_prevue():
    valid = pd.date_range(pd.Timestamp("2026-07-01", tz=PARIS), periods=48, freq="h")
    rain = np.zeros(48)
    rain[30:33] = 0.5  # 1,5 mm le 2 juillet (heure de Paris)
    context = pd.DataFrame(
        {
            "variable": "rain_prev",
            "valid_time": valid.tz_convert("UTC").map(pd.Timestamp.isoformat),
            "value": rain.astype(str),
        }
    )
    assert D.rainy_days(context) == {"2026-07-02"}
    assert D.rainy_days(context, threshold_mm=2.0) == set()


def test_tranche_d_heures_mesurees():
    history = _history()
    case = D.find_case(_cases(), "C-1", "2026-07-10")
    band = D.observed_hours_band(_cases(), lambda c: history, publication_lag_hours=24)
    assert band[case.case_id] == "168-140 h"
    from src.models.known import batch as B

    holed = B.degrade_history(history, case, "panne-96", 24)  # il reste 72 h
    band = D.observed_hours_band(_cases(), lambda c: holed, publication_lag_hours=24)
    assert band[case.case_id] == "83-24 h"

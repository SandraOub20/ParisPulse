"""Tests E4 : scores, heure décalée, doublon, prévision manquante, compteur sans mesure."""

import numpy as np
import pandas as pd
import pytest

from src.eval.metrics import evaluate_all

ORIGIN = pd.Timestamp("2026-07-01 22:00", tz="UTC")
HOURS = [ORIGIN + pd.Timedelta(hours=h) for h in range(24)]


def make(preds, measured=None):
    """preds : {(compteur, méthode): 24 valeurs}. measured : {compteur: nb d'heures mesurées}."""
    counters = sorted({c for c, _ in preds})
    measured = measured or {}
    cases = pd.DataFrame(
        {
            "case_id": [f"{c}_case" for c in counters],
            "counter_id": counters,
            "origin": ORIGIN,
            "scenario": "known_site",
        }
    )
    obs = pd.DataFrame(
        [
            (c, t, 10.0, h < measured.get(c, 24), h < measured.get(c, 24))
            for c in counters
            for h, t in enumerate(HOURS)
        ],
        columns=["counter_id", "timestamp", "count", "is_observed", "is_scoreable"],
    )
    rows = [
        (f"{c}_case", m, c, h + 1, t, v, "", "ok")
        for (c, m), vals in preds.items()
        for h, (t, v) in enumerate(zip(HOURS, vals))
    ]
    fc = pd.DataFrame(
        rows,
        columns=[
            "case_id",
            "method_run_id",
            "counter_id",
            "horizon",
            "target_timestamp",
            "y_pred",
            "variant",
            "prediction_status",
        ],
    )
    return cases, fc, obs


def test_hand_example():
    # compteur A : erreurs +2 (12 h) puis -3 (12 h) ; compteur B : +4 sur 12 h mesurées seulement
    a = [12.0] * 12 + [7.0] * 12
    b = [14.0] * 24
    cases, fc, obs = make({("A", "m"): a, ("B", "m"): b}, measured={"B": 12})
    out = evaluate_all(cases, fc, obs)
    by = out["metrics_by_counter"].set_index("counter_id")
    assert by.loc["A", "MAE"] == pytest.approx(2.5)  # (12*2 + 12*3) / 24
    assert by.loc["A", "bias"] == pytest.approx(-0.5)  # (12*2 - 12*3) / 24
    assert by.loc["A", "RMSE"] == pytest.approx(np.sqrt(6.5))  # (12*4 + 12*9) / 24
    assert by.loc["A", "MAPE"] == pytest.approx(25.0)  # (12*0.2 + 12*0.3) / 24 * 100
    assert by.loc["B", "n_predictions"] == 12
    assert by.loc["B", "MAE"] == pytest.approx(4.0)
    assert out["global_metrics"]["MAE"].iloc[0] == pytest.approx(3.25)  # moyenne non pondérée


def test_shifted_hour():
    cases, fc, obs = make({("A", "m"): [10.0] * 24})
    fc["target_timestamp"] = fc["target_timestamp"] + pd.Timedelta(hours=1)
    with pytest.raises(ValueError, match="timestamp"):
        evaluate_all(cases, fc, obs)


def test_duplicate_forecast():
    cases, fc, obs = make({("A", "m"): [10.0] * 24})
    with pytest.raises(ValueError, match="dupliqu"):
        evaluate_all(cases, pd.concat([fc, fc.iloc[[0]]]), obs)


def test_duplicate_observation():
    cases, fc, obs = make({("A", "m"): [10.0] * 24})
    with pytest.raises(ValueError, match="dupliqu"):
        evaluate_all(cases, fc, pd.concat([obs, obs.iloc[[0]]]))


def test_missing_forecast_hours():
    full = [12.0] * 24
    cases, fc, obs = make({("A", "full"): full, ("A", "short"): full})
    fc = fc[~((fc["method_run_id"] == "short") & (fc["horizon"] > 19))]
    out = evaluate_all(cases, fc, obs)
    cov = out["coverage"].set_index("method_run_id")
    assert cov.loc["short", "n_predicted_hours"] == 19
    assert cov.loc["short", "coverage_status"] == "partial"
    assert cov.loc["full", "coverage_status"] == "complete"
    by = out["metrics_by_counter"].set_index("method_run_id")
    assert by.loc["short", "n_predictions"] == 19  # heures manquantes jamais comptées comme 0
    assert by.loc["short", "MAE"] == pytest.approx(2.0)
    assert out["metrics_comparable"].empty  # cas incomplet pour une méthode : exclu


def test_counter_without_measured_hour():
    cases, fc, obs = make({("A", "m"): [12.0] * 24, ("B", "m"): [12.0] * 24}, measured={"B": 0})
    out = evaluate_all(cases, fc, obs)
    assert list(out["metrics_by_counter"]["counter_id"]) == ["A"]  # B : pas de score, jamais 0
    assert out["global_metrics"]["MAE"].iloc[0] == pytest.approx(2.0)
    assert out["global_metrics"]["n_counters_MAE"].iloc[0] == 1
    assert out["metrics_by_case"].set_index("counter_id").loc["B", "n_evaluable_hours"] == 0


def test_negative_or_missing_prediction_not_scored():
    vals = [12.0] * 22 + [np.nan, -1.0]
    cases, fc, obs = make({("A", "m"): vals})
    by = evaluate_all(cases, fc, obs)["metrics_by_counter"]
    assert by["n_predictions"].iloc[0] == 22

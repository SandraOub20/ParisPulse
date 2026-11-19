"""Chaîne E2 cases.csv + counts.csv -> predict_24h -> .pred.csv / .runs.csv (synthétique)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.known import baseline
from src.models.known.predict import (
    build_inputs,
    counts_history_loader,
    predict_24h,
    run_experiment,
)
from src.models.schemas import Case, ForecastInputs, assert_causal

UTC = "UTC"
ORIGIN = "2026-07-01T22:00:00+00:00"  # minuit local du 2 juillet 2026 (CEST)


def case_row(**overrides) -> dict:
    row = {
        "case_id": "K1",
        "counter_id": "C-1",
        "site_group_id": "G-1",
        "origin": ORIGIN,
        "scenario": "known_site",
        "temporal_split": "validation",
        "spatial_role": "S_train",
        "local_budget_hours": "",
        "support_start": "",
        "support_end": "",
        "protocol_id": "P-test",
        "snapshot_id": "S-test",
    }
    row.update(overrides)
    return row


def write_counts(tmp_path) -> pd.DataFrame:
    """Trois semaines horaires ; une heure t-168 h estimée par E1 (J-7), une manquante."""
    ts = pd.date_range("2026-06-10T00:00", "2026-07-03T23:00", freq="h", tz=UTC)
    counts = pd.DataFrame(
        {
            "counter_id": "C-1",
            "timestamp": ts.map(pd.Timestamp.isoformat),
            "interval_end": (ts + pd.Timedelta(hours=1)).map(pd.Timestamp.isoformat),
            "count_raw": np.arange(len(ts), dtype=float),
            "is_observed": True,
            "is_scoreable": True,
            "quality_flags": "[]",
            "source_file_id": "synthetic",
            "snapshot_id": "S-test",
        }
    )
    counts["count"] = counts["count_raw"]
    # Source de h1 (2026-06-24T22Z) : absente, estimée par E1 à J-7.
    estimated = counts["timestamp"] == "2026-06-24T22:00:00+00:00"
    counts.loc[estimated, ["count_raw", "is_observed", "is_scoreable"]] = [np.nan, False, False]
    counts.loc[estimated, "count"] = 999.0
    path = tmp_path / "counts.csv"
    counts.to_csv(path, index=False)
    return path


def test_case_from_row_parses_utc_and_empty_cells():
    case = Case.from_row(pd.Series(case_row(local_budget_hours="168")))
    assert case.origin == pd.Timestamp(ORIGIN)
    assert str(case.origin.tz) == "UTC"
    assert case.local_budget_hours == 168
    assert case.support_start is None

    with pytest.raises(ValueError, match="fuseau"):
        Case.from_row(case_row(origin="2026-07-01T22:00:00"))
    with pytest.raises(ValueError, match="scénario"):
        Case.from_row(case_row(scenario="other"))


def test_loader_measured_vs_e1_filled(tmp_path):
    path = write_counts(tmp_path)
    measured = counts_history_loader("S-test", path=path)("C-1")
    filled = counts_history_loader("S-test", values="e1_filled", path=path)("C-1")
    at = pd.Timestamp("2026-06-24T22:00", tz=UTC)

    assert np.isnan(measured.loc[measured["timestamp"] == at, "count"].item())
    assert filled.loc[filled["timestamp"] == at, "count"].item() == 999.0
    assert measured.loc[measured["timestamp"] == at, "count_e1"].item() == 999.0


def test_predict_24h_uses_measured_value_and_falls_back(tmp_path):
    loader = counts_history_loader("S-test", path=write_counts(tmp_path))
    case = Case.from_row(case_row())
    result = predict_24h(case, loader("C-1"))
    preds = result.predictions.set_index("horizon")

    # h1 : la source t-168 h est une estimation E1 -> ignorée, repli explicite.
    assert preds.loc[1, "prediction_status"] == "fallback"
    assert preds.loc[1, "y_pred"] != 999.0
    # h2 : source 2026-06-24T23Z, mesurée ; valeur = rang horaire depuis le 10/06 00Z.
    expected = pd.Timestamp("2026-06-24T23:00", tz=UTC) - pd.Timestamp("2026-06-10", tz=UTC)
    assert preds.loc[2, "y_pred"] == expected / pd.Timedelta(hours=1)
    assert result.cost.preparation_seconds > 0

    filled = counts_history_loader("S-test", values="e1_filled", path=tmp_path / "counts.csv")
    assert predict_24h(case, filled("C-1")).predictions["y_pred"].iloc[0] == 999.0


def test_build_inputs_drops_future_and_unpublished_rows(tmp_path):
    loader = counts_history_loader("S-test", path=write_counts(tmp_path))
    case = Case.from_row(case_row())
    inputs = build_inputs(case, loader("C-1"), publication_lag_hours=24)

    assert inputs.information_cutoff == pd.Timestamp("2026-06-30T22:00", tz=UTC)
    assert inputs.history["interval_end"].max() == inputs.information_cutoff
    assert len(loader("C-1")) > len(inputs.history)


def test_context_filter_keeps_calendar_and_drops_late_rows():
    case = Case.from_row(case_row())
    context = pd.DataFrame(
        {
            "variable": ["is_holiday", "temp_forecast", "temp_observed"],
            "available_at": [np.nan, "2026-06-30T00:00:00+00:00", "2026-07-02T10:00:00+00:00"],
            "context_version": "ctx-test",
        }
    )
    history = pd.DataFrame({"timestamp": pd.DatetimeIndex([], tz=UTC), "count": []})
    inputs = build_inputs(case, history, context, publication_lag_hours=24)
    assert inputs.context["variable"].tolist() == ["is_holiday", "temp_forecast"]
    assert inputs.context_version == "ctx-test"


def test_assert_causal_rejects_leaks():
    case = Case.from_row(case_row())
    cutoff = case.origin - pd.Timedelta(hours=24)
    late = pd.DataFrame({"timestamp": [case.origin], "count": [1.0]})
    with pytest.raises(ValueError, match="coupure"):
        assert_causal(ForecastInputs(case=case, history=late, information_cutoff=cutoff))
    with pytest.raises(ValueError, match="postérieure"):
        assert_causal(
            ForecastInputs(
                case=case, history=late.iloc[:0], information_cutoff=case.origin + pd.Timedelta(1)
            )
        )


def test_new_site_and_unknown_variant_are_refused(tmp_path):
    loader = counts_history_loader("S-test", path=write_counts(tmp_path))
    with pytest.raises(ValueError, match="E3"):
        predict_24h(Case.from_row(case_row(scenario="new_site")), loader("C-1"))
    with pytest.raises(ValueError, match="indisponible"):
        predict_24h(Case.from_row(case_row()), loader("C-1"), variant="gbm")


def test_run_experiment_writes_files_and_keeps_failed_cases(tmp_path):
    loader = counts_history_loader("S-test", path=write_counts(tmp_path))
    cases = pd.DataFrame([case_row(), case_row(case_id="K2", counter_id="UNKNOWN")])
    pred_path, runs_path = run_experiment(
        cases, loader, "reference", "EXP-test", "e2-ref", root=tmp_path / "out"
    )
    pred = pd.read_csv(pred_path, dtype=str, keep_default_na=False)
    runs = pd.read_csv(runs_path, dtype=str, keep_default_na=False)

    assert pred_path.name == "e2-ref.pred.csv" and len(pred) == 48
    assert runs.set_index("case_id")["status"].to_dict() == {"K1": "fallback", "K2": "error"}
    assert "absent" in runs.set_index("case_id").loc["K2", "status_reason"]
    assert (pred.loc[pred["case_id"] == "K2", "y_pred"] == "").all()
    assert set(pred["method_used"]) - {""} <= {
        baseline.METHOD_NAME,
        baseline.FALLBACK_DOW_HOUR,
        baseline.FALLBACK_HOUR,
    }

"""Vérifier la révélation et le parcours E3 avec uniquement les archives livrées."""

import io
import json
from zipfile import ZipFile

import pandas as pd
import pytest

from src.app import service
from src.app.dashboard.forecast_case import model_forecast_plot
from src.app.export import study_zip
from src.models.schemas import FORECAST_COLUMNS, HORIZON_HOURS, target_timestamps


def test_reference_and_export_keep_targets_hidden_until_reveal():
    counter = pd.Series({"counter_id": "001", "site_group_id": "01", "site_role": "S_train"})
    case = service.technical_case(counter, pd.Timestamp("2026-10-25").date(), "test")
    hours = pd.date_range(
        case.origin - pd.Timedelta(days=7),
        case.origin + pd.Timedelta(hours=HORIZON_HOURS),
        freq="h",
        inclusive="left",
    )
    history = pd.DataFrame(
        {
            "counter_id": case.counter_id,
            "timestamp": hours,
            "interval_end": hours + pd.Timedelta(hours=1),
            "count_raw": 10.0,
            "count": 10.0,
            "is_observed": True,
            "is_scoreable": True,
        }
    )
    target = history["timestamp"].ge(case.origin)
    history.loc[target, "count_raw"] = 25
    history.loc[history["timestamp"].eq(case.origin), "is_scoreable"] = False

    study = service.calculate_reference(case, history, "reference", publication_lag_hours=24)
    assert study.forecast["y_pred"].tolist() == [10] * HORIZON_HOURS
    assert study.forecast["target_timestamp"].tolist() == list(hours[-HORIZON_HOURS:])
    predicted = model_forecast_plot((study,))
    assert len(predicted.data) == 1
    assert predicted.data[0].name == service.REFERENCE_LABELS["reference"]
    assert pd.to_datetime(predicted.data[0].x, utc=True).equals(hours[-HORIZON_HOURS:])
    assert predicted.layout.xaxis.range == (case.origin, case.origin + pd.Timedelta(hours=24))
    with ZipFile(io.BytesIO(study_zip(study))) as archive:
        assert set(archive.namelist()) == {"forecasts.csv", "case_runs.csv", "manifest.json"}
        assert not json.loads(archive.read("manifest.json"))["targets_revealed"]

    evaluation = service.reveal(study, history)
    assert evaluation["mae"] == 15
    assert evaluation["n_compared_hours"] == 23
    compared = model_forecast_plot((study,), evaluation["observations"])
    assert compared.data[1].name == "Mesures réelles"
    with ZipFile(io.BytesIO(study_zip(study, evaluation))) as archive:
        observations = pd.read_csv(archive.open("observations.csv"))
        assert observations["y_true"].isna().sum() == 1
        assert "errors.csv" in archive.namelist()
        assert json.loads(archive.read("manifest.json"))["targets_revealed"]


def test_chronos_archive_has_selectable_budgets_without_e4_file(tmp_path):
    origin = pd.Timestamp("2026-06-30T22:00Z")
    counter = pd.Series({"counter_id": "001", "site_group_id": "01", "site_role": "S_dev_new"})
    path = tmp_path / "chronos.pred.csv"
    frames = []
    for budget in (24, 72):
        frames.append(
            target_timestamps(origin)
            .assign(
                case_id=f"001_20260630T22_new_site_b{budget}",
                counter_id="001",
                snapshot_id="test",
                protocol_id="proto-v1",
                scenario="new_site",
                origin=origin.isoformat(),
                method_run_id="e3-chronos-2-frozen",
                model_run_id="chronos",
                variant="frozen",
                y_pred=float(budget),
                prediction_status="ok",
            )
            .reindex(columns=FORECAST_COLUMNS)
        )
    pd.concat(frames).to_csv(path, index=False)
    catalog = service.archived_forecasts((path,), "test")
    cases = service.archived_cases(catalog, counter, pd.DataFrame())
    assert [case.local_budget_hours for case in cases] == [24, 72]
    assert cases[1].support_end == origin - pd.Timedelta(hours=24)
    assert cases[1].support_end - cases[1].support_start == pd.Timedelta(hours=72)
    study = service.open_archive(cases[1], catalog, path, "e3-chronos-2-frozen")
    assert study.forecast["y_pred"].tolist() == [72] * HORIZON_HOURS


def test_local_calculation_and_comparison_respect_bounded_support():
    counter = pd.Series({"counter_id": "001", "site_group_id": "01", "site_role": "S_dev_new"})
    case = service.technical_new_case(counter, pd.Timestamp("2026-07-01").date(), "test", 24, 24)
    hours = pd.date_range(case.origin - pd.Timedelta(days=8), periods=216, freq="h")
    allowed = (hours >= case.support_start) & (hours < case.support_end)
    history = pd.DataFrame(
        {
            "counter_id": case.counter_id,
            "timestamp": hours,
            "interval_end": hours + pd.Timedelta(hours=1),
            "count_raw": [9.0 if in_support else 1000.0 for in_support in allowed],
            "count": 1000.0,
            "is_observed": True,
            "is_scoreable": True,
        }
    )
    study = service.calculate_local_reference(case, history, 24)
    assert study.forecast["y_pred"].tolist() == [9.0] * HORIZON_HOURS
    assert study.forecast["prediction_status"].eq("fallback").all()
    service.verify_same_support(study, study)
    changed = history.assign(count_raw=history["count_raw"] + 1)
    alternative = service.calculate_local_reference(case, changed, 24)
    with pytest.raises(ValueError, match="même historique local"):
        service.verify_same_support(study, alternative)

    with ZipFile(io.BytesIO(study_zip(study, alternatives=((study, None),)))) as archive:
        assert "observations.csv" not in archive.namelist()
        assert len(pd.read_csv(archive.open("forecasts.csv"))) == 48

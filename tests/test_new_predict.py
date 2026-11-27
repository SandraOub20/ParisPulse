"""Tests de la chaîne E3 Chronos-2 sans téléchargement de modèle."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.models.new import predict as new_predict
from src.models.schemas import FORECAST_COLUMNS, Case

ORIGIN = pd.Timestamp("2026-07-01T22:00:00Z")
LAG_HOURS = 24
BUDGET_HOURS = 168


class FakeChronos2:
    def __init__(self, *, negative_target=False):
        self.context = None
        self.prediction_length = None
        self.negative_target = negative_target

    def predict_df(
        self,
        context,
        *,
        prediction_length,
        quantile_levels,
        id_column,
        timestamp_column,
        target,
    ):
        self.context = context.copy()
        self.prediction_length = prediction_length
        assert quantile_levels == [0.5]
        assert (id_column, timestamp_column, target) == ("item_id", "timestamp", "target")
        assert self.context[timestamp_column].dt.tz is None
        forecast_start = context[timestamp_column].max() + pd.Timedelta(hours=1)
        values = np.arange(prediction_length, dtype=float)
        if self.negative_target:
            values[24] = -1.0
        return pd.DataFrame(
            {
                timestamp_column: pd.date_range(
                    forecast_start, periods=prediction_length, freq="h"
                ),
                "0.5": values,
            }
        )


class FakeGoogleTimesFM:
    def __init__(self, *, negative_target=False):
        self.horizon = None
        self.inputs = None
        self.negative_target = negative_target

    def forecast(self, *, horizon, inputs):
        self.horizon = horizon
        self.inputs = inputs
        point = np.arange(horizon, dtype=float)
        quantiles = np.repeat(point[:, None], 10, axis=1)
        if self.negative_target:
            quantiles[24, 5] = -1.0
        return point[None, :], quantiles[None, :, :]

    def compile(self, config):
        return None


def new_site_case(**overrides):
    support_end = ORIGIN - pd.Timedelta(hours=LAG_HOURS)
    row = {
        "case_id": "N1",
        "counter_id": "C-1",
        "site_group_id": "G-1",
        "origin": ORIGIN.isoformat(),
        "scenario": "new_site",
        "spatial_role": "S_dev_new",
        "protocol_id": "P-test",
        "snapshot_id": "S-test",
        "local_budget_hours": BUDGET_HOURS,
        "support_start": (support_end - pd.Timedelta(hours=BUDGET_HOURS)).isoformat(),
        "support_end": support_end.isoformat(),
    }
    row.update(overrides)
    return Case.from_row(row)


def history_for_case(case):
    start = case.support_start
    end = case.support_end
    timestamps = pd.date_range(
        start - pd.Timedelta(hours=2),
        end + pd.Timedelta(hours=2),
        freq="h",
    )
    history = pd.DataFrame(
        {
            "counter_id": "C-1",
            "timestamp": timestamps,
            "interval_end": timestamps + pd.Timedelta(hours=1),
            "count": 1000.0,
            "count_raw": 1.0,
            "is_observed": True,
            "is_scoreable": True,
        }
    )
    hidden = history["timestamp"] == start + pd.Timedelta(hours=2)
    history.loc[hidden, "is_observed"] = False
    history.loc[hidden, "count_raw"] = 999.0
    return history


def test_predict_24h_filters_support_and_offsets_for_publication_lag(monkeypatch):
    case = new_site_case()
    model = FakeChronos2()
    monkeypatch.setattr(new_predict.manager, "load_model", lambda name: model)

    result = new_predict.predict_24h(case, history_for_case(case), publication_lag_hours=LAG_HOURS)

    assert model.prediction_length == LAG_HOURS + 24
    assert len(model.context) == BUDGET_HOURS
    assert model.context["timestamp"].min() == case.support_start.tz_localize(None)
    assert model.context["timestamp"].max() == (
        case.support_end - pd.Timedelta(hours=1)
    ).tz_localize(None)
    assert pd.isna(model.context.loc[2, "target"])
    assert model.context["target"].dropna().eq(1.0).all()
    assert result.predictions["target_timestamp"].iloc[0] == ORIGIN
    assert result.predictions["target_timestamp"].iloc[-1] == ORIGIN + pd.Timedelta(hours=23)
    assert result.predictions["y_pred"].tolist() == list(map(float, range(24, 48)))
    assert result.support_id.startswith("sha256:")
    assert result.status == "ok"


def test_save_forecasts_uses_shared_contract_csv(monkeypatch, tmp_path):
    case = new_site_case()
    monkeypatch.setattr(new_predict.manager, "load_model", lambda name: FakeChronos2())
    result = new_predict.predict_24h(case, history_for_case(case), publication_lag_hours=LAG_HOURS)

    path, runs_path = new_predict.save_forecasts(result, tmp_path / "chronos.pred.csv")
    saved = pd.read_csv(path, dtype=str, keep_default_na=False)
    runs = pd.read_csv(runs_path, dtype=str, keep_default_na=False)

    assert list(saved.columns) == FORECAST_COLUMNS
    assert len(saved) == 24
    assert set(saved["scenario"]) == {"new_site"}
    assert set(saved["variant"]) == {"frozen"}
    assert runs_path.name == "chronos.runs.csv"
    assert len(runs) == 1
    assert runs.loc[0, "status"] == "ok"


def test_negative_quantile_is_clipped_and_marked(monkeypatch):
    case = new_site_case()
    monkeypatch.setattr(
        new_predict.manager,
        "load_model",
        lambda name: FakeChronos2(negative_target=True),
    )

    result = new_predict.predict_24h(case, history_for_case(case), publication_lag_hours=LAG_HOURS)

    assert result.predictions.loc[0, "y_pred"] == 0.0
    assert result.predictions.loc[0, "status_reason"] == "negative_quantile_clipped_to_zero"


def test_google_timesfm_frozen_matches_prediction_contract(monkeypatch):
    case = new_site_case()
    model = FakeGoogleTimesFM()
    monkeypatch.setattr(new_predict.manager, "load_model", lambda name: model)

    result = new_predict.predict_24h(
        case,
        history_for_case(case),
        variant="frozen",
        model_name="google_TimesFM_2.5",
        publication_lag_hours=LAG_HOURS,
    )

    assert model.horizon == LAG_HOURS + 24
    assert len(model.inputs) == 1
    assert len(model.inputs[0]) == BUDGET_HOURS
    assert result.method_run_id == "e3-google-TimesFM_2.5-frozen-v1"
    assert result.model_run_id == "google-TimesFM_2.5"
    assert result.variant == "frozen"
    assert result.predictions["y_pred"].tolist() == list(map(float, range(24, 48)))


def test_google_timesfm_negative_median_is_clipped(monkeypatch):
    case = new_site_case()
    monkeypatch.setattr(
        new_predict.manager,
        "load_model",
        lambda name: FakeGoogleTimesFM(negative_target=True),
    )

    result = new_predict.predict_24h(
        case,
        history_for_case(case),
        variant="frozen",
        model_name="google_TimesFM_2.5",
        publication_lag_hours=LAG_HOURS,
    )

    assert result.predictions.loc[0, "y_pred"] == 0.0
    assert result.predictions.loc[0, "status_reason"] == "negative_quantile_clipped_to_zero"


def test_google_timesfm_adapted_uses_blend_v2(monkeypatch):
    case = new_site_case()
    model = FakeGoogleTimesFM()
    monkeypatch.setattr(new_predict.manager, "load_model", lambda name: model)

    result = new_predict.predict_24h(
        case,
        history_for_case(case),
        variant="adapted",
        model_name="google_TimesFM_2.5",
        publication_lag_hours=LAG_HOURS,
    )

    assert model.horizon == LAG_HOURS + 24
    assert result.method_run_id == "e3-google-TimesFM_2.5-adapted-v2"
    assert result.model_run_id == "google-TimesFM_2.5"
    assert result.predictions["method_used"].eq("google-TimesFM-2.5-adapted-v2").all()
    assert result.predictions["y_pred"].iloc[0] == pytest.approx(0.9 * 24 + 0.1)


def test_adapted_prediction_uses_blend_v2_and_refuses_known_site(monkeypatch):
    case = new_site_case()
    loaded_models = []
    monkeypatch.setattr(
        new_predict.manager, "load_model", lambda name: loaded_models.append(name) or FakeChronos2()
    )

    result = new_predict.predict_24h(
        case,
        history_for_case(case),
        variant="adapted",
        publication_lag_hours=LAG_HOURS,
    )
    assert result.method_run_id == "e3-chronos-2-adapted-v2"
    assert result.predictions["method_used"].eq("chronos-2-adapted-v2").all()
    assert result.predictions["y_pred"].iloc[0] == pytest.approx(0.85 * 24 + 0.15)
    assert loaded_models == ["chronos-2"]

    monkeypatch.setattr(
        new_predict.manager,
        "load_model",
        lambda name: pytest.fail("un modèle ne doit pas être chargé pour un cas known_site"),
    )
    known = new_site_case(scenario="known_site")
    with pytest.raises(ValueError, match="scénario"):
        new_predict.predict_24h(known, history_for_case(case))


@pytest.mark.parametrize(
    ("model_name", "variant"),
    [
        ("team2", "adapted"),
    ],
)
def test_unimplemented_model_variants_load_then_raise(monkeypatch, model_name, variant):
    loaded_models = []
    monkeypatch.setattr(
        new_predict.manager,
        "load_model",
        lambda name: loaded_models.append(name),
    )

    case = new_site_case()
    with pytest.raises(NotImplementedError, match=model_name):
        case = new_site_case()
        new_predict.predict_24h(
            case,
            history_for_case(case),
            variant=variant,
            model_name=model_name,
            publication_lag_hours=LAG_HOURS,
        )

    assert loaded_models == [model_name]


def test_team2_frozen_uses_mlp_with_only_available_context(monkeypatch):
    case = new_site_case()
    model = SimpleNamespace(
        model_run_id="e2-mlp-ctx-20260701-s0-9ce9",
        estimator=object(),
        config=SimpleNamespace(fit_cutoff=pd.Timestamp("2026-06-30T22:00:00Z")),
    )
    context = pd.DataFrame(
        {
            "available_at": [
                ORIGIN - pd.Timedelta(hours=1),
                ORIGIN + pd.Timedelta(hours=1),
            ],
            "context_version": ["e1-context/0.3.0", "future-version"],
        }
    )
    received = {}

    def fake_predict_mlp(estimator, inputs, *, fit_cutoff):
        received["estimator"] = estimator
        received["inputs"] = inputs
        received["fit_cutoff"] = fit_cutoff
        return SimpleNamespace(values=np.full(24, 7.0), reason=None)

    monkeypatch.setattr(new_predict.manager, "load_model", lambda name: model)
    monkeypatch.setattr(new_predict.neural, "predict_mlp", fake_predict_mlp)

    result = new_predict.predict_24h(
        case,
        history_for_case(case),
        model_name="team2",
        context=context,
        publication_lag_hours=LAG_HOURS,
    )

    assert received["estimator"] is model.estimator
    assert received["fit_cutoff"] == model.config.fit_cutoff
    assert len(received["inputs"].context) == 1
    assert received["inputs"].context["context_version"].tolist() == ["e1-context/0.3.0"]
    assert result.model_run_id == model.model_run_id
    assert result.fit_cutoff == model.config.fit_cutoff
    assert result.feature_version == new_predict.neural.INPUT_VERSION
    assert result.status == "ok"
    assert result.predictions["method_used"].eq("mlp").all()
    assert result.predictions["y_pred"].tolist() == [7.0] * 24


def test_team2_frozen_falls_back_to_weekly_reference_on_mlp_refusal(monkeypatch):
    case = new_site_case()
    model = SimpleNamespace(
        model_run_id="e2-mlp-ctx-20260701-s0-9ce9",
        estimator=object(),
        config=SimpleNamespace(fit_cutoff=pd.Timestamp("2026-06-30T22:00:00Z")),
    )
    monkeypatch.setattr(new_predict.manager, "load_model", lambda name: model)
    monkeypatch.setattr(
        new_predict.neural,
        "predict_mlp",
        lambda estimator, inputs, *, fit_cutoff: SimpleNamespace(
            values=None, reason="mlp_context_missing"
        ),
    )

    result = new_predict.predict_24h(
        case,
        history_for_case(case),
        model_name="team2",
        publication_lag_hours=LAG_HOURS,
    )

    assert result.status == "fallback"
    assert result.status_reason == "mlp_context_missing"
    assert result.predictions["prediction_status"].eq("fallback").all()
    assert result.predictions["status_reason"].eq("mlp_context_missing").all()
    assert result.predictions["y_pred"].eq(1.0).all()


def test_prediction_refuses_non_reserved_geographic_role(monkeypatch):
    case = new_site_case(spatial_role="S_train")
    monkeypatch.setattr(
        new_predict.manager,
        "load_model",
        lambda name: pytest.fail("un modèle ne doit pas être chargé"),
    )

    with pytest.raises(ValueError, match="spatial_role"):
        new_predict.predict_24h(case, history_for_case(case))


def test_prediction_refuses_missing_budgeted_support():
    case = new_site_case()
    history = history_for_case(case)
    history["is_observed"] = False

    with pytest.raises(ValueError, match="aucune mesure publiée"):
        new_predict.predict_24h(case, history, publication_lag_hours=LAG_HOURS)

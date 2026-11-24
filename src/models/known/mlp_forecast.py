"""Utiliser le MLP livré par E2 dans les deux scénarios avec ses règles de refus."""

from __future__ import annotations

import platform
from functools import lru_cache
from time import perf_counter

import numpy as np

from src.models.known import baseline, train
from src.models.schemas import HORIZON_HOURS, ForecastInputs, ForecastResult, target_timestamps

MLP_MODEL_RUN_ID = "e2-mlp-ctx-20260701-s0-9ce9"


@lru_cache(maxsize=4)
def load_mlp_artifact(model_run_id: str = MLP_MODEL_RUN_ID) -> train.TrainedModel:
    """Charger une version immuable, en vérifiant la fiche et l'empreinte des poids."""
    try:
        from src.models.known import neural
    except ImportError as error:
        raise RuntimeError("Le MLP nécessite PyTorch. Installez le groupe dl.") from error

    model = train.load_model(model_run_id, expected_feature_version=neural.INPUT_VERSION)
    if model.config.method != "mlp":
        raise ValueError(f"Le modèle {model_run_id} doit être un MLP.")
    return model


def infer_mlp(model: train.TrainedModel, inputs: ForecastInputs):
    from src.models.known.neural import predict_mlp

    return predict_mlp(model.estimator, inputs, fit_cutoff=model.config.fit_cutoff)


def predict_trained_mlp(
    inputs: ForecastInputs, model: train.TrainedModel, variant: str, method_run_id: str
) -> ForecastResult:
    """Retourner la sortie du MLP ou appliquer son repli hebdomadaire explicite."""
    started = perf_counter()
    case = inputs.case
    config = model.config
    reason = None
    if config.snapshot_id and config.snapshot_id != case.snapshot_id:
        reason = "mlp_snapshot_incompatible"
    elif case.origin < config.fit_cutoff:
        reason = "mlp_origin_before_fit_cutoff"
    elif case.scenario == "known_site" and case.site_group_id not in model.donor_site_groups:
        reason = "mlp_site_not_in_training"
    elif case.scenario == "new_site" and (
        case.site_group_id in model.donor_site_groups
        or case.site_group_id not in model.excluded_site_groups
    ):
        reason = "mlp_site_not_confirmed_reserved"
    elif config.use_context and config.context_version != inputs.context_version:
        reason = (
            "mlp_context_missing" if inputs.context_version is None else "mlp_context_incompatible"
        )

    values = None
    if reason is None:
        try:
            prediction = infer_mlp(model, inputs)
            values, reason = prediction.values, prediction.reason
        except ValueError as error:
            reason = f"mlp_inputs_incompatible: {error}"

    if values is not None:
        values = np.asarray(values, dtype=float)
        if values.shape != (HORIZON_HOURS,) or not (np.isfinite(values) & (values >= 0)).all():
            raise ValueError("Le MLP doit retourner 24 valeurs finies et positives ou nulles.")
        result = ForecastResult(
            case=case,
            method_run_id=method_run_id,
            model_run_id=model.model_run_id,
            variant=variant,
            predictions=target_timestamps(case.origin).assign(
                y_pred=values, method_used="mlp", prediction_status="ok", status_reason=None
            ),
            status="ok",
            fit_cutoff=config.fit_cutoff,
            support_id=inputs.support_id,
            context_version=inputs.context_version,
            feature_version=config.feature_version,
        )
    else:
        if not reason:
            raise ValueError("Le MLP a refusé la prévision sans fournir de raison.")
        result = baseline.weekly_reference(inputs, variant, method_run_id=method_run_id)
        available = result.predictions["y_pred"].notna()
        result.predictions["prediction_status"] = np.where(available, "fallback", "unavailable")
        result.predictions["status_reason"] = reason
        result.status = "fallback" if available.all() else "unavailable"
        result.status_reason = reason
        result.model_run_id = model.model_run_id

    result.cost.inference_seconds = perf_counter() - started
    result.cost.hardware = f"{platform.system()}-{platform.machine()}"
    return result

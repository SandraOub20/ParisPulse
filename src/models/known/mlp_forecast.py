"""Utiliser le MLP livré par E2 dans les deux scénarios avec ses règles de refus."""

from __future__ import annotations

from functools import lru_cache

from src.models.known import train
from src.models.schemas import ForecastInputs, ForecastResult

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
    """Retourner la sortie du MLP ou appliquer son repli hebdomadaire explicite.

    Délègue à predict.trained_forecast, seule implémentation commune au MLP et au HGB
    (mêmes contrôles d'éligibilité, mêmes codes de refus, même repli) : signature
    inchangée pour l'application (E5) et les nouveaux sites (E3).
    """
    from src.models.known.predict import MLP_VARIANT, trained_forecast

    return trained_forecast(
        inputs, MLP_VARIANT, model, variant=variant, method_run_id=method_run_id
    )

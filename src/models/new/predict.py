
from ._core import manager


def predict(model_name,history,horizon=24):
    model = manager.load_model(model_name)

    if model_name == "chronos-2":
        # TODO : préparation Chronos-2 (avec manager)
        # TODO : prédiction Chronos-2
        pass
    elif model_name == "google_TimesFM_2.5":
        # TODO : préparation Google TimesFM 2.5 (avec manager)
        # TODO : prédiction Google TimesFM 2.5
        pass
    elif model_name == "team2":
        # TODO : préparation modèle E2 (avec manager)
        # TODO : prédiction modèle E2
        pass

    else:
        raise ValueError("Modèle inconnu")


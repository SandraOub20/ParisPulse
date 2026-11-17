
from ._core import manager


def adapt(model_name,history,horizon=24):
    model = manager.load_model(model_name)

    if model_name == "chronos-2":
        # TODO : adaptation Chronos-2
        pass
    elif model_name == "google_TimesFM_2.5":
        # TODO : adaptation Google TimesFM 2.5
        pass
    elif model_name == "team2":
        # TODO : adaptation modèle E2
        pass

    else:
        raise ValueError("Modèle inconnu")

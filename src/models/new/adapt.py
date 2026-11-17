"""Adaptation du modèle E3 à l'historique autorisé d'un nouveau site."""


def adapt(model_name, history):
    """Retourne une copie du modèle adaptée au site à partir de `history`.

    L'adaptation doit rester limitée à l'historique local autorisé pour le cas.
    """
    if model_name == "chronos-2":
        # TODO : charger, copier et adapter Chronos-2 sur history.
        adapted_model = None
    elif model_name == "google_TimesFM_2.5":
        # TODO : charger, copier et adapter TimesFM 2.5 sur history.
        adapted_model = None
    elif model_name == "team2":
        # TODO : charger, copier et adapter le modèle E2 sur history.
        adapted_model = None
    else:
        raise ValueError(f"Modèle inconnu : {model_name}")

    # TODO : retourner le modèle adapté sans modifier le modèle global partagé.
    return adapted_model

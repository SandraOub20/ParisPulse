"""Adaptation du modèle E3 à l'historique autorisé d'un nouveau site."""


def adapt(model_name, history):
    """Retourne une copie du modèle adaptée au site à partir de `history`.

    L'adaptation doit rester limitée à l'historique local autorisé pour le cas.
    """
    model = manager.load_model(model_name)
    adapted_model = model
    if model_name == "chronos-2":
        # TODO : adapter Chronos-2 sur history (travailler sur adapted_model).
        adapted_model = None
    elif model_name == "google_TimesFM_2.5":
        # TODO : adapter TimesFM 2.5 sur history (travailler sur adapted_model).
        adapted_model = None
    elif model_name == "team2":
        # TODO : adapter le modèle E2 sur history (travailler sur adapted_model).
        adapted_model = None
    else:
        raise ValueError(f"Modèle inconnu : {model_name}")

    # TODO : retourner le modèle adapté sans modifier le modèle global (model) partagé.
    return adapted_model

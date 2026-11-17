"""Point d'entrée E3 pour les prévisions sur de nouveaux sites."""

import pandas as pd

from ._core import manager
from .adapt import adapt


def predict_24h(case, history, variant="frozen", model_name="chronos-2"):
    """Prépare une prévision de 24 heures pour le compteur et l'origine du cas.

    Retour attendu : un DataFrame de 24 lignes conforme au contrat des
    prévisions. `history` est le même support local pour les deux variantes.
    """
    if variant not in {"frozen", "adapted"}:
        raise ValueError("variant doit être 'frozen' ou 'adapted'.")

    if variant == "frozen":
        # frozen retourne le modèle public/team2 sans adaptation ;
        model = manager.load_model(model_name)
    elif variant == "adapted":
        # adapt retourne le modèle adapté ; history reste le support autorisé.
        model = adapt(model_name, history)

    else:
        raise ValueError("variant doit être 'frozen' ou 'adapted'.")

    # La sélection de variante est terminée : une seule branche de prédiction
    # par modèle sert aux variantes gelée et adaptée.
    if model_name == "chronos-2":
        # TODO : prédire 24 heures avec model et history.
        pass
    elif model_name == "google_TimesFM_2.5":
        # TODO : prédire 24 heures avec model et history.
        pass
    elif model_name == "team2":
        # TODO : prédire 24 heures avec model et history.
        pass
    else:
        raise ValueError(f"Modèle inconnu : {model_name}")

    # TODO : construire et retourner 24 lignes au format doc/templates/forecasts.csv,
    # avec les identifiants du cas et de la méthode, les timestamps UTC,
    # y_pred, variant, method_used, prediction_status et les champs de traçabilité.


def save_forecasts(forecasts, path="forecasts.csv"):
    """Enregistre le résultat d'un seul compteur dans `forecasts.csv`."""
    # TODO : vérifier les 24 horizons distincts et les colonnes du contrat.
    # TODO : écrire le CSV UTF-8 avec les colonnes du gabarit commun.
    pass


if __name__ == "__main__":
    case_example = {
        "counter_id": "12345",
        "origin": "2026-10-01T00:00:00Z",
    }
    history_example = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                end="2026-09-30T00:00:00Z",
                periods=24,
                freq="h",
            ),
            "count": list(range(24)),
        }
    )

    forecasts = predict_24h(
        case_example,
        history_example,
        variant="frozen",
    )
    save_forecasts(forecasts, path="forecasts.csv")

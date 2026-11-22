
import math
from numbers import Real
from datetime import datetime, timedelta, timezone

def verifier_24_predictions(predictions):
    """
    Vérifie qu'un modèle retourne exactement
    24 prévisions horaires.
    """

    if len(predictions) != 24:
        raise ValueError(
            f"24 prévisions attendues, "
            f"{len(predictions)} reçues."
        )

    return True



def verifier_valeurs(predictions):
    """
    Vérifie que les prévisions sont des nombres
    valides, finis et non négatifs.
    """

    for i, valeur in enumerate(predictions, start=1):
        if (
            isinstance(valeur, bool)
            or not isinstance(valeur, Real)
            or not math.isfinite(valeur)
            or valeur < 0
        ):
            raise ValueError(
                f"Valeur invalide à l'horizon {i}: {valeur}"
            )

    return True

def verifier_horizons(origin, heures):
    """
    Vérifie les 24 heures consécutives
    à partir d'une origine UTC.
    """

    debut = datetime.fromisoformat(
        origin.replace("Z", "+00:00")
    )

    if debut.tzinfo is None:
        raise ValueError("L'origine doit avoir un fuseau horaire.")

    debut = debut.astimezone(timezone.utc)

    if len(heures) != 24:
        raise ValueError("Il faut exactement 24 horodatages.")

    for i, heure in enumerate(heures):
        date = datetime.fromisoformat(
            heure.replace("Z", "+00:00")
        )

        if date.tzinfo is None:
            raise ValueError("Horodatage sans fuseau horaire.")

        date_utc = date.astimezone(timezone.utc)
        attendu = debut + timedelta(hours=i)

        if date_utc != attendu:
            raise ValueError(
                f"Horizon {i + 1} : heure incorrecte."
            )

    return True

if __name__ == "__main__":
    origine = "2025-10-15T00:00:00Z"

    heures = [
        (
            datetime.fromisoformat(
                origine.replace("Z", "+00:00")
            ) + timedelta(hours=i)
        ).isoformat()
        for i in range(24)
    ]

    print("Horizons valides :", verifier_horizons(origine, heures))

def verifier_predictions_avec_statut(predictions, statut):
    """
    Vérifie les valeurs des prédictions selon leur statut.

    None représente une prévision manquante.
    """

    # On doit toujours avoir 24 horizons.
    verifier_24_predictions(predictions)

    if statut not in ("ok", "fallback", "unavailable"):
        raise ValueError(f"Statut inconnu : {statut}")

    valeurs_manquantes = sum(
        valeur is None for valeur in predictions
    )

    if statut in ("ok", "fallback") and valeurs_manquantes > 0:
        raise ValueError(
            "Une prévision complète ne doit pas contenir de valeur manquante."
        )

    if statut == "unavailable" and valeurs_manquantes == 0:
        raise ValueError(
            "Le statut unavailable nécessite au moins une valeur manquante."
        )

    # Vérifier toutes les valeurs présentes.
    valeurs_presentes = [
        valeur for valeur in predictions if valeur is not None
    ]

    verifier_valeurs(valeurs_presentes)

    return True

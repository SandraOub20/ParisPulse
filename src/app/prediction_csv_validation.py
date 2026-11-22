
import csv
from collections import defaultdict

from src.app.prediction_validation import (
    verifier_24_predictions,
    verifier_horizons,
    verifier_predictions_avec_statut,
)


def verifier_fichier_predictions_csv(chemin_fichier):
    groupes = defaultdict(list)

    with open(
        chemin_fichier,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as fichier:
        lecteur = csv.DictReader(fichier)

        for ligne in lecteur:
            cle = (
                ligne["case_id"],
                ligne["method_run_id"]
            )

            groupes[cle].append(ligne)

    for cle, lignes in groupes.items():
        verifier_24_predictions(lignes)

        horizons = sorted(
            int(ligne["horizon"])
            for ligne in lignes
        )

        if horizons != list(range(1, 25)):
            raise ValueError(
                f"Horizons incorrects pour {cle}"
            )
        
        # Remettre les lignes dans l'ordre des horizons
        lignes_tries = sorted(
            lignes,
            key=lambda ligne: int(ligne["horizon"])
        )

        # Récupérer l'origine du cas
        origine = lignes_tries[0]["origin"]

        # Récupérer les 24 horodatages
        heures = [
            ligne["target_timestamp"]
            for ligne in lignes_tries
        ]

        # Réutiliser ta fonction de validation UTC
        verifier_horizons(origine, heures)

        # Convertir les valeurs du CSV en nombres Python
        predictions = []

        for ligne in lignes_tries:
            valeur = ligne["y_pred"]

            if valeur is None or valeur.strip() == "":
                predictions.append(None)
            else:
                try:
                    predictions.append(float(valeur))
                except ValueError as erreur:
                    raise ValueError(
                        f"Valeur y_pred invalide pour {cle}: {valeur}"
                    ) from erreur

        # Vérifier le statut de chaque horizon
        statuts = [
            ligne["prediction_status"]
            for ligne in lignes_tries
        ]

        if any(statut not in ("ok", "fallback", "unavailable")
               for statut in statuts):
            raise ValueError(f"Statut inconnu pour {cle}")

        # Une valeur manquante rend le cas indisponible.
        # Sinon, un fallback sur une heure rend le cas fallback.
        if "unavailable" in statuts:
            statut_cas = "unavailable"
        elif "fallback" in statuts:
            statut_cas = "fallback"
        else:
            statut_cas = "ok"

        verifier_predictions_avec_statut(
            predictions, statut_cas
        )

    

    return len(groupes)

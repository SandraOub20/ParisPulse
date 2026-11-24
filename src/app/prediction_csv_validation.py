
import csv
from collections import defaultdict

from src.app.prediction_validation import (
    verifier_24_predictions,
    verifier_horizons,
    verifier_predictions_avec_statut,
)

COLONNES_ATTENDUES = [
    "case_id",
    "method_run_id",
    "model_run_id",
    "counter_id",
    "origin",
    "scenario",
    "horizon",
    "target_timestamp",
    "y_pred",
    "variant",
    "method_used",
    "prediction_status",
    "status_reason",
    "fit_cutoff",
    "support_id",
    "adaptation_id",
    "snapshot_id",
    "context_version",
    "protocol_id",
    "feature_version",
]


def verifier_colonnes(colonnes):
    """Vérifie que les 20 colonnes du contrat sont présentes."""

    if colonnes is None:
        raise ValueError("Fichier CSV sans en-tête.")

    manquantes = [
        colonne
        for colonne in COLONNES_ATTENDUES
        if colonne not in colonnes
    ]

    if manquantes:
        raise ValueError(
            f"Colonnes manquantes : {manquantes}"
        )

    return True


def verifier_statut_ligne(ligne):
    """Vérifie la cohérence de chaque prédiction."""

    statut = ligne["prediction_status"].strip()
    valeur = ligne["y_pred"].strip()
    raison = ligne["status_reason"].strip()
    methode = ligne["method_used"].strip()

    if statut not in ("ok", "fallback", "unavailable", "error"):
        raise ValueError(f"Statut inconnu : {statut}")

    if statut in ("ok", "fallback") and not valeur:
        raise ValueError(
            "Une prévision ok/fallback doit avoir une valeur."
        )

    if statut in ("unavailable", "error"):
        if valeur:
            raise ValueError(
                f"Une prévision {statut} doit être vide."
            )

        if not raison:
            raise ValueError(
                f"Une prévision {statut} doit avoir une raison."
            )

    if statut == "fallback":
        if not raison:
            raise ValueError(
                "Un fallback doit avoir une raison."
            )

        if not methode:
            raise ValueError(
                "Un fallback doit identifier sa méthode."
            )

    if statut in ("ok", "fallback") and not methode:
        raise ValueError(
            "Une méthode doit être indiquée."
        )

    return True


def verifier_coherence_groupe(lignes):
    """Vérifie les informations communes aux 24 horizons."""

    champs = [
        "case_id",
        "method_run_id",
        "counter_id",
        "origin",
        "scenario",
        "snapshot_id",
        "protocol_id",
    ]

    for champ in champs:
        valeurs = {
            ligne[champ].strip()
            for ligne in lignes
        }

        if len(valeurs) != 1:
            raise ValueError(
                f"Valeurs incohérentes pour {champ}"
            )

        if not lignes[0][champ].strip():
            raise ValueError(
                f"Champ obligatoire vide : {champ}"
            )

    if lignes[0]["scenario"] not in (
        "known_site",
        "new_site",
    ):
        raise ValueError("Scénario inconnu.")

    return True


def verifier_fichier_predictions_csv(chemin_fichier):
    """Valide les prédictions d'un CSV selon le contrat."""

    groupes = defaultdict(list)

    with open(
        chemin_fichier,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as fichier:

        lecteur = csv.DictReader(fichier)

        verifier_colonnes(lecteur.fieldnames)

        for numero, ligne in enumerate(lecteur, start=2):
            if None in ligne or any(
                valeur is None for valeur in ligne.values()
            ):
                raise ValueError(
                    f"Ligne CSV mal formée : {numero}"
                )

            verifier_statut_ligne(ligne)

            cle = (
                ligne["case_id"],
                ligne["method_run_id"],
            )

            groupes[cle].append(ligne)

    for cle, lignes in groupes.items():

        verifier_24_predictions(lignes)
        verifier_coherence_groupe(lignes)

        lignes_tries = sorted(
            lignes,
            key=lambda ligne: int(ligne["horizon"])
        )

        horizons = [
            int(ligne["horizon"])
            for ligne in lignes_tries
        ]

        if horizons != list(range(1, 25)):
            raise ValueError(
                f"Horizons incorrects pour {cle}"
            )

        origine = lignes_tries[0]["origin"]

        heures = [
            ligne["target_timestamp"]
            for ligne in lignes_tries
        ]

        verifier_horizons(origine, heures)

        predictions = []

        for ligne in lignes_tries:
            valeur = ligne["y_pred"].strip()

            if not valeur:
                predictions.append(None)
            else:
                try:
                    predictions.append(float(valeur))
                except ValueError as erreur:
                    raise ValueError(
                        f"Valeur invalide pour {cle}: {valeur}"
                    ) from erreur

        statuts = [
            ligne["prediction_status"].strip()
            for ligne in lignes_tries
        ]

        if "unavailable" in statuts or "error" in statuts:
            statut_cas = "unavailable"
        elif "fallback" in statuts:
            statut_cas = "fallback"
        else:
            statut_cas = "ok"

        verifier_predictions_avec_statut(
            predictions,
            statut_cas,
        )

    return len(groupes)

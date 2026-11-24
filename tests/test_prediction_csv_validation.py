
import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.app.prediction_csv_validation import (
    COLONNES_ATTENDUES,
    verifier_fichier_predictions_csv,
)


class TestPredictionCSVValidation(unittest.TestCase):

    def creer_csv(self, chemin, modifier=None):
        """Crée un fichier CSV fictif de 24 horizons."""

        origine = "2026-05-31T22:00:00+00:00"
        debut = datetime.fromisoformat(origine)

        lignes = []

        for i in range(24):
            lignes.append({
                "case_id": "cas_test",
                "method_run_id": "modele_test",
                "model_run_id": "",
                "counter_id": "compteur_test",
                "origin": origine,
                "scenario": "known_site",
                "horizon": str(i + 1),
                "target_timestamp": (
                    debut + timedelta(hours=i)
                ).isoformat(),
                "y_pred": "25.0",
                "variant": "reference",
                "method_used": "weekly_naive",
                "prediction_status": "ok",
                "status_reason": "",
                "fit_cutoff": "",
                "support_id": "",
                "adaptation_id": "",
                "snapshot_id": "snapshot_test",
                "context_version": "",
                "protocol_id": "proto_test",
                "feature_version": "",
            })

        if modifier is not None:
            modifier(lignes)

        with open(
            chemin,
            "w",
            newline="",
            encoding="utf-8",
        ) as fichier:
            writer = csv.DictWriter(
                fichier,
                fieldnames=COLONNES_ATTENDUES,
            )
            writer.writeheader()
            writer.writerows(lignes)

    def executer_validation(self, modifier=None):
        """Crée un CSV temporaire, puis le valide."""

        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "test.pred.csv"
            self.creer_csv(chemin, modifier)
            return verifier_fichier_predictions_csv(chemin)

    # TEST 1 : CSV valide
    def test_csv_valide(self):
        self.assertEqual(self.executer_validation(), 1)

    # TEST 2 : seulement 23 horizons
    def test_csv_23_lignes(self):
        def modifier(lignes):
            lignes.pop()

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 3 : horizon dupliqué
    def test_csv_horizon_duplique(self):
        def modifier(lignes):
            lignes[5]["horizon"] = "4"

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 4 : prédiction négative
    def test_csv_valeur_negative(self):
        def modifier(lignes):
            lignes[5]["y_pred"] = "-10"

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 5 : unavailable avec valeur manquante
    def test_csv_unavailable_avec_manquant(self):
        def modifier(lignes):
            lignes[5]["y_pred"] = ""
            lignes[5]["prediction_status"] = "unavailable"
            lignes[5]["status_reason"] = "lag168_missing"

        self.assertEqual(self.executer_validation(modifier), 1)

    # TEST 6 : statut ok avec valeur manquante
    def test_csv_ok_avec_manquant(self):
        def modifier(lignes):
            lignes[5]["y_pred"] = ""

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 7 : fallback sans raison
    def test_csv_fallback_sans_raison(self):
        def modifier(lignes):
            lignes[5]["prediction_status"] = "fallback"
            lignes[5]["status_reason"] = ""

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 8 : fallback sans méthode
    def test_csv_fallback_sans_methode(self):
        def modifier(lignes):
            lignes[5]["prediction_status"] = "fallback"
            lignes[5]["status_reason"] = "lag168_missing"
            lignes[5]["method_used"] = ""

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 9 : unavailable sans raison
    def test_csv_unavailable_sans_raison(self):
        def modifier(lignes):
            lignes[5]["y_pred"] = ""
            lignes[5]["prediction_status"] = "unavailable"
            lignes[5]["status_reason"] = ""

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    def test_csv_error_conserve_dans_le_cas(self):
        def modifier(lignes):
            lignes[5].update(
                prediction_status="error",
                y_pred="",
                status_reason="Historique local indisponible",
            )

        self.assertEqual(self.executer_validation(modifier), 1)

    def test_csv_error_avec_valeur_ou_sans_raison(self):
        for valeur, raison in (("25.0", "Erreur"), ("", "")):
            with self.subTest(valeur=valeur, raison=raison):
                def modifier(lignes):
                    lignes[5].update(prediction_status="error", y_pred=valeur, status_reason=raison)

                with self.assertRaises(ValueError):
                    self.executer_validation(modifier)

    # TEST 10 : compteur incohérent
    def test_csv_compteur_incoherent(self):
        def modifier(lignes):
            lignes[5]["counter_id"] = "autre_compteur"

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 11 : scénario invalide
    def test_csv_scenario_invalide(self):
        def modifier(lignes):
            lignes[5]["scenario"] = "unknown"

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 12 : snapshot incohérent
    def test_csv_snapshot_incoherent(self):
        def modifier(lignes):
            lignes[5]["snapshot_id"] = "autre_snapshot"

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    # TEST 13 : horodatage incorrect
    def test_csv_horodatage_incorrect(self):
        def modifier(lignes):
            lignes[5]["target_timestamp"] = (
                "2026-06-01T12:00:00+00:00"
            )

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)


if __name__ == "__main__":
    unittest.main()

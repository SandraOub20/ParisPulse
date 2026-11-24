
import csv
import tempfile
import unittest
from pathlib import Path

from src.app.prediction_csv_validation import (
    verifier_fichier_predictions_csv,
)


class TestPredictionCSVValidation(unittest.TestCase):

    def creer_csv(self, chemin, modifier=None):
        """Crée un petit CSV fictif de 24 horizons."""

        colonnes = [
            "case_id",
            "method_run_id",
            "origin",
            "horizon",
            "target_timestamp",
            "y_pred",
            "prediction_status",
            "status_reason",
            "method_used",
        ]


        origine = "2026-05-31T22:00:00+00:00"

        from datetime import datetime, timedelta

        debut = datetime.fromisoformat(origine)
        lignes = []

        for i in range(24):
            lignes.append({
                "case_id": "cas_test",
                "method_run_id": "modele_test",
                "origin": origine,
                "horizon": str(i + 1),
                "target_timestamp": (
                    debut + timedelta(hours=i)
                ).isoformat(),
                "y_pred": "25.0",
                "prediction_status": "ok",
                "status_reason": "",
                "method_used": "modele_test",
            })

        if modifier is not None:
            modifier(lignes)

        with open(chemin, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=colonnes)
            writer.writeheader()
            writer.writerows(lignes)

    def executer_validation(self, modifier=None):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "test.pred.csv"
            self.creer_csv(chemin, modifier)
            return verifier_fichier_predictions_csv(chemin)

    def test_csv_valide(self):
        self.assertEqual(self.executer_validation(), 1)

    def test_csv_23_lignes(self):
        def modifier(lignes):
            lignes.pop()

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    def test_csv_horizon_duplique(self):
        def modifier(lignes):
            lignes[5]["horizon"] = "4"

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    def test_csv_valeur_negative(self):
        def modifier(lignes):
            lignes[5]["y_pred"] = "-10"

        with self.assertRaises(ValueError):
            self.executer_validation(modifier)

    def test_csv_unavailable_avec_manquant(self):
        def modifier(lignes):
            lignes[5]["y_pred"] = ""
            lignes[5]["prediction_status"] = "unavailable"
            lignes[5]["status_reason"] = "lag168_missing"

        self.assertEqual(
            self.executer_validation(modifier), 1
        )


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

if __name__ == "__main__":
    unittest.main()

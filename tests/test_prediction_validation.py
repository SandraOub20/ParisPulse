
import unittest
from datetime import datetime, timedelta, timezone

from src.app.prediction_validation import (
    verifier_24_predictions,
    verifier_valeurs,
    verifier_horizons,
)


class TestPredictionValidation(unittest.TestCase):

    # TEST 1 : Vérifier 24 prévisions
    def test_24_predictions_valides(self):
        predictions = [20] * 24

        self.assertTrue(
            verifier_24_predictions(predictions)
        )

    # TEST 2 : Détecter 23 prévisions
    def test_23_predictions_invalides(self):
        predictions = [20] * 23

        with self.assertRaises(ValueError):
            verifier_24_predictions(predictions)

    # TEST 3 : Vérifier les valeurs correctes
    def test_valeurs_valides(self):
        predictions = [20, 30, 0, 50]

        self.assertTrue(
            verifier_valeurs(predictions)
        )

    # TEST 4 : Détecter une valeur négative
    def test_valeur_negative(self):
        predictions = [20] * 24
        predictions[5] = -10

        with self.assertRaises(ValueError):
            verifier_valeurs(predictions)

    # TEST 5 : Détecter une valeur NaN
    def test_valeur_nan(self):
        predictions = [20] * 24
        predictions[3] = float("nan")

        with self.assertRaises(ValueError):
            verifier_valeurs(predictions)

    # TEST 6 : Vérifier 24 horizons UTC
    def test_horizons_valides(self):
        origine = datetime(
            2025, 10, 15, tzinfo=timezone.utc
        )

        heures = [
            (origine + timedelta(hours=i)).isoformat()
            for i in range(24)
        ]

        self.assertTrue(
            verifier_horizons(origine.isoformat(), heures)
        )

    # TEST 7 : Détecter une heure incorrecte
    def test_horizon_incorrect(self):
        origine = datetime(
            2025, 10, 15, tzinfo=timezone.utc
        )

        heures = [
            (origine + timedelta(hours=i)).isoformat()
            for i in range(24)
        ]

        # On remplace la 6e heure par la 7e
        heures[5] = heures[6]

        with self.assertRaises(ValueError):
            verifier_horizons(origine.isoformat(), heures)


if __name__ == "__main__":
    unittest.main()

"""Tests V1 : données E1, séparation des directions et score local sans fuite."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import types

import numpy as np
import pandas as pd

from src.app import v1_service as svc


class V1ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.snapshot = self.base / "data" / "processed" / "hist-test"
        self.snapshot.mkdir(parents=True)
        self.origin = pd.Timestamp("2026-08-10T00:00:00+00:00")
        self.case = SimpleNamespace(
            case_id="case-1", counter_id="SENS-A", origin=self.origin,
            scenario="known_site", snapshot_id="hist-test", protocol_id="proto-test",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def make_history(self):
        hours = pd.date_range(self.origin, periods=24, freq="h", tz="UTC")
        x = pd.DataFrame({
            "counter_id": ["SENS-A"] * 24, "timestamp": hours,
            "interval_end": hours + pd.Timedelta(hours=1),
            "count_raw": [100.0] * 24, "count": [100.0] * 24,
            "is_observed": [True] * 24, "is_scoreable": [True] * 24,
        })
        x.loc[3, ["count_raw", "count"]] = [np.nan, 70.0]
        x.loc[3, ["is_observed", "is_scoreable"]] = [False, False]
        x.loc[5, ["count_raw", "count"]] = [0.0, 0.0]
        return x

    def make_forecasts(self):
        hours = pd.date_range(self.origin, periods=24, freq="h", tz="UTC")
        return pd.DataFrame({
            "case_id": ["case-1"] * 24,
            "counter_id": ["SENS-A"] * 24,
            "origin": [self.origin] * 24,
            "horizon": list(range(1, 25)),
            "target_timestamp": hours,
            "y_pred": [110.0] * 24,
            "method_run_id": ["baseline"] * 24,
            "prediction_status": ["ok"] * 24,
        })

    def test_inventory_keeps_two_directions_separate(self):
        pd.DataFrame({
            "counter_id": ["SENS-A", "SENS-B"],
            "site_name": ["Même site", "Même site"],
            "latitude": [48.8, 48.8], "longitude": [2.3, 2.3],
            "direction": ["Nord", "Sud"],
        }).to_csv(self.snapshot / "counters.csv", index=False)
        pd.DataFrame({
            "counter_id": ["SENS-A", "SENS-A", "SENS-B"],
            "period_role": ["quality", "selection", "selection"],
            "selection_status": ["excluded", "retained", "retained"],
            "site_role": ["S_train", "S_train", "S_train"],
        }).to_csv(self.snapshot / "inventory_quality.csv", index=False)
        inv = svc.load_inventory(self.snapshot)
        self.assertEqual(len(inv), 2)
        self.assertEqual(set(inv["counter_id"]), {"SENS-A", "SENS-B"})
        self.assertEqual(set(inv["selection_status"]), {"retained"})

    def test_read_counter_and_keep_imputed_hour_distinct(self):
        data = self.make_history()
        other = data.copy()
        other["counter_id"] = "SENS-B"
        pd.concat([data, other], ignore_index=True).to_csv(self.snapshot / "counts.csv", index=False)
        got = svc.load_counter_history(self.snapshot, "SENS-A", chunksize=7)
        self.assertEqual(len(got), 24)
        self.assertEqual(set(got["counter_id"]), {"SENS-A"})
        self.assertFalse(bool(got.loc[3, "is_scoreable"]))
        self.assertEqual(got.loc[3, "count"], 70.0)
        self.assertTrue(pd.isna(got.loc[3, "count_raw"]))
        self.assertTrue(bool(got.loc[5, "is_scoreable"]))
        self.assertEqual(got.loc[5, "count_raw"], 0.0)

    def test_score_does_not_treat_missing_observations_as_zero(self):
        f = self.make_forecasts()
        h = self.make_history()
        result = svc.evaluate_local(self.case, f, h)
        self.assertEqual(result["n_compared_hours"], 23)
        self.assertAlmostEqual(result["mae"], (22 * 10 + 110) / 23)
        errors = result["errors"]
        self.assertEqual(list(errors.columns), svc.ERROR_COLUMNS)
        self.assertFalse(bool(errors.iloc[3]["is_scoreable"]))
        self.assertTrue(pd.isna(errors.iloc[3]["absolute_error"]))
        self.assertEqual(errors.iloc[5]["y_true"], 0.0)
        self.assertEqual(errors.iloc[5]["absolute_error"], 110.0)

    def test_forecast_rejects_wrong_target_hour(self):
        f = self.make_forecasts()
        f.loc[0, "target_timestamp"] = self.origin + pd.Timedelta(hours=10)
        with self.assertRaisesRegex(ValueError, "heures différentes"):
            svc.validate_forecast(f, self.case)

    def test_forecast_rejects_wrong_counter(self):
        f = self.make_forecasts()
        f.loc[1, "counter_id"] = "SENS-B"
        with self.assertRaisesRegex(ValueError, "autre compteur"):
            svc.validate_forecast(f, self.case)

    def test_forecast_can_be_missing_but_not_zero_by_default(self):
        f = self.make_forecasts()
        f.loc[1, "y_pred"] = np.nan
        f.loc[1, "prediction_status"] = "unavailable"
        result = svc.evaluate_local(self.case, f, self.make_history())
        self.assertEqual(result["n_compared_hours"], 22)
        self.assertEqual(result["n_forecast_hours"], 23)

    def test_model_receives_only_past_data(self):
        h = self.make_history()
        older = h.copy()
        older["timestamp"] -= pd.Timedelta(days=8)
        older["interval_end"] -= pd.Timedelta(days=8)
        h = pd.concat([h, older], ignore_index=True)
        fake_mod = types.ModuleType("src.models.known.predict")
        fake_mod.default_publication_lag = lambda: 24
        observed = {}
        def fake_predict(case, history, variant):
            observed["latest"] = history["interval_end"].max()
            observed["values"] = list(history["count"])
            observed["variant"] = variant
            return SimpleNamespace(to_forecast_frame=lambda: self.make_forecasts())
        fake_mod.predict_24h = fake_predict
        parent = types.ModuleType("src.models")
        known = types.ModuleType("src.models.known")
        with patch.dict(sys.modules, {
            "src.models": parent, "src.models.known": known,
            "src.models.known.predict": fake_mod,
        }):
            got = svc.predict_known_reference(self.case, h)
        self.assertEqual(len(got), 24)
        self.assertLessEqual(observed["latest"], self.origin - pd.Timedelta(hours=24))
        self.assertEqual(observed["variant"], "reference")


if __name__ == "__main__":
    unittest.main()

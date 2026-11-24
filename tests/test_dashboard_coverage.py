"""Contrôler la représentation des trous horaires et des changements d'heure."""

import math

import pandas as pd

from src.app.dashboard.coverage import (
    CORRECTED,
    EXCLUDED,
    FILLED,
    MEASURED,
    MISSING,
    availability_plot,
    hourly_status,
    hourly_window,
)


def test_hourly_coverage_distinguishes_zeros_gaps_and_e1_replacements():
    hours = pd.date_range("2026-10-24T22:00Z", periods=6, freq="h")
    history = pd.DataFrame(
        {
            "timestamp": hours[[0, 1, 3, 4, 5]],
            "count_raw": [0.0, None, 0.0, 0.0, 77.0],
            "count": [0.0, 18.0, 0.0, 12.0, 77.0],
            "is_observed": [True, False, True, True, True],
            "is_scoreable": [True, False, False, False, True],
        }
    )
    history["interval_end"] = history["timestamp"] + pd.Timedelta(hours=1)

    window = hourly_window(history, hours[0], hours[-1])
    status = hourly_status(window)
    assert list(status) == [MEASURED, FILLED, MISSING, EXCLUDED, CORRECTED]
    assert len(window) == 5

    measured, estimated, excluded, missing = availability_plot(window, status).data
    assert measured.y[0] == 0
    assert math.isnan(measured.y[2])
    assert not measured.connectgaps
    assert list(estimated.y) == [18, 12]
    assert list(missing.x) == [hours[2]]
    assert list(excluded.x) == [hours[3]]
    assert missing.yaxis == "y2"
    assert "02:00 (UTC+0200)" in missing.text[0]
    assert "02:00 (UTC+0100)" in excluded.text[0]

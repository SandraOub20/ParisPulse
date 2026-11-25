
"""Temporary test for the 24-hour forecast visualization."""

import pandas as pd
import streamlit as st

from src.app.dashboard.predictions import show_predictions

st.set_page_config(page_title="ParisPulse - Forecast Test", layout="wide")

st.title("ParisPulse — 24-hour forecast")
st.warning("DEMONSTRATION ONLY — all values below are fictitious.")

# Generate 24 hourly timestamps in Paris time.
timestamps = pd.date_range(
    start="2026-11-17 00:00",
    periods=24,
    freq="h",
    tz="Europe/Paris",
)

# Forecast origin: first timestamp, converted to UTC.
origin = timestamps[0].tz_convert("UTC")

# Fictitious predictions.
predictions = pd.DataFrame({
    "origin": [origin] * 24,
    "horizon": range(1, 25),
    "target_timestamp": timestamps,
    "y_pred": [
        35, 28, 20, 15, 12, 18, 30, 55,
        85, 110, 125, 130, 120, 115, 108, 100,
        95, 105, 115, 100, 80, 65, 50, 40,
    ],
    "prediction_status": ["ok"] * 24,
    "method_used": ["demo_model"] * 24,
})

# Fictitious actual observations.
observations = pd.DataFrame({
    "target_timestamp": timestamps,
    "y_true": [
        32, 25, 22, 14, 10, 20, 33, 52,
        90, 105, 128, 135, 118, 112, 110, 98,
        92, 108, 119, 97, 83, 63, 48, 42,
    ],
})


def load_demo_observations():
    """Load fictitious observations only after the reveal toggle is enabled."""
    return observations


# Display the forecast and reveal observations only after user consent.
show_predictions(
    predictions=predictions,
    load_observations=load_demo_observations,
    case_id="demo-case-001",
)

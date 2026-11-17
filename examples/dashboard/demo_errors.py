
"""Temporary test for prediction error visualizations."""

import numpy as np
import pandas as pd
import streamlit as st

from src.app.dashboard.errors import show_errors

st.set_page_config(
    page_title="ParisPulse - Error Analysis",
    layout="wide",
)

st.title("ParisPulse — Prediction error analysis")
st.warning(
    "DEMONSTRATION ONLY — all evaluation data below are fictitious."
)

# Generate 24 hourly timestamps in Paris local time.
timestamps = pd.date_range(
    start="2026-11-17 00:00",
    periods=24,
    freq="h",
    tz="Europe/Paris",
)

predicted = [
    35, 28, 20, 15, 12, 18, 30, 55,
    85, 110, 125, 130, 120, 115, 108, 100,
    95, 105, 115, 100, 80, 65, 50, 40,
]

actual = [
    32, 25, 22, 14, 10, 18, 33, 52,
    90, 105, 128, 135, 118, 112, 110, 98,
    92, 108, 119, 97, 83, 63, 48, 42,
]

# Calculate residuals: prediction minus actual observation.
signed_errors = [
    prediction - observation
    for prediction, observation in zip(predicted, actual)
]

# Create 24 valid hourly evaluation rows.
errors = pd.DataFrame({
    "case_id": ["DEMO_CASE_001"] * 24,
    "counter_id": ["DEMO_COUNTER_001"] * 24,
    "horizon": range(1, 25),
    "target_timestamp": timestamps,
    "y_true": actual,
    "y_pred": predicted,
    "is_scoreable": [True] * 24,
    "signed_error": signed_errors,
    "absolute_error": [abs(error) for error in signed_errors],
    "squared_error": [error ** 2 for error in signed_errors],
})

# Add fictitious rows to test data validation.
extra_rows = pd.DataFrame([
    {
        "case_id": "DEMO_CASE_001",
        "counter_id": "DEMO_COUNTER_001",
        "horizon": 25,
        "target_timestamp": timestamps[-1] + pd.Timedelta(hours=1),
        "y_true": 50,
        "y_pred": 55,
        "is_scoreable": False,
        "signed_error": 5,
        "absolute_error": 5,
        "squared_error": 25,
    },
    {
        "case_id": "DEMO_CASE_001",
        "counter_id": "DEMO_COUNTER_001",
        "horizon": 26,
        "target_timestamp": timestamps[-1] + pd.Timedelta(hours=2),
        "y_true": 50,
        "y_pred": 60,
        "is_scoreable": True,
        "signed_error": np.inf,
        "absolute_error": 10,
        "squared_error": 100,
    },
    {
        "case_id": "DEMO_CASE_001",
        "counter_id": "DEMO_COUNTER_001",
        "horizon": 27,
        "target_timestamp": timestamps[-1] + pd.Timedelta(hours=3),
        "y_true": 50,
        "y_pred": 40,
        "is_scoreable": True,
        "signed_error": -10,
        "absolute_error": -10,
        "squared_error": 100,
    },
])

errors = pd.concat(
    [errors, extra_rows],
    ignore_index=True,
)

# Calculate the fictitious MAE using only the 24 valid demo rows.
# This value is for interface testing, not an official evaluation result.
demo_mae = errors.iloc[:24]["absolute_error"].mean()

mae_by_counter = pd.DataFrame({
    "counter_id": ["DEMO_COUNTER_001"],
    "mae": [demo_mae],
})

show_errors(
    errors=errors,
    mae_macro=demo_mae,
    mae_by_counter=mae_by_counter,
)

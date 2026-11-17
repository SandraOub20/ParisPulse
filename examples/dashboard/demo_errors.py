
"""Temporary test for prediction error visualizations."""

import pandas as pd
import streamlit as st

from src.app.dashboard.errors import show_errors

st.set_page_config(page_title="ParisPulse - Error Analysis", layout="wide")

st.title("ParisPulse — Prediction error analysis")
st.warning("DEMONSTRATION ONLY — fictitious evaluation data.")

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
    32, 25, 22, 14, 10, 20, 33, 52,
    90, 105, 128, 135, 118, 112, 110, 98,
    92, 108, 119, 97, 83, 63, 48, 42,
]

signed_errors = [
    prediction - observation
    for prediction, observation in zip(predicted, actual)
]

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

# Fictitious value for interface testing only.
demo_mae = errors["absolute_error"].mean()

mae_by_counter = pd.DataFrame({
    "counter_id": ["DEMO_COUNTER_001"],
    "mae": [demo_mae],
})

show_errors(
    errors=errors,
    mae_macro=demo_mae,
    mae_by_counter=mae_by_counter,
)

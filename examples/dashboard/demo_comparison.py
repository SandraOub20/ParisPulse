
"""Temporary test for forecasting model comparison."""

import numpy as np
import pandas as pd
import streamlit as st

from src.app.dashboard.comparison import show_model_comparison

st.set_page_config(
    page_title="ParisPulse - Model Comparison",
    layout="wide",
)

st.title("ParisPulse — Forecasting model comparison")
st.warning(
    "DEMONSTRATION ONLY — all evaluation results are fictitious."
)

# Three models evaluated under identical conditions.
scores = pd.DataFrame({
    "method_run_id": [
        "Weekly_Baseline",
        "Random_Forest",
        "Gradient_Boosting",
    ],
    "mae_macro": [18.5, 12.3, 9.7],
    "scenario": ["known_site"] * 3,
    "temporal_split": ["test_period"] * 3,
    "comparison_population_id": ["demo_population"] * 3,
    "protocol_id": ["demo_protocol_v2"] * 3,
    "snapshot_id": ["demo_snapshot"] * 3,
    "n_expected_cases": [10] * 3,
    "n_complete_cases": [10] * 3,
    "n_compared_cases": [10] * 3,
    "n_compared_hours": [240] * 3,
    "n_evaluable_counters": [1] * 3,
    "coverage_24h": [1.0] * 3,
    "rmse": [22.0, 15.0, 12.0],
    "bias": [2.0, 1.0, 0.5],
    "n_fallback_cases": [0] * 3,
})

# Add an invalid MAE row to test validation.
invalid_mae_row = pd.DataFrame({
    "method_run_id": ["Invalid_Demo"],
    "mae_macro": [np.inf],
    "scenario": ["known_site"],
    "temporal_split": ["test_period"],
    "comparison_population_id": ["demo_population"],
    "protocol_id": ["demo_protocol_v2"],
    "snapshot_id": ["demo_snapshot"],
    "n_expected_cases": [10],
    "n_complete_cases": [10],
    "n_compared_cases": [10],
    "n_compared_hours": [240],
    "n_evaluable_counters": [1],
    "coverage_24h": [1.0],
    "rmse": [20.0],
    "bias": [1.0],
    "n_fallback_cases": [0],
})

scores = pd.concat(
    [scores, invalid_mae_row],
    ignore_index=True,
)

show_model_comparison(scores)

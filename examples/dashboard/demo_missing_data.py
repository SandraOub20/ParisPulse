
"""Temporary test for missing-data visualization."""

import pandas as pd
import streamlit as st

from src.app.dashboard.missing_data import show_missing_data

st.set_page_config(page_title="ParisPulse - Data Quality", layout="wide")

st.title("ParisPulse — Missing data analysis")
st.warning(
    "DEMONSTRATION ONLY — fictitious bicycle observations."
)

timestamps = pd.date_range(
    start="2026-11-17 00:00",
    periods=12,
    freq="h",
    tz="Europe/Paris",
)

data = pd.DataFrame({
    "timestamp": timestamps,
    "count": [
        45, 0, 72, None, 95, 83,
        None, 0, 110, 125, None, 68,
    ],
    "is_observed": [
        True, True, True, False, True, True,
        True, True, True, True, None, True,
    ],
})

show_missing_data(data)

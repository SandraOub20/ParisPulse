
"""Temporary test for the historical observations chart."""

import pandas as pd
import streamlit as st

from src.app.dashboard.history import show_history

st.set_page_config(page_title="ParisPulse - History Test", layout="wide")

st.title("ParisPulse — Historical observations")
st.warning(
    "DEMONSTRATION ONLY — all values below are fictitious."
)

timestamps = pd.date_range(
    start="2026-11-16 08:00",
    periods=12,
    freq="h",
    tz="Europe/Paris",
)

data = pd.DataFrame({
    "timestamp": timestamps,
    "count": [
        45, 72, 95, 0, 110, None,
        98, None, 76, 90, 105, 68,
    ],
    "is_observed": [
        True, True, True, True, True, True,
        False, False, True, True, True, True,
    ],
})

show_history(data)


"""Temporary test for the historical observations chart."""

import pandas as pd
import streamlit as st

from src.app.dashboard.history import show_history

st.set_page_config(page_title="ParisPulse - History Test", layout="wide")

st.title("ParisPulse — Historical observations")
st.warning("DEMONSTRATION ONLY — fictitious data, not real ParisPulse observations.")

data = pd.DataFrame({
    "timestamp": pd.date_range(
        start="2026-11-16 08:00",
        periods=12,
        freq="h",
        tz="Europe/Paris",
    ),
    "count": [45, 72, 95, 83, 110, 125, 98, 87, 76, 90, 105, 68],
})

show_history(data)

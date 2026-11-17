
"""Historical bicycle observations visualization."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


def show_history(data: pd.DataFrame) -> None:
    """Display historical bicycle counts for a selected counter."""

    st.subheader("Historical observations")

    required_columns = {"timestamp", "count"}
    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        st.error(
            f"Missing required columns: {', '.join(sorted(missing_columns))}"
        )
        return

    if data.empty:
        st.info("No historical observations available.")
        return

    history = data.copy()

    # Parse timestamps and numeric counts.
    history["timestamp"] = pd.to_datetime(
        history["timestamp"], utc=True, errors="coerce"
    )
    history["count"] = pd.to_numeric(
        history["count"], errors="coerce"
    )

    invalid_timestamps = int(history["timestamp"].isna().sum())

    # A usable count must be finite.
    finite_counts = (
        history["count"].notna()
        & np.isfinite(history["count"])
    )

    history.loc[~finite_counts, "count"] = np.nan

    unavailable_counts = int(history["count"].isna().sum())

    # Remove rows without valid timestamps.
    history = history.dropna(subset=["timestamp"]).copy()

    if history.empty:
        st.warning("No valid timestamps available.")
        st.caption(
            f"Unavailable counts: {unavailable_counts} | "
            f"Invalid timestamps: {invalid_timestamps}"
        )
        return

    # Convert UTC timestamps to Paris local time for display.
    history["timestamp"] = (
        history["timestamp"].dt.tz_convert("Europe/Paris")
    )

    # Each selected counter should have one row per timestamp.
    if history["timestamp"].duplicated().any():
        st.error("Duplicate observation timestamps were detected.")
        return

    history = history.sort_values("timestamp").copy()

    # Respect the official meaning of is_observed.
    if "is_observed" in history.columns:
        observed = (
            history["is_observed"]
            .astype("string")
            .str.strip()
            .str.lower()
            .map({"true": True, "false": False})
        )

        history["observation_status"] = "Unknown"

        history.loc[
            observed.eq(False),
            "observation_status",
        ] = "Not observed"

        history.loc[
            observed.eq(True) & history["count"].notna(),
            "observation_status",
        ] = "Observed"

        history.loc[
            observed.eq(True) & history["count"].isna(),
            "observation_status",
        ] = "Observed, count unavailable"

    else:
        # Fallback when is_observed is not supplied.
        history["observation_status"] = (
            history["count"]
            .notna()
            .map({True: "Observed", False: "Missing"})
        )

    # Display historical counts.
    fig = px.line(
        history,
        x="timestamp",
        y="count",
        color="observation_status",
        title="Bicycle traffic over time",
        labels={
            "timestamp": "Date and time (Europe/Paris)",
            "count": "Bicycle count",
            "observation_status": "Observation status",
        },
        markers=True,
        hover_data=["observation_status"],
    )

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Date and time (Europe/Paris)",
        yaxis_title="Bicycle count",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics.
    col1, col2, col3 = st.columns(3)

    col1.metric("Total rows", len(data))
    col2.metric("Unavailable counts", unavailable_counts)
    col3.metric("Invalid timestamps", invalid_timestamps)

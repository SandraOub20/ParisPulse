
"""Historical bicycle observations visualization."""

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

    history["timestamp"] = pd.to_datetime(
        history["timestamp"], utc=True, errors="coerce"
    )
    history["count"] = pd.to_numeric(
        history["count"], errors="coerce"
    )

    # Preserve missing-value counts before filtering invalid timestamps.
    missing_count = int(history["count"].isna().sum())
    invalid_timestamps = int(history["timestamp"].isna().sum())

    # Convert UTC timestamps to Paris local time for display.
    history = history.dropna(subset=["timestamp"]).copy()
    history["timestamp"] = history["timestamp"].dt.tz_convert(
        "Europe/Paris"
    )
    history = history.sort_values("timestamp")

    if history.empty:
        st.warning("No valid timestamps available.")
        st.caption(
            f"Missing counts: {missing_count} | "
            f"Invalid timestamps: {invalid_timestamps}"
        )
        return

    # Use is_observed when supplied by the official data contract.
    if "is_observed" in history.columns:
        history["is_observed"] = (
            history["is_observed"]
            .astype("string")
            .str.lower()
            .map({"true": True, "false": False})
        )

        history["observation_status"] = history["is_observed"].map(
            {True: "Observed", False: "Not observed"}
        ).fillna("Unknown")
    else:
        history["observation_status"] = history["count"].notna().map(
            {True: "Observed", False: "Missing"}
        )

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

    st.caption(
        f"Rows: {len(data)} | "
        f"Missing counts: {missing_count} | "
        f"Invalid timestamps: {invalid_timestamps}"
    )

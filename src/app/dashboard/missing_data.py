
"""Missing observation analysis for the ParisPulse dashboard."""

import pandas as pd
import plotly.express as px
import streamlit as st


def show_missing_data(data: pd.DataFrame) -> None:
    """Display missing observations without treating genuine zeros as missing."""

    st.subheader("Missing data analysis")

    required_columns = {"timestamp", "count"}
    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        st.error(
            f"Missing required columns: {', '.join(sorted(missing_columns))}"
        )
        return

    if data.empty:
        st.info("No observations are available.")
        return

    history = data.copy()

    history["timestamp"] = pd.to_datetime(
        history["timestamp"], utc=True, errors="coerce"
    )
    history["count"] = pd.to_numeric(
        history["count"], errors="coerce"
    )

    invalid_timestamps = int(history["timestamp"].isna().sum())
    history = history.dropna(subset=["timestamp"]).copy()

    history["timestamp"] = history["timestamp"].dt.tz_convert(
        "Europe/Paris"
    )

    # Use the official observation flag when available.
    if "is_observed" in history.columns:
        observed_flag = (
            history["is_observed"]
            .astype("string")
            .str.lower()
            .map({"true": True, "false": False})
        )
        history["is_missing"] = observed_flag.eq(False) | (
            observed_flag.isna() & history["count"].isna()
        )
    else:
        history["is_missing"] = history["count"].isna()

    missing_count = int(history["is_missing"].sum())
    total_count = len(history)
    observed_count = total_count - missing_count
    missing_percentage = (
        missing_count / total_count * 100 if total_count else 0
    )
    zero_count = int(
        (history["count"].eq(0) & ~history["is_missing"]).sum()
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total observations", total_count)
    col2.metric("Observed values", observed_count)
    col3.metric("Missing values", missing_count)
    col4.metric("Missing percentage", f"{missing_percentage:.1f}%")

    st.metric("Genuine zero counts", zero_count)

    history["data_status"] = history["is_missing"].map(
        {True: "Missing", False: "Observed"}
    )

    fig = px.scatter(
        history,
        x="timestamp",
        y="count",
        color="data_status",
        title="Bicycle observations and missing values",
        labels={
            "timestamp": "Date and time (Europe/Paris)",
            "count": "Bicycle count",
            "data_status": "Data status",
        },
        hover_data=["data_status"],
    )

    fig.update_layout(
        xaxis_title="Date and time (Europe/Paris)",
        yaxis_title="Bicycle count",
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Data quality summary**")

    if missing_count == 0:
        st.success("No missing observations were detected.")
    else:
        st.warning(
            f"{missing_count} observations are missing "
            f"({missing_percentage:.1f}% of the dataset)."
        )

        missing_rows = history.loc[
            history["is_missing"], ["timestamp"]
        ]
        st.dataframe(missing_rows, use_container_width=True)

    st.caption(
        f"Invalid timestamps excluded: {invalid_timestamps}. "
        "A genuine zero is an observed value; a missing value is unavailable."
    )

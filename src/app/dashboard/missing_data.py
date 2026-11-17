
"""Missing observation analysis for the ParisPulse dashboard."""

import numpy as np
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

    # Parse timestamps and numeric counts.
    history["timestamp"] = pd.to_datetime(
        history["timestamp"], utc=True, errors="coerce"
    )
    history["count"] = pd.to_numeric(
        history["count"], errors="coerce"
    )

    invalid_timestamps = int(history["timestamp"].isna().sum())

    # A valid bicycle count must be finite and non-negative.
    valid_counts = (
        history["count"].notna()
        & np.isfinite(history["count"])
        & history["count"].ge(0)
    )

    history.loc[~valid_counts, "count"] = np.nan

    # Remove rows with invalid timestamps.
    history = history.dropna(subset=["timestamp"]).copy()

    if history.empty:
        st.warning("No valid timestamps available.")
        return

    # Convert UTC timestamps to Paris local time.
    history["timestamp"] = (
        history["timestamp"].dt.tz_convert("Europe/Paris")
    )

    # Each counter should have one row per timestamp.
    if history["timestamp"].duplicated().any():
        st.error("Duplicate observation timestamps were detected.")
        return

    history = history.sort_values("timestamp").copy()

    # Classify observations using the official contract.
    if "is_observed" in history.columns:
        observed_flag = (
            history["is_observed"]
            .astype("string")
            .str.strip()
            .str.lower()
            .map({"true": True, "false": False})
        )

        history["data_status"] = "Unknown"

        history.loc[
            observed_flag.eq(False),
            "data_status",
        ] = "Missing observation"

        history.loc[
            observed_flag.eq(True) & history["count"].notna(),
            "data_status",
        ] = "Observed"

        history.loc[
            observed_flag.eq(True) & history["count"].isna(),
            "data_status",
        ] = "Observed, count unavailable"

    else:
        # Fallback when the official observation flag is absent.
        history["data_status"] = (
            history["count"]
            .notna()
            .map({True: "Observed", False: "Missing"})
        )

    # Calculate summary statistics.
    total_count = len(history)

    missing_count = int(
        history["data_status"].eq("Missing observation").sum()
    )

    observed_count = int(
        history["data_status"].eq("Observed").sum()
    )

    unavailable_observed_count = int(
        history["data_status"]
        .eq("Observed, count unavailable")
        .sum()
    )

    unknown_count = int(
        history["data_status"].eq("Unknown").sum()
    )

    missing_percentage = (
        missing_count / total_count * 100 if total_count else 0
    )

    # Genuine zeros are valid observed counts.
    zero_count = int(
        (
            history["count"].eq(0)
            & history["data_status"].eq("Observed")
        ).sum()
    )

    # Display metrics.
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total observations", total_count)
    col2.metric("Observed values", observed_count)
    col3.metric("Missing observations", missing_count)
    col4.metric("Missing percentage", f"{missing_percentage:.1f}%")

    col5, col6 = st.columns(2)

    col5.metric("Genuine zero counts", zero_count)
    col6.metric("Observed, count unavailable", unavailable_observed_count)

    # Plot only rows with usable numerical counts.
    chart_data = history[history["count"].notna()].copy()

    if not chart_data.empty:
        fig = px.scatter(
            chart_data,
            x="timestamp",
            y="count",
            color="data_status",
            title="Bicycle observations and data availability",
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
    else:
        st.info("No valid numerical counts are available to plot.")

    # Display data quality summary.
    st.markdown("**Data quality summary**")

    if missing_count == 0:
        st.success("No missing source observations were detected.")
    else:
        st.warning(
            f"{missing_count} observations are missing "
            f"({missing_percentage:.1f}% of the dataset)."
        )

        missing_rows = history.loc[
            history["data_status"].eq("Missing observation"),
            ["timestamp", "count", "data_status"],
        ]

        st.dataframe(missing_rows, use_container_width=True)

    if unavailable_observed_count:
        st.info(
            f"{unavailable_observed_count} source observations exist "
            "but have no usable numerical count."
        )

    if unknown_count:
        st.info(
            f"{unknown_count} rows have an unknown observation status."
        )

    st.caption(
        f"Invalid timestamps excluded: {invalid_timestamps}. "
        "Genuine zeros are valid observations, not missing values."
    )

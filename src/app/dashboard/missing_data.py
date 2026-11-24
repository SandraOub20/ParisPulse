
"""Missing observation analysis for the ParisPulse dashboard."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

LOCAL_TZ = "Europe/Paris"


def _parse_bool(values: pd.Series) -> pd.Series:
    """Convert Boolean values and strings into nullable Boolean values."""

    return (
        values.astype("string")
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
        .astype("boolean")
    )


def show_missing_data(data: pd.DataFrame) -> None:
    """Display missing source observations and E1 replacements accurately."""

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

    # Detect whether the complete E1 observation contract is available.
    e1_columns = {
        "count_raw",
        "is_observed",
        "is_scoreable",
    }
    is_e1_data = e1_columns.issubset(history.columns)

    # Keep the original published value separate from the processed value.
    if "count_raw" not in history.columns:
        history["count_raw"] = history["count"]

    # Parse timestamps and numerical values.
    history["timestamp"] = pd.to_datetime(
        history["timestamp"],
        utc=True,
        errors="coerce",
    )

    history["count"] = pd.to_numeric(
        history["count"],
        errors="coerce",
    )

    history["count_raw"] = pd.to_numeric(
        history["count_raw"],
        errors="coerce",
    )

    invalid_timestamps = int(history["timestamp"].isna().sum())

    valid_counts = (
        history["count"].notna()
        & np.isfinite(history["count"].fillna(0))
        & history["count"].ge(0)
    )

    valid_raw_counts = (
        history["count_raw"].notna()
        & np.isfinite(history["count_raw"].fillna(0))
        & history["count_raw"].ge(0)
    )

    invalid_processed_values = int(
        (history["count"].notna() & ~valid_counts).sum()
    )

    invalid_raw_values = int(
        (history["count_raw"].notna() & ~valid_raw_counts).sum()
    )

    history.loc[~valid_counts, "count"] = np.nan
    history.loc[~valid_raw_counts, "count_raw"] = np.nan

    # Remove rows without valid timestamps.
    history = history.dropna(subset=["timestamp"]).copy()

    if history.empty:
        st.warning("No valid timestamps are available.")
        return

    # Convert UTC timestamps to Paris local time.
    history["timestamp"] = (
        history["timestamp"].dt.tz_convert(LOCAL_TZ)
    )

    # Each counter must have one row per timestamp.
    if history["timestamp"].duplicated().any():
        duplicate_count = int(
            history["timestamp"].duplicated().sum()
        )
        st.error(
            f"{duplicate_count} duplicate observation timestamps "
            "were detected."
        )
        return

    history = history.sort_values("timestamp").copy()

    # Parse source observation and scoreability indicators.
    if "is_observed" in history.columns:
        observed_flag = _parse_bool(history["is_observed"])
    else:
        observed_flag = history["count"].notna().astype("boolean")

    if "is_scoreable" in history.columns:
        scoreable_flag = _parse_bool(history["is_scoreable"])
    else:
        scoreable_flag = observed_flag.copy()

    observed = observed_flag.eq(True).fillna(False)
    not_observed = observed_flag.eq(False).fillna(False)

    scoreable = scoreable_flag.eq(True).fillna(False)
    not_scoreable = scoreable_flag.eq(False).fillna(False)

    valid_counts = history["count"].notna()
    valid_raw_counts = history["count_raw"].notna()

    # ---------------------------------------------------------
    # Classify source observations and processed replacements.
    # ---------------------------------------------------------

    history["data_status"] = "Unknown / not classified"

    if is_e1_data:
        # Original observations eligible for evaluation.
        scoreable_measurements = (
            observed
            & scoreable
            & valid_raw_counts
        )

        # Missing source measurements that received an E1 replacement.
        gap_replacements = (
            not_observed
            & valid_counts
        )

        # Missing source measurements that remain unfilled.
        unfilled_source_gaps = (
            not_observed
            & ~valid_counts
        )

        # Observed source values that were replaced during processing.
        observed_replacements = (
            observed
            & not_scoreable
            & valid_counts
            & (
                ~valid_raw_counts
                | history["count"].ne(history["count_raw"]).fillna(False)
            )
        )

        # Original values retained but excluded from evaluation.
        original_non_scoreable = (
            observed
            & not_scoreable
            & valid_raw_counts
            & history["count"].eq(history["count_raw"]).fillna(False)
        )

        history.loc[
            scoreable_measurements,
            "data_status",
        ] = "Original measurement (scoreable)"

        history.loc[
            original_non_scoreable,
            "data_status",
        ] = "Original measurement (not scoreable)"

        history.loc[
            observed_replacements,
            "data_status",
        ] = "E1 replacement (observed source)"

        history.loc[
            gap_replacements,
            "data_status",
        ] = "E1 replacement (missing source)"

        history.loc[
            unfilled_source_gaps,
            "data_status",
        ] = "Missing source observation"

        history.loc[
            observed & ~valid_counts,
            "data_status",
        ] = "Observed, processed count unavailable"

        history.loc[
            observed & ~valid_raw_counts & ~observed_replacements,
            "data_status",
        ] = "Observed, raw source value unavailable"

    else:
        # Backward compatibility for older demo datasets.
        scoreable_measurements = observed & valid_counts
        gap_replacements = pd.Series(False, index=history.index)
        observed_replacements = pd.Series(False, index=history.index)

        unfilled_source_gaps = not_observed
        original_non_scoreable = pd.Series(
            False,
            index=history.index,
        )

        history.loc[
            scoreable_measurements,
            "data_status",
        ] = "Observed (legacy data)"

        history.loc[
            not_observed,
            "data_status",
        ] = "Missing observation"

        st.info(
            "Legacy mode: the complete E1 observation contract "
            "is not available."
        )

    # ---------------------------------------------------------
    # Summary statistics.
    # ---------------------------------------------------------

    total_count = len(history)

    missing_source_count = int(not_observed.sum())

    scoreable_count = int(
        scoreable_measurements.sum()
    )

    gap_replacement_count = int(
        gap_replacements.sum()
    )

    observed_replacement_count = int(
        observed_replacements.sum()
    )

    replacement_count = (
        gap_replacement_count
        + observed_replacement_count
    )

    unfilled_count = int(
        unfilled_source_gaps.sum()
    )

    original_non_scoreable_count = int(
        original_non_scoreable.sum()
    )

    genuine_zero_count = int(
        (
            scoreable_measurements
            & history["count_raw"].eq(0)
        ).sum()
    )

    unavailable_observed_count = int(
        (
            observed
            & ~history["count"].notna()
        ).sum()
    )

    missing_percentage = (
        missing_source_count / total_count * 100
        if total_count
        else 0
    )

    # ---------------------------------------------------------
    # Display metrics.
    # ---------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total historical rows", f"{total_count:,}")
    col2.metric("Scoreable measurements", f"{scoreable_count:,}")
    col3.metric("Missing source observations", f"{missing_source_count:,}")
    col4.metric("E1 processed replacements", f"{replacement_count:,}")

    col5, col6, col7 = st.columns(3)

    col5.metric("Source gaps filled by E1", f"{gap_replacement_count:,}")
    col6.metric("Unfilled source gaps", f"{unfilled_count:,}")
    col7.metric("Genuine measured zeros", f"{genuine_zero_count:,}")

    st.caption(
        f"Missing source observation rate: {missing_percentage:.1f}% "
        "| Original non-scoreable measurements: "
        f"{original_non_scoreable_count:,} "
        f"| Observed rows without processed counts: "
        f"{unavailable_observed_count:,}"
    )

    # ---------------------------------------------------------
    # Plot valid processed counts, preserving their data status.
    # ---------------------------------------------------------

    chart_data = history.loc[
        history["count"].notna()
    ].copy()

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
            hover_data=[
                column
                for column in [
                    "count_raw",
                    "is_observed",
                    "is_scoreable",
                    "data_status",
                    "quality_flags",
                ]
                if column in chart_data.columns
            ],
        )

        fig.update_layout(
            xaxis_title="Date and time (Europe/Paris)",
            yaxis_title="Bicycle count",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )
    else:
        st.info("No valid numerical counts are available to plot.")

    # ---------------------------------------------------------
    # Inspect missing source observations.
    # ---------------------------------------------------------

    st.markdown("**Data quality summary**")

    if missing_source_count == 0:
        st.success("No missing source observations were detected.")
    else:
        st.warning(
            f"{missing_source_count:,} source observations are missing "
            f"({missing_percentage:.1f}% of historical rows). "
            f"E1 filled {gap_replacement_count:,} of these gaps; "
            f"{unfilled_count:,} remain without a processed count."
        )

        missing_columns = [
            column
            for column in [
                "timestamp",
                "count_raw",
                "count",
                "is_observed",
                "is_scoreable",
                "data_status",
                "quality_flags",
            ]
            if column in history.columns
        ]

        missing_rows = history.loc[
            not_observed,
            missing_columns,
        ]

        st.dataframe(
            missing_rows,
            use_container_width=True,
        )

    if unavailable_observed_count:
        st.info(
            f"{unavailable_observed_count:,} rows are marked as observed "
            "but have no usable processed count."
        )

    st.caption(
        f"Invalid timestamps excluded: {invalid_timestamps:,} "
        f"| Invalid processed values: {invalid_processed_values:,} "
        f"| Invalid raw values: {invalid_raw_values:,}. "
        "Genuine zeros are valid measurements, not missing observations."
    )

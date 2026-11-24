
"""Historical bicycle observations visualization using E1 data."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

LOCAL_TZ = "Europe/Paris"


def _parse_bool(values: pd.Series) -> pd.Series:
    """Parse CSV boolean values without treating missing values as False."""

    normalized = (
        values.astype("string")
        .str.strip()
        .str.lower()
    )

    return normalized.map(
        {
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        }
    ).astype("boolean")


def show_history(data: pd.DataFrame) -> None:
    """Display historical counts while distinguishing measurements and replacements.

    E1 conventions:
    - count_raw: original published measurement.
    - count: processed value, potentially replaced by E1.
    - is_observed: whether the source published a measurement.
    - is_scoreable: whether the value is an eligible evaluation target.

    The function expects data already filtered to one counter.
    """

    st.subheader("Historical bicycle observations")

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
    total_input_rows = len(history)

    # Do not accidentally combine several counters into one time series.
    if "counter_id" in history.columns:
        counter_ids = history["counter_id"].dropna().astype(str).unique()

        if len(counter_ids) > 1:
            st.error(
                "History visualization requires one selected counter. "
                "Filter the data by counter_id before calling show_history()."
            )
            return

        if len(counter_ids) == 1:
            st.caption(f"Counter: {counter_ids[0]}")

    # ---------------------------------------------------------
    # 1. Check whether the complete E1 data contract is present
    # ---------------------------------------------------------

    e1_columns = {
        "count_raw",
        "is_observed",
        "is_scoreable",
    }

    is_e1_data = e1_columns.issubset(history.columns)

    if not is_e1_data:
        st.warning(
            "The complete E1 observation columns are not available. "
            "Legacy mode is being used; original measurements and "
            "processed replacements cannot be reliably distinguished."
        )

    # Maintain compatibility with older dashboard demos.
    if "count_raw" not in history.columns:
        history["count_raw"] = history["count"]

    if "is_observed" not in history.columns:
        history["is_observed"] = history["count_raw"].notna()

    if "is_scoreable" not in history.columns:
        history["is_scoreable"] = (
            history["is_observed"]
            & history["count_raw"].notna()
        )

    # ---------------------------------------------------------
    # 2. Parse timestamps and numerical values
    # ---------------------------------------------------------

    history["timestamp"] = pd.to_datetime(
        history["timestamp"],
        utc=True,
        errors="coerce",
    )

    original_count = history["count"].copy()
    original_raw_count = history["count_raw"].copy()

    history["count"] = pd.to_numeric(
        history["count"],
        errors="coerce",
    )

    history["count_raw"] = pd.to_numeric(
        history["count_raw"],
        errors="coerce",
    )

    invalid_timestamps = int(
        history["timestamp"].isna().sum()
    )

    invalid_processed_values = int(
        (
            original_count.notna()
            & (
                history["count"].isna()
                | ~np.isfinite(
                    history["count"].fillna(0)
                )
                | history["count"].lt(0)
            )
        ).sum()
    )

    invalid_raw_values = int(
        (
            original_raw_count.notna()
            & (
                history["count_raw"].isna()
                | ~np.isfinite(
                    history["count_raw"].fillna(0)
                )
                | history["count_raw"].lt(0)
            )
        ).sum()
    )

    # Invalid numerical values become unavailable, never zero.
    valid_processed = (
        history["count"].notna()
        & np.isfinite(history["count"])
        & history["count"].ge(0)
    )

    valid_raw = (
        history["count_raw"].notna()
        & np.isfinite(history["count_raw"])
        & history["count_raw"].ge(0)
    )

    history.loc[~valid_processed, "count"] = np.nan
    history.loc[~valid_raw, "count_raw"] = np.nan

    # Remove invalid timestamps.
    history = history.dropna(
        subset=["timestamp"]
    ).copy()

    if history.empty:
        st.warning("No valid historical timestamps are available.")
        st.caption(
            f"Invalid timestamps: {invalid_timestamps}"
        )
        return

    # ---------------------------------------------------------
    # 3. Parse E1 quality indicators
    # ---------------------------------------------------------

    history["observed_flag"] = _parse_bool(
        history["is_observed"]
    )

    history["scoreable_flag"] = _parse_bool(
        history["is_scoreable"]
    )

    observed = history["observed_flag"].eq(True).fillna(False)
    not_observed = history["observed_flag"].eq(False).fillna(False)

    scoreable = history["scoreable_flag"].eq(True).fillna(False)
    not_scoreable = history["scoreable_flag"].eq(False).fillna(False)

    # An original measurement that is eligible as an evaluation target.
    measured_scoreable = (
        observed
        & scoreable
        & history["count_raw"].notna()
    )

    # An original source measurement that is not eligible as a target.
    reported_not_scoreable = (
        observed
        & not_scoreable
        & history["count_raw"].notna()
    )

    # A processed value that is not an original scoreable measurement.
    # This includes J-7 replacements and eligible prior-year replacements.
    processed_replacement = (
        not_scoreable
        & history["count"].notna()
        & (
            not_observed
            | history["count_raw"].isna()
            | history["count"].ne(history["count_raw"])
        )
    )

    # Genuine measured zero: original zero and scoreable.
    genuine_zero = (
        measured_scoreable
        & history["count_raw"].eq(0)
    )

    history["display_status"] = "Unknown / not classified"

    history.loc[
        measured_scoreable,
        "display_status",
    ] = "Original measurement (scoreable)"

    history.loc[
        reported_not_scoreable,
        "display_status",
    ] = "Original measurement (not scoreable)"

    history.loc[
        processed_replacement,
        "display_status",
    ] = "Processed replacement (not scoreable)"

    history.loc[
        not_observed & history["count"].isna(),
        "display_status",
    ] = "Missing observation"

    history.loc[
        observed & history["count_raw"].isna(),
        "display_status",
    ] = "Observed flag, raw value unavailable"

    # ---------------------------------------------------------
    # 4. Validate the historical timeline
    # ---------------------------------------------------------

    # Convert UTC timestamps to Paris time only for display.
    history["timestamp"] = (
        history["timestamp"].dt.tz_convert(LOCAL_TZ)
    )

    if history["timestamp"].duplicated().any():
        duplicate_count = int(
            history["timestamp"].duplicated().sum()
        )

        st.error(
            f"{duplicate_count} duplicate timestamps were detected. "
            "The historical series cannot be displayed safely."
        )
        return

    history = history.sort_values(
        "timestamp"
    ).copy()

    # ---------------------------------------------------------
    # 5. Prepare hover information
    # ---------------------------------------------------------

    for column in [
        "quality_flags",
        "source_file_id",
        "is_observed",
        "is_scoreable",
    ]:
        if column not in history.columns:
            history[column] = ""

    hover_data = history[
        [
            "is_observed",
            "is_scoreable",
            "quality_flags",
            "source_file_id",
        ]
    ].fillna("").astype(str).to_numpy()

    # ---------------------------------------------------------
    # 6. Draw the historical chart
    # ---------------------------------------------------------

    fig = go.Figure()

    # Blue line: original measurements eligible for scoring.
    # Genuine zeros remain visible as zero.
    fig.add_trace(
        go.Scatter(
            x=history["timestamp"],
            y=history["count_raw"].where(
                measured_scoreable
            ),
            mode="lines+markers",
            name="Original measurements (scoreable)",
            line=dict(
                color="#2563eb",
                width=1.5,
            ),
            marker=dict(
                color="#2563eb",
                size=4,
                symbol="circle",
            ),
            connectgaps=False,
            customdata=hover_data,
            hovertemplate=(
                "Time: %{x}<br>"
                "Original count: %{y}<br>"
                "Observed: %{customdata[0]}<br>"
                "Scoreable: %{customdata[1]}<br>"
                "Quality flags: %{customdata[2]}"
                "<extra>Original measurement</extra>"
            ),
        )
    )

    # Grey markers: published values that E1 marked as not scoreable.
    # For example, an original zero that was replaced in processed count.
    reported_data = history.loc[
        reported_not_scoreable
    ].copy()

    if not reported_data.empty:
        fig.add_trace(
            go.Scatter(
                x=reported_data["timestamp"],
                y=reported_data["count_raw"],
                mode="markers",
                name="Original published value (not scoreable)",
                marker=dict(
                    color="#94a3b8",
                    size=7,
                    symbol="circle-open",
                    line=dict(width=1.5),
                ),
                customdata=reported_data[
                    [
                        "quality_flags",
                        "is_scoreable",
                    ]
                ].fillna("").astype(str).to_numpy(),
                hovertemplate=(
                    "Time: %{x}<br>"
                    "Original published count: %{y}<br>"
                    "Scoreable: %{customdata[1]}<br>"
                    "Quality flags: %{customdata[0]}"
                    "<extra>Original, not scoreable</extra>"
                ),
            )
        )

    # Orange diamonds: E1 processed replacements.
    # These are never labelled as original measurements.
    replacement_data = history.loc[
        processed_replacement
    ].copy()

    if not replacement_data.empty:
        fig.add_trace(
            go.Scatter(
                x=replacement_data["timestamp"],
                y=replacement_data["count"],
                mode="markers",
                name="E1 processed replacement (not scoreable)",
                marker=dict(
                    color="#f59e0b",
                    size=8,
                    symbol="diamond",
                    line=dict(
                        color="white",
                        width=0.7,
                    ),
                ),
                customdata=replacement_data[
                    [
                        "count_raw",
                        "is_observed",
                        "is_scoreable",
                        "quality_flags",
                    ]
                ].fillna("").astype(str).to_numpy(),
                hovertemplate=(
                    "Time: %{x}<br>"
                    "Processed value: %{y}<br>"
                    "Original raw value: %{customdata[0]}<br>"
                    "Observed: %{customdata[1]}<br>"
                    "Scoreable: %{customdata[2]}<br>"
                    "Quality flags: %{customdata[3]}"
                    "<extra>E1 processed replacement</extra>"
                ),
            )
        )

    fig.update_layout(
        title="Historical bicycle traffic",
        xaxis_title="Date and time (Europe/Paris)",
        yaxis_title="Bicycle count",
        hovermode="x unified",
        legend_title="Value type",
        height=520,
    )

    fig.update_xaxes(
        showgrid=True,
    )

    fig.update_yaxes(
        rangemode="tozero",
        showgrid=True,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    # ---------------------------------------------------------
    # 7. Historical data summary
    # ---------------------------------------------------------

    missing_processed = int(
        history["count"].isna().sum()
    )

    original_measurements = int(
        measured_scoreable.sum()
        + reported_not_scoreable.sum()
    )

    replacement_count = int(
        processed_replacement.sum()
    )

    genuine_zero_count = int(
        genuine_zero.sum()
    )

    metric_columns = st.columns(5)

    metric_columns[0].metric(
        "Historical rows",
        f"{len(history):,}",
    )

    metric_columns[1].metric(
        "Scoreable measurements",
        f"{int(measured_scoreable.sum()):,}",
    )

    metric_columns[2].metric(
        "Processed replacements",
        f"{replacement_count:,}",
    )

    metric_columns[3].metric(
        "Missing processed counts",
        f"{missing_processed:,}",
    )

    metric_columns[4].metric(
        "Genuine measured zeros",
        f"{genuine_zero_count:,}",
    )

    st.caption(
        f"Source rows: {total_input_rows:,} | "
        f"Original published measurements: {original_measurements:,} | "
        f"Invalid timestamps: {invalid_timestamps:,} | "
        f"Invalid processed values: {invalid_processed_values:,} | "
        f"Invalid raw values: {invalid_raw_values:,}"
    )

    # ---------------------------------------------------------
    # 8. Inspect unavailable and processed values
    # ---------------------------------------------------------

    exceptional_rows = history.loc[
        ~measured_scoreable,
        [
            "timestamp",
            "count_raw",
            "count",
            "is_observed",
            "is_scoreable",
            "display_status",
            "quality_flags",
        ],
    ].copy()

    if not exceptional_rows.empty:
        with st.expander(
            "Inspect missing, replaced and non-scoreable values"
        ):
            st.caption(
                "Showing up to 100 rows. Processed replacements are "
                "not original measurements and are not evaluation targets."
            )

            st.dataframe(
                exceptional_rows.head(100),
                use_container_width=True,
                hide_index=True,
            )

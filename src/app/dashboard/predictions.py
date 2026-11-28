"""24-hour bicycle forecast visualization."""

from collections.abc import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

LOCAL_TZ = "Europe/Paris"
EXPECTED_HORIZONS = range(1, 25)
VALID_STATUSES = {"ok", "fallback"}


def show_predictions(
    predictions: pd.DataFrame,
    load_observations: Callable[[], pd.DataFrame] | None = None,
    case_id: str | None = None,
) -> bool:
    """Display forecasts and load actual observations only after user consent.

    Normal predictions use blue circular markers.
    Fallback predictions use orange diamond markers.
    Missing or invalid predictions remain visible as gaps.

    Returns True when the user has chosen to reveal observations.
    """

    st.subheader("Next 24 hours — bicycle forecast")

    # ---------------------------------------------------------
    # 1. Validate required input columns
    # ---------------------------------------------------------

    required_columns = {
        "origin",
        "horizon",
        "target_timestamp",
        "y_pred",
    }

    missing_columns = required_columns - set(predictions.columns)

    if missing_columns:
        st.error(f"Missing required columns: {', '.join(sorted(missing_columns))}")
        return False

    if predictions.empty:
        st.info("No forecast is available for this case.")
        return False

    forecast = predictions.copy()

    # ---------------------------------------------------------
    # 2. Parse timestamps and numerical values
    # ---------------------------------------------------------

    forecast["origin"] = pd.to_datetime(
        forecast["origin"],
        utc=True,
        errors="coerce",
    )

    forecast["target_timestamp"] = pd.to_datetime(
        forecast["target_timestamp"],
        utc=True,
        errors="coerce",
    )

    forecast["horizon"] = pd.to_numeric(
        forecast["horizon"],
        errors="coerce",
    )

    forecast["y_pred"] = pd.to_numeric(
        forecast["y_pred"],
        errors="coerce",
    )

    invalid_origins = int(forecast["origin"].isna().sum())
    invalid_timestamps = int(forecast["target_timestamp"].isna().sum())

    # Rows without a usable origin or target timestamp cannot
    # be positioned on the forecast timeline.
    forecast = forecast.dropna(subset=["origin", "target_timestamp"]).copy()

    if forecast.empty:
        st.error("No forecast rows have valid timestamps.")
        return False

    # All rows must belong to the same forecast origin.
    if forecast["origin"].nunique() != 1:
        st.error("A forecast case must contain exactly one origin.")
        return False

    origin = forecast["origin"].iloc[0]

    # ---------------------------------------------------------
    # 3. Validate horizons
    # ---------------------------------------------------------

    valid_horizon = (
        forecast["horizon"].notna()
        & np.isfinite(forecast["horizon"])
        & forecast["horizon"].between(1, 24)
        & forecast["horizon"].mod(1).eq(0)
    )

    invalid_horizons = int((~valid_horizon).sum())

    forecast = forecast.loc[valid_horizon].copy()
    forecast["horizon"] = forecast["horizon"].astype(int)

    if forecast.empty:
        st.error("No valid forecast horizons are available.")
        return False

    # ---------------------------------------------------------
    # 4. Validate target timestamps
    # ---------------------------------------------------------

    expected_timestamps_utc = forecast["origin"] + pd.to_timedelta(
        forecast["horizon"] - 1,
        unit="h",
    )

    timestamp_mismatch = forecast["target_timestamp"] != expected_timestamps_utc

    if timestamp_mismatch.any():
        st.error(
            f"{int(timestamp_mismatch.sum())} forecast rows have "
            "target timestamps inconsistent with origin and horizon."
        )
        return False

    # Exactly one row per horizon is expected.
    if forecast["horizon"].duplicated().any():
        st.error("Duplicate forecast horizons were detected.")
        return False

    forecast = forecast.sort_values("horizon").copy()

    present_horizons = set(forecast["horizon"])
    expected_horizons = set(EXPECTED_HORIZONS)

    missing_horizons = sorted(expected_horizons - present_horizons)

    # ---------------------------------------------------------
    # 5. Prepare status and prediction values
    # ---------------------------------------------------------

    finite_predictions = (
        forecast["y_pred"].notna() & np.isfinite(forecast["y_pred"]) & forecast["y_pred"].ge(0)
    )

    if "prediction_status" in forecast.columns:
        forecast["prediction_status"] = (
            forecast["prediction_status"].astype("string").str.lower().str.strip()
        )
    else:
        # Compatibility with older forecast files without status.
        forecast["prediction_status"] = np.where(
            finite_predictions,
            "ok",
            "unavailable",
        )

    if "method_used" not in forecast.columns:
        forecast["method_used"] = pd.Series(
            pd.NA,
            index=forecast.index,
            dtype="string",
        )

    if "status_reason" not in forecast.columns:
        forecast["status_reason"] = pd.Series(
            pd.NA,
            index=forecast.index,
            dtype="string",
        )

    forecast["is_valid"] = forecast["prediction_status"].isin(VALID_STATUSES) & finite_predictions

    valid_horizons = set(forecast.loc[forecast["is_valid"], "horizon"])

    fallback_hours = int(
        (forecast["prediction_status"].eq("fallback") & forecast["is_valid"]).sum()
    )

    # ---------------------------------------------------------
    # 6. Display validation information
    # ---------------------------------------------------------

    st.caption(
        f"Valid forecasts: {len(valid_horizons)} / 24 | "
        f"Fallback hours: {fallback_hours} | "
        f"Invalid origins: {invalid_origins} | "
        f"Invalid timestamps: {invalid_timestamps} | "
        f"Invalid horizons: {invalid_horizons}"
    )

    if missing_horizons:
        st.warning("Missing forecast horizons: " + ", ".join(map(str, missing_horizons)))

    if len(valid_horizons) != 24:
        st.warning("This case does not contain 24 valid hourly forecasts.")

    # ---------------------------------------------------------
    # 7. Build a complete 24-hour timeline
    # ---------------------------------------------------------

    # Reindexing restores missing horizons as empty rows.
    # It does not replace missing predictions with zero.
    plot_data = forecast.set_index("horizon").reindex(list(EXPECTED_HORIZONS))

    plot_data.index.name = "row_index"
    plot_data["horizon"] = plot_data.index.astype(int)

    # Remember which hours actually existed in the source CSV.
    source_row_present = plot_data["target_timestamp"].notna()

    # Convert existing timestamps to Paris time.
    plot_data["target_timestamp"] = plot_data["target_timestamp"].dt.tz_convert(LOCAL_TZ)

    # Generate expected timestamps only for positioning missing
    # horizon rows on the timeline. No prediction is generated.
    expected_local_timestamps = pd.Series(
        [origin + pd.Timedelta(hours=h - 1) for h in EXPECTED_HORIZONS],
        index=plot_data.index,
    ).dt.tz_convert(LOCAL_TZ)

    plot_data["target_timestamp"] = plot_data["target_timestamp"].combine_first(
        expected_local_timestamps
    )

    # Missing source rows receive explicit diagnostic labels.
    plot_data["prediction_status"] = plot_data["prediction_status"].astype("string")

    plot_data.loc[
        ~source_row_present,
        "prediction_status",
    ] = "missing_horizon"

    plot_data["status_reason"] = plot_data["status_reason"].astype("string")

    plot_data.loc[
        ~source_row_present,
        "status_reason",
    ] = "No prediction row in source CSV"

    # Recalculate validity after inserting missing horizons.
    plot_data["is_valid"] = (
        plot_data["prediction_status"].isin(VALID_STATUSES)
        & plot_data["y_pred"].notna()
        & np.isfinite(plot_data["y_pred"])
        & plot_data["y_pred"].ge(0)
    )

    # Invalid values become NaN in the graph, never zero.
    plot_data["plot_y"] = pd.to_numeric(
        plot_data["y_pred"],
        errors="coerce",
    ).where(plot_data["is_valid"])

    plot_data["is_fallback"] = plot_data["prediction_status"].eq("fallback") & plot_data["is_valid"]

    # ---------------------------------------------------------
    # 8. Display effective methods
    # ---------------------------------------------------------

    methods = sorted(
        plot_data.loc[
            plot_data["is_valid"],
            "method_used",
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    if methods:
        st.caption("Methods used: " + ", ".join(methods))

    # ---------------------------------------------------------
    # 9. Draw the forecast chart
    # ---------------------------------------------------------

    fig = go.Figure()

    # Trend line: connectgaps=False preserves missing hours.
    fig.add_trace(
        go.Scatter(
            x=plot_data["target_timestamp"],
            y=plot_data["plot_y"],
            mode="lines",
            name="Forecast trend",
            line=dict(
                color="#94a3b8",
                width=2,
            ),
            connectgaps=False,
            hoverinfo="skip",
        )
    )

    normal_points = plot_data.loc[plot_data["is_valid"] & ~plot_data["is_fallback"]]

    fallback_points = plot_data.loc[plot_data["is_fallback"]]

    # Normal predictions: blue circles.
    if not normal_points.empty:
        normal_customdata = (
            normal_points[
                [
                    "horizon",
                    "method_used",
                    "prediction_status",
                ]
            ]
            .fillna("")
            .to_numpy()
        )

        fig.add_trace(
            go.Scatter(
                x=normal_points["target_timestamp"],
                y=normal_points["plot_y"],
                mode="markers",
                name="Normal prediction",
                marker=dict(
                    color="#2563eb",
                    size=10,
                    symbol="circle",
                    line=dict(
                        color="white",
                        width=1,
                    ),
                ),
                customdata=normal_customdata,
                hovertemplate=(
                    "Horizon: %{customdata[0]}<br>"
                    "Time: %{x}<br>"
                    "Prediction: %{y}<br>"
                    "Method: %{customdata[1]}<br>"
                    "Status: %{customdata[2]}"
                    "<extra>Normal prediction</extra>"
                ),
            )
        )

    # Fallback predictions: orange diamonds.
    if not fallback_points.empty:
        fallback_customdata = (
            fallback_points[
                [
                    "horizon",
                    "method_used",
                    "prediction_status",
                    "status_reason",
                ]
            ]
            .fillna("")
            .to_numpy()
        )

        fig.add_trace(
            go.Scatter(
                x=fallback_points["target_timestamp"],
                y=fallback_points["plot_y"],
                mode="markers",
                name="Fallback prediction",
                marker=dict(
                    color="#f59e0b",
                    size=12,
                    symbol="diamond",
                    line=dict(
                        color="white",
                        width=1,
                    ),
                ),
                customdata=fallback_customdata,
                hovertemplate=(
                    "Horizon: %{customdata[0]}<br>"
                    "Time: %{x}<br>"
                    "Prediction: %{y}<br>"
                    "Method: %{customdata[1]}<br>"
                    "Status: %{customdata[2]}<br>"
                    "Reason: %{customdata[3]}"
                    "<extra>Fallback prediction</extra>"
                ),
            )
        )

    fig.update_layout(
        title="Predicted bicycle traffic — next 24 hours",
        xaxis_title="Target time (Europe/Paris)",
        yaxis_title="Predicted bicycle count",
        hovermode="x unified",
        legend_title="Prediction type",
        height=480,
    )

    if plot_data["is_valid"].any():
        st.plotly_chart(
            fig,
            use_container_width=True,
        )
    else:
        st.info("No valid prediction is available to display.")

    # ---------------------------------------------------------
    # 10. Report unavailable, invalid and missing predictions
    # ---------------------------------------------------------

    gap_rows = plot_data.loc[
        ~plot_data["is_valid"],
        [
            "prediction_status",
            "status_reason",
        ],
    ].reset_index()

    if not gap_rows.empty:
        st.warning(
            f"{len(gap_rows)} forecast hour(s) are unavailable, "
            "invalid or missing. They are displayed as gaps, not zeros."
        )

        st.dataframe(
            gap_rows.rename(
                columns={
                    "prediction_status": "status",
                    "status_reason": "reason",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    # Preserve all 24 timestamps for the actual-observation comparison.
    display_forecast = plot_data.reset_index(drop=True)
    # ---------------------------------------------------------
    # 11. Reveal actual observations only after user consent
    # ---------------------------------------------------------

    method_key = "unknown_method"

    if "method_run_id" in forecast.columns:
        method_values = forecast["method_run_id"].dropna().astype(str).unique()

        if len(method_values) == 1:
            method_key = method_values[0]

    case_key = case_id or "default"

    state_key = f"reveal_observations_{method_key}_{case_key}"

    revealed = st.toggle(
        "Reveal actual observations",
        key=state_key,
    )

    if not revealed:
        return False

    if load_observations is None:
        st.info("Actual observations are not connected yet.")
        return True

    observations = load_observations()

    if observations is None or observations.empty:
        st.info("Actual observations are not available for this case.")
        return True

    required_actual_columns = {
        "target_timestamp",
        "y_true",
    }

    missing_actual_columns = required_actual_columns - set(observations.columns)

    if missing_actual_columns:
        st.error("Missing observation columns: " + ", ".join(sorted(missing_actual_columns)))
        return True

    # ---------------------------------------------------------
    # 12. Validate and join actual observations
    # ---------------------------------------------------------

    actual = observations.copy()

    actual["target_timestamp"] = pd.to_datetime(
        actual["target_timestamp"],
        utc=True,
        errors="coerce",
    )

    actual["y_true"] = pd.to_numeric(
        actual["y_true"],
        errors="coerce",
    )

    actual = actual.dropna(subset=["target_timestamp"]).copy()

    actual["target_timestamp"] = actual["target_timestamp"].dt.tz_convert(LOCAL_TZ)

    if actual["target_timestamp"].duplicated().any():
        st.error("Duplicate observation timestamps were detected.")
        return True

    comparison = display_forecast[
        [
            "horizon",
            "target_timestamp",
            "plot_y",
        ]
    ].rename(columns={"plot_y": "y_pred"})

    comparison = comparison.merge(
        actual[
            [
                "target_timestamp",
                "y_true",
            ]
        ],
        on="target_timestamp",
        how="left",
        validate="one_to_one",
    )

    # ---------------------------------------------------------
    # 13. Display predictions versus actual observations
    # ---------------------------------------------------------

    comparison_fig = go.Figure()

    comparison_fig.add_trace(
        go.Scatter(
            x=comparison["target_timestamp"],
            y=comparison["y_pred"],
            mode="lines+markers",
            name="Prediction",
            line=dict(color="#2563eb", width=2),
            connectgaps=False,
        )
    )

    comparison_fig.add_trace(
        go.Scatter(
            x=comparison["target_timestamp"],
            y=comparison["y_true"],
            mode="lines+markers",
            name="Actual observations",
            line=dict(color="#16a34a", width=2),
            connectgaps=False,
        )
    )

    comparison_fig.update_layout(
        title="Predictions vs actual observations",
        xaxis_title="Target time (Europe/Paris)",
        yaxis_title="Bicycle count",
        hovermode="x unified",
        height=480,
    )

    st.plotly_chart(
        comparison_fig,
        use_container_width=True,
    )

    return True


"""24-hour bicycle forecast visualization."""

from collections.abc import Callable

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


def show_predictions(
    predictions: pd.DataFrame,
    load_observations: Callable[[], pd.DataFrame] | None = None,
    case_id: str | None = None,
) -> bool:
    """Display forecasts and load actual observations only after user consent.

    Returns True when the user has chosen to reveal observations.
    """

    st.subheader("Next 24 hours — bicycle forecast")

    required_columns = {
        "origin",
        "horizon",
        "target_timestamp",
        "y_pred",
    }
    missing_columns = required_columns - set(predictions.columns)

    if missing_columns:
        st.error(
            f"Missing required columns: {', '.join(sorted(missing_columns))}"
        )
        return False

    if predictions.empty:
        st.info("No forecast is available for this case.")
        return False

    forecast = predictions.copy()

    # Parse timestamps and numeric values.
    forecast["origin"] = pd.to_datetime(
        forecast["origin"], utc=True, errors="coerce"
    )
    forecast["target_timestamp"] = pd.to_datetime(
        forecast["target_timestamp"], utc=True, errors="coerce"
    )
    forecast["horizon"] = pd.to_numeric(
        forecast["horizon"], errors="coerce"
    )
    forecast["y_pred"] = pd.to_numeric(
        forecast["y_pred"], errors="coerce"
    )

    invalid_origins = int(forecast["origin"].isna().sum())
    invalid_timestamps = int(forecast["target_timestamp"].isna().sum())

    forecast = forecast.dropna(
        subset=["origin", "horizon", "target_timestamp"]
    ).copy()

    # Horizons must be integers between 1 and 24.
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

    # Each target timestamp must match origin + (horizon - 1) hours.
    expected_timestamps = (
        forecast["origin"]
        + pd.to_timedelta(forecast["horizon"] - 1, unit="h")
    )

    timestamp_mismatch = (
        forecast["target_timestamp"] != expected_timestamps
    )

    if timestamp_mismatch.any():
        st.error(
            f"{int(timestamp_mismatch.sum())} forecast rows have "
            "target timestamps inconsistent with origin and horizon."
        )
        return False

    # A forecast must have one row per horizon.
    if forecast["horizon"].duplicated().any():
        st.error("Duplicate forecast horizons were detected.")
        return False

    forecast = forecast.sort_values("horizon").copy()

    expected_horizons = set(range(1, 25))
    present_horizons = set(forecast["horizon"])
    missing_horizons = sorted(expected_horizons - present_horizons)

    # Convert timestamps to Paris local time for display.
    forecast["target_timestamp"] = (
        forecast["target_timestamp"].dt.tz_convert("Europe/Paris")
    )

    # Validate prediction values.
    finite_predictions = (
        forecast["y_pred"].notna()
        & np.isfinite(forecast["y_pred"])
        & forecast["y_pred"].ge(0)
    )

    if "prediction_status" in forecast.columns:
        forecast["prediction_status"] = (
            forecast["prediction_status"]
            .astype("string")
            .str.lower()
            .str.strip()
        )

        valid_statuses = {"ok", "fallback"}

        forecast["is_valid"] = (
            forecast["prediction_status"].isin(valid_statuses)
            & finite_predictions
        )
    else:
        forecast["is_valid"] = finite_predictions

    valid_horizons = set(
        forecast.loc[forecast["is_valid"], "horizon"]
    )

    st.caption(
        f"Valid forecasts: {len(valid_horizons)} / 24 | "
        f"Invalid origins: {invalid_origins} | "
        f"Invalid timestamps: {invalid_timestamps} | "
        f"Invalid horizons: {invalid_horizons}"
    )

    if missing_horizons:
        st.warning(
            "Missing forecast horizons: "
            + ", ".join(map(str, missing_horizons))
        )

    if len(valid_horizons) != 24:
        st.warning(
            "This case does not contain 24 valid hourly forecasts."
        )

    display_forecast = forecast[forecast["is_valid"]].copy()

    if not display_forecast.empty:
        if "method_used" in display_forecast.columns:
            methods = sorted(
                display_forecast["method_used"]
                .dropna()
                .astype(str)
                .unique()
            )

            if methods:
                st.caption("Methods used: " + ", ".join(methods))

        fig = px.line(
            display_forecast,
            x="target_timestamp",
            y="y_pred",
            title="Predicted bicycle traffic",
            labels={
                "target_timestamp": "Target time (Europe/Paris)",
                "y_pred": "Predicted bicycle count",
            },
            markers=True,
        )
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No valid prediction is available to display.")

    # Reset the reveal state when the selected case changes.
    state_key = f"reveal_observations_{case_id or 'default'}"

    revealed = st.toggle(
        "Reveal actual observations",
        key=state_key,
    )

    # Actual observations are loaded only after explicit user consent.
    if revealed:
        if load_observations is None:
            st.info("Actual observations are not connected yet.")
            return True

        observations = load_observations()

        if observations is None or observations.empty:
            st.info("Actual observations are not available for this case.")
            return True

        required_actual_columns = {"target_timestamp", "y_true"}
        missing_actual_columns = (
            required_actual_columns - set(observations.columns)
        )

        if missing_actual_columns:
            st.error(
                "Missing observation columns: "
                + ", ".join(sorted(missing_actual_columns))
            )
            return True

        actual = observations.copy()

        actual["target_timestamp"] = pd.to_datetime(
            actual["target_timestamp"], utc=True, errors="coerce"
        )
        actual["y_true"] = pd.to_numeric(
            actual["y_true"], errors="coerce"
        )

        actual = actual.dropna(
            subset=["target_timestamp"]
        ).copy()

        actual["target_timestamp"] = (
            actual["target_timestamp"].dt.tz_convert("Europe/Paris")
        )

        if actual["target_timestamp"].duplicated().any():
            st.error("Duplicate observation timestamps were detected.")
            return True

        comparison = display_forecast.merge(
            actual[["target_timestamp", "y_true"]],
            on="target_timestamp",
            how="left",
            validate="one_to_one",
        )

        comparison_fig = px.line(
            comparison,
            x="target_timestamp",
            y=["y_pred", "y_true"],
            title="Predictions vs actual observations",
            labels={
                "target_timestamp": "Target time (Europe/Paris)",
                "value": "Bicycle count",
                "variable": "Series",
            },
            markers=True,
        )
        comparison_fig.update_layout(hovermode="x unified")
        st.plotly_chart(comparison_fig, use_container_width=True)

    return revealed

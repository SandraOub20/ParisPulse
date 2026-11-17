
"""24-hour bicycle forecast visualization."""

from collections.abc import Callable

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

    required_columns = {"horizon", "target_timestamp", "y_pred"}
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

    forecast["horizon"] = pd.to_numeric(
        forecast["horizon"], errors="coerce"
    )
    forecast["target_timestamp"] = pd.to_datetime(
        forecast["target_timestamp"], utc=True, errors="coerce"
    )
    forecast["y_pred"] = pd.to_numeric(
        forecast["y_pred"], errors="coerce"
    )

    invalid_timestamps = int(forecast["target_timestamp"].isna().sum())
    forecast = forecast.dropna(
        subset=["horizon", "target_timestamp"]
    ).copy()

    if forecast["horizon"].duplicated().any():
        st.error("Duplicate forecast horizons were detected.")
        return False

    forecast = forecast.sort_values("horizon")
    forecast["target_timestamp"] = (
        forecast["target_timestamp"].dt.tz_convert("Europe/Paris")
    )

    if "prediction_status" in forecast.columns:
        forecast["prediction_status"] = (
            forecast["prediction_status"].astype("string").str.lower()
        )
        valid_statuses = {"ok", "fallback"}
        forecast["is_valid"] = (
            forecast["prediction_status"].isin(valid_statuses)
            & forecast["y_pred"].notna()
            & forecast["y_pred"].ge(0)
        )
    else:
        forecast["is_valid"] = (
            forecast["y_pred"].notna() & forecast["y_pred"].ge(0)
        )

    valid_horizons = set(
        forecast.loc[forecast["is_valid"], "horizon"].astype(int)
    )
    expected_horizons = set(range(1, 25))
    missing_horizons = sorted(expected_horizons - set(
        forecast["horizon"].astype(int)
    ))

    st.caption(
        f"Valid forecasts: {len(valid_horizons)} / 24 | "
        f"Invalid timestamps: {invalid_timestamps}"
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
            st.caption(
                "Methods used: "
                + ", ".join(
                    sorted(
                        display_forecast["method_used"]
                        .dropna()
                        .astype(str)
                        .unique()
                    )
                )
            )

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
        "Révéler les observations réelles",
        key=state_key,
    )

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
        actual = actual.dropna(subset=["target_timestamp"])
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

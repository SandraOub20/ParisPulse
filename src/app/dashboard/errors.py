
"""Prediction error visualizations supplied by Team 4."""

import pandas as pd
import plotly.express as px
import streamlit as st


def show_errors(
    errors: pd.DataFrame,
    mae_macro: float | None = None,
    mae_by_counter: pd.DataFrame | None = None,
) -> None:
    """Display evaluation results supplied by Team 4."""

    st.subheader("Prediction errors and model reliability")

    if mae_macro is not None and pd.notna(mae_macro):
        st.metric("Macro MAE (Team 4)", f"{float(mae_macro):.2f}")
    else:
        st.info("Macro MAE has not been provided by Team 4 yet.")

    if errors.empty:
        st.warning("No hourly error data is available.")
        return

    required = {
        "target_timestamp",
        "signed_error",
        "absolute_error",
    }
    missing = required - set(errors.columns)

    if missing:
        st.error(f"Missing columns: {', '.join(sorted(missing))}")
        return

    data = errors.copy()

    data["target_timestamp"] = pd.to_datetime(
        data["target_timestamp"], utc=True, errors="coerce"
    )
    data["signed_error"] = pd.to_numeric(
        data["signed_error"], errors="coerce"
    )
    data["absolute_error"] = pd.to_numeric(
        data["absolute_error"], errors="coerce"
    )

    invalid_timestamps = int(data["target_timestamp"].isna().sum())
    data = data.dropna(
        subset=["target_timestamp", "signed_error", "absolute_error"]
    ).copy()

    if "is_scoreable" in data.columns:
        scoreable = (
            data["is_scoreable"]
            .astype("string")
            .str.lower()
            .map({"true": True, "false": False})
        )
        data = data[scoreable.eq(True)].copy()

    data["target_timestamp"] = data["target_timestamp"].dt.tz_convert(
        "Europe/Paris"
    )
    data = data.sort_values("target_timestamp")

    if data.empty:
        st.warning("No valid scoreable hourly errors are available.")
        return

    st.caption(
        f"Scoreable error rows: {len(data)} | "
        f"Invalid timestamps excluded: {invalid_timestamps}"
    )

    # Experiment visualization 1: actual vs predicted.
    if {"y_true", "y_pred"}.issubset(data.columns):
        st.markdown("**Visualization 1 — Actual vs predicted**")

        comparison = data.copy()
        comparison["y_true"] = pd.to_numeric(
            comparison["y_true"], errors="coerce"
        )
        comparison["y_pred"] = pd.to_numeric(
            comparison["y_pred"], errors="coerce"
        )

        comparison = comparison.dropna(
            subset=["y_true", "y_pred"]
        )

        if not comparison.empty:
            comparison = comparison.melt(
                id_vars="target_timestamp",
                value_vars=["y_true", "y_pred"],
                var_name="series",
                value_name="bicycle_count",
            )

            fig_comparison = px.line(
                comparison,
                x="target_timestamp",
                y="bicycle_count",
                color="series",
                markers=True,
                title="Actual bicycle counts vs predictions",
                labels={
                    "target_timestamp": "Target time (Europe/Paris)",
                    "bicycle_count": "Bicycle count",
                    "series": "Series",
                },
            )
            fig_comparison.update_layout(hovermode="x unified")
            st.plotly_chart(fig_comparison, use_container_width=True)

    # Experiment visualization 2: hourly residuals.
    st.markdown("**Visualization 2 — Hourly prediction errors**")

    fig_errors = px.bar(
        data,
        x="target_timestamp",
        y="signed_error",
        title="Hourly residuals (prediction - actual)",
        labels={
            "target_timestamp": "Target time (Europe/Paris)",
            "signed_error": "Signed prediction error",
        },
        hover_data=["absolute_error"],
    )
    fig_errors.add_hline(y=0, line_dash="dash")
    fig_errors.update_layout(hovermode="x unified")
    st.plotly_chart(fig_errors, use_container_width=True)

    # Optional detailed scores supplied by Team 4.
    if mae_by_counter is not None and not mae_by_counter.empty:
        st.markdown("**MAE by counter — Team 4**")
        st.dataframe(mae_by_counter, use_container_width=True)

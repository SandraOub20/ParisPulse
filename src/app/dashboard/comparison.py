
"""Forecasting model comparison visualization."""

import pandas as pd
import plotly.express as px
import streamlit as st


def show_model_comparison(scores: pd.DataFrame) -> None:
    """Compare models under identical evaluation conditions."""

    st.subheader("Forecasting model comparison")

    required_columns = {
        "method_run_id",
        "mae_macro",
        "scenario",
        "temporal_split",
        "comparison_population_id",
        "protocol_id",
        "snapshot_id",
    }

    missing = required_columns - set(scores.columns)

    if missing:
        st.error(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )
        return

    if scores.empty:
        st.info("No model comparison results are available yet.")
        return

    data = scores.copy()

    data["mae_macro"] = pd.to_numeric(
        data["mae_macro"], errors="coerce"
    )

    data = data.dropna(
        subset=[
            "mae_macro",
            "scenario",
            "temporal_split",
            "comparison_population_id",
            "protocol_id",
            "snapshot_id",
        ]
    )

    if data.empty:
        st.warning("No valid evaluation scores are available.")
        return

    st.markdown("**Select identical evaluation conditions**")

    filter_columns = [
        "scenario",
        "temporal_split",
        "comparison_population_id",
        "protocol_id",
        "snapshot_id",
    ]

    for column in filter_columns:
        values = sorted(data[column].astype(str).unique().tolist())

        selected = st.selectbox(
            f"Select {column}",
            values,
            key=f"model_comparison_{column}",
        )

        data = data[data[column].astype(str) == selected]

    if data.empty:
        st.info("No results match the selected evaluation conditions.")
        return

    # Keep one comparable result per forecasting method.
    if data["method_run_id"].duplicated().any():
        st.warning(
            "Multiple score rows exist for the same method run. "
            "Please select or prepare one comparable evaluation row per run."
        )
        st.dataframe(data, use_container_width=True)
        return

    # Display comparison population information.
    if "n_compared_cases" in data.columns:
        st.caption(
            f"Compared cases: {data['n_compared_cases'].iloc[0]}"
        )

    if "n_compared_hours" in data.columns:
        st.caption(
            f"Compared hours: {data['n_compared_hours'].iloc[0]}"
        )

    if "n_complete_cases" in data.columns:
        st.caption(
            f"Complete cases: {data['n_complete_cases'].iloc[0]}"
        )

    fig = px.bar(
        data,
        x="method_run_id",
        y="mae_macro",
        color="method_run_id",
        title="Macro MAE by forecasting method",
        labels={
            "method_run_id": "Forecasting method",
            "mae_macro": "Macro MAE (lower is better)",
        },
        hover_data=[
            column
            for column in [
                "n_compared_cases",
                "n_compared_hours",
                "n_complete_cases",
                "coverage_24h",
            ]
            if column in data.columns
        ],
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Evaluation results supplied by Team 4**")
    st.dataframe(data, use_container_width=True)

    best = data.loc[data["mae_macro"].idxmin()]

    st.success(
        f"Lowest macro MAE in this comparable selection: "
        f"{best['method_run_id']} ({best['mae_macro']:.2f})"
    )

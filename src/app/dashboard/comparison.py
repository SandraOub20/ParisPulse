
"""Forecasting model comparison visualization."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


def show_model_comparison(scores: pd.DataFrame) -> None:
    """Compare models under identical evaluation conditions."""

    st.subheader("Forecasting model comparison")

    if scores.empty:
        st.info("No model comparison results are available yet.")
        return

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

    data = scores.copy()

    # Validate method identifiers.
    data["method_run_id"] = (
        data["method_run_id"].astype("string").str.strip()
    )

    # Validate numerical MAE values.
    data["mae_macro"] = pd.to_numeric(
        data["mae_macro"], errors="coerce"
    )

    valid_mae = (
        data["mae_macro"].notna()
        & np.isfinite(data["mae_macro"])
        & data["mae_macro"].ge(0)
    )

    invalid_mae_count = int((~valid_mae).sum())
    data = data.loc[valid_mae].copy()

    # Remove rows with missing evaluation metadata.
    metadata_columns = [
        "method_run_id",
        "scenario",
        "temporal_split",
        "comparison_population_id",
        "protocol_id",
        "snapshot_id",
    ]

    for column in metadata_columns:
        data[column] = data[column].astype("string").str.strip()

    valid_metadata = data[metadata_columns].notna().all(axis=1)

    for column in metadata_columns:
        valid_metadata &= data[column].ne("")

    invalid_metadata_count = int((~valid_metadata).sum())
    data = data.loc[valid_metadata].copy()

    if data.empty:
        st.warning("No valid evaluation scores are available.")
        return

    st.caption(
        f"Valid score rows: {len(data)} | "
        f"Invalid MAE rows excluded: {invalid_mae_count} | "
        f"Invalid metadata rows excluded: {invalid_metadata_count}"
    )

    st.markdown("**Select identical evaluation conditions**")

    filter_columns = [
        "scenario",
        "temporal_split",
        "comparison_population_id",
        "protocol_id",
        "snapshot_id",
    ]

    # Filter progressively using the available values.
    for column in filter_columns:
        values = sorted(
            data[column].astype(str).unique().tolist()
        )

        if not values:
            st.warning(f"No available values for {column}.")
            return

        selected = st.selectbox(
            f"Select {column}",
            values,
            key=f"model_comparison_{column}",
        )

        data = data[
            data[column].astype(str) == selected
        ].copy()

    if data.empty:
        st.info("No results match the selected conditions.")
        return

    # Keep one comparable result per method run.
    if data["method_run_id"].duplicated().any():
        st.warning(
            "Multiple score rows exist for the same method run. "
            "Please provide one comparable evaluation row per run."
        )
        st.dataframe(data, use_container_width=True)
        return

    # Check that evaluation population sizes are consistent.
    population_columns = [
        "n_compared_cases",
        "n_compared_hours",
        "n_complete_cases",
    ]

    for column in population_columns:
        if column in data.columns:
            values = pd.to_numeric(
                data[column], errors="coerce"
            )

            if values.isna().any() or values.nunique() != 1:
                st.error(
                    f"Inconsistent {column} values across models. "
                    "The models cannot be compared reliably."
                )
                st.dataframe(data, use_container_width=True)
                return

            st.caption(
                f"{column.replace('_', ' ').capitalize()}: "
                f"{int(values.iloc[0])}"
            )

    # Display coverage information when supplied by Team 4.
    if "coverage_24h" in data.columns:
        st.caption("24-hour coverage information is available.")

    if len(data) < 2:
        st.warning(
            "At least two forecasting methods are required "
            "for a model comparison."
        )
        st.dataframe(data, use_container_width=True)
        return

    # Compare macro MAE across the selected models.
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

    # Identify the lowest MAE only within the selected comparable group.
    best = data.loc[data["mae_macro"].idxmin()]

    st.success(
        f"Lowest macro MAE in this comparable selection: "
        f"{best['method_run_id']} ({best['mae_macro']:.2f})"
    )

"""Chronologie des mesures et des trous dans les comptages E1."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.app.v1_service import LOCAL_TZ

MEASURED = "Mesure exploitable"
FILLED = "Trou comblé par E1"
MISSING = "Trou non comblé"
CORRECTED = "Mesure corrigée par E1"
EXCLUDED = "Mesure écartée"


def hourly_window(history: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Rétablir les heures absentes du CSV sur une grille UTC jusqu’à la coupure."""
    hours = pd.date_range(start, end, freq="h", inclusive="left", name="timestamp")
    return history.loc[history["interval_end"].le(end)].set_index("timestamp").reindex(hours)


def hourly_status(window: pd.DataFrame) -> pd.Series:
    """Distinguer absence de mesure, imputation et correction d'une valeur publiée."""
    raw, processed = window["count_raw"], window["count"]
    observed = window["is_observed"].eq(True)
    valid_raw = raw.ge(0) & np.isfinite(raw)
    valid_processed = processed.ge(0) & np.isfinite(processed)
    measured = observed & window["is_scoreable"].eq(True) & valid_raw
    corrected = observed & ~measured & valid_processed & (~valid_raw | processed.ne(raw))

    status = pd.Series(MISSING, index=window.index, name="status")
    status.loc[~observed & valid_processed] = FILLED
    status.loc[observed] = EXCLUDED
    status.loc[corrected] = CORRECTED
    status.loc[measured] = MEASURED
    return status


def availability_plot(window: pd.DataFrame, status: pd.Series) -> go.Figure:
    """Afficher les comptages et placer les heures sans valeur sous la courbe."""
    hours = window.index
    local_labels = hours.tz_convert(LOCAL_TZ).strftime("%d/%m/%Y à %H:%M (UTC%z)")
    missing = status.eq(MISSING)
    has_missing = missing.any()
    rows = 2 if has_missing else 1
    figure = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.9, 0.1] if has_missing else None,
    )
    measured = window["count_raw"].where(status.eq(MEASURED))
    figure.add_scatter(
        x=hours,
        y=measured,
        mode="lines+markers",
        name="Mesures",
        line={"color": "#2563eb", "width": 2},
        marker={"size": 4},
        fill="tozeroy",
        fillcolor="rgba(37,99,235,0.08)",
        connectgaps=False,
        text=local_labels,
        hovertemplate="%{text}<br>%{y:.0f} vélos<extra>Mesure</extra>",
        showlegend=bool(measured.notna().any()),
        row=1,
        col=1,
    )
    estimated = status.isin((FILLED, CORRECTED))
    if estimated.any():
        figure.add_scatter(
            x=hours[estimated],
            y=window.loc[estimated, "count"],
            mode="markers",
            name="Estimations E1",
            marker={"color": "#b45309", "size": 8, "symbol": "diamond"},
            text=local_labels[estimated] + " · " + status.loc[estimated].to_numpy(),
            hovertemplate="%{text}<br>%{y:.0f} vélos estimés<extra></extra>",
            row=1,
            col=1,
        )
    raw = window["count_raw"]
    excluded = status.eq(EXCLUDED) & raw.ge(0) & np.isfinite(raw)
    if excluded.any():
        figure.add_scatter(
            x=hours[excluded],
            y=raw.loc[excluded],
            mode="markers",
            name="Mesures écartées",
            marker={"color": "#64748b", "size": 8, "symbol": "circle-open"},
            text=local_labels[excluded],
            hovertemplate="%{text}<br>%{y:.0f} vélos signalés<extra>Mesure écartée</extra>",
            row=1,
            col=1,
        )
    if has_missing:
        figure.add_scatter(
            x=hours[missing],
            y=[0.5] * int(missing.sum()),
            mode="markers",
            name="Heures sans valeur",
            marker={"color": "#be3459", "size": 7, "symbol": "x"},
            text=local_labels[missing],
            hovertemplate="%{text}<extra>Heure sans valeur</extra>",
            row=2,
            col=1,
        )
        figure.update_yaxes(
            range=[0, 1],
            tickvals=[0.5],
            ticktext=["Sans valeur"],
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            row=2,
            col=1,
        )
    figure.update_layout(
        height=430,
        margin={"l": 10, "r": 14, "t": 62, "b": 12},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.04},
        hovermode="closest",
    )
    figure.update_xaxes(
        type="date",
        gridcolor="rgba(100,116,139,0.14)",
        nticks=10,
        tickformatstops=[
            {"dtickrange": [None, 86_400_000], "value": "%H:%M<br>%d/%m"},
            {"dtickrange": [86_400_000, None], "value": "%d/%m"},
        ],
        range=[hours[0] - pd.Timedelta(minutes=30), hours[-1] + pd.Timedelta(minutes=30)],
    )
    figure.update_xaxes(title_text="Date et heure (UTC)", row=rows, col=1)
    figure.update_yaxes(
        title_text="Vélos / heure",
        rangemode="tozero",
        gridcolor="rgba(100,116,139,0.16)",
        fixedrange=True,
        row=1,
        col=1,
    )
    return figure


def show_coverage(window: pd.DataFrame) -> None:
    if window.empty:
        st.info("Aucune heure dans la période sélectionnée.")
        return
    status = hourly_status(window)
    st.plotly_chart(
        availability_plot(window, status), config={"displaylogo": False, "scrollZoom": False}
    )
    st.caption("Survolez un point pour lire l’heure de Paris et le statut du comptage.")
    counts = status.value_counts()
    measured, missing, filled = st.columns(3)
    measured.metric("Heures mesurées exploitables", f"{counts.get(MEASURED, 0)} / {len(status)}")
    missing.metric("Trous non comblés", int(counts.get(MISSING, 0)))
    filled.metric("Trous comblés par E1", int(counts.get(FILLED, 0)))

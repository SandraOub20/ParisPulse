"""Visualiser les prévisions du modèle sur les 24 heures cibles."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.app.service import LOCAL_TZ, Study, method_label
from src.models.schemas import HORIZON_HOURS


def model_forecast_plot(
    studies: tuple[Study, ...],
    observations: pd.DataFrame | None = None,
) -> go.Figure:
    origin = studies[0].case.origin
    end = origin + pd.Timedelta(hours=HORIZON_HOURS)
    figure = go.Figure()

    for index, study in enumerate(studies):
        forecast = study.forecast
        name = method_label(study)
        color = "#087f73" if index == 0 else "#93610f"
        figure.add_scatter(
            x=forecast["target_timestamp"],
            y=forecast["y_pred"],
            mode="lines+markers",
            line={"color": color, "width": 2.5, "dash": "dash" if index else "solid"},
            marker={"size": 5},
            name=name,
            connectgaps=False,
            text=paris_hover(forecast["target_timestamp"]),
            hovertemplate=f"%{{text}}<br>%{{y:.1f}} vélos<extra>{name}</extra>",
        )
        fallback = forecast.loc[forecast["prediction_status"].eq("fallback")]
        if not fallback.empty:
            figure.add_scatter(
                x=fallback["target_timestamp"],
                y=fallback["y_pred"],
                mode="markers",
                marker={"color": color, "size": 8, "symbol": "diamond-open"},
                name=f"Repli · méthode {index + 1}" if len(studies) > 1 else "Heure avec repli",
                text=paris_hover(fallback["target_timestamp"]),
                hovertemplate="%{text}<br>%{y:.1f} vélos<extra>Repli</extra>",
            )
    if observations is not None:
        figure.add_scatter(
            x=observations["target_timestamp"],
            y=observations["y_true"],
            name="Mesures réelles",
            mode="lines+markers",
            line={"color": "#8147a4", "width": 2, "dash": "dot"},
            marker={"size": 5},
            connectgaps=False,
            text=paris_hover(observations["target_timestamp"]),
            hovertemplate="%{text}<br>%{y:.0f} vélos<extra>Mesure réelle</extra>",
        )

    ticks = pd.date_range(origin, end, freq="4h")
    figure.update_layout(
        height=375,
        margin={"l": 8, "r": 12, "t": 70, "b": 12},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.06},
        hovermode="closest",
        xaxis={
            "type": "date",
            "range": [origin, end],
            "tickvals": ticks,
            "ticktext": ticks.tz_convert(LOCAL_TZ).strftime("%d/%m<br>%H:%M"),
            "title": "Heure de Paris",
            "gridcolor": "rgba(100,116,139,0.14)",
        },
        yaxis={"title": "Vélos / heure", "rangemode": "tozero"},
    )
    return figure


def paris_hover(values: pd.DatetimeIndex | pd.Series) -> pd.Index:
    return pd.DatetimeIndex(values).tz_convert(LOCAL_TZ).strftime("%d/%m/%Y à %H:%M (UTC%z)")

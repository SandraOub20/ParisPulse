
"""Visualiser les prévisions du modèle sur les 24 heures cibles."""

from __future__ import annotations

import numpy as np
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
    status_windows: set[tuple[pd.Timestamp, str]] = set()

    status_labels = {
        "ok": "Disponible",
        "fallback": "Repli",
        "unavailable": "Indisponible",
        "error": "Erreur",
    }

    for index, study in enumerate(studies):
        forecast = study.forecast.copy()
        name = method_label(study)
        color = "#087f73" if index == 0 else "#93610f"

        if "prediction_status" in forecast.columns:
            status = (
                forecast["prediction_status"]
                .astype("string")
                .str.strip()
                .str.lower()
                .fillna("error")
            )
        else:
            status = pd.Series("ok", index=forecast.index, dtype="string")

        if "status_reason" in forecast.columns:
            reasons = (
                forecast["status_reason"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
        else:
            reasons = pd.Series("", index=forecast.index, dtype="string")

        if "method_used" in forecast.columns:
            effective_methods = (
                forecast["method_used"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
        else:
            effective_methods = pd.Series(
                name,
                index=forecast.index,
                dtype="string",
            )

        numeric_predictions = pd.to_numeric(
            forecast["y_pred"],
            errors="coerce",
        )
        valid_numeric = (
            numeric_predictions.notna()
            & np.isfinite(numeric_predictions)
            & numeric_predictions.ge(0)
        )
        valid_status = status.isin(["ok", "fallback"])
        display_predictions = numeric_predictions.where(
            valid_numeric & valid_status
        )

        hover_details = []
        for timestamp, status_value, reason, effective_method in zip(
            paris_hover(forecast["target_timestamp"]),
            status,
            reasons,
            effective_methods,
            strict=True,
        ):
            status_text = status_labels.get(
                str(status_value),
                str(status_value),
            )
            reason_text = reason if reason else "Aucune raison précisée"
            method_text = (
                effective_method if effective_method else name
            )
            hover_details.append(
                f"{timestamp}<br>Statut : {status_text}"
                f"<br>Méthode effective : {method_text}"
                f"<br>Raison : {reason_text}"
            )

        forecast["_status"] = status
        forecast["_numeric_prediction"] = numeric_predictions
        forecast["_hover_detail"] = hover_details

        figure.add_scatter(
            x=forecast["target_timestamp"],
            y=display_predictions,
            mode="lines+markers",
            line={
                "color": color,
                "width": 2.5,
                "dash": "dash" if index else "solid",
            },
            marker={"size": 5},
            name=name,
            connectgaps=False,
            text=forecast["_hover_detail"],
            hovertemplate=(
                "%{text}<br>Vélos prévus : %{y:.1f}"
                f"<extra>{name}</extra>"
            ),
        )

        fallback = forecast.loc[
            forecast["_status"].eq("fallback")
            & valid_numeric
        ]
        if not fallback.empty:
            figure.add_scatter(
                x=fallback["target_timestamp"],
                y=fallback["_numeric_prediction"],
                mode="markers",
                marker={
                    "color": "#d97706",
                    "size": 9,
                    "symbol": "diamond",
                },
                name=(
                    f"Repli · {name}"
                    if len(studies) > 1
                    else "Heure avec repli"
                ),
                text=fallback["_hover_detail"],
                hovertemplate=(
                    "%{text}<br>Vélos prévus : %{y:.1f}"
                    "<extra>Prévision de repli</extra>"
                ),
            )

        for status_value, marker_color, marker_symbol, legend_name in [
            (
                "unavailable",
                "#64748b",
                "x",
                "Indisponible · sans valeur",
            ),
            (
                "error",
                "#dc2626",
                "triangle-down",
                "Erreur · sans valeur",
            ),
        ]:
            unavailable_rows = forecast.loc[
                forecast["_status"].eq(status_value)
            ]
            if unavailable_rows.empty:
                continue

            figure.add_scatter(
                x=unavailable_rows["target_timestamp"],
                y=[0.96 - index * 0.06] * len(unavailable_rows),
                yaxis="y2",
                mode="markers",
                marker={
                    "color": marker_color,
                    "size": 10,
                    "symbol": marker_symbol,
                    "line": {
                        "width": 1.5,
                        "color": marker_color,
                    },
                },
                name=(
                    f"{legend_name} · {name}"
                    if len(studies) > 1
                    else legend_name
                ),
                text=unavailable_rows["_hover_detail"],
                hovertemplate=(
                    "%{text}<br>Aucune valeur prédite : ce repère indique"
                    " uniquement le statut, pas 0 vélo.<extra></extra>"
                ),
            )

            for timestamp in unavailable_rows["target_timestamp"]:
                window = (pd.Timestamp(timestamp), status_value)
                if window in status_windows:
                    continue
                status_windows.add(window)
                shade = (
                    "rgba(100,116,139,0.12)"
                    if status_value == "unavailable"
                    else "rgba(220,38,38,0.12)"
                )
                figure.add_vrect(
                    x0=pd.Timestamp(timestamp)
                    - pd.Timedelta(minutes=30),
                    x1=pd.Timestamp(timestamp)
                    + pd.Timedelta(minutes=30),
                    fillcolor=shade,
                    line_width=0,
                    layer="below",
                )

    if observations is not None:
        figure.add_scatter(
            x=observations["target_timestamp"],
            y=observations["y_true"],
            name="Mesures réelles",
            mode="lines+markers",
            line={
                "color": "#8147a4",
                "width": 2,
                "dash": "dot",
            },
            marker={"size": 5},
            connectgaps=False,
            text=paris_hover(observations["target_timestamp"]),
            hovertemplate=(
                "%{text}<br>%{y:.0f} vélos"
                "<extra>Mesure réelle</extra>"
            ),
        )

    ticks = pd.date_range(origin, end, freq="4h")
    figure.update_layout(
        height=375,
        margin={"l": 8, "r": 12, "t": 70, "b": 12},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.06,
        },
        hovermode="closest",
        xaxis={
            "type": "date",
            "range": [origin, end],
            "tickvals": ticks,
            "ticktext": ticks.tz_convert(LOCAL_TZ).strftime(
                "%d/%m<br>%H:%M"
            ),
            "title": "Heure de Paris",
            "gridcolor": "rgba(100,116,139,0.14)",
        },
        yaxis={
            "title": "Vélos / heure",
            "rangemode": "tozero",
        },
        yaxis2={
            "overlaying": "y",
            "side": "right",
            "range": [0, 1],
            "visible": False,
            "showgrid": False,
            "zeroline": False,
            "fixedrange": True,
        },
    )
    return figure



def paris_hover(
    values: pd.DatetimeIndex | pd.Series,
) -> pd.Index:
    return pd.DatetimeIndex(values).tz_convert(LOCAL_TZ).strftime(
        "%d/%m/%Y à %H:%M (UTC%z)"
    )

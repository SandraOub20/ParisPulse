"""Visualiser les prévisions du modèle sur les 24 heures cibles."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.app.service import LOCAL_TZ, Study, method_label
from src.models.schemas import HORIZON_HOURS

# Libellés des statuts retournés par les modèles.
PREDICTION_LABELS = {
    "ok": "Disponible",
    "fallback": "Avec repli",
    "unavailable": "Indisponible",
    "error": "Erreur",
}


# Traduction des causes connues.
STATUS_REASONS = {
    "lag168_missing": "Mesure de la semaine précédente manquante",
    "lag168_missing;no_fallback_history": ("Aucune mesure historique à cette heure"),
    "profile_weeks_missing": ("Mesures de référence manquantes sur quatre semaines"),
    "profile_weeks_missing;no_fallback_history": ("Aucune mesure historique à cette heure"),
    "hgb_origin_before_fit_cutoff": ("Date antérieure à la fin de l’apprentissage du HGB"),
    "hgb_origin_not_midnight": ("Le HGB prévoit uniquement à partir de minuit"),
    "hgb_context_missing": ("Contexte E1 indisponible"),
    "hgb_context_incompatible": ("Version du contexte différente de l’apprentissage"),
    "hgb_snapshot_incompatible": ("Instantané différent de celui de l’apprentissage"),
    "hgb_site_not_in_training": ("Site absent de l’apprentissage du HGB"),
    "hgb_no_history": ("Aucune mesure publiée pour ce compteur"),
    "hgb_non_finite_output": ("Sortie du HGB inexploitable"),
}


def forecast_hover(forecast: pd.DataFrame) -> pd.DataFrame:
    """Préparer les informations affichées au survol."""

    status = forecast["prediction_status"]

    labels = status.map(PREDICTION_LABELS).fillna(status)

    methods = forecast["method_used"].fillna("").replace("", "Non renseignée")

    reasons = (
        forecast["status_reason"].replace(STATUS_REASONS).fillna("").replace("", "Non renseignée")
    )

    return pd.DataFrame(
        {
            "heure": paris_hover(forecast["target_timestamp"]),
            "statut": labels.to_numpy(),
            "methode": methods.to_numpy(),
            "raison": reasons.to_numpy(),
        }
    )


def model_forecast_plot(
    studies: tuple[Study, ...],
    observations: pd.DataFrame | None = None,
) -> go.Figure:

    origin = studies[0].case.origin
    end = origin + pd.Timedelta(hours=HORIZON_HOURS)

    # Détecter les heures sans prévision exploitable.
    has_unavailable = any(
        (
            ~study.forecast["prediction_status"].isin(("ok", "fallback"))
            | study.forecast["y_pred"].isna()
        ).any()
        for study in studies
    )

    # Ajouter une bande séparée uniquement en cas
    # de prévisions indisponibles.
    rows = 2 if has_unavailable else 1

    figure = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.82, 0.18] if has_unavailable else [1],
    )

    hover_template = (
        "%{customdata[0]}"
        "<br>Prévision : %{y:.1f} vélos"
        "<br>Statut : %{customdata[1]}"
        "<br>Méthode effective : %{customdata[2]}"
        "<br>Raison : %{customdata[3]}"
        "<extra>%{fullData.name}</extra>"
    )

    for index, study in enumerate(studies):
        forecast = study.forecast.copy()
        name = method_label(study)
        color = "#087f73" if index == 0 else "#2563eb"

        valid = forecast["prediction_status"].isin(("ok", "fallback")) & forecast["y_pred"].notna()

        # Les valeurs indisponibles restent absentes :
        # elles ne sont jamais remplacées par zéro.
        figure.add_scatter(
            x=forecast["target_timestamp"],
            y=forecast["y_pred"].where(valid),
            mode="lines+markers",
            line={
                "color": color,
                "width": 2.5,
                "dash": "dash" if index else "solid",
            },
            marker={"size": 5},
            name=name,
            connectgaps=False,
            customdata=forecast_hover(forecast).to_numpy(),
            hovertemplate=hover_template,
            row=1,
            col=1,
        )

        # Signaler les heures calculées avec une méthode de repli.
        fallback = forecast.loc[forecast["prediction_status"].eq("fallback") & valid]

        if not fallback.empty:
            figure.add_scatter(
                x=fallback["target_timestamp"],
                y=fallback["y_pred"],
                mode="markers",
                marker={
                    "color": "#d97706",
                    "size": 10,
                    "symbol": "diamond",
                    "line": {"color": color, "width": 1.5},
                },
                name=f"Heures avec repli · {name}" if len(studies) > 1 else "Heures avec repli",
                customdata=forecast_hover(fallback).to_numpy(),
                hovertemplate=hover_template,
                row=1,
                col=1,
            )

        # Afficher les heures indisponibles dans une zone distincte.
        unavailable = forecast.loc[~valid]

        if not unavailable.empty:
            figure.add_scatter(
                x=unavailable["target_timestamp"],
                y=[index + 1] * len(unavailable),
                mode="markers",
                marker={
                    "color": "#dc2626",
                    "size": 10,
                    "symbol": "x",
                },
                name=f"Heures indisponibles · {name}"
                if len(studies) > 1
                else "Heures indisponibles",
                customdata=forecast_hover(unavailable).to_numpy(),
                hovertemplate=(
                    "%{customdata[0]}"
                    "<br>Prévision : indisponible"
                    "<br>Statut : %{customdata[1]}"
                    "<br>Méthode effective : %{customdata[2]}"
                    "<br>Raison : %{customdata[3]}"
                    "<extra>%{fullData.name}</extra>"
                ),
                row=2,
                col=1,
            )

    # Conserver l'affichage automatique des mesures réelles.
    if observations is not None:
        actual = observations["y_true"]

        if "is_scoreable" in observations.columns:
            actual = actual.where(observations["is_scoreable"].eq(True))

        figure.add_scatter(
            x=observations["target_timestamp"],
            y=actual,
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
            hovertemplate=("%{text}<br>%{y:.0f} vélos<extra>Mesure réelle</extra>"),
            row=1,
            col=1,
        )

    ticks = pd.date_range(origin, end, freq="4h")

    figure.update_layout(
        height=470 if has_unavailable else 375,
        margin={"l": 8, "r": 12, "t": 80, "b": 12},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.06,
        },
        hovermode="closest",
    )

    figure.update_xaxes(
        type="date",
        range=[origin, end],
        tickvals=ticks,
        ticktext=ticks.tz_convert(LOCAL_TZ).strftime("%d/%m<br>%H:%M"),
        gridcolor="rgba(100,116,139,0.14)",
    )

    figure.update_xaxes(
        title_text="Heure de Paris",
        row=rows,
        col=1,
    )

    figure.update_yaxes(
        title_text="Vélos / heure",
        rangemode="tozero",
        row=1,
        col=1,
    )

    if has_unavailable:
        figure.update_yaxes(
            range=[0.5, len(studies) + 0.5],
            tickvals=list(range(1, len(studies) + 1)),
            ticktext=[f"Méthode {i + 1}" for i in range(len(studies))],
            title_text="Indisponible",
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            row=2,
            col=1,
        )

    return figure


def paris_hover(values: pd.DatetimeIndex | pd.Series) -> pd.Index:
    return pd.DatetimeIndex(values).tz_convert(LOCAL_TZ).strftime("%d/%m/%Y à %H:%M (UTC%z)")

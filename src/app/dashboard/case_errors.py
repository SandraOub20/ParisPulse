"""Visualisation des erreurs horaires sur le cas étudié."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.app.service import LOCAL_TZ, Study, method_label


def show_case_errors(
    studies: tuple[Study, ...],
    evaluations: tuple[dict, ...] | None,
) -> None:
    """Afficher les erreurs déjà calculées par le service."""

    st.subheader("Erreurs horaires de prévision")

    if evaluations is None:
        st.info("Aucune évaluation disponible pour ce cas.")
        return

    figure = go.Figure()
    colors = ("#087f73", "#2563eb")
    has_errors = False

    for index, (study, evaluation) in enumerate(zip(studies, evaluations, strict=True)):
        errors = evaluation["errors"].copy()

        # Conserver uniquement les heures évaluables.
        valid = errors["is_scoreable"].eq(True) & errors["signed_error"].notna()

        if valid.any():
            has_errors = True

        # Ne jamais remplacer une erreur indisponible par zéro.
        signed = errors["signed_error"].where(valid)

        labels = (
            pd.DatetimeIndex(errors["target_timestamp"])
            .tz_convert(LOCAL_TZ)
            .strftime("%d/%m/%Y à %H:%M (UTC%z)")
        )

        customdata = pd.DataFrame(
            {
                "heure": labels,
                "prediction": errors["y_pred"].to_numpy(),
                "observation": errors["y_true"].to_numpy(),
                "absolute_error": errors["absolute_error"].to_numpy(),
            }
        ).to_numpy()

        figure.add_bar(
            x=errors["target_timestamp"],
            y=signed,
            name=method_label(study),
            marker_color=colors[index % len(colors)],
            customdata=customdata,
            hovertemplate=(
                "%{customdata[0]}"
                "<br>Prévision : %{customdata[1]:.1f}"
                "<br>Observation : %{customdata[2]:.0f}"
                "<br>Erreur signée : %{y:.1f}"
                "<br>Erreur absolue : %{customdata[3]:.1f}"
                "<extra>%{fullData.name}</extra>"
            ),
        )

    if not has_errors:
        st.info("Aucune heure ne possède à la fois une prévision et une observation exploitables.")
        return

    origin = studies[0].case.origin
    end = origin + pd.Timedelta(hours=24)
    ticks = pd.date_range(origin, end, freq="4h")

    figure.add_hline(
        y=0,
        line_dash="dash",
        line_color="#64748b",
    )

    figure.update_layout(
        barmode="group",
        height=330,
        margin={"l": 8, "r": 12, "t": 65, "b": 12},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.06,
        },
        xaxis={
            "type": "date",
            "range": [
                origin - pd.Timedelta(minutes=30),
                end,
            ],
            "tickvals": ticks,
            "ticktext": ticks.tz_convert(LOCAL_TZ).strftime("%d/%m<br>%H:%M"),
            "title": "Heure de Paris",
        },
        yaxis={
            "title": "Erreur (vélos/h)",
        },
        hovermode="closest",
    )

    st.plotly_chart(
        figure,
        config={
            "displaylogo": False,
            "scrollZoom": False,
        },
    )

    st.caption(
        "Erreur = prévision − observation. "
        "Une valeur positive indique une surestimation, "
        "une valeur négative une sous-estimation. "
        "Les heures non évaluables ne sont pas représentées."
    )

    for study, evaluation in zip(studies, evaluations, strict=True):
        st.caption(
            f"{method_label(study)} : {evaluation['n_compared_hours']} heures évaluées sur 24."
        )

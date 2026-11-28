"""Interface officielle de ParisPulse V2."""

from __future__ import annotations

from html import escape
from importlib.util import find_spec
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src.app import evaluation_service, service, v1_service
from src.app.dashboard.case_errors import show_case_errors
from src.app.dashboard.comparison import show_official_evaluation
from src.app.dashboard.coverage import hourly_window, show_coverage
from src.app.dashboard.forecast_case import model_forecast_plot
from src.app.export import study_zip
from src.common.config import data_path
from src.eval.cases import E3_ROLES, case_csv, forecasting_team
from src.models.known.predict import default_publication_lag
from src.models.schemas import HORIZON_HOURS, Case

TEAL = "#087f73"
BLUE = "#245dbb"
AMBER = "#a45609"
SCENARIOS = ("Sites connus", "Nouveaux sites", "Tout le réseau")
# Clé du sélecteur « Périmètre » de la barre latérale, relue par l'onglet E4.
PERIMETER_KEY = "perimeter"
# Le périmètre choisit les vues E4 affichées, jamais les scores eux-mêmes.
E4_TEAMS_BY_SCENARIO = {SCENARIOS[0]: ("E2",), SCENARIOS[1]: ("E3",), SCENARIOS[2]: ("E2", "E3")}
MAP_ROUTES = {
    "known": ("E2 · Site connu", TEAL),
    "new": ("E3 · Nouveau site réservé", BLUE),
    "inventory": ("Inventaire", "#64748b"),
}
STATUS_LABELS = {
    "retained": "Retenu",
    "robustness": "Robustesse",
    "reserved_dev_new": "Réservé · validation",
    "reserved_test_new": "Réservé · test",
    "excluded": "Exclu",
}
PREDICTION_LABELS = {
    "ok": "Disponible",
    "fallback": "Avec repli",
    "unavailable": "Indisponible",
    "error": "Erreur",
}
STATUS_REASONS = {
    "lag168_missing": "Mesure de la semaine précédente manquante",
    "lag168_missing;no_fallback_history": "Aucune mesure historique à cette heure",
    "profile_weeks_missing": "Mesures de référence manquantes sur quatre semaines",
    "profile_weeks_missing;no_fallback_history": "Aucune mesure historique à cette heure",
    "hgb_origin_before_fit_cutoff": "Date antérieure à la fin de l’apprentissage du HGB",
    "hgb_origin_not_midnight": "Le HGB prévoit uniquement à partir de minuit",
    "hgb_context_missing": "Contexte E1 (calendrier, grèves, météo) indisponible",
    "hgb_context_incompatible": "Version du contexte différente de l’apprentissage",
    "hgb_snapshot_incompatible": "Instantané différent de celui de l’apprentissage",
    "hgb_site_not_in_training": "Site absent de l’apprentissage du HGB",
    "hgb_no_history": "Aucune mesure publiée pour ce compteur",
    "hgb_non_finite_output": "Sortie du HGB inexploitable",
    "mlp_origin_before_fit_cutoff": "Date antérieure à la fin de l’apprentissage du MLP",
    "mlp_origin_not_midnight": "Le MLP prévoit uniquement à partir de minuit",
    "mlp_context_missing": "Contexte E1 indisponible",
    "mlp_context_incompatible": "Version du contexte incompatible",
    "mlp_snapshot_incompatible": "Instantané différent de celui de l’apprentissage",
    "mlp_site_not_in_training": "Site absent de l’apprentissage du MLP",
    "mlp_no_history": "Aucune mesure publiée pour ce compteur",
    "mlp_window_too_sparse": "Historique insuffisamment renseigné pour le MLP",
    "mlp_level_too_low": "Niveau de fréquentation trop faible pour le MLP",
    "mlp_non_finite_output": "Sortie du MLP inexploitable",
}


def signature(path: Path) -> tuple[Path, int, int]:
    stat = path.stat() if path.is_file() else None
    return (path, stat.st_mtime_ns, stat.st_size) if stat else (path, 0, 0)


@st.cache_data(show_spinner=False, max_entries=8)
def inventory_cached(snapshot: Path, version: tuple) -> pd.DataFrame:
    return v1_service.load_inventory(snapshot)


@st.cache_data(show_spinner="Chargement des mesures du compteur…", max_entries=16)
def history_cached(snapshot: Path, counter_id: str, version: tuple) -> pd.DataFrame:
    return v1_service.load_counter_history(snapshot, counter_id)


@st.cache_data(show_spinner=False, max_entries=8)
def archive_cached(versions: tuple, snapshot_id: str) -> pd.DataFrame:
    return service.archived_forecasts(tuple(item[0] for item in versions), snapshot_id)


def e3_archives(snapshot_id: str) -> pd.DataFrame:
    try:
        versions = tuple(
            signature(file) for file in sorted(data_path("predictions").glob("*/*.pred.csv"))
        )
        return archive_cached(versions, snapshot_id)
    except (OSError, ValueError, KeyError) as error:
        st.warning(f"Archives E3 indisponibles · {error}")
        return service.archived_forecasts((), snapshot_id)


@st.cache_data(show_spinner=False, max_entries=8)
def cases_cached(version: tuple, snapshot_id: str) -> pd.DataFrame:
    path, _, _ = version
    if not path.is_file():
        return pd.DataFrame()
    table = pd.read_csv(path, dtype="string", keep_default_na=False)
    table = table.loc[table["snapshot_id"].eq(snapshot_id)]
    if table["case_id"].duplicated().any():
        raise ValueError(f"Identifiants de cas en double dans {path.parent.name}/cases.csv.")
    return table


@st.cache_data(show_spinner=False, max_entries=4)
def context_cached(version: tuple) -> pd.DataFrame:
    path, _, _ = version
    return pd.read_csv(path, dtype="string") if path.is_file() else pd.DataFrame()


E4_FILES = (
    evaluation_service.SCORES_FILE,
    evaluation_service.COVERAGE_FILE,
    evaluation_service.MANIFEST_FILE,
)


def e4_version(root: Path) -> tuple:
    """Signature des fichiers officiels E4 : toute republication invalide le cache."""
    return tuple(
        signature(evaluation_service.experiment_dir(team, root) / name)
        for team in evaluation_service.TEAMS
        for name in E4_FILES
    )


@st.cache_data(show_spinner="Chargement des évaluations officielles E4…", max_entries=4)
def official_results_cached(root: Path, version: tuple) -> evaluation_service.OfficialResults:
    return evaluation_service.load_official_results(root)


def show_e4_evaluation(scenario: str = SCENARIOS[2]) -> None:
    """Scores globaux E4, indépendants du compteur ; le périmètre choisit les vues."""
    try:
        root = data_path("evaluation") / evaluation_service.PROTOCOL_ID
        results = official_results_cached(root, e4_version(root))
    except (OSError, ValueError, KeyError) as error:
        st.error(f"Évaluations officielles E4 indisponibles · {error}")
        return
    teams = E4_TEAMS_BY_SCENARIO.get(scenario, E4_TEAMS_BY_SCENARIO[SCENARIOS[2]])
    show_official_evaluation(results, teams=teams)


def render_map(counters: pd.DataFrame, map_key: str, selection_key: str) -> None:
    points = counters.loc[counters["located"]].copy()
    if points.empty:
        st.info("Les coordonnées manquent pour cette sélection.")
        return
    positions = points[["latitude", "longitude"]].drop_duplicates()
    view = folium.Map(
        location=positions.mean().tolist(),
        zoom_start=13,
        tiles="OpenStreetMap",
        scrollWheelZoom=False,
        control_scale=True,
    )
    if len(positions) > 1:
        view.fit_bounds([positions.min().tolist(), positions.max().tolist()], padding=(24, 24))

    groups = {}
    # Superposer les directions empêche de sélectionner un marqueur. Le menu garde chaque sens.
    for coords, rows in points.groupby(["latitude", "longitude"], sort=False):
        eligible = rows.loc[rows["capability"].ne("inventory")]
        row = (eligible if not eligible.empty else rows).iloc[0]
        route, color = MAP_ROUTES[row["capability"]]
        label = service.optional_text(row["site_name"]) or str(row["counter_id"])
        label = f"{label} · {row['counter_id']} · {route}"
        tooltip = escape(label).replace("`", "&#96;").replace("$", "&#36;").replace("\\", "&#92;")
        groups[label] = (row["counter_id"], rows["counter_id"].tolist())
        folium.CircleMarker(
            coords,
            radius=5.5,
            weight=1.5,
            color=color,
            fill=True,
            fill_opacity=0.85,
            tooltip=tooltip,
        ).add_to(view)

    def choose_from_map() -> None:
        event = st.session_state.get(map_key, {})
        tooltip = event.get("last_object_clicked_tooltip")
        selected = groups.get(tooltip)
        if selected is not None:
            preferred, ids = selected
            if st.session_state.get(selection_key) not in ids:
                st.session_state[selection_key] = preferred

    st_folium(
        view,
        key=map_key,
        height=375,
        use_container_width=True,
        returned_objects=["last_object_clicked_tooltip", "last_object_clicked_count"],
        on_change=choose_from_map,
    )


def display_date(timestamp: pd.Timestamp) -> str:
    return timestamp.tz_convert(service.LOCAL_TZ).strftime("%d/%m/%Y à %H:%M")


def local_labels(timestamps: pd.Series) -> pd.Series:
    return timestamps.dt.tz_convert(service.LOCAL_TZ).dt.strftime("%d/%m %H:%M (UTC%z)")


def plot_layout(figure: go.Figure, ylabel: str, height: int) -> None:
    figure.update_layout(
        height=height,
        margin={"l": 8, "r": 12, "t": 16, "b": 8},
        yaxis={"title": ylabel, "rangemode": "tozero"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.13},
    )


def show_history(history: pd.DataFrame, case: Case, lag: int, *, key: str = "history-plot") -> None:
    if history.empty:
        st.info("Aucune mesure disponible pour ce compteur.")
        return
    cutoff = case.origin - pd.Timedelta(hours=lag)
    if case.scenario == "new_site":
        if case.support_start is None or case.support_end is None:
            st.info("Les bornes de l’historique local sont renseignées dans cases.csv (E4).")
            return
        start, end = case.support_start, min(case.support_end, cutoff)
    else:
        end = cutoff
        start = end - pd.Timedelta(days=7)
    window = hourly_window(history, start, end)
    timeline = window.index
    window["timestamp"] = timeline
    label = local_labels(window["timestamp"])
    observed = window["is_scoreable"].eq(True) & window["count_raw"].notna()
    estimated = ~observed & window["count"].notna()
    missing = ~(observed | estimated)
    figure = go.Figure()
    figure.add_scatter(
        x=timeline,
        y=window["count_raw"].where(observed),
        name="Mesures",
        mode="lines",
        line={"color": TEAL, "width": 2.2},
        customdata=label,
        hovertemplate="%{customdata} · %{y:.0f} vélos<extra></extra>",
    )
    figure.add_scatter(
        x=timeline[estimated],
        y=window.loc[estimated, "count"],
        name="Valeurs estimées (E1)",
        mode="markers",
        marker={"color": AMBER, "symbol": "diamond"},
        customdata=label[estimated],
        hovertemplate="%{customdata} · %{y:.0f} vélos<extra></extra>",
    )
    plot_layout(figure, "Vélos / heure", 295)
    figure.update_xaxes(showticklabels=False, title="Survoler pour lire l’heure de Paris")
    st.plotly_chart(figure, config={"displaylogo": False}, key=key)
    st.caption(
        f"Du {display_date(start)} au {display_date(end)} (Paris) · "
        f"{observed.sum()} heures mesurées · {estimated.sum()} estimées · "
        f"{missing.sum()} sans valeur"
    )


def show_missing_history(
    history: pd.DataFrame, case: Case | None, lag: int, widget_key: str
) -> None:
    st.subheader("Comptages et heures manquantes")
    if history.empty:
        st.info("Aucun comptage enregistré pour ce compteur.")
        return
    if case is not None and case.scenario == "new_site":
        if case.support_start is None or case.support_end is None:
            st.info("Les bornes de l’historique local sont renseignées dans cases.csv (E4).")
            return
        start = case.support_start
        end = min(case.support_end, case.origin - pd.Timedelta(hours=lag))
    else:
        end = (
            case.origin - pd.Timedelta(hours=lag)
            if case is not None
            else history["interval_end"].max()
        )
        days = st.selectbox(
            "Période à examiner",
            (7, 30, 90),
            index=1,
            format_func=lambda value: f"{value} derniers jours",
            key=f"coverage-period-{widget_key}",
        )
        start = max(history["timestamp"].min(), end - pd.Timedelta(days=days))
    st.caption(f"Du {display_date(start)} au {display_date(end)} (heure de Paris)")
    show_coverage(hourly_window(history, start, end))


def show_context(snapshot: Path, case: Case) -> None:
    try:
        context = service.context_for_case(
            context_cached(signature(snapshot / "context.csv")), case
        )
    except (OSError, ValueError, KeyError) as error:
        st.warning(f"Contexte indisponible · {error}")
        return
    if context.empty:
        st.info("Aucune donnée de contexte disponible à l’origine sur ces 24 heures.")
        return
    st.caption("Calendrier et météo connus au départ, affichés à titre de contexte.")
    calendar = context.loc[context["role"].eq("known_calendar")].sort_values("local_date")
    if not calendar.empty:
        display = calendar[["local_date", "variable", "value", "label"]].copy()
        display["variable"] = display["variable"].map(service.CONTEXT_LABELS)
        display["value"] = display["value"].replace({"true": "Oui", "false": "Non"})
        display = display.rename(
            columns={
                "local_date": "Date",
                "variable": "Événement",
                "value": "État",
                "label": "Détail",
            }
        )
        st.dataframe(display, hide_index=True)
    weather = context.loc[context["role"].eq("forecast_bulletin")].copy()
    if not weather.empty:
        weather["Heure de Paris"] = local_labels(
            pd.to_datetime(weather["valid_time"], format="ISO8601", utc=True)
            - pd.Timedelta(hours=1)
        )
        weather["variable"] = weather["variable"].map(service.CONTEXT_LABELS)
        weather["value"] = pd.to_numeric(weather["value"], errors="coerce")
        st.dataframe(
            weather.pivot_table(index="Heure de Paris", columns="variable", values="value")
            .reset_index()
            .rename_axis(None, axis=1),
            hide_index=True,
        )


def time_for_study(study: service.Study) -> float | None:
    if study.runs.empty:
        return None
    seconds = pd.to_numeric(
        study.runs.iloc[0][
            ["preparation_seconds", "inference_seconds", "adaptation_seconds", "wait_seconds"]
        ],
        errors="coerce",
    ).sum(min_count=1)
    return float(seconds) if pd.notna(seconds) else None


def show_study(studies: tuple[service.Study, ...], evaluations: tuple[dict, ...] | None) -> None:
    study = studies[0]
    case = study.case
    forecast = study.forecast
    n_valid = int(forecast["prediction_status"].isin(service.VALID_STATUSES).sum())
    n_fallback = int(forecast["prediction_status"].eq("fallback").sum())
    evaluation = evaluations[0] if evaluations is not None else None
    mae = evaluation["mae"] if evaluation is not None else None
    score = f"{mae:.1f} vélos/h" if mae is not None else "Indisponible"
    elapsed = time_for_study(study)
    metrics = st.columns(4)
    metrics[0].metric("Heures prédites", f"{n_valid} / {HORIZON_HOURS}", border=True)
    metrics[1].metric("Heures avec repli", n_fallback, border=True)
    metrics[2].metric("MAE sur ce cas (indicatif)", score, border=True)
    metrics[3].metric(
        "Temps de calcul", f"{elapsed:.3f} s" if elapsed is not None else "—", border=True
    )
    if forecast["variant"].iloc[0] == service.HGB:
        refused = forecast.loc[~forecast["method_used"].eq(service.HGB), "status_reason"].dropna()
        if not refused.empty:
            reason = STATUS_REASONS.get(refused.iloc[0], refused.iloc[0])
            st.warning(
                f"Le HGB n’a pas prévu ce cas : {reason}. "
                "Les valeurs affichées viennent de la référence hebdomadaire."
            )

    if forecast["variant"].iloc[0] == "mlp" and case.scenario == "known_site":
        refused = forecast.loc[
            ~forecast["method_used"].eq("mlp"),
            "status_reason",
        ].dropna()

        if not refused.empty:
            reason = STATUS_REASONS.get(refused.iloc[0], refused.iloc[0])

            st.warning(
                f"Le MLP sélectionné n’a pas prévu ce cas : {reason}. "
                "Les valeurs disponibles proviennent de la référence hebdomadaire."
            )

    adapted_run_id = service.ADAPTATION_PAIR[1]
    if case.spatial_role == "S_dev_new" and any(
        str(item.forecast["method_run_id"].iloc[0]).startswith(adapted_run_id) for item in studies
    ):
        st.info(
            "Les paramètres de l’adaptation de Chronos-2 ont été choisis "
            "sur les données de validation, sans réentraîner le modèle. "
            "Ses performances doivent être confirmées sur des données de test indépendantes."
        )
    if n_valid != HORIZON_HOURS:
        st.warning(
            "La prévision est incomplète. Le tableau horaire détaille les heures et les raisons."
        )
    if evaluation is not None:
        st.caption(
            f"Score indicatif sur ce cas · {evaluation['n_compared_hours']} heures comparées sur 24."
        )

    st.subheader("Prévisions du modèle" if len(studies) == 1 else "Prévisions des modèles")
    observations = evaluation["observations"] if evaluation is not None else None
    if observations is not None and not observations["is_scoreable"].any():
        observations = None
        st.caption("Aucune mesure exploitable sur ces 24 heures.")
    st.plotly_chart(
        model_forecast_plot(studies, observations),
        config={"displaylogo": False, "scrollZoom": False},
    )
    if len(studies) > 1:
        show_comparison(studies, evaluations)
    show_case_errors(studies, evaluations)
    with st.expander("Les 24 valeurs horaires et leur provenance", expanded=True):
        details = pd.DataFrame(
            {
                "Horizon": forecast["horizon"],
                "Heure de Paris": local_labels(forecast["target_timestamp"]),
                "Vélos prévus": forecast["y_pred"].round(1),
                "Statut": forecast["prediction_status"].map(PREDICTION_LABELS),
                "Méthode effective": forecast["method_used"].fillna(""),
                "Raison": forecast["status_reason"].replace(STATUS_REASONS).fillna(""),
            }
        )
        if len(studies) > 1:
            alternative = service.method_label(studies[1])
            details[f"Vélos prévus · {alternative}"] = studies[1].forecast["y_pred"].round(1)
            details[f"Statut · {alternative}"] = (
                studies[1].forecast["prediction_status"].map(PREDICTION_LABELS)
            )
        if evaluation is not None:
            details["Vélos mesurés"] = evaluation["observations"]["y_true"]
            details["Écart absolu"] = evaluation["errors"]["absolute_error"].round(1)
        st.dataframe(details, hide_index=True, height=310)
        for item in studies:
            st.caption(f"{item.source} · {service.method_label(item)} · {item.case.protocol_id}")
    alternatives = tuple(
        (item, evaluations[index] if evaluations is not None else None)
        for index, item in enumerate(studies[1:], start=1)
    )
    st.download_button(
        "Télécharger l’étude (.zip)",
        study_zip(study, evaluation, alternatives=alternatives),
        file_name=f"parispulse-{case.case_id}.zip",
        mime="application/zip",
        on_click="ignore",
        key=f"export-{case.case_id}",
    )


def show_comparison(
    studies: tuple[service.Study, ...], evaluations: tuple[dict, ...] | None
) -> None:
    st.subheader("Comparaison des méthodes sur ce cas")
    st.caption(
        "Scores indicatifs calculés sur les 24 heures de ce seul cas. Les scores globaux "
        "des méthodes figurent dans l’onglet « Évaluation officielle E4 »."
    )
    coverage = [
        int(item.forecast["prediction_status"].isin(service.VALID_STATUSES).sum())
        for item in studies
    ]
    complete = all(hours == HORIZON_HOURS for hours in coverage)
    rows = []
    for index, (item, count) in enumerate(zip(studies, coverage, strict=True)):
        evaluation = evaluations[index] if evaluations is not None and complete else None
        rows.append(
            {
                "Méthode": service.method_label(item),
                "Provenance": item.source,
                "Heures prédites": count,
                "Replis": int(item.forecast["prediction_status"].eq("fallback").sum()),
                "Calcul (s)": time_for_study(item),
                "Heures comparées": evaluation["n_compared_hours"]
                if evaluation is not None
                else None,
                "MAE (vélos/h)": evaluation["mae"] if evaluation is not None else None,
            }
        )
    st.dataframe(rows, hide_index=True)
    if evaluations is None:
        st.caption("La comparaison des scores est indisponible pour ce cas.")
    elif not complete:
        st.caption("La comparaison des scores exige 24 prévisions pour chaque méthode.")
    else:
        st.caption("Les deux scores utilisent les mêmes heures réellement mesurées.")


def protocol_cases(snapshot_id: str, counter: pd.Series, scenario: str) -> pd.DataFrame:
    tables = []
    try:
        paths = sorted(data_path("evaluation").glob("*/cases.csv"))
    except KeyError as error:
        st.warning(f"Cas E4 indisponibles · {error}")
        return pd.DataFrame()
    for path in paths:
        try:
            table = cases_cached(signature(path), snapshot_id)
            if table.empty:
                continue
            rows = table.loc[
                table["counter_id"].eq(counter["counter_id"]) & table["scenario"].eq(scenario)
            ]
            if not rows["spatial_role"].eq(service.counter_role(counter)).all():
                raise ValueError("Le rôle spatial des cas E4 diffère de l’inventaire.")
            tables.append(rows)
        except (OSError, ValueError, KeyError) as error:
            st.warning(f"Cas du protocole {path.parent.name} indisponibles · {error}")
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def configure_known(
    counter: pd.Series,
    history: pd.DataFrame,
    snapshot: Path,
    widget_key: str,
    lag: int,
) -> tuple:
    measured = history.loc[history["is_observed"] & history["count_raw"].notna(), "timestamp"]
    if measured.empty:
        st.info("Ce compteur ne possède pas de mesures publiées.")
        return None, None, None
    first = (measured.min() + pd.Timedelta(hours=lag + 1)).tz_convert(service.LOCAL_TZ)
    first_day = first.ceil("D").date()
    last_day = measured.max().tz_convert(service.LOCAL_TZ).date()
    if first_day > last_day:
        st.info("Historique publié trop court pour constituer un cas.")
        return None, None, None
    day = st.date_input(
        "Date de départ (minuit à Paris)",
        value=service.default_known_day(first_day, last_day),
        min_value=first_day,
        max_value=last_day,
        format="DD/MM/YYYY",
        key=f"date-{widget_key}",
    )
    methods = {
        **service.KNOWN_SITE_LABELS,
        service.COMPARE_REFERENCES: "Comparer les deux références",
    }
    method = st.selectbox(
        "Méthode",
        list(methods),
        format_func=methods.__getitem__,
        key=f"method-{widget_key}",
    )
    case = service.technical_case(counter, day, snapshot.name)
    evaluation = protocol_cases(snapshot.name, counter, "known_site")
    if evaluation.empty:
        return case, method, None
    origins = pd.to_datetime(evaluation["origin"], format="ISO8601", utc=True, errors="coerce")
    matches = evaluation.loc[origins.eq(case.origin)]
    if len(matches) > 1:
        protocols = matches["protocol_id"].unique().tolist()
        if len(protocols) != len(matches):
            st.warning("Plusieurs cas E4 correspondent à cette date. Un cas technique est utilisé.")
            return case, method, None
        protocol = st.selectbox("Protocole E4", protocols, key=f"protocol-{widget_key}")
        matches = matches.loc[matches["protocol_id"].eq(protocol)]
    if not matches.empty:
        try:
            case = Case.from_row(matches.iloc[0])
        except ValueError as error:
            st.warning(f"Cas E4 indisponible. Un cas technique est utilisé · {error}")
    return case, method, None


def configure_new(
    counter: pd.Series,
    history: pd.DataFrame,
    snapshot: Path,
    catalog: pd.DataFrame,
    widget_key: str,
    lag: int,
) -> tuple:
    counter_id = counter["counter_id"]

    try:
        budget = service.fixed_e3_budget(counter)
    except (OSError, ValueError, KeyError) as error:
        st.warning(f"Budget E3 indisponible : {error}")
        return None, None, None

    st.metric(
        "Budget d'historique local attribué",
        f"{budget} h ({budget // 24} jour(s))",
    )

    rows = catalog.loc[catalog["counter_id"].eq(counter_id)]
    evaluation = protocol_cases(snapshot.name, counter, "new_site")
    try:
        if not evaluation.empty and evaluation["case_id"].duplicated().any():
            raise ValueError("Un identifiant de cas est présent dans plusieurs protocoles.")
        by_id = {row["case_id"]: Case.from_row(row) for row in evaluation.to_dict("records")}
    except (ValueError, KeyError, TypeError) as error:
        st.warning(f"Cas du protocole E4 indisponibles · {error}")
        evaluation = pd.DataFrame()
        by_id = {}
    try:
        archived = service.archived_cases(catalog, counter, evaluation)
        for case in archived:
            by_id.setdefault(case.case_id, case)
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.warning(f"Cas des archives E3 indisponibles · {error}")

    # Ne conserver que les cas correspondant au budget fixe
    by_id = {case_id: case for case_id, case in by_id.items() if case.local_budget_hours == budget}

    use_free_date = not by_id or st.toggle(
        "Choisir une date libre",
        key=f"free-date-{widget_key}",
    )
    if not use_free_date:
        choices = {
            case.case_id: case
            for case in sorted(by_id.values(), key=lambda case: (case.origin, case.protocol_id))
            if (case.local_budget_hours or 0) == budget
        }
        case_id = st.selectbox(
            "Départ des 24 heures à prévoir",
            list(choices),
            format_func=lambda cid: (
                f"{display_date(choices[cid].origin)} · {choices[cid].protocol_id}"
            ),
            key=f"archive-date-{widget_key}-{budget}",
        )
        case = choices[case_id]
    else:
        if service.counter_role(counter) not in E3_ROLES:
            st.info("Le rôle réservé à E3 de ce compteur doit être renseigné dans l’inventaire.")
            return None, None, None
        # case = configure_new_date(counter, history, snapshot, widget_key, lag)
        case = configure_new_date(counter, history, snapshot, widget_key, lag, budget)
        if case is None:
            return None, None, None

    sources = rows.loc[rows["case_id"].eq(case.case_id), ["archive", "method_run_id"]]
    labels = {}
    can_run = case.spatial_role in E3_ROLES and bool(case.local_budget_hours)
    if can_run:
        if find_spec("chronos") is not None and find_spec("torch") is not None:
            labels[(None, service.CHRONOS_LIVE)] = "Chronos-2 gelé · calcul à la demande"
            labels[(None, service.COMPARE_CHRONOS)] = "Comparer la référence locale et Chronos-2"
            labels[(None, service.CHRONOS_ADAPTED_LIVE)] = (
                "Chronos-2 adapté v2 · calcul à la demande"
            )
            labels[(None, service.COMPARE_ADAPTATION)] = (
                "Comparer Chronos-2 avant et après adaptation"
            )
        else:
            st.caption("Chronos-2 à la demande nécessite le groupe de dépendances `dl`.")
        labels[(None, service.LOCAL_REFERENCE)] = "Référence locale E3 · calcul à la demande"
    for row in sources.dropna().drop_duplicates().itertuples(index=False):
        title = service.e3_method_label(row.method_run_id)
        labels[(row.archive, row.method_run_id)] = (
            f"{title} · archive {Path(row.archive).parent.name}"
        )
        if can_run:
            comparison = f"{service.COMPARE_ARCHIVE_PREFIX}{row.method_run_id}"
            labels[(row.archive, comparison)] = f"Comparer la référence locale à {title} (archive)"
    if set(service.ADAPTATION_PAIR) <= set(sources["method_run_id"].dropna()):
        adapted = sources.loc[sources["method_run_id"].eq(service.ADAPTATION_PAIR[1]), "archive"]
        labels[(adapted.iloc[0], service.COMPARE_ADAPTATION_ARCHIVE)] = (
            "Comparer Chronos-2 avant et après adaptation (archives)"
        )
    if not labels:
        st.info("Ce cas n’a pas de méthode disponible avec le budget renseigné.")
        return None, None, None
    file, method = st.selectbox(
        "Méthode",
        list(labels),
        key=f"new-method-{widget_key}-{case.case_id}",
        format_func=labels.__getitem__,
    )
    return case, method, Path(file) if file else None


def configure_new_date(
    counter: pd.Series,
    history: pd.DataFrame,
    snapshot: Path,
    widget_key: str,
    lag: int,
    budget: int,
) -> Case | None:
    if history.empty:
        st.info("Aucun comptage enregistré pour ce compteur.")
        return None
    measured = history.loc[history["is_observed"] & history["count_raw"].notna(), "timestamp"]
    if measured.empty:
        st.info("Ce compteur ne possède pas de mesure publiée.")
        return None
    latest = measured.max().tz_convert(service.LOCAL_TZ).date()
    first = measured.min() + pd.Timedelta(hours=lag)
    eligible = {
        budget: (first + pd.Timedelta(hours=budget + 1))
        .tz_convert(service.LOCAL_TZ)
        .ceil("D")
        .date()
    }

    if eligible[budget] > latest:
        st.info(f"Historique insuffisant pour le budget fixe de {budget} heures.")
        return None

    eligible = {budget: day for budget, day in eligible.items() if day <= latest}
    if not eligible:
        st.info("Historique trop court pour constituer un support local de 24 heures.")
        return None

    day = st.date_input(
        "Départ des 24 heures à prévoir (minuit à Paris)",
        value=eligible[budget],
        min_value=eligible[budget],
        max_value=latest,
        format="DD/MM/YYYY",
        key=f"technical-date-{widget_key}-{budget}",
    )
    st.caption("Cas libre, avec un historique limité au budget sélectionné.")
    return service.technical_new_case(counter, day, snapshot.name, budget, lag)


def main() -> None:
    st.set_page_config(page_title="ParisPulse V2", page_icon="🚲", layout="wide")
    st.html("""
        <style>
        .block-container {max-width: 86rem; padding-top: 4.15rem; padding-bottom: 3rem;}
        .parispulse-header {
            background: #103c3a; color: #fff; border-radius: 18px;
            padding: 1.45rem clamp(1.1rem, 3vw, 2.2rem);
            margin-bottom: 0.6rem; overflow: hidden;
            background-image: linear-gradient(105deg, #113936 0%, #0b5248 100%);
        }
        .parispulse-header h1 {color: #fff; margin: 0; padding: 0; line-height: 1.12;}
        .parispulse-header p {color: #d5f0eb; margin: 0.4rem 0 0;}
        .parispulse-header .edition {
            display: inline-block; margin-left: .55rem; vertical-align: middle;
            border: 1px solid #9ac9be; border-radius: 999px; color: #ebfaf7;
            padding: .19rem .5rem; font-size: .75rem; font-weight: 600;
        }
        iframe[title="streamlit_folium.st_folium"] {border-radius: 10px;}
        @media (max-width: 700px) {
            .block-container {padding-top: 4rem;}
            .parispulse-header h1 {font-size: 2rem;}
        }
        </style>
        <header class="parispulse-header">
            <h1>ParisPulse<span class="edition">V2</span></h1>
            <p>Observatoire des comptages vélo à Paris</p>
        </header>
    """)
    # Onglets toujours exécutés : l'état du compteur et de la prévision est conservé.
    explorer_tab, evaluation_tab = st.tabs(["Prévision par compteur", "Évaluation officielle E4"])
    with explorer_tab:
        show_counter_explorer()
    with evaluation_tab:
        # Le parcours compteur s'exécute avant : le périmètre choisi est déjà connu.
        # Sans instantané E1, le sélecteur n'est pas affiché : toutes les vues E4 restent.
        show_e4_evaluation(st.session_state.get(PERIMETER_KEY, SCENARIOS[2]))


def show_counter_explorer() -> None:
    """Carte, prévision sur 24 h et étude d'un cas pour le compteur sélectionné."""
    directories = sorted(
        (path.parent for path in data_path("processed").glob("*/counters.csv")), reverse=True
    )
    if not directories:
        st.warning("Installez l’instantané E1 pour afficher les compteurs de Paris.")
        st.code(
            "git lfs pull --include='livraison/hist-20261117.zip'\n"
            "unzip -n livraison/hist-20261117.zip",
            language="bash",
        )
        return
    snapshots = {directory.name: directory for directory in directories}
    snapshot_id = st.sidebar.selectbox("Instantané des données", list(snapshots))
    snapshot = snapshots[snapshot_id]
    scenario = st.sidebar.radio("Périmètre", SCENARIOS, index=2, key=PERIMETER_KEY)
    inventory_version = tuple(
        signature(snapshot / name) for name in ("counters.csv", "inventory_quality.csv")
    )
    try:
        inventory = inventory_cached(snapshot, inventory_version)
    except (OSError, ValueError, KeyError) as error:
        st.error(f"Impossible de lire l’inventaire · {error}")
        return

    inventory["site_role"] = inventory.apply(service.counter_role, axis=1)
    known = inventory["site_role"].eq("S_train")
    new = inventory["site_role"].isin(E3_ROLES)
    inventory["capability"] = "inventory"
    inventory.loc[known, "capability"] = "known"
    inventory.loc[new, "capability"] = "new"
    if scenario == SCENARIOS[0]:
        visible = inventory.loc[known]
    elif scenario == SCENARIOS[1]:
        visible = inventory.loc[new]
    else:
        visible = inventory
    st.sidebar.caption(f"{len(visible)} compteurs directionnels · {snapshot_id}")
    if visible.empty:
        st.info("Aucun compteur dans ce périmètre. Sélectionnez « Tout le réseau » dans le menu.")
        return
    counters = visible.set_index("counter_id", drop=False)
    sites = {
        cid: " · ".join(
            filter(
                None,
                (
                    service.optional_text(row["site_name"])
                    or service.optional_text(row["counter_name"]),
                    service.optional_text(row["direction"]),
                ),
            )
        )
        for cid, row in counters.iterrows()
    }
    duplicates = pd.Series(sites).duplicated(keep=False)
    labels = {
        cid: (f"{label} · {cid}" if label and duplicates[cid] else label or cid)
        for cid, label in sites.items()
    }
    order = visible.sort_values(["selection_status", "label"], ascending=[False, True])[
        "counter_id"
    ].tolist()
    retained = visible.loc[visible["selection_status"].eq("retained"), "counter_id"].tolist()
    development = visible.loc[visible["site_role"].eq("S_dev_new"), "counter_id"].tolist()
    selection_key = f"counter-{snapshot_id}-{scenario}"
    if st.session_state.get(selection_key) not in labels:
        st.session_state[selection_key] = (retained or development or order)[0]
    map_column, settings = st.columns([1.55, 1], gap="large")
    with map_column:
        with st.container(border=True):
            st.subheader("Carte des compteurs")
            render_map(visible, f"map-{snapshot_id}-{scenario}", selection_key)
            st.caption("Cliquez sur un point, puis choisissez le sens dans le menu.")
            st.caption("Turquoise · E2   |   Bleu · E3   |   Gris · inventaire")
    counts_version = signature(snapshot / "counts.csv")
    with settings:
        with st.container(border=True):
            st.subheader("Prévision sur 24 h")
            selected = st.selectbox(
                "Compteur et sens",
                order,
                key=selection_key,
                format_func=labels.__getitem__,
            )
            selection = (snapshot_id, scenario, selected)
            if st.session_state.get("selection") != selection:
                st.session_state["selection"] = selection
                st.session_state.pop("forecast-result", None)
            counter = counters.loc[selected]
            status = service.optional_text(counter["selection_status"])
            reason = service.optional_text(counter["status_reason"])
            status_text = STATUS_LABELS.get(status, status or "Statut E1 non renseigné")
            st.caption(f"Compteur {selected} · {status_text}")
            if not counts_version[1]:
                st.warning("counts.csv est absent de cet instantané. Réinstallez le fichier E1.")
                return
            try:
                history = history_cached(snapshot, selected, counts_version)
                lag = default_publication_lag()
            except (OSError, ValueError, KeyError) as error:
                st.error(f"Impossible de préparer le compteur · {error}")
                return
            widget_key = f"{snapshot_id}-{selected}"
            case = None
            catalog = None
            if counter["capability"] == "inventory":
                st.info(reason or "Ce compteur figure dans l’inventaire sans méthode disponible.")
            elif counter["capability"] == "known":
                case, method, archive = configure_known(counter, history, snapshot, widget_key, lag)
            else:
                include_archives = st.toggle(
                    "Proposer les prévisions archivées",
                    key=f"include-archives-{widget_key}",
                    help="Ajoute la lecture et la comparaison de résultats déjà calculés.",
                )
                catalog = (
                    e3_archives(snapshot_id)
                    if include_archives
                    else service.archived_forecasts((), snapshot_id)
                )
                case, method, archive = configure_new(
                    counter, history, snapshot, catalog, widget_key, lag
                )
            if case is not None:
                engine = forecasting_team(case)
                archive_version = ()
                if archive:
                    # Toutes les archives du cas : une comparaison peut en lire plusieurs.
                    files = sorted(set(catalog.loc[catalog["case_id"].eq(case.case_id), "archive"]))
                    archive_version = tuple(
                        signature(path)
                        for file in map(Path, files)
                        for path in (
                            file,
                            file.with_name(file.name.removesuffix(".pred.csv") + ".runs.csv"),
                        )
                    )
                context_version = signature(snapshot / "context.csv")
                run_key = (
                    case,
                    method,
                    archive,
                    archive_version,
                    counts_version,
                    context_version,
                    inventory_version,
                    lag,
                )
                if st.session_state.get("scope") != run_key:
                    st.session_state["scope"] = run_key
                    st.session_state.pop("forecast-result", None)
                opens_only = archive is not None and not method.startswith(
                    service.COMPARE_ARCHIVE_PREFIX
                )
                mode = (
                    "lecture d’une archive"
                    if opens_only
                    else "calcul et comparaison à une archive"
                    if archive is not None
                    else "calcul à la demande"
                )
                st.caption(f"Cas {case.protocol_id} · E4 → {engine} · {mode}")
                st.download_button(
                    "Télécharger cases.csv",
                    case_csv(case),
                    file_name="cases.csv",
                    mime="text/csv",
                    on_click="ignore",
                    help=f"Une ligne pour le cas {case.case_id}.",
                )
                action = "Ouvrir la prévision" if opens_only else "Calculer la prévision"
                if st.button(action, type="primary", width="stretch"):
                    st.session_state.pop("forecast-result", None)
                    st.session_state["study-tab"] = "Prévision"
                    try:
                        with st.spinner(
                            "Lecture de l’archive…" if opens_only else "Calcul des 24 heures…"
                        ):
                            studies = service.run_studies(
                                case, method, archive, history, catalog, lag
                            )
                    except (OSError, ValueError, KeyError, RuntimeError) as error:
                        st.error(f"Prévision indisponible · {error}")

                    else:
                        evaluations = None
                        try:
                            evaluations = tuple(service.reveal(study, history) for study in studies)
                        except (ValueError, KeyError) as error:
                            st.warning(f"Comparaison avec les mesures indisponible · {error}")
                        st.session_state["forecast-result"] = (studies, evaluations)

                if st.session_state.get("forecast-result"):
                    st.markdown("[Voir la courbe et les 24 lignes](#etude-du-cas)")

    if case is None:
        show_missing_history(history, case, lag, widget_key)
        return
    st.subheader(f"Étude du {display_date(case.origin)}", anchor="etude-du-cas")
    result = st.session_state.get("forecast-result")
    forecast_tab, history_tab, coverage_tab, context_tab = st.tabs(
        ["Prévision", "Historique disponible", "Données manquantes", "Contexte E1"],
        key="study-tab",
        on_change="rerun",
    )
    with forecast_tab:
        end = case.origin + pd.Timedelta(hours=HORIZON_HOURS)
        st.caption(
            f"Compteur {case.counter_id} · Période à prévoir du {display_date(case.origin)} "
            f"au {display_date(end)} (heure de Paris)"
        )
        if result is None:
            st.info(f"Sélectionnez « {action} » pour afficher le graphique et les 24 valeurs.")
            st.subheader("Passé disponible")
            show_history(history, case, lag, key="forecast-history-preview")
        else:
            try:
                show_study(*result)
            except (ValueError, KeyError) as error:
                st.error(f"Impossible d’afficher l’étude · {error}")
    with history_tab:
        show_history(history, case, lag)
    with coverage_tab:
        show_missing_history(history, case, lag, widget_key)
    with context_tab:
        show_context(snapshot, case)


if __name__ == "__main__":
    main()

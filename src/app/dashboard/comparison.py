"""Comparaison des méthodes de prévision à partir des évaluations officielles E4.

Deux points d'entrée :
- ``show_official_evaluation(results)`` : section globale E4, avec une vue E2 et une vue
  E3 distinctes, distincte des comparaisons locales sur un seul cas ;
- ``show_model_comparison(scores)`` : API historique, compare des lignes de scores
  quelconques respectant le contrat de ``scores.csv``.

Ce module n'effectue aucun calcul de métrique : les valeurs affichées sont celles de
``scores.csv`` et ``coverage.csv``, lues et contrôlées par ``src/app/evaluation_service``.
Une valeur absente est affichée « non disponible », jamais comme zéro.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.app import evaluation_service as ev

MISSING = "non disponible"

REQUIRED_COLUMNS = (
    "method_run_id",
    "mae_macro",
    *ev.COMPARISON_METADATA,
)
METRICS = {
    "mae_macro": ("MAE macro (vélos/h)", 2),
    "rmse": ("RMSE (vélos/h)", 2),
    "r2": ("R²", 3),
    "bias": ("Biais (vélos/h)", 2),
}
POPULATION_SIZE_COLUMNS = ("n_complete_cases", "n_compared_cases", "n_compared_hours")
POPULATION_LABELS = {
    ev.POPULATION_SELF: "self · chaque méthode sur ses propres cas",
    ev.POPULATION_COMMON: "common_complete · mêmes cas complets pour toutes les méthodes",
}
POPULATION_HELP = {
    ev.POPULATION_SELF: (
        "Chaque méthode est évaluée sur tous les cas qu'elle a prévus. Les effectifs "
        "peuvent différer d'une méthode à l'autre : la comparaison reste indicative."
    ),
    ev.POPULATION_COMMON: (
        "Seuls les cas complets pour toutes les méthodes de la population sont retenus, "
        "sur les mêmes heures mesurées : c'est la comparaison à privilégier."
    ),
}
TEAM_LABELS = {"E2": "E2 · sites connus", "E3": "E3 · nouveaux sites"}
COVERAGE_LABELS = {
    "method_run_id": "Méthode",
    "variant": "Variante",
    "n_expected_cases": "Cas attendus",
    "n_predicted_cases": "Cas prédits",
    "n_complete_cases": "Cas complets (24 h)",
    "n_fallback_complete_cases": "dont complétés par repli",
    "n_evaluable_cases": "Cas évaluables",
    "n_error_cases": "Erreurs",
    "n_partial_cases": "Partiels",
    "n_no_forecast_cases": "Sans prévision",
    "coverage_24h": "Couverture 24 h",
    "matches_scores": "Cohérent avec scores.csv",
}


# ------------------------------------------------------------ fonctions pures


def format_value(value: object, digits: int = 2, *, percent: bool = False) -> str:
    """Formater une valeur officielle ; une valeur absente n'est jamais affichée 0."""
    if value is None or value is pd.NA or (isinstance(value, float) and np.isnan(value)):
        return MISSING
    if isinstance(value, (bool, np.bool_)):
        return "oui" if value else "non"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    number = float(value)
    return f"{number:.{digits}%}" if percent else f"{number:.{digits}f}"


def prepare_scores(scores: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Contrôler un tableau de scores avant affichage.

    Les MAE absentes restent ``NaN`` et sont conservées ; les MAE invalides (texte,
    infini, négative) et les lignes sans métadonnées de comparaison sont exclues et
    comptées. Lève ``ValueError`` si une colonne obligatoire manque.
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in scores.columns]
    if missing:
        raise ValueError(f"Colonnes obligatoires manquantes : {', '.join(missing)}")
    data = scores.copy()
    if "variant" not in data.columns:
        data["variant"] = ""

    for column in ("method_run_id", "variant", *ev.COMPARISON_METADATA):
        data[column] = data[column].astype("string").str.strip()

    raw_mae = data["mae_macro"]
    absent = raw_mae.isna() | raw_mae.astype("string").str.strip().eq("")
    for column in METRICS:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").astype(float)
    mae = data["mae_macro"]
    invalid_mae = ~absent & (mae.isna() | ~np.isfinite(mae) | mae.lt(0))

    identifiers = data[["method_run_id", *ev.COMPARISON_METADATA]]
    invalid_metadata = (identifiers.isna() | identifiers.eq("")).any(axis=1) & ~invalid_mae

    data = data.loc[~invalid_mae & ~invalid_metadata].copy()
    if "population_kind" not in data.columns:
        data["population_kind"] = data["comparison_population_id"].map(_population_kind)
    counts = {
        "valid_rows": len(data),
        "invalid_mae": int(invalid_mae.sum()),
        "invalid_metadata": int(invalid_metadata.sum()),
        "missing_mae": int(data["mae_macro"].isna().sum()),
    }
    return data.reset_index(drop=True), counts


def _population_kind(population_id: str) -> str | None:
    try:
        return ev.population_kind(population_id)
    except ev.EvaluationDataError:
        return None


def comparable_population(scores: pd.DataFrame, comparison_population_id: str) -> pd.DataFrame:
    """Lignes d'une seule population, validées par E5 puis triées par MAE officielle."""
    return ev.ranked_methods(ev.select_population(scores, comparison_population_id))


def population_sizes_check(population: pd.DataFrame) -> tuple[str, str]:
    """Niveau (``info``, ``warning``, ``error``) et message sur les effectifs comparés."""
    kind = population["population_kind"].iloc[0] if "population_kind" in population else None
    differing = []
    for column in POPULATION_SIZE_COLUMNS:
        if column in population.columns:
            values = pd.to_numeric(population[column], errors="coerce")
            if values.isna().any() or values.nunique() > 1:
                differing.append(column)
    if not differing:
        return "info", "Toutes les méthodes sont comparées sur les mêmes effectifs."
    names = ", ".join(differing)
    if kind == ev.POPULATION_SELF:
        return (
            "warning",
            f"Effectifs différents entre méthodes ({names}) : chaque méthode est évaluée sur "
            "ses propres cas. Comparaison indicative ; préférez la population common_complete.",
        )
    return (
        "error",
        f"Effectifs incohérents entre méthodes ({names}) : ces modèles ne peuvent pas être "
        "classés de façon fiable.",
    )


def metrics_table(population: pd.DataFrame) -> pd.DataFrame:
    """Tableau d'affichage des métriques officielles, valeurs absentes explicites."""
    columns = {"method_run_id": "Méthode", "variant": "Variante"}
    table = population[[c for c in columns if c in population.columns]].rename(columns=columns)
    for column, (label, digits) in METRICS.items():
        if column in population.columns:
            table[label] = population[column].map(lambda v, d=digits: format_value(v, d))
    extras = {
        "n_compared_cases": ("Cas comparés", 0, False),
        "n_compared_hours": ("Heures comparées", 0, False),
        "n_evaluable_counters": ("Compteurs évaluables", 0, False),
        "coverage_24h": ("Couverture 24 h", 1, True),
        "n_fallback_cases": ("Cas avec repli", 0, False),
    }
    for column, (label, digits, percent) in extras.items():
        if column in population.columns:
            table[label] = population[column].map(
                lambda v, d=digits, p=percent: format_value(v, d, percent=p)
            )
    return table.reset_index(drop=True)


def identifiers_table(population: pd.DataFrame) -> pd.DataFrame:
    """Identifiants communs de la population comparée (une ligne par métadonnée)."""
    rows = [("comparison_population_id", population["comparison_population_id"].iloc[0])]
    kind = population["population_kind"].iloc[0] if "population_kind" in population else None
    rows.append(("population_kind", kind or MISSING))
    for column in ("experiment_id", *ev.COMPARISON_METADATA):
        if column in population.columns and column != "comparison_population_id":
            rows.append((column, population[column].iloc[0]))
    if "local_budget_hours" in population.columns:
        budget = population["local_budget_hours"].iloc[0]
        rows.append(("local_budget_hours", f"{int(budget)} h" if pd.notna(budget) else MISSING))
    return pd.DataFrame(rows, columns=["Identifiant", "Valeur"])


def coverage_table(summary: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    """Couverture officielle des méthodes de la population (résumé E5 de coverage.csv)."""
    keys = ["method_run_id", "variant", "local_budget_hours"]
    if any(key not in population.columns or key not in summary.columns for key in keys):
        return pd.DataFrame(columns=list(COVERAGE_LABELS.values()))
    wanted = population[keys].drop_duplicates()
    rows = summary.merge(wanted, on=keys, how="inner")
    table = rows[list(COVERAGE_LABELS)].copy()
    for column in COVERAGE_LABELS:
        if column == "coverage_24h":
            table[column] = table[column].map(lambda v: format_value(v, 1, percent=True))
        elif column not in ("method_run_id", "variant"):
            table[column] = table[column].map(format_value)
    return table.rename(columns=COVERAGE_LABELS).reset_index(drop=True)


def provenance_table(results: ev.TeamResults) -> pd.DataFrame:
    """Provenance déclarée par le manifeste E4 de l'équipe."""
    manifest = results.manifest
    declared = manifest.get("outputs_sha256") or {}
    names = sorted(Path(str(path).replace("\\", "/")).name for path in declared)
    outputs = ", ".join(names) if names else MISSING
    rows = [
        ("Équipe évaluée", results.team),
        ("experiment_id", manifest.get("experiment_id", MISSING)),
        ("protocol_id", manifest.get("protocol_id", MISSING)),
        ("snapshot_id", manifest.get("snapshot_id", MISSING)),
        ("Généré le", manifest.get("generated_at", MISSING)),
        ("Script E4", manifest.get("script", MISSING)),
        ("Sorties déclarées", outputs),
    ]
    return pd.DataFrame(rows, columns=["Provenance", "Valeur"])


# ---------------------------------------------------------------- affichage


def _show_message(level: str, message: str) -> None:
    {"info": st.caption, "warning": st.warning, "error": st.error}[level](message)


def _select_metadata(data: pd.DataFrame, key: str) -> pd.DataFrame | None:
    """Fixer chaque métadonnée de comparaison ; un menu n'apparaît que s'il y a un choix."""
    for column in ev.COMPARISON_METADATA:
        values = sorted(data[column].dropna().astype(str).unique().tolist())
        if not values:
            st.warning(f"Aucune valeur disponible pour {column}.")
            return None
        if len(values) == 1:
            selected = values[0]
        else:
            selected = st.selectbox(column, values, key=f"{key}_{column}")
        data = data.loc[data[column].astype(str).eq(selected)]
    return data


def _render_population(
    population: pd.DataFrame, key: str, coverage_summary: pd.DataFrame | None = None
) -> None:
    st.markdown("**Identifiants de la population comparée**")
    st.dataframe(identifiers_table(population), hide_index=True, key=f"{key}_ids")

    kind = population["population_kind"].iloc[0]
    if kind in POPULATION_HELP:
        st.caption(POPULATION_HELP[kind])
    level, message = population_sizes_check(population)
    _show_message(level, message)

    st.markdown("**Métriques officielles E4**")
    st.dataframe(metrics_table(population), hide_index=True, key=f"{key}_metrics")
    missing = int(population["mae_macro"].isna().sum())
    if missing:
        st.warning(
            f"{missing} méthode(s) sans MAE officielle (aucune heure évaluable) : "
            "affichées « non disponible » et exclues du graphique."
        )

    with_mae = population.loc[population["mae_macro"].notna()]
    if len(with_mae) >= 2 and level != "error":
        figure = px.bar(
            with_mae,
            x="method_run_id",
            y="mae_macro",
            color="variant",
            title="MAE macro officielle par méthode (plus bas = meilleur)",
            labels={"method_run_id": "Méthode", "mae_macro": "MAE macro (vélos/h)"},
        )
        st.plotly_chart(figure, key=f"{key}_chart")
        best = with_mae.iloc[0]  # population déjà triée par ev.ranked_methods
        st.success(
            f"MAE macro la plus basse dans cette population : {best['method_run_id']} "
            f"({format_value(best['mae_macro'])} vélos/h)."
        )
    elif level != "error":
        st.info("Au moins deux méthodes avec une MAE officielle sont nécessaires au classement.")

    if coverage_summary is not None:
        st.markdown("**Couverture officielle E4**")
        st.caption(
            "Cas prédits : au moins une heure prévue · complets : 24 heures prévues, repli "
            "compris · évaluables : au moins une heure prévue et mesurée. La couverture porte "
            "sur tous les cas attendus du protocole, quelle que soit la population choisie."
        )
        table = coverage_table(coverage_summary, population)
        if table.empty:
            st.info("Aucune couverture officielle pour ces méthodes.")
        else:
            st.dataframe(table, hide_index=True, key=f"{key}_coverage")
            if table[COVERAGE_LABELS["matches_scores"]].ne("oui").any():
                st.error("coverage.csv et scores.csv ne concordent pas pour certaines méthodes.")


def show_model_comparison(
    scores: pd.DataFrame,
    *,
    coverage_summary: pd.DataFrame | None = None,
    key: str = "model_comparison",
) -> None:
    """Comparer des méthodes évaluées dans des conditions identiques (API historique)."""
    st.subheader("Comparaison des méthodes de prévision")
    if scores.empty:
        st.info("Aucun résultat de comparaison n'est encore disponible.")
        return
    try:
        data, counts = prepare_scores(scores)
    except ValueError as error:
        st.error(str(error))
        return
    if data.empty:
        st.warning("Aucun score d'évaluation valide n'est disponible.")
        return
    st.caption(
        f"Lignes valides : {counts['valid_rows']} | MAE invalides exclues : "
        f"{counts['invalid_mae']} | métadonnées invalides exclues : "
        f"{counts['invalid_metadata']} | MAE absentes conservées : {counts['missing_mae']}"
    )

    selected = _select_metadata(data, key)
    if selected is None or selected.empty:
        st.info("Aucun résultat ne correspond aux conditions choisies.")
        return
    population_id = selected["comparison_population_id"].iloc[0]
    try:
        population = comparable_population(selected, population_id)
    except (ValueError, ev.EvaluationDataError) as error:
        st.error(f"Populations incompatibles : {error}")
        st.dataframe(selected, hide_index=True, key=f"{key}_rejected")
        return
    _render_population(population, key, coverage_summary)


def show_team_evaluation(results: ev.TeamResults, *, key: str | None = None) -> None:
    """Vue d'une équipe : budget E3, type de population puis comparaison."""
    key = key or f"official_{results.team}"
    scores = results.scores
    if scores.empty:
        st.info(f"Aucun score officiel pour {results.team}.")
        return

    if results.team == "E3":
        budget = st.radio(
            "Budget d'historique local",
            list(ev.LOCAL_BUDGETS),
            format_func=lambda hours: f"{hours} h",
            horizontal=True,
            key=f"{key}_budget",
        )
        if budget not in ev.available_budgets(scores):
            st.warning(f"Aucun score officiel E3 pour le budget {budget} h.")
            return
        scores = ev.filter_budget(scores, budget)

    kinds = [kind for kind in ev.POPULATION_KINDS if kind in set(scores["population_kind"])]
    if not kinds:
        st.warning("Aucune population de comparaison self ou common_complete disponible.")
        return
    kind = st.radio(
        "Population de comparaison",
        kinds,
        format_func=POPULATION_LABELS.get,
        horizontal=True,
        key=f"{key}_population",
    )
    show_model_comparison(
        scores.loc[scores["population_kind"].eq(kind)],
        coverage_summary=results.coverage_summary(),
        key=f"{key}_{kind}",
    )
    with st.expander("Provenance de l'évaluation"):
        st.dataframe(provenance_table(results), hide_index=True, key=f"{key}_provenance")


def visible_teams(teams: Sequence[str] | None = None) -> tuple[str, ...]:
    """Équipes à afficher, dans l'ordre officiel ; ``None`` = toutes les équipes."""
    if teams is None:
        return ev.TEAMS
    requested = set(teams)
    unknown = requested - set(ev.TEAMS)
    if unknown or not requested:
        raise ValueError(f"Équipes à afficher invalides : {sorted(unknown) or 'aucune'}.")
    return tuple(team for team in ev.TEAMS if team in requested)


def _show_team_or_problem(results: ev.OfficialResults, team: str) -> None:
    if team in results.problems:
        st.error(f"Résultats officiels {team} indisponibles : {results.problems[team]}")
    elif team not in results.teams:
        st.info(f"Aucun résultat officiel {team} n'a été chargé.")
    else:
        show_team_evaluation(results.teams[team])


def show_official_evaluation(
    results: ev.OfficialResults | None = None,
    *,
    root: Path | None = None,
    teams: Sequence[str] | None = None,
) -> None:
    """Section globale des évaluations officielles E4.

    ``teams`` choisit seulement les vues affichées (par exemple selon le périmètre de
    l'application) : les scores restent ceux du protocole E4 complet, jamais refiltrés.
    Plusieurs équipes s'affichent dans des sous-onglets distincts, jamais mélangées.
    """
    shown = visible_teams(teams)
    st.header("Évaluation officielle E4")
    st.caption(
        "Scores calculés par l'Équipe 4 sur l'ensemble des cas du protocole. Ils ne "
        "remplacent pas le score indicatif affiché pour un seul cas."
    )
    if results is None:
        try:
            results = ev.load_official_results(root)
        except (OSError, ValueError) as error:
            st.error(f"Impossible de charger les résultats officiels E4 : {error}")
            return

    if len(shown) == 1:
        (team,) = shown
        st.caption(
            f"Vue limitée à {TEAM_LABELS.get(team, team)} selon le périmètre choisi. "
            "Les scores restent ceux du protocole E4 complet."
        )
        _show_team_or_problem(results, team)
        return
    for team, tab in zip(shown, st.tabs([TEAM_LABELS.get(t, t) for t in shown])):
        with tab:
            _show_team_or_problem(results, team)

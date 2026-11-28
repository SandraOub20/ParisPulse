"""E5 — Navigation principale de l'application et non-régression du parcours compteur.

L'application réelle (``src/app/streamlit_app.py``) est exécutée avec ``AppTest`` sur un
mini-instantané E1 et des fichiers officiels E4 fabriqués dans un dossier temporaire :
aucune donnée réelle, aucun modèle lourd (les tests choisissent la référence E2).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import src.common.config as config
from src.app import evaluation_service as ev
from src.app import service
from tests.test_e5_dashboard_comparison import e2_coverage, e2_scores, e3_coverage, e3_scores
from tests.test_e5_evaluation_service import rehash, write_team

APP = str(Path(__file__).resolve().parents[1] / "src" / "app" / "streamlit_app.py")
SNAPSHOT = "hist-nav"
COUNTER = "C-NAV"
EXPLORER, EVALUATION = "Prévision par compteur", "Évaluation officielle E4"
STUDY_TABS = ["Prévision", "Historique disponible", "Données manquantes", "Contexte E1"]


# --------------------------------------------------------------------------- données


def write_snapshot(processed: Path) -> Path:
    """Un compteur E2 (S_train, retenu) avec cinq semaines de mesures horaires."""
    folder = processed / SNAPSHOT
    folder.mkdir(parents=True)
    pd.DataFrame(
        {
            "counter_id": [COUNTER],
            "counter_name": ["Compteur test"],
            "site_name": ["Site test"],
            "direction": ["Nord"],
            "site_group_id": ["G-NAV"],
            "latitude": [48.86],
            "longitude": [2.35],
        }
    ).to_csv(folder / "counters.csv", index=False)
    pd.DataFrame(
        {
            "counter_id": [COUNTER],
            "period_role": ["selection"],
            "selection_status": ["retained"],
            "status_reason": [""],
            "site_role": ["S_train"],
        }
    ).to_csv(folder / "inventory_quality.csv", index=False)
    hours = pd.date_range("2026-08-01T00:00Z", "2026-09-03T23:00Z", freq="h")
    values = 50.0 + 10.0 * np.sin(np.arange(len(hours)) * 2 * np.pi / 24)
    pd.DataFrame(
        {
            "counter_id": COUNTER,
            "timestamp": hours.map(pd.Timestamp.isoformat),
            "interval_end": (hours + pd.Timedelta(hours=1)).map(pd.Timestamp.isoformat),
            "count_raw": values,
            "count": values,
            "is_observed": True,
            "is_scoreable": True,
        }
    ).to_csv(folder / "counts.csv", index=False)
    return folder


def write_official(evaluation: Path) -> Path:
    root = evaluation / ev.PROTOCOL_ID
    write_team(root, "E2", e2_scores(), e2_coverage())
    write_team(root, "E3", e3_scores(), e3_coverage())
    return root


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Rediriger ``data_path`` vers un dossier temporaire (relu à chaque exécution du script)."""
    folders = {key: tmp_path / key for key in ("processed", "evaluation", "predictions")}
    for folder in folders.values():
        folder.mkdir()
    monkeypatch.setattr(config, "data_path", lambda key: folders.get(key, tmp_path / key))
    return folders


def run_app(timeout: float = 60) -> AppTest:
    return AppTest.from_file(APP, default_timeout=timeout).run()


# ------------------------------------------------------------------ outils AppTest


def top_tabs(at: AppTest) -> dict:
    return {tab.label: tab for tab in at.tabs if tab.label in (EXPLORER, EVALUATION)}


def texts(elements) -> str:
    return " | ".join(str(element.value) for element in elements)


def labels(elements) -> list[str]:
    return [element.label for element in elements]


def assert_clean(at: AppTest) -> None:
    assert not at.exception, texts(at.exception)


def calculate(at: AppTest, method: str) -> AppTest:
    at.selectbox(key=f"method-{SNAPSHOT}-{COUNTER}").set_value(method).run()
    (button,) = [b for b in at.button if b.label == "Calculer la prévision"]
    button.click().run()
    assert_clean(at)
    return at


# ------------------------------------------------------------- navigation principale


def test_main_navigation_has_explorer_and_official_evaluation_tabs(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = run_app()
    assert_clean(at)
    # at.tabs parcourt l'arbre en profondeur : les onglets d'étude sont imbriqués.
    assert [tab.label for tab in at.tabs][0] == EXPLORER
    assert [t.label for t in at.tabs if t.label in (EXPLORER, EVALUATION)] == [EXPLORER, EVALUATION]
    tabs = top_tabs(at)
    assert [t.label for t in tabs[EXPLORER].tabs] == STUDY_TABS
    team_tabs = {t.label for t in tabs[EVALUATION].tabs}
    assert team_tabs == {"E2 : sites connus", "E3 : nouveaux sites"}
    assert "Évaluation officielle E4" in texts(tabs[EVALUATION].header)
    assert "Évaluation officielle E4" not in texts(tabs[EXPLORER].header)
    assert "Prévision sur 24 h" in texts(tabs[EXPLORER].subheader)


def test_official_evaluation_is_available_without_e1_snapshot(paths):
    write_official(paths["evaluation"])  # aucun instantané : le parcours compteur s'arrête
    at = run_app()
    assert_clean(at)
    tabs = top_tabs(at)
    assert "Installez l’instantané E1" in texts(tabs[EXPLORER].warning)
    evaluation = tabs[EVALUATION]
    assert not evaluation.error
    frames = [f.value for f in evaluation.dataframe if "MAE macro (vélos/h)" in f.value.columns]
    assert len(frames) == 2  # une vue E2, une vue E3
    assert {"e2-mlp", "e2-reference"} == set(frames[0]["Méthode"])
    assert labels(at.radio)[:1] == ["Population de comparaison"]


def test_missing_official_files_do_not_block_the_counter_flow(paths):
    write_snapshot(paths["processed"])  # aucun fichier E4
    at = run_app()
    assert_clean(at)
    tabs = top_tabs(at)
    errors = texts(tabs[EVALUATION].error)
    assert "E2 indisponibles" in errors and "E3 indisponibles" in errors
    assert "Prévision sur 24 h" in texts(tabs[EXPLORER].subheader)
    assert [tab.label for tab in at.tabs if tab.label in STUDY_TABS] == STUDY_TABS


def test_unreadable_evaluation_path_is_reported_in_e4_tab_only(paths, monkeypatch):
    write_snapshot(paths["processed"])

    def broken(key):
        if key == "evaluation":
            raise KeyError("evaluation")
        return paths[key]

    monkeypatch.setattr(config, "data_path", broken)
    at = run_app()
    assert_clean(at)
    tabs = top_tabs(at)
    assert "Évaluations officielles E4 indisponibles" in texts(tabs[EVALUATION].error)
    assert not tabs[EXPLORER].error


# -------------------------------------------------------------------------- cache


def test_official_results_are_cached_and_reloaded_when_files_change(paths, monkeypatch):
    write_snapshot(paths["processed"])
    root = write_official(paths["evaluation"])
    calls = []
    original = ev.load_official_results

    def counting(root=None, **kwargs):
        calls.append(root)
        return original(root, **kwargs)

    monkeypatch.setattr(ev, "load_official_results", counting)
    at = run_app()
    at.run()  # nouvelle interaction : le cache sert les mêmes fichiers
    assert_clean(at)
    assert len(calls) == 1

    # E4 republie ses scores : la signature change, le cache est relu.
    folder = root / ev.EXPERIMENTS["E2"]
    path = folder / ev.SCORES_FILE
    path.write_text(path.read_text(encoding="utf-8").replace("22.2", "21.9"), encoding="utf-8")
    rehash(folder)
    at.run()
    assert_clean(at)
    assert len(calls) == 2
    frames = [
        f.value
        for f in top_tabs(at)[EVALUATION].dataframe
        if "MAE macro (vélos/h)" in f.value.columns
    ]
    assert "21.90" in frames[0]["MAE macro (vélos/h)"].tolist()


def test_e4_version_tracks_every_official_file(paths):
    import importlib

    app = importlib.import_module("src.app.streamlit_app")
    root = write_official(paths["evaluation"])
    version = app.e4_version(root)
    assert len(version) == len(ev.TEAMS) * 3
    assert all(size > 0 for _, _, size in version)
    (root / ev.EXPERIMENTS["E3"] / ev.COVERAGE_FILE).unlink()
    changed = app.e4_version(root)
    assert changed != version
    assert sum(size == 0 for _, _, size in changed) == 1


# --------------------------------------------- périmètre de la barre latérale → vues E4

KNOWN, NEW, ALL = "Sites connus", "Nouveaux sites", "Tout le réseau"
TEAM_TABS = {"E2 : sites connus", "E3 : nouveaux sites"}


def e4_metrics(container) -> list[pd.DataFrame]:
    return [f.value for f in container.dataframe if "MAE macro (vélos/h)" in f.value.columns]


def with_perimeter(perimeter: str) -> AppTest:
    at = run_app()
    at.radio(key="perimeter").set_value(perimeter).run()
    assert_clean(at)
    return at


def test_perimeter_reuses_the_single_sidebar_selector(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = run_app()
    perimeters = [radio for radio in at.sidebar.radio if radio.label == "Périmètre"]
    assert len(perimeters) == 1 and perimeters[0].key == "perimeter"
    assert perimeters[0].value == ALL
    assert [radio.label for radio in at.radio].count("Périmètre") == 1  # pas de 2e sélecteur


def test_known_sites_perimeter_shows_only_e2_evaluation(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = with_perimeter(KNOWN)
    evaluation = top_tabs(at)[EVALUATION]
    assert not {t.label for t in evaluation.tabs} & TEAM_TABS
    assert "Vue limitée à E2 : sites connus" in texts(evaluation.caption)
    (metrics,) = e4_metrics(evaluation)
    assert set(metrics["Méthode"]) == {"e2-mlp", "e2-reference"}
    keys = {radio.key for radio in at.radio}
    assert "official_E2_population" in keys
    assert not {"official_E3_budget", "official_E3_population"} & keys
    # Le parcours compteur reste celui des sites connus.
    assert "Prévision sur 24 h" in texts(top_tabs(at)[EXPLORER].subheader)


def test_new_sites_perimeter_shows_only_e3_with_budgets(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = with_perimeter(NEW)
    evaluation = top_tabs(at)[EVALUATION]
    assert not {t.label for t in evaluation.tabs} & TEAM_TABS
    assert "Vue limitée à E3 : nouveaux sites" in texts(evaluation.caption)
    assert at.radio(key="official_E3_budget").options == ["24 h", "72 h", "168 h"]
    assert "official_E2_population" not in {radio.key for radio in at.radio}
    at.radio(key="official_E3_budget").set_value(168).run()
    assert_clean(at)
    (metrics,) = e4_metrics(top_tabs(at)[EVALUATION])
    assert set(metrics["Méthode"]) == {
        "e3-chronos-2-frozen-v1",
        "e3-google-TimesFM_2.5-frozen-v1",
    }
    (identifiers,) = [
        f.value for f in top_tabs(at)[EVALUATION].dataframe if "Identifiant" in f.value.columns
    ]
    assert "168 h" in identifiers["Valeur"].tolist()


def test_whole_network_perimeter_keeps_e2_and_e3_in_separate_subtabs(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = with_perimeter(ALL)
    evaluation = top_tabs(at)[EVALUATION]
    subtabs = {t.label: t for t in evaluation.tabs if t.label in TEAM_TABS}
    assert set(subtabs) == TEAM_TABS
    (e2,) = e4_metrics(subtabs["E2 : sites connus"])
    (e3,) = e4_metrics(subtabs["E3 : nouveaux sites"])
    assert set(e2["Méthode"]) == {"e2-mlp", "e2-reference"}
    assert set(e3["Méthode"]) == {"e3-chronos-2-frozen-v1", "e3-google-TimesFM_2.5-frozen-v1"}
    assert not set(e2["Méthode"]) & set(e3["Méthode"])
    e2_ids, e3_ids = (
        next(f.value for f in subtabs[label].dataframe if "Identifiant" in f.value)
        for label in ("E2 : sites connus", "E3 : nouveaux sites")
    )
    assert any(str(v).startswith("known_site_") for v in e2_ids["Valeur"])
    assert any(str(v).startswith("new_site_b") for v in e3_ids["Valeur"])


def test_perimeter_changes_views_but_never_the_official_scores(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = with_perimeter(ALL)
    subtabs = {t.label: t for t in top_tabs(at)[EVALUATION].tabs if t.label in TEAM_TABS}
    (e2_all,) = e4_metrics(subtabs["E2 : sites connus"])
    (e3_all,) = e4_metrics(subtabs["E3 : nouveaux sites"])
    at.radio(key="perimeter").set_value(KNOWN).run()
    (e2_only,) = e4_metrics(top_tabs(at)[EVALUATION])
    at.radio(key="perimeter").set_value(NEW).run()
    (e3_only,) = e4_metrics(top_tabs(at)[EVALUATION])
    pd.testing.assert_frame_equal(e2_all, e2_only)
    pd.testing.assert_frame_equal(e3_all, e3_only)


def test_perimeter_view_keeps_e4_population_and_coverage(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = with_perimeter(NEW)
    at.radio(key="official_E3_population").set_value("common_complete").run()
    assert_clean(at)
    evaluation = top_tabs(at)[EVALUATION]
    frames = {column for f in evaluation.dataframe for column in f.value.columns}
    assert {"MAE macro (vélos/h)", "R²", "Cas évaluables", "Provenance"} <= frames
    (identifiers,) = [f.value for f in evaluation.dataframe if "Identifiant" in f.value.columns]
    assert "common_complete" in identifiers["Valeur"].tolist()


def test_forecast_is_kept_while_browsing_e4_with_a_perimeter(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = with_perimeter(KNOWN)
    at = calculate(at, "reference")
    selection = at.session_state["selection"]
    at.radio(key="official_E2_population").set_value("self").run()
    at.run()
    assert_clean(at)
    assert at.session_state["selection"] == selection
    assert at.session_state["forecast-result"] is not None
    assert at.radio(key="perimeter").value == KNOWN
    assert "MAE sur ce cas (indicatif)" in labels(at.metric)


# --------------------------------------------------- non-régression parcours compteur


def test_counter_flow_still_offers_map_methods_and_study_tabs(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = run_app()
    assert_clean(at)
    explorer = top_tabs(at)[EXPLORER]
    assert {"Carte des compteurs", "Prévision sur 24 h"} <= set(
        element.value for element in explorer.subheader
    )
    assert at.selectbox(key=f"counter-{SNAPSHOT}-Tout le réseau").value == COUNTER
    methods = at.selectbox(key=f"method-{SNAPSHOT}-{COUNTER}").options
    assert service.KNOWN_SITE_LABELS["reference"] in methods
    assert [tab.label for tab in at.tabs if tab.label in STUDY_TABS] == STUDY_TABS
    assert "Calculer la prévision" in labels(at.button)


def test_forecast_shows_local_indicative_mae_label(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = calculate(run_app(), "reference")
    assert at.session_state["forecast-result"] is not None
    metric_labels = labels(at.metric)
    assert "MAE sur ce cas (indicatif)" in metric_labels
    assert "Erreur moyenne absolue" not in metric_labels


def test_local_comparison_points_to_official_e4_tab(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = calculate(run_app(), service.COMPARE_REFERENCES)
    captions = texts(top_tabs(at)[EXPLORER].caption)
    assert "Comparaison des méthodes sur ce cas" in texts(at.subheader)
    assert "Scores indicatifs calculés sur les 24 heures de ce seul cas" in captions
    assert "« Évaluation officielle E4 »" in captions


def test_counter_and_forecast_state_survive_e4_interactions(paths):
    write_snapshot(paths["processed"])
    write_official(paths["evaluation"])
    at = calculate(run_app(), "reference")
    studies, _ = at.session_state["forecast-result"]
    selection = at.session_state["selection"]

    at.radio(key="official_E3_budget").set_value(168).run()
    at.radio(key="official_E3_population").set_value("common_complete").run()
    assert_clean(at)

    assert at.session_state["selection"] == selection
    assert at.session_state["forecast-result"] is not None
    assert at.session_state["forecast-result"][0][0].case == studies[0].case
    assert at.selectbox(key=f"method-{SNAPSHOT}-{COUNTER}").value == "reference"
    assert "MAE sur ce cas (indicatif)" in labels(at.metric)
    assert at.radio(key="official_E3_budget").value == 168

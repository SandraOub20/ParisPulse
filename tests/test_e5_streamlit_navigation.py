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
    assert team_tabs == {"E2 · sites connus", "E3 · nouveaux sites"}
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
        f.value for f in top_tabs(at)[EVALUATION].dataframe
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

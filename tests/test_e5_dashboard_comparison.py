"""E5 — Tests de l'affichage des évaluations officielles E4 (src/app/dashboard/comparison.py).

Les fonctions pures sont testées directement ; le rendu Streamlit est exécuté avec
``streamlit.testing.v1.AppTest`` sur des fichiers E4 fabriqués dans un dossier temporaire
(fabriques reprises de ``tests/test_e5_evaluation_service.py``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.app import evaluation_service as ev
from src.app.dashboard import comparison as cmp
from tests.test_e5_evaluation_service import (
    PROTOCOL,
    SNAPSHOT,
    coverage_rows,
    population,
    score_row,
    write_team,
)

CHRONOS = "e3-chronos-2-frozen-v1"
TIMESFM = "e3-google-TimesFM_2.5-frozen-v1"
E3_MAE = {24: ("26.1", "27.9"), 72: ("22.8", "22.5"), 168: ("19.7", "19.8")}
STATUSES = ["complete"] * 8 + ["fallback_complete", "error"]  # 9 complets sur 10


def e3_scores() -> list[dict]:
    rows = []
    for budget, maes in E3_MAE.items():
        for kind in ev.POPULATION_KINDS:
            for method, mae in zip((CHRONOS, TIMESFM), maes):
                rows.append(
                    score_row(
                        "E3",
                        budget,
                        method_run_id=method,
                        mae_macro=mae,
                        comparison_population_id=population("E3", budget, kind),
                        n_fallback_cases="1.0" if kind == "self" else "",
                    )
                )
    return rows


def e3_coverage() -> list[dict]:
    rows = []
    for budget in ev.LOCAL_BUDGETS:
        for method in (CHRONOS, TIMESFM):
            for row in coverage_rows("E3", method, "frozen", budget, STATUSES):
                rows.append({**row, "case_id": f"{row['case_id']}_{method}"})
    return rows


def e2_scores() -> list[dict]:
    return [
        score_row("E2", method_run_id="e2-mlp", variant="mlp", mae_macro="22.2"),
        score_row("E2", method_run_id="e2-reference", variant="reference", mae_macro="29.7"),
    ]


def e2_coverage() -> list[dict]:
    return coverage_rows("E2", "e2-mlp", "mlp", None, STATUSES) + coverage_rows(
        "E2", "e2-reference", "reference", None, STATUSES
    )


@pytest.fixture
def official_root(tmp_path):
    write_team(tmp_path, "E2", e2_scores(), e2_coverage())
    write_team(tmp_path, "E3", e3_scores(), e3_coverage())
    return tmp_path


def legacy_scores(**overrides) -> pd.DataFrame:
    """Format de l'ancienne démonstration : pas de variant ni de population E4 connue."""
    base = {
        "scenario": "known_site",
        "temporal_split": "test_period",
        "comparison_population_id": "demo_population",
        "protocol_id": "demo_protocol",
        "snapshot_id": "demo_snapshot",
        "n_compared_cases": 10,
        "n_compared_hours": 240,
        "n_complete_cases": 10,
    }
    rows = [
        {**base, "method_run_id": "Weekly", "mae_macro": 18.5},
        {**base, "method_run_id": "Forest", "mae_macro": 12.3},
        {**base, "method_run_id": "Invalid", "mae_macro": np.inf},
    ]
    frame = pd.DataFrame(rows)
    for column, value in overrides.items():
        frame[column] = value
    return frame


# ------------------------------------------------------------------ outils AppTest


def run_official(root) -> AppTest:
    def app(root):
        from pathlib import Path

        from src.app.dashboard.comparison import show_official_evaluation

        show_official_evaluation(root=Path(root))

    return AppTest.from_function(app, args=(str(root),), default_timeout=30).run()


def run_legacy(scores: pd.DataFrame) -> AppTest:
    def app(scores):
        from src.app.dashboard.comparison import show_model_comparison

        show_model_comparison(scores)

    return AppTest.from_function(app, args=(scores,), default_timeout=30).run()


def frames_with(container, column: str) -> list[pd.DataFrame]:
    return [frame.value for frame in container.dataframe if column in frame.value.columns]


def texts(elements) -> str:
    return " | ".join(str(element.value) for element in elements)


def assert_clean(at: AppTest) -> None:
    assert not at.exception, texts(at.exception)


# ------------------------------------------------------------ valeurs manquantes


@pytest.mark.parametrize("value", [None, np.nan, pd.NA, float("nan")])
def test_missing_values_are_never_formatted_as_zero(value):
    assert cmp.format_value(value) == cmp.MISSING


def test_real_zero_and_percent_are_kept():
    assert cmp.format_value(0) == "0"
    assert cmp.format_value(0.0) == "0.00"
    assert cmp.format_value(np.int64(320)) == "320"
    assert cmp.format_value(0.9838709, 1, percent=True) == "98.4%"
    assert cmp.format_value(True) == "oui"


def test_metrics_table_shows_missing_metrics_and_fallbacks(tmp_path):
    rows = [
        score_row(method_run_id=CHRONOS, mae_macro="20.0"),
        score_row(
            method_run_id=TIMESFM,
            mae_macro="",
            rmse="",
            r2="",
            bias="",
            n_compared_hours="0",
            n_compared_cases="0",
            n_fallback_cases="",
        ),
    ]
    write_team(tmp_path, "E3", rows)
    ranked = cmp.comparable_population(ev.load_scores("E3", tmp_path), population("E3", 24))

    table = cmp.metrics_table(ranked).set_index("Méthode")

    assert ranked["method_run_id"].tolist() == [CHRONOS, TIMESFM]  # MAE absente en fin
    for label in ("MAE macro (vélos/h)", "RMSE (vélos/h)", "R²", "Biais (vélos/h)"):
        assert table.loc[TIMESFM, label] == cmp.MISSING
    assert table.loc[TIMESFM, "Cas avec repli"] == cmp.MISSING
    assert table.loc[TIMESFM, "Cas comparés"] == "0"  # vrai zéro officiel
    assert table.loc[CHRONOS, "MAE macro (vélos/h)"] == "20.00"
    assert np.isnan(ranked.loc[1, "mae_macro"])


def test_prepare_scores_keeps_missing_mae_and_excludes_invalid_mae():
    base = legacy_scores().iloc[0].to_dict()
    extra = pd.DataFrame(
        [
            {**base, "method_run_id": "Empty", "mae_macro": None},
            {**base, "method_run_id": "Text", "mae_macro": "abc"},
            {**base, "method_run_id": "Neg", "mae_macro": -1},
            {**base, "method_run_id": "NoPop", "snapshot_id": ""},
        ]
    )
    scores = pd.concat([legacy_scores().astype({"mae_macro": object}), extra], ignore_index=True)

    data, counts = cmp.prepare_scores(scores)

    assert counts == {"valid_rows": 3, "invalid_mae": 3, "invalid_metadata": 1, "missing_mae": 1}
    assert set(data["method_run_id"]) == {"Weekly", "Forest", "Empty"}
    assert data.loc[data["method_run_id"].eq("Empty"), "mae_macro"].isna().all()
    assert data["variant"].eq("").all()  # colonne absente de l'ancien format
    assert data["population_kind"].isna().all()  # population hors convention E4


def test_prepare_scores_reports_missing_columns():
    with pytest.raises(ValueError, match="comparison_population_id"):
        cmp.prepare_scores(legacy_scores().drop(columns="comparison_population_id"))


# ----------------------------------------------------------- populations


def test_self_population_with_different_sizes_is_only_indicative():
    frame = pd.DataFrame(
        {
            "population_kind": ["self"] * 2,
            "n_compared_cases": [300, 305],
            "n_compared_hours": [7180] * 2,
        }
    )
    level, message = cmp.population_sizes_check(frame)
    assert level == "warning" and "common_complete" in message


@pytest.mark.parametrize("kind", [ev.POPULATION_COMMON, None])
def test_common_or_unknown_population_with_different_sizes_is_incompatible(kind):
    frame = pd.DataFrame({"population_kind": [kind] * 2, "n_compared_cases": [300, 305]})
    level, message = cmp.population_sizes_check(frame)
    assert level == "error" and "n_compared_cases" in message


def test_identical_sizes_are_accepted():
    frame = pd.DataFrame({"population_kind": ["common_complete"] * 2, "n_compared_cases": [5, 5]})
    assert cmp.population_sizes_check(frame)[0] == "info"


def test_population_mixing_snapshots_is_refused():
    base = {**score_row(), "population_kind": "self"}
    scores = pd.DataFrame([base, {**base, "method_run_id": TIMESFM, "snapshot_id": "autre"}])
    with pytest.raises(ev.EvaluationDataError, match="snapshot_id"):
        cmp.comparable_population(scores, population("E3", 24))


def test_identifiers_table_shows_population_metadata(official_root):
    scores = ev.filter_budget(ev.load_scores("E3", official_root), 72)
    common = scores.loc[scores["population_kind"].eq("common_complete")]
    population_id = population("E3", 72, "common_complete")
    table = cmp.identifiers_table(cmp.comparable_population(common, population_id))
    values = dict(zip(table["Identifiant"], table["Valeur"]))
    assert values["comparison_population_id"] == population("E3", 72, "common_complete")
    assert values["population_kind"] == "common_complete"
    assert values["local_budget_hours"] == "72 h"
    assert (values["protocol_id"], values["snapshot_id"]) == (PROTOCOL, SNAPSHOT)
    assert values["experiment_id"] == "EXP-E3"


# -------------------------------------------------------------- couverture


def test_coverage_table_separates_predicted_complete_evaluable_errors_and_fallbacks(tmp_path):
    statuses = ["complete"] * 6 + ["fallback_complete", "partial", "error", "no_forecast"]
    write_team(
        tmp_path,
        "E3",
        [score_row(n_complete_cases="7", n_compared_cases="6", coverage_24h="0.7")],
        coverage_rows("E3", CHRONOS, "frozen", 24, statuses),
    )
    results = ev.load_team_results("E3", tmp_path)
    population_rows = cmp.comparable_population(results.scores, population("E3", 24))

    (row,) = cmp.coverage_table(results.coverage_summary(), population_rows).to_dict("records")

    assert row["Cas attendus"] == "10"
    assert row["Cas prédits"] == "8"
    assert row["Cas complets (24 h)"] == "7"
    assert row["dont complétés par repli"] == "1"
    assert row["Cas évaluables"] == "6"
    assert (row["Erreurs"], row["Partiels"], row["Sans prévision"]) == ("1", "1", "1")
    assert row["Couverture 24 h"] == "70.0%"
    assert row["Cohérent avec scores.csv"] == "oui"


def test_coverage_table_keeps_only_population_methods_and_budget(official_root):
    results = ev.load_team_results("E3", official_root)
    scores = ev.filter_budget(results.scores, 168)
    selected = scores["method_run_id"].eq(TIMESFM) & scores["population_kind"].eq("self")
    one_method = scores.loc[selected]
    table = cmp.coverage_table(results.coverage_summary(), one_method)
    assert table["Méthode"].tolist() == [TIMESFM]
    assert table["Cas attendus"].tolist() == ["10"]


def test_provenance_table_reads_manifest(official_root):
    values = dict(cmp.provenance_table(ev.load_team_results("E3", official_root)).values)
    assert values["experiment_id"] == "EXP-E3"
    assert values["snapshot_id"] == SNAPSHOT
    assert values["Sorties déclarées"] == "coverage.csv, scores.csv"  # chemins Windows lus


# ---------------------------------------------------- section officielle (AppTest)


def test_official_section_shows_distinct_e2_and_e3_views(official_root):
    at = run_official(official_root)
    assert_clean(at)
    assert at.header[0].value == "Évaluation officielle E4"
    e2_tab, e3_tab = at.tabs
    assert e2_tab.label.startswith("E2") and e3_tab.label.startswith("E3")

    (e2_metrics,) = frames_with(e2_tab, "MAE macro (vélos/h)")
    (e3_metrics,) = frames_with(e3_tab, "MAE macro (vélos/h)")
    assert set(e2_metrics["Méthode"]) == {"e2-mlp", "e2-reference"}
    assert set(e3_metrics["Méthode"]) == {CHRONOS, TIMESFM}
    assert {"RMSE (vélos/h)", "R²", "Biais (vélos/h)"} <= set(e3_metrics.columns)
    assert "e2-mlp" in texts(e2_tab.success) and CHRONOS in texts(e3_tab.success)
    # Le budget n'existe que dans la vue E3.
    assert [radio.key for radio in at.radio] == [
        "official_E2_population",
        "official_E3_budget",
        "official_E3_population",
    ]


@pytest.mark.parametrize("budget", ev.LOCAL_BUDGETS)
def test_e3_budget_filter_changes_displayed_scores(official_root, budget):
    at = run_official(official_root)
    assert at.radio(key="official_E3_budget").options == ["24 h", "72 h", "168 h"]
    at.radio(key="official_E3_budget").set_value(budget).run()
    assert_clean(at)

    (metrics,) = frames_with(at.tabs[1], "MAE macro (vélos/h)")
    shown = dict(zip(metrics["Méthode"], metrics["MAE macro (vélos/h)"]))
    expected = dict(zip((CHRONOS, TIMESFM), E3_MAE[budget]))
    assert shown == {method: f"{float(mae):.2f}" for method, mae in expected.items()}
    (identifiers,) = frames_with(at.tabs[1], "Identifiant")
    assert population("E3", budget) in identifiers["Valeur"].tolist()


def test_population_kind_selection_switches_to_common_complete(official_root):
    at = run_official(official_root)
    at.radio(key="official_E3_population").set_value("common_complete").run()
    assert_clean(at)
    (identifiers,) = frames_with(at.tabs[1], "Identifiant")
    assert population("E3", 24, "common_complete") in identifiers["Valeur"].tolist()
    (metrics,) = frames_with(at.tabs[1], "MAE macro (vélos/h)")
    assert metrics["Cas avec repli"].eq(cmp.MISSING).all()  # absent dans common_complete
    assert cmp.POPULATION_HELP[ev.POPULATION_COMMON] in texts(at.tabs[1].caption)


def test_official_section_shows_coverage_and_provenance(official_root):
    at = run_official(official_root)
    (coverage,) = frames_with(at.tabs[1], "Cas évaluables")
    assert coverage["Cas attendus"].eq("10").all()
    assert coverage["Cas complets (24 h)"].eq("9").all()
    assert coverage["Erreurs"].eq("1").all()
    assert coverage["dont complétés par repli"].eq("1").all()
    (provenance,) = frames_with(at.tabs[1], "Provenance")
    assert "EXP-E3" in provenance["Valeur"].tolist()


def test_missing_budget_is_reported(tmp_path):
    write_team(tmp_path, "E2", e2_scores(), e2_coverage())
    rows = [r for r in e3_scores() if r["local_budget_hours"] == "24.0"]
    cover = [r for r in e3_coverage() if r["local_budget_hours"] == "24.0"]
    write_team(tmp_path, "E3", rows, cover)
    at = run_official(tmp_path)
    at.radio(key="official_E3_budget").set_value(72).run()
    assert_clean(at)
    assert "budget 72 h" in texts(at.tabs[1].warning)
    assert not frames_with(at.tabs[1], "MAE macro (vélos/h)")


def test_missing_team_files_show_error_without_hiding_other_team(tmp_path):
    write_team(tmp_path, "E2", e2_scores(), e2_coverage())
    at = run_official(tmp_path)
    assert_clean(at)
    assert "E3 indisponibles" in texts(at.tabs[1].error)
    assert "absent" in texts(at.tabs[1].error)
    assert frames_with(at.tabs[0], "MAE macro (vélos/h)")


def test_invalid_official_file_shows_explicit_error(tmp_path):
    write_team(tmp_path, "E2", e2_scores(), e2_coverage())
    rows = e3_scores()
    rows[0]["mae_macro"] = "abc"
    write_team(tmp_path, "E3", rows, e3_coverage())
    at = run_official(tmp_path)
    assert_clean(at)
    assert "mae_macro non numérique" in texts(at.tabs[1].error)


def test_missing_mae_is_shown_as_unavailable_and_kept_out_of_ranking(tmp_path):
    write_team(tmp_path, "E2", e2_scores(), e2_coverage())
    rows = e3_scores()
    empty = dict(mae_macro="", rmse="", r2="", bias="", n_compared_hours="0", n_compared_cases="0")
    rows[1].update(empty)  # TimesFM, budget 24, self
    write_team(tmp_path, "E3", rows, e3_coverage())
    at = run_official(tmp_path)
    assert_clean(at)

    (metrics,) = frames_with(at.tabs[1], "MAE macro (vélos/h)")
    assert metrics.set_index("Méthode").loc[TIMESFM, "MAE macro (vélos/h)"] == cmp.MISSING
    assert "sans MAE officielle" in texts(at.tabs[1].warning)
    assert "Au moins deux méthodes" in texts(at.tabs[1].info)
    assert not at.tabs[1].success


def test_unloadable_results_show_error(monkeypatch):
    def broken(root=None):
        raise OSError("disque indisponible")

    monkeypatch.setattr(ev, "load_official_results", broken)  # AppTest : même processus

    def app():
        from src.app.dashboard.comparison import show_official_evaluation

        show_official_evaluation()

    at = AppTest.from_function(app, default_timeout=30).run()
    assert_clean(at)
    assert "disque indisponible" in texts(at.error)


# ------------------------------------------- API historique show_model_comparison


def test_legacy_api_still_compares_valid_rows():
    at = run_legacy(legacy_scores())
    assert_clean(at)
    assert "MAE invalides exclues : 1" in texts(at.caption)
    (metrics,) = frames_with(at, "MAE macro (vélos/h)")
    assert metrics["Méthode"].tolist() == ["Forest", "Weekly"]
    assert "Forest" in texts(at.success)
    assert at.get("plotly_chart")


def test_legacy_api_filters_by_metadata():
    other = legacy_scores(snapshot_id="other_snapshot").iloc[[0]].assign(method_run_id="Other")
    scores = pd.concat([legacy_scores(), other], ignore_index=True)
    at = run_legacy(scores)
    selectbox = at.selectbox(key="model_comparison_snapshot_id")
    assert selectbox.options == ["demo_snapshot", "other_snapshot"]
    selectbox.select("other_snapshot").run()
    assert_clean(at)
    (metrics,) = frames_with(at, "MAE macro (vélos/h)")
    assert metrics["Méthode"].tolist() == ["Other"]
    assert "Au moins deux méthodes" in texts(at.info)


def test_legacy_api_refuses_incompatible_population_sizes():
    scores = legacy_scores()
    scores.loc[1, "n_compared_cases"] = 9
    at = run_legacy(scores)
    assert_clean(at)
    assert "Effectifs incohérents" in texts(at.error)
    assert not at.success and not at.get("plotly_chart")


def test_legacy_api_refuses_duplicated_method():
    scores = legacy_scores()
    scores.loc[2] = scores.loc[1]
    at = run_legacy(scores)
    assert_clean(at)
    assert "Populations incompatibles" in texts(at.error)


@pytest.mark.parametrize(
    ("scores", "message"),
    [
        (pd.DataFrame(), "Aucun résultat"),
        (legacy_scores().drop(columns="protocol_id"), "protocol_id"),
    ],
)
def test_legacy_api_reports_empty_or_invalid_input(scores, message):
    at = run_legacy(scores)
    assert_clean(at)
    assert message in texts([*at.info, *at.error])

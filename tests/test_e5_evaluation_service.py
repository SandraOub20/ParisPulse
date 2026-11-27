"""E5 — Tests du chargement des résultats officiels E4 (src/app/evaluation_service.py).

Les fichiers sont fabriqués dans un dossier temporaire au format exact de
``src/eval/backtest.py`` ; un test final relit les vrais fichiers livrés par E4.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.app import evaluation_service as ev

PERIOD = "20260630T22-20260830T22"
PROTOCOL = "proto-v1"
SNAPSHOT = "hist-test"


# --------------------------------------------------------------------------- fabriques


def population(team: str, budget: int | None = None, kind: str = "self") -> str:
    if team == "E2":
        return f"known_site_{PERIOD}_{kind}"
    return f"new_site_b{budget}_{PERIOD}_{kind}"


def score_row(team: str = "E3", budget: int | None = 24, **overrides) -> dict:
    row = {
        "experiment_id": ev.EXPERIMENTS[team],
        "scenario": ev.SCENARIOS[team],
        "temporal_split": "validation",
        "method_run_id": "e3-chronos-2-frozen-v1" if team == "E3" else "e2-mlp",
        "variant": "frozen" if team == "E3" else "mlp",
        "local_budget_hours": f"{float(budget)}" if team == "E3" and budget else "",
        "comparison_population_id": population(team, budget),
        "n_expected_cases": "10",
        "n_complete_cases": "9",
        "n_compared_cases": "8",
        "n_compared_hours": "190",
        "n_evaluable_counters": "2",
        "mae_macro": "21.5",
        "rmse": "40.0",
        "r2": "0.5",
        "bias": "-1.5",
        "coverage_24h": "0.9",
        "n_fallback_cases": "1.0",
        "protocol_id": PROTOCOL,
        "snapshot_id": SNAPSHOT,
    }
    row.update(overrides)
    return row


def coverage_rows(team: str, method: str, variant: str, budget: int | None, statuses) -> list[dict]:
    hours = {"complete": 24, "fallback_complete": 24, "partial": 12, "error": 0, "no_forecast": 0}
    rows = []
    for index, status in enumerate(statuses):
        rows.append(
            {
                "case_id": f"C{index}_{ev.SCENARIOS[team]}_b{budget}",
                "counter_id": f"C{index % 2}",
                "origin": "2026-06-30T22:00:00+00:00",
                "scenario": ev.SCENARIOS[team],
                "method_run_id": method,
                "variant": variant,
                "local_budget_hours": f"{float(budget)}" if budget else "",
                "coverage_status": status,
                "n_predicted_hours": str(hours[status]),
                "is_complete_24h": str(status in ev.COMPLETE_STATUSES),
                "status_reason": "",
                "protocol_id": PROTOCOL,
                "snapshot_id": SNAPSHOT,
            }
        )
    return rows


def default_coverage(team: str) -> list[dict]:
    """10 cas attendus : 8 complets, 1 complété par repli, 1 en erreur (comme score_row)."""
    statuses = ["complete"] * 8 + ["fallback_complete", "error"]
    if team == "E2":
        return coverage_rows("E2", "e2-mlp", "mlp", None, statuses)
    return coverage_rows("E3", "e3-chronos-2-frozen-v1", "frozen", 24, statuses)


def write_csv(path: Path, rows: list[dict], columns, *, newline: str = "\n") -> None:
    frame = pd.DataFrame(rows, columns=list(columns))
    path.write_bytes(frame.to_csv(index=False, lineterminator=newline).encode("utf-8"))


def write_team(
    root: Path,
    team: str,
    scores: list[dict] | None = None,
    coverage: list[dict] | None = None,
    *,
    manifest_overrides: dict | None = None,
    score_columns=ev.SCORE_COLUMNS,
    coverage_columns=ev.COVERAGE_COLUMNS,
) -> Path:
    folder = root / ev.EXPERIMENTS[team]
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / ev.SCORES_FILE, scores or [score_row(team)], score_columns)
    write_csv(folder / ev.COVERAGE_FILE, coverage or default_coverage(team), coverage_columns)
    manifest = {
        "experiment_id": ev.EXPERIMENTS[team],
        "protocol_id": PROTOCOL,
        "snapshot_id": SNAPSHOT,
        "outputs_sha256": {
            # Chemins Windows pour E3, comme dans la livraison réelle.
            (f"data\\evaluation\\{name}" if team == "E3" else f"data/evaluation/{name}"): sha(
                folder / name
            )
            for name in (ev.SCORES_FILE, ev.COVERAGE_FILE)
        },
        **(manifest_overrides or {}),
    }
    (folder / ev.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rehash(folder: Path) -> None:
    """Mettre à jour le manifeste après une modification volontaire d'un fichier."""
    path = folder / ev.MANIFEST_FILE
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["outputs_sha256"] = {
        name: sha(folder / name) for name in (ev.SCORES_FILE, ev.COVERAGE_FILE)
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def e3_three_budgets() -> list[dict]:
    rows = []
    for budget, mae in ((24, "26.1"), (72, "22.8"), (168, "19.7")):
        for kind in ("self", "common_complete"):
            rows.append(
                score_row(
                    "E3",
                    budget,
                    mae_macro=mae,
                    comparison_population_id=population("E3", budget, kind),
                    n_fallback_cases="0.0" if kind == "self" else "",
                )
            )
    return rows


def e3_three_budgets_coverage() -> list[dict]:
    statuses = ["complete"] * 8 + ["fallback_complete", "error"]
    rows = []
    for budget in ev.LOCAL_BUDGETS:
        rows += coverage_rows("E3", "e3-chronos-2-frozen-v1", "frozen", budget, statuses)
    return rows


# ----------------------------------------------------------- 1. fichiers manquants


def test_missing_scores_file_is_reported_explicitly(tmp_path):
    folder = write_team(tmp_path, "E3")
    (folder / ev.SCORES_FILE).unlink()
    with pytest.raises(FileNotFoundError, match="E3.*scores.csv"):
        ev.load_scores("E3", tmp_path)


def test_missing_coverage_and_manifest_are_reported(tmp_path):
    folder = write_team(tmp_path, "E2")
    (folder / ev.COVERAGE_FILE).unlink()
    with pytest.raises(FileNotFoundError, match="coverage.csv"):
        ev.load_coverage("E2", tmp_path)
    (folder / ev.MANIFEST_FILE).unlink()
    with pytest.raises(FileNotFoundError, match="scoring_manifest.json"):
        ev.load_scores("E2", tmp_path)


def test_missing_team_does_not_block_the_other(tmp_path):
    write_team(tmp_path, "E2")
    results = ev.load_official_results(tmp_path)
    assert set(results.teams) == {"E2"}
    assert "E3" in results.problems and "absent" in results.problems["E3"]
    empty = results.scores("E3")
    assert empty.empty and set(ev.SCORE_COLUMNS) <= set(empty.columns)


def test_unknown_team_is_refused(tmp_path):
    with pytest.raises(ValueError, match="Équipe inconnue"):
        ev.load_scores("E4", tmp_path)


# ---------------------------------------------------------- 2. colonnes et types


@pytest.mark.parametrize("dropped", ["mae_macro", "comparison_population_id", "snapshot_id"])
def test_missing_score_column_is_refused(tmp_path, dropped):
    columns = [c for c in ev.SCORE_COLUMNS if c != dropped]
    write_team(tmp_path, "E3", score_columns=columns)
    with pytest.raises(ev.EvaluationDataError, match=f"colonnes manquantes.*{dropped}"):
        ev.load_scores("E3", tmp_path)


def test_missing_coverage_column_is_refused(tmp_path):
    columns = [c for c in ev.COVERAGE_COLUMNS if c != "is_complete_24h"]
    write_team(tmp_path, "E3", coverage_columns=columns)
    with pytest.raises(ev.EvaluationDataError, match="is_complete_24h"):
        ev.load_coverage("E3", tmp_path)


def test_numeric_columns_are_typed(tmp_path):
    write_team(tmp_path, "E3")
    scores = ev.load_scores("E3", tmp_path)
    integers = ("n_expected_cases", "n_compared_cases", "n_fallback_cases", "local_budget_hours")
    for column in integers:
        assert str(scores[column].dtype) == "Int64"
    for column in ("mae_macro", "rmse", "r2", "bias", "coverage_24h"):
        assert scores[column].dtype == np.float64
    row = scores.iloc[0]
    assert row["local_budget_hours"] == 24 and row["n_fallback_cases"] == 1
    assert row["mae_macro"] == pytest.approx(21.5)


@pytest.mark.parametrize(
    ("column", "value"),
    [("n_expected_cases", "dix"), ("n_compared_hours", "12.5"), ("coverage_24h", "1.2")],
)
def test_invalid_counts_or_coverage_are_refused(tmp_path, column, value):
    write_team(tmp_path, "E3", [score_row(**{column: value})])
    with pytest.raises(ev.EvaluationDataError, match=column):
        ev.load_scores("E3", tmp_path)


def test_required_count_cannot_be_empty(tmp_path):
    write_team(tmp_path, "E3", [score_row(n_compared_cases="")])
    with pytest.raises(ev.EvaluationDataError, match="n_compared_cases vide"):
        ev.load_scores("E3", tmp_path)


def test_more_complete_cases_than_expected_is_refused(tmp_path):
    write_team(tmp_path, "E3", [score_row(n_complete_cases="11")])
    with pytest.raises(ev.EvaluationDataError, match="plus de cas"):
        ev.load_scores("E3", tmp_path)


# --------------------------------------------------- 3. MAE invalide / valeurs manquantes


@pytest.mark.parametrize("value", ["abc", "inf", "-inf", "-0.5", "nan"])
def test_invalid_mae_is_refused(tmp_path, value):
    write_team(tmp_path, "E3", [score_row(mae_macro=value)])
    with pytest.raises(ev.EvaluationDataError, match="mae_macro"):
        ev.load_scores("E3", tmp_path)


def test_missing_mae_stays_missing_when_no_hour_is_evaluable(tmp_path):
    row = score_row(
        mae_macro="", rmse="", r2="", bias="", n_compared_hours="0", n_compared_cases="0"
    )
    write_team(tmp_path, "E3", [row])
    scores = ev.load_scores("E3", tmp_path)
    for column in ("mae_macro", "rmse", "r2", "bias"):
        assert np.isnan(scores.loc[0, column])
        assert scores.loc[0, column] != 0


def test_missing_mae_with_evaluable_hours_is_refused(tmp_path):
    write_team(tmp_path, "E3", [score_row(mae_macro="")])
    with pytest.raises(ev.EvaluationDataError, match="mae_macro incohérente"):
        ev.load_scores("E3", tmp_path)


def test_empty_fallback_count_stays_missing(tmp_path):
    rows = [
        score_row(),
        score_row(
            comparison_population_id=population("E3", 24, "common_complete"),
            n_fallback_cases="",
        ),
    ]
    write_team(tmp_path, "E3", rows)
    scores = ev.load_scores("E3", tmp_path)
    common = scores.loc[scores["population_kind"].eq("common_complete")].iloc[0]
    assert pd.isna(common["n_fallback_cases"])
    assert scores["n_fallback_cases"].isna().sum() == 1


# ------------------------------------------- 4. séparation E2 / E3 et métadonnées


def test_e2_and_e3_are_loaded_separately(tmp_path):
    write_team(tmp_path, "E2")
    write_team(tmp_path, "E3")
    results = ev.load_official_results(tmp_path)
    assert results.problems == {}
    e2, e3 = results.scores("E2"), results.scores("E3")
    assert e2["team"].eq("E2").all() and e2["scenario"].eq("known_site").all()
    assert e3["team"].eq("E3").all() and e3["scenario"].eq("new_site").all()
    assert e2["local_budget_hours"].isna().all()
    assert e3["local_budget_hours"].notna().all()


@pytest.mark.parametrize(
    ("team", "overrides", "message"),
    [
        ("E3", {"scenario": "known_site"}, "scénario"),
        ("E2", {"experiment_id": "EXP-E3"}, "experiment_id"),
        ("E3", {"snapshot_id": "autre"}, "snapshot_id différent"),
        ("E3", {"protocol_id": "proto-v2"}, "protocol_id différent"),
        ("E3", {"temporal_split": ""}, "identifiants vides"),
    ],
)
def test_rows_from_another_team_or_protocol_are_refused(tmp_path, team, overrides, message):
    write_team(tmp_path, team, [score_row(team, **overrides)])
    with pytest.raises(ev.EvaluationDataError, match=message):
        ev.load_scores(team, tmp_path)


def test_comparison_metadata_are_preserved(tmp_path):
    write_team(tmp_path, "E3", e3_three_budgets())
    scores = ev.load_scores("E3", tmp_path)
    assert set(ev.COMPARISON_METADATA) <= set(scores.columns)
    row = scores.iloc[0]
    assert (row["scenario"], row["temporal_split"], row["protocol_id"], row["snapshot_id"]) == (
        "new_site",
        "validation",
        PROTOCOL,
        SNAPSHOT,
    )
    assert set(scores["population_kind"]) == {"self", "common_complete"}
    groups = ev.comparison_groups(scores)
    assert len(groups) == 6 and groups["n_methods"].eq(1).all()


def test_duplicated_score_rows_are_refused(tmp_path):
    write_team(tmp_path, "E3", [score_row(), score_row(mae_macro="30")])
    with pytest.raises(ev.EvaluationDataError, match="plusieurs scores"):
        ev.load_scores("E3", tmp_path)


def test_unknown_population_kind_is_refused(tmp_path):
    write_team(tmp_path, "E3", [score_row(comparison_population_id=f"new_site_b24_{PERIOD}_all")])
    with pytest.raises(ev.EvaluationDataError, match="Population de comparaison inconnue"):
        ev.load_scores("E3", tmp_path)


# --------------------------------------------------------- 5. budgets E3


@pytest.mark.parametrize(("budget", "mae"), [(24, 26.1), (72, 22.8), (168, 19.7)])
def test_filter_budget_keeps_only_requested_budget(tmp_path, budget, mae):
    write_team(tmp_path, "E3", e3_three_budgets(), e3_three_budgets_coverage())
    scores = ev.load_scores("E3", tmp_path)
    assert ev.available_budgets(scores) == [24, 72, 168]
    selected = ev.filter_budget(scores, budget)
    assert len(selected) == 2
    assert selected["local_budget_hours"].eq(budget).all()
    assert selected["comparison_population_id"].str.contains(f"_b{budget}_").all()
    assert selected["mae_macro"].tolist() == [mae, mae]

    coverage = ev.filter_budget(ev.load_coverage("E3", tmp_path), budget)
    assert len(coverage) == 10 and coverage["local_budget_hours"].eq(budget).all()


def test_filter_budget_refuses_unknown_budget_and_e2(tmp_path):
    write_team(tmp_path, "E2")
    write_team(tmp_path, "E3", e3_three_budgets())
    with pytest.raises(ValueError, match="Budget 48 h inconnu"):
        ev.filter_budget(ev.load_scores("E3", tmp_path), 48)
    with pytest.raises(ValueError, match="qu'aux résultats E3"):
        ev.filter_budget(ev.load_scores("E2", tmp_path), 24)


@pytest.mark.parametrize(
    ("team", "overrides", "message"),
    [
        (
            "E3",
            {"local_budget_hours": "48.0", "comparison_population_id": population("E3", 48)},
            "budget E3",
        ),
        ("E3", {"local_budget_hours": ""}, "budget E3"),
        ("E2", {"local_budget_hours": "24.0"}, "E2 ne déclare pas"),
        ("E3", {"comparison_population_id": population("E3", 72)}, "sans le budget déclaré"),
    ],
)
def test_inconsistent_budgets_in_scores_are_refused(tmp_path, team, overrides, message):
    write_team(tmp_path, team, [score_row(team, **overrides)])
    with pytest.raises(ev.EvaluationDataError, match=message):
        ev.load_scores(team, tmp_path)


# --------------------------------------------------- 6. intégrité / manifeste


def test_modified_file_is_refused_unless_verification_disabled(tmp_path):
    folder = write_team(tmp_path, "E3")
    path = folder / ev.SCORES_FILE
    path.write_text(path.read_text().replace("21.5", "1.0"))
    with pytest.raises(ev.EvaluationDataError, match="empreinte du manifeste"):
        ev.load_scores("E3", tmp_path)
    assert ev.verify_outputs("E3", tmp_path)[ev.SCORES_FILE] == "modifié"
    assert ev.load_scores("E3", tmp_path, verify=False)["mae_macro"].iloc[0] == 1.0


def test_line_endings_converted_by_git_are_accepted(tmp_path):
    folder = write_team(tmp_path, "E2")
    path = folder / ev.SCORES_FILE
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))  # hash du manifeste en LF
    assert ev.verify_outputs("E2", tmp_path)[ev.SCORES_FILE] == "conforme"
    assert len(ev.load_scores("E2", tmp_path)) == 1


def test_manifest_of_another_experiment_is_refused(tmp_path):
    write_team(tmp_path, "E2", manifest_overrides={"experiment_id": "EXP-E3"})
    with pytest.raises(ev.EvaluationDataError, match="experiment_id"):
        ev.load_manifest("E2", tmp_path)


# ------------------------------------------------------------- 7. couverture


def test_coverage_summary_distinguishes_predicted_complete_and_evaluable(tmp_path):
    statuses = ["complete"] * 6 + ["fallback_complete", "partial", "error", "no_forecast"]
    coverage = coverage_rows("E3", "e3-chronos-2-frozen-v1", "frozen", 24, statuses)
    scores = [score_row(n_complete_cases="7", n_compared_cases="6", coverage_24h="0.7")]
    write_team(tmp_path, "E3", scores, coverage)

    summary = ev.load_team_results("E3", tmp_path).coverage_summary()

    (row,) = summary.to_dict("records")
    assert row["n_expected_cases"] == 10 and row["n_coverage_cases"] == 10
    assert row["n_predicted_cases"] == 8  # 6 complets + 1 repli + 1 partiel
    assert row["n_complete_cases"] == 7  # repli compris, partiel exclu
    assert row["n_fallback_complete_cases"] == 1
    assert (row["n_partial_cases"], row["n_error_cases"], row["n_no_forecast_cases"]) == (1, 1, 1)
    assert row["n_evaluable_cases"] == 6  # repris de scores.csv, jamais recalculé
    assert row["coverage_24h"] == pytest.approx(0.7)
    assert row["matches_scores"] is True
    assert row["comparison_population_id"] == population("E3", 24)


def test_coverage_summary_flags_disagreement_with_scores(tmp_path):
    write_team(tmp_path, "E3", [score_row(n_complete_cases="10")])
    summary = ev.load_team_results("E3", tmp_path).coverage_summary()
    assert not summary["matches_scores"].iloc[0]


def test_coverage_summary_is_split_by_budget(tmp_path):
    write_team(tmp_path, "E3", e3_three_budgets(), e3_three_budgets_coverage())
    summary = ev.load_team_results("E3", tmp_path).coverage_summary()
    assert summary["local_budget_hours"].tolist() == [24, 72, 168]
    assert summary["matches_scores"].all()
    assert summary["n_coverage_cases"].eq(10).all()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"coverage_status": "done"}, "coverage_status inconnu"),
        ({"is_complete_24h": "maybe"}, "True ou False"),
        ({"is_complete_24h": "False"}, "incohérents"),
        ({"n_predicted_hours": "23"}, "incohérents"),
        ({"n_predicted_hours": "25"}, "supérieur"),
        ({"snapshot_id": "autre"}, "snapshot_id différent"),
    ],
)
def test_invalid_coverage_rows_are_refused(tmp_path, overrides, message):
    coverage = default_coverage("E3")
    coverage[0].update(overrides)
    write_team(tmp_path, "E3", coverage=coverage)
    with pytest.raises(ev.EvaluationDataError, match=message):
        ev.load_coverage("E3", tmp_path)


# ------------------------------------------- 8. fonctions pour comparison.py


def test_select_population_and_ranking(tmp_path):
    rows = [
        score_row(method_run_id="e3-chronos-2-frozen-v1", mae_macro="22.8"),
        score_row(method_run_id="e3-google-TimesFM_2.5-frozen-v1", mae_macro="20.0"),
        score_row(
            method_run_id="e3-empty",
            mae_macro="",
            rmse="",
            r2="",
            bias="",
            n_compared_hours="0",
            n_compared_cases="0",
        ),
        score_row(comparison_population_id=population("E3", 24, "common_complete")),
    ]
    write_team(tmp_path, "E3", rows)
    scores = ev.load_scores("E3", tmp_path)

    selected = ev.select_population(scores, population("E3", 24))
    assert len(selected) == 3
    ranked = ev.ranked_methods(selected)
    assert ranked["method_run_id"].tolist() == [
        "e3-google-TimesFM_2.5-frozen-v1",
        "e3-chronos-2-frozen-v1",
        "e3-empty",
    ]
    assert np.isnan(ranked["mae_macro"].iloc[-1])

    with pytest.raises(ValueError, match="absente"):
        ev.select_population(scores, population("E3", 168))


def test_select_population_refuses_mixed_metadata():
    base = {**score_row(), "population_kind": "self", "team": "E3"}
    scores = pd.DataFrame([base, {**base, "method_run_id": "other", "snapshot_id": "autre"}])
    with pytest.raises(ev.EvaluationDataError, match="plusieurs snapshot_id"):
        ev.select_population(scores, population("E3", 24))
    duplicated = pd.DataFrame([base, base])
    with pytest.raises(ev.EvaluationDataError, match="méthode en double"):
        ev.select_population(duplicated, population("E3", 24))


# ------------------------------------------------- fichiers réellement livrés par E4


REAL_ROOT = ev.experiment_dir("E2").parent


@pytest.mark.skipif(
    not all((REAL_ROOT / ev.EXPERIMENTS[t] / ev.SCORES_FILE).is_file() for t in ev.TEAMS),
    reason="résultats officiels E4 absents",
)
def test_official_e4_files_load_and_agree():
    results = ev.load_official_results()
    assert results.problems == {}
    e2, e3 = results.scores("E2"), results.scores("E3")
    assert e2["scenario"].eq("known_site").all() and e3["scenario"].eq("new_site").all()
    assert set(ev.available_budgets(e3)) <= set(ev.LOCAL_BUDGETS)
    # Les populations communes n'ont pas de nombre de replis : il reste absent, pas 0.
    common = e2.loc[e2["population_kind"].eq("common_complete"), "n_fallback_cases"]
    assert common.isna().all()
    for team in ev.TEAMS:
        assert results.teams[team].coverage_summary()["matches_scores"].all()

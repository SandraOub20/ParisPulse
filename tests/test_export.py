"""Tests du module d'export E5 (src/app/export.py).

Règle centrale vérifiée : aucune observation cible ni aucun score
n'est exporté avant la révélation.
"""

import csv
import json
from datetime import datetime

import pytest

from src.app.export import (
    CASE_RUN_COLUMNS,
    COVERAGE_COLUMNS,
    FORECAST_COLUMNS,
    SCORE_COLUMNS,
    _csv_value,
    _safe_experiment_id,
    export_study,
)

EXPERIMENT_ID = "EXP-001"


# --------------------------------------------------------------------------
# Données de test (synthétiques, séparées des données réelles)
# --------------------------------------------------------------------------


def make_forecasts(n: int = 24) -> list[dict]:
    return [
        {
            "case_id": "case_A",
            "method_run_id": "ref_v1",
            "counter_id": "PARIS_01",
            "origin": "2026-07-01T22:00:00+00:00",
            "scenario": "known_site",
            "horizon": h,
            "y_pred": 100.5 + h,
            "variant": "reference",
            "prediction_status": "ok",
            "status_reason": None,
        }
        for h in range(1, n + 1)
    ]


def make_coverage() -> list[dict]:
    return [
        {
            "case_id": "case_A",
            "counter_id": "PARIS_01",
            "method_run_id": "ref_v1",
            "coverage_status": "complete",
            "n_predicted_hours": 24,
            "is_complete_24h": True,
        }
    ]


def make_case_runs() -> list[dict]:
    return [
        {
            "case_id": "case_A",
            "method_run_id": "ref_v1",
            "status": "ok",
            "inference_seconds": 0.12,
            "cache_hit": False,
            "memory_mb": None,
        }
    ]


def make_observations() -> list[dict]:
    return [
        {"counter_id": "PARIS_01", "timestamp": "2026-07-01T22:00:00+00:00", "count": 0.0},
        {"counter_id": "PARIS_01", "timestamp": "2026-07-01T23:00:00+00:00", "count": None},
    ]


def make_scores() -> list[dict]:
    return [
        {
            "experiment_id": EXPERIMENT_ID,
            "scenario": "known_site",
            "method_run_id": "ref_v1",
            "n_expected_cases": 1,
            "n_complete_cases": 1,
            "mae_macro": 12.3,
        }
    ]


def read_csv(path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def read_manifest(export_dir) -> dict:
    return json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))


def export_hidden(tmp_path, **kwargs):
    return export_study(
        EXPERIMENT_ID,
        forecasts=make_forecasts(),
        coverage=make_coverage(),
        case_runs=make_case_runs(),
        output_root=tmp_path,
        **kwargs,
    )


def export_revealed(tmp_path, **kwargs):
    params = {"scores": make_scores(), "observations": make_observations()}
    params.update(kwargs)
    return export_study(
        EXPERIMENT_ID,
        forecasts=make_forecasts(),
        coverage=make_coverage(),
        case_runs=make_case_runs(),
        revealed=True,
        output_root=tmp_path,
        **params,
    )


# --------------------------------------------------------------------------
# Conversion des valeurs CSV
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (True, "true"),
        (False, "false"),
        (["missing", "zero_run"], '["missing", "zero_run"]'),
        ({"a": 1}, '{"a": 1}'),
        (("x",), '["x"]'),
        (0, 0),
        (0.0, 0.0),
        ("texte", "texte"),
    ],
)
def test_csv_value_respecte_le_contrat(value, expected):
    assert _csv_value(value) == expected


def test_csv_value_conserve_les_accents_en_json():
    assert _csv_value(["créneau"]) == '["créneau"]'


# --------------------------------------------------------------------------
# Sécurité de l'identifiant d'expérience
# --------------------------------------------------------------------------


@pytest.mark.parametrize("experiment_id", ["EXP-001", "exp_2.v3", "A"])
def test_identifiant_valide_accepte(experiment_id):
    assert _safe_experiment_id(experiment_id) == experiment_id


@pytest.mark.parametrize(
    "experiment_id",
    ["", ".", "..", "../evil", "a/b", "a\\b", "C:evil", "exp 1", "exp\n1"],
)
def test_identifiant_dangereux_refuse(experiment_id):
    with pytest.raises(ValueError):
        _safe_experiment_id(experiment_id)


def test_export_refuse_un_chemin_hors_du_dossier(tmp_path):
    root = tmp_path / "exports"
    with pytest.raises(ValueError):
        export_study(
            "../evil",
            forecasts=[],
            coverage=[],
            case_runs=[],
            output_root=root,
        )
    assert not (tmp_path / "evil").exists()


# --------------------------------------------------------------------------
# Export avant révélation
# --------------------------------------------------------------------------


def test_avant_revelation_fichiers_attendus(tmp_path):
    export_dir = export_hidden(tmp_path)

    assert export_dir == tmp_path / EXPERIMENT_ID
    assert (export_dir / "forecasts.csv").is_file()
    assert (export_dir / "coverage.csv").is_file()
    assert (export_dir / "case_runs.csv").is_file()
    assert (export_dir / "manifest.json").is_file()


def test_avant_revelation_ni_observations_ni_scores(tmp_path):
    # Même si l'appelant transmet des cibles par erreur, elles ne sortent pas.
    export_dir = export_hidden(
        tmp_path,
        scores=make_scores(),
        observations=make_observations(),
    )

    assert not (export_dir / "observations.csv").exists()
    assert not (export_dir / "scores.csv").exists()

    manifest = read_manifest(export_dir)
    assert manifest["revealed"] is False
    assert "observations.csv" not in manifest["files"]
    assert "scores.csv" not in manifest["files"]


def test_avant_revelation_seuls_les_fichiers_autorises(tmp_path):
    export_dir = export_hidden(tmp_path, observations=make_observations())

    assert sorted(p.name for p in export_dir.iterdir()) == [
        "case_runs.csv",
        "coverage.csv",
        "forecasts.csv",
        "manifest.json",
    ]


def test_masquer_supprime_un_export_revele_precedent(tmp_path):
    export_dir = export_revealed(tmp_path)
    assert (export_dir / "observations.csv").exists()
    assert (export_dir / "scores.csv").exists()

    export_hidden(tmp_path)

    assert not (export_dir / "observations.csv").exists()
    assert not (export_dir / "scores.csv").exists()
    assert read_manifest(export_dir)["revealed"] is False


# --------------------------------------------------------------------------
# Export après révélation
# --------------------------------------------------------------------------


def test_apres_revelation_observations_et_scores_exportes(tmp_path):
    export_dir = export_revealed(tmp_path)

    columns, rows = read_csv(export_dir / "observations.csv")
    assert columns == ["counter_id", "timestamp", "count"]
    assert len(rows) == 2
    # Le zéro observé reste distinct du manque.
    assert rows[0]["count"] == "0.0"
    assert rows[1]["count"] == ""

    columns, rows = read_csv(export_dir / "scores.csv")
    assert columns == SCORE_COLUMNS
    assert rows[0]["mae_macro"] == "12.3"
    assert rows[0]["rmse"] == ""

    manifest = read_manifest(export_dir)
    assert manifest["revealed"] is True
    assert manifest["files"] == [
        "forecasts.csv",
        "coverage.csv",
        "case_runs.csv",
        "observations.csv",
        "scores.csv",
    ]


def test_apres_revelation_previsions_inchangees(tmp_path):
    hidden_dir = export_hidden(tmp_path / "hidden")
    revealed_dir = export_revealed(tmp_path / "revealed")

    hidden = (hidden_dir / "forecasts.csv").read_bytes()
    revealed = (revealed_dir / "forecasts.csv").read_bytes()
    assert hidden == revealed


@pytest.mark.parametrize(
    "missing",
    [{"scores": None}, {"observations": None}, {"scores": None, "observations": None}],
)
def test_revelation_sans_observations_ou_scores_refusee(tmp_path, missing):
    with pytest.raises(ValueError):
        export_revealed(tmp_path, **missing)


def test_revelation_avec_observations_vides(tmp_path):
    export_dir = export_revealed(tmp_path, observations=[])

    assert not (export_dir / "observations.csv").exists()
    assert (export_dir / "scores.csv").exists()
    manifest = read_manifest(export_dir)
    assert "observations.csv" not in manifest["files"]
    assert "scores.csv" in manifest["files"]


# --------------------------------------------------------------------------
# Contenu des CSV
# --------------------------------------------------------------------------


def test_previsions_24_lignes_et_colonnes_du_contrat(tmp_path):
    export_dir = export_hidden(tmp_path)

    columns, rows = read_csv(export_dir / "forecasts.csv")
    assert columns == FORECAST_COLUMNS
    assert len(rows) == 24
    assert [int(r["horizon"]) for r in rows] == list(range(1, 25))
    assert rows[0]["y_pred"] == "101.5"  # non arrondi
    assert rows[0]["status_reason"] == ""  # None -> cellule vide
    assert rows[0]["model_run_id"] == ""  # colonne absente -> cellule vide


def test_en_tetes_coverage_et_case_runs(tmp_path):
    export_dir = export_hidden(tmp_path)

    columns, rows = read_csv(export_dir / "coverage.csv")
    assert columns == COVERAGE_COLUMNS
    assert rows[0]["is_complete_24h"] == "true"

    columns, rows = read_csv(export_dir / "case_runs.csv")
    assert columns == CASE_RUN_COLUMNS
    assert rows[0]["cache_hit"] == "false"
    assert rows[0]["memory_mb"] == ""


def test_colonnes_hors_contrat_ignorees(tmp_path):
    forecasts = make_forecasts()
    forecasts[0]["y_true"] = 999  # une cible glissée par erreur

    export_dir = export_study(
        EXPERIMENT_ID,
        forecasts=forecasts,
        coverage=[],
        case_runs=[],
        output_root=tmp_path,
    )

    columns, _ = read_csv(export_dir / "forecasts.csv")
    assert "y_true" not in columns
    assert "999" not in (export_dir / "forecasts.csv").read_text(encoding="utf-8")


def test_listes_vides_donnent_un_csv_avec_en_tete(tmp_path):
    export_dir = export_study(
        EXPERIMENT_ID,
        forecasts=[],
        coverage=[],
        case_runs=[],
        output_root=tmp_path,
    )

    columns, rows = read_csv(export_dir / "forecasts.csv")
    assert columns == FORECAST_COLUMNS
    assert rows == []


def test_encodage_utf8(tmp_path):
    forecasts = make_forecasts(1)
    forecasts[0]["status_reason"] = "historique trop court — repli"

    export_dir = export_study(
        EXPERIMENT_ID,
        forecasts=forecasts,
        coverage=[],
        case_runs=[],
        output_root=tmp_path,
    )

    _, rows = read_csv(export_dir / "forecasts.csv")
    assert rows[0]["status_reason"] == "historique trop court — repli"


# --------------------------------------------------------------------------
# Manifeste
# --------------------------------------------------------------------------


def test_manifeste_contenu_minimal(tmp_path):
    export_dir = export_hidden(tmp_path)
    manifest = read_manifest(export_dir)

    assert manifest["schema_version"] == 2
    assert manifest["experiment_id"] == EXPERIMENT_ID
    assert manifest["files"] == ["forecasts.csv", "coverage.csv", "case_runs.csv"]

    exported_at = datetime.fromisoformat(manifest["exported_at"])
    assert exported_at.utcoffset() is not None
    assert exported_at.utcoffset().total_seconds() == 0


def test_manifeste_conserve_la_provenance(tmp_path):
    export_dir = export_hidden(
        tmp_path,
        manifest={"snapshot_id": "snap_2026-11-10", "protocol_id": "proto_v1"},
    )
    manifest = read_manifest(export_dir)

    assert manifest["snapshot_id"] == "snap_2026-11-10"
    assert manifest["protocol_id"] == "proto_v1"


def test_manifeste_ne_peut_pas_mentir_sur_la_revelation(tmp_path):
    # Les champs fournis par l'appelant ne remplacent pas l'état réel de l'export.
    export_dir = export_hidden(
        tmp_path,
        manifest={"revealed": True, "files": ["scores.csv"], "experiment_id": "autre"},
    )
    manifest = read_manifest(export_dir)

    assert manifest["revealed"] is False
    assert manifest["experiment_id"] == EXPERIMENT_ID
    assert "scores.csv" not in manifest["files"]


def test_manifeste_appelant_non_modifie(tmp_path):
    original = {"snapshot_id": "snap"}
    export_hidden(tmp_path, manifest=original)
    assert original == {"snapshot_id": "snap"}

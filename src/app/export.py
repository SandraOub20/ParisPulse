"""Export des résultats d'une étude ParisPulse.

Les observations et les scores ne sont exportés qu'après révélation.
Les prévisions restent indépendantes de la révélation.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

FORECAST_COLUMNS = [
    "case_id",
    "method_run_id",
    "model_run_id",
    "counter_id",
    "origin",
    "scenario",
    "horizon",
    "target_timestamp",
    "y_pred",
    "variant",
    "method_used",
    "prediction_status",
    "status_reason",
    "fit_cutoff",
    "support_id",
    "adaptation_id",
    "snapshot_id",
    "context_version",
    "protocol_id",
    "feature_version",
]

COVERAGE_COLUMNS = [
    "case_id",
    "counter_id",
    "origin",
    "scenario",
    "method_run_id",
    "local_budget_hours",
    "coverage_status",
    "n_predicted_hours",
    "is_complete_24h",
    "status_reason",
    "protocol_id",
    "snapshot_id",
]

CASE_RUN_COLUMNS = [
    "case_id",
    "method_run_id",
    "model_run_id",
    "status",
    "status_reason",
    "preparation_seconds",
    "inference_seconds",
    "adaptation_seconds",
    "wait_seconds",
    "cache_hit",
    "memory_mb",
    "hardware",
    "protocol_id",
    "snapshot_id",
]

SCORE_COLUMNS = [
    "experiment_id",
    "scenario",
    "temporal_split",
    "method_run_id",
    "comparison_population_id",
    "n_expected_cases",
    "n_complete_cases",
    "n_compared_cases",
    "n_compared_hours",
    "n_evaluable_counters",
    "mae_macro",
    "rmse",
    "bias",
    "coverage_24h",
    "n_fallback_cases",
    "protocol_id",
    "snapshot_id",
]


def _write_csv(
    path: Path,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Écrit un CSV UTF-8 avec les colonnes du contrat."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )
        writer.writeheader()

        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})


def _csv_value(value: Any) -> Any:
    """Convertit les valeurs en respectant le format CSV du contrat."""
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)

    return value


def _safe_experiment_id(experiment_id: str) -> str:
    """Évite les chemins arbitraires dans le nom du dossier."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", experiment_id):
        raise ValueError("experiment_id contient des caractères non autorisés.")

    if experiment_id in {".", ".."}:
        raise ValueError("experiment_id invalide.")

    return experiment_id


def export_study(
    experiment_id: str,
    forecasts: Sequence[Mapping[str, Any]],
    coverage: Sequence[Mapping[str, Any]],
    case_runs: Sequence[Mapping[str, Any]],
    scores: Sequence[Mapping[str, Any]] | None = None,
    observations: Sequence[Mapping[str, Any]] | None = None,
    revealed: bool = False,
    manifest: Mapping[str, Any] | None = None,
    output_root: str | Path | None = None,
) -> Path:
    """Exporte une étude ParisPulse dans artifacts/exports/.

    Les prévisions, couvertures et exécutions sont toujours exportées.
    Les observations et les scores sont exportés uniquement si revealed=True.

    Args:
        experiment_id: Identifiant de l'étude.
        forecasts: Lignes conformes au schéma forecasts.csv.
        coverage: Lignes conformes au schéma coverage.csv.
        case_runs: Lignes conformes au schéma case_runs.csv.
        scores: Scores calculés par le module d'évaluation E4.
        observations: Observations cibles autorisées après révélation.
        revealed: Indique si les observations cibles ont été révélées.
        manifest: Métadonnées et provenance de l'étude.
        output_root: Dossier de sortie personnalisé (utile pour les tests).

    Returns:
        Le chemin du dossier d'export créé.
    """
    experiment_id = _safe_experiment_id(experiment_id)

    if output_root is None:
        output_root = Path(__file__).resolve().parents[2] / "artifacts" / "exports"

    export_dir = Path(output_root) / experiment_id
    export_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        export_dir / "forecasts.csv",
        FORECAST_COLUMNS,
        forecasts,
    )

    _write_csv(
        export_dir / "coverage.csv",
        COVERAGE_COLUMNS,
        coverage,
    )

    _write_csv(
        export_dir / "case_runs.csv",
        CASE_RUN_COLUMNS,
        case_runs,
    )

    if revealed:
        if observations is None or scores is None:
            raise ValueError(
                "Les observations et les scores doivent être fournis "
                "pour un export après révélation."
            )

        observation_columns = list(observations[0].keys()) if observations else []
        if observation_columns:
            _write_csv(
                export_dir / "observations.csv",
                observation_columns,
                observations,
            )

        _write_csv(
            export_dir / "scores.csv",
            SCORE_COLUMNS,
            scores,
        )

    else:
        # Ne jamais laisser subsister des données révélées d'un export précédent.
        for filename in ("observations.csv", "scores.csv"):
            old_file = export_dir / filename
            if old_file.exists():
                old_file.unlink()

    manifest_data = dict(manifest or {})
    manifest_data.update(
        {
            "schema_version": 2,
            "experiment_id": experiment_id,
            "revealed": revealed,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "files": [
                "forecasts.csv",
                "coverage.csv",
                "case_runs.csv",
            ],
        }
    )

    if revealed:
        if observations:
            manifest_data["files"].append("observations.csv")
        manifest_data["files"].append("scores.csv")

    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return export_dir

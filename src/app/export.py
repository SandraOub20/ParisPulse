"""Assembler une étude téléchargeable et sa provenance.

Deux points d'entrée :
- ``study_zip`` : archive .zip téléchargée depuis l'interface Streamlit ;
- ``export_study`` : export sur disque aux colonnes du contrat (doc/CONTRATS.md).

Les observations et les scores ne sont exportés qu'après révélation.
Les prévisions restent indépendantes de la révélation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from src.app.service import VALID_STATUSES, Study
from src.eval.cases import case_csv, forecasting_team


def study_summary(study: Study, evaluation: dict | None) -> dict:
    forecast = study.forecast
    coverage = forecast["prediction_status"].value_counts().to_dict()
    manifest = {
        "source": study.source,
        "method_run_id": forecast["method_run_id"].iloc[0],
        "publication_lag_hours": study.publication_lag_hours,
        "forecast_hours": int(forecast["prediction_status"].isin(VALID_STATUSES).sum()),
        "expected_hours": len(forecast),
        "status_counts": coverage,
    }
    if evaluation is not None:
        manifest["evaluation"] = {
            "scope": "Contrôle local sur ce cas",
            "mae_bikes_per_hour": evaluation["mae"],
            "compared_hours": evaluation["n_compared_hours"],
            "reason": evaluation["reason"],
        }
    return manifest


def csv_text(tables: list[pd.DataFrame]) -> str:
    return "".join(
        table.to_csv(index=False, header=index == 0) for index, table in enumerate(tables)
    )


def case_scores_csv(scored: list[tuple[Study, dict]]) -> str:
    """Score local du cas, une ligne par méthode, aux colonnes SCORE_COLUMNS du contrat.

    Un seul compteur : la MAE du compteur est aussi sa moyenne entre compteurs. Ce n'est
    pas le score E4 du protocole, d'où ``comparison_population_id = case:<case_id>``.
    """
    rows = []
    for item, score in scored:
        errors = score["errors"]
        valid = errors.loc[errors["is_scoreable"].eq(True)]
        n = len(valid)
        forecast = item.forecast
        n_valid = int(forecast["prediction_status"].isin(VALID_STATUSES).sum())
        rows.append(
            {
                "experiment_id": "",
                "scenario": item.case.scenario,
                "temporal_split": item.case.temporal_split,
                "method_run_id": forecast["method_run_id"].iloc[0],
                "comparison_population_id": f"case:{item.case.case_id}",
                "n_expected_cases": 1,
                "n_complete_cases": int(n_valid == len(forecast) == 24),
                "n_compared_cases": int(n > 0),
                "n_compared_hours": n,
                "n_evaluable_counters": int(n > 0),
                "mae_macro": score["mae"],
                "rmse": math.sqrt(valid["squared_error"].mean()) if n else None,
                "bias": float(valid["signed_error"].mean()) if n else None,
                "coverage_24h": n_valid / 24,
                "n_fallback_cases": int(forecast["prediction_status"].eq("fallback").any()),
                "protocol_id": item.case.protocol_id,
                "snapshot_id": item.case.snapshot_id,
            }
        )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=SCORE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_value(row.get(column)) for column in SCORE_COLUMNS})
    return buffer.getvalue()


def study_zip(
    study: Study,
    evaluation: dict | None = None,
    *,
    alternatives: tuple[tuple[Study, dict | None], ...] = (),
) -> bytes:
    manifest = {
        "application": "ParisPulse V2",
        "case": asdict(study.case),
        "forecasting_team": forecasting_team(study.case),
        "targets_revealed": evaluation is not None,
        **study_summary(study, evaluation),
    }
    if alternatives:
        manifest["other_methods"] = [
            study_summary(item, score if evaluation is not None else None)
            for item, score in alternatives
        ]
    studies = [study, *(item for item, _ in alternatives)]
    runs = [item.runs for item in studies if not item.runs.empty]
    files: dict[str, str] = {
        "forecasts.csv": csv_text([item.forecast for item in studies]),
        "cases.csv": case_csv(study.case),
    }
    if runs:
        files["case_runs.csv"] = csv_text(runs)
    if evaluation is not None:
        scored = [(study, evaluation), *((item, s) for item, s in alternatives if s is not None)]
        files["observations.csv"] = evaluation["observations"].to_csv(index=False)
        files["errors.csv"] = csv_text([score["errors"] for _, score in scored])
        files["scores.csv"] = case_scores_csv(scored)
    # Provenance : empreinte de chaque fichier, vérifiable après téléchargement.
    manifest["files"] = [
        {
            "name": name,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")),
        }
        for name, text in files.items()
    ]
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str)
        )
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Export sur disque aux colonnes du contrat
# --------------------------------------------------------------------------

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

"""Assembler une étude téléchargeable et sa provenance."""

from __future__ import annotations

import io
import json
from dataclasses import asdict
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
    if study.adaptation is not None:
        manifest["adaptation"] = study.adaptation
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
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str)
        )
        archive.writestr("forecasts.csv", csv_text([item.forecast for item in studies]))
        archive.writestr("cases.csv", case_csv(study.case))
        if runs:
            archive.writestr("case_runs.csv", csv_text(runs))
        if evaluation is not None:
            archive.writestr("observations.csv", evaluation["observations"].to_csv(index=False))
            errors = [evaluation["errors"]]
            errors.extend(score["errors"] for _, score in alternatives if score is not None)
            archive.writestr("errors.csv", csv_text(errors))
    return buffer.getvalue()

"""Calcul de 24 heures sur sites connus et traçage des expériences - E2 avec E5.

À faire :
1. Recevoir un cas et ses seules entrées autorisées ; choisir une version admissible du modèle.
2. Produire 24 lignes au format forecasts.csv, sans observations cibles.
3. Sauvegarder <method_run_id>.pred.csv et .runs.csv dans data/prediction_results/<experiment_id>/.
4. Fournir le même calcul à E5 et prouver le recalcul sur une autre origine.

Signature imposée par E5 pour son code : predict_24h(case, history, variant="reference").
Coexistence avec ForecastMethod(inputs, variant) du registre : incohérence C4, en suspens
(voir reports/teams/E2_SUIVI.md, §10).
history doit déjà être filtré sur le passé admissible ; le contexte autorisé est passé
en argument nommé optionnel pour rester compatible avec ForecastInputs.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.schemas import (
    CASE_RUNS_COLUMNS,
    FORECAST_COLUMNS,
    HORIZON_HOURS,
    Case,
    ForecastInputs,
    ForecastResult,
    Variant,
)


def build_inputs(
    case: Case,
    history: pd.DataFrame,
    context: pd.DataFrame | None = None,
    publication_lag_hours: int = 24,
) -> ForecastInputs:
    """Restreindre l'historique et le contexte à ce qui est disponible à l'origine."""
    raise NotImplementedError("E2 : filtrage available_at <= origin puis assert_causal")


def predict_24h(
    case: Case,
    history: pd.DataFrame,
    variant: Variant = "reference",
    *,
    context: pd.DataFrame | None = None,
    model_run_id: str | None = None,
) -> ForecastResult:
    """Point d'entrée E2 appelé par E5 et par les expériences.

    - reference -> baseline.weekly_reference ;
    - autre variante -> modèle entraîné (train.load_model), repli sur la référence si
      historique insuffisant ou ressource absente, avec statut fallback explicite.
    """
    raise NotImplementedError("E2 : routage variante -> méthode, statut et coût")


def run_experiment(
    cases: pd.DataFrame,
    history_loader,
    variant: Variant,
    experiment_id: str,
    method_run_id: str,
) -> tuple[Path, Path]:
    """Prévoir tous les cas puis écrire .pred.csv et .runs.csv ; retourner leurs chemins."""
    raise NotImplementedError("E2 : boucle sur les cas, aucune cible dans les sorties")


def write_predictions(results: Iterable[ForecastResult], path: Path) -> Path:
    """Écrire <method_run_id>.pred.csv (colonnes FORECAST_COLUMNS, CSV UTF-8, UTC ISO).

    24 lignes par cas, y compris les horizons sans prévision (y_pred vide et raison).
    Refuse une clé (case_id, method_run_id, horizon) en double ou un cas sans 24 lignes.
    """
    frames = []
    for result in results:
        frame = result.to_forecast_frame()
        if len(frame) != HORIZON_HOURS:
            raise ValueError(f"{result.case.case_id} : {len(frame)} lignes au lieu de 24")
        frames.append(frame)
    if not frames:
        raise ValueError("aucun résultat à écrire")
    table = pd.concat(frames, ignore_index=True)
    key = ["case_id", "method_run_id", "horizon"]
    if table.duplicated(key).any():
        raise ValueError(f"clé {key} en double dans les prévisions")
    return _write_csv(table, FORECAST_COLUMNS, path)


def write_runs(results: Iterable[ForecastResult], path: Path) -> Path:
    """Écrire <method_run_id>.runs.csv (une ligne par cas, colonnes CASE_RUNS_COLUMNS)."""
    rows = [result.to_run_row() for result in results]
    if not rows:
        raise ValueError("aucun résultat à écrire")
    table = pd.DataFrame(rows, columns=CASE_RUNS_COLUMNS)
    if table.duplicated(["case_id", "method_run_id"]).any():
        raise ValueError("cas en double dans le fichier de coût")
    return _write_csv(table, CASE_RUNS_COLUMNS, path)


def _write_csv(table: pd.DataFrame, columns: list[str], path: Path) -> Path:
    """Appliquer les conventions CONTRATS §1 : UTC ISO avec fuseau, true/false, vide = absent."""
    out = table[columns].astype(object)
    for column in out.columns:
        out[column] = out[column].map(_format_cell)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8")
    return path


def _format_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool | np.bool_):
        return "true" if value else "false"
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            raise ValueError(f"date sans fuseau à l'export : {value}")
        return value.tz_convert("UTC").isoformat()
    if isinstance(value, float | np.floating) and not np.isfinite(value):
        return ""
    if value is pd.NaT or value is pd.NA:
        return ""
    return value

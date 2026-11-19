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

import pandas as pd

from src.models.schemas import Case, ForecastInputs, ForecastResult, Variant


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
    """Écrire <method_run_id>.pred.csv (colonnes FORECAST_COLUMNS, CSV UTF-8, UTC ISO)."""
    raise NotImplementedError("E2 : export forecasts.csv")


def write_runs(results: Iterable[ForecastResult], path: Path) -> Path:
    """Écrire <method_run_id>.runs.csv (une ligne par cas, colonnes CASE_RUNS_COLUMNS)."""
    raise NotImplementedError("E2 : export case_runs.csv")

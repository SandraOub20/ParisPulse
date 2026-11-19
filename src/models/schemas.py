"""Objets échangés par les méthodes E2/E3 - PROPOSITION à migrer dans src/common/contracts.py.

Tant que ``src/common/contracts.py`` n'est pas adopté par les cinq équipes, ce module fixe
provisoirement les structures dont dépendent ``known/`` et ``new/``. Les noms de champs
suivent doc/CONTRATS.md (§1, §5, §7) et les en-têtes de doc/templates/.

Règles rappelées :
- toutes les dates sont des ``pd.Timestamp`` UTC avec fuseau ;
- ``origin`` = début du premier intervalle prévu ; horizon h vise
  ``[origin + (h-1) h, origin + h h)`` ;
- les entrées ne contiennent jamais de cible future (``available_at <= origin``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

HORIZON_HOURS = 24

Scenario = Literal["known_site", "new_site"]
Variant = Literal["reference", "frozen", "adapted"] | str
PredictionStatus = Literal["ok", "fallback", "unavailable", "error"]

# En-têtes des gabarits (doc/templates/forecasts.csv et case_runs.csv).
FORECAST_COLUMNS: list[str] = [
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
CASE_RUNS_COLUMNS: list[str] = [
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


@dataclass(frozen=True)
class Case:
    """Une ligne de data/evaluation/<protocol_id>/cases.csv (fournie par E4)."""

    case_id: str
    counter_id: str
    site_group_id: str | None
    origin: pd.Timestamp
    scenario: Scenario
    protocol_id: str
    snapshot_id: str
    temporal_split: str | None = None
    spatial_role: str | None = None
    local_budget_hours: int | None = None
    support_start: pd.Timestamp | None = None
    support_end: pd.Timestamp | None = None

    @classmethod
    def from_row(cls, row: pd.Series) -> Case:
        """Construire un cas depuis une ligne de cases.csv (conversion UTC à vérifier)."""
        raise NotImplementedError("E2/E4 : parser cases.csv et convertir les dates en UTC")


@dataclass
class ForecastInputs:
    """Entrées autorisées pour un cas : passé admissible et contexte connu à l'origine.

    ``history`` reprend les colonnes de counts.csv restreintes au compteur (et, pour un
    nouveau site, au support local). ``context`` reprend context.csv filtré sur
    ``available_at <= origin``. Aucune colonne cible postérieure à ``information_cutoff``.
    """

    case: Case
    history: pd.DataFrame
    information_cutoff: pd.Timestamp
    context: pd.DataFrame | None = None
    context_version: str | None = None
    support_id: str | None = None
    support_manifest: dict[str, Any] | None = None


@dataclass
class RunCost:
    """Coût d'une exécution de cas (une ligne de .runs.csv, jamais répétée 24 fois)."""

    preparation_seconds: float = 0.0
    inference_seconds: float = 0.0
    adaptation_seconds: float = 0.0
    wait_seconds: float = 0.0
    cache_hit: bool = False
    memory_mb: float | None = None
    hardware: str | None = None


@dataclass
class ForecastResult:
    """Sortie commune E2/E3 : 24 horizons, méthode effective, statut, provenance et coût.

    ``predictions`` contient au minimum : horizon, target_timestamp, y_pred,
    method_used, prediction_status, status_reason (une ligne par horizon).
    """

    case: Case
    method_run_id: str
    model_run_id: str | None
    variant: Variant
    predictions: pd.DataFrame
    status: PredictionStatus
    status_reason: str | None = None
    fit_cutoff: pd.Timestamp | None = None
    support_id: str | None = None
    adaptation_id: str | None = None
    context_version: str | None = None
    feature_version: str | None = None
    cost: RunCost = field(default_factory=RunCost)

    def is_complete(self) -> bool:
        """Vrai si les 24 horizons distincts ont une prévision finie non négative."""
        preds = self.predictions
        if len(preds) != HORIZON_HOURS:
            return False
        if sorted(preds["horizon"].tolist()) != list(range(1, HORIZON_HOURS + 1)):
            return False
        values = pd.to_numeric(preds["y_pred"], errors="coerce").to_numpy(dtype=float)
        return bool(np.isfinite(values).all() and (values >= 0).all())

    def to_forecast_frame(self) -> pd.DataFrame:
        """Convertir au format doc/templates/forecasts.csv (colonnes FORECAST_COLUMNS).

        Les dates restent des Timestamp UTC ; leur écriture ISO est faite par l'export.
        Les horizons sans prévision gardent y_pred manquant (jamais 0).
        """
        case = self.case
        frame = self.predictions[
            [
                "horizon",
                "target_timestamp",
                "y_pred",
                "method_used",
                "prediction_status",
                "status_reason",
            ]
        ].copy()
        frame = frame.assign(
            case_id=case.case_id,
            method_run_id=self.method_run_id,
            model_run_id=self.model_run_id,
            counter_id=case.counter_id,
            origin=case.origin,
            scenario=case.scenario,
            variant=self.variant,
            fit_cutoff=self.fit_cutoff,
            support_id=self.support_id,
            adaptation_id=self.adaptation_id,
            snapshot_id=case.snapshot_id,
            context_version=self.context_version,
            protocol_id=case.protocol_id,
            feature_version=self.feature_version,
        )
        return frame.sort_values("horizon")[FORECAST_COLUMNS].reset_index(drop=True)

    def to_run_row(self) -> dict[str, Any]:
        """Convertir en une ligne au format doc/templates/case_runs.csv."""
        cost = self.cost
        return {
            "case_id": self.case.case_id,
            "method_run_id": self.method_run_id,
            "model_run_id": self.model_run_id,
            "status": self.status,
            "status_reason": self.status_reason,
            "preparation_seconds": cost.preparation_seconds,
            "inference_seconds": cost.inference_seconds,
            "adaptation_seconds": cost.adaptation_seconds,
            "wait_seconds": cost.wait_seconds,
            "cache_hit": cost.cache_hit,
            "memory_mb": cost.memory_mb,
            "hardware": cost.hardware,
            "protocol_id": self.case.protocol_id,
            "snapshot_id": self.case.snapshot_id,
        }


def target_timestamps(origin: pd.Timestamp, horizon_hours: int = HORIZON_HOURS) -> pd.DataFrame:
    """Retourner ``horizon`` (1..24) et ``target_timestamp`` UTC dérivés de l'origine.

    L'horizon couvre 24 heures écoulées UTC, même un jour de changement d'heure.
    """
    if origin.tzinfo is None:
        raise ValueError("origin doit porter un fuseau (UTC)")
    origin = origin.tz_convert("UTC")
    horizons = range(1, horizon_hours + 1)
    return pd.DataFrame(
        {
            "horizon": list(horizons),
            "target_timestamp": [origin + pd.Timedelta(hours=h - 1) for h in horizons],
        }
    )


def assert_causal(inputs: ForecastInputs) -> None:
    """Vérifier qu'aucune entrée n'est postérieure à la coupure d'information.

    À contrôler : ``available_at <= origin`` pour l'historique et le contexte, et pour un
    nouveau site, historique strictement inclus dans [support_start, support_end].
    """
    raise NotImplementedError("E2/E3 avec E4 : implémenter les contrôles de causalité")

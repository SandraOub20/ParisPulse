"""Apprentissage et comparaison des méthodes sur sites connus - E2.

À faire :
1. Lire les cas et séparations proposés par E4, puis utiliser le protocole validé.
2. Exclure les sites réservés d'E3 ; vérifier la disponibilité des labels à la coupure.
3. Comparer au moins une variante explicative et coordonner l'expérience DL collective.
4. Sauvegarder paramètres, provenance, coût et poids dans artifacts/models/ ; préserver le test final.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

METHOD_NAME = "known_site_model"


@dataclass
class TrainConfig:
    """Réglages figés avant toute mesure sur la période de test."""

    method: str  # ex. "gbm", "ridge", "mlp_torch"
    fit_cutoff: pd.Timestamp
    use_context: bool = True
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    protocol_id: str | None = None
    snapshot_id: str | None = None
    context_version: str | None = None
    feature_version: str | None = None


@dataclass
class TrainedModel:
    """Modèle entraîné et métadonnées (doc/templates/model_metadata.example.json)."""

    model_run_id: str
    config: TrainConfig
    estimator: Any
    donor_site_groups: list[str]
    label_interval: tuple[pd.Timestamp, pd.Timestamp]
    train_seconds: float
    hardware: str | None = None


def load_training_data(snapshot_id: str, protocol_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Charger counts.csv et le contexte ; retourner (counts, context)."""
    raise NotImplementedError("E2 : lecture via src/common/config.py")


def exclude_reserved_sites(counts: pd.DataFrame, reserved_groups: list[str]) -> pd.DataFrame:
    """Retirer toutes les directions des groupes réservés (dev_new, test_new) d'E3."""
    raise NotImplementedError("E2 : exclusion par site_group_id, pas par counter_id")


def fit(config: TrainConfig, counts: pd.DataFrame, context: pd.DataFrame | None) -> TrainedModel:
    """Entraîner la méthode choisie ; dépendances lourdes (torch) importées paresseusement."""
    raise NotImplementedError("E2 : apprentissage")


def compare_variants(configs: list[TrainConfig], validation_cases: pd.DataFrame) -> pd.DataFrame:
    """Comparer des variantes sur la validation (jamais sur le test final).

    Ex. même modèle avec/sans contexte ; local vs partagé ; autre fonction de perte.
    Les scores officiels restent calculés par E4.
    """
    raise NotImplementedError("E2 avec E4 : ablation d'information")


def save_model(model: TrainedModel, root: Path | None = None) -> Path:
    """Écrire artifacts/models/<model_run_id>/metadata.json, poids et SHA-256."""
    raise NotImplementedError("E2 : provenance, coût et empreintes")


def load_model(model_run_id: str, root: Path | None = None) -> TrainedModel:
    """Recharger un modèle et vérifier son empreinte."""
    raise NotImplementedError("E2 : chargement contrôlé")

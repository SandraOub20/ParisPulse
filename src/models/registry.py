"""Registre des méthodes E2/E3 - interface commune appelée par E5.

Chaque méthode déclare nom, version, scénarios, coupure, historique minimal, ressources et
repli. E5 orchestre via get_method / select_method sans réécrire les modèles.

À faire :
1. Aligner ForecastMethod sur src/common/contracts.py une fois adopté.
2. Enregistrer la référence E2 dès la première matinée, puis les autres méthodes.
3. Référencer les métadonnées dans artifacts/models/<model_run_id>/metadata.json.
4. Faire valider avec E4/E5 la règle de routage et ses messages.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from src.models.schemas import Case, ForecastInputs, ForecastResult, Scenario, Variant


class ForecastMethod(Protocol):
    """Signature commune : mêmes entrées contrôlées, même structure de sortie."""

    def __call__(self, inputs: ForecastInputs, variant: Variant = ...) -> ForecastResult: ...


@dataclass(frozen=True)
class MethodSpec:
    """Fiche d'une méthode exécutable (exposée par get_capabilities côté E5)."""

    name: str
    version: str
    owner_team: str  # "E2" ou "E3"
    scenarios: tuple[Scenario, ...]
    variants: tuple[str, ...]
    min_history_hours: int
    fn: ForecastMethod
    model_run_id: str | None = None
    fit_cutoff: str | None = None  # ISO UTC ; doit précéder toute origine servie
    requires: tuple[str, ...] = ()  # dépendances optionnelles, ex. ("torch",)
    needs_gpu: bool = False
    fallback: str | None = None  # nom de la méthode de repli déclarée
    notes: str = ""
    extra: dict[str, str] = field(default_factory=dict)


_REGISTRY: dict[str, MethodSpec] = {}


def register(spec: MethodSpec) -> MethodSpec:
    """Ajouter une méthode au registre ; refuser un doublon nom/version."""
    raise NotImplementedError("E2/E3 : enregistrer la méthode et contrôler l'unicité")


def get_method(name: str) -> MethodSpec:
    """Retourner la fiche d'une méthode, ou lever une erreur explicite."""
    raise NotImplementedError("E2/E3 : lecture du registre")


def list_methods(scenario: Scenario | None = None) -> list[MethodSpec]:
    """Lister les méthodes disponibles, éventuellement filtrées par scénario."""
    raise NotImplementedError("E2/E3 : filtrage du registre")


def check_eligibility(
    spec: MethodSpec, case: Case, inputs: ForecastInputs
) -> tuple[bool, str | None]:
    """Dire si la méthode peut servir ce cas et pourquoi sinon.

    Contrôles : scénario, fit_cutoff < origin, historique minimal mesuré disponible,
    dépendances installées, site réservé absent des sites donneurs (E3).
    """
    raise NotImplementedError("E2/E3 avec E5 : conditions d'utilisation")


def select_method(
    case: Case,
    inputs: ForecastInputs,
    preferred: str | None = None,
    *,
    resolver: Callable[[str], MethodSpec] = get_method,
) -> tuple[MethodSpec, str | None]:
    """Choisir la méthode effective et, si besoin, descendre la chaîne de replis.

    Retourne la fiche retenue et la raison du repli (None si méthode préférée).
    Le repli est toujours déclaré ; aucun cas ne disparaît silencieusement.
    """
    raise NotImplementedError("E2/E3 avec E5 : règle de routage validée par E4")


def register_defaults() -> None:
    """Enregistrer les méthodes livrées (référence hebdomadaire, modèles E2, méthodes E3)."""
    raise NotImplementedError("E2/E3 : appeler register() pour chaque méthode livrée")

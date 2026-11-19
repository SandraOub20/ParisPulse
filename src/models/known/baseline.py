"""Référence hebdomadaire recalculable et repli - E2.

À faire :
1. Utiliser la valeur décalée de 168 heures UTC si elle est disponible à l'origine.
2. Joindre par timestamp ; ne pas décaler 168 lignes si la grille comporte des manques.
3. Définir un repli fondé sur le seul passé admissible et conserver les zéros observés.
4. Retourner 24 horizons ou des indisponibilités explicites ; vérifier quelques valeurs à la main.
5. Tester si possible Prophet (Meta) comme variante optionnelle - dépendance non déclarée
   dans pyproject.toml : import paresseux, jamais obligatoire pour la référence.

Note : avec publication_lag_hours = 24, la valeur t-168 h reste disponible pour les
24 horizons (dernière cible t = origin + 23 h -> source disponible à origin - 120 h).
"""

from __future__ import annotations

import pandas as pd

from src.models.schemas import ForecastInputs, ForecastResult, Variant

METHOD_NAME = "weekly_naive"
METHOD_VERSION = "0.1.0"
SEASONAL_LAG = pd.Timedelta(hours=168)
MIN_HISTORY_HOURS = 168


def weekly_reference(inputs: ForecastInputs, variant: Variant = "reference") -> ForecastResult:
    """Prévoir y(t) = y(t - 168 h), jointure par timestamp, avec repli horaire par horizon.

    - valeur t-168 h observée (zéro compris) et disponible -> ok ;
    - manquante -> fallback_value puis statut fallback et raison ;
    - aucun repli possible -> y_pred manquant (NaN, écrit vide dans le CSV ; jamais 0),
      statut unavailable et raison ; le cas est alors incomplet.

    Un zéro observé à t-168 h est une prévision valide (0.0), distincte d'une valeur manquante.
    """
    raise NotImplementedError("E2 : référence hebdomadaire")


def lookup_lagged(history: pd.DataFrame, targets: pd.Series, lag: pd.Timedelta) -> pd.Series:
    """Retourner count à target - lag par jointure sur timestamp (NaN si absent)."""
    raise NotImplementedError("E2 : jointure par timestamp, jamais par position")


def fallback_value(history: pd.DataFrame, target: pd.Timestamp, cutoff: pd.Timestamp) -> float | None:
    """Repli causal pour une heure cible, à figer avec E4/E5.

    Proposition : médiane des mêmes heure locale / jour de semaine sur les N dernières
    semaines admissibles, puis moyenne de la même heure locale, sinon None.
    """
    raise NotImplementedError("E2 : repli fondé sur le seul passé admissible")


def prophet_reference(inputs: ForecastInputs, variant: Variant = "prophet") -> ForecastResult:
    """Variante optionnelle Prophet, ajustée sur l'historique admissible du cas seulement."""
    try:
        import prophet  # noqa: F401
    except ImportError as exc:  # pragma: no cover - dépendance optionnelle
        raise RuntimeError("Prophet non installé : utiliser weekly_reference") from exc
    raise NotImplementedError("E2 : ajustement Prophet par cas, coût à tracer")

"""Fiabilité du parcours E5 : historique suffisant, prévisions complètes, messages clairs.

Trois contrôles, appelés par l'interface avant et après le calcul :

- ``check_history`` : le compteur a-t-il assez de mesures *autorisées* pour la méthode ?
  Seul le passé publié à l'origine est lu (même filtre que le service) : aucune cible.
- ``check_forecast`` : les 24 horizons sont-ils présents, uniques et valides ?
- ``explain_reason`` / ``explain_error`` : transformer un code ou une exception en phrase
  compréhensible par l'utilisateur.

Ces contrôles n'empêchent pas une méthode d'appliquer son propre repli ; ils rendent
visibles, avant et après le calcul, les cas où la prévision sera ou a été dégradée.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.app import service
from src.models.known.baseline import FALLBACK_WEEKS, MIN_HISTORY_HOURS
from src.models.schemas import HORIZON_HOURS, Case

# Niveaux renvoyés par check_history (affichés en st.success / st.warning / st.error).
LEVEL_OK = "ok"
LEVEL_PARTIAL = "partial"
LEVEL_NONE = "none"

# Méthodes E2 qui lisent quatre semaines (médiane du profil hebdomadaire).
PROFILE_METHODS = {"reference_profile", service.COMPARE_REFERENCES}

REASON_MESSAGES = {
    "lag168_missing": "Mesure de la semaine précédente manquante : valeur de repli utilisée",
    "no_fallback_history": "Aucune mesure historique à cette heure pour calculer un repli",
    "profile_weeks_missing": "Mesures de référence manquantes sur quatre semaines",
    "negative_quantile_clipped_to_zero": "Valeur négative du modèle ramenée à zéro",
}

ERROR_HINTS = {
    (AttributeError, ImportError, NameError): (
        "la méthode n’est pas utilisable dans cette version du code (à signaler à son équipe)"
    ),
    OSError: "un fichier ou une ressource est introuvable",
    KeyError: "une colonne ou une donnée attendue est absente",
    RuntimeError: "le calcul a été interrompu",
}


@dataclass(frozen=True)
class HistoryCheck:
    """Mesures disponibles avant l'origine pour la méthode demandée."""

    level: str
    required_hours: int
    observed_hours: int
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    message: str

    @property
    def can_forecast(self) -> bool:
        """Faux seulement si aucune mesure n'est utilisable : le calcul serait vide."""
        return self.level != LEVEL_NONE


@dataclass(frozen=True)
class ForecastCheck:
    """Bilan des 24 horizons d'une prévision, avant toute observation cible."""

    n_expected: int
    n_valid: int
    n_fallback: int
    n_failed: int
    missing_horizons: tuple[int, ...]
    duplicate_horizons: tuple[int, ...]
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_complete(self) -> bool:
        """Cas complet au sens du protocole : 24 horizons distincts, tous valides."""
        return (
            self.n_valid == self.n_expected
            and not self.missing_horizons
            and not self.duplicate_horizons
        )


def required_history_hours(case: Case, method: str | None = None) -> int:
    """Heures de passé dont la méthode a besoin pour ne pas recourir au repli."""
    if case.scenario == "new_site":
        if not case.local_budget_hours or case.local_budget_hours <= 0:
            raise ValueError("Le cas nouveau site doit préciser un budget local positif.")
        return int(case.local_budget_hours)
    if method in PROFILE_METHODS:
        return FALLBACK_WEEKS * MIN_HISTORY_HOURS
    return MIN_HISTORY_HOURS


def check_history(
    case: Case,
    history: pd.DataFrame,
    publication_lag_hours: int,
    method: str | None = None,
) -> HistoryCheck:
    """Compter les mesures autorisées dans la fenêtre lue par la méthode.

    La fenêtre se termine à la coupure d'information ``origin - délai`` ; pour un nouveau
    site, elle est en plus limitée au support local du cas. Une heure compte si elle a été
    réellement mesurée (``is_observed``) et porte une valeur ; le zéro observé compte.
    """
    required = required_history_hours(case, method)
    end = case.origin - pd.Timedelta(hours=publication_lag_hours)
    start = end - pd.Timedelta(hours=required)
    past = service.published_history(case, history, publication_lag_hours)
    timestamps = pd.to_datetime(past["timestamp"], utc=True)
    in_window = past.loc[timestamps.ge(start)]
    values = pd.to_numeric(in_window["count_raw"], errors="coerce")
    measured = in_window["is_observed"].eq(True) & values.notna()
    observed = int(in_window.loc[measured, "timestamp"].nunique())

    if observed == 0:
        level = LEVEL_NONE
        message = (
            f"Historique insuffisant : aucune mesure disponible sur les {required} heures "
            "précédant la coupure. La prévision ne peut pas être calculée pour ce cas."
        )
    elif observed < required:
        level = LEVEL_PARTIAL
        message = (
            f"Historique incomplet : {observed} heures mesurées sur {required} nécessaires "
            f"({observed / required:.0%}). Les heures estimées ou absentes ne comptent pas ; "
            "certaines heures peuvent utiliser un repli ou rester sans prévision."
        )
    else:
        level = LEVEL_OK
        message = f"Historique suffisant : {observed} heures mesurées sur {required}."
    return HistoryCheck(level, required, observed, start, end, message)


def explain_reason(reason: object) -> str:
    """Traduire un ``status_reason`` (codes séparés par « ; ») en texte lisible."""
    if reason is None or (isinstance(reason, float) and pd.isna(reason)) or reason == "":
        return ""
    text = str(reason)
    if ":" in text and text.split(":", 1)[0].isidentifier() and text.split(":", 1)[0][0].isupper():
        # Forme « TypeErreur: message » produite par error_result d'E2.
        return f"Erreur de calcul : {text.split(':', 1)[1].strip()}"
    parts = [part.strip() for part in text.split(";") if part.strip()]
    return " ; ".join(REASON_MESSAGES.get(part, part) for part in parts)


def explain_error(error: BaseException) -> str:
    """Message affiché quand le calcul d'une prévision lève une exception."""
    # KeyError entoure son message de guillemets : les retirer pour la lisibilité.
    detail = str(error.args[0]) if isinstance(error, KeyError) and error.args else str(error)
    detail = detail or type(error).__name__
    for kind, hint in ERROR_HINTS.items():
        if isinstance(error, kind):
            return f"Prévision indisponible : {hint} ({detail})."
    return f"Prévision indisponible : {detail}"


def check_forecast(forecast: pd.DataFrame, expected: int = HORIZON_HOURS) -> ForecastCheck:
    """Vérifier horizons manquants, doublons, valeurs absentes et statuts d'échec."""
    horizons = pd.to_numeric(forecast["horizon"], errors="coerce")
    present = set(horizons.dropna().astype(int))
    missing = tuple(h for h in range(1, expected + 1) if h not in present)
    duplicated = tuple(sorted(set(horizons[horizons.duplicated()].dropna().astype(int))))

    status = forecast["prediction_status"].astype("string").str.lower()
    values = pd.to_numeric(forecast["y_pred"], errors="coerce")
    usable = status.isin(service.VALID_STATUSES) & values.notna() & values.ge(0)
    n_valid = int(horizons[usable].nunique())
    n_fallback = int(status.eq("fallback").sum())
    n_failed = int((~usable).sum())

    problems: list[str] = []
    if missing:
        problems.append(f"Horizons absents : {_ranges(missing)}.")
    if duplicated:
        problems.append(f"Horizons en double : {_ranges(duplicated)}.")
    failed = forecast.loc[~usable]
    for reason, rows in failed.groupby(failed["status_reason"].fillna(""), sort=False):
        hours = tuple(sorted(pd.to_numeric(rows["horizon"], errors="coerce").dropna().astype(int)))
        label = explain_reason(reason) or "aucune raison fournie par la méthode"
        problems.append(f"Sans prévision ({_ranges(hours)}) : {label}.")
    return ForecastCheck(
        expected, n_valid, n_fallback, n_failed, missing, duplicated, tuple(problems)
    )


def _ranges(hours: tuple[int, ...]) -> str:
    """(1, 2, 3, 7) -> « h1–h3, h7 »."""
    if not hours:
        return "aucun"
    groups: list[str] = []
    start = previous = hours[0]
    for hour in (*hours[1:], None):
        if hour is not None and hour == previous + 1:
            previous = hour
            continue
        groups.append(f"h{start}" if start == previous else f"h{start}–h{previous}")
        if hour is not None:
            start = previous = hour
    return ", ".join(groups)

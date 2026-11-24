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
from src.models.schemas import HORIZON_HOURS, Case, target_timestamps

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
    """Nombre de mesures passées que la méthode lit directement.

    - site connu, « semaine précédente » : y(t − 168 h) pour chacune des 24 cibles ;
    - site connu, profil 4 semaines : y(t − k × 168 h), k = 1…4, soit 96 mesures ;
    - nouveau site : toutes les heures du support local (budget du cas).
    """
    if case.scenario == "new_site":
        if not case.local_budget_hours or case.local_budget_hours <= 0:
            raise ValueError("Le cas nouveau site doit préciser un budget local positif.")
        return int(case.local_budget_hours)
    weeks = FALLBACK_WEEKS if method in PROFILE_METHODS else 1
    return weeks * HORIZON_HOURS


def _needed_timestamps(case: Case, method: str | None, end: pd.Timestamp) -> pd.DatetimeIndex:
    """Heures exactes lues par la méthode (cf. required_history_hours)."""
    if case.scenario == "new_site":
        return pd.date_range(
            end - pd.Timedelta(hours=required_history_hours(case, method)),
            end,
            freq="h",
            inclusive="left",
        )
    targets = pd.to_datetime(target_timestamps(case.origin)["target_timestamp"], utc=True)
    weeks = FALLBACK_WEEKS if method in PROFILE_METHODS else 1
    lags = [targets - k * pd.Timedelta(hours=MIN_HISTORY_HOURS) for k in range(1, weeks + 1)]
    return pd.DatetimeIndex(pd.concat(lags)).sort_values()


def check_history(
    case: Case,
    history: pd.DataFrame,
    publication_lag_hours: int,
    method: str | None = None,
) -> HistoryCheck:
    """Compter les mesures autorisées que la méthode va réellement lire.

    Seul le passé publié à l'origine est lu (coupure ``origin − délai``, support local pour
    un nouveau site). Une heure compte si elle a été réellement mesurée (``is_observed``) et
    porte une valeur ; le zéro observé compte, une heure estimée par E1 ne compte pas.

    - ``ok`` : toutes les mesures lues directement sont présentes ;
    - ``partial`` : certaines manquent ; ces heures passeront par le repli (une semaine
      plus ancienne pour un site connu) ou resteront sans prévision ;
    - ``none`` : aucune mesure dans tout le passé utilisable (4 semaines pour un site connu,
      support local pour un nouveau site) : le calcul ne peut rien produire.
    """
    required = required_history_hours(case, method)
    end = case.origin - pd.Timedelta(hours=publication_lag_hours)
    needed = _needed_timestamps(case, method, end)
    past = service.published_history(case, history, publication_lag_hours)
    values = pd.to_numeric(past["count_raw"], errors="coerce")
    measured_times = pd.to_datetime(
        past.loc[past["is_observed"].eq(True) & values.notna(), "timestamp"], utc=True
    )
    observed = int(pd.Index(needed).isin(measured_times).sum())

    usable_hours = required if case.scenario == "new_site" else FALLBACK_WEEKS * MIN_HISTORY_HOURS
    usable_start = end - pd.Timedelta(hours=usable_hours)
    any_measured = bool(measured_times.ge(usable_start).any())
    missing = required - observed

    if not any_measured:
        level = LEVEL_NONE
        message = (
            f"Historique insuffisant : aucune mesure sur les {usable_hours} heures autorisées "
            "avant la prévision. Elle ne peut pas être calculée pour ce compteur à cette date."
        )
    elif missing > 0:
        level = LEVEL_PARTIAL
        consequence = (
            "Ces heures utiliseront une semaine plus ancienne (repli) ou resteront sans prévision."
            if case.scenario == "known_site"
            else "La méthode ne dispose que des mesures restantes du support local."
        )
        message = (
            f"Historique incomplet : {missing} des {required} mesures lues par la méthode "
            f"manquent (heures absentes ou estimées par E1). {consequence}"
        )
    else:
        level = LEVEL_OK
        message = f"Historique suffisant : les {required} mesures lues par la méthode sont là."
    return HistoryCheck(level, required, observed, needed.min(), end, message)


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

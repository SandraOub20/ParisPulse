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

Admissibilité (provisoire, C3/M2 de reports/teams/E2_SUIVI.md) : counts.csv ne porte pas
encore de colonne available_at. Une observation est admissible si son interval_end est
<= inputs.information_cutoff, que l'appelant fixe à origin - publication_lag. La référence
refiltre elle-même l'historique : une ligne postérieure à la coupure n'est jamais utilisée.

Repli (proposition D-03, N = FALLBACK_WEEKS à valider avec E4/E5), par horizon :
1. médiane des N dernières observations admissibles de même jour de semaine et même heure
   locale (Europe/Paris) que la cible ;
2. sinon moyenne des 7 x N dernières observations admissibles de même heure locale ;
3. sinon aucune prévision (y_pred manquant, statut unavailable).
La valeur principale suit 168 h UTC alors que le repli suit l'heure locale (I3, à trancher).

Deux références recalculables, sans apprentissage, vérifiables à la main :
- weekly_reference (weekly_naive) : y(t - 168 h) ;
- weekly_profile_reference (weekly_profile_median) : médiane de y(t - k x 168 h), k = 1..4.
"""

from __future__ import annotations

import platform
import time

import numpy as np
import pandas as pd

from src.models.schemas import (
    ForecastInputs,
    ForecastResult,
    PredictionStatus,
    RunCost,
    Variant,
    target_timestamps,
)

METHOD_NAME = "weekly_naive"
METHOD_VERSION = "0.1.0"
SEASONAL_LAG = pd.Timedelta(hours=168)
MIN_HISTORY_HOURS = 168
LOCAL_TZ = "Europe/Paris"
FALLBACK_WEEKS = 4

# Référence profil : médiane des mêmes heures UTC sur plusieurs semaines.
PROFILE_METHOD_NAME = "weekly_profile_median"
PROFILE_METHOD_VERSION = "0.1.0"
PROFILE_VARIANT = "reference_profile"
PROFILE_WEEKS = 4

# Valeurs de method_used et de status_reason (codes stables lus par E4/E5).
FALLBACK_DOW_HOUR = "profile_median_dow_hour"
FALLBACK_HOUR = "profile_mean_hour"
REASON_LAG_MISSING = "lag168_missing"
REASON_NO_FALLBACK = "lag168_missing;no_fallback_history"
REASON_PROFILE_MISSING = "profile_weeks_missing"


def weekly_reference(
    inputs: ForecastInputs,
    variant: Variant = "reference",
    *,
    method_run_id: str | None = None,
    fallback_weeks: int = FALLBACK_WEEKS,
) -> ForecastResult:
    """Prévoir y(t) = y(t - 168 h), jointure par timestamp, avec repli horaire par horizon.

    - valeur t-168 h observée (zéro compris) et disponible -> ok ;
    - manquante -> fallback_value puis statut fallback et raison ;
    - aucun repli possible -> y_pred manquant (NaN, écrit vide dans le CSV ; jamais 0),
      statut unavailable et raison ; le cas est alors incomplet.

    Un zéro observé à t-168 h est une prévision valide (0.0), distincte d'une valeur manquante.
    Statut du cas : unavailable si au moins un horizon est sans prévision, sinon fallback si
    au moins un horizon a utilisé le repli, sinon ok.
    """
    return _seasonal_reference(
        inputs,
        variant,
        lags=(SEASONAL_LAG,),
        method_name=METHOD_NAME,
        method_version=METHOD_VERSION,
        missing_reason=REASON_LAG_MISSING,
        method_run_id=method_run_id,
        fallback_weeks=fallback_weeks,
    )


def weekly_profile_reference(
    inputs: ForecastInputs,
    variant: Variant = PROFILE_VARIANT,
    *,
    method_run_id: str | None = None,
    n_weeks: int = PROFILE_WEEKS,
    fallback_weeks: int = FALLBACK_WEEKS,
) -> ForecastResult:
    """Prévoir y(t) = médiane de y(t - k x 168 h), k = 1..n_weeks, jointure par timestamp.

    Plus robuste qu'une seule semaine à une journée atypique (pluie, grève, panne). La
    médiane porte sur les semaines observées et admissibles (zéros compris) ; avec une seule
    semaine disponible, elle vaut la référence hebdomadaire. Sans aucune des n_weeks semaines,
    même chaîne de repli que weekly_reference. Mêmes lags UTC que weekly_reference (I3).
    """
    if n_weeks < 1:
        raise ValueError("n_weeks doit valoir au moins 1")
    return _seasonal_reference(
        inputs,
        variant,
        lags=tuple(SEASONAL_LAG * k for k in range(1, n_weeks + 1)),
        method_name=PROFILE_METHOD_NAME,
        method_version=PROFILE_METHOD_VERSION,
        missing_reason=REASON_PROFILE_MISSING,
        method_run_id=method_run_id,
        fallback_weeks=fallback_weeks,
    )


def _seasonal_reference(
    inputs: ForecastInputs,
    variant: Variant,
    *,
    lags: tuple[pd.Timedelta, ...],
    method_name: str,
    method_version: str,
    missing_reason: str,
    method_run_id: str | None,
    fallback_weeks: int,
) -> ForecastResult:
    """Médiane des valeurs aux lags donnés (une seule = valeur elle-même), puis repli."""
    started = time.perf_counter()
    case = inputs.case
    cutoff = _as_utc_timestamp(inputs.information_cutoff, "information_cutoff")
    origin = _as_utc_timestamp(case.origin, "case.origin")
    if cutoff > origin:
        raise ValueError(f"information_cutoff {cutoff} postérieure à l'origine {origin}")

    history = admissible_history(inputs.history, cutoff, counter_id=case.counter_id)
    targets = target_timestamps(origin)
    lagged = pd.concat(
        [lookup_lagged(history, targets["target_timestamp"], lag) for lag in lags], axis=1
    )
    primary = lagged.median(axis=1, skipna=True)

    y_pred: list[float] = []
    method_used: list[str | None] = []
    statuses: list[PredictionStatus] = []
    reasons: list[str | None] = []
    for target, value in zip(targets["target_timestamp"], primary, strict=True):
        if pd.notna(value):
            y_pred.append(float(value))
            method_used.append(method_name)
            statuses.append("ok")
            reasons.append(None)
            continue
        fb_value, fb_method = _fallback(history, target, cutoff, fallback_weeks)
        if fb_value is None:
            y_pred.append(np.nan)
            method_used.append(None)
            statuses.append("unavailable")
            reasons.append(f"{missing_reason};no_fallback_history")
        else:
            y_pred.append(fb_value)
            method_used.append(fb_method)
            statuses.append("fallback")
            reasons.append(missing_reason)

    predictions = targets.assign(
        y_pred=y_pred,
        method_used=method_used,
        prediction_status=statuses,
        status_reason=reasons,
    )
    status, reason = _case_status(statuses)
    cost = RunCost(
        inference_seconds=time.perf_counter() - started,
        hardware=f"{platform.system()}-{platform.machine()}",
    )
    return ForecastResult(
        case=case,
        method_run_id=method_run_id or f"{method_name}-{method_version}",
        model_run_id=None,
        variant=variant,
        predictions=predictions,
        status=status,
        status_reason=reason,
        fit_cutoff=None,
        support_id=inputs.support_id,
        context_version=inputs.context_version,
        feature_version=None,
        cost=cost,
    )


def admissible_history(
    history: pd.DataFrame, cutoff: pd.Timestamp, *, counter_id: str | None = None
) -> pd.DataFrame:
    """Retourner les lignes d'un seul compteur dont interval_end <= cutoff, timestamps en UTC.

    Refuse un historique multi-compteurs, des timestamps sans fuseau ou des doublons de
    timestamp (à résoudre par E1 : une jointure les multiplierait).
    """
    missing = {"timestamp", "count"} - set(history.columns)
    if missing:
        raise ValueError(f"colonnes absentes de l'historique : {sorted(missing)}")
    out = history.copy()
    if counter_id is not None and "counter_id" in out.columns:
        others = set(out["counter_id"].dropna().astype(str)) - {str(counter_id)}
        if others:
            raise ValueError(f"historique d'autres compteurs que {counter_id} : {sorted(others)}")
    out["timestamp"] = _as_utc_series(out["timestamp"], "timestamp")
    if "interval_end" in out.columns:
        out["interval_end"] = _as_utc_series(out["interval_end"], "interval_end")
    else:
        out["interval_end"] = out["timestamp"] + pd.Timedelta(hours=1)
    if out["timestamp"].duplicated().any():
        dup = out.loc[out["timestamp"].duplicated(), "timestamp"].iloc[0]
        raise ValueError(f"timestamp en double dans l'historique : {dup.isoformat()}")
    cutoff = _as_utc_timestamp(cutoff, "cutoff")
    out = out.loc[out["interval_end"] <= cutoff]
    return out.sort_values("timestamp").reset_index(drop=True)


def lookup_lagged(history: pd.DataFrame, targets: pd.Series, lag: pd.Timedelta) -> pd.Series:
    """Retourner count à target - lag par jointure sur timestamp (NaN si absent).

    Le résultat garde l'index de ``targets``. Une heure absente de la grille et une heure
    présente avec count manquant donnent toutes deux NaN ; un zéro observé reste 0.0.
    """
    timestamps = _as_utc_series(history["timestamp"], "timestamp")
    if timestamps.duplicated().any():
        raise ValueError("timestamp en double : jointure ambiguë")
    by_time = pd.Series(history["count"].to_numpy(dtype=float), index=pd.DatetimeIndex(timestamps))
    sources = pd.DatetimeIndex(_as_utc_series(targets, "targets")) - lag
    return pd.Series(by_time.reindex(sources).to_numpy(), index=targets.index, name="count")


def fallback_value(
    history: pd.DataFrame,
    target: pd.Timestamp,
    cutoff: pd.Timestamp,
    *,
    fallback_weeks: int = FALLBACK_WEEKS,
) -> float | None:
    """Repli causal pour une heure cible, à figer avec E4/E5.

    Médiane des mêmes heure locale / jour de semaine sur les N dernières observations
    admissibles, puis moyenne de la même heure locale sur les 7 x N dernières, sinon None.
    """
    admissible = admissible_history(history, cutoff)
    value, _ = _fallback(admissible, target, cutoff, fallback_weeks)
    return value


def _fallback(
    admissible: pd.DataFrame, target: pd.Timestamp, cutoff: pd.Timestamp, n_weeks: int
) -> tuple[float | None, str | None]:
    """Appliquer la chaîne de repli à un historique déjà restreint au passé admissible."""
    observed = admissible.loc[
        admissible["count"].notna() & (admissible["interval_end"] <= cutoff),
        ["timestamp", "count"],
    ]
    if observed.empty:
        return None, None
    local = observed["timestamp"].dt.tz_convert(LOCAL_TZ)
    target_local = _as_utc_timestamp(target, "target").tz_convert(LOCAL_TZ)
    same_hour = local.dt.hour == target_local.hour
    same_dow = same_hour & (local.dt.dayofweek == target_local.dayofweek)

    dow_values = observed.loc[same_dow, "count"].tail(n_weeks)
    if not dow_values.empty:
        return float(dow_values.median()), FALLBACK_DOW_HOUR
    hour_values = observed.loc[same_hour, "count"].tail(7 * n_weeks)
    if not hour_values.empty:
        return float(hour_values.mean()), FALLBACK_HOUR
    return None, None


def _case_status(statuses: list[PredictionStatus]) -> tuple[PredictionStatus, str | None]:
    n_unavailable = statuses.count("unavailable")
    n_fallback = statuses.count("fallback")
    if n_unavailable:
        return "unavailable", f"{n_unavailable}/{len(statuses)} horizons sans prévision"
    if n_fallback:
        return "fallback", f"{n_fallback}/{len(statuses)} horizons en repli"
    return "ok", None


def _as_utc_series(values: pd.Series, name: str) -> pd.Series:
    """Convertir en datetime UTC ; refuser des dates sans fuseau plutôt que de le supposer."""
    if pd.api.types.is_datetime64_any_dtype(values):
        if getattr(values.dt, "tz", None) is None:
            raise ValueError(f"{name} sans fuseau : dates UTC avec fuseau attendues")
        return values.dt.tz_convert("UTC")
    parsed = pd.to_datetime(values, format="ISO8601", utc=True)
    return parsed


def _as_utc_timestamp(value: pd.Timestamp, name: str) -> pd.Timestamp:
    value = pd.Timestamp(value)
    if value.tzinfo is None:
        raise ValueError(f"{name} sans fuseau : dates UTC avec fuseau attendues")
    return value.tz_convert("UTC")


def prophet_reference(inputs: ForecastInputs, variant: Variant = "prophet") -> ForecastResult:
    """Variante optionnelle Prophet, ajustée sur l'historique admissible du cas seulement."""
    try:
        import prophet  # noqa: F401
    except ImportError as exc:  # pragma: no cover - dépendance optionnelle
        raise RuntimeError("Prophet non installé : utiliser weekly_reference") from exc
    raise NotImplementedError("E2 : ajustement Prophet par cas, coût à tracer")

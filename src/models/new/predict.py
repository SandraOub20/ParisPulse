"""Prévision sur un nouveau site, sans adaptation."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.models.known.baseline import admissible_history
from src.models.known.predict import (
    default_publication_lag,
    write_predictions,
    write_runs,
)
from src.models.schemas import (
    HORIZON_HOURS,
    Case,
    ForecastInputs,
    ForecastResult,
    RunCost,
    assert_causal,
    target_timestamps,
)

from ._core import manager

CHRONOS_MODEL_NAME = "chronos-2"
GOOGLE_MODEL_NAME = "google_TimesFM_2.5"
TEAM2_MODEL_NAME = "team2"
SUPPORTED_MODELS = {CHRONOS_MODEL_NAME, GOOGLE_MODEL_NAME, TEAM2_MODEL_NAME}
SUPPORTED_VARIANTS = {"frozen", "adapted"}
POINT_QUANTILE = 0.5
MODEL_TARGET_LIMIT = 1024


def predict_24h(
    case: Case | pd.Series | dict[str, Any],
    history: pd.DataFrame,
    variant: str = "frozen",
    model_name: str = CHRONOS_MODEL_NAME,
    *,
    publication_lag_hours: int | None = None
) -> ForecastResult:
    """Prévoir 24 heures avec Chronos-2 sur le seul support local autorisé.

    L'entrée ``history`` peut contenir le comptage complet du compteur : elle est
    refiltrée par scénario, coupure, disponibilité, budget local et mesures publiées.
    L'adaptation et les autres modèles sont hors périmètre.
    """
    if variant not in SUPPORTED_VARIANTS:
        raise ValueError(f"variant doit être l'une de {sorted(SUPPORTED_VARIANTS)}.")
    if model_name not in SUPPORTED_MODELS:
        raise ValueError(f"Modèle inconnu : {model_name}")
    
    case = case if isinstance(case, Case) else Case.from_row(case)

    if case.scenario != "new_site":
        raise ValueError(f"{case.case_id} : scénario {case.scenario} hors périmètre E3")
    
    if case.spatial_role not in {"S_dev_new", "S_test_new"}:
        raise ValueError(
            f"{case.case_id} : spatial_role doit désigner un site réservé à E3 "
            "('S_dev_new' ou 'S_test_new')."
        )


    started = time.perf_counter()
    inputs, context_df, forecast_offset = _prepare_inputs(case, history, publication_lag_hours)
    preparation_seconds = time.perf_counter() - started

    forecast_length = forecast_offset + HORIZON_HOURS
    if forecast_length > MODEL_TARGET_LIMIT:
        raise ValueError(
            f"l'intervalle à franchir ({forecast_offset} h) dépasse la limite de model"
        )
    if model_name == CHRONOS_MODEL_NAME:
        if variant == "frozen":

            method_run_id = "e3-chronos-2-frozen-v1"
            model_run_id= "amazon-chronos-2"

            model = manager.load_model(model_name)

            inference_started = time.perf_counter()
            chronos_output = model.predict_df(
                context_df,
                prediction_length=forecast_length,
                quantile_levels=[POINT_QUANTILE],
                id_column="item_id",
                timestamp_column="timestamp",
                target="target",
            )
            inference_seconds = time.perf_counter() - inference_started

            predictions = _extract_predictions(chronos_output, inputs.case.origin, "chronos-2")
        elif variant == "adapted":
            method_run_id = "e3-chronos-2-adapted-v1"
            model_run_id= "amazon-chronos-2"
            manager.load_model(model_name)
            raise NotImplementedError(f"adapted n'est pas encore implémenté pour {model_name}.")
    elif model_name == GOOGLE_MODEL_NAME:
        if variant == "frozen":
            method_run_id = "e3-google-TimesFM_2.5-frozen-v1"
            model_run_id= "google-TimesFM_2.5"

            model = manager.load_model(model_name)

            inference_started = time.perf_counter()
            google_output = model.forecast(
                horizon=forecast_length,
                inputs=[context_df["target"].to_numpy(dtype=float)],
            )
            inference_seconds = time.perf_counter() - inference_started

            predictions = _extract_timesfm_predictions(
                google_output,
                inputs.case.origin,
                inputs.case.support_end,
                forecast_length,
                "google-TimesFM-2.5",
            )
        elif variant == "adapted":
            method_run_id = "e3-google-TimesFM_2.5-adapted-v1"
            model_run_id= "google-TimesFM_2.5"
            manager.load_model(model_name)
            raise NotImplementedError(f"adapted n'est pas encore implémenté pour {model_name}.")
    elif model_name == TEAM2_MODEL_NAME:
        manager.load_model(model_name)
        if variant == "frozen":
            method_run_id = "e3-team3-mlp-frozen-v1"
            model_run_id= "team3-frozen"
            raise NotImplementedError(f"frozen n'est pas encore implémenté pour {model_name}.")
        elif variant == "adapted":
            method_run_id = "e3-team3-mlp-adapted-v1"
            model_run_id= "team3-adapted"
            raise NotImplementedError(f"adapted n'est pas encore implémenté pour {model_name}.")

    return ForecastResult(
        case=inputs.case,
        method_run_id=method_run_id,
        model_run_id=model_run_id,
        variant=variant,
        predictions=predictions,
        status="ok",
        support_id=inputs.support_id,
        cost=RunCost(
            preparation_seconds=preparation_seconds,
            inference_seconds=inference_seconds,
            hardware=f"{platform.system()}-{platform.machine()}",
        ),
    )


def save_forecasts(
    forecasts: ForecastResult, path: str | Path = "forecasts.pred.csv"
) -> tuple[Path, Path]:
    """Enregistrer les prévisions et le coût au format CSV commun E2."""
    if not isinstance(forecasts, ForecastResult):
        raise TypeError("forecasts doit être un ForecastResult.")
    prediction_path = Path(path)
    if prediction_path.name.endswith(".pred.csv"):
        run_path = prediction_path.with_name(
            prediction_path.name.removesuffix(".pred.csv") + ".runs.csv"
        )
    else:
        run_path = prediction_path.with_suffix(".runs.csv")
    return (
        write_predictions([forecasts], prediction_path),
        write_runs([forecasts], run_path),
    )


def _prepare_inputs(
    case: Case,
    history: pd.DataFrame,
    publication_lag_hours: int | None,
) -> tuple[ForecastInputs, pd.DataFrame, int]:
    lag = default_publication_lag() if publication_lag_hours is None else publication_lag_hours
    if lag < 0:
        raise ValueError("publication_lag_hours ne peut pas être négatif.")
    if case.local_budget_hours is None or case.local_budget_hours <= 0:
        raise ValueError(f"{case.case_id} : local_budget_hours doit être strictement positif.")

    origin = _as_utc_timestamp(case.origin, "origin")
    cutoff = origin - pd.Timedelta(hours=lag)
    budget_start = cutoff - pd.Timedelta(hours=case.local_budget_hours)
    support_start = (
        _as_utc_timestamp(case.support_start, "support_start")
        if case.support_start is not None
        else budget_start
    )
    support_end = (
        _as_utc_timestamp(case.support_end, "support_end")
        if case.support_end is not None
        else cutoff
    )
    if support_start < budget_start or support_end > cutoff or support_start >= support_end:
        raise ValueError(
            f"{case.case_id} : bornes du support incompatibles avec le budget et le délai."
        )
    if any(value != value.floor("h") for value in (support_start, support_end)):
        raise ValueError(
            f"{case.case_id} : les bornes du support doivent être alignées sur l'heure."
        )

    case = replace(case, origin=origin, support_start=support_start, support_end=support_end)
    history = history.copy()
    if "timestamp" not in history or "count" not in history:
        raise ValueError("history doit contenir les colonnes 'timestamp' et 'count'.")
    history["timestamp"] = _as_utc_series(history["timestamp"], "timestamp")
    if "interval_end" in history:
        history["interval_end"] = _as_utc_series(history["interval_end"], "interval_end")
    else:
        history["interval_end"] = history["timestamp"] + pd.Timedelta(hours=1)
    if "available_at" in history:
        history["available_at"] = _as_utc_series(
            history["available_at"], "available_at", allow_missing=True
        )

    admissible = admissible_history(history, cutoff, counter_id=case.counter_id)
    if "available_at" in admissible:
        available = admissible["available_at"]
        admissible = admissible.loc[available.isna() | (available <= origin)]
    admissible = admissible.loc[
        (admissible["timestamp"] >= support_start) & (admissible["interval_end"] <= support_end)
    ].copy()

    observed = _observed_mask(admissible)
    source_column = "count_raw" if "count_raw" in admissible else "count"
    values = pd.to_numeric(admissible[source_column], errors="coerce")
    invalid_numeric = observed & admissible[source_column].notna() & values.isna()
    if invalid_numeric.any():
        raise ValueError(f"{source_column} contient une mesure non numérique.")
    if (observed & values.notna() & ~np.isfinite(values)).any():
        raise ValueError("l'historique contient une mesure non finie.")
    if (observed & values.notna() & (values < 0)).any():
        raise ValueError("l'historique contient une mesure négative.")
    admissible["count"] = values.where(observed)

    grid = pd.date_range(support_start, support_end, freq="h", inclusive="left")
    if grid.empty:
        raise ValueError(f"{case.case_id} : support local vide.")
    indexed = admissible.set_index("timestamp")["count"]
    context_values = indexed.reindex(grid).astype(float)
    if context_values.notna().sum() == 0:
        raise ValueError(f"{case.case_id} : aucune mesure publiée dans le support local.")

    support_id = _support_id(case, lag, grid, context_values)
    filtered_history = pd.DataFrame(
        {
            "counter_id": case.counter_id,
            "timestamp": grid,
            "interval_end": grid + pd.Timedelta(hours=1),
            "count": context_values.to_numpy(),
        }
    )
    inputs = ForecastInputs(
        case=case,
        history=filtered_history,
        information_cutoff=cutoff,
        support_id=support_id,
        support_manifest={
            "support_start": support_start.isoformat(),
            "support_end": support_end.isoformat(),
            "local_budget_hours": case.local_budget_hours,
            "publication_lag_hours": lag,
            "grid_hours": len(grid),
            "measured_hours": int(context_values.notna().sum()),
        },
    )
    assert_causal(inputs)

    context_df = pd.DataFrame(
        {
            "item_id": case.counter_id,
            # Chronos's pandas API expects datetime64 without a timezone; these
            # naive values represent UTC and are localized back after inference.
            "timestamp": grid.tz_localize(None),
            "target": context_values.to_numpy(),
        }
    )
    forecast_offset = int((origin - support_end) / pd.Timedelta(hours=1))
    return inputs, context_df, forecast_offset


def _extract_predictions(output: pd.DataFrame, origin: pd.Timestamp, method_name: str) -> pd.DataFrame:
    if not isinstance(output, pd.DataFrame):
        raise TypeError("Chronos-2 predict_df doit retourner un DataFrame.")
    if "timestamp" not in output:
        raise ValueError("La sortie Chronos-2 ne contient pas la colonne timestamp.")
    quantile_column = next(
        (
            column
            for column in output.columns
            if column == POINT_QUANTILE or str(column) == str(POINT_QUANTILE)
        ),
        None,
    )
    if quantile_column is None:
        raise ValueError(f"La sortie Chronos-2 ne contient pas le quantile {POINT_QUANTILE}.")

    forecasts = output[["timestamp", quantile_column]].copy()
    forecasts["timestamp"] = _chronos_utc_series(forecasts["timestamp"])
    if forecasts["timestamp"].duplicated().any():
        raise ValueError("Chronos-2 a retourné des timestamps en double.")
    forecasts = forecasts.set_index("timestamp")[quantile_column]

    targets = target_timestamps(origin)
    values = pd.to_numeric(forecasts.reindex(targets["target_timestamp"]), errors="coerce")
    array = values.to_numpy(dtype=float)
    if len(array) != HORIZON_HOURS or not np.isfinite(array).all():
        raise ValueError("Chronos-2 n'a pas retourné 24 prévisions finies pour l'origine demandée.")
    clipped = array < 0
    predictions = targets.assign(
        y_pred=np.maximum(array, 0.0),
        method_used=method_name,
        prediction_status="ok",
        status_reason=np.where(clipped, "negative_quantile_clipped_to_zero", None),
    )
    return predictions


def _extract_timesfm_predictions(
    output: Any,
    origin: pd.Timestamp,
    support_end: pd.Timestamp,
    forecast_length: int,
    method_name: str,
) -> pd.DataFrame:
    if not isinstance(output, (tuple, list)) or len(output) != 2:
        raise TypeError("TimesFM 2.5 doit retourner (point_forecast, quantile_forecast).")

    point_forecast, quantile_forecast = output
    point = np.asarray(point_forecast)
    quantiles = np.asarray(quantile_forecast)

    if point.ndim == 2 and point.shape[0] == 1:
        point = point[0]
    point = np.asarray(point).reshape(-1)

    values = point
    if quantiles.size:
        quantiles = np.asarray(quantiles)
        if quantiles.ndim == 3 and quantiles.shape[0] == 1:
            quantiles = quantiles[0]
        if quantiles.ndim == 2:
            if quantiles.shape[1] >= 6:
                values = quantiles[:, 5]
            else:
                values = quantiles[:, 0]
        elif quantiles.ndim == 1 and quantiles.size >= 6:
            values = quantiles
    values = np.asarray(values, dtype=float).reshape(-1)

    if len(values) != forecast_length:
        raise ValueError(
            f"TimesFM 2.5 a retourné {len(values)} prévisions au lieu de {forecast_length}."
        )

    forecast_start = support_end
    timestamps = pd.date_range(forecast_start, periods=forecast_length, freq="h")
    forecasts = pd.Series(values, index=timestamps)

    targets = target_timestamps(origin)
    array = pd.to_numeric(forecasts.reindex(targets["target_timestamp"]), errors="coerce").to_numpy(
        dtype=float
    )
    if len(array) != HORIZON_HOURS or not np.isfinite(array).all():
        raise ValueError("TimesFM 2.5 n'a pas retourné 24 prévisions finies pour l'origine demandée.")
    clipped = array < 0
    return targets.assign(
        y_pred=np.maximum(array, 0.0),
        method_used=method_name,
        prediction_status="ok",
        status_reason=np.where(clipped, "negative_quantile_clipped_to_zero", None),
    )


def _observed_mask(history: pd.DataFrame) -> pd.Series:
    if "is_observed" not in history:
        return pd.Series(True, index=history.index, dtype=bool)

    def parse(value: object) -> bool:
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if pd.isna(value):
            raise ValueError("is_observed contient une valeur absente.")
        normalized = str(value).strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
        raise ValueError(f"is_observed contient une valeur invalide : {value!r}")

    return history["is_observed"].map(parse).astype(bool)


def _support_id(case: Case, lag: int, timestamps: pd.DatetimeIndex, values: pd.Series) -> str:
    observations = [
        [timestamp.isoformat(), None if pd.isna(value) else float(value)]
        for timestamp, value in zip(timestamps, values, strict=True)
    ]
    payload = {
        "case_id": case.case_id,
        "counter_id": case.counter_id,
        "origin": case.origin.isoformat(),
        "support_start": case.support_start.isoformat(),
        "support_end": case.support_end.isoformat(),
        "publication_lag_hours": lag,
        "observations": observations,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _as_utc_timestamp(value: pd.Timestamp, name: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{name} doit inclure un fuseau horaire.")
    return timestamp.tz_convert("UTC")


def _chronos_utc_series(values: pd.Series) -> pd.Series:
    """Interpréter les dates naïves de Chronos comme UTC (format envoyé au modèle)."""
    timestamps = []
    for value in values:
        if pd.isna(value):
            raise ValueError("Chronos a retourné un timestamp absent.")
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        timestamps.append(timestamp)
    return pd.Series(pd.DatetimeIndex(timestamps), index=values.index, name=values.name)


def _as_utc_series(values: pd.Series, name: str, *, allow_missing: bool = False) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(values):
        if values.dt.tz is None:
            raise ValueError(f"{name} doit inclure un fuseau horaire.")
        return values.dt.tz_convert("UTC")

    parsed: list[pd.Timestamp] = []
    for value in values:
        if pd.isna(value):
            if allow_missing:
                parsed.append(pd.NaT)
                continue
            raise ValueError(f"{name} contient une date absente.")
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            raise ValueError(f"{name} doit inclure un fuseau horaire.")
        parsed.append(timestamp.tz_convert("UTC"))
    return pd.Series(pd.DatetimeIndex(parsed), index=values.index, name=values.name)

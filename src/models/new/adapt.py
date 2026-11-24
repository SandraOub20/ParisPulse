"""Correction locale du biais estimée sur des journées de rejeu dans le support E3."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from time import perf_counter

import numpy as np
import pandas as pd

from src.models.schemas import HORIZON_HOURS, Case, ForecastInputs, ForecastResult

CALIBRATION_VERSION = "local-median-bias-v1"
MIN_CALIBRATION_PAIRS = 12
MIN_CONTEXT_HOURS = 24
MAX_REPLAY_ORIGINS = 2
SHRINKAGE_HOURS = 24
LOCAL_TZ = "Europe/Paris"


def adapt(
    inputs: ForecastInputs,
    frozen: ForecastResult,
    replay: Callable[[Case], ForecastResult],
) -> ForecastResult:
    """Réestimer un biais additif par cas, en conservant les poids du modèle gelé."""
    started = perf_counter()
    case = inputs.case
    lag = case.origin - inputs.information_cutoff
    horizon = pd.Timedelta(hours=HORIZON_HOURS)
    first = (
        (case.support_start + lag + pd.Timedelta(hours=MIN_CONTEXT_HOURS))
        .tz_convert(LOCAL_TZ)
        .ceil("D")
    )
    last = (case.support_end - horizon).tz_convert(LOCAL_TZ).normalize()
    origins = pd.date_range(first, last, freq="D").tz_convert("UTC")[-MAX_REPLAY_ORIGINS:]
    observed = inputs.history.set_index("timestamp")["count"]
    residuals = []
    replayed_at = []
    refusals = []
    reason = "adaptation_frozen_model_refused" if frozen.status != "ok" else None

    if reason is None:
        for origin in origins:
            targets = observed.loc[(observed.index >= origin) & (observed.index < origin + horizon)]
            if targets.notna().sum() < MIN_CALIBRATION_PAIRS:
                continue
            calibration_case = replace(
                case,
                case_id=f"{case.case_id}-replay-{origin:%Y%m%dT%H%MZ}",
                origin=origin,
                support_end=origin - lag,
            )
            try:
                prediction = replay(calibration_case).predictions
            except ValueError as error:
                refusals.append(str(error))
                continue
            values = prediction.loc[prediction["prediction_status"].eq("ok")].set_index(
                "target_timestamp"
            )["y_pred"]
            errors = (targets - values).dropna()
            if not errors.empty:
                residuals.extend(errors.tolist())
                replayed_at.append(origin.isoformat())

    count = len(residuals)
    if reason is None and count < MIN_CALIBRATION_PAIRS:
        reason = "adaptation_insufficient_local_pairs"

    details = {
        "algorithm": CALIBRATION_VERSION,
        "base_model_run_id": frozen.model_run_id,
        "support_id": inputs.support_id,
        "cutoff_utc": inputs.information_cutoff.isoformat(),
        "replay_origins_utc": replayed_at,
        "paired_hours": count,
        "minimum_paired_hours": MIN_CALIBRATION_PAIRS,
        "shrinkage_hours": SHRINKAGE_HOURS,
        "refusals": refusals,
    }
    predictions = frozen.predictions.copy()
    adaptation_id = None
    status = frozen.status
    if reason is None:
        bias = float(np.median(residuals)) * count / (count + SHRINKAGE_HOURS)
        details.update(status="applied", bias_bikes_per_hour=bias)
        payload = json.dumps(details, sort_keys=True, allow_nan=False).encode()
        adaptation_id = f"e3-bias-{hashlib.sha256(payload).hexdigest()[:16]}"
        predictions["y_pred"] = (predictions["y_pred"] + bias).clip(lower=0)
        predictions["method_used"] += "+local_bias"
    else:
        details.update(status="fallback", reason=reason)
        available = predictions["prediction_status"].isin(("ok", "fallback"))
        predictions.loc[available, "prediction_status"] = "fallback"
        previous_reason = predictions["status_reason"].fillna("")
        predictions["status_reason"] = reason + previous_reason.map(
            lambda value: f";{value}" if value else ""
        )
        if available.all():
            status = "fallback"

    return replace(
        frozen,
        method_run_id=frozen.method_run_id.replace("-frozen-", "-adapted-"),
        variant="adapted",
        predictions=predictions,
        status=status,
        status_reason=reason,
        adaptation_id=adaptation_id,
        adaptation=details,
        cost=replace(frozen.cost, adaptation_seconds=perf_counter() - started),
    )

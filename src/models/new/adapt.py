"""Adaptation des modèles E3 à l'historique autorisé d'un nouveau site."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ._core import manager

_ALLOWED_BUDGETS = {24, 72, 168}
_CALIBRATION_HORIZON_HOURS = 24
_MIN_CONTEXT_HOURS = 6
_MIN_TRAINING_SAMPLES = 8
_MIN_VALIDATION_SAMPLES = 5
_RIDGE_STRENGTH = 4.0
_ONE_DAY_RIDGE_STRENGTH = 8.0
_LOCAL_TIMEZONE = "Europe/Paris"

_BLEND_WEIGHTS_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "models"
    / "e3-chronos2-adapted-v2"
    / "blend_weights.json"
)

# Adapted-v1
@dataclass
class Chronos2Calibrator:
    """Conserve le Chronos gelé et les seules corrections apprises localement."""

    model: Any
    local_budget_hours: int
    coefficients: dict[str, tuple[float, float]]

    def correct_v1(self, predictions: pd.DataFrame) -> pd.DataFrame:
        """Appliquer ``max(0, a * prévision + b)`` selon l'heure cible."""
        required = {"target_timestamp", "y_pred"}
        if not required.issubset(predictions.columns):
            raise ValueError(
                "Les prévisions Chronos adaptées doivent avoir target_timestamp et y_pred."
            )

        corrected = predictions.copy()
        raw_values = pd.to_numeric(corrected["y_pred"], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(raw_values).all():
            raise ValueError("Les prévisions Chronos à calibrer doivent être finies.")

        # La correction horaire est exprimée en heure de Paris, pas en heure UTC.
        timestamps = pd.to_datetime(corrected["target_timestamp"], utc=True)
        buckets = timestamps.dt.tz_convert(_LOCAL_TIMEZONE).dt.hour.map(_time_bucket_v1)
        values = np.empty_like(raw_values)
        clipped = np.zeros(len(values), dtype=bool)
        for index, (bucket, raw_value) in enumerate(zip(buckets, raw_values, strict=True)):
            # Un calibrateur global sert de repli quand une plage manque de données.
            a, b = self.coefficients.get(bucket, self.coefficients["global"])
            calibrated = a * max(0.0, raw_value) + b
            clipped[index] = calibrated < 0
            values[index] = max(0.0, calibrated)

        corrected["y_pred"] = values
        if "status_reason" in corrected and clipped.any():
            reasons = corrected["status_reason"].astype(object).to_numpy(copy=True)
            for index in np.flatnonzero(clipped):
                previous = reasons[index]
                reasons[index] = (
                    "calibration_clipped_to_zero"
                    if previous is None or pd.isna(previous)
                    else f"{previous};calibration_clipped_to_zero"
                )
            corrected["status_reason"] = reasons
        return corrected

# Adapted-v2
def hourly_profile(history: pd.DataFrame) -> dict[int, float]:
    """Calculer la médiane observée pour chaque heure locale de Paris."""
    timestamps = pd.to_datetime(history["timestamp"], utc=True)
    hours = timestamps.dt.tz_convert(_LOCAL_TIMEZONE).dt.hour.to_numpy()
    values = pd.to_numeric(history["count"], errors="coerce").to_numpy(dtype=float)
    series = pd.Series(values, index=hours).dropna()
    return {int(hour): float(value) for hour, value in series.groupby(level=0).median().items()}


def profile_values(profile: dict[int, float], target_timestamps: pd.Series) -> np.ndarray:
    """Récupérer la valeur du profil pour chaque heure cible."""
    hours = pd.to_datetime(target_timestamps, utc=True).dt.tz_convert(_LOCAL_TIMEZONE).dt.hour
    return np.array([profile.get(int(hour), np.nan) for hour in hours], dtype=float)


def blend_forecast(p: np.ndarray, q: np.ndarray, weight: float) -> np.ndarray:
    """Mélanger Chronos et le profil local, en retenant Chronos si le profil manque."""
    chronos = np.maximum(np.asarray(p, dtype=float), 0.0)
    profile = np.asarray(q, dtype=float)
    mixed = np.where(np.isnan(profile), chronos, weight * chronos + (1.0 - weight) * profile)
    return np.maximum(mixed, 0.0)


def _load_blend_weight(budget: int, path: Path | None = None) -> float:
    weights_path = _BLEND_WEIGHTS_PATH if path is None else path
    if not weights_path.exists():
        raise FileNotFoundError(f"Fichier de poids de mélange introuvable : {weights_path}")
    data = json.loads(weights_path.read_text(encoding="utf-8"))
    weights = data.get("weights")
    if not isinstance(weights, dict) or str(budget) not in weights:
        raise KeyError(f"Pas de poids appris pour le budget {budget} h dans {weights_path}.")
    weight = float(weights[str(budget)])
    if not 0.0 <= weight <= 1.0:
        raise ValueError(f"Poids de mélange invalide : {weight}")
    return weight


@dataclass
class Chronos2BlendAdapter:
    """Chronos gelé mélangé au profil horaire du support local."""

    model: Any
    local_budget_hours: int
    weight: float
    profile: dict[int, float]

    def correct(self, predictions: pd.DataFrame) -> pd.DataFrame:
        required = {"target_timestamp", "y_pred"}
        if not required.issubset(predictions.columns):
            raise ValueError("Il faut target_timestamp et y_pred.")
        corrected = predictions.copy()
        chronos = pd.to_numeric(corrected["y_pred"], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(chronos).all():
            raise ValueError("Les prévisions Chronos à mélanger doivent être finies.")
        profile = profile_values(self.profile, corrected["target_timestamp"])
        corrected["y_pred"] = blend_forecast(chronos, profile, self.weight)
        return corrected


def adapt(
    model_name: str,
    history: pd.DataFrame,
    *,
    local_budget_hours: int | None = None,
):
    """Retourner le modèle 'model_name' adapté."""
    if model_name == "chronos-2":

        budget = _resolve_budget_v1(history, local_budget_hours)
        weight = _load_blend_weight(budget)
        model = manager.load_model(model_name)

        return Chronos2BlendAdapter(
            model=model,
            local_budget_hours=budget,
            weight=weight,
            profile=hourly_profile(history),
        )

    elif model_name == "google_TimesFM_2.5":
        raise NotImplementedError(f"adapt() n'est pas implémenté pour {model_name}.")

    elif model_name == "team2":
        raise NotImplementedError(f"adapt() n'est pas implémenté pour {model_name}.")
    
    else:
        raise ValueError(f"Modèle inconnu : {model_name}")

def _resolve_budget_v1(history: pd.DataFrame, local_budget_hours: int | None) -> int:
    """Autoriser explicitement les budgets d'un et trois jours, jamais sept."""
    if local_budget_hours is not None:
        budget = int(local_budget_hours)
    else:
        # Cet inféré couvre les appels directs à adapt_v1() qui n'ont pas de Case.
        if "timestamp" not in history or history.empty:
            raise ValueError("L'historique Chronos doit contenir au moins un timestamp.")
        timestamps = pd.to_datetime(history["timestamp"], utc=True)
        budget = int((timestamps.max() - timestamps.min()) / pd.Timedelta(hours=1)) + 1

    if budget not in _ALLOWED_BUDGETS:
        raise ValueError(
            "L'adaptation de Chronos-2 est limitée aux budgets locaux de 24 h, 72 h et 168 h."
        )
    return budget


def _fit_chronos_calibrator_v1(
    model: Any, history: pd.DataFrame, budget: int
) -> dict[str, tuple[float, float]]:
    """Ajuster des corrections ridge sur des prévisions à origines glissantes."""
    if not {"timestamp", "count"}.issubset(history.columns):
        raise ValueError("L'historique Chronos doit contenir les colonnes timestamp et count.")
    if history.empty:
        raise ValueError("L'historique Chronos ne peut pas être vide.")

    # Le support fourni par predict.py est déjà limité au compteur, au budget et
    # aux mesures admissibles à l'origine. On valide son ordre avant les fenêtres.
    timestamps = pd.to_datetime(history["timestamp"], utc=True)
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise ValueError("Les timestamps de l'historique Chronos doivent être uniques et triés.")
    if len(timestamps) > 1 and not (timestamps.diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("L'historique Chronos doit être une grille horaire régulière.")

    counts = pd.to_numeric(history["count"], errors="coerce").to_numpy(dtype=float)
    if np.isinf(counts).any() or (counts[np.isfinite(counts)] < 0).any():
        raise ValueError("L'historique Chronos contient une mesure non finie ou négative.")

    # Avec 24 h, on ajuste un seul couple global : les sous-groupes seraient trop
    # fragiles. Avec 72 h ou 168 h, matin/soir peuvent être distingués si les données suffisent.
    identity = {"global": (1.0, 0.0)}
    if len(history) > budget:
        raise ValueError("L'historique Chronos dépasse le budget local déclaré.")
    if len(timestamps) < _MIN_CONTEXT_HOURS + 2:
        return identity

    calibration_rows = _rolling_residuals_v1(model, timestamps, counts)
    if calibration_rows.empty:
        return identity

    # On réserve les origines les plus récentes à la validation. Le choix de
    # correction ne s'appuie donc pas uniquement sur les fenêtres ayant servi à
    # l'ajustement.
    origins = sorted(calibration_rows["origin_index"].unique())
    if len(origins) < 4:
        return identity
    split = max(1, int(len(origins) * 0.7))
    training_origins = set(origins[:split])
    validation_origins = set(origins[split:])
    training = calibration_rows.loc[calibration_rows["origin_index"].isin(training_origins)]
    validation = calibration_rows.loc[calibration_rows["origin_index"].isin(validation_origins)]

    ridge_strength = _ONE_DAY_RIDGE_STRENGTH if budget == 24 else _RIDGE_STRENGTH
    global_coefficients = _validated_coefficients_v1(
        training, validation, ridge_strength=ridge_strength
    )
    coefficients = {"global": global_coefficients}

    if budget in {72, 168}:
        # Les groupes sont des heures locales de la journée : un créneau matin,
        # un créneau soir, et le reste. Un groupe peu représenté garde le global.
        for bucket in ("morning", "evening", "other"):
            train_group = training.loc[training["bucket"] == bucket]
            valid_group = validation.loc[validation["bucket"] == bucket]
            if (
                len(train_group) < _MIN_TRAINING_SAMPLES
                or len(valid_group) < _MIN_VALIDATION_SAMPLES
            ):
                continue
            coefficients[bucket] = _validated_coefficients_v1(
                train_group,
                valid_group,
                fallback=global_coefficients,
                ridge_strength=ridge_strength,
            )
    return coefficients


def _rolling_residuals_v1(model: Any, timestamps: pd.Series, counts: np.ndarray) -> pd.DataFrame:
    """Créer des résidus sans sortir de la période d'historique autorisée."""
    context_frames: list[pd.DataFrame] = []
    origin_by_id: dict[str, int] = {}
    for origin_index in range(_MIN_CONTEXT_HOURS - 1, len(timestamps) - 1):
        # Les trous sont permis dans le contexte, mais une origine sans assez de
        # mesures passées ne fournit pas de prévision locale utile.
        if np.isfinite(counts[: origin_index + 1]).sum() < _MIN_CONTEXT_HOURS:
            continue
        item_id = f"calibration-{origin_index}"
        origin_by_id[item_id] = origin_index
        context_frames.append(
            pd.DataFrame(
                {
                    "item_id": item_id,
                    # Chronos reçoit des timestamps sans fuseau représentant UTC.
                    "timestamp": timestamps.iloc[: origin_index + 1].dt.tz_localize(None),
                    "target": counts[: origin_index + 1],
                }
            )
        )

    if not context_frames:
        return pd.DataFrame()

    rolling_context = pd.concat(context_frames, ignore_index=True)
    output = model.predict_df(
        rolling_context,
        prediction_length=_CALIBRATION_HORIZON_HOURS,
        quantile_levels=[0.5],
        id_column="item_id",
        timestamp_column="timestamp",
        target="target",
    )
    if not isinstance(output, pd.DataFrame) or not {"item_id", "timestamp"}.issubset(
        output.columns
    ):
        raise TypeError(
            "Chronos-2 doit retourner item_id et timestamp pour les fenêtres glissantes."
        )
    quantile_column = next(
        (column for column in output.columns if column == 0.5 or str(column) == "0.5"),
        None,
    )
    if quantile_column is None:
        raise ValueError("La sortie Chronos-2 glissante ne contient pas le quantile 0.5.")

    output = output.copy()
    output["timestamp"] = pd.to_datetime(output["timestamp"], utc=True)
    forecast_map = {
        item_id: group.set_index("timestamp")[quantile_column]
        for item_id, group in output.groupby("item_id", sort=False)
    }
    actual_map = pd.Series(counts, index=pd.DatetimeIndex(timestamps))

    rows: list[dict[str, Any]] = []
    for item_id, origin_index in origin_by_id.items():
        forecasts = forecast_map.get(item_id)
        if forecasts is None:
            continue
        origin_timestamp = timestamps.iloc[origin_index]
        # Seules les cibles observées et strictement postérieures à l'origine
        # deviennent des résidus. Aucune valeur hors de history n'est consultée.
        for target_timestamp, forecast in forecasts.items():
            horizon = int((target_timestamp - origin_timestamp) / pd.Timedelta(hours=1))
            if not 1 <= horizon <= _CALIBRATION_HORIZON_HOURS:
                continue
            actual = actual_map.get(target_timestamp, np.nan)
            if not np.isfinite(forecast) or not np.isfinite(actual):
                continue
            local_hour = target_timestamp.tz_convert(_LOCAL_TIMEZONE).hour
            rows.append(
                {
                    "origin_index": origin_index,
                    "bucket": _time_bucket_v1(local_hour),
                    "forecast": max(0.0, float(forecast)),
                    "actual": float(actual),
                }
            )
    return pd.DataFrame(rows)


def _validated_coefficients_v1(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    fallback: tuple[float, float] = (1.0, 0.0),
    ridge_strength: float = _RIDGE_STRENGTH,
) -> tuple[float, float]:
    """Garder une correction seulement si MAE et RMSE baissent en validation."""
    if len(training) < _MIN_TRAINING_SAMPLES or len(validation) < _MIN_VALIDATION_SAMPLES:
        return fallback

    candidate = _ridge_coefficients_v1(training["forecast"], training["actual"], ridge_strength)
    baseline_values = validation["forecast"].to_numpy(dtype=float)
    actual_values = validation["actual"].to_numpy(dtype=float)
    corrected_values = np.maximum(0.0, candidate[0] * baseline_values + candidate[1])

    # Exiger une amélioration des deux métriques sur les origines réservées évite
    # de retenir une correction qui n'aide que la moyenne quadratique ou absolue.
    baseline_mae, baseline_rmse = _errors_v1(baseline_values, actual_values)
    corrected_mae, corrected_rmse = _errors_v1(corrected_values, actual_values)
    if corrected_mae < baseline_mae and corrected_rmse < baseline_rmse:
        return candidate
    return fallback


def _ridge_coefficients_v1(
    forecasts: pd.Series, actuals: pd.Series, ridge_strength: float
) -> tuple[float, float]:
    """Résoudre une régression linéaire régularisée vers a=1 et b=0."""
    x = forecasts.to_numpy(dtype=float)
    y = actuals.to_numpy(dtype=float)
    scale = max(1.0, float(np.median(np.abs(x))))

    # On ajuste les écarts à la prévision gelée. La pénalité sur les deux
    # coefficients ramène fortement le résultat vers l'identité, en particulier
    # quand le budget local ne contient que 24 heures.
    features = np.column_stack((x / scale, np.ones(len(x))))
    residuals = (y - x) / scale
    gram = features.T @ features / len(x)
    right_hand_side = features.T @ residuals / len(x)
    adjustment = np.linalg.solve(gram + ridge_strength * np.eye(2), right_hand_side)
    a = float(np.clip(1.0 + adjustment[0], 0.5, 1.5))
    b = float(np.clip(adjustment[1] * scale, -scale, scale))
    return a, b


def _errors_v1(predictions: np.ndarray, actuals: np.ndarray) -> tuple[float, float]:
    errors = predictions - actuals
    return float(np.mean(np.abs(errors))), float(np.sqrt(np.mean(errors**2)))


def _time_bucket_v1(hour: int) -> str:
    """Classer une heure de Paris dans un petit nombre de plages."""
    if 6 <= hour <= 11:
        return "morning"
    if 17 <= hour <= 22:
        return "evening"
    return "other"

"""Routage des prévisions à la demande et des résultats archivés."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from src.app import v1_service
from src.common.config import load_config
from src.eval.cases import E3_ROLES, forecasting_team, interactive_case
from src.models.known.baseline import weekly_reference
from src.models.known.predict import load_context, predict_24h
from src.models.new import predict as new_predict
from src.models.schemas import (
    CASE_RUNS_COLUMNS,
    FORECAST_COLUMNS,
    HORIZON_HOURS,
    Case,
    ForecastResult,
    target_timestamps,
)

LOCAL_TZ = v1_service.LOCAL_TZ
VALID_STATUSES = {"ok", "fallback"}
REFERENCE_LABELS = {
    "reference": "Même heure la semaine précédente",
    "reference_profile": "Médiane des quatre semaines précédentes",
}
HGB = "hgb"
# Méthodes d'un site connu. La première est proposée par défaut : EXP-E2-03 retient le HGB.
KNOWN_SITE_LABELS = {HGB: "HGB (modèle entraîné)", **REFERENCE_LABELS}
LOCAL_REFERENCE = "local_reference"
CHRONOS_LIVE = "chronos_live"
COMPARE_REFERENCES = "compare_references"
COMPARE_CHRONOS = "compare_chronos"
COMPARE_ARCHIVE_PREFIX = "compare_archive:"
CONTEXT_LABELS = {
    "is_holiday": "Jour férié",
    "is_school_holiday": "Vacances scolaires",
    "is_strike": "Grève des transports",
    "temp_prev": "Température prévue (°C)",
    "rain_prev": "Précipitations prévues (mm)",
    "wind_prev": "Vent prévu (km/h)",
}


@dataclass
class Study:
    case: Case
    forecast: pd.DataFrame
    runs: pd.DataFrame
    source: str
    publication_lag_hours: int | None


def method_label(study: Study) -> str:
    variant = study.forecast["variant"].iloc[0]
    run_id = str(study.forecast["method_run_id"].iloc[0])
    if variant == LOCAL_REFERENCE:
        return "Référence locale"
    if variant == "frozen" and "chronos" in run_id:
        return "Chronos-2 gelé"
    if variant == HGB and not study.forecast["method_used"].eq(HGB).any():
        return "Repli du HGB sur la référence"
    return KNOWN_SITE_LABELS.get(variant, run_id)


def verify_same_support(first: Study, second: Study) -> None:
    first_id = first.forecast["support_id"].dropna().unique().tolist()
    second_id = second.forecast["support_id"].dropna().unique().tolist()
    if len(first_id) != 1 or first_id != second_id:
        raise ValueError(
            "Les méthodes ne déclarent pas le même historique local. "
            "Vous pouvez consulter leurs prévisions séparément."
        )


def archived_forecasts(paths: tuple[Path, ...], snapshot_id: str) -> pd.DataFrame:
    """Indexer les sorties E3 livrées, y compris les cas dont le calcul a échoué."""
    tables = []
    for path in paths:
        forecasts = pd.read_csv(path, dtype="string", usecols=FORECAST_COLUMNS)
        forecasts = forecasts.loc[
            forecasts["snapshot_id"].eq(snapshot_id) & forecasts["scenario"].eq("new_site")
        ].copy()
        if forecasts.empty:
            continue
        forecasts["archive"] = str(path)
        tables.append(forecasts)
    columns = [*FORECAST_COLUMNS, "archive"]
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=columns)


def archived_cases(
    catalog: pd.DataFrame, counter: pd.Series, evaluation: pd.DataFrame
) -> list[Case]:
    rows = catalog.loc[catalog["counter_id"].eq(counter["counter_id"])].drop_duplicates("case_id")
    if rows.empty:
        return []
    by_id = {} if evaluation.empty else evaluation.set_index("case_id").to_dict("index")
    cases = []
    for row in rows.to_dict("records"):
        details = by_id.get(row["case_id"])
        if details is not None:
            case = Case.from_row({**details, "case_id": row["case_id"]})
            if (
                case.counter_id != row["counter_id"]
                or case.scenario != "new_site"
                or case.protocol_id != row["protocol_id"]
                or case.snapshot_id != row["snapshot_id"]
                or case.origin != pd.Timestamp(row["origin"])
            ):
                raise ValueError(f"Le cas E4 {case.case_id} ne correspond pas à l’archive E3.")
        else:
            # Le format des identifiants et le délai de 24 h sont ceux de proto-v1.
            prefix, sep, suffix = row["case_id"].rpartition("_b")
            origin = pd.Timestamp(row["origin"])
            expected = f"{row['counter_id']}_{origin:%Y%m%dT%H}_new_site"
            budget = (
                int(suffix)
                if row["protocol_id"] == "proto-v1"
                and prefix == expected
                and sep
                and suffix in ("24", "72", "168")
                else None
            )
            support_end = origin - pd.Timedelta(hours=24) if budget else None
            support_start = support_end - pd.Timedelta(hours=budget) if budget else None
            case = Case.from_row(
                {
                    **row,
                    "site_group_id": optional_text(counter["site_group_id"]),
                    "spatial_role": optional_text(counter["site_role"]),
                    "local_budget_hours": budget,
                    "support_start": support_start,
                    "support_end": support_end,
                }
            )
        cases.append(case)
    return sorted(cases, key=lambda case: (case.origin, case.local_budget_hours or 0, case.case_id))


def optional_text(value: object) -> str:
    return "" if pd.isna(value) else str(value)


def counter_role(counter: pd.Series) -> str | None:
    """Identifier le rôle du compteur à partir de l'inventaire E1."""
    status = optional_text(counter.get("selection_status"))
    if status.startswith("excluded"):
        return None
    role_from_status = {
        "retained": "S_train",
        "robustness": "S_train",
        "reserved_dev_new": "S_dev_new",
        "reserved_test_new": "S_test_new",
    }.get(status)
    declared = optional_text(counter.get("site_role"))
    if declared and role_from_status and declared != role_from_status:
        return None
    role = declared or role_from_status
    return role if role == "S_train" or role in E3_ROLES else None


def default_known_day(first_day: date, last_day: date) -> date:
    """Date proposée pour un site connu : la fin de la validation, jamais le test réservé.

    Sans date de validation dans la configuration, l'avant-dernier jour mesuré est proposé.
    """
    validation_end = (load_config().get("protocol") or {}).get("validation_until")
    if validation_end is None:
        wanted = (pd.Timestamp(last_day) - pd.Timedelta(days=1)).date()
    else:
        wanted = pd.Timestamp(validation_end).date()
    return min(max(first_day, wanted), last_day)


def technical_case(counter: pd.Series, day: date, snapshot_id: str) -> Case:
    return interactive_case(
        str(counter["counter_id"]),
        optional_text(counter.get("site_group_id")) or None,
        counter_role(counter) or "",
        day,
        snapshot_id,
    )


def technical_new_case(
    counter: pd.Series, day: date, snapshot_id: str, budget: int, lag: int
) -> Case:
    return interactive_case(
        str(counter["counter_id"]),
        optional_text(counter.get("site_group_id")) or None,
        counter_role(counter) or "",
        day,
        snapshot_id,
        local_budget_hours=budget,
        publication_lag_hours=lag,
    )


def study_from_result(result: ForecastResult, source: str, lag: int) -> Study:
    return Study(
        result.case,
        validate_forecast(result.to_forecast_frame(), result.case),
        pd.DataFrame([result.to_run_row()], columns=CASE_RUNS_COLUMNS),
        source,
        lag,
    )


def calculate_reference(
    case: Case, history: pd.DataFrame, variant: str, publication_lag_hours: int
) -> Study:
    past = measured_history(case, history, publication_lag_hours)
    result = predict_24h(case, past, variant=variant, publication_lag_hours=publication_lag_hours)
    return study_from_result(result, "Référence E2 calculée à la demande", publication_lag_hours)


def calculate_hgb(
    case: Case,
    history: pd.DataFrame,
    publication_lag_hours: int,
    context: pd.DataFrame | None = None,
) -> Study:
    """Appeler le HGB d'E2 avec le contexte E1 ; s'il refuse le cas, E2 sert la référence."""
    if context is None:
        # Sans contexte, le modèle se replie toujours sur la référence.
        context = load_context(case.snapshot_id)
    result = predict_24h(
        case,
        measured_history(case, history, publication_lag_hours),
        variant=HGB,
        context=context,
        publication_lag_hours=publication_lag_hours,
    )
    used = result.predictions["method_used"].eq(HGB).any()
    source = (
        "HGB E2 calculé à la demande"
        if used
        else "Référence calculée à la demande après refus du HGB"
    )
    return study_from_result(result, source, publication_lag_hours)


def measured_history(case: Case, history: pd.DataFrame, publication_lag_hours: int) -> pd.DataFrame:
    """Historique publié du cas où `count` ne contient que les mesures réelles."""
    past = published_history(case, history, publication_lag_hours).copy()
    past["count"] = past["count_raw"].where(past["is_observed"])
    return past


def calculate_local_reference(case: Case, history: pd.DataFrame, lag: int) -> Study:
    """Appliquer la référence E2 avec exactement le support autorisé pour E3."""
    if forecasting_team(case) != "E3":
        raise ValueError("La référence locale est réservée aux sites E3.")
    started = perf_counter()
    inputs, _, _ = new_predict.prepare_inputs(case, published_history(case, history, lag), lag)
    preparation = perf_counter() - started
    result = weekly_reference(inputs, LOCAL_REFERENCE, method_run_id="local-weekly-reference")
    result.cost.preparation_seconds = preparation
    return study_from_result(result, "Référence locale E3 calculée à la demande", lag)


def calculate_chronos(case: Case, history: pd.DataFrame, lag: int) -> Study:
    result = new_predict.predict_24h(
        case, published_history(case, history, lag), publication_lag_hours=lag
    )
    # Le suffixe distingue ce calcul de l'archive qui porte le même identifiant E3.
    result.method_run_id = f"{result.method_run_id}-live"
    return study_from_result(result, "Chronos-2 E3 gelé calculé à la demande", lag)


def published_history(case: Case, history: pd.DataFrame, lag: int) -> pd.DataFrame:
    """Limiter les entrées transmises au moteur à la fenêtre autorisée du compteur."""
    if lag < 0:
        raise ValueError("Le délai de publication doit être positif ou nul.")
    cutoff = case.origin - pd.Timedelta(hours=lag)
    mask = history["counter_id"].eq(case.counter_id) & history["interval_end"].le(cutoff)
    if case.scenario == "new_site":
        if not case.local_budget_hours or case.local_budget_hours < 0:
            raise ValueError("Le cas E3 doit préciser un budget local positif.")
        earliest = cutoff - pd.Timedelta(hours=case.local_budget_hours)
        start = case.support_start if case.support_start is not None else earliest
        end = case.support_end if case.support_end is not None else cutoff
        if not earliest <= start < end <= cutoff:
            raise ValueError("Les bornes du support E3 dépassent le budget local autorisé.")
        mask &= history["timestamp"].ge(start) & history["interval_end"].le(end)
    return history.loc[mask]


def open_archive(case: Case, catalog: pd.DataFrame, file: Path, method_run_id: str) -> Study:
    rows = catalog.loc[
        catalog["case_id"].eq(case.case_id)
        & catalog["archive"].eq(str(file))
        & catalog["method_run_id"].eq(method_run_id),
        FORECAST_COLUMNS,
    ]
    forecast = validate_forecast(rows, case)
    run_path = file.with_name(file.name.removesuffix(".pred.csv") + ".runs.csv")
    runs = pd.DataFrame(columns=CASE_RUNS_COLUMNS)
    if run_path.is_file():
        logs = pd.read_csv(run_path, dtype="string", usecols=CASE_RUNS_COLUMNS)
        runs = logs.loc[
            logs["case_id"].eq(case.case_id)
            & logs["method_run_id"].eq(method_run_id)
            & logs["protocol_id"].eq(case.protocol_id)
            & logs["snapshot_id"].eq(case.snapshot_id)
            & logs["model_run_id"].eq(forecast["model_run_id"].iloc[0])
        ]
        if len(runs) > 1:
            raise ValueError(f"Exécutions archivées en double pour le cas {case.case_id}.")
    return Study(case, forecast, runs, f"{file.parent.name}/{file.name}", None)


def run_studies(
    case: Case,
    method: str,
    archive: Path | None,
    history: pd.DataFrame,
    catalog: pd.DataFrame | None,
    lag: int,
    *,
    context: pd.DataFrame | None = None,
) -> tuple[Study, ...]:
    """Exécuter le moteur désigné par le cas E4, ou ouvrir une archive explicite."""
    if forecasting_team(case) == "E2":
        variants = tuple(REFERENCE_LABELS) if method == COMPARE_REFERENCES else (method,)
        if archive is not None or any(variant not in KNOWN_SITE_LABELS for variant in variants):
            raise ValueError("La méthode sélectionnée est incompatible avec un cas E2.")
        return tuple(
            calculate_hgb(case, history, lag, context)
            if variant == HGB
            else calculate_reference(case, history, variant, lag)
            for variant in variants
        )

    if archive is not None:
        if catalog is None:
            raise ValueError("Le catalogue des prévisions archivées est indisponible.")
        archived_id = method.removeprefix(COMPARE_ARCHIVE_PREFIX)
        stored = open_archive(case, catalog, archive, archived_id)
        if method == archived_id:
            return (stored,)
        reference = calculate_local_reference(case, history, lag)
        verify_same_support(reference, stored)
        return reference, stored
    if method == LOCAL_REFERENCE:
        return (calculate_local_reference(case, history, lag),)
    if method == CHRONOS_LIVE:
        return (calculate_chronos(case, history, lag),)
    if method == COMPARE_CHRONOS:
        reference = calculate_local_reference(case, history, lag)
        chronos = calculate_chronos(case, history, lag)
        verify_same_support(reference, chronos)
        return reference, chronos
    raise ValueError("La méthode sélectionnée est incompatible avec un cas E3.")


def validate_forecast(rows: pd.DataFrame, case: Case) -> pd.DataFrame:
    """Contrôler les métadonnées et le contrat avant affichage ou export."""
    if not rows.empty:
        horizons = pd.to_numeric(rows["horizon"], errors="raise")
        if not horizons.isin(range(1, HORIZON_HOURS + 1)).all():
            raise ValueError("Les horizons doivent être entiers et compris entre 1 et 24.")
        if not pd.to_datetime(rows["origin"], format="ISO8601", utc=True).eq(case.origin).all():
            raise ValueError("L’origine archivée diffère de celle du cas.")
        if not rows["scenario"].fillna("").eq(case.scenario).all():
            raise ValueError("Le scénario archivé diffère de celui du cas.")
    result = v1_service.validate_forecast(rows, case)
    values = pd.to_numeric(rows["y_pred"], errors="raise")
    valid = rows["prediction_status"].str.lower().isin(VALID_STATUSES)
    if values[~valid].notna().any():
        raise ValueError("Une heure en échec doit avoir une prévision vide.")
    result["prediction_status"] = result["prediction_status"].str.lower()
    return result[FORECAST_COLUMNS]


def reveal(study: Study, history: pd.DataFrame) -> dict:
    """Récupérer les mesures cibles et évaluer la prévision existante."""
    case = study.case
    targets = target_timestamps(case.origin)
    mask = history["counter_id"].eq(case.counter_id) & history["timestamp"].isin(
        targets["target_timestamp"]
    )
    window = history.loc[mask].copy()
    window["timestamp"] = pd.to_datetime(window["timestamp"], utc=True)
    window["count_raw"] = pd.to_numeric(window["count_raw"], errors="coerce")
    window["is_scoreable"] = (
        window["is_scoreable"].eq(True)
        & window["count_raw"].ge(0)
        & np.isfinite(window["count_raw"])
    )
    window["count_raw"] = window["count_raw"].where(window["is_scoreable"])
    observations = targets.merge(
        window[["timestamp", "count_raw", "is_scoreable"]].rename(
            columns={"timestamp": "target_timestamp", "count_raw": "y_true"}
        ),
        how="left",
        on="target_timestamp",
        validate="one_to_one",
    )
    observations.insert(0, "counter_id", case.counter_id)
    observations.insert(0, "case_id", case.case_id)
    observations["is_scoreable"] = observations["is_scoreable"].eq(True)
    return {
        **v1_service.evaluate_local(case, study.forecast, window),
        "observations": observations,
    }


def context_for_case(context: pd.DataFrame, case: Case) -> pd.DataFrame:
    """Sélectionner calendrier et bulletins disponibles pour les heures visées."""
    if context.empty:
        return context
    hours = target_timestamps(case.origin)["target_timestamp"]
    days = hours.dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d")
    available = pd.to_datetime(context["available_at"], format="ISO8601", utc=True)
    valid = pd.to_datetime(context["valid_time"], format="ISO8601", utc=True)
    calendar = context["role"].eq("known_calendar") & context["local_date"].isin(days)
    weather = context["role"].eq("forecast_bulletin") & valid.isin(hours + pd.Timedelta(hours=1))
    return context.loc[
        context["variable"].isin(CONTEXT_LABELS)
        & (calendar | weather)
        & (available.le(case.origin) | (calendar & available.isna()))
    ].copy()

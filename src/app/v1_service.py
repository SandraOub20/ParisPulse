"""V1 ParisPulse : lecture E1, appel E2 et contrôle MAE indépendant d'E4.

Aucun modèle n'est réimplémenté dans ce module. L'évaluation locale est provisoire
et utilise uniquement les observations marquées is_scoreable par E1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LOCAL_TZ = "Europe/Paris"
SNAPSHOT_DEFAULT = "hist-20261117"
COUNT_INPUT_COLUMNS = [
    "counter_id", "timestamp", "interval_end", "count_raw", "count",
    "is_observed", "is_scoreable",
]
ERROR_COLUMNS = [
    "case_id", "counter_id", "horizon", "target_timestamp", "method_run_id",
    "y_true", "y_pred", "is_scoreable", "signed_error", "absolute_error",
    "squared_error", "protocol_id", "snapshot_id",
]


def bool_series(series: pd.Series) -> pd.Series:
    """Convertit correctement les booléens E1, y compris lus depuis un CSV."""
    return series.astype("string").str.strip().str.lower().isin(("true", "1"))


def snapshot_dirs(root: Path = ROOT) -> list[Path]:
    return sorted(
        (p.parent for p in (root / "data" / "processed").glob("*/counters.csv")),
        key=lambda p: p.name,
        reverse=True,
    )


def load_inventory(snapshot_dir: Path) -> pd.DataFrame:
    """Une ligne par *compteur directionnel*, jamais de somme entre directions."""
    counter_file = snapshot_dir / "counters.csv"
    if not counter_file.is_file():
        raise FileNotFoundError(f"Fichier absent : {counter_file}")
    counters = pd.read_csv(counter_file, dtype={"counter_id": "string"}, low_memory=False)
    must = {"counter_id", "latitude", "longitude"}
    missing = must - set(counters.columns)
    if missing:
        raise ValueError(f"counters.csv : colonnes obligatoires absentes : {sorted(missing)}")
    if counters["counter_id"].isna().any() or counters["counter_id"].duplicated().any():
        raise ValueError("counters.csv : counter_id vide ou dupliqué")

    for name in ("counter_name", "site_name", "direction", "site_group_id"):
        if name not in counters:
            counters[name] = ""
    for coord in ("latitude", "longitude"):
        counters[coord] = pd.to_numeric(counters[coord], errors="coerce")
    counters["located"] = counters["latitude"].between(-90, 90) & counters["longitude"].between(-180, 180)
    names = counters["counter_name"].fillna("").astype(str).str.strip()
    names = names.mask(names.eq(""), counters["site_name"].fillna("").astype(str))
    names = names.mask(names.eq(""), "Compteur")
    counters["label"] = names + " | " + counters["direction"].fillna("").astype(str) + " | " + counters["counter_id"].astype(str)

    quality_file = snapshot_dir / "inventory_quality.csv"
    if quality_file.is_file():
        quality = pd.read_csv(quality_file, dtype="string")
        if "counter_id" in quality:
            if "period_role" in quality:
                selection = quality[quality["period_role"].eq("selection")]
                if not selection.empty:
                    quality = selection
            # Deux périodes éventuelles : la décision 'selection' a priorité.
            quality = quality.drop_duplicates("counter_id")
            names = ["selection_status", "status_reason", "site_role", "n_observed"]
            selected = ["counter_id"] + [c for c in names if c in quality]
            counters = counters.merge(quality[selected], on="counter_id", how="left", validate="one_to_one")
    for name in ("selection_status", "status_reason", "site_role", "n_observed"):
        if name not in counters:
            counters[name] = pd.NA
    return counters.sort_values("label").reset_index(drop=True)


def load_counter_history(snapshot_dir: Path, counter_id: str, chunksize: int = 150_000) -> pd.DataFrame:
    """Lit seulement un compteur pour ne pas charger 3 millions de lignes en mémoire."""
    path = snapshot_dir / "counts.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Fichier absent : {path}")
    found: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        path, usecols=COUNT_INPUT_COLUMNS, dtype={"counter_id": "string"}, chunksize=chunksize,
        low_memory=False,
    ):
        selected = chunk.loc[chunk["counter_id"].eq(str(counter_id))].copy()
        if not selected.empty:
            found.append(selected)
    if not found:
        return pd.DataFrame(columns=COUNT_INPUT_COLUMNS)
    rows = pd.concat(found, ignore_index=True)
    for name in ("timestamp", "interval_end"):
        rows[name] = pd.to_datetime(rows[name], utc=True, format="ISO8601", errors="raise")
    for name in ("count_raw", "count"):
        rows[name] = pd.to_numeric(rows[name], errors="coerce")
    for name in ("is_observed", "is_scoreable"):
        rows[name] = bool_series(rows[name])
    if rows["timestamp"].isna().any() or rows["timestamp"].duplicated().any():
        raise ValueError("counts.csv : heure manquante ou doublon pour ce compteur")
    return rows.sort_values("timestamp").reset_index(drop=True)


def load_cases(snapshot_id: str, root: Path = ROOT) -> pd.DataFrame:
    """Cas E4 facultatifs. Ne fabrique pas de cas scientifiques sans protocole."""
    paths = sorted((root / "data" / "evaluation").glob("*/cases.csv"))
    if not paths:
        return pd.DataFrame()
    # Dernier protocole par nom ; le fichier reste révisable par E4.
    cases = pd.read_csv(paths[-1], dtype="string", keep_default_na=False)
    required = {"case_id", "counter_id", "origin", "scenario", "snapshot_id"}
    if required - set(cases.columns):
        raise ValueError(f"cases.csv : colonnes manquantes {sorted(required - set(cases.columns))}")
    cases = cases[cases["snapshot_id"].eq(snapshot_id)].copy()
    if cases["case_id"].duplicated().any():
        raise ValueError("cases.csv : case_id dupliqué")
    return cases


def pilot_case(counter_id: str, day: Any, snapshot_id: str, *, site_group_id: str | None = None):
    """Cas TECHNIQUE provisoire si cases.csv E4 n'est pas encore présent."""
    from src.models.schemas import Case

    origin = pd.Timestamp(day).tz_localize(LOCAL_TZ).tz_convert("UTC")
    return Case(
        case_id=f"v1-{counter_id}-{origin:%Y%m%dT%H%M}",
        counter_id=str(counter_id), site_group_id=site_group_id,
        origin=origin, scenario="known_site", protocol_id="v1-technique-non-valide",
        snapshot_id=snapshot_id, temporal_split="technical",
        spatial_role="S_train",
    )


def make_case(row: pd.Series | dict[str, Any]):
    from src.models.schemas import Case
    return Case.from_row(row)


def predict_known_reference(case: Any, history: pd.DataFrame, variant: str = "reference") -> pd.DataFrame:
    """Appelle réellement E2, sans lui fournir les observations des heures cibles."""
    from src.models.known.predict import default_publication_lag, predict_24h

    if case.scenario != "known_site":
        raise ValueError("E2 ne doit pas prévoir un nouveau site")
    cutoff = case.origin - pd.Timedelta(hours=default_publication_lag())
    past = history.loc[history["interval_end"] <= cutoff].copy()
    # E2 utilise les valeurs publiées (et non les imputations de E1).
    past["count_e1"] = past["count"]
    past["count"] = past["count_raw"].where(past["is_observed"])
    result = predict_24h(case, past, variant=variant)
    return result.to_forecast_frame()


def precomputed_new_forecast(case: Any, root: Path = ROOT) -> pd.DataFrame:
    """Lit une prévision E3 déjà calculée ; n'installe pas Chronos automatiquement."""
    paths = sorted((root / "data" / "prediction_results").glob("*/*.pred.csv"))
    for path in paths:
        matches: list[pd.DataFrame] = []
        for chunk in pd.read_csv(path, dtype={"case_id": "string", "counter_id": "string"}, chunksize=50_000):
            sub = chunk.loc[chunk["case_id"].eq(case.case_id)]
            if not sub.empty:
                matches.append(sub.copy())
        if matches:
            result = pd.concat(matches, ignore_index=True)
            methods = result["method_run_id"].dropna().unique().tolist()
            if len(methods) != 1:
                raise ValueError("E3 : plusieurs méthodes pour un cas, sélection manuelle requise")
            if "snapshot_id" in result and not result["snapshot_id"].astype(str).eq(case.snapshot_id).all():
                raise ValueError("E3 : snapshot différent de celui du cas")
            return result
    raise FileNotFoundError(
        "Aucune prévision E3 enregistrée pour ce cas. "
        "La V1 n'exécute pas Chronos-2 en direct."
    )


def validate_forecast(forecasts: pd.DataFrame, case: Any) -> pd.DataFrame:
    """Vérifie les 24 horizons E2/E3 avant tout affichage et toute évaluation."""
    required = {
        "case_id", "counter_id", "origin", "horizon", "target_timestamp", "y_pred",
        "method_run_id", "prediction_status",
    }
    absent = required - set(forecasts.columns)
    if absent:
        raise ValueError(f"Prévisions : colonnes manquantes {sorted(absent)}")
    f = forecasts.copy()
    if len(f) != 24:
        raise ValueError(f"24 lignes attendues, reçu {len(f)}")
    f["horizon"] = pd.to_numeric(f["horizon"], errors="raise").astype(int)
    if sorted(f["horizon"]) != list(range(1, 25)):
        raise ValueError("Les horizons doivent être uniques de 1 à 24")
    if not f["case_id"].astype(str).eq(case.case_id).all():
        raise ValueError("Prévisions : case_id différent du cas")
    if not f["counter_id"].astype(str).eq(case.counter_id).all():
        raise ValueError("Prévisions : autre compteur détecté")
    if f["method_run_id"].nunique(dropna=False) != 1 or f["method_run_id"].isna().any():
        raise ValueError("Prévisions : plusieurs exécutions ou identifiant de méthode absent")
    for column, expected_value in (
        ("snapshot_id", case.snapshot_id), ("protocol_id", case.protocol_id)
    ):
        if column in f and not f[column].astype(str).eq(expected_value).all():
            raise ValueError(f"Prévisions : {column} différent du cas")
    f["target_timestamp"] = pd.to_datetime(f["target_timestamp"], utc=True, format="ISO8601")
    expected = pd.DatetimeIndex([case.origin + pd.Timedelta(hours=i) for i in range(24)])
    f = f.sort_values("horizon").reset_index(drop=True)
    if not f["target_timestamp"].reset_index(drop=True).equals(pd.Series(expected)):
        raise ValueError("Prévisions : heures différentes de l'origine et des 24 horizons")
    f["y_pred"] = pd.to_numeric(f["y_pred"], errors="coerce")
    bad_values = f["y_pred"].notna() & (~np.isfinite(f["y_pred"]) | (f["y_pred"] < 0))
    if bad_values.any():
        raise ValueError("Prévisions : valeurs non finies ou négatives")
    statuses = f["prediction_status"].astype(str).str.lower()
    if not statuses.isin(["ok", "fallback", "unavailable", "error"]).all():
        raise ValueError("Prévisions : statut inconnu")
    if (statuses.isin(["ok", "fallback"]) & f["y_pred"].isna()).any():
        raise ValueError("Prévisions : statut valide mais y_pred absent")
    return f


def evaluate_local(case: Any, forecasts: pd.DataFrame, history: pd.DataFrame) -> dict[str, Any]:
    """MAE locale *provisoire* ; ne se substitue pas au score officiel E4."""
    f = validate_forecast(forecasts, case)
    obs = history[["counter_id", "timestamp", "count_raw", "is_scoreable"]].copy()
    if obs.duplicated(["counter_id", "timestamp"]).any():
        raise ValueError("Observations : compteur + heure dupliqués")
    aligned = f.merge(
        obs, how="left", left_on=["counter_id", "target_timestamp"],
        right_on=["counter_id", "timestamp"], validate="one_to_one",
    )
    y_true = pd.to_numeric(aligned["count_raw"], errors="coerce")
    y_pred = pd.to_numeric(aligned["y_pred"], errors="coerce")
    status = aligned["prediction_status"].astype(str).str.lower()
    actual_ok = bool_series(aligned["is_scoreable"]).fillna(False)
    valid = actual_ok & y_true.notna() & y_pred.notna() & status.isin(["ok", "fallback"])
    signed = (y_pred - y_true).where(valid)
    absolute = signed.abs()
    square = signed.pow(2)
    errors = pd.DataFrame({
        "case_id": case.case_id,
        "counter_id": case.counter_id,
        "horizon": aligned["horizon"],
        "target_timestamp": aligned["target_timestamp"],
        "method_run_id": aligned["method_run_id"],
        "y_true": y_true,
        "y_pred": y_pred,
        "is_scoreable": valid,
        "signed_error": signed,
        "absolute_error": absolute,
        "squared_error": square,
        "protocol_id": case.protocol_id,
        "snapshot_id": case.snapshot_id,
    })[ERROR_COLUMNS]
    n = int(valid.sum())
    return {
        "mae": float(absolute.mean()) if n else None,
        "n_compared_hours": n,
        "n_forecast_hours": int((y_pred.notna() & status.isin(["ok", "fallback"])).sum()),
        "reason": None if n else "Aucune heure avec prévision et vraie observation exploitables",
        "errors": errors,
    }

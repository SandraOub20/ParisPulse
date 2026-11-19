"""Calcul de 24 heures sur sites connus et traçage des expériences - E2 avec E5.

À faire :
1. Recevoir un cas et ses seules entrées autorisées ; choisir une version admissible du modèle.
2. Produire 24 lignes au format forecasts.csv, sans observations cibles.
3. Sauvegarder <method_run_id>.pred.csv et .runs.csv dans data/prediction_results/<experiment_id>/.
4. Fournir le même calcul à E5 et prouver le recalcul sur une autre origine.

Signature imposée par E5 pour son code : predict_24h(case, history, variant="reference").
Coexistence avec ForecastMethod(inputs, variant) du registre : incohérence C4, en suspens
(voir reports/teams/E2_SUIVI.md, §10).
predict_24h refiltre lui-même l'historique et le contexte sur le passé admissible : un
historique complet du compteur peut donc lui être passé sans risque de fuite.

Valeurs d'entrée (counts_history_loader, MOD-005) : par défaut ``values="measured"``, la
colonne ``count`` vaut la mesure publiée (``count_raw`` si ``is_observed``), sans les
estimations d'E1 (J-7, année précédente) ni le masque rétrospectif ``long_zero_run``. La
valeur livrée par E1 reste disponible dans ``count_e1`` et via ``values="e1_filled"``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path, load_config
from src.models.known import baseline
from src.models.schemas import (
    CASE_RUNS_COLUMNS,
    FORECAST_COLUMNS,
    HORIZON_HOURS,
    Case,
    ForecastInputs,
    ForecastResult,
    RunCost,
    Variant,
    assert_causal,
    target_timestamps,
)

# Variantes servies par predict_24h ; les modèles entraînés s'ajouteront ici.
REFERENCE_VARIANTS: dict[str, Callable[..., ForecastResult]] = {
    "reference": baseline.weekly_reference,
    baseline.PROFILE_VARIANT: baseline.weekly_profile_reference,
}
VALUE_POLICIES = ("measured", "e1_filled")
COUNT_COLUMNS = [
    "counter_id",
    "timestamp",
    "interval_end",
    "count_raw",
    "count",
    "is_observed",
    "is_scoreable",
]


def default_publication_lag() -> int:
    """Latence simulée de config/project*.yaml (protocol.publication_lag_hours)."""
    protocol = load_config().get("protocol") or {}
    return int(protocol.get("publication_lag_hours", 24))


def counts_history_loader(
    snapshot_id: str, values: str = "measured", path: Path | None = None
) -> Callable[[str], pd.DataFrame]:
    """Lire counts.csv une fois et retourner ``counter_id -> historique du compteur``.

    Dates converties une seule fois en UTC. ``values`` fixe la colonne ``count`` utilisée
    en entrée : ``measured`` (mesure publiée uniquement) ou ``e1_filled`` (valeur livrée).
    """
    if values not in VALUE_POLICIES:
        raise ValueError(f"values doit valoir {VALUE_POLICIES}, reçu {values!r}")
    path = Path(path) if path else data_path("processed") / snapshot_id / "counts.csv"
    counts = pd.read_csv(path, usecols=COUNT_COLUMNS, dtype={"counter_id": str})
    for column in ("timestamp", "interval_end"):
        counts[column] = pd.to_datetime(counts[column], utc=True, format="ISO8601")
    counts = counts.rename(columns={"count": "count_e1"})
    if values == "measured":
        counts["count"] = counts["count_raw"].where(counts["is_observed"])
    else:
        counts["count"] = counts["count_e1"]
    by_counter = {cid: frame.reset_index(drop=True) for cid, frame in counts.groupby("counter_id")}

    def load(counter_id: str) -> pd.DataFrame:
        if counter_id not in by_counter:
            raise ValueError(f"compteur {counter_id} absent de {snapshot_id}")
        return by_counter[counter_id]

    load.snapshot_id = snapshot_id  # type: ignore[attr-defined]
    load.values = values  # type: ignore[attr-defined]
    return load


def build_inputs(
    case: Case,
    history: pd.DataFrame,
    context: pd.DataFrame | None = None,
    publication_lag_hours: int | None = None,
) -> ForecastInputs:
    """Restreindre l'historique et le contexte à ce qui est disponible à l'origine.

    information_cutoff = origin - latence ; mesures gardées si interval_end <= coupure ;
    contexte gardé si available_at vide (connu à l'avance) ou <= origin. Sites connus
    seulement : le support local des nouveaux sites relève d'E3.
    """
    if case.scenario != "known_site":
        raise ValueError(f"{case.case_id} : scénario {case.scenario} hors périmètre E2 (E3)")
    lag = default_publication_lag() if publication_lag_hours is None else publication_lag_hours
    cutoff = case.origin - pd.Timedelta(hours=lag)
    hist = baseline.admissible_history(history, cutoff, counter_id=case.counter_id)

    ctx = None
    context_version = None
    if context is not None:
        ctx = context
        if "available_at" in ctx.columns:
            available = pd.to_datetime(ctx["available_at"], utc=True, format="ISO8601")
            ctx = ctx.loc[available.isna() | (available <= case.origin)]
        if "context_version" in ctx.columns and ctx["context_version"].notna().any():
            context_version = str(ctx["context_version"].dropna().iloc[0])
    inputs = ForecastInputs(
        case=case,
        history=hist,
        information_cutoff=cutoff,
        context=ctx,
        context_version=context_version,
    )
    assert_causal(inputs)
    return inputs


def predict_24h(
    case: Case,
    history: pd.DataFrame,
    variant: Variant = "reference",
    *,
    context: pd.DataFrame | None = None,
    model_run_id: str | None = None,
    method_run_id: str | None = None,
    publication_lag_hours: int | None = None,
) -> ForecastResult:
    """Point d'entrée E2 appelé par E5 et par les expériences.

    - reference -> baseline.weekly_reference (weekly_naive) ;
    - reference_profile -> baseline.weekly_profile_reference (médiane sur 4 semaines) ;
    - autre variante -> modèle entraîné (train.load_model), à venir : refus explicite.
    Le temps de préparation (filtrage causal) est compté dans preparation_seconds.
    """
    if variant not in REFERENCE_VARIANTS:
        raise ValueError(
            f"variante {variant!r} indisponible ; disponibles : {sorted(REFERENCE_VARIANTS)}"
        )
    started = time.perf_counter()
    inputs = build_inputs(case, history, context, publication_lag_hours)
    preparation = time.perf_counter() - started
    result = REFERENCE_VARIANTS[variant](inputs, variant, method_run_id=method_run_id)
    result.cost.preparation_seconds = preparation
    return result


def run_experiment(
    cases: pd.DataFrame,
    history_loader: Callable[[str], pd.DataFrame],
    variant: Variant,
    experiment_id: str,
    method_run_id: str,
    *,
    context: pd.DataFrame | None = None,
    root: Path | None = None,
    publication_lag_hours: int | None = None,
) -> tuple[Path, Path]:
    """Prévoir tous les cas puis écrire .pred.csv et .runs.csv ; retourner leurs chemins.

    Un cas qui échoue n'est pas retiré : 24 lignes vides, statut error et message.
    Aucune observation cible n'est écrite dans les sorties.
    """
    results = []
    for _, row in cases.iterrows():
        case = Case.from_row(row)
        try:
            result = predict_24h(
                case,
                history_loader(case.counter_id),
                variant,
                context=context,
                method_run_id=method_run_id,
                publication_lag_hours=publication_lag_hours,
            )
        except Exception as exc:  # noqa: BLE001 - l'échec est tracé, jamais silencieux
            result = error_result(case, method_run_id, variant, exc)
        results.append(result)
    out_dir = Path(root) if root else data_path("predictions") / experiment_id
    pred = write_predictions(results, out_dir / f"{method_run_id}.pred.csv")
    runs = write_runs(results, out_dir / f"{method_run_id}.runs.csv")
    return pred, runs


def error_result(
    case: Case, method_run_id: str, variant: Variant, exc: BaseException
) -> ForecastResult:
    """Résultat explicite d'un calcul échoué : 24 horizons sans prévision, statut error."""
    reason = f"{type(exc).__name__}: {exc}"[:300]
    predictions = target_timestamps(case.origin).assign(
        y_pred=np.nan, method_used=None, prediction_status="error", status_reason=reason
    )
    return ForecastResult(
        case=case,
        method_run_id=method_run_id,
        model_run_id=None,
        variant=variant,
        predictions=predictions,
        status="error",
        status_reason=reason,
        cost=RunCost(),
    )


def write_predictions(results: Iterable[ForecastResult], path: Path) -> Path:
    """Écrire <method_run_id>.pred.csv (colonnes FORECAST_COLUMNS, CSV UTF-8, UTC ISO).

    24 lignes par cas, y compris les horizons sans prévision (y_pred vide et raison).
    Refuse une clé (case_id, method_run_id, horizon) en double ou un cas sans 24 lignes.
    """
    frames = []
    for result in results:
        frame = result.to_forecast_frame()
        if len(frame) != HORIZON_HOURS:
            raise ValueError(f"{result.case.case_id} : {len(frame)} lignes au lieu de 24")
        frames.append(frame)
    if not frames:
        raise ValueError("aucun résultat à écrire")
    table = pd.concat(frames, ignore_index=True)
    key = ["case_id", "method_run_id", "horizon"]
    if table.duplicated(key).any():
        raise ValueError(f"clé {key} en double dans les prévisions")
    return _write_csv(table, FORECAST_COLUMNS, path)


def write_runs(results: Iterable[ForecastResult], path: Path) -> Path:
    """Écrire <method_run_id>.runs.csv (une ligne par cas, colonnes CASE_RUNS_COLUMNS)."""
    rows = [result.to_run_row() for result in results]
    if not rows:
        raise ValueError("aucun résultat à écrire")
    table = pd.DataFrame(rows, columns=CASE_RUNS_COLUMNS)
    if table.duplicated(["case_id", "method_run_id"]).any():
        raise ValueError("cas en double dans le fichier de coût")
    return _write_csv(table, CASE_RUNS_COLUMNS, path)


def _write_csv(table: pd.DataFrame, columns: list[str], path: Path) -> Path:
    """Appliquer les conventions CONTRATS §1 : UTC ISO avec fuseau, true/false, vide = absent."""
    out = table[columns].astype(object)
    for column in out.columns:
        out[column] = out[column].map(_format_cell)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8")
    return path


def _format_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool | np.bool_):
        return "true" if value else "false"
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            raise ValueError(f"date sans fuseau à l'export : {value}")
        return value.tz_convert("UTC").isoformat()
    if isinstance(value, float | np.floating) and not np.isfinite(value):
        return ""
    if value is pd.NaT or value is pd.NA:
        return ""
    return value


def train_site_counters(snapshot_id: str) -> set[str]:
    """Compteurs que l'inventaire E1 classe S_train (sites connus), période de sélection."""
    inventory = pd.read_csv(
        data_path("processed") / snapshot_id / "inventory_quality.csv", dtype=str
    )
    if "period_role" in inventory.columns:
        inventory = inventory.loc[inventory["period_role"] == "selection"]
    return set(inventory.loc[inventory["site_role"] == "S_train", "counter_id"])


def select_cases(
    cases: pd.DataFrame,
    snapshot_id: str,
    splits: Iterable[str],
    allowed_counters: set[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Garder les cas sites connus des blocs demandés sur des compteurs S_train.

    Retourne aussi le décompte des cas écartés par motif (jamais d'exclusion silencieuse).
    ``snapshot_id`` des cas est remplacé par l'instantané réellement lu, compté s'il diffère.
    """
    splits = set(splits)
    report: dict[str, int] = {"input": len(cases)}
    keep = cases["scenario"] == "known_site"
    report["not_known_site"] = int((~keep).sum())
    in_split = cases["temporal_split"].isin(splits)
    report["other_split"] = int((keep & ~in_split).sum())
    keep &= in_split
    on_train = cases["counter_id"].isin(allowed_counters)
    report["counter_not_S_train"] = int((keep & ~on_train).sum())
    keep &= on_train
    selected = cases.loc[keep].copy()
    report["snapshot_replaced"] = int((selected["snapshot_id"] != snapshot_id).sum())
    selected["snapshot_id"] = snapshot_id
    report["selected"] = len(selected)
    return selected, report


def main(argv: list[str] | None = None) -> int:
    """Calculer une référence E2 sur un cases.csv et écrire .pred.csv / .runs.csv.

    Exemple : python -m src.models.known.predict --cases data/evaluation/proto-v0/cases.csv
    --snapshot hist-20261117 --experiment E2-TECH-001 --variant reference
    Le bloc test est refusé sauf --allow-test (à n'utiliser qu'après gel des choix).
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(description=main.__doc__.splitlines()[0])
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--variant", default="reference", choices=sorted(REFERENCE_VARIANTS))
    parser.add_argument("--method-run-id")
    parser.add_argument("--values", default="measured", choices=VALUE_POLICIES)
    parser.add_argument("--split", action="append", default=None, help="défaut : validation")
    parser.add_argument("--allow-test", action="store_true")
    args = parser.parse_args(argv)

    splits = args.split or ["validation"]
    if "test" in splits and not args.allow_test:
        parser.error("bloc test refusé : réservé à la mesure finale après gel (--allow-test)")
    cases = pd.read_csv(args.cases, dtype=str, keep_default_na=False)
    selected, report = select_cases(
        cases, args.snapshot, splits, train_site_counters(args.snapshot)
    )
    method_run_id = args.method_run_id or f"e2-{args.variant}-{args.values}"
    started = time.perf_counter()
    loader = counts_history_loader(args.snapshot, values=args.values)
    loading = time.perf_counter() - started
    pred, runs = run_experiment(selected, loader, args.variant, args.experiment, method_run_id)
    selected.to_csv(pred.parent / f"{method_run_id}.cases_used.csv", index=False)
    report.update(
        {
            "values": args.values,
            "load_seconds": round(loading, 1),
            "total_seconds": round(time.perf_counter() - started, 1),
        }
    )
    (pred.parent / f"{method_run_id}.selection.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({"pred": str(pred), "runs": str(runs), **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Calcul de 24 heures sur sites connus et traçage des expériences - E2 avec E5.

- ``predict_24h(case, history, variant=...)`` (signature demandée par E5) : un cas, ses seules
  entrées admissibles, 24 lignes au format forecasts.csv, sans observation cible.
- Variantes : ``reference`` et ``reference_profile`` (baseline.py), ``mlp`` (neural.py) et
  ``hgb`` (tabular.py, retenu pour l'application, D-24). Modèle par défaut : DEFAULT_MODEL_RUN_IDS.
- ``trained_forecast`` contrôle l'éligibilité (``eligibility_reason``) puis bascule sur la
  référence en cas de refus ; ``status_reason`` garde le code exact.
- ``run_experiment`` / ``main`` écrivent <method_run_id>.pred.csv, .runs.csv,
  .cases_used.csv et .selection.json dans data/prediction_results/<experiment_id>/ ;
  ``--batch`` fait le même calcul en bloc (batch.py), avec des fichiers identiques.
- registry.py (C4) n'est pas utilisé : E3 et E5 appellent predict_24h directement.

predict_24h refiltre lui-même l'historique et le contexte sur le passé admissible : un
historique complet du compteur peut donc lui être passé sans risque de fuite.

Valeurs d'entrée (counts_history_loader, MOD-005) : par défaut ``values="measured"``, la
colonne ``count`` vaut la mesure publiée (``count_raw`` si ``is_observed``), sans les
estimations d'E1 (J-7, année précédente) ni le masque rétrospectif ``long_zero_run``. La
valeur livrée par E1 reste disponible dans ``count_e1`` et via ``values="e1_filled"``.
"""

from __future__ import annotations

import importlib
import json
import platform
import time
from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path, load_config
from src.models.known import baseline, train
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

REFERENCE_VARIANTS: dict[str, Callable[..., ForecastResult]] = {
    "reference": baseline.weekly_reference,
    baseline.PROFILE_VARIANT: baseline.weekly_profile_reference,
}
MLP_VARIANT = "mlp"
HGB_VARIANT = "hgb"
# Variantes servies par un modèle entraîné : variante -> module qui déclare sa méthode
# (register_backend). Importé seulement à la demande : torch n'est chargé que pour "mlp".
TRAINED_VARIANTS: dict[str, str] = {
    MLP_VARIANT: "src.models.known.neural",
    HGB_VARIANT: "src.models.known.tabular",
}
SUPPORTED_VARIANTS = (*REFERENCE_VARIANTS, *TRAINED_VARIANTS)  # lu par l'application (E5)
# Modèle servi quand model_run_id n'est pas donné : versions déclarées dans EXP-E2-03,
# provisoires jusqu'au choix de cette fiche.
DEFAULT_MODEL_RUN_IDS: dict[str, str] = {
    MLP_VARIANT: "e2-mlp-ctx-20260701-s0-9ce9",
    HGB_VARIANT: "e2-hgb-ctx-20260701-s0-b357",
}
_MODEL_CACHE: dict[tuple[str, str], train.TrainedModel] = {}
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


def load_trained(model_run_id: str, variant: str, root: Path | None = None) -> train.TrainedModel:
    """Charger une seule fois le modèle entraîné d'une variante (mlp, hgb).

    1. La méthode écrite dans metadata.json doit être celle de la variante : lue avant
       tout import, pour qu'un identifiant de MLP demandé en "hgb" n'importe pas torch.
    2. Le module de la méthode est importé (il déclare son backend), puis
       train.load_model vérifie poids (SHA-256) et fiche.
    3. Le modèle est gardé en mémoire : un seul chargement par dossier et identifiant.
    """
    if variant not in TRAINED_VARIANTS:
        raise ValueError(
            f"variante {variant!r} sans modèle entraîné ; disponibles : {sorted(TRAINED_VARIANTS)}"
        )
    root = Path(root) if root else data_path("models")
    key = (str(root.resolve()), model_run_id)
    if key in _MODEL_CACHE:
        method = _MODEL_CACHE[key].config.method
    else:
        metadata_path = root / model_run_id / train.METADATA_FILE
        if not metadata_path.exists():
            raise FileNotFoundError(f"modèle {model_run_id} introuvable : {metadata_path}")
        method = json.loads(metadata_path.read_text(encoding="utf-8")).get("model_name")
    if method != variant:
        raise ValueError(f"{model_run_id} est un modèle {method!r}, pas {variant!r}")
    if key not in _MODEL_CACHE:
        importlib.import_module(TRAINED_VARIANTS[variant])
        _MODEL_CACHE[key] = train.load_model(model_run_id, root)
    return _MODEL_CACHE[key]


def _load_model(variant: str, model_run_id: str | None) -> train.TrainedModel:
    """Modèle d'une variante entraînée : model_run_id donné, sinon celui par défaut."""
    run_id = model_run_id or DEFAULT_MODEL_RUN_IDS.get(variant)
    if run_id is None:
        raise ValueError(f"variante {variant!r} : model_run_id obligatoire")
    return load_trained(run_id, variant)


def eligibility_reason(inputs: ForecastInputs, model, method: str) -> str | None:
    """Code de refus avant tout calcul (None si le modèle peut servir ce cas).

    Contrôles proposés par E5 (Sandra), réécrits ici pour toutes les méthodes entraînées :
    instantané du modèle ; origine avant la coupure ; site connu absent de l'apprentissage ;
    nouveau site qui n'est pas confirmé réservé ; version du contexte différente.
    """
    case = inputs.case
    config = model.config
    if config.snapshot_id and config.snapshot_id != case.snapshot_id:
        return f"{method}_snapshot_incompatible"
    if case.origin < config.fit_cutoff:
        return f"{method}_origin_before_fit_cutoff"
    if case.scenario == "known_site" and case.site_group_id not in model.donor_site_groups:
        return f"{method}_site_not_in_training"
    if case.scenario == "new_site" and (
        case.site_group_id in model.donor_site_groups
        or case.site_group_id not in getattr(model, "excluded_site_groups", [])
    ):
        return f"{method}_site_not_confirmed_reserved"
    if config.use_context and config.context_version != inputs.context_version:
        if inputs.context_version is None:
            return f"{method}_context_missing"
        return f"{method}_context_incompatible"
    return None


def trained_forecast(
    inputs: ForecastInputs,
    method: str,
    model: train.TrainedModel,
    *,
    variant: str | None = None,
    method_run_id: str | None = None,
    min_observed_hours: int | None = None,
) -> ForecastResult:
    """Prévoir un cas avec un modèle entraîné (mlp, hgb), ou se replier sur la référence.

    - eligibility_reason, puis le modèle lui-même, peuvent refuser (code mlp_* / hgb_*) ;
    - le modèle prévoit : 24 valeurs finies >= 0, method_used = méthode, statut ok ;
    - il refuse : la référence de sa fiche (model.fallback, "reference" par défaut) prévoit
      les 24 horizons ; statut fallback, status_reason = code de refus (cas et horizons),
      method_used = méthode réellement employée. Un horizon sans repli reste vide
      (unavailable), jamais 0.
    variant : étiquette écrite dans le résultat (par défaut la méthode ; E3 passe "frozen").
    min_observed_hours : MLP seulement, remplace le seuil appris (bras A′ d'EXP-E2-05).
    model_run_id et fit_cutoff du modèle sont tracés dans les deux cas.
    """
    started = time.perf_counter()
    reason = eligibility_reason(inputs, model, method)
    values = None
    if reason is None:
        try:
            raw = _raw_forecast(method, model, inputs, min_observed_hours=min_observed_hours)
            values, reason = raw.values, raw.reason
        except ValueError as error:
            reason = f"{method}_inputs_incompatible: {error}"
    result = _assemble_result(
        inputs, method, model, values, reason, variant=variant, method_run_id=method_run_id
    )
    result.cost.inference_seconds = time.perf_counter() - started
    return result


def _assemble_result(
    inputs: ForecastInputs,
    method: str,
    model: train.TrainedModel,
    values,
    reason: str | None,
    *,
    variant: str | None = None,
    method_run_id: str | None = None,
) -> ForecastResult:
    """Résultat d'un cas à partir de la sortie brute du modèle (values ou reason).

    Seul endroit qui écrit statuts, repli et provenance : le calcul cas par cas
    (trained_forecast) et le calcul en bloc l'utilisent tous les deux, et leurs fichiers
    sont donc identiques, au coût près.
    - values (24 valeurs) : statut ok, method_used = méthode ;
    - sinon : repli sur la référence de la fiche du modèle, status_reason = reason.
    """
    variant = variant or method
    if values is not None:
        values = np.asarray(values, dtype=float)
        if values.shape != (HORIZON_HOURS,) or not (np.isfinite(values) & (values >= 0)).all():
            raise ValueError(f"{method} : 24 valeurs finies et positives ou nulles attendues")
        predictions = target_timestamps(inputs.case.origin).assign(
            y_pred=values, method_used=method, prediction_status="ok", status_reason=None
        )
        status, reason = "ok", None
    else:
        if not reason:
            raise ValueError(f"{method} : prévision refusée sans raison")
        fallback_name = getattr(model, "fallback", "reference")
        if fallback_name not in REFERENCE_VARIANTS:
            raise ValueError(f"{model.model_run_id} : repli {fallback_name!r} inconnu")
        ref = REFERENCE_VARIANTS[fallback_name](inputs, variant)
        predictions = ref.predictions.copy()
        served = predictions["y_pred"].notna()
        predictions["prediction_status"] = np.where(served, "fallback", "unavailable")
        predictions["status_reason"] = reason
        status = "fallback" if served.all() else "unavailable"
    return ForecastResult(
        case=inputs.case,
        method_run_id=method_run_id or model.model_run_id,
        model_run_id=model.model_run_id,
        variant=variant,
        predictions=predictions,
        status=status,
        status_reason=reason,
        fit_cutoff=model.config.fit_cutoff,
        support_id=inputs.support_id,
        context_version=inputs.context_version,
        feature_version=model.config.feature_version,
        cost=RunCost(hardware=f"{platform.system()}-{platform.machine()}"),
    )


def _raw_forecast(
    method: str,
    model: train.TrainedModel,
    inputs: ForecastInputs,
    *,
    min_observed_hours: int | None = None,
):
    """Sortie brute du modèle : objet avec values (24,) ou None, et reason (code de refus).

    Module importé à la demande : torch n'est chargé que pour le MLP. Le seuil d'heures
    mesurées ne concerne que le MLP (le HGB n'en a pas).
    """
    if method == MLP_VARIANT:
        neural = importlib.import_module(TRAINED_VARIANTS[MLP_VARIANT])
        return neural.predict_mlp(
            model.estimator,
            inputs,
            fit_cutoff=model.config.fit_cutoff,
            min_observed_hours=min_observed_hours,
        )
    if min_observed_hours is not None:
        raise ValueError(f"min_observed_hours ne s'applique qu'au MLP, pas à {method!r}")
    if method == HGB_VARIANT:
        tabular = importlib.import_module(TRAINED_VARIANTS[HGB_VARIANT])
        return tabular.predict_hgb(model.estimator, inputs)
    raise ValueError(f"méthode {method!r} sans prévision entraînée")


def load_context(snapshot_id: str, path: Path | None = None) -> pd.DataFrame:
    """Lire context.csv d'E1 en texte, comme train.load_training_data (même lecture).

    Texte partout : la colonne value mêle nombres et booléens ; features la convertit.
    build_inputs ne garde ensuite que le contexte connu à l'origine de chaque cas.
    """
    path = Path(path) if path else data_path("processed") / snapshot_id / "context.csv"
    if not path.exists():
        raise FileNotFoundError(f"context.csv introuvable : {path}")
    return pd.read_csv(path, dtype=str)


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
    min_observed_hours: int | None = None,
) -> ForecastResult:
    """Point d'entrée E2 appelé par E5 et par les expériences.

    - reference -> baseline.weekly_reference (weekly_naive) ;
    - reference_profile -> baseline.weekly_profile_reference (médiane sur 4 semaines) ;
    - mlp, hgb -> modèle entraîné (model_run_id, sinon DEFAULT_MODEL_RUN_IDS), chargé
      une fois, repli sur la référence s'il refuse le cas (trained_forecast).
      Le MLP et le HGB avec contexte en ont besoin : sans context, ils se replient.
    min_observed_hours : MLP seulement, seuil d'heures mesurées à la place de celui appris.
    Le temps de préparation (filtrage causal) est compté dans preparation_seconds ; le
    chargement du modèle, fait une seule fois par expérience, n'y est pas compté.
    """
    if min_observed_hours is not None and variant not in TRAINED_VARIANTS:
        raise ValueError(f"min_observed_hours sans objet pour la variante {variant!r}")
    if variant not in REFERENCE_VARIANTS and variant not in TRAINED_VARIANTS:
        available = sorted(REFERENCE_VARIANTS) + sorted(TRAINED_VARIANTS)
        raise ValueError(f"variante {variant!r} indisponible ; disponibles : {available}")
    model = None
    if variant in TRAINED_VARIANTS:
        model = _load_model(variant, model_run_id)
    started = time.perf_counter()
    inputs = build_inputs(case, history, context, publication_lag_hours)
    preparation = time.perf_counter() - started
    if model is None:
        result = REFERENCE_VARIANTS[variant](inputs, variant, method_run_id=method_run_id)
    else:
        result = trained_forecast(
            inputs,
            variant,
            model,
            method_run_id=method_run_id,
            min_observed_hours=min_observed_hours,
        )
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
    model_run_id: str | None = None,
    min_observed_hours: int | None = None,
) -> tuple[Path, Path]:
    """Prévoir tous les cas puis écrire .pred.csv et .runs.csv ; retourner leurs chemins.

    Un cas qui échoue n'est pas retiré : 24 lignes vides, statut error et message.
    Aucune observation cible n'est écrite dans les sorties. model_run_id : modèle des
    variantes mlp et hgb (défaut : DEFAULT_MODEL_RUN_IDS), chargé une fois pour tous les cas.
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
                model_run_id=model_run_id,
                method_run_id=method_run_id,
                publication_lag_hours=publication_lag_hours,
                min_observed_hours=min_observed_hours,
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
        # Colonnes en objet : _write_csv formate tout en texte, et un cas en erreur
        # (y_pred entièrement vide) ne change alors pas le type des autres.
        frames.append(frame.astype(object))
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
    """Calculer une référence ou un modèle E2 sur un cases.csv ; écrire .pred.csv / .runs.csv.

    Exemples : python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv
    --snapshot hist-20261117 --experiment E2-TECH-001 --variant reference
    ... --variant hgb --model-run-id e2-hgb-ctx-20260701-s0-b357 (contexte E1 chargé).
    Le bloc test est refusé sauf --allow-test (à n'utiliser qu'après gel des choix).
    """
    import argparse

    parser = argparse.ArgumentParser(description=main.__doc__.splitlines()[0])
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--variant", default="reference", choices=sorted(SUPPORTED_VARIANTS))
    parser.add_argument("--model-run-id", help=f"mlp et hgb ; défaut : {DEFAULT_MODEL_RUN_IDS}")
    parser.add_argument(
        "--context", type=Path, help="défaut pour les modèles : context.csv de l'instantané"
    )
    parser.add_argument(
        "--min-observed-hours", type=int, help="MLP seulement : seuil à la place de celui appris"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="mlp et hgb : sortie du modèle en bloc (batch.py), mêmes fichiers en quelques s",
    )
    parser.add_argument(
        "--degrade",
        help="EXP-E2-05, avec --batch : niveau d'effacement de la semaine visible "
        "(d0, panne-48, panne-96, panne-144, trous-50) ; suffixe le method_run_id",
    )
    parser.add_argument("--method-run-id")
    parser.add_argument("--values", default="measured", choices=VALUE_POLICIES)
    parser.add_argument("--split", action="append", default=None, help="défaut : validation")
    parser.add_argument("--allow-test", action="store_true")
    args = parser.parse_args(argv)

    splits = args.split or ["validation"]
    if "test" in splits and not args.allow_test:
        parser.error("bloc test refusé : réservé à la mesure finale après gel (--allow-test)")
    trained = args.variant in TRAINED_VARIANTS
    if trained and args.values != "measured":
        parser.error("les modèles ont appris sur les mesures seules (D-11) : --values measured")
    if args.min_observed_hours is not None and args.variant != MLP_VARIANT:
        parser.error("--min-observed-hours ne s'applique qu'au MLP")
    if args.degrade is not None and not args.batch:
        parser.error("--degrade passe par le calcul en bloc : ajouter --batch")
    if not trained and args.model_run_id:
        parser.error(f"--model-run-id sans objet pour la variante {args.variant}")
    if trained:
        model = _load_model(args.variant, args.model_run_id)  # échoue tôt, avant counts.csv
        args.model_run_id = model.model_run_id
    cases = pd.read_csv(args.cases, dtype=str, keep_default_na=False)
    selected, report = select_cases(
        cases, args.snapshot, splits, train_site_counters(args.snapshot)
    )
    method_run_id = args.method_run_id or (
        args.model_run_id if trained else f"e2-{args.variant}-{args.values}"
    )
    if args.degrade is not None:
        method_run_id = f"{method_run_id}_{args.degrade}"
    started = time.perf_counter()
    loader = counts_history_loader(args.snapshot, values=args.values)
    context = load_context(args.snapshot, path=args.context) if trained else None
    loading = time.perf_counter() - started
    runner = run_experiment
    extra = {}
    if args.batch:
        from src.models.known import batch  # import tardif : batch importe ce module

        runner = batch.run_experiment_batch
        if args.degrade is not None:
            extra["degrade"] = args.degrade
    pred, runs = runner(
        selected,
        loader,
        args.variant,
        args.experiment,
        method_run_id,
        context=context,
        model_run_id=args.model_run_id,
        min_observed_hours=args.min_observed_hours,
        **extra,
    )
    selected.to_csv(pred.parent / f"{method_run_id}.cases_used.csv", index=False)
    report.update(
        {
            "values": args.values,
            "model_run_id": args.model_run_id,
            "min_observed_hours": args.min_observed_hours,
            "mode": "batch" if args.batch and trained else "cas par cas",
            "degrade": args.degrade,
            "context_rows": None if context is None else len(context),
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

"""Calcul en bloc des prévisions E2 pour une expérience (beaucoup de cas d'un coup).

Même résultat que le calcul cas par cas de predict.py (predict_24h, run_experiment), en
quelques secondes au lieu d'environ 0,5 s par cas :
- la sortie brute des modèles est calculée pour tous les cas à la fois, avec les chemins
  en bloc déjà testés (neural.build_windows / predict_windows, tabular.predict_frame) ;
- chaque cas passe ensuite par predict._assemble_result, le même code que le cas par cas
  pour les statuts, le repli et la provenance.
Seul le coût diffère : en bloc, le temps est réparti entre les cas, ce qui n'est pas le
coût d'un calcul isolé dans l'application (environ 0,4 s par cas).

Réservé aux expériences ; l'application (E5) et E3 continuent d'appeler predict_24h.
"""

from __future__ import annotations

import dataclasses
import importlib
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.known import predict as P
from src.models.known import train
from src.models.schemas import HORIZON_HOURS, Case

LOCAL_TZ = "Europe/Paris"


def batch_raw_mlp(
    cases: list[Case],
    counts: pd.DataFrame,
    context: pd.DataFrame | None,
    model: train.TrainedModel,
    *,
    min_observed_hours: int | None = None,
    publication_lag_hours: int | None = None,
) -> tuple[np.ndarray, list[str | None]]:
    """Sortie brute du MLP pour tous les cas : valeurs (n, 24) et code de refus par cas.

    Mêmes contrôles, dans le même ordre, que neural.predict_mlp pour un cas :
    1. origine hors minuit (Paris) ; 2. origine avant la coupure du modèle (fiche et bilan) ;
    3. aucune ligne publiée pour le compteur avant origin - latence ; 4. contexte absent
    alors que le modèle l'utilise ; 5. refus de la fenêtre (refusal_reasons : trop vide,
    niveau trop bas, contexte inconnu à l'origine) ; 6. sortie non finie.
    Une ligne refusée a des valeurs NaN et un code ; une ligne servie a reason None.

    counts : historique de tous les compteurs (counter_id, timestamp, interval_end, count),
    count = mesures publiées seulement (D-11). Seules les heures finies avant
    origin - latence sont lues (fenêtre de build_windows) : aucune cible n'est lue.
    context : context.csv entier ; la disponibilité est appliquée origine par origine.
    Lève ValueError si la latence diffère de celle du réseau (erreur de configuration).
    """
    neural = importlib.import_module(P.TRAINED_VARIANTS[P.MLP_VARIANT])
    net = model.estimator
    lag = P.default_publication_lag() if publication_lag_hours is None else publication_lag_hours
    if int(lag) != neural._lag_of(net):
        raise ValueError(
            f"latence {lag} h différente de celle de l'apprentissage ({neural._lag_of(net)} h)"
        )
    n = len(cases)
    values = np.full((n, HORIZON_HOURS), np.nan)
    reasons: list[str | None] = [None] * n
    if n == 0:
        return values, reasons

    origins = pd.DatetimeIndex([pd.Timestamp(c.origin).tz_convert("UTC") for c in cases])
    counter_ids = np.array([str(c.counter_id) for c in cases])

    # 1. et 2. : origine à minuit, après la coupure (la plus tardive de la fiche et du bilan)
    local = origins.tz_convert(LOCAL_TZ)
    not_midnight = np.asarray(local != local.normalize())
    learned = (getattr(net, "training_report", None) or {}).get("fit_cutoff")
    cutoffs = [pd.Timestamp(model.config.fit_cutoff)]
    if learned is not None:
        cutoffs.append(pd.Timestamp(learned))
    cutoff = max(t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC") for t in cutoffs)
    before_cutoff = np.asarray(origins < cutoff)

    # 3. aucune ligne publiée avant origin - latence (compteur pas encore installé)
    ends = pd.to_datetime(counts["interval_end"], utc=True)
    first_end = ends.groupby(counts["counter_id"].astype(str)).min()
    first = pd.DatetimeIndex(first_end.reindex(counter_ids).to_numpy()).tz_localize(None)
    information = (origins - pd.Timedelta(hours=int(lag))).tz_localize(None)
    no_history = np.asarray(first.isna() | (first > information))

    # 4. contexte absent pour un modèle qui l'utilise
    use_context = bool(neural._layout_of(net)["use_context"])
    context_absent = use_context and (context is None or len(context) == 0)

    for i in range(n):
        if not_midnight[i]:
            reasons[i] = neural.REFUSE_NOT_MIDNIGHT
        elif before_cutoff[i]:
            reasons[i] = neural.REFUSE_BEFORE_CUTOFF
        elif no_history[i]:
            reasons[i] = neural.REFUSE_NO_HISTORY
        elif context_absent:
            reasons[i] = neural.REFUSE_CONTEXT
    todo = np.flatnonzero([r is None for r in reasons])
    if todo.size == 0:
        return values, reasons

    # 5. et 6. : fenêtres de tous les cas restants, en une fois
    wanted = set(counter_ids[todo])
    sub = counts.loc[counts["counter_id"].astype(str).isin(wanted)]
    frame = pd.DataFrame(
        {
            "counter_id": sub["counter_id"].astype(str).to_numpy(),
            "timestamp": pd.to_datetime(sub["timestamp"], utc=True).to_numpy(),
            "count": pd.to_numeric(sub["count"], errors="coerce").to_numpy(dtype=float),
        }
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["count_raw"] = np.nan  # cibles inconnues à l'origine : jamais lues ici
    frame["is_scoreable"] = False
    threshold = (
        neural._min_observed_of(net) if min_observed_hours is None else int(min_observed_hours)
    )
    windows = neural.build_windows(
        frame,
        pd.DataFrame({"counter_id": counter_ids[todo], "origin": origins[todo]}),
        context if use_context else None,
        use_context=use_context,
        publication_lag_hours=int(lag),
        min_observed_hours=threshold,
    )
    window_reasons = neural.refusal_reasons(windows)
    predicted = neural.predict_windows(net, windows)
    for row, i in enumerate(todo):
        if window_reasons[row] is not None:
            reasons[i] = window_reasons[row]
        elif not np.isfinite(predicted[row]).all():
            reasons[i] = neural.REFUSE_NON_FINITE
        else:
            values[i] = predicted[row]
    return values, reasons


def batch_raw_hgb(
    cases: list[Case],
    counts: pd.DataFrame,
    context: pd.DataFrame | None,
    model: train.TrainedModel,
    *,
    publication_lag_hours: int | None = None,
) -> tuple[np.ndarray, list[str | None]]:
    """Sortie brute du HGB pour tous les cas : valeurs (n, 24) et code de refus par cas.

    Mêmes contrôles, dans le même ordre, que tabular.refusal_reason puis predict_hgb :
    1. origine hors minuit (Paris) ; 2. origine avant fit_cutoff du modèle ; 3. aucune
    mesure publiée avant origin - latence (le HGB tolère une semaine trouée, mais pas un
    historique vide) ; 4. contexte absent alors que le modèle l'utilise ; 5. toutes les
    valeurs de contexte du cas inconnues à l'origine ; 6. sortie non finie.
    Variables : features._assemble, le calcul commun à build_feature_frame (cas par cas)
    et build_training_frame, appelé sans étiquette : les 24 heures de chaque cas sont
    gardées et aucune cible n'est lue.
    Lève ValueError si la latence diffère de celle du modèle (erreur de configuration).
    """
    from src.models.known import features as F

    tabular = importlib.import_module(P.TRAINED_VARIANTS[P.HGB_VARIANT])
    hgb = model.estimator
    lag = P.default_publication_lag() if publication_lag_hours is None else publication_lag_hours
    if int(lag) != int(hgb.publication_lag_hours):
        raise ValueError(
            f"latence {lag} h différente de celle de l'apprentissage "
            f"({hgb.publication_lag_hours} h)"
        )
    n = len(cases)
    values = np.full((n, HORIZON_HOURS), np.nan)
    reasons: list[str | None] = [None] * n
    if n == 0:
        return values, reasons

    origins = pd.DatetimeIndex([pd.Timestamp(c.origin).tz_convert("UTC") for c in cases])
    counter_ids = np.array([str(c.counter_id) for c in cases])
    local = origins.tz_convert(LOCAL_TZ)
    not_midnight = np.asarray(local != local.normalize())
    fit_cutoff = pd.Timestamp(hgb.fit_cutoff)
    fit_cutoff = (
        fit_cutoff.tz_convert("UTC") if fit_cutoff.tzinfo else fit_cutoff.tz_localize("UTC")
    )
    before_cutoff = np.asarray(origins < fit_cutoff)

    measured = pd.to_numeric(counts["count"], errors="coerce").notna()
    ends = pd.to_datetime(counts.loc[measured, "interval_end"], utc=True)
    first_end = ends.groupby(counts.loc[measured, "counter_id"].astype(str)).min()
    first = pd.DatetimeIndex(first_end.reindex(counter_ids).to_numpy()).tz_localize(None)
    information = (origins - pd.Timedelta(hours=int(lag))).tz_localize(None)
    no_history = np.asarray(first.isna() | (first > information))
    context_absent = hgb.use_context and (context is None or len(context) == 0)

    for i in range(n):
        if not_midnight[i]:
            reasons[i] = tabular.REFUSE_NOT_MIDNIGHT
        elif before_cutoff[i]:
            reasons[i] = tabular.REFUSE_BEFORE_CUTOFF
        elif no_history[i]:
            reasons[i] = tabular.REFUSE_NO_HISTORY
        elif context_absent:
            reasons[i] = tabular.REFUSE_CONTEXT
    todo = np.flatnonzero([r is None for r in reasons])
    if todo.size == 0:
        return values, reasons

    groups = tuple(hgb.context_groups)
    prepared = F._prepare_context(context, groups) if groups else {}
    context_columns = [c for g in groups for c in F.CONTEXT_GROUPS[g]]
    by_counter = {str(k): v for k, v in counts.groupby(counts["counter_id"].astype(str))}
    steps = np.arange(HORIZON_HOURS, dtype=np.int64)
    for counter_id in sorted(set(counter_ids[todo])):
        idx = todo[counter_ids[todo] == counter_id]
        rows = by_counter[counter_id]
        grid = F._make_grid(
            F._to_hours(rows["timestamp"], "timestamp"),
            pd.to_numeric(rows["count"], errors="coerce").to_numpy(dtype=float),
        )
        origin_h = F._to_hours(pd.Series(origins[idx]), "origin")
        X = F._assemble(
            grid,
            prepared,
            groups,
            np.repeat(origin_h, HORIZON_HOURS),
            np.repeat(origin_h, HORIZON_HOURS) + np.tile(steps, idx.size),
            int(lag),
            case_ids=np.repeat(np.array([cases[i].case_id for i in idx], dtype=object), 24),
            counter_id=counter_id,
        )
        predicted = tabular.predict_frame(hgb, X).reshape(idx.size, HORIZON_HOURS)
        if context_columns:
            unknown = X[context_columns].isna().to_numpy().reshape(idx.size, -1).all(axis=1)
        else:
            unknown = np.zeros(idx.size, dtype=bool)
        for row, i in enumerate(idx):
            if unknown[row]:
                reasons[i] = tabular.REFUSE_CONTEXT
            elif not np.isfinite(predicted[row]).all():
                reasons[i] = tabular.REFUSE_NON_FINITE
            else:
                values[i] = predicted[row]
    return values, reasons


RAW_BATCH: dict[str, Callable[..., tuple[np.ndarray, list[str | None]]]] = {
    P.MLP_VARIANT: batch_raw_mlp,
    P.HGB_VARIANT: batch_raw_hgb,
}


def run_experiment_batch(
    cases: pd.DataFrame,
    history_loader: Callable[[str], pd.DataFrame],
    variant: str,
    experiment_id: str,
    method_run_id: str,
    *,
    context: pd.DataFrame | None = None,
    root: Path | None = None,
    publication_lag_hours: int | None = None,
    model_run_id: str | None = None,
    min_observed_hours: int | None = None,
) -> tuple[Path, Path]:
    """Comme predict.run_experiment, mais la sortie brute du modèle est calculée en bloc.

    Mêmes paramètres et mêmes fichiers (.pred.csv, .runs.csv) que run_experiment ; seul le
    coût diffère. Par cas : build_inputs (sans contexte : seul l'historique sert au repli),
    eligibility_reason, puis la sortie brute en bloc (RAW_BATCH), et _assemble_result, le
    même code que le cas par cas. Un cas qui échoue (compteur absent...) reste dans les
    fichiers, en statut error. Les références (sans modèle) passent par run_experiment.
    Coût écrit par cas : preparation_seconds = son filtrage causal, inference_seconds = la
    part du calcul en bloc (temps total / nombre de cas).
    """
    if variant not in RAW_BATCH:
        return P.run_experiment(
            cases,
            history_loader,
            variant,
            experiment_id,
            method_run_id,
            context=context,
            root=root,
            publication_lag_hours=publication_lag_hours,
            model_run_id=model_run_id,
            min_observed_hours=min_observed_hours,
        )
    if min_observed_hours is not None and variant != P.MLP_VARIANT:
        raise ValueError(f"min_observed_hours sans objet pour la variante {variant!r}")
    model = P._load_model(variant, model_run_id)
    lag = P.default_publication_lag() if publication_lag_hours is None else publication_lag_hours
    context_version = None
    if context is not None and "context_version" in context.columns:
        versions = context["context_version"].dropna()
        context_version = str(versions.iloc[0]) if len(versions) else None

    # 1. Par cas : mêmes contrôles que build_inputs (les échecs sont gardés), puis une version
    #    légère des entrées, sans historique : garder 6 014 copies du passé de chaque
    #    compteur saturait la mémoire. Le passé n'est reconstruit qu'au repli (étape 3).
    items: list[tuple[Case, object | None, float, BaseException | None]] = []
    histories: dict[str, pd.DataFrame] = {}
    for _, row in cases.iterrows():
        case = Case.from_row(row)
        started = time.perf_counter()
        try:
            if case.counter_id not in histories:
                histories[case.counter_id] = history_loader(case.counter_id)
            inputs = P.build_inputs(case, histories[case.counter_id], None, lag)
            light = dataclasses.replace(
                inputs,
                history=inputs.history.iloc[0:0].copy(),  # copie : une vue garderait tout
                context_version=context_version if context is not None else None,
            )
            del inputs
            items.append((case, light, time.perf_counter() - started, None))
        except Exception as exc:  # noqa: BLE001 - l'échec est tracé, jamais silencieux
            items.append((case, None, 0.0, exc))

    # 2. Sortie brute en bloc, pour les cas préparés et éligibles.
    method = variant
    reasons: dict[int, str | None] = {}
    todo = []
    for k, (_, inputs, _, exc) in enumerate(items):
        if exc is None:
            reasons[k] = P.eligibility_reason(inputs, model, method)
            if reasons[k] is None:
                todo.append(k)
    started = time.perf_counter()
    raw_values = np.full((len(items), HORIZON_HOURS), np.nan)
    if todo:
        # une seule copie de l'historique par compteur (et non par cas : 6 014 copies
        # saturaient la mémoire)
        needed = sorted({items[k][0].counter_id for k in todo})
        counts = pd.concat([histories[c] for c in needed], ignore_index=True)
        extra = {"min_observed_hours": min_observed_hours} if variant == P.MLP_VARIANT else {}
        values, raw_reasons = RAW_BATCH[variant](
            [items[k][0] for k in todo],
            counts,
            context,
            model,
            publication_lag_hours=lag,
            **extra,
        )
        for row, k in enumerate(todo):
            raw_values[k] = values[row]
            reasons[k] = raw_reasons[row]
    share = (time.perf_counter() - started) / max(len(todo), 1)

    # 3. Un résultat par cas, avec le même assemblage que le cas par cas.
    results = []
    for k, (case, inputs, preparation, exc) in enumerate(items):
        if exc is not None:
            results.append(P.error_result(case, method_run_id, variant, exc))
            continue
        values = raw_values[k] if reasons[k] is None else None
        if values is None:  # repli : la référence a besoin du passé, reconstruit puis jeté
            full = P.build_inputs(case, histories[case.counter_id], None, lag)
            inputs = dataclasses.replace(inputs, history=full.history)
        result = P._assemble_result(
            inputs, method, model, values, reasons[k], method_run_id=method_run_id
        )
        result.cost.preparation_seconds = preparation
        result.cost.inference_seconds = share if k in todo else 0.0
        results.append(result)
    out_dir = Path(root) if root else P.data_path("predictions") / experiment_id
    pred = P.write_predictions(results, out_dir / f"{method_run_id}.pred.csv")
    runs = P.write_runs(results, out_dir / f"{method_run_id}.runs.csv")
    return pred, runs

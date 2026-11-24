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

import importlib

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

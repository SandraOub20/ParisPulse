"""Gradient boosting tabulaire (HGB) pour les sites connus - E2.

Modèle : sklearn.ensemble.HistGradientBoostingRegressor, un seul modèle global pour tous
les compteurs S_train et les 24 horizons (une ligne = un compteur × une origine × une heure
cible). Pas d'identifiant de compteur (D-15) : les niveaux récents en tiennent lieu.

    entrée : features.feature_columns(groupes) de la version f1.0 : calendrier de base
             (horizon, heure, jour, week-end, mois), historique (lags 168/336 h, profil
             4 semaines, niveaux, tendance, manques, zéros), contexte selon les groupes
             retenus (calendar, strikes, weather_forecast)
    sortie : une valeur en vélos/h par ligne, bornée à >= 0

Pourquoi ce modèle (à justifier par la bibliographie dans la fiche EXP-E2-03) :
- PLAN_PROJET §7 propose un « gradient boosting global » pour les sites connus ;
- variables hétérogènes, interactions heure × jour × niveau apprises sans réglage manuel ;
- valeurs manquantes gérées nativement : un NaN reste un NaN, jamais un 0 (C1) ;
- loss="absolute_error" optimise directement la MAE, métrique du projet ;
- apprentissage CPU en minutes, coût d'inférence faible.

Causalité (mêmes garanties que les références et le MLP) :
- un seul calcul de variables : features.build_training_frame à l'apprentissage,
  features.build_feature_frame à la prévision (égalité testée dans test_known_features) ;
- origines d'apprentissage fixées par train.fit (mêmes compteurs, mêmes origines que le
  MLP : comparaison équitable) et revérifiées ici avant toute lecture de cible ;
- latence : celle de la configuration uniquement (D-22) ;
- arrêt anticipé TEMPOREL sur les holdout_weeks dernières semaines avant fit_cutoff. Le
  découpage aléatoire de sklearn (early_stopping=True, validation_fraction) est interdit :
  il mélangerait des heures d'une même journée entre apprentissage et contrôle.

Arrêt anticipé : le modèle est d'abord appris avec max_iter arbres sur la partie
apprentissage ; staged_predict donne la MAE du holdout après chaque arbre ; le modèle est
ensuite réappris avec le meilleur nombre d'arbres (sur l'apprentissage seul, ou sur
apprentissage + holdout si refit_on_holdout). Sans sous-échantillonnage, l'apprentissage
est déterministe : le réapprentissage sur l'apprentissage seul redonne exactement les
mêmes premiers arbres. Coût : environ deux apprentissages.

Prévision (predict_hgb) : 24 valeurs >= 0, ou un refus motivé (codes REFUSE_*). Le repli
sur la référence est décidé par l'appelant (predict.py), jamais ici, comme pour le MLP.

Points ouverts (voir reports/teams/E2_SUIVI.md) :
- loss principale (absolute_error proposée ; poisson en variante) ;
- réapprendre ou non sur les semaines d'arrêt anticipé (même question que D-20) ;
- variables catégorielles (hour_local, dow_local, month_local, horizon) ou numériques ;
- _check_training_origins et _holdout_start dupliquent neural.py (qui importe torch) :
  à factoriser dans train.py ou features.py avec Idir.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from src.models.known import baseline, train
from src.models.known import features as F
from src.models.known.train import MethodBackend, register_backend
from src.models.schemas import HORIZON_HOURS, ForecastInputs

METHOD = "hgb"
WEIGHTS_FILE = "model.joblib"
# Version du contenu de model.joblib, à incrémenter si SAVED_FIELDS change.
# 1 : objet HGBModel picklé (illisible s'il a été écrit par la commande) ; 2 : dictionnaire.
FILE_FORMAT = 2

# Réglages de l'apprentissage (fit_hgb). Utiliser hgb_hyperparameters() pour les compléter :
# metadata.json et le nom du modèle portent alors tous les réglages réellement utilisés.
DEFAULT_HYPERPARAMETERS: dict[str, Any] = {
    "loss": "absolute_error",  # MAE directe ; "poisson" en variante (comptages)
    "learning_rate": 0.1,
    "max_iter": 500,  # plafond : l'arrêt anticipé temporel choisit le nombre d'arbres
    "max_leaf_nodes": 31,
    "min_samples_leaf": 20,
    "l2_regularization": 0.0,
    "max_bins": 255,
    "categorical": False,  # True : hour_local, dow_local, month_local, horizon en catégories
    "context_groups": None,  # None = tous les groupes si use_context ; liste pour l'ablation
    "holdout_weeks": 4,  # arrêt anticipé sur les dernières semaines avant fit_cutoff (0 = aucun)
    "patience": 20,  # itérations sans progrès sur le holdout avant d'arrêter
    "refit_on_holdout": False,  # True : réapprendre sur tout avec le nombre d'arbres retenu
}
LOSSES = ("absolute_error", "poisson", "squared_error")
CATEGORICAL_COLUMNS = ("hour_local", "dow_local", "month_local", "horizon")

# Codes de refus de predict_hgb : stables, lus par predict.py (repli), E4 et E5.
REFUSE_NOT_MIDNIGHT = "hgb_origin_not_midnight"  # origines d'apprentissage toutes à minuit
REFUSE_BEFORE_CUTOFF = "hgb_origin_before_fit_cutoff"  # journée vue pendant l'apprentissage
REFUSE_NO_HISTORY = "hgb_no_history"  # aucune mesure publiée pour ce compteur
REFUSE_CONTEXT = "hgb_context_missing"  # modèle avec contexte, contexte absent à l'origine
REFUSE_NON_FINITE = "hgb_non_finite_output"  # sortie non finie (ne devrait jamais arriver)


@dataclass
class HGBModel:
    """Ce qui est sauvegardé dans model.joblib : l'estimateur et de quoi le réutiliser sûrement.

    La disposition des entrées (colonnes, ordre, groupes de contexte, latence, version des
    variables) est comparée au chargement et à la prévision : un modèle appris sur des
    entrées rangées autrement est refusé (réentraîner).
    """

    estimator: Any  # HistGradientBoostingRegressor entraîné
    feature_columns: list[str]  # ordre exact des colonnes de X
    context_groups: tuple[str, ...]  # () si use_context=False
    publication_lag_hours: int
    fit_cutoff: pd.Timestamp
    feature_version: str = F.FEATURE_VERSION
    file_format: int = FILE_FORMAT
    training_report: dict[str, Any] = field(default_factory=dict)

    @property
    def use_context(self) -> bool:
        return bool(self.context_groups)


@dataclass(frozen=True)
class HGBForecast:
    """Résultat de predict_hgb : 24 valeurs en vélos/h, ou un refus motivé (values=None)."""

    values: np.ndarray | None  # (24,) >= 0, horizons 1 à 24 dans l'ordre
    reason: str | None  # code REFUSE_* en cas de refus, None sinon

    @property
    def ok(self) -> bool:
        return self.values is not None


# --------------------------------------------------------------------------- réglages


def hgb_hyperparameters(**overrides: Any) -> dict[str, Any]:
    """Réglages complets de fit_hgb : DEFAULT_HYPERPARAMETERS remplacés par overrides.

    À passer tels quels dans TrainConfig.hyperparameters : metadata.json et le nom du
    modèle portent alors tous les réglages réellement utilisés. Refuse une clé inconnue
    (faute de frappe) ou une valeur hors domaine. context_groups est rendu comme une liste
    dans l'ordre de features.CONTEXT_GROUPS (empreinte stable), ou None.
    """
    unknown = set(overrides) - set(DEFAULT_HYPERPARAMETERS)
    if unknown:
        raise ValueError(
            f"réglages HGB inconnus : {sorted(unknown)} ; connus : {sorted(DEFAULT_HYPERPARAMETERS)}"
        )
    hp = {**DEFAULT_HYPERPARAMETERS, **overrides}
    for key, low, high in (
        ("max_iter", 1, None),
        ("max_leaf_nodes", 2, None),
        ("min_samples_leaf", 1, None),
        ("max_bins", 2, 255),
        ("holdout_weeks", 0, None),
        ("patience", 1, None),
    ):
        value = hp[key]
        bad = isinstance(value, bool) or not isinstance(value, int) or value < low
        if bad or (high is not None and value > high):
            bounds = f"dans [{low}, {high}]" if high is not None else f">= {low}"
            raise ValueError(f"réglage {key}={value!r} : entier {bounds} attendu")
    for key, strict in (("learning_rate", True), ("l2_regularization", False)):
        value = hp[key]
        ok = not isinstance(value, bool) and isinstance(value, int | float)
        ok = ok and bool(np.isfinite(value)) and (value > 0 if strict else value >= 0)
        if not ok:
            raise ValueError(
                f"réglage {key}={value!r} : nombre {'>' if strict else '>='} 0 attendu"
            )
        hp[key] = float(value)  # 1 et 1.0 donnent la même empreinte de configuration
    for key in ("categorical", "refit_on_holdout"):
        if not isinstance(hp[key], bool):
            raise ValueError(f"réglage {key}={hp[key]!r} : booléen attendu")
    if hp["loss"] not in LOSSES:
        raise ValueError(f"loss={hp['loss']!r} : {LOSSES} attendus")
    groups = hp["context_groups"]
    if groups is not None:
        if isinstance(groups, str) or not isinstance(groups, list | tuple):
            raise ValueError(f"context_groups={groups!r} : liste de groupes ou None attendue")
        hp["context_groups"] = list(F.resolve_context_groups(True, groups))
        if not hp["context_groups"]:
            raise ValueError("context_groups vide : utiliser use_context=False")
    return {key: hp[key] for key in DEFAULT_HYPERPARAMETERS}


def resolve_groups(config: train.TrainConfig, hp: dict[str, Any]) -> tuple[str, ...]:
    """Groupes de contexte du modèle : features.resolve_context_groups(use_context, hp).

    train.TrainConfig n'a pas de champ context_groups : l'ablation par groupe passe par
    hp["context_groups"], qui entre ainsi dans l'empreinte et dans metadata.json.
    Refuse context_groups non vide avec use_context=False (réglage contradictoire).
    """
    groups = hp.get("context_groups")
    if not config.use_context and groups:
        raise ValueError("context_groups donné avec use_context=False : réglage contradictoire")
    return F.resolve_context_groups(bool(config.use_context), groups)


# --------------------------------------------------------------------------- apprentissage


def fit_hgb(
    config: train.TrainConfig,
    counts: pd.DataFrame,
    context: pd.DataFrame | None,
    origins: pd.DataFrame,
) -> HGBModel:
    """Apprendre le HGB sur les origines fixées par train.fit (backend « hgb »).

    1. Réglages, groupes de contexte, latence de la configuration ; use_context sans
       contexte refusé (ValueError).
    2. _check_training_origins AVANT toute lecture de cible.
    3. X, y = features.build_training_frame(...) ; entrée du modèle = X[feature_columns]
       seulement (les META_COLUMNS servent à la traçabilité et au découpage).
    4. Découpage temporel : holdout = origines des holdout_weeks dernières semaines.
    5. Apprentissage, choix du nombre d'arbres sur le holdout, réapprentissage avec ce nombre.
    6. Bilan rangé dans HGBModel.training_report.
    """
    started = time.perf_counter()
    hp = hgb_hyperparameters(**config.hyperparameters)
    groups = resolve_groups(config, hp)
    lag = F._default_lag()
    fit_cutoff = F._utc(config.fit_cutoff, "fit_cutoff")
    if groups and (context is None or len(context) == 0):
        raise ValueError(
            "use_context=True sans contexte : fournir context.csv ou apprendre avec "
            "use_context=False (sinon le modèle apprendrait un contexte toujours absent)"
        )
    _check_training_origins(origins, fit_cutoff, lag)

    X, y = F.build_training_frame(
        counts,
        origins,
        context if groups else None,
        fit_cutoff,
        bool(groups),
        context_groups=list(groups) or None,
        publication_lag_hours=lag,
    )
    if X.empty:
        raise ValueError("aucune cible d'apprentissage publiée à fit_cutoff")
    built = time.perf_counter()
    columns = F.feature_columns(groups)
    values = X[columns].to_numpy(dtype=np.float32)
    target = y.to_numpy(dtype=np.float64)
    train_mask, hold_mask = _split_holdout(X, fit_cutoff, hp["holdout_weeks"])

    curve: list[float] = []
    if hold_mask.any():
        probe = _make_estimator(hp, columns, config.seed)
        probe.fit(values[train_mask], target[train_mask])
        n_trees, curve = _best_iteration(
            probe, values[hold_mask], target[hold_mask], hp["patience"]
        )
    else:
        n_trees = hp["max_iter"]
    final_rows = (train_mask | hold_mask) if hp["refit_on_holdout"] else train_mask
    estimator = _make_estimator({**hp, "max_iter": n_trees}, columns, config.seed)
    estimator.fit(values[final_rows], target[final_rows])
    fitted = time.perf_counter()

    hold_pred = (
        np.clip(estimator.predict(values[hold_mask]), 0.0, None) if hold_mask.any() else None
    )
    report = _training_report(
        fit_cutoff=fit_cutoff,
        lag=lag,
        groups=groups,
        hp=hp,
        X=X,
        columns=columns,
        train_mask=train_mask,
        hold_mask=hold_mask,
        n_trees=n_trees,
        curve=curve,
        holdout=(
            _holdout_metrics(X.loc[hold_mask], target[hold_mask], hold_pred)
            if hold_pred is not None
            else None
        ),
        features_seconds=built - started,
        fit_seconds=fitted - built,
    )
    return HGBModel(
        estimator=estimator,
        feature_columns=columns,
        context_groups=tuple(groups),
        publication_lag_hours=lag,
        fit_cutoff=fit_cutoff,
        training_report=report,
    )


def _check_training_origins(origins: pd.DataFrame, fit_cutoff: pd.Timestamp, lag: int) -> None:
    """Mêmes contrôles que neural._check_training_origins (à factoriser, voir module).

    Refuse : aucune origine ; une origine dont les 24 cibles ne sont pas publiées à
    fit_cutoff (origine + 24 h + latence > fit_cutoff : fuite) ; une origine hors minuit
    (Europe/Paris) ; une origine en double pour un même compteur.
    """
    if origins.empty:
        raise ValueError("aucune origine d'apprentissage")
    origin_h = F._to_hours(origins["origin"], "origin")
    late = origin_h + HORIZON_HOURS + lag > F._hour_of(fit_cutoff, "fit_cutoff")
    if late.any():
        first = pd.Timestamp(int(origin_h[late].min()) * F.HOUR_NS, tz="UTC").isoformat()
        raise ValueError(
            f"{int(late.sum())} origine(s) dont les 24 cibles ne sont pas publiées à "
            f"fit_cutoff (première : {first}) : apprendre dessus serait une fuite"
        )
    local = pd.DatetimeIndex(origin_h * F.HOUR_NS, tz="UTC").tz_convert(F.LOCAL_TZ)
    if (local.hour != 0).any():
        raise ValueError("origine hors minuit (Europe/Paris) : les cas d'E4 sont à minuit")
    keys = pd.DataFrame({"counter_id": origins["counter_id"].astype(str), "origin_h": origin_h})
    if keys.duplicated().any():
        raise ValueError("origine en double : ses 24 lignes compteraient deux fois")


def _holdout_start(fit_cutoff: pd.Timestamp, weeks: int) -> pd.Timestamp | None:
    """Minuit (Paris) qui ouvre les `weeks` dernières semaines avant fit_cutoff ; None si 0.

    Même calcul que neural._holdout_start (dates locales : un changement d'heure dans
    l'intervalle ne décale pas la limite).
    """
    if weeks == 0:
        return None
    day = fit_cutoff.tz_convert(F.LOCAL_TZ).tz_localize(None).normalize()
    return (day - pd.Timedelta(days=7 * weeks)).tz_localize(F.LOCAL_TZ).tz_convert("UTC")


def _split_holdout(
    X: pd.DataFrame, fit_cutoff: pd.Timestamp, weeks: int
) -> tuple[np.ndarray, np.ndarray]:
    """Masques booléens (apprentissage, holdout) sur les lignes de X, selon X["origin"].

    Une origine entière (ses 24 heures) est toujours du même côté. ValueError si
    l'apprentissage est vide, ou si le holdout est vide alors que weeks > 0.
    """
    start = _holdout_start(fit_cutoff, weeks)
    if start is None:
        hold = np.zeros(len(X), dtype=bool)
    else:
        hold = (X["origin"] >= start).to_numpy()
    train_mask = ~hold
    if not train_mask.any():
        raise ValueError("aucune ligne d'apprentissage avant l'arrêt anticipé")
    if start is not None and not hold.any():
        raise ValueError(
            f"aucune ligne dans les {weeks} semaines avant fit_cutoff : arrêt anticipé "
            "impossible (holdout_weeks=0 pour apprendre sans)"
        )
    return train_mask, hold


def _make_estimator(hp: dict[str, Any], columns: list[str], seed: int) -> Any:
    """HistGradientBoostingRegressor configuré depuis hp.

    early_stopping=False (jamais de découpage aléatoire) ; random_state=seed ;
    categorical_features = masque des CATEGORICAL_COLUMNS présentes si hp["categorical"]
    (valeurs entières >= 0 et < max_bins : heure 0-23, jour 0-6, mois 1-12, horizon 1-24).
    """
    categorical = None
    if hp["categorical"]:
        if hp["max_bins"] <= HORIZON_HOURS:
            raise ValueError("categorical=True demande max_bins > 24 (horizon 1 à 24)")
        categorical = [c in CATEGORICAL_COLUMNS for c in columns]
    return HistGradientBoostingRegressor(
        loss=hp["loss"],
        learning_rate=hp["learning_rate"],
        max_iter=hp["max_iter"],
        max_leaf_nodes=hp["max_leaf_nodes"],
        min_samples_leaf=hp["min_samples_leaf"],
        l2_regularization=hp["l2_regularization"],
        max_bins=hp["max_bins"],
        categorical_features=categorical,
        early_stopping=False,
        random_state=seed,
    )


def _best_iteration(
    estimator: Any, X_hold: np.ndarray, y_hold: np.ndarray, patience: int
) -> tuple[int, list[float]]:
    """Nombre d'arbres qui minimise la MAE du holdout (staged_predict, sorties >= 0).

    Le parcours s'arrête après `patience` arbres sans progrès. Retourne aussi la courbe
    (MAE après chaque arbre parcouru) pour le bilan. MAE sur toutes les cellules du holdout
    (contrôle interne, pas la MAE macro d'E4).
    """
    curve: list[float] = []
    best, best_mae, waited = 1, np.inf, 0
    for i, pred in enumerate(estimator.staged_predict(X_hold), start=1):
        mae = float(np.mean(np.abs(np.clip(pred, 0.0, None) - y_hold)))
        curve.append(round(mae, 6))
        if mae < best_mae:
            best, best_mae, waited = i, mae, 0
        else:
            waited += 1
            if waited >= patience:
                break
    return best, curve


def _training_report(
    *,
    fit_cutoff: pd.Timestamp,
    lag: int,
    groups: tuple[str, ...],
    hp: dict[str, Any],
    X: pd.DataFrame,
    columns: list[str],
    train_mask: np.ndarray,
    hold_mask: np.ndarray,
    n_trees: int,
    curve: list[float],
    holdout: dict | None,
    features_seconds: float,
    fit_seconds: float,
) -> dict[str, Any]:
    """Bilan JSON-sérialisable de l'apprentissage, sur le modèle de neural._training_report.

    L'importance des variables n'est PAS calculée ici : à faire sur la validation, par
    permutation, dans l'expérience EXP-E2-03.
    """

    def part(mask: np.ndarray) -> dict[str, Any]:
        sub = X.loc[mask]
        if sub.empty:
            return {
                "rows": 0,
                "origins": 0,
                "counters": 0,
                "first_origin": None,
                "last_origin": None,
            }
        return {
            "rows": int(len(sub)),
            "origins": int(sub[["counter_id", "origin"]].drop_duplicates().shape[0]),
            "counters": int(sub["counter_id"].nunique()),
            "first_origin": sub["origin"].min().isoformat(),
            "last_origin": sub["origin"].max().isoformat(),
        }

    nan_share = X[columns].isna().mean()
    return {
        "method": METHOD,
        "fit_cutoff": fit_cutoff.isoformat(),
        "publication_lag_hours": int(lag),
        "context_groups": list(groups),
        "feature_version": F.FEATURE_VERSION,
        "hyperparameters": hp,
        "examples": {
            "train": part(train_mask),
            "holdout": part(hold_mask),
            "refit_on_holdout": bool(hp["refit_on_holdout"]),
        },
        "nan_share": {c: round(float(v), 6) for c, v in nan_share.items() if v > 0},
        "n_trees": int(n_trees),
        "holdout_curve": curve,
        "holdout_metrics": holdout,
        "features_seconds": round(features_seconds, 3),
        "fit_seconds": round(fit_seconds, 3),
    }


def _holdout_metrics(X_hold: pd.DataFrame, y_hold: np.ndarray, pred: np.ndarray) -> dict:
    """MAE de contrôle sur le holdout : HGB, lag_168h et profile_median_4w sur LES MÊMES cellules.

    Cellules = lignes où les trois prévisions existent. MAE par compteur puis moyenne
    entre compteurs (comme E4). Contrôle de bon fonctionnement, PAS une comparaison
    officielle (celle-ci se fait sur la validation, avec les scores d'E4).
    Si le modèle a été réappris sur le holdout (refit_on_holdout), ce contrôle est optimiste.
    """
    lag = X_hold["lag_168h"].to_numpy(dtype=float)
    profile = X_hold["profile_median_4w"].to_numpy(dtype=float)
    cells = np.isfinite(pred) & np.isfinite(lag) & np.isfinite(profile) & np.isfinite(y_hold)
    counters = X_hold["counter_id"].astype(str).to_numpy()
    out: dict[str, Any] = {"cells": int(cells.sum()), "counters": int(len(set(counters[cells])))}
    for name, values in (("hgb", pred), ("lag_168h", lag), ("profile_median_4w", profile)):
        if not cells.any():
            out[f"mae_{name}"] = None
            continue
        errors = pd.Series(np.abs(values[cells] - y_hold[cells]))
        per_counter = errors.groupby(counters[cells]).mean()
        out[f"mae_{name}"] = round(float(per_counter.mean()), 4)
    return out


# --------------------------------------------------------------------------- prévision


def refusal_reason(model: HGBModel, inputs: ForecastInputs) -> str | None:
    """Code de refus d'un cas (None s'il peut être prévu), avant tout calcul de variables.

    Ordre : origine hors minuit ; origine < fit_cutoff du modèle ; aucune mesure publiée
    (historique admissible vide) ; modèle avec contexte et contexte absent.
    Le HGB tolère les NaN : une fenêtre clairsemée n'est PAS un motif de refus (différence
    avec le MLP, à documenter dans la fiche). ValueError si la latence du cas
    (origin - information_cutoff) diffère de model.publication_lag_hours.
    """
    case = inputs.case
    origin = F._utc(case.origin, "case.origin")
    cutoff = F._utc(inputs.information_cutoff, "information_cutoff")
    if origin - cutoff != pd.Timedelta(hours=model.publication_lag_hours):
        raise ValueError(
            f"{case.case_id} : latence du cas {origin - cutoff} différente de celle de "
            f"l'apprentissage ({model.publication_lag_hours} h)"
        )
    local = origin.tz_convert(F.LOCAL_TZ)
    if local != local.normalize():
        return REFUSE_NOT_MIDNIGHT
    if origin < F._utc(model.fit_cutoff, "fit_cutoff"):
        return REFUSE_BEFORE_CUTOFF
    history = baseline.admissible_history(inputs.history, cutoff, counter_id=case.counter_id)
    if pd.to_numeric(history["count"], errors="coerce").notna().sum() == 0:
        return REFUSE_NO_HISTORY
    if model.use_context and (inputs.context is None or len(inputs.context) == 0):
        return REFUSE_CONTEXT
    return None


def predict_frame(model: HGBModel, X: pd.DataFrame) -> np.ndarray:
    """Prévisions >= 0 pour des lignes de variables (build_feature_frame ou build_training_frame).

    Contrôle que X contient model.feature_columns et que X["feature_version"] vaut
    model.feature_version. Sert au cas par cas et au calcul en bloc (validation).
    """
    missing = [c for c in model.feature_columns if c not in X.columns]
    if missing:
        raise ValueError(f"colonnes absentes des variables : {missing}")
    if "feature_version" in X.columns:
        versions = set(X["feature_version"].astype(str))
        if versions - {model.feature_version}:
            raise ValueError(
                f"variables {sorted(versions)} au lieu de {model.feature_version!r} : réentraîner"
            )
    if X.empty:
        return np.empty(0)
    values = X[model.feature_columns].to_numpy(dtype=np.float32)
    return np.clip(model.estimator.predict(values), 0.0, None)


def predict_hgb(model: HGBModel, inputs: ForecastInputs) -> HGBForecast:
    """Prévoir les 24 heures d'un cas, ou refuser avec une raison (repli : l'appelant).

    1. refusal_reason ; 2. features.build_feature_frame (même calcul qu'à l'apprentissage) ;
    3. predict_frame. Les cibles ne sont jamais lues (build_feature_frame ne produit pas de
    label). Un modèle avec contexte dont toutes les valeurs de contexte sont inconnues à
    l'origine est refusé (REFUSE_CONTEXT).
    """
    reason = refusal_reason(model, inputs)
    if reason is not None:
        return HGBForecast(None, reason)
    X = F.build_feature_frame(
        inputs, model.use_context, context_groups=list(model.context_groups) or None
    )
    if model.use_context:
        context_columns = [c for g in model.context_groups for c in F.CONTEXT_GROUPS[g]]
        if X[context_columns].isna().all().all():
            return HGBForecast(None, REFUSE_CONTEXT)
    values = predict_frame(model, X)
    if len(values) != HORIZON_HOURS or not np.isfinite(values).all():
        return HGBForecast(None, REFUSE_NON_FINITE)
    return HGBForecast(values, None)


# --------------------------------------------------------------------------- sauvegarde


SAVED_FIELDS = (
    "file_format",
    "estimator",
    "feature_columns",
    "context_groups",
    "publication_lag_hours",
    "fit_cutoff",
    "feature_version",
    "training_report",
)


def save_hgb(model: HGBModel, path: Path) -> None:
    """Écrire model.joblib (joblib.dump) pour train.save_model.

    Le fichier contient un dictionnaire de champs (SAVED_FIELDS), pas l'objet HGBModel :
    lancé par « python -m src.models.known.tabular », ce module s'appelle __main__ et une
    classe picklée y serait introuvable au chargement (format 1, abandonné).
    joblib = pickle : le fichier peut exécuter du code au chargement. Il n'est relu que
    via train.load_model, qui vérifie d'abord le SHA-256 enregistré dans metadata.json.
    """
    if type(model).__name__ != "HGBModel":
        raise TypeError(f"HGBModel attendu, reçu {type(model).__name__}")
    payload = {name: getattr(model, name) for name in SAVED_FIELDS}
    payload["feature_columns"] = list(model.feature_columns)
    payload["context_groups"] = list(model.context_groups)
    payload["fit_cutoff"] = F._utc(model.fit_cutoff, "fit_cutoff").isoformat()
    joblib.dump(payload, Path(path))


def load_hgb(path: Path) -> HGBModel:
    """Relire model.joblib et refuser un modèle incompatible avec le code actuel.

    Refuse : contenu qui n'est pas un modèle HGB sauvegardé par save_hgb ; file_format
    inconnu ; feature_version différente de features.FEATURE_VERSION ; feature_columns
    différentes de features.feature_columns(context_groups) ; latence différente de la
    configuration.
    """
    saved = joblib.load(Path(path))
    if not isinstance(saved, dict) or set(saved) != set(SAVED_FIELDS):
        raise ValueError(f"{path} : contenu d'un HGBModel attendu, trouvé {type(saved).__name__}")
    model = HGBModel(
        estimator=saved["estimator"],
        feature_columns=list(saved["feature_columns"]),
        context_groups=tuple(saved["context_groups"]),
        publication_lag_hours=int(saved["publication_lag_hours"]),
        fit_cutoff=F._utc(pd.Timestamp(saved["fit_cutoff"]), "fit_cutoff"),
        feature_version=saved["feature_version"],
        file_format=saved["file_format"],
        training_report=saved["training_report"],
    )
    if model.file_format != FILE_FORMAT:
        raise ValueError(f"{path} : format {model.file_format!r}, attendu {FILE_FORMAT}")
    if model.feature_version != F.FEATURE_VERSION:
        raise ValueError(
            f"{path} : appris sur les variables {model.feature_version!r}, le code fournit "
            f"{F.FEATURE_VERSION!r} : réentraîner le modèle"
        )
    if list(model.feature_columns) != F.feature_columns(model.context_groups):
        raise ValueError(f"{path} : colonnes d'entrée différentes du code : réentraîner")
    if model.publication_lag_hours != F._default_lag():
        raise ValueError(
            f"{path} : latence {model.publication_lag_hours} h différente de la configuration "
            f"({F._default_lag()} h)"
        )
    return model


# Branchement sur train.py : save_model / load_model / fit savent écrire, relire et
# entraîner un HGB. Importer ce module déclare la méthode « hgb » (sinon train.fit lève
# KeyError).
register_backend(
    METHOD,
    MethodBackend(
        WEIGHTS_FILE,
        save=save_hgb,
        load=load_hgb,
        fit=fit_hgb,
        minimum_history_hours=None,  # NaN tolérés : une seule mesure publiée suffit
    ),
)


# --------------------------------------------------------------------------- commande


def main(argv: list[str] | None = None) -> int:
    """Entraîner le HGB sur un instantané E1, le sauvegarder et afficher son bilan (JSON).

    Exemple (coupure au 01/07/2026 minuit à Paris, avec contexte, graine 0) :
    python -m src.models.known.tabular --snapshot hist-20261117 \
        --fit-cutoff 2026-06-30T22:00:00+00:00 --seed 0
    Réglages : --set loss=poisson, --set 'context_groups=["calendar"]'...
    Écrit artifacts/models/<model_run_id>/ : model.joblib, metadata.json et
    training_report.json. Entrées = mesures seules (D-11).
    """
    parser = argparse.ArgumentParser(description=main.__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True, help="instantané E1, ex. hist-20261117")
    parser.add_argument("--fit-cutoff", required=True, help="ISO 8601 avec fuseau")
    parser.add_argument("--train-start", help="ISO 8601 avec fuseau ; défaut : début des données")
    parser.add_argument("--no-context", action="store_true", help="apprendre sans contexte")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--set", action="append", default=[], metavar="CLÉ=VALEUR", help="réglage du HGB"
    )
    parser.add_argument("--protocol-id")
    parser.add_argument("--root", type=Path, help="dossier des modèles (défaut : config)")
    parser.add_argument("--no-save", action="store_true", help="apprendre sans écrire")
    args = parser.parse_args(argv)

    try:
        fit_cutoff = _parse_utc(args.fit_cutoff, "--fit-cutoff")
        train_start = _parse_utc(args.train_start, "--train-start") if args.train_start else None
        hp = hgb_hyperparameters(**dict(_parse_setting(item) for item in args.set))
    except ValueError as exc:
        parser.error(str(exc))

    started = time.perf_counter()
    data = train.load_training_data(args.snapshot)
    loaded = time.perf_counter()
    config = train.TrainConfig(
        method=METHOD,
        fit_cutoff=fit_cutoff,
        train_start=train_start,
        use_context=not args.no_context,
        hyperparameters=hp,
        seed=args.seed,
        protocol_id=args.protocol_id,
        snapshot_id=args.snapshot,
        context_version=data.context_version,
        feature_version=F.FEATURE_VERSION,
    )
    model = train.fit(config, data.counts, data.context, data.inventory)
    summary = {
        "model_run_id": model.model_run_id,
        "snapshot_id": args.snapshot,
        "load_seconds": round(loaded - started, 1),
        "train_fit_seconds": round(model.train_seconds, 1),
        "total_seconds": round(time.perf_counter() - started, 1),
        "donor_site_groups": len(model.donor_site_groups),
        "excluded_site_groups": model.excluded_site_groups,
        "label_interval": [stamp.isoformat() for stamp in model.label_interval],
        "training_report": model.estimator.training_report,
    }
    if not args.no_save:
        out = train.save_model(model, args.root)
        summary["model_dir"] = train.repo_relative(out)
        (out / "training_report.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _parse_utc(text: str, name: str) -> pd.Timestamp:
    stamp = pd.Timestamp(text)
    if stamp.tzinfo is None:
        raise ValueError(f"{name} doit porter un fuseau, ex. 2026-06-30T22:00:00+00:00")
    return stamp.tz_convert("UTC")


def _parse_setting(text: str) -> tuple[str, Any]:
    """« max_iter=300 » -> ("max_iter", 300) ; valeur JSON si possible, texte sinon."""
    key, sep, raw = text.partition("=")
    if not sep or not key.strip():
        raise ValueError(f"--set attend CLÉ=VALEUR, reçu {text!r}")
    try:
        return key.strip(), json.loads(raw)
    except json.JSONDecodeError:
        return key.strip(), raw


if __name__ == "__main__":
    raise SystemExit(main())

"""Réseau compact (MLP) pour les sites connus - E2, expérience de deep learning.

Un exemple = un compteur et une origine (minuit à Paris). Le réseau voit la dernière
semaine publiée et prévoit les 24 heures de la journée d'un coup.

    entrée : 168 h visibles divisées par leur niveau, 168 masques (1 = mesuré),
             la journée à prévoir (jour de la semaine, changement d'heure ; fériés,
             vacances, grève si use_context), la météo prévue heure par heure (si use_context)
    sortie : 24 valeurs divisées par le même niveau, remultipliées ensuite

L'heure de chaque sortie n'est pas donnée en entrée : l'origine étant minuit à Paris,
la sortie k correspond toujours à la k-ième heure de la journée.

Un seul calcul (build_windows) sert à l'apprentissage et à la prévision : le réseau
voit en production exactement ce qu'il a appris. Le contexte est joint par les mêmes
fonctions que features.py (mêmes règles de disponibilité que le HGB).

Apprentissage (fit_mlp, MOD-008) :
- perte L1 sur les seules vraies mesures (target_mask), exemples utilisables seulement ;
- pondérée par le niveau de la fenêtre : on minimise l'erreur absolue en vélos/h, la
  métrique du projet (pondération par l'échelle, comme DeepAR) ; la perte L1 borne
  l'influence des cibles extrêmes sans plafond arbitraire ;
- arrêt anticipé sur les 4 dernières semaines avant fit_cutoff, jamais sur la validation ;
- graine fixée sans modifier le générateur aléatoire global de torch.

Prévision (predict_mlp) : 24 valeurs >= 0 en vélos/h, ou un refus motivé (codes REFUSE_*).
Le repli sur la référence est décidé par l'appelant (predict.py), jamais ici.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

from src.models.known import baseline, train
from src.models.known import features as F
from src.models.known.train import MethodBackend, register_backend
from src.models.schemas import HORIZON_HOURS, ForecastInputs

METHOD = "mlp"
WEIGHTS_FILE = "weights.pt"
FILE_FORMAT = 2  # version du contenu de weights.pt (2 : latence dans la disposition, bilan)
READABLE_FORMATS = (1, FILE_FORMAT)  # format 1 (MOD-007) : latence implicite de 24 h
INPUT_VERSION = "mlp-in1"  # version des entrées de build_windows : à incrémenter si elles changent

WINDOW_HOURS = 168  # une semaine visible
DEFAULT_LAG_HOURS = 24  # délai de publication simulé
MIN_OBSERVED_HOURS = 84  # au moins la moitié de la fenêtre mesurée
MIN_SCALE = 1.0  # niveau moyen minimal (vélos/h) pour normaliser sans exploser
INPUT_CLIP = 10.0  # une heure d'entrée vaut au plus 10 fois le niveau (pics aberrants)
# Mise à l'échelle fixe de la météo prévue (pas de statistique apprise à sauvegarder).
WEATHER_SCALE = {"temp_prev": 10.0, "rain_prev": 1.0, "wind_prev": 5.0}
# Journée à prévoir, donnée une seule fois : jour de la semaine (0 = lundi) et
# dst_shift = longueur du jour - 24 h (-1 au passage à l'heure d'été, +1 à l'heure d'hiver).
DAY_BASE = [f"dow_{d}" for d in range(7)] + ["dst_shift"]
DAY_CONTEXT_GROUPS = ("calendar", "strikes")  # une valeur par jour
HOURLY_CONTEXT_GROUPS = ("weather_forecast",)  # une valeur par heure cible

# Réglages de l'apprentissage (fit_mlp). Utiliser mlp_hyperparameters() pour les compléter :
# metadata.json et le nom du modèle portent alors tous les réglages réellement utilisés.
DEFAULT_HYPERPARAMETERS: dict[str, Any] = {
    "hidden": 128,  # neurones par couche cachée
    "layers": 2,  # couches cachées (0 = modèle linéaire : ce n'est plus du deep learning)
    "dropout": 0.1,
    "lr": 1e-3,  # pas d'apprentissage d'AdamW
    "weight_decay": 1e-4,  # régularisation L2 découplée (AdamW)
    "batch_size": 256,
    "max_epochs": 100,  # plafond : l'arrêt anticipé s'arrête en général avant
    "patience": 8,  # époques sans progrès sur l'arrêt anticipé avant d'arrêter
    "holdout_weeks": 4,  # arrêt anticipé sur les dernières semaines avant fit_cutoff (0 = aucun)
    "loss_weighting": "scale",  # "scale" : erreur en vélos/h ; "none" : erreur relative au niveau
    # Seuil d'heures mesurées sur la semaine visible (apprentissage et prévision), D-18.
    "min_observed_hours": MIN_OBSERVED_HOURS,
    # Masquage à l'apprentissage (EXP-E2-05) : 0 = désactivé, comportement d'avant.
    "mask_prob": 0.0,  # part des exemples d'apprentissage masqués, retirée à chaque époque
    "mask_min_hours": 24,  # longueur minimale du bloc effacé
    "mask_max_hours": 144,  # longueur maximale du bloc effacé
}
LOSS_WEIGHTINGS = ("scale", "none")
EXTREME_TARGET_RATIO = INPUT_CLIP  # cible > 10 fois le niveau de sa fenêtre : comptée au bilan
PREDICT_CHUNK = 65_536  # exemples par passage dans le réseau (mémoire bornée)

# Codes de refus de predict_mlp : stables, lus par predict.py (repli), E4 et E5.
REFUSE_NOT_MIDNIGHT = "mlp_origin_not_midnight"  # la sortie k doit être la k-ième heure du jour
REFUSE_BEFORE_CUTOFF = "mlp_origin_before_fit_cutoff"  # journée vue pendant l'apprentissage
REFUSE_NO_HISTORY = "mlp_no_history"  # aucune mesure publiée pour ce compteur
REFUSE_CONTEXT = "mlp_context_missing"  # contexte utilisé par le réseau inconnu à l'origine
REFUSE_SPARSE = "mlp_window_too_sparse"  # moins de min_observed_hours (84 par défaut) mesurées
REFUSE_LOW_LEVEL = "mlp_level_too_low"  # niveau < 1 vélo/h : normalisation instable
REFUSE_NON_FINITE = "mlp_non_finite_output"  # sortie non finie (ne devrait jamais arriver)


@dataclass
class Windows:
    """Les exemples du MLP, prêts à être donnés au réseau (un par compteur × origine).

    Formes, avec n exemples et k colonnes de calendrier (calendar_columns) :
      series       (n, 168)  float32 : heures visibles / niveau, plafonnées, 0 si manquante
      mask         (n, 168)  float32 : 1 si l'heure est mesurée, 0 sinon
      calendar     (n, k)    float32 : la journée (une fois), puis la météo heure par heure
      target       (n, 24)   float32 : vraies valeurs / niveau (0 si inconnue)
      target_mask  (n, 24)   bool    : la cible est une vraie mesure (is_scoreable)
      scale        (n,)      float32 : niveau (moyenne des heures mesurées de la fenêtre)
      usable       (n,)      bool    : assez de mesures et niveau assez grand pour prévoir
      context_missing (n,)   bool    : une valeur de contexte lue par le réseau est inconnue
                                       à l'origine (remplacée par 0 dans calendar) - MOD-008
      publication_lag_hours  int     : délai de publication avec lequel la fenêtre est coupée
    """

    counter_id: np.ndarray
    origin: pd.DatetimeIndex
    series: np.ndarray
    mask: np.ndarray
    calendar: np.ndarray
    target: np.ndarray
    target_mask: np.ndarray
    scale: np.ndarray
    usable: np.ndarray
    calendar_columns: list[str]
    context_missing: np.ndarray | None = None
    publication_lag_hours: int | None = None
    min_observed_hours: int = MIN_OBSERVED_HOURS  # seuil utilisé pour usable et les refus

    def __len__(self) -> int:
        return len(self.scale)

    @property
    def X(self) -> np.ndarray:
        """Entrée complète du réseau : série, masques, calendrier, côte à côte."""
        return np.hstack([self.series, self.mask, self.calendar]).astype(np.float32)

    @property
    def n_inputs(self) -> int:
        return self.series.shape[1] + self.mask.shape[1] + self.calendar.shape[1]


def calendar_columns(use_context: bool) -> list[str]:
    """Noms des colonnes du bloc calendrier, dans l'ordre exact de Windows.calendar.

    Sans contexte : 8 colonnes (dow_0..dow_6, dst_shift).
    Avec contexte : + is_holiday, is_school_holiday, is_strike (une fois pour la journée)
    + temp_prev_h01..h24, rain_prev_h01..h24, wind_prev_h01..h24 (heure par heure) = 83.
    """
    groups = F.resolve_context_groups(use_context)
    columns = list(DAY_BASE)
    for group in DAY_CONTEXT_GROUPS:
        if group in groups:
            columns += F.CONTEXT_GROUPS[group]
    for group in HOURLY_CONTEXT_GROUPS:
        if group in groups:
            for variable in F.CONTEXT_GROUPS[group]:
                columns += [f"{variable}_h{h:02d}" for h in range(1, HORIZON_HOURS + 1)]
    return columns


def build_windows(
    counts: pd.DataFrame,
    origins: pd.DataFrame,
    context: pd.DataFrame | None = None,
    *,
    use_context: bool = True,
    publication_lag_hours: int = DEFAULT_LAG_HOURS,
    min_observed_hours: int = MIN_OBSERVED_HOURS,
) -> Windows:
    """Construire un exemple par ligne de origins (colonnes counter_id, origin).

    counts : counter_id, timestamp (UTC), count (entrée : mesures seules, voir
    train.load_training_data), count_raw et is_scoreable (pour les cibles).
    min_observed_hours : heures mesurées minimales pour qu'un exemple soit utilisable
    (84 par défaut, D-18) ; rangé dans Windows pour que refusal_reasons applique le même.
    Fenêtre d'un exemple : les 168 heures qui finissent à origin - délai, donc
    publiées à l'origine. Rien après n'est lu en entrée.
    Cibles : les 24 heures à partir de l'origine (leurs valeurs ne servent qu'à apprendre
    ou à mesurer l'erreur, jamais d'entrée).
    """
    for column in ("counter_id", "timestamp", "count", "count_raw", "is_scoreable"):
        if column not in counts.columns:
            raise ValueError(f"counts : colonne {column!r} absente")
    lag = int(publication_lag_hours)
    origin_h = F._to_hours(origins["origin"], "origin")
    wanted = origins["counter_id"].astype(str).to_numpy()

    # 1. Une grille dense par compteur : ligne = compteur, colonne = heure depuis h0.
    ids, values, targets, h0 = _dense_grids(counts, sorted(set(wanted)))
    row = np.searchsorted(ids, wanted)

    # 2. Fenêtre visible et heures cibles de chaque exemple (indices dans la grille).
    win_h = origin_h[:, None] - lag - WINDOW_HOURS + np.arange(WINDOW_HOURS)[None, :]
    tgt_h = origin_h[:, None] + np.arange(HORIZON_HOURS)[None, :]
    window = _take(values, row, win_h - h0)
    truth = _take(targets, row, tgt_h - h0)

    # 3. Niveau de la fenêtre et normalisation.
    observed = ~np.isnan(window)
    n_obs = observed.sum(axis=1)
    total = np.where(observed, window, 0.0).sum(axis=1)
    scale = total / np.maximum(n_obs, 1)  # moyenne des heures mesurées (0 si aucune)
    usable = (n_obs >= min_observed_hours) & (scale >= MIN_SCALE)
    safe = np.where(usable, scale, 1.0)[:, None]
    series = np.clip(np.nan_to_num(window / safe, nan=0.0), 0.0, INPUT_CLIP)
    target_mask = ~np.isnan(truth)
    target = np.nan_to_num(truth / safe, nan=0.0)

    # 4. La journée à prévoir et, si use_context, la météo prévue heure par heure.
    columns = calendar_columns(use_context)
    calendar, context_missing = _calendar_block(tgt_h, origin_h, context, use_context, columns)

    return Windows(
        counter_id=wanted,
        origin=pd.DatetimeIndex(pd.to_datetime(origin_h * F.HOUR_NS, utc=True)),
        series=series.astype(np.float32),
        mask=observed.astype(np.float32),
        calendar=calendar.astype(np.float32),
        target=target.astype(np.float32),
        target_mask=target_mask,
        scale=np.where(usable, scale, np.nan).astype(np.float32),
        usable=usable,
        calendar_columns=columns,
        context_missing=context_missing,
        publication_lag_hours=lag,
        min_observed_hours=int(min_observed_hours),
    )


def _dense_grids(
    counts: pd.DataFrame, counter_ids: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Entrées (count) et cibles (count_raw si is_scoreable) en tableaux compteur × heure.

    Une heure absente de counts reste NaN : elle compte comme manquante, jamais comme zéro.
    """
    sub = counts.loc[counts["counter_id"].astype(str).isin(counter_ids)]
    missing = set(counter_ids) - set(sub["counter_id"].astype(str))
    if missing:
        raise ValueError(f"compteurs absents de counts : {sorted(missing)}")
    hours = F._to_hours(sub["timestamp"], "timestamp")
    h0, h1 = int(hours.min()), int(hours.max())
    ids = np.array(sorted(counter_ids))
    r = np.searchsorted(ids, sub["counter_id"].astype(str).to_numpy())
    c = hours - h0
    values = np.full((len(ids), h1 - h0 + 1), np.nan, dtype=np.float32)
    targets = np.full_like(values, np.nan)
    values[r, c] = pd.to_numeric(sub["count"], errors="coerce").to_numpy(dtype=np.float32)
    scoreable = F._as_bool(sub["is_scoreable"])
    raw = pd.to_numeric(sub["count_raw"], errors="coerce").to_numpy(dtype=np.float32)
    targets[r, c] = np.where(scoreable, raw, np.nan)
    return ids, values, targets, h0


def _take(grid: np.ndarray, row: np.ndarray, col: np.ndarray) -> np.ndarray:
    """grid[row, col] ligne par ligne ; NaN hors de la période couverte."""
    inside = (col >= 0) & (col < grid.shape[1])
    out = grid[row[:, None], np.clip(col, 0, grid.shape[1] - 1)]
    return np.where(inside, out, np.nan)


def _calendar_block(
    tgt_h: np.ndarray,
    origin_h: np.ndarray,
    context: pd.DataFrame | None,
    use_context: bool,
    columns: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Tableau (n, k) dans l'ordre de calendar_columns, et indicateur de contexte inconnu.

    1. La journée, une seule fois (elle est la même pour les 24 heures) : jour de la
       semaine en 7 cases, dst_shift, puis fériés, vacances, grève si use_context.
    2. La météo prévue, heure par heure : 24 températures, 24 pluies, 24 vents.
    Une valeur de contexte inconnue à l'origine (ligne absente ou publiée trop tard) est
    mise à 0 dans le tableau et signalée dans le second résultat (MOD-008) : sans ce signal,
    une météo manquante passerait pour « 0 °C, pas de pluie, pas de vent ».
    """
    n = len(origin_h)
    first = tgt_h[:, 0]  # première heure cible = minuit à Paris : elle date la journée
    dow = F._calendar_core(first)["dow_local"]
    parts = [(dow == d).astype(float)[:, None] for d in range(7)]
    parts.append(_dst_shift(first)[:, None])
    missing = np.zeros(n, dtype=bool)

    groups = F.resolve_context_groups(use_context)
    if groups:
        tables = F._prepare_context(context, groups)
        origins_flat = np.repeat(origin_h, HORIZON_HOURS)
        ctx = F._context_core(tables, origins_flat, tgt_h.ravel(), groups)  # NaN si trop tard
        for group in DAY_CONTEXT_GROUPS:
            if group in groups:
                for variable in F.CONTEXT_GROUPS[group]:
                    day = ctx[variable].reshape(n, HORIZON_HOURS)[:, 0]
                    missing |= np.isnan(day)
                    parts.append(np.nan_to_num(day, nan=0.0)[:, None])
        for group in HOURLY_CONTEXT_GROUPS:
            if group in groups:
                for variable in F.CONTEXT_GROUPS[group]:
                    hourly = ctx[variable].reshape(n, HORIZON_HOURS)
                    missing |= np.isnan(hourly).any(axis=1)
                    hourly = np.nan_to_num(hourly, nan=0.0)
                    parts.append(hourly / WEATHER_SCALE.get(variable, 1.0))
    block = np.hstack(parts)
    if block.shape[1] != len(columns):
        raise AssertionError("calendrier : nombre de colonnes inattendu")
    return block, missing


def _dst_shift(first_h: np.ndarray) -> np.ndarray:
    """Longueur du jour local moins 24 h : -1 (heure d'été), +1 (heure d'hiver), 0 sinon."""
    local = pd.DatetimeIndex(first_h * F.HOUR_NS, tz="UTC").tz_convert(F.LOCAL_TZ)
    day = local.tz_localize(None).normalize()
    start = day.tz_localize(F.LOCAL_TZ)
    end = (day + pd.Timedelta(days=1)).tz_localize(F.LOCAL_TZ)
    return ((end - start) / pd.Timedelta(hours=1)).to_numpy() - 24


# --------------------------------------------------------------------------- réseau


class MLPNet(nn.Module):
    """Perceptron multicouche : n_inputs -> [hidden, ReLU, dropout] x layers -> 24 sorties.

    Les réglages qui fixent la forme du réseau sont gardés dans self.arch : ils sont
    sauvegardés avec les poids pour pouvoir reconstruire exactement le même réseau.
    input_layout et training_report sont renseignés par fit_mlp ou load_mlp (MOD-008) ;
    forward ne les lit jamais.
    """

    def __init__(
        self,
        n_inputs: int,
        hidden: int = 128,
        layers: int = 2,
        dropout: float = 0.1,
        n_outputs: int = HORIZON_HOURS,
    ) -> None:
        super().__init__()
        self.arch = {
            "n_inputs": int(n_inputs),
            "hidden": int(hidden),
            "layers": int(layers),
            "dropout": float(dropout),
            "n_outputs": int(n_outputs),
        }
        blocks: list[nn.Module] = []
        width = n_inputs
        for _ in range(layers):
            blocks += [nn.Linear(width, hidden), nn.ReLU(), nn.Dropout(dropout)]
            width = hidden
        blocks.append(nn.Linear(width, n_outputs))
        self.layers = nn.Sequential(*blocks)
        self.input_layout: dict[str, Any] | None = None  # disposition des entrées apprises
        self.training_report: dict[str, Any] | None = None  # bilan de fit_mlp

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


# --------------------------------------------------------------------------- apprentissage


def mlp_hyperparameters(**overrides: Any) -> dict[str, Any]:
    """Réglages complets de fit_mlp : DEFAULT_HYPERPARAMETERS remplacés par overrides.

    À passer tels quels dans TrainConfig.hyperparameters : metadata.json et le nom du
    modèle portent alors tous les réglages réellement utilisés, pas seulement ceux qu'on a
    changés. Refuse une clé inconnue (faute de frappe) ou une valeur hors domaine.
    """
    unknown = set(overrides) - set(DEFAULT_HYPERPARAMETERS)
    if unknown:
        raise ValueError(
            f"réglages MLP inconnus : {sorted(unknown)} ; connus : {sorted(DEFAULT_HYPERPARAMETERS)}"
        )
    hp = {**DEFAULT_HYPERPARAMETERS, **overrides}
    for key, minimum in (
        ("hidden", 1),
        ("layers", 0),
        ("batch_size", 1),
        ("max_epochs", 1),
        ("patience", 1),
        ("holdout_weeks", 0),
        ("min_observed_hours", 1),
        ("mask_min_hours", 1),
        ("mask_max_hours", 1),
    ):
        value = hp[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"réglage {key}={value!r} : entier >= {minimum} attendu")
    for key, low, high, strict in (
        ("dropout", 0.0, 1.0, False),
        ("lr", 0.0, None, True),
        ("weight_decay", 0.0, None, False),
        ("mask_prob", 0.0, 1.0, False),
    ):
        value = hp[key]
        ok = not isinstance(value, bool) and isinstance(value, int | float)
        ok = ok and np.isfinite(value) and value >= low and not (strict and value == low)
        if not ok or (high is not None and value >= high):
            sign = ">" if strict else ">="
            bounds = f"dans [{low}, {high})" if high is not None else f"{sign} {low}"
            raise ValueError(f"réglage {key}={value!r} : nombre {bounds} attendu")
        hp[key] = float(value)  # 1 et 1.0 donnent la même empreinte de configuration
    for key in ("min_observed_hours", "mask_max_hours"):
        if hp[key] > WINDOW_HOURS:
            raise ValueError(f"réglage {key}={hp[key]!r} : au plus {WINDOW_HOURS} h (fenêtre)")
    if hp["mask_min_hours"] > hp["mask_max_hours"]:
        raise ValueError("mask_min_hours doit être <= mask_max_hours")
    if hp["loss_weighting"] not in LOSS_WEIGHTINGS:
        raise ValueError(f"loss_weighting={hp['loss_weighting']!r} : {LOSS_WEIGHTINGS} attendus")
    return {key: hp[key] for key in DEFAULT_HYPERPARAMETERS}


def mask_windows(
    windows: Windows,
    rows: np.ndarray,
    rng: np.random.Generator,
    *,
    prob: float,
    min_hours: int,
    max_hours: int,
) -> Windows:
    """Copie de windows où une part prob des lignes rows perd un bloc continu d'heures.

    Pour chaque ligne tirée : un bloc de min_hours à max_hours heures, à une position tirée
    au hasard dans la semaine visible, passe à « non mesuré » (masque 0, série 0, jamais une
    valeur 0 prise pour une mesure). Le niveau est recalculé sur les heures restantes, puis
    la série et les cibles sont renormalisées par ce niveau, comme le ferait build_windows
    sur une semaine réellement trouée. Une ligne qui deviendrait inutilisable (moins de
    windows.min_observed_hours mesurées, ou niveau < MIN_SCALE) n'est pas masquée.
    Les cibles réelles (en vélos/h) et leur masque ne changent pas. windows n'est pas modifié.
    Approximation : une heure plafonnée à INPUT_CLIP fois le niveau le reste après masquage.
    """
    out = dataclasses.replace(
        windows,
        series=windows.series.copy(),
        mask=windows.mask.copy(),
        target=windows.target.copy(),
        scale=windows.scale.copy(),
    )
    rows = np.asarray(rows, dtype=np.int64)
    if prob <= 0 or rows.size == 0:
        return out
    chosen = rows[rng.random(rows.size) < prob]
    if chosen.size == 0:
        return out
    lengths = rng.integers(min_hours, max_hours + 1, size=chosen.size)
    starts = rng.integers(0, WINDOW_HOURS - lengths + 1)
    hours = np.arange(WINDOW_HOURS)[None, :]
    block = (hours >= starts[:, None]) & (hours < (starts + lengths)[:, None])

    old_scale = windows.scale[chosen].astype(np.float64)
    raw = windows.series[chosen].astype(np.float64) * old_scale[:, None]  # vélos/h
    kept = (windows.mask[chosen] == 1) & ~block
    n_obs = kept.sum(axis=1)
    new_scale = np.where(kept, raw, 0.0).sum(axis=1) / np.maximum(n_obs, 1)
    ok = (n_obs >= windows.min_observed_hours) & (new_scale >= MIN_SCALE)
    rows_ok, kept, raw, new_scale = chosen[ok], kept[ok], raw[ok], new_scale[ok]
    out.mask[rows_ok] = kept.astype(np.float32)
    series = np.where(kept, raw / new_scale[:, None], 0.0)
    out.series[rows_ok] = np.clip(series, 0.0, INPUT_CLIP).astype(np.float32)
    truth = windows.target[rows_ok].astype(np.float64) * old_scale[ok][:, None]
    out.target[rows_ok] = (truth / new_scale[:, None]).astype(np.float32)
    out.scale[rows_ok] = new_scale.astype(np.float32)
    return out


def fit_mlp(
    config: train.TrainConfig,
    counts: pd.DataFrame,
    context: pd.DataFrame | None,
    origins: pd.DataFrame,
) -> MLPNet:
    """Apprendre le MLP sur les origines fixées par train.fit (backend « mlp »).

    1. Contrôles avant toute lecture de cible : chaque origine est à minuit (Paris), sans
       doublon, et ses 24 cibles sont publiées à fit_cutoff (origine + 24 h + latence) ;
       sinon ValueError, car apprendre dessus serait une fuite.
    2. build_windows avec la latence de la configuration (celle de training_origins).
    3. Exemples gardés : fenêtre utilisable, contexte complet, au moins une vraie cible.
    4. Arrêt anticipé : les exemples des holdout_weeks dernières semaines avant fit_cutoff
       (dates locales) ne servent qu'à choisir la meilleure époque ; le réseau rendu est
       celui de cette époque, sans réapprentissage sur ces semaines.
    5. Perte L1 masquée (target_mask), pondérée par le niveau si loss_weighting="scale".
    Le bilan (effectifs, époques, pertes, contrôle sur l'arrêt anticipé) est rangé dans
    net.training_report et sauvegardé avec les poids.
    """
    started = time.perf_counter()
    hp = mlp_hyperparameters(**config.hyperparameters)
    lag = F._default_lag()
    fit_cutoff = F._utc(config.fit_cutoff, "fit_cutoff")
    use_context = bool(config.use_context)
    if use_context and (context is None or len(context) == 0):
        raise ValueError(
            "use_context=True sans contexte : fournir context.csv ou apprendre avec "
            "use_context=False (sinon le réseau apprendrait une météo à 0)"
        )
    _check_training_origins(origins, fit_cutoff, lag)

    windows = build_windows(
        counts,
        origins,
        context,
        use_context=use_context,
        publication_lag_hours=lag,
        min_observed_hours=hp["min_observed_hours"],
    )
    context_missing = windows.context_missing
    has_target = windows.target_mask.any(axis=1)
    keep = windows.usable & ~context_missing & has_target
    holdout_start = _holdout_start(fit_cutoff, hp["holdout_weeks"])
    if holdout_start is None:
        in_holdout = np.zeros(len(windows), dtype=bool)
    else:
        in_holdout = np.asarray(windows.origin >= holdout_start)
    train_rows = np.flatnonzero(keep & ~in_holdout)
    hold_rows = np.flatnonzero(keep & in_holdout)
    if train_rows.size == 0:
        raise ValueError("aucun exemple d'apprentissage utilisable avant l'arrêt anticipé")
    if holdout_start is not None and hold_rows.size == 0:
        raise ValueError(
            f"aucun exemple dans les {hp['holdout_weeks']} semaines avant fit_cutoff : "
            "arrêt anticipé impossible (holdout_weeks=0 pour apprendre sans)"
        )

    X = windows.X  # calculé une fois : la propriété recopie les trois blocs à chaque appel
    weights = windows.scale if hp["loss_weighting"] == "scale" else np.ones(len(windows))
    train_set = _tensors(X, windows, weights, train_rows)
    hold_set = _tensors(X, windows, weights, hold_rows) if hold_rows.size else None

    history: list[dict[str, Any]] = []
    best_loss, best_epoch, best_state, waited = np.inf, 0, None, 0
    with torch.random.fork_rng(devices=[]):  # graine locale : l'état global est rendu après
        torch.manual_seed(config.seed)
        rng = np.random.default_rng(config.seed)
        # Générateur à part pour les masques : sans masquage, l'ordre des lots (rng) et donc
        # les poids restent exactement ceux d'avant EXP-E2-05.
        mask_rng = np.random.default_rng([config.seed, 1])
        masked_per_epoch: list[int] = []
        net = MLPNet(
            windows.n_inputs, hidden=hp["hidden"], layers=hp["layers"], dropout=hp["dropout"]
        )
        optimizer = torch.optim.AdamW(
            net.parameters(), lr=hp["lr"], weight_decay=hp["weight_decay"]
        )
        x_train, t_train, m_train, w_train = train_set
        for epoch in range(1, hp["max_epochs"] + 1):
            net.train()
            if hp["mask_prob"] > 0:  # nouveau tirage à chaque époque, apprentissage seulement
                masked = mask_windows(
                    windows,
                    train_rows,
                    mask_rng,
                    prob=hp["mask_prob"],
                    min_hours=hp["mask_min_hours"],
                    max_hours=hp["mask_max_hours"],
                )
                masked_weights = (
                    masked.scale if hp["loss_weighting"] == "scale" else np.ones(len(masked))
                )
                x_train, t_train, m_train, w_train = _tensors(
                    masked.X, masked, masked_weights, train_rows
                )
                changed = (masked.mask[train_rows] != windows.mask[train_rows]).any(axis=1)
                masked_per_epoch.append(int(changed.sum()))
            order = torch.from_numpy(rng.permutation(len(x_train)))
            loss_sum, weight_sum = 0.0, 0.0
            for start in range(0, len(order), hp["batch_size"]):
                batch = order[start : start + hp["batch_size"]]
                total, weight = _masked_l1(
                    net(x_train[batch]), t_train[batch], m_train[batch], w_train[batch]
                )
                loss = total / weight
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
                loss_sum += float(total.detach())
                weight_sum += float(weight)
            hold_loss = _objective(net, hold_set) if hold_set is not None else None
            history.append(
                {"epoch": epoch, "train_loss": loss_sum / weight_sum, "holdout_loss": hold_loss}
            )
            if hold_loss is None:
                continue
            if hold_loss < best_loss:
                best_loss, best_epoch, waited = hold_loss, epoch, 0
                best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            else:
                waited += 1
                if waited >= hp["patience"]:
                    break
        if best_state is not None:
            net.load_state_dict(best_state)
    net.eval()

    report = _training_report(
        config=config,
        hp=hp,
        lag=lag,
        windows=windows,
        keep=keep,
        train_rows=train_rows,
        hold_rows=hold_rows,
        holdout_start=holdout_start,
        history=history,
        best_epoch=best_epoch if hold_set is not None else len(history),
        net=net,
        X=X,
    )
    if masked_per_epoch:
        report["masking"] = {
            "train_examples": int(train_rows.size),
            "masked_per_epoch_mean": round(float(np.mean(masked_per_epoch)), 1),
            "masked_share_mean": round(float(np.mean(masked_per_epoch)) / train_rows.size, 4),
        }
    report["fit_seconds"] = round(time.perf_counter() - started, 3)
    net.input_layout = _input_layout(use_context, lag)
    net.training_report = report
    return net


def _check_training_origins(origins: pd.DataFrame, fit_cutoff: pd.Timestamp, lag: int) -> None:
    """Refuser des origines qui rendraient l'apprentissage incorrect (avant toute cible)."""
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
        raise ValueError(
            "origine hors minuit (Europe/Paris) : la sortie k du MLP est la k-ième heure du jour"
        )
    keys = pd.DataFrame({"counter_id": origins["counter_id"].astype(str), "origin_h": origin_h})
    if keys.duplicated().any():
        raise ValueError("origine en double : l'exemple compterait deux fois dans la perte")


def _holdout_start(fit_cutoff: pd.Timestamp, weeks: int) -> pd.Timestamp | None:
    """Minuit (Paris) qui ouvre les `weeks` dernières semaines avant fit_cutoff ; None si 0.

    Calcul en dates locales : un changement d'heure dans l'intervalle ne décale pas la limite.
    """
    if weeks == 0:
        return None
    day = fit_cutoff.tz_convert(F.LOCAL_TZ).tz_localize(None).normalize()
    return (day - pd.Timedelta(days=7 * weeks)).tz_localize(F.LOCAL_TZ).tz_convert("UTC")


def _tensors(
    X: np.ndarray, windows: Windows, weights: np.ndarray, rows: np.ndarray
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Entrées, cibles, masque des vraies cibles et poids des exemples choisis."""
    return (
        torch.from_numpy(np.ascontiguousarray(X[rows], dtype=np.float32)),
        torch.from_numpy(np.ascontiguousarray(windows.target[rows], dtype=np.float32)),
        torch.from_numpy(windows.target_mask[rows].astype(np.float32)),
        torch.from_numpy(np.asarray(weights, dtype=np.float32)[rows]),
    )


def _masked_l1(
    pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, weight: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Somme des erreurs absolues pondérées sur les vraies cibles, et somme des poids.

    pred, target, mask : (b, 24) ; weight : (b,), le niveau de chaque fenêtre (ou 1).
    Une cible masquée (non mesurée) ne compte ni dans l'erreur ni dans les poids. Avec
    weight = niveau, |sortie - cible| x niveau est l'erreur absolue en vélos/h. Propriété
    de la L1 : le gradient ne dépend que du signe de l'erreur, si bien qu'une cible
    extrême ne pèse pas plus qu'une autre cible du même côté de la prévision.
    """
    cell_weight = mask * weight[:, None]
    return ((pred - target).abs() * cell_weight).sum(), cell_weight.sum()


def _objective(net: MLPNet, tensors: tuple[torch.Tensor, ...]) -> float:
    """Perte d'apprentissage (_masked_l1) sur un jeu entier, sans gradient, en float64."""
    x, target, mask, weight = tensors
    was_training = net.training
    net.eval()
    total, weight_sum = 0.0, 0.0
    with torch.no_grad():
        for start in range(0, len(x), PREDICT_CHUNK):
            part = slice(start, start + PREDICT_CHUNK)
            errors, weights = _masked_l1(
                net(x[part]).double(),
                target[part].double(),
                mask[part].double(),
                weight[part].double(),
            )
            total += float(errors)
            weight_sum += float(weights)
    net.train(was_training)
    return total / weight_sum


def _forward(net: MLPNet, X: np.ndarray) -> np.ndarray:
    """Sorties normalisées du réseau (mode évaluation, par morceaux) ; mode d'origine rendu."""
    was_training = net.training
    net.eval()
    parts = []
    with torch.no_grad():
        for start in range(0, len(X), PREDICT_CHUNK):
            chunk = np.ascontiguousarray(X[start : start + PREDICT_CHUNK], dtype=np.float32)
            parts.append(net(torch.from_numpy(chunk)).numpy().astype(np.float64))
    net.train(was_training)
    return np.concatenate(parts) if parts else np.empty((0, HORIZON_HOURS))


def _training_report(
    *,
    config: train.TrainConfig,
    hp: dict[str, Any],
    lag: int,
    windows: Windows,
    keep: np.ndarray,
    train_rows: np.ndarray,
    hold_rows: np.ndarray,
    holdout_start: pd.Timestamp | None,
    history: list[dict[str, Any]],
    best_epoch: int,
    net: MLPNet,
    X: np.ndarray,
) -> dict[str, Any]:
    """Bilan lisible sans le code : effectifs, exclusions, époques, contrôle d'arrêt anticipé.

    Uniquement des types simples (dictionnaires, listes, nombres, textes, None) : il est
    rangé dans weights.pt, relu avec weights_only=True, et recopié en JSON par main().
    """
    usable = windows.usable
    context_missing = windows.context_missing
    has_target = windows.target_mask.any(axis=1)
    kept_max = np.where(windows.target_mask[keep], windows.target[keep], -np.inf).max(axis=1)

    def stamps(rows: np.ndarray) -> list[str] | None:
        if rows.size == 0:
            return None
        chosen = windows.origin[rows]
        return [chosen.min().isoformat(), chosen.max().isoformat()]

    return {
        "method": METHOD,
        "file_format": FILE_FORMAT,
        "input_version": INPUT_VERSION,
        "seed": int(config.seed),
        "hyperparameters": hp,
        "use_context": bool(config.use_context),
        "publication_lag_hours": int(lag),
        "fit_cutoff": F._utc(config.fit_cutoff, "fit_cutoff").isoformat(),
        "holdout_start": None if holdout_start is None else holdout_start.isoformat(),
        "examples": {
            "total": len(windows),
            "excluded_not_usable": int((~usable).sum()),
            "excluded_context_missing": int((usable & context_missing).sum()),
            "excluded_no_target": int((usable & ~context_missing & ~has_target).sum()),
            "train": int(train_rows.size),
            "holdout": int(hold_rows.size),
            "train_target_cells": int(windows.target_mask[train_rows].sum()),
            "holdout_target_cells": int(windows.target_mask[hold_rows].sum()),
            "counters": len(set(windows.counter_id[keep])),
        },
        "origins": {"train": stamps(train_rows), "holdout": stamps(hold_rows)},
        "extreme_targets": {
            "ratio_threshold": EXTREME_TARGET_RATIO,
            "examples_share": float((kept_max > EXTREME_TARGET_RATIO).mean()),
            "max_normalized_target": float(kept_max.max()),
        },
        "epochs_run": len(history),
        "best_epoch": int(best_epoch),
        "stopped_early": len(history) < hp["max_epochs"],
        "history": history,
        "holdout_metrics": _holdout_metrics(net, windows, X, hold_rows, lag),
        "n_parameters": int(sum(p.numel() for p in net.parameters())),
        "torch_version": str(torch.__version__),  # TorchVersion refusé par weights_only
        "torch_threads": int(torch.get_num_threads()),
    }


def _holdout_metrics(
    net: MLPNet, windows: Windows, X: np.ndarray, rows: np.ndarray, lag: int
) -> dict[str, Any] | None:
    """Contrôle sur l'arrêt anticipé (période d'apprentissage, avant fit_cutoff).

    MAE en vélos/h du réseau, puis réseau et référence hebdomadaire y(t - 168 h) sur les
    mêmes cellules : cible mesurée et valeur d'il y a une semaine mesurée dans la fenêtre
    (indice lag + k) et non plafonnée. Contrôle technique : ce n'est pas la comparaison
    officielle des méthodes (validation, scores d'E4).
    """
    if rows.size == 0:
        return None
    scale = windows.scale[rows].astype(np.float64)[:, None]
    pred = np.clip(_forward(net, X[rows]) * scale, 0.0, None)
    truth = windows.target[rows].astype(np.float64) * scale
    scored = windows.target_mask[rows]
    counters = windows.counter_id[rows]
    metrics: dict[str, Any] = {
        "mlp": _mae(pred, truth, scored, counters),
        "compared_cells": 0,
        "mlp_on_compared": None,
        "weekly_naive_on_compared": None,
    }
    if lag + HORIZON_HOURS <= WINDOW_HOURS:
        part = slice(lag, lag + HORIZON_HOURS)  # y(t - 168 h) dans la fenêtre visible
        naive_norm = windows.series[rows, part].astype(np.float64)
        naive_ok = (windows.mask[rows, part] == 1) & (naive_norm < INPUT_CLIP)
        both = scored & naive_ok
        metrics["compared_cells"] = int(both.sum())
        metrics["mlp_on_compared"] = _mae(pred, truth, both, counters)
        metrics["weekly_naive_on_compared"] = _mae(naive_norm * scale, truth, both, counters)
    return metrics


def _mae(pred: np.ndarray, truth: np.ndarray, cells: np.ndarray, counters: np.ndarray) -> dict:
    """MAE sur les cellules choisies : toutes ensemble (micro) et par compteur puis moyenne."""
    errors = np.abs(pred - truth)
    per_counter = []
    for counter in np.unique(counters):
        chosen = cells & (counters == counter)[:, None]
        if chosen.any():
            per_counter.append(float(errors[chosen].mean()))
    n_cells = int(cells.sum())
    return {
        "mae_micro": float(errors[cells].mean()) if n_cells else None,
        "mae_macro": float(np.mean(per_counter)) if per_counter else None,
        "cells": n_cells,
        "counters": len(per_counter),
    }


# --------------------------------------------------------------------------- prévision


@dataclass(frozen=True)
class MLPForecast:
    """Résultat de predict_mlp : 24 valeurs en vélos/h, ou un refus motivé (values=None)."""

    values: np.ndarray | None  # (24,) >= 0, horizons 1 à 24 dans l'ordre
    reason: str | None  # code REFUSE_* en cas de refus, None sinon
    scale: float | None = None  # niveau de la fenêtre (vélos/h)
    observed_hours: int = 0  # heures mesurées dans la semaine visible

    @property
    def ok(self) -> bool:
        return self.values is not None


def refusal_reasons(windows: Windows) -> np.ndarray:
    """Code de refus de chaque exemple (None s'il peut être prévu), comme predict_mlp.

    Seule source des refus liés aux données de la fenêtre, utilisée par predict_mlp et
    predict_windows : un calcul de couverture en bloc donne donc les mêmes motifs que le
    calcul cas par cas. Ordre : contexte inconnu, puis fenêtre trop vide, puis niveau trop bas.
    """
    observed = windows.mask.sum(axis=1)
    reasons = np.full(len(windows), None, dtype=object)
    threshold = windows.min_observed_hours
    reasons[~windows.usable & (observed >= threshold)] = REFUSE_LOW_LEVEL
    reasons[~windows.usable & (observed < threshold)] = REFUSE_SPARSE
    if windows.context_missing is not None:
        reasons[windows.context_missing] = REFUSE_CONTEXT
    return reasons


def predict_windows(net: MLPNet, windows: Windows) -> np.ndarray:
    """Prévisions (n, 24) en vélos/h, >= 0 ; ligne NaN si l'exemple est refusé.

    Même calcul que predict_mlp pour beaucoup d'exemples à la fois (expériences,
    contrôles). Exemple refusé : voir refusal_reasons. Refuse des fenêtres rangées
    autrement que les entrées du réseau (contexte, latence).
    """
    layout = _layout_of(net)
    if (
        windows.calendar_columns != layout["calendar_columns"]
        or windows.n_inputs != net.arch["n_inputs"]
        or windows.publication_lag_hours not in (None, layout["publication_lag_hours"])
    ):
        raise ValueError("fenêtres rangées autrement que les entrées apprises (contexte, latence)")
    out = np.full((len(windows), HORIZON_HOURS), np.nan)
    rows = np.flatnonzero(pd.isna(refusal_reasons(windows)))
    if rows.size:
        scale = windows.scale[rows].astype(np.float64)[:, None]
        out[rows] = np.clip(_forward(net, windows.X[rows]) * scale, 0.0, None)
    return out


def predict_mlp(
    net: MLPNet,
    inputs: ForecastInputs,
    *,
    fit_cutoff: pd.Timestamp | None = None,
    min_observed_hours: int | None = None,
) -> MLPForecast:
    """Prévoir les 24 heures d'un cas, ou refuser avec une raison (repli : l'appelant).

    - inputs : predict.build_inputs (historique et contexte connus à l'origine) ;
      l'historique est refiltré ici sur information_cutoff et sur le support local
      éventuel du cas, par sécurité ;
    - min_observed_hours : seuil d'heures mesurées ; par défaut celui appris par le réseau
      (84 pour un réseau d'avant EXP-E2-05). Le donner sert à évaluer un réseau avec un
      autre seuil (bras A′ d'EXP-E2-05), sans le réapprendre ;
    - fit_cutoff : coupure du modèle. Une origine antérieure est refusée : le modèle a
      appris sur ces journées. Un réseau entraîné la connaît (son bilan) : elle est
      vérifiée même si l'appelant l'oublie ; si les deux sont données, la plus tardive vaut ;
    - la latence du cas (origin - information_cutoff) doit être celle de l'apprentissage,
      sinon ValueError : la semaine visible ne serait plus alignée sur celle apprise.
    Les cibles ne sont jamais transmises au réseau (count_raw vide, is_scoreable faux).
    """
    layout = _layout_of(net)
    case = inputs.case
    origin = F._utc(case.origin, "case.origin")
    cutoff = F._utc(inputs.information_cutoff, "information_cutoff")
    lag = layout["publication_lag_hours"]
    if origin - cutoff != pd.Timedelta(hours=lag):
        raise ValueError(
            f"{case.case_id} : latence du cas {origin - cutoff} différente de celle de "
            f"l'apprentissage ({lag} h)"
        )
    local = origin.tz_convert(F.LOCAL_TZ)
    if local != local.normalize():
        return MLPForecast(None, REFUSE_NOT_MIDNIGHT)
    learned_cutoff = (getattr(net, "training_report", None) or {}).get("fit_cutoff")
    cutoffs = [
        F._utc(pd.Timestamp(t), "fit_cutoff") for t in (fit_cutoff, learned_cutoff) if t is not None
    ]
    if cutoffs and origin < max(cutoffs):
        return MLPForecast(None, REFUSE_BEFORE_CUTOFF)

    history = baseline.admissible_history(inputs.history, cutoff, counter_id=case.counter_id)
    if case.support_start is not None:
        history = history.loc[history["timestamp"] >= case.support_start]
    if case.support_end is not None:
        history = history.loc[history["interval_end"] <= case.support_end]
    if history.empty:
        return MLPForecast(None, REFUSE_NO_HISTORY)
    use_context = bool(layout["use_context"])
    if use_context and (inputs.context is None or len(inputs.context) == 0):
        return MLPForecast(None, REFUSE_CONTEXT)

    frame = pd.DataFrame({"timestamp": history["timestamp"].reset_index(drop=True)})
    frame["counter_id"] = str(case.counter_id)
    frame["count"] = pd.to_numeric(history["count"], errors="coerce").to_numpy(dtype=float)
    frame["count_raw"] = np.nan  # cibles inconnues à l'origine : jamais lues ici
    frame["is_scoreable"] = False
    threshold = _min_observed_of(net) if min_observed_hours is None else int(min_observed_hours)
    windows = build_windows(
        frame,
        pd.DataFrame({"counter_id": [str(case.counter_id)], "origin": [origin]}),
        inputs.context if use_context else None,
        use_context=use_context,
        publication_lag_hours=lag,
        min_observed_hours=threshold,
    )
    observed = int(windows.mask[0].sum())
    reason = refusal_reasons(windows)[0]
    if reason is not None:
        return MLPForecast(None, reason, observed_hours=observed)
    values = predict_windows(net, windows)[0]
    scale = float(windows.scale[0])
    if not np.isfinite(values).all():
        return MLPForecast(None, REFUSE_NON_FINITE, scale, observed)
    return MLPForecast(values, None, scale, observed)


# --------------------------------------------------------------------------- sauvegarde


def save_mlp(net: MLPNet, path: Path, *, use_context: bool) -> None:
    """Écrire dans un seul fichier : forme du réseau, disposition des entrées, poids, bilan.

    La disposition des entrées (taille de fenêtre, latence, colonnes du calendrier) est
    gardée pour refuser au chargement un réseau appris sur des entrées rangées autrement.
    Le bilan de fit_mlp voyage avec les poids : il reste lisible sans le code.
    """
    layout = _input_layout(use_context, _lag_of(net))
    learned = getattr(net, "input_layout", None)
    if learned is not None and learned != layout:
        raise ValueError("use_context différent de la disposition apprise par le réseau")
    torch.save(
        {
            "format": FILE_FORMAT,
            "arch": net.arch,
            "layout": layout,
            "state_dict": net.state_dict(),
            "training": getattr(net, "training_report", None),
        },
        Path(path),
    )


def load_mlp(path: Path) -> MLPNet:
    """Relire un réseau écrit par save_mlp, prêt à prévoir (mode évaluation).

    weights_only=True : seuls des nombres, textes et tableaux sont relus, jamais du code.
    Un fichier au format 1 (MOD-007) n'écrivait pas la latence : elle valait 24 h.
    """
    saved = torch.load(Path(path), weights_only=True)
    file_format = saved.get("format")
    if file_format not in READABLE_FORMATS:
        raise ValueError(f"{path} : format {file_format!r}, attendus {READABLE_FORMATS}")
    layout = dict(saved["layout"])
    if file_format == 1:
        layout.setdefault("publication_lag_hours", DEFAULT_LAG_HOURS)
    try:
        expected = _input_layout(layout["use_context"], layout["publication_lag_hours"])
    except (KeyError, TypeError, ValueError):
        expected = None
    if layout != expected:
        raise ValueError(
            f"{path} : réseau appris sur des entrées rangées autrement que le code actuel "
            "(taille de fenêtre, latence ou colonnes du calendrier) : réentraîner le modèle"
        )
    net = MLPNet(**saved["arch"])
    net.load_state_dict(saved["state_dict"])
    net.input_layout = layout
    net.training_report = saved.get("training")
    net.eval()  # coupe le dropout : une même entrée donne toujours la même prévision
    return net


def _input_layout(use_context: bool, publication_lag_hours: int = DEFAULT_LAG_HOURS) -> dict:
    """Description de l'entrée attendue par le réseau, comparée au chargement."""
    return {
        "use_context": bool(use_context),
        "window_hours": WINDOW_HOURS,
        "horizon_hours": HORIZON_HOURS,
        "publication_lag_hours": int(publication_lag_hours),
        "calendar_columns": calendar_columns(use_context),
    }


def _use_context_of(net: MLPNet) -> bool:
    """use_context d'un réseau : sa disposition apprise, sinon déduite du nombre d'entrées."""
    layout = getattr(net, "input_layout", None)
    if layout is not None:
        return bool(layout["use_context"])
    n_calendar = net.arch["n_inputs"] - 2 * WINDOW_HOURS
    if n_calendar == len(calendar_columns(True)):
        return True
    if n_calendar == len(calendar_columns(False)):
        return False
    raise ValueError(f"réseau à {net.arch['n_inputs']} entrées : disposition inconnue")


def _lag_of(net: MLPNet) -> int:
    layout = getattr(net, "input_layout", None)
    return DEFAULT_LAG_HOURS if layout is None else int(layout["publication_lag_hours"])


def _min_observed_of(net: MLPNet) -> int:
    """Seuil d'heures mesurées appris par le réseau (bilan), 84 pour un réseau d'avant."""
    report = getattr(net, "training_report", None) or {}
    hp = report.get("hyperparameters") or {}
    return int(hp.get("min_observed_hours", MIN_OBSERVED_HOURS))


def _layout_of(net: MLPNet) -> dict[str, Any]:
    """Disposition apprise du réseau ; à défaut (réseau jamais entraîné), celle du code."""
    layout = getattr(net, "input_layout", None)
    return layout if layout is not None else _input_layout(_use_context_of(net))


def _save_backend(net: MLPNet, path: Path) -> None:
    """Version pour train.save_model : use_context est lu dans la disposition du réseau."""
    save_mlp(net, path, use_context=_use_context_of(net))


# Branchement sur train.py : save_model / load_model / fit savent maintenant écrire,
# relire et entraîner un MLP (fit_mlp, MOD-008).
register_backend(
    METHOD,
    MethodBackend(
        WEIGHTS_FILE,
        save=_save_backend,
        load=load_mlp,
        fit=fit_mlp,
        minimum_history_hours=WINDOW_HOURS + DEFAULT_LAG_HOURS,
    ),
)


# --------------------------------------------------------------------------- commande


def main(argv: list[str] | None = None) -> int:
    """Entraîner le MLP sur un instantané E1, le sauvegarder et afficher son bilan (JSON).

    Exemple (coupure au 01/07/2026 minuit à Paris, avec contexte, graine 0) :
    python -m src.models.known.neural --snapshot hist-20261117 \
        --fit-cutoff 2026-06-30T22:00:00+00:00 --seed 0
    Écrit artifacts/models/<model_run_id>/ : weights.pt, metadata.json et
    training_report.json (copie lisible du bilan). Entrées = mesures seules (D-11).
    """
    parser = argparse.ArgumentParser(description=main.__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True, help="instantané E1, ex. hist-20261117")
    parser.add_argument("--fit-cutoff", required=True, help="ISO 8601 avec fuseau")
    parser.add_argument("--train-start", help="ISO 8601 avec fuseau ; défaut : début des données")
    parser.add_argument("--no-context", action="store_true", help="apprendre sans contexte")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--set", action="append", default=[], metavar="CLÉ=VALEUR", help="réglage du MLP"
    )
    parser.add_argument("--protocol-id")
    parser.add_argument("--root", type=Path, help="dossier des modèles (défaut : config)")
    parser.add_argument("--no-save", action="store_true", help="apprendre sans écrire")
    args = parser.parse_args(argv)

    try:
        fit_cutoff = _parse_utc(args.fit_cutoff, "--fit-cutoff")
        train_start = _parse_utc(args.train_start, "--train-start") if args.train_start else None
        hp = mlp_hyperparameters(**dict(_parse_setting(item) for item in args.set))
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
        feature_version=INPUT_VERSION,
    )
    model = train.fit(config, data.counts, data.context, data.inventory)
    summary = {
        "model_run_id": model.model_run_id,
        "snapshot_id": args.snapshot,
        "load_seconds": round(loaded - started, 1),
        "train_fit_seconds": round(model.train_seconds, 1),
        "total_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": _peak_memory_mb(),
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
    """« hidden=64 » -> ("hidden", 64) ; valeur JSON si possible, texte sinon."""
    key, sep, raw = text.partition("=")
    if not sep or not key.strip():
        raise ValueError(f"--set attend CLÉ=VALEUR, reçu {text!r}")
    try:
        return key.strip(), json.loads(raw)
    except json.JSONDecodeError:
        return key.strip(), raw


def _peak_memory_mb() -> float | None:
    """Pic de mémoire du processus (Linux, macOS) ; None ailleurs (Windows)."""
    try:
        import resource
        import sys
    except ImportError:  # pragma: no cover - Windows
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)


if __name__ == "__main__":
    raise SystemExit(main())

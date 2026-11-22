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
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

from src.models.known import features as F
from src.models.known.train import MethodBackend, register_backend
from src.models.schemas import HORIZON_HOURS

METHOD = "mlp"
WEIGHTS_FILE = "weights.pt"
FILE_FORMAT = 1  # version du contenu de weights.pt

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
) -> Windows:
    """Construire un exemple par ligne de origins (colonnes counter_id, origin).

    counts : counter_id, timestamp (UTC), count (entrée : mesures seules, voir
    train.load_training_data), count_raw et is_scoreable (pour les cibles).
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
    usable = (n_obs >= MIN_OBSERVED_HOURS) & (scale >= MIN_SCALE)
    safe = np.where(usable, scale, 1.0)[:, None]
    series = np.clip(np.nan_to_num(window / safe, nan=0.0), 0.0, INPUT_CLIP)
    target_mask = ~np.isnan(truth)
    target = np.nan_to_num(truth / safe, nan=0.0)

    # 4. La journée à prévoir et, si use_context, la météo prévue heure par heure.
    columns = calendar_columns(use_context)
    calendar = _calendar_block(tgt_h, origin_h, context, use_context, columns)

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
) -> np.ndarray:
    """Tableau (n, k) dans l'ordre de calendar_columns.

    1. La journée, une seule fois (elle est la même pour les 24 heures) : jour de la
       semaine en 7 cases, dst_shift, puis fériés, vacances, grève si use_context.
    2. La météo prévue, heure par heure : 24 températures, 24 pluies, 24 vents.
    """
    n = len(origin_h)
    first = tgt_h[:, 0]  # première heure cible = minuit à Paris : elle date la journée
    dow = F._calendar_core(first)["dow_local"]
    parts = [(dow == d).astype(float)[:, None] for d in range(7)]
    parts.append(_dst_shift(first)[:, None])

    groups = F.resolve_context_groups(use_context)
    if groups:
        tables = F._prepare_context(context, groups)
        origins_flat = np.repeat(origin_h, HORIZON_HOURS)
        ctx = F._context_core(tables, origins_flat, tgt_h.ravel(), groups)  # NaN si trop tard
        for group in DAY_CONTEXT_GROUPS:
            if group in groups:
                for variable in F.CONTEXT_GROUPS[group]:
                    day = np.nan_to_num(ctx[variable].reshape(n, HORIZON_HOURS)[:, 0], nan=0.0)
                    parts.append(day[:, None])
        for group in HOURLY_CONTEXT_GROUPS:
            if group in groups:
                for variable in F.CONTEXT_GROUPS[group]:
                    hourly = np.nan_to_num(ctx[variable].reshape(n, HORIZON_HOURS), nan=0.0)
                    parts.append(hourly / WEATHER_SCALE.get(variable, 1.0))
    block = np.hstack(parts)
    if block.shape[1] != len(columns):
        raise AssertionError("calendrier : nombre de colonnes inattendu")
    return block


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

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


# --------------------------------------------------------------------------- sauvegarde


def save_mlp(net: MLPNet, path: Path, *, use_context: bool) -> None:
    """Écrire dans un seul fichier : forme du réseau, disposition des entrées et poids.

    La disposition des entrées (taille de fenêtre, colonnes du calendrier) est gardée
    pour refuser au chargement un réseau appris sur des entrées rangées autrement.
    """
    torch.save(
        {
            "format": FILE_FORMAT,
            "arch": net.arch,
            "layout": _input_layout(use_context),
            "state_dict": net.state_dict(),
        },
        Path(path),
    )


def load_mlp(path: Path) -> MLPNet:
    """Relire un réseau écrit par save_mlp, prêt à prévoir (mode évaluation).

    weights_only=True : seuls des nombres, textes et tableaux sont relus, jamais du code.
    """
    saved = torch.load(Path(path), weights_only=True)
    if saved.get("format") != FILE_FORMAT:
        raise ValueError(f"{path} : format {saved.get('format')!r}, attendu {FILE_FORMAT}")
    layout = saved["layout"]
    expected = _input_layout(layout["use_context"])
    if layout != expected:
        raise ValueError(
            f"{path} : réseau appris sur des entrées rangées autrement que le code actuel "
            "(taille de fenêtre ou colonnes du calendrier) : réentraîner le modèle"
        )
    net = MLPNet(**saved["arch"])
    net.load_state_dict(saved["state_dict"])
    net.eval()  # coupe le dropout : une même entrée donne toujours la même prévision
    return net


def _input_layout(use_context: bool) -> dict[str, Any]:
    """Description de l'entrée attendue par le réseau, comparée au chargement."""
    return {
        "use_context": bool(use_context),
        "window_hours": WINDOW_HOURS,
        "horizon_hours": HORIZON_HOURS,
        "calendar_columns": calendar_columns(use_context),
    }


def _save_backend(net: MLPNet, path: Path) -> None:
    """Version pour train.save_model : use_context est lu dans la forme du réseau."""
    n_calendar = net.arch["n_inputs"] - 2 * WINDOW_HOURS
    use_context = n_calendar == len(calendar_columns(True))
    if not use_context and n_calendar != len(calendar_columns(False)):
        raise ValueError(f"réseau à {net.arch['n_inputs']} entrées : disposition inconnue")
    save_mlp(net, path, use_context=use_context)


# Branchement sur train.py : save_model / load_model savent maintenant écrire et relire
# un MLP. fit=None tant que l'apprentissage (fit_mlp) n'est pas écrit.
register_backend(
    METHOD,
    MethodBackend(
        WEIGHTS_FILE,
        save=_save_backend,
        load=load_mlp,
        fit=None,
        minimum_history_hours=WINDOW_HOURS + DEFAULT_LAG_HOURS,
    ),
)

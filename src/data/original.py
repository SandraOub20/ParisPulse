"""Valeurs d'origine d'un counts.csv rempli (J-7, année d'avant) - E1, Sabrina.

Depuis le 19/11/2026 (décision de Sabrina), `fill_counts.py` remplace `count` directement
dans counts.csv. `count_raw` et les drapeaux permettent de revenir aux valeurs d'origine :
- heure remplie par J-7 : `is_observed` faux et `count` rempli (une heure sans mesure a
  toujours `count` vide, doc/CONTRATS.md) -> `count` redevient vide ;
- zéro remplacé par l'année d'avant : `is_observed` vrai, `is_scoreable` faux, `count_raw`
  = 0 et `count` > 0 (impossible à l'origine, où `count` = valeur lue de `count_raw`)
  -> `count` = 0 et `is_scoreable` vrai.
Sur un counts.csv non rempli, rien ne change.

Limite : l'historique vidé des sites réservés à E3 ne se retrouve pas ici (`count_raw`
vidé aussi) : il se recalcule depuis le brut.

Les analyses d'E1 sur les zéros (zeros, zeros_years, zeros_experiment) et l'examen des
alertes lisent counts.csv avec `load_original_counts`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.quality import normalize_counts

COLUMNS = ["counter_id", "timestamp", "count", "count_raw", "is_observed", "is_scoreable"]


def restore_masks(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """(heures remplies par J-7, zéros remplacés par l'année d'avant), sur des colonnes texte."""
    count = pd.to_numeric(df["count"].replace("", np.nan), errors="coerce")
    raw = pd.to_numeric(df["count_raw"].replace("", np.nan), errors="coerce")
    observed = df["is_observed"].str.lower().eq("true")
    scoreable = df["is_scoreable"].str.lower().eq("true")
    j7 = ~observed & count.notna()
    year = observed & ~scoreable & count.gt(0) & raw.eq(0)
    return j7, year


def load_original_counts(path: Path) -> pd.DataFrame:
    """counts.csv au format de `quality.load_counts`, avec les valeurs d'avant remplissage."""
    raw = pd.read_csv(path, usecols=COLUMNS, dtype=str, keep_default_na=False)
    j7, year = restore_masks(raw)
    raw.loc[j7, "count"] = ""
    raw.loc[year, "count"] = "0"
    raw.loc[year, "is_scoreable"] = "true"
    return normalize_counts(raw)

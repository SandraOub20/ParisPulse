"""Remplacement des heures sans mesure par la même heure une semaine avant (J-7) - E1, Sabrina.

Demande de l'équipe (Nihed, 17/11/2026, tâche B2 de la passation) : remplacer les
heures sans mesure (`missing` et `empty_value`) par la valeur de J-7. La passation
proposait une nouvelle colonne ; décision de Sabrina (18/11/2026) : remplacer `count`
directement, `count_raw` restant vide pour revenir à l'état d'avant traitement.

Règle (décisions de Sabrina, 17 et 18/11/2026) :
- heure visée : drapeau `missing` ou `empty_value` (sans valeur), pendant la période
  active du compteur,
  c'est-à-dire entre sa première et sa dernière heure observée ; rien avant
  l'installation ni après l'arrêt ;
- une heure absente du fichier (ligne non reçue) dans cette période est d'abord créée,
  avec le drapeau `missing` ;
- valeur : `count` de la même heure de Paris sept jours avant, si cette heure a une
  mesure (`is_scoreable`) ; jamais une valeur elle-même remplacée ;
- si J-7 n'a pas de mesure, ou n'existe pas (heure sautée ou répétée au changement
  d'heure), l'heure reste vide.

Sortie : `count` reçoit la valeur de J-7. `count_raw` reste vide (trace : une heure
remplacée a `count` rempli et `count_raw` vide), `quality_flags` est inchangé, et
`is_observed` reste faux : l'heure n'a pas été mesurée. Avec la règle de prepare
(observée et `count` non vide), `is_scoreable` reste faux : une valeur remplacée n'est
jamais une cible évaluable (`doc/CONTRATS.md` §3 : « Les cibles ne sont jamais
imputées »).

Appelé par `fill_counts.py` (une seule commande, qui remplit directement counts.csv ;
`count_raw` et les drapeaux gardent la trace). Fonctionne pour tout instantané.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.data.quality import TZ_LOCAL

MISSING_FLAG = "missing"
TARGET_FLAGS = {"missing", "empty_value"}
FILL_VERSION = "e1-fill-j7/0.3.0"


def j7_timestamps(ts: pd.Series) -> pd.Series:
    """Même heure de Paris sept jours avant, en UTC ; NaT si elle n'existe pas ou est double."""
    wall = ts.dt.tz_convert(TZ_LOCAL).dt.tz_localize(None) - pd.Timedelta(days=7)
    local = wall.dt.tz_localize(TZ_LOCAL, ambiguous="NaT", nonexistent="NaT")
    return local.dt.tz_convert("UTC")


def _flags(value) -> list[str]:
    if isinstance(value, list):
        return list(value)
    if value is None or (isinstance(value, float) and np.isnan(value)) or value == "":
        return []
    return list(json.loads(value))


def complete_active_grid(counts: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les heures absentes de la période active de chaque compteur (drapeau `missing`).

    `counts` : colonnes `counter_id`, `ts` (UTC), `count`, `is_observed`, `is_scoreable`,
    `quality_flags` (liste). Les autres colonnes des lignes créées sont vides.
    """
    parts = []
    for cid, g in counts.groupby("counter_id", sort=False):
        seen = g.loc[g["is_observed"], "ts"]
        if seen.empty:
            parts.append(g)
            continue
        grid = pd.date_range(seen.min(), seen.max(), freq="h", tz="UTC")
        absent = grid.difference(pd.DatetimeIndex(g["ts"]))
        if len(absent):
            new = pd.DataFrame(
                {
                    "counter_id": cid,
                    "ts": absent,
                    "count": np.nan,
                    "is_observed": False,
                    "is_scoreable": False,
                    "quality_flags": [[MISSING_FLAG] for _ in absent],
                }
            )
            g = pd.concat([g, new], ignore_index=True)
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["counter_id", "ts"], kind="stable").reset_index(drop=True)


def fill_j7(counts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remplace `count` des heures sans mesure actives par J-7. Retourne (copie, bilan)."""
    df = counts.copy()
    df["quality_flags"] = df["quality_flags"].map(_flags)
    n_before = len(df)
    df = complete_active_grid(df)
    n_created = len(df) - n_before

    seen = df.loc[df["is_observed"]].groupby("counter_id")["ts"].agg(["min", "max"])
    bounds = df[["counter_id"]].join(seen, on="counter_id")
    active = (df["ts"] >= bounds["min"]) & (df["ts"] <= bounds["max"])
    # Heures visées : drapeau missing ou empty_value (décision du 18/11/2026), sans valeur
    flagged = df["quality_flags"].map(lambda f: bool(set(f) & TARGET_FLAGS))
    target = active & flagged & df["count"].isna()

    measured = df.loc[df["is_scoreable"] & df["count"].notna(), ["counter_id", "ts", "count"]]
    lookup = df.loc[target, ["counter_id"]].assign(ts=j7_timestamps(df.loc[target, "ts"]))
    value = lookup.merge(measured, on=["counter_id", "ts"], how="left")["count"].to_numpy()
    idx = df.index[target]
    filled = idx[~np.isnan(value)]
    df.loc[filled, "count"] = value[~np.isnan(value)]
    # is_observed reste faux : is_scoreable (observée et count non vide) reste faux

    report = {
        "fill_version": FILL_VERSION,
        "rule": "même heure de Paris J-7, si mesurée ; période active seulement ; "
        "count remplacé, count_raw vide, is_observed et is_scoreable faux",
        "n_rows_created": int(n_created),
        "n_hours_without_value_active": int(target.sum()),
        "n_hours_filled": int(len(filled)),
        "n_hours_left_empty": int(target.sum() - len(filled)),
        "n_hours_without_value_outside_active": int((~active & df["count"].isna()).sum()),
    }
    return df, report

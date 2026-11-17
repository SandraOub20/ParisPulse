"""Inventaire du réseau, qualité des séries et choix de l'échantillon - E1 avec E4.

Lit les sorties de `prepare.py` dans `data/processed/<snapshot_id>/` :
`counts.csv` et `counters.csv` (colonnes de `doc/templates/`). Produit :

- `inventory_quality.csv` : une ligne par compteur et par période (colonnes du
  gabarit, puis colonnes descriptives) ;
- `selection_summary.json` : critères, effectifs, listes de groupes de sites
  à recopier dans `config/project.yaml` (`protocol.site_groups`), et trous
  communs au réseau (`network_gaps`) ;
- la colonne `site_group_id` de `counters.csv`, réécrite avec les groupes
  candidats (sites à moins de `alias_distance_m`), seule colonne modifiée.

Groupes de sites : toujours recalculés à partir de `site_id` (jamais modifié),
pour que relancer le script donne exactement le même résultat. Ils sont
CANDIDATS : déduits de la distance, non vérifiés sur place.

Deux périodes par compteur (`period_role`) :
- `selection` : du début de l'instantané au début du test (exclu). Les
  statuts sont décidés UNIQUEMENT sur cette période (PROTOCOLE §3 : les
  critères ne consomment pas le futur du test).
- `full_snapshot` : tout l'instantané, pour DÉCRIRE le réseau. Le statut y est
  recopié depuis la période `selection`, jamais recalculé.

Statuts (`selection_status`) :
- `retained` : compteur gardé, site connu (`S_train`) pour E2 ;
- `robustness` : utilisable mais difficile (historique court, manques,
  suite de zéros, faible volume, série interrompue) ; site connu, évalué à part ;
- `reserved_dev_new` / `reserved_test_new` : site entier réservé à E3
  (`S_dev_new` / `S_test_new`), toutes directions et alias possibles ensemble ;
- `excluded` : écarté, raison donnée. Il reste dans l'inventaire et sur la carte.

Les zéros ne sont jamais transformés en manques : une suite de zéros est
mesurée et signalée, sa cause n'est pas établie par les fichiers.

Usage, depuis la racine du dépôt :
  uv run python -m src.data.quality --snapshot flux-20261112
  uv run python -m src.data.quality --snapshot flux-20261112 --fin-selection 2026-10-01 --figures
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path, load_config, relative_to_root

TZ_LOCAL = "Europe/Paris"
QUALITY_VERSION = "e1-quality/0.1.0"
LONG_ZERO_RUN_HOURS = 24  # même seuil que prepare.LONG_ZERO_RUN_HOURS
DEFAULT_TEST_START_LOCAL = "2026-10-01"  # PROTOCOLE §3 : test = origines d'octobre 2026
PARIS_CENTER = (48.8566, 2.3522)  # Hôtel de Ville, référence des zones
COMMUTE_HOURS = (7, 8, 9, 17, 18, 19)  # heures locales de pointe

PERIOD_SELECTION = "selection"
PERIOD_FULL = "full_snapshot"

STATUS_RETAINED = "retained"
STATUS_ROBUSTNESS = "robustness"
STATUS_DEV_NEW = "reserved_dev_new"
STATUS_TEST_NEW = "reserved_test_new"
STATUS_EXCLUDED = "excluded"

TEMPLATE_COLUMNS = [
    "counter_id",
    "period_start",
    "period_end",
    "n_expected",
    "n_observed",
    "n_scoreable",
    "n_missing",
    "n_zeros",
    "longest_zero_run",
    "selection_status",
    "status_reason",
    "snapshot_id",
]
EXTRA_COLUMNS = [
    "period_role",
    "site_role",
    "site_id",
    "site_group_id",
    "candidate_group_id",
    "counter_name",
    "latitude",
    "longitude",
    "has_coordinates",
    "dist_center_km",
    "zone",
    "first_observed",
    "last_observed",
    "history_days",
    "observed_days",
    "missing_rate",
    "missing_rate_in_span",
    "n_invalid",
    "n_long_zero_runs",
    "n_long_zero_run_hours",
    "long_zero_share",
    "n_dst_days_incomplete",
    "mean_count",
    "median_count",
    "p95_count",
    "max_count",
    "weekday_weekend_ratio",
    "commute_peak_ratio",
    "volume_class",
    "profile_type",
    "alias_candidates",
    "nearby_sites_300m",
    "uncertainties",
    "quality_version",
]
INVENTORY_COLUMNS = TEMPLATE_COLUMNS + EXTRA_COLUMNS


@dataclass(frozen=True)
class SelectionCriteria:
    """Critères fixés AVANT le test ; justification dans reports/experiments/."""

    # En dessous de 28 jours observés : ni référence hebdomadaire sur plusieurs
    # semaines, ni support local de 7 jours suivi d'une cible -> exclu.
    min_observed_days: float = 28.0
    # En dessous de 180 jours observés : une seule saison -> robustesse.
    full_history_days: float = 180.0
    # Manques dans l'intervalle de fonctionnement : > 10 % robustesse, > 50 % exclu.
    max_missing_rate: float = 0.10
    max_missing_rate_excluded: float = 0.50
    # Part des heures observées dans des suites de zéros >= 24 h : > 50 % exclu
    # (la série ne décrit plus le passage) ; toute suite >= 24 h -> robustesse.
    max_long_zero_share: float = 0.50
    # Moyenne horaire < 5 passages : faible volume -> robustesse.
    low_volume_mean: float = 5.0
    # Série arrêtée plus de 7 jours avant la fin de la période -> robustesse.
    max_stop_days_before_end: float = 7.0
    # Sites réservés à E3 (fractions des groupes éligibles), au moins 2 chacun.
    reserve_dev_fraction: float = 0.10
    reserve_test_fraction: float = 0.15
    min_reserved_groups: int = 2
    # Deux groupes de sites à moins de 100 m : même lieu possible, gardés ensemble.
    # Sur flux-20261114, les deux sens d'un même lieu ont souvent deux site_id
    # distants de 0 à 93 m (Pont National : 57 m) ; la paire suivante est à 113 m.
    alias_distance_m: float = 100.0
    # Sites voisins à moins de 300 m : descriptif seulement (aucun effet sur les
    # groupes ni les statuts). Sert à proposer un compteur proche quand un
    # compteur n'a pas de mesure (exclu, série arrêtée, trou).
    nearby_distance_m: float = 300.0
    # Heure « trou du réseau » si au moins 90 % des compteurs actifs sont sans mesure.
    network_gap_share: float = 0.90
    seed: str = "parispulse-e1"

    @classmethod
    def from_config(cls, overrides: dict | None = None) -> SelectionCriteria:
        allowed = {f.name for f in fields(cls)}
        values = {k: v for k, v in (overrides or {}).items() if k in allowed}
        return cls(**values)


# ----------------------------------------------------------------- lecture
def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.lower().eq("true")


def normalize_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Colonnes utiles de counts.csv, typées ; refuse une clé dupliquée."""
    out = pd.DataFrame(
        {
            "counter_id": df["counter_id"].astype(str),
            "ts": pd.to_datetime(df["timestamp"], utc=True, format="ISO8601"),
            "count": pd.to_numeric(df["count"], errors="coerce"),
            "is_observed": _as_bool(df["is_observed"]),
            "is_scoreable": _as_bool(df["is_scoreable"]),
        }
    )
    dup = out.duplicated(["counter_id", "ts"])
    if dup.any():
        raise ValueError(
            f"{int(dup.sum())} clés (counter_id, timestamp) dupliquées dans counts.csv : "
            "contrat non respecté, corriger prepare avant l'inventaire."
        )
    return out.sort_values(["counter_id", "ts"], kind="stable").reset_index(drop=True)


def load_counts(path: Path) -> pd.DataFrame:
    cols = ["counter_id", "timestamp", "count", "is_observed", "is_scoreable"]
    raw = pd.read_csv(path, usecols=cols, dtype={c: str for c in cols if c != "count"})
    return normalize_counts(raw)


def load_counters(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in ("latitude", "longitude"):
        df[col] = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
    return df


# ----------------------------------------------------------------- mesures
def local_midnight_utc(day: str) -> pd.Timestamp:
    """Minuit heure de Paris d'une date AAAA-MM-JJ, converti en UTC."""
    return pd.Timestamp(day).tz_localize(TZ_LOCAL).tz_convert("UTC")


def hour_grid(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    """Heures UTC de [start, end)."""
    return pd.date_range(start, end, freq="h", tz="UTC", inclusive="left", name="ts")


def true_runs(mask: np.ndarray) -> np.ndarray:
    """Longueurs des suites consécutives de True."""
    m = np.concatenate([[0], mask.astype(np.int8), [0]])
    d = np.diff(m)
    return np.flatnonzero(d == -1) - np.flatnonzero(d == 1)


def _mean(values: np.ndarray) -> float:
    return float(np.mean(values)) if len(values) else np.nan


def counter_metrics(series: pd.DataFrame, grid: pd.DatetimeIndex) -> dict:
    """Mesures d'un compteur sur une grille horaire UTC fixée (même pour tous).

    Une heure de la grille absente de counts.csv compte comme manquante : la
    durée d'historique fait partie de la qualité observée sur la période.
    """
    g = series.set_index("ts").reindex(grid)
    observed = g["is_observed"].eq(True).to_numpy()
    scoreable = g["is_scoreable"].eq(True).to_numpy()
    count = g["count"].to_numpy(dtype=float)
    n_expected = len(grid)
    n_observed = int(observed.sum())

    zero = observed & scoreable & (count == 0)
    runs = true_runs(zero)
    long_runs = runs[runs >= LONG_ZERO_RUN_HOURS]

    m = {
        "n_expected": n_expected,
        "n_observed": n_observed,
        "n_scoreable": int(scoreable.sum()),
        "n_missing": n_expected - n_observed,
        "n_invalid": int((observed & ~scoreable).sum()),
        "n_zeros": int(zero.sum()),
        "longest_zero_run": int(runs.max()) if len(runs) else 0,
        "n_long_zero_runs": int(len(long_runs)),
        "n_long_zero_run_hours": int(long_runs.sum()),
        "long_zero_share": float(long_runs.sum() / n_observed) if n_observed else np.nan,
        "missing_rate": float(1 - n_observed / n_expected) if n_expected else np.nan,
        "observed_days": n_observed / 24,
    }

    if n_observed:
        idx = np.flatnonzero(observed)
        first, last = grid[idx[0]], grid[idx[-1]]
        span = idx[-1] - idx[0] + 1
        m.update(
            first_observed=first,
            last_observed=last,
            history_days=span / 24,
            missing_rate_in_span=float(1 - n_observed / span),
        )
    else:
        m.update(
            first_observed=pd.NaT,
            last_observed=pd.NaT,
            history_days=0.0,
            missing_rate_in_span=np.nan,
        )

    vals = count[scoreable]
    m.update(
        mean_count=_mean(vals),
        median_count=float(np.median(vals)) if len(vals) else np.nan,
        p95_count=float(np.quantile(vals, 0.95)) if len(vals) else np.nan,
        max_count=float(np.max(vals)) if len(vals) else np.nan,
    )

    local = grid.tz_convert(TZ_LOCAL)
    weekday = np.asarray(local.dayofweek < 5)
    peak = np.isin(np.asarray(local.hour), COMMUTE_HOURS)
    wk = _mean(count[scoreable & weekday])
    we = _mean(count[scoreable & ~weekday])
    pk = _mean(count[scoreable & weekday & peak])
    m["weekday_weekend_ratio"] = wk / we if we and np.isfinite(we) and we > 0 else np.nan
    m["commute_peak_ratio"] = pk / wk if wk and np.isfinite(wk) and wk > 0 else np.nan

    # Jours de changement d'heure (23 ou 25 h) incomplets : signalés, jamais supprimés.
    day = pd.Series(local.normalize())
    expected = day.value_counts()
    seen = day[observed].value_counts()
    edges = {day.iloc[0], day.iloc[-1]} if len(day) else set()
    m["n_dst_days_incomplete"] = int(
        sum(1 for d, n in expected.items() if n != 24 and d not in edges and 0 < seen.get(d, 0) < n)
    )
    return m


def profile_type(weekday_weekend_ratio: float, commute_peak_ratio: float) -> str:
    """Profil descriptif (non utilisé pour exclure) : sert à vérifier la diversité."""
    if not (np.isfinite(weekday_weekend_ratio) and np.isfinite(commute_peak_ratio)):
        return "indéterminé"
    if weekday_weekend_ratio >= 1.3 and commute_peak_ratio >= 1.5:
        return "pendulaire"
    if weekday_weekend_ratio < 0.9:
        return "loisirs"
    return "mixte"


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def zone_of(dist_km: float) -> str:
    if not np.isfinite(dist_km):
        return "inconnue"
    if dist_km < 2.5:
        return "centre"
    if dist_km < 5.0:
        return "intermédiaire"
    return "périphérie"


def volume_classes(mean_counts: pd.Series) -> tuple[pd.Series, list[float]]:
    """Tertiles des moyennes horaires (faible / moyen / fort) et leurs seuils."""
    valid = mean_counts.dropna()
    if valid.nunique() < 3:
        return pd.Series("indéterminé", index=mean_counts.index), []
    q1, q2 = (float(x) for x in valid.quantile([1 / 3, 2 / 3]))
    cls = np.select(
        [mean_counts.isna(), mean_counts < q1, mean_counts < q2],
        ["indéterminé", "faible", "moyen"],
        "fort",
    )
    return pd.Series(cls, index=mean_counts.index), [q1, q2]


# ----------------------------------------------------------------- groupes de sites
def _by_distance(neighbours: dict[str, int]) -> dict[str, int]:
    """Voisins triés du plus proche au plus loin (puis par identifiant)."""
    return dict(sorted(neighbours.items(), key=lambda kv: (kv[1], kv[0])))


def candidate_groups(
    counters: pd.DataFrame,
    alias_distance_m: float,
    nearby_distance_m: float = SelectionCriteria.nearby_distance_m,
) -> pd.DataFrame:
    """Rassemble les `site_group_id` à moins de `alias_distance_m` (alias possibles).

    Un nom identique ne suffit pas à raccorder deux séries ; la proximité ne le
    prouve pas non plus : on garde ces groupes ENSEMBLE (jamais répartis entre
    donneurs et réservés) et on le signale comme incertitude.

    Colonnes de voisinage, en dictionnaires {site voisin: distance en mètres,
    arrondie}, triés du plus proche au plus loin, sans le site lui-même :
    - `alias_candidates` : voisins directs à moins de `alias_distance_m`
      (ce sont eux qui forment les groupes, par chaînage) ;
    - `nearby_sites_300m` : voisins à moins de `nearby_distance_m`, alias compris ;
      descriptif, sans effet sur les groupes ni les statuts.
    """
    sites = (
        counters.groupby("site_group_id", sort=True)[["latitude", "longitude"]].mean().reset_index()
    )
    parent = {s: s for s in sites["site_group_id"]}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    aliases: dict[str, dict[str, int]] = {s: {} for s in parent}
    nearby: dict[str, dict[str, int]] = {s: {} for s in parent}
    located = sites.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    if len(located) > 1:
        lat = located["latitude"].to_numpy()
        lon = located["longitude"].to_numpy()
        dist = haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :]) * 1000
        ids = located["site_group_id"].to_numpy()
        limit = max(alias_distance_m, nearby_distance_m)
        for i, j in zip(*np.nonzero(np.triu(dist < limit, k=1))):
            a, b, d = ids[i], ids[j], dist[i, j]
            meters = int(round(float(d)))
            if d < nearby_distance_m:
                nearby[a][b] = nearby[b][a] = meters
            if d < alias_distance_m:
                aliases[a][b] = aliases[b][a] = meters
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    return pd.DataFrame(
        {
            "site_group_id": list(parent),
            "candidate_group_id": [find(s) for s in parent],
            "alias_candidates": [_by_distance(aliases[s]) for s in parent],
            "nearby_sites_300m": [_by_distance(nearby[s]) for s in parent],
        }
    )


def candidate_site_groups(
    counters: pd.DataFrame, alias_distance_m: float = SelectionCriteria.alias_distance_m
) -> pd.Series:
    """`counter_id` -> groupe candidat, avec la règle de `build_inventory`.

    Utilisé aussi par `prepare.py --tout`, pour que `counters.csv` contienne les
    groupes dès la préparation (même résultat que la réécriture de `run`).
    """
    c = counters[["counter_id", "site_id", "latitude", "longitude"]].copy()
    c["counter_id"] = c["counter_id"].astype(str)
    c["site_id"] = c["site_id"].fillna("").astype(str)
    for col in ("latitude", "longitude"):
        c[col] = pd.to_numeric(c[col].replace("", np.nan), errors="coerce")
    c["site_group_id"] = site_group_key(c)
    groups = candidate_groups(c, alias_distance_m)
    out = c.merge(groups, on="site_group_id").set_index("counter_id")
    return out["candidate_group_id"].astype(str)


def _stable_rank(value: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def reserve_new_sites(inv: pd.DataFrame, criteria: SelectionCriteria) -> dict[str, str]:
    """Choisit les groupes candidats réservés à E3 : {candidate_group_id: statut}.

    Éligible : tous les compteurs du groupe candidat sont `retained`. Les groupes
    sont répartis par strate (classe de volume x zone) dans un ordre déterministe
    (hachage + graine), en alternant les strates pour diversifier les profils.
    Au moins la moitié des groupes éligibles reste en apprentissage.
    """
    by_group = inv.groupby("candidate_group_id")
    eligible = by_group["selection_status"].apply(lambda s: (s == STATUS_RETAINED).all())
    eligible = eligible[eligible].index.tolist()
    n = len(eligible)
    n_test = max(criteria.min_reserved_groups, round(criteria.reserve_test_fraction * n))
    n_dev = max(criteria.min_reserved_groups, round(criteria.reserve_dev_fraction * n))
    if n_test + n_dev > n // 2:
        n_test, n_dev = (n // 2 + 1) // 2, n // 4
    if n_test == 0:
        return {}

    strata: dict[str, list[str]] = {}
    for g in eligible:
        rows = inv[inv["candidate_group_id"] == g]
        key = f"{rows['volume_class'].mode().iloc[0]}|{rows['zone'].mode().iloc[0]}"
        strata.setdefault(key, []).append(g)
    queues = {k: sorted(v, key=lambda g: _stable_rank(g, criteria.seed)) for k, v in strata.items()}
    order: list[str] = []
    while any(queues.values()):
        for k in sorted(queues):
            if queues[k]:
                order.append(queues[k].pop(0))
    out = {g: STATUS_TEST_NEW for g in order[:n_test]}
    out.update({g: STATUS_DEV_NEW for g in order[n_test : n_test + n_dev]})
    return out


# ----------------------------------------------------------------- statuts
def decide_status(row: pd.Series, period_end: pd.Timestamp, c: SelectionCriteria):
    """Statut d'un compteur sur la période de sélection et raisons lisibles."""
    excluded, robust = [], []
    if row["n_scoreable"] == 0:
        excluded.append("aucune mesure évaluable sur la période de sélection")
    else:
        if row["observed_days"] < c.min_observed_days:
            excluded.append(
                f"historique observé {row['observed_days']:.0f} j < {c.min_observed_days:.0f} j"
            )
        if row["missing_rate_in_span"] > c.max_missing_rate_excluded:
            excluded.append(
                f"manques {row['missing_rate_in_span']:.0%} en fonctionnement "
                f"> {c.max_missing_rate_excluded:.0%}"
            )
        if row["long_zero_share"] > c.max_long_zero_share:
            excluded.append(
                f"{row['long_zero_share']:.0%} des heures observées dans des suites de zéros "
                f">= {LONG_ZERO_RUN_HOURS} h"
            )
    if excluded:
        return STATUS_EXCLUDED, "; ".join(excluded)

    if row["observed_days"] < c.full_history_days:
        robust.append(
            f"historique court : {row['observed_days']:.0f} j observés "
            f"< {c.full_history_days:.0f} j"
        )
    if row["missing_rate_in_span"] > c.max_missing_rate:
        robust.append(f"manques {row['missing_rate_in_span']:.0%} > {c.max_missing_rate:.0%}")
    if row["n_long_zero_runs"] > 0:
        robust.append(
            f"{row['n_long_zero_runs']} suite(s) de zéros >= {LONG_ZERO_RUN_HOURS} h "
            f"(max {row['longest_zero_run']} h), cause non établie"
        )
    if row["mean_count"] < c.low_volume_mean:
        robust.append(f"faible volume : {row['mean_count']:.1f} passages/h en moyenne")
    stop_days = (period_end - pd.Timedelta(hours=1) - row["last_observed"]) / pd.Timedelta(days=1)
    if stop_days > c.max_stop_days_before_end:
        robust.append(f"série interrompue {stop_days:.0f} j avant la fin de la période")
    if robust:
        return STATUS_ROBUSTNESS, "; ".join(robust)
    return STATUS_RETAINED, "tous les critères satisfaits"


def site_role(status: str) -> str:
    return {
        STATUS_RETAINED: "S_train",
        STATUS_ROBUSTNESS: "S_train",
        STATUS_DEV_NEW: "S_dev_new",
        STATUS_TEST_NEW: "S_test_new",
    }.get(status, "none")


SITE_GROUP_RULE = (
    "site_group_id candidat : sites (site_id) à moins de alias_distance_m réunis par "
    "chaînage ; identifiant = plus petit site_id du groupe ; déduit de la distance, "
    "non vérifié sur place (E1, quality.py)."
)


def site_group_key(counters: pd.DataFrame) -> pd.Series:
    """Clé de regroupement : `site_id`, ou `counter_id` si le site est inconnu."""
    site = counters["site_id"].astype(str).str.strip()
    return site.where(site != "", counters["counter_id"].astype(str))


def uncertainties(row: pd.Series) -> list[str]:
    out = ["site_group_id candidat (sites proches réunis), non vérifié sur place"]
    if not row["has_coordinates"]:
        out.append("coordonnées absentes : non placé sur la carte")
    if row["alias_candidates"]:
        near = ", ".join(f"{s} ({d} m)" for s, d in row["alias_candidates"].items())
        out.append(f"site tout proche de {near} : alias possible")
    if row["n_dst_days_incomplete"]:
        out.append(f"{row['n_dst_days_incomplete']} jour(s) de changement d'heure incomplet(s)")
    if not str(row.get("direction") or "").strip():
        out.append("direction non validée")
    return out


# ----------------------------------------------------------------- inventaire
def period_metrics(counts: pd.DataFrame, counters: pd.DataFrame, grid, role: str):
    rows = []
    groups = dict(tuple(counts.groupby("counter_id", sort=False)))
    empty = counts.iloc[0:0]
    for cid in counters["counter_id"]:
        m = counter_metrics(groups.get(cid, empty), grid)
        m["counter_id"] = cid
        rows.append(m)
    out = pd.DataFrame(rows)
    out["period_role"] = role
    out["period_start"] = grid[0] if len(grid) else pd.NaT
    out["period_end"] = grid[-1] + pd.Timedelta(hours=1) if len(grid) else pd.NaT
    return out


def build_inventory(
    counts: pd.DataFrame,
    counters: pd.DataFrame,
    snapshot_id: str,
    selection_end: pd.Timestamp,
    criteria: SelectionCriteria | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Inventaire (deux périodes par compteur) et résumé de sélection."""
    c = criteria or SelectionCriteria()
    counters = counters.copy()
    counters["counter_id"] = counters["counter_id"].astype(str)
    unknown = sorted(set(counts["counter_id"]) - set(counters["counter_id"]))
    if unknown:
        raise ValueError(f"Compteurs absents de counters.csv : {unknown[:5]}")
    # Groupes recalculés depuis site_id, jamais depuis un site_group_id déjà réécrit :
    # relancer après la réécriture de counters.csv redonne les mêmes groupes.
    counters["site_group_id"] = site_group_key(counters)

    start = counts["ts"].min().floor("h")
    full_end = counts["ts"].max().floor("h") + pd.Timedelta(hours=1)
    sel_end = min(selection_end, full_end)
    if sel_end <= start:
        raise ValueError("La période de sélection est vide : vérifier --fin-selection.")

    sel_counts = counts[counts["ts"] < sel_end]
    sel = period_metrics(sel_counts, counters, hour_grid(start, sel_end), PERIOD_SELECTION)
    full = period_metrics(counts, counters, hour_grid(start, full_end), PERIOD_FULL)

    # Descripteurs fixes du compteur
    meta = counters[
        ["counter_id", "site_id", "site_group_id", "counter_name", "latitude", "longitude"]
        + (["direction"] if "direction" in counters else [])
    ].copy()
    meta["has_coordinates"] = meta["latitude"].notna() & meta["longitude"].notna()
    meta["dist_center_km"] = haversine_km(
        meta["latitude"], meta["longitude"], PARIS_CENTER[0], PARIS_CENTER[1]
    )
    meta["zone"] = meta["dist_center_km"].map(zone_of)
    groups = candidate_groups(counters, c.alias_distance_m, c.nearby_distance_m)
    meta = meta.merge(groups, on="site_group_id")
    # La décision de l'étape 3 : le groupe utilisé partout est le groupe candidat.
    meta["site_group_id"] = meta["candidate_group_id"]

    thresholds = {}
    for name, df in (("selection", sel), ("full", full)):
        df["volume_class"], thresholds[name] = volume_classes(df["mean_count"])
        ratios = zip(df["weekday_weekend_ratio"], df["commute_peak_ratio"])
        df["profile_type"] = [profile_type(a, b) for a, b in ratios]
    sel = sel.merge(meta, on="counter_id")
    full = full.merge(meta, on="counter_id")

    # Décision sur la seule période de sélection
    decided = sel.apply(lambda r: decide_status(r, sel_end, c), axis=1, result_type="expand")
    sel["selection_status"], sel["status_reason"] = decided[0], decided[1]
    reserved = reserve_new_sites(sel, c)
    is_res = sel["candidate_group_id"].isin(reserved)
    sel.loc[is_res, "selection_status"] = sel.loc[is_res, "candidate_group_id"].map(reserved)
    sel.loc[is_res, "status_reason"] = (
        "site entier réservé à E3 (strate volume x zone, tirage déterministe), "
        "toutes directions et alias possibles ensemble"
    )
    sel["site_role"] = sel["selection_status"].map(site_role)

    status_cols = ["counter_id", "selection_status", "status_reason", "site_role"]
    full = full.merge(sel[status_cols], on="counter_id")

    inv = pd.concat([sel, full], ignore_index=True)
    inv["uncertainties"] = inv.apply(uncertainties, axis=1)
    inv["snapshot_id"] = snapshot_id
    inv["quality_version"] = QUALITY_VERSION
    inv = inv.sort_values(["counter_id", "period_role"], ascending=[True, False], kind="stable")
    inv = inv[INVENTORY_COLUMNS].reset_index(drop=True)
    summary = selection_summary(inv, snapshot_id, c, thresholds)
    summary["network_gaps"] = network_gaps(counts, c.network_gap_share)
    return inv, summary


def network_gap_hours(
    counts: pd.DataFrame, share: float = SelectionCriteria.network_gap_share
) -> pd.DataFrame:
    """Heures où au moins `share` des compteurs actifs sont sans mesure.

    Un compteur est « actif » entre sa première et sa dernière heure observée.
    Avec la grille commune (prepare --tout), un compteur a une ligne à toutes les
    heures : avant son installation et après son arrêt, il n'est pas compté.
    Colonnes : `size` (compteurs actifs), `sum` (compteurs observés), index `ts`.
    """
    span = counts.loc[counts["is_observed"]].groupby("counter_id")["ts"].agg(["min", "max"])
    bounds = counts[["counter_id"]].join(span, on="counter_id")
    active = counts[(counts["ts"] >= bounds["min"]) & (counts["ts"] <= bounds["max"])]
    per_hour = active.groupby("ts")["is_observed"].agg(["size", "sum"])
    per_hour = per_hour[per_hour["size"] >= 10]
    return per_hour[(1 - per_hour["sum"] / per_hour["size"]) >= share]


def network_gaps(
    counts: pd.DataFrame, share: float = SelectionCriteria.network_gap_share
) -> list[dict]:
    """Périodes où presque tout le réseau est sans mesure (panne ou publication).

    Voir `network_gap_hours` pour la définition d'un compteur actif. Descriptif,
    sur tout l'instantané : sert à E4 (cas sans cible) et E5 (message), pas à la
    sélection.
    """
    missing = network_gap_hours(counts, share)
    if missing.empty:
        return []
    ts = missing.index.to_series()
    run = (ts.diff() != pd.Timedelta(hours=1)).cumsum()
    out = []
    for _, block in missing.groupby(run.to_numpy()):
        start, end = block.index[0], block.index[-1] + pd.Timedelta(hours=1)
        out.append(
            {
                "start": _iso(start),
                "end_exclusive": _iso(end),
                "start_local": start.tz_convert(TZ_LOCAL).isoformat(),
                "hours": int(len(block)),
                "min_share_missing": round(float(1 - (block["sum"] / block["size"]).max()), 3),
            }
        )
    return out


def selection_summary(inv: pd.DataFrame, snapshot_id: str, c: SelectionCriteria, thr) -> dict:
    sel = inv[inv["period_role"] == PERIOD_SELECTION]

    def groups(role: str) -> list[str]:
        return sorted(sel.loc[sel["site_role"] == role, "site_group_id"].unique().tolist())

    def counters_of(status: str) -> list[str]:
        return sorted(sel.loc[sel["selection_status"] == status, "counter_id"].tolist())

    alias = sel.groupby("candidate_group_id")["site_id"].nunique()
    return {
        "quality_version": QUALITY_VERSION,
        "snapshot_id": snapshot_id,
        "selection_period": {
            "start": _iso(sel["period_start"].iloc[0]),
            "end_exclusive": _iso(sel["period_end"].iloc[0]),
            "rule": "statuts décidés sur cette seule période (avant le test)",
        },
        "criteria": asdict(c),
        "long_zero_run_hours": LONG_ZERO_RUN_HOURS,
        "volume_tertiles_selection": thr.get("selection"),
        "n_counters": int(len(sel)),
        "n_site_groups": int(sel["site_group_id"].nunique()),
        "counters_by_status": sel["selection_status"].value_counts().sort_index().to_dict(),
        "site_groups_by_role": (
            sel.groupby("site_role")["site_group_id"].nunique().sort_index().to_dict()
        ),
        "site_groups": {
            "train": groups("S_train"),
            "dev_new": groups("S_dev_new"),
            "test_new": groups("S_test_new"),
        },
        "counters": {
            "robustness": counters_of(STATUS_ROBUSTNESS),
            "excluded": counters_of(STATUS_EXCLUDED),
        },
        "possible_alias_groups": sorted(alias[alias > 1].index.tolist()),
        "diversity": {
            col: pd.crosstab(sel[col], sel["selection_status"]).to_dict(orient="index")
            for col in ("volume_class", "zone", "profile_type")
        },
    }


# ----------------------------------------------------------------- sorties
def _iso(ts) -> str:
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S+00:00")


def inventory_table(inv: pd.DataFrame) -> pd.DataFrame:
    """Version texte conforme aux conventions CSV (booléens, dates, listes JSON)."""
    out = inv.copy()
    for col in ("period_start", "period_end", "first_observed", "last_observed"):
        out[col] = out[col].map(_iso)
    out["has_coordinates"] = out["has_coordinates"].map({True: "true", False: "false"})
    for col in ("alias_candidates", "nearby_sites_300m", "uncertainties"):
        out[col] = out[col].map(lambda v: json.dumps(v, ensure_ascii=False))
    rounding = {
        "dist_center_km": 3,
        "history_days": 3,
        "observed_days": 3,
        "missing_rate": 5,
        "missing_rate_in_span": 5,
        "long_zero_share": 5,
        "mean_count": 3,
        "median_count": 3,
        "p95_count": 3,
        "weekday_weekend_ratio": 4,
        "commute_peak_ratio": 4,
    }
    return out.round(rounding)


def counters_with_groups(counters_raw: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    """`counters.csv` (lu en texte) avec `site_group_id` = groupe candidat.

    Seule cette colonne change ; ordre des lignes et des colonnes conservé.
    """
    groups = (
        inv[inv["period_role"] == PERIOD_SELECTION]
        .set_index("counter_id")["site_group_id"]
        .astype(str)
    )
    out = counters_raw.copy()
    mapped = out["counter_id"].astype(str).map(groups)
    if mapped.isna().any():
        missing = out.loc[mapped.isna(), "counter_id"].tolist()[:5]
        raise ValueError(f"Compteurs sans groupe calculé : {missing}")
    out["site_group_id"] = mapped
    return out


def write_site_groups(counters_path: Path, inv: pd.DataFrame) -> bool:
    """Réécrit `site_group_id` dans counters.csv ; True si le fichier a changé."""
    raw = pd.read_csv(counters_path, dtype=str, keep_default_na=False)
    new = counters_with_groups(raw, inv)
    if new.equals(raw):
        return False
    new.to_csv(counters_path, index=False)
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def update_manifest(
    snapshot_id: str, paths: dict[str, Path], summary: dict, counters_path: Path | None = None
) -> Path | None:
    """Ajoute les sorties au manifeste de l'instantané s'il existe (créé par acquire).

    `counters_path` : counters.csv réécrit (site_group_id) ; son empreinte et la
    limite connue correspondante sont mises à jour.
    """
    path = data_path("manifests") / f"{snapshot_id}.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    files = [f for f in manifest.get("files", []) if f.get("role") not in paths]
    for role, p in paths.items():
        files.append({"path": relative_to_root(p), "role": role, "sha256": _sha256(p)})
    if counters_path is not None:
        rel = relative_to_root(counters_path)
        for f in files:
            if f.get("path") == rel:
                f["sha256"] = _sha256(counters_path)
                f["site_group_id"] = "candidat, réécrit par quality.py"
        manifest["known_limitations"] = [
            SITE_GROUP_RULE if str(x).startswith("site_group_id = site_id") else x
            for x in manifest.get("known_limitations", [])
        ]
        for report in (manifest.get("counters") or {}).values():
            if isinstance(report, dict) and "site_group_id_status" in report:
                report["site_group_id_status"] = "candidat, voir quality.site_group_rule"
    manifest["files"] = files
    manifest["quality"] = {
        "quality_version": QUALITY_VERSION,
        "selection_period": summary["selection_period"],
        "criteria": summary["criteria"],
        "counters_by_status": summary["counters_by_status"],
        "site_group_rule": SITE_GROUP_RULE,
        "n_site_groups": summary["n_site_groups"],
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def save_figures(inv: pd.DataFrame, out_dir: Path) -> list[Path]:
    """Distributions et carte des statuts (période de sélection)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sel = inv[inv["period_role"] == PERIOD_SELECTION]
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    panels = [
        ("mean_count", "Passages moyens par heure"),
        ("observed_days", "Jours observés (période de sélection)"),
        ("missing_rate_in_span", "Taux de manque en fonctionnement"),
        ("longest_zero_run", "Plus longue suite de zéros (h)"),
    ]
    for ax, (col, title) in zip(axes.ravel(), panels):
        ax.hist(sel[col].dropna(), bins=30, color="#4C72B0")
        ax.set_title(title)
        ax.set_ylabel("compteurs")
    fig.tight_layout()
    p1 = out_dir / "inventory_distributions.png"
    fig.savefig(p1, dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 7))
    colors = {
        STATUS_RETAINED: "#4C72B0",
        STATUS_ROBUSTNESS: "#DD8452",
        STATUS_DEV_NEW: "#55A868",
        STATUS_TEST_NEW: "#8172B3",
        STATUS_EXCLUDED: "#C44E52",
    }
    for status, color in colors.items():
        d = sel[(sel["selection_status"] == status) & (sel["has_coordinates"])]
        ax.scatter(d["longitude"], d["latitude"], s=30, c=color, label=f"{status} ({len(d)})")
    ax.set_title("Compteurs par statut (période de sélection)")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.legend(fontsize=8)
    p2 = out_dir / "inventory_map.png"
    fig.savefig(p2, dpi=120)
    plt.close(fig)
    return [p1, p2]


def print_summary(summary: dict) -> None:
    sp = summary["selection_period"]
    print(f"\n=== Inventaire {summary['snapshot_id']} ({summary['quality_version']})")
    print(f"Période de sélection : {sp['start']} -> {sp['end_exclusive']} (exclu)")
    print(f"Compteurs : {summary['n_counters']} ; groupes de sites : {summary['n_site_groups']}")
    print("Compteurs par statut :")
    for k, v in summary["counters_by_status"].items():
        print(f"  {k:<18} {v}")
    print("Groupes de sites par rôle :", summary["site_groups_by_role"])
    print("Sites réservés E3 - dev :", summary["site_groups"]["dev_new"])
    print("Sites réservés E3 - test :", summary["site_groups"]["test_new"])
    if summary["possible_alias_groups"]:
        print("Groupes candidats à alias (gardés ensemble) :", summary["possible_alias_groups"])
    print("Trous communs au réseau (heure de Paris) :")
    for gap in summary.get("network_gaps", []):
        print(f"  {gap['start_local']}  {gap['hours']} h")
    for col, table in summary["diversity"].items():
        print(f"Diversité par {col} :")
        print(pd.DataFrame(table).T.fillna(0).astype(int).to_string())


def selection_end_from_config(cli_value: str | None) -> pd.Timestamp:
    """Fin de la période de sélection = début du test (minuit local)."""
    if cli_value:
        return local_midnight_utc(cli_value)
    test_start = (load_config().get("protocol") or {}).get("test_start")
    return local_midnight_utc(str(test_start) if test_start else DEFAULT_TEST_START_LOCAL)


def run(snapshot_id: str, fin_selection: str | None = None, figures: bool = False) -> dict:
    out_dir = data_path("processed") / snapshot_id
    counts_path, counters_path = out_dir / "counts.csv", out_dir / "counters.csv"
    for p in (counts_path, counters_path):
        if not p.exists():
            raise FileNotFoundError(f"Entrée introuvable : {relative_to_root(p)} (lancer prepare)")
    criteria = SelectionCriteria.from_config(load_config().get("quality"))
    inv, summary = build_inventory(
        load_counts(counts_path),
        load_counters(counters_path),
        snapshot_id,
        selection_end_from_config(fin_selection),
        criteria,
    )
    # Avant les empreintes : à la 2e exécution, counters.csv est déjà à jour et
    # les empreintes ne changent plus (même résultat à chaque relance).
    changed = write_site_groups(counters_path, inv)
    summary["site_group_rule"] = SITE_GROUP_RULE
    summary["inputs"] = {relative_to_root(p): _sha256(p) for p in (counts_path, counters_path)}
    paths = {
        "inventory_quality": out_dir / "inventory_quality.csv",
        "selection_summary": out_dir / "selection_summary.json",
    }
    inventory_table(inv).to_csv(paths["inventory_quality"], index=False)
    paths["selection_summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    manifest = update_manifest(snapshot_id, paths, summary, counters_path)
    print_summary(summary)
    print(
        f"\ncounters.csv : site_group_id {'réécrit' if changed else 'déjà à jour'} "
        f"({summary['n_site_groups']} groupes candidats)"
    )
    written = list(paths.values()) + [counters_path] + ([manifest] if manifest else [])
    if figures:
        written += save_figures(inv, out_dir / "figures")
    print("\nFichiers :", *(f"- {relative_to_root(p)}" for p in written), sep="\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané, ex. flux-20261112")
    ap.add_argument(
        "--fin-selection",
        help="date locale AAAA-MM-JJ de fin (exclue) de la période de sélection ; "
        f"défaut : protocol.test_start ou {DEFAULT_TEST_START_LOCAL}",
    )
    ap.add_argument("--figures", action="store_true", help="enregistrer histogrammes et carte")
    args = ap.parse_args(argv)
    run(args.snapshot, args.fin_selection, args.figures)
    return 0


if __name__ == "__main__":
    sys.exit(main())

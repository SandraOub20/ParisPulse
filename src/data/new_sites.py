"""Sites réservés à E3 rendus « nouveaux » : installés il y a 1, 3 ou 7 jours - E1, Sabrina.

Décision E1 (Sabrina, 18/11/2026) : les compteurs réservés à E3 (`reserved_dev_new` et
`reserved_test_new` de inventory_quality.csv) sont présentés comme installés
récemment, avec les budgets d'historique local du plan (PLAN_PROJET.md §7 : 7 jours
en cas principal, 1 et 3 jours en approfondissement) :
- référence : fin de l'instantané (minuit, heure de Paris, après sa dernière heure) ;
- un budget par site (`candidate_group_id`) : les deux sens d'un site reçoivent le
  même ; budgets attribués à tour de rôle (1, 3, 7) dans un ordre tiré par hachage
  (reproductible), séparément pour `reserved_dev_new` et `reserved_test_new` ;
- avant l'installation fictive, chaque heure devient une heure « avant installation »
  de la grille commune : `count` et `count_raw` vides, `is_observed` et `is_scoreable`
  faux, drapeau `missing` ; `installation_date` de counters.csv = date d'installation
  fictive.

Le brut et counts.csv ne sont pas modifiés : l'historique complet se recalcule.
Limite : avec la fin de l'instantané comme référence, il n'y a aucune heure après pour
évaluer les prévisions d'E3 sur ces données.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from src.data.quality import TZ_LOCAL

BUDGET_DAYS = (1, 3, 7)  # PLAN_PROJET.md §7
RESERVED_STATUSES = ("reserved_dev_new", "reserved_test_new")
SEED = "parispulse-e1-sites-nouveaux"
NEW_SITES_VERSION = "e1-new-sites/0.1.0"


def _rank(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def assign_budgets(inventory: pd.DataFrame, budgets=BUDGET_DAYS) -> pd.DataFrame:
    """Budget (jours) de chaque compteur réservé : counter_id, status, group, budget_days."""
    sel = inventory[inventory["period_role"] == "selection"]
    sel = sel[sel["selection_status"].isin(RESERVED_STATUSES)]
    rows = []
    for status in RESERVED_STATUSES:
        part = sel[sel["selection_status"] == status]
        groups = sorted(part["candidate_group_id"].astype(str).unique(), key=_rank)
        budget_of = {g: budgets[i % len(budgets)] for i, g in enumerate(groups)}
        for r in part.itertuples():
            rows.append(
                {
                    "counter_id": str(r.counter_id),
                    "status": status,
                    "group": str(r.candidate_group_id),
                    "budget_days": budget_of[str(r.candidate_group_id)],
                }
            )
    return pd.DataFrame(rows, columns=["counter_id", "status", "group", "budget_days"])


def reference_time(counts: pd.DataFrame) -> pd.Timestamp:
    """Minuit (Paris) qui suit la dernière heure de l'instantané, en UTC."""
    end = (counts["ts"].max() + pd.Timedelta(hours=1)).tz_convert(TZ_LOCAL)
    midnight = end.normalize()
    if midnight < end:
        midnight += pd.Timedelta(days=1)
    return midnight.tz_convert("UTC")


def install_time(reference: pd.Timestamp, days: int) -> pd.Timestamp:
    """`days` jours de calendrier (Paris) avant la référence, en UTC."""
    local = reference.tz_convert(TZ_LOCAL).tz_localize(None) - pd.Timedelta(days=days)
    return local.tz_localize(TZ_LOCAL).tz_convert("UTC")


def make_new_sites(
    counts: pd.DataFrame, assignment: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Vide l'historique des compteurs réservés avant leur installation fictive.

    `counts` : colonnes `counter_id`, `ts` (UTC), `count`, `is_observed`, `is_scoreable`,
    `quality_flags` (liste), et `count_raw` si présente.
    Retourne (comptages, assignation avec date d'installation, bilan).
    """
    df = counts.copy()
    ref = reference_time(df)
    plan = assignment.copy()
    plan["installed_at"] = [install_time(ref, int(d)) for d in plan["budget_days"]]
    plan["installation_date"] = plan["installed_at"].dt.tz_convert(TZ_LOCAL).dt.date.astype(str)
    start = df["counter_id"].map(dict(zip(plan["counter_id"], plan["installed_at"])))
    before = start.notna() & (df["ts"] < start)
    n_hidden = int((before & df["is_observed"].astype(bool)).sum())
    df.loc[before, "count"] = np.nan
    if "count_raw" in df.columns:
        df.loc[before, "count_raw"] = ""
    df.loc[before, ["is_observed", "is_scoreable"]] = False
    df.loc[before, "quality_flags"] = pd.Series([["missing"]] * int(before.sum()), index=df.index[before])
    kept = df[start.notna() & ~before].groupby("counter_id")["is_observed"].sum()
    plan["observed_hours_kept"] = plan["counter_id"].map(kept).fillna(0).astype(int)
    report = {
        "new_sites_version": NEW_SITES_VERSION,
        "rule": "compteurs réservés à E3 installés 1, 3 ou 7 jours avant la fin de "
        "l'instantané ; historique antérieur vidé (brut et counts.csv intacts)",
        "reference": ref.isoformat(),
        "n_counters": int(len(plan)),
        "n_sites": int(plan["group"].nunique()),
        "counters_by_budget_days": {
            str(k): int(v) for k, v in plan["budget_days"].value_counts().sort_index().items()
        },
        "n_observed_hours_hidden": n_hidden,
    }
    return df, plan, report


def update_counters(counters: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    """counters.csv avec la date d'installation fictive des compteurs réservés."""
    out = counters.copy()
    new_date = out["counter_id"].map(dict(zip(plan["counter_id"], plan["installation_date"])))
    out["installation_date"] = new_date.fillna(out["installation_date"])
    return out

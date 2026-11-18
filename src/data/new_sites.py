"""Sites réservés à E3 rendus « nouveaux » : une version des données par budget - E1, Sabrina.

Décisions E1 (Sabrina, 18/11/2026) :
- compteurs : tous ceux réservés à E3 (`reserved_dev_new` et `reserved_test_new` de
  inventory_quality.csv), les mêmes dans chaque version ;
- une version par budget d'historique local, 1, 3 ou 7 jours (PLAN_PROJET.md §7,
  PROTOCOLE_EVALUATION.md §5 : 7 jours en cas principal, 1 et 3 en approfondissement) ;
  d'une version à l'autre, seul le budget change (« faire varier un seul facteur à la fois ») ;
- référence : première origine d'évaluation du groupe de sites, à minuit heure de Paris
  (PROTOCOLE_EVALUATION.md §3-4, proposé, non validé) : `S_dev_new` sur le bloc de
  validation (juillet-août 2026), donc 01/07/2026 ; `S_test_new` sur les origines
  d'octobre 2026, donc 01/10/2026 ;
- installation fictive = début du support local de cette origine (PROTOCOLE_EVALUATION.md
  §5) : origine - délai de publication (`protocol.publication_lag_hours`, 24 h) - budget,
  en heures écoulées. À l'origine, le site a donc exactement le budget de mesures publiées ;
- avant l'installation, chaque heure devient une heure « avant installation » de la
  grille commune : `count` et `count_raw` vides, `is_observed` et `is_scoreable` faux,
  drapeau `missing` ; `installation_date` de counters.csv = date (Paris) de
  l'installation fictive.

Limite : les données correspondent au support de la première origine. Aux origines
suivantes, le site a plus d'historique que le budget : E3 limite ses entrées au support
de chaque cas (PROTOCOLE_EVALUATION.md §5 : « accumuler des observations entre cas
changerait le budget d'information »).

Le brut et counts.csv ne sont pas modifiés : l'historique complet se recalcule.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.quality import TZ_LOCAL
from src.data.zeros import local_midnight, publication_lag_hours

BUDGET_DAYS = (1, 3, 7)  # PLAN_PROJET.md §7, PROTOCOLE_EVALUATION.md §5
RESERVED_STATUSES = ("reserved_dev_new", "reserved_test_new")
# Première origine d'évaluation (minuit, heure de Paris) : PROTOCOLE_EVALUATION.md §3-4
FIRST_ORIGIN = {"reserved_dev_new": "2026-07-01", "reserved_test_new": "2026-10-01"}
NEW_SITES_VERSION = "e1-new-sites/0.2.0"


def reserved_counters(inventory: pd.DataFrame) -> pd.DataFrame:
    """Compteurs réservés à E3 : counter_id, status, group (`candidate_group_id`)."""
    sel = inventory[inventory["period_role"] == "selection"]
    sel = sel[sel["selection_status"].isin(RESERVED_STATUSES)]
    out = pd.DataFrame(
        {
            "counter_id": sel["counter_id"].astype(str),
            "status": sel["selection_status"],
            "group": sel["candidate_group_id"].astype(str),
        }
    )
    return out.sort_values(["status", "counter_id"]).reset_index(drop=True)


def install_time(status: str, budget_days: int, lag_hours: int) -> pd.Timestamp:
    """Début du support de la première origine : origine - délai - budget (UTC)."""
    origin = local_midnight(FIRST_ORIGIN[status])
    return origin - pd.Timedelta(hours=lag_hours + 24 * budget_days)


def make_new_sites(
    counts: pd.DataFrame,
    reserved: pd.DataFrame,
    budget_days: int,
    lag_hours: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Vide l'historique des compteurs réservés avant leur installation fictive.

    `counts` : colonnes `counter_id`, `ts` (UTC), `count`, `is_observed`, `is_scoreable`,
    `quality_flags` (liste), et `count_raw` si présente.
    Retourne (comptages, compteurs avec date d'installation, bilan).
    """
    lag = publication_lag_hours() if lag_hours is None else lag_hours
    df = counts.copy()
    plan = reserved.copy()
    plan["budget_days"] = budget_days
    plan["installed_at"] = [install_time(s, budget_days, lag) for s in plan["status"]]
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
        "rule": "compteurs réservés à E3 installés au début du support local de la première "
        "origine d'évaluation (origine - délai - budget) ; historique antérieur vidé "
        "(brut et counts.csv intacts)",
        "budget_days": budget_days,
        "lag_hours": lag,
        "first_origin_local": FIRST_ORIGIN,
        "installed_at": {
            s: install_time(s, budget_days, lag).isoformat() for s in RESERVED_STATUSES
        },
        "n_counters": int(len(plan)),
        "n_sites": int(plan["group"].nunique()),
        "n_observed_hours_hidden": n_hidden,
    }
    return df, plan, report


def update_counters(counters: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    """counters.csv avec la date d'installation fictive des compteurs réservés."""
    out = counters.copy()
    new_date = out["counter_id"].map(dict(zip(plan["counter_id"], plan["installation_date"])))
    out["installation_date"] = new_date.fillna(out["installation_date"])
    return out

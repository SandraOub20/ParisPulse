"""Examen des alertes du manifeste d'un instantané - E1, Sabrina (tâche A3).

Même méthode que la fiche de Tasnim sur `flux-20261115`
(`reports/experiments/E1-alertes-manifeste.md`), automatisée pour pouvoir être lancée
sur `hist-20261117` (431 alertes selon la passation de Nihed).

Chaque alerte de `counters.<id>.alerts` est classée :

- **dst_hour_lost_network** : jour de 25 h où il manque une heure, et cette heure ne
  manque pas qu'à ce compteur (au moins `NETWORK_SHARE` des compteurs actifs sans mesure)
  -> perte à la source, rien à corriger (type A de la fiche de Tasnim) ;
- **dst_day_not_published** : jour de changement d'heure sans aucune mesure sur le
  réseau -> journée non publiée, déjà `network_gap` (type B) ;
- **dst_counter** : jour de changement d'heure incomplet pour ce compteur seulement
  -> à examiner ;
- **peak_evening_direction** : pics de semaine inattendus, mais l'autre sens du même
  site a son pic du matin entre 7 h et 9 h -> sens des trajets du soir, pas une erreur
  de fuseau (type D) ;
- **peak_low_volume** : pics inattendus sur un compteur de faible volume (moyenne
  < `low_volume_mean` de `quality.SelectionCriteria`) -> profil non interprétable ;
- **peak_broken** : pics inattendus sur un compteur dont plus de la moitié des heures
  observées sont dans de longues suites de zéros -> panne connue ;
- **peak_other**, **metadata**, **other** : à examiner à la main.

Aucune alerte n'est corrigée ici : le script range et compte, la lecture reste humaine.

Usage :
  uv run python -m src.data.alerts_review --snapshot flux-20261115
  uv run python -m src.data.alerts_review --snapshot hist-20261117
"""

from __future__ import annotations

import argparse
import json
import re
import sys

import pandas as pd

from src.common.config import data_path
from src.data.prepare import check_peaks, hourly_profile
from src.data.original import load_original_counts
from src.data.quality import TZ_LOCAL, SelectionCriteria, load_counters

NETWORK_SHARE = SelectionCriteria.network_gap_share  # seuil défini une seule fois (quality.py)
DST_RE = re.compile(r"Jour de changement d'heure (\d{4}-\d{2}-\d{2}) : (\d+)/(\d+) heures")
PEAK_RE = re.compile(r"Pics en semaine à (\d+) h et (\d+) h")

ACTIONS = {
    "dst_hour_lost_network": "aucune (perte à la source) ; à documenter pour E4",
    "dst_day_not_published": "aucune (déjà network_gap) ; journée sans cible pour E4",
    "dst_counter": "à examiner : manque propre au compteur",
    "peak_evening_direction": "aucune : sens des trajets du soir",
    "peak_low_volume": "aucune sur l'heure : volume trop faible pour situer un pic",
    "peak_broken": "aucune sur l'heure : compteur en panne (suites de zéros)",
    "peak_other": "à examiner : pic inattendu sans explication automatique",
    "metadata": "à examiner : métadonnées variables (renommage ?)",
    "other": "à examiner",
}


def manifest_alerts(manifest: dict) -> pd.DataFrame:
    rows = [
        {"counter_id": cid, "alert": a}
        for cid, c in (manifest.get("counters") or {}).items()
        for a in c.get("alerts", [])
    ]
    return pd.DataFrame(rows, columns=["counter_id", "alert"])


def active_mask(counts: pd.DataFrame) -> pd.Series:
    """Vrai entre la première et la dernière heure observée de chaque compteur."""
    seen = counts.loc[counts["is_observed"]].groupby("counter_id")["ts"].agg(["min", "max"])
    b = counts[["counter_id"]].join(seen, on="counter_id")
    return (counts["ts"] >= b["min"]) & (counts["ts"] <= b["max"])


def classify_dst(
    day: str,
    counter_id: str,
    counts: pd.DataFrame,
    active: pd.Series,
    local_dates: pd.Series | None = None,
) -> str:
    """`local_dates` : date de Paris de chaque ligne, calculée une fois par `review`."""
    if local_dates is None:
        local_dates = counts["ts"].dt.tz_convert(TZ_LOCAL).dt.date
    local_day = local_dates == pd.Timestamp(day).date()
    net = counts[local_day & active]
    by_hour = net.groupby("ts")["is_observed"].agg(["sum", "size"])
    if by_hour["sum"].sum() == 0:
        return "dst_day_not_published"
    own = net[(net["counter_id"] == counter_id) & ~net["is_observed"]]
    if own.empty:
        return "dst_counter"
    missing_share = 1 - by_hour.loc[own["ts"], "sum"] / by_hour.loc[own["ts"], "size"]
    return "dst_hour_lost_network" if (missing_share >= NETWORK_SHARE).all() else "dst_counter"


def opposite_morning_peak(counter_id: str, counters: pd.DataFrame, counts: pd.DataFrame):
    """Heure du pic du matin de l'autre sens du même site, ou None."""
    site = counters.loc[counters["counter_id"] == counter_id, "site_id"]
    if site.empty or not str(site.iloc[0]).strip():
        return None
    others = counters.loc[
        (counters["site_id"] == site.iloc[0]) & (counters["counter_id"] != counter_id),
        "counter_id",
    ]
    for oid in others:
        morning, _, _ = check_peaks(hourly_profile(counts[counts["counter_id"] == oid]))
        if morning is not None and 7 <= morning <= 9:
            return morning
    return None


def classify_peak(counter_id, counters, counts, inventory, criteria) -> str:
    row = inventory[inventory["counter_id"] == counter_id]
    if len(row) and float(row["long_zero_share"].iloc[0]) > criteria.max_long_zero_share:
        return "peak_broken"
    if opposite_morning_peak(counter_id, counters, counts) is not None:
        return "peak_evening_direction"
    if len(row) and float(row["mean_count"].iloc[0]) < criteria.low_volume_mean:
        return "peak_low_volume"
    return "peak_other"


def review(manifest, counts, counters, inventory, criteria=None) -> pd.DataFrame:
    """Une ligne par alerte : compteur, texte, catégorie, action."""
    c = criteria or SelectionCriteria()
    inv = inventory[inventory["period_role"] == "selection"] if len(inventory) else inventory
    active = active_mask(counts)
    local_dates = counts["ts"].dt.tz_convert(TZ_LOCAL).dt.date  # une seule conversion
    out = manifest_alerts(manifest)
    cats = []
    for r in out.itertuples():
        if m := DST_RE.search(r.alert):
            cats.append(classify_dst(m.group(1), r.counter_id, counts, active, local_dates))
        elif PEAK_RE.search(r.alert):
            cats.append(classify_peak(r.counter_id, counters, counts, inv, c))
        elif "valeurs distinctes de" in r.alert:
            cats.append("metadata")
        else:
            cats.append("other")
    out["category"] = cats
    out["action"] = out["category"].map(ACTIONS)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané")
    args = ap.parse_args(argv)
    folder = data_path("processed") / args.snapshot
    manifest = json.loads(
        (data_path("manifests") / f"{args.snapshot}.json").read_text(encoding="utf-8")
    )
    inventory = pd.read_csv(folder / "inventory_quality.csv", dtype={"counter_id": str})
    res = review(
        manifest,
        load_original_counts(folder / "counts.csv"),
        load_counters(folder / "counters.csv"),
        inventory,
    )
    names = dict(zip(inventory["counter_id"], inventory["counter_name"]))
    res["counter_name"] = res["counter_id"].map(names)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 120)
    print(
        f"Instantané {args.snapshot} : {len(res)} alertes sur {res['counter_id'].nunique()} compteurs"
    )
    summary = res.groupby(["category", "action"]).agg(
        alertes=("alert", "size"), compteurs=("counter_id", "nunique")
    )
    print(summary.to_string())
    todo = res[res["action"].str.startswith("à examiner")]
    print(f"\nÀ examiner à la main : {len(todo)}")
    if len(todo):
        print(todo[["counter_name", "category", "alert"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

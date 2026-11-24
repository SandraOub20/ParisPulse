"""Critère des zéros pour le statut `robustness` : comparaison de deux options - E1, Sabrina.

Tâche A2 de la passation de Nihed (17/11/2026) : sur l'historique de 3 ans, garder
« au moins une suite de zéros >= 24 h » (règle actuelle de `quality.decide_status`) ou
passer à une part d'heures en suites de zéros. Décision à prendre avec Zeineb puis E4 :
ce module ne décide rien, il montre l'effet de chaque option.

Méthode : pour chaque compteur (ligne `period_role = selection` de
inventory_quality.csv), le statut est recalculé avec `quality.decide_status`, sans
modifier `quality.py` :
- option 1 (actuelle) : la ligne telle quelle ;
- option 2 (seuil `s`) : la règle « suite de zéros » ne compte que si
  `long_zero_share > s` ; toutes les autres règles sont inchangées.

Limite : les sites réservés à E3 sont tirés parmi les groupes dont tous les compteurs
sont `retained` (`quality.reserve_groups`). Un changement de critère peut donc changer
ce tirage ; il n'est pas refait ici. Les statuts comparés sont ceux d'avant la
réservation (`retained`, `robustness`, `excluded`).

Usage :
  uv run python -m src.data.zeros_criteria --snapshot flux-20261115
  uv run python -m src.data.zeros_criteria --snapshot hist-20261117 --seuils 0.01 0.05 0.1
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

import pandas as pd

from src.common.config import data_path
from src.data.quality import (
    STATUS_DEV_NEW,
    STATUS_RETAINED,
    STATUS_TEST_NEW,
    SelectionCriteria,
    decide_status,
)

# Seuils montrés par défaut : exemples pour la discussion, aucun n'est une décision
DEFAULT_THRESHOLDS = (0.01, 0.05, 0.10)
NUMERIC = (
    "n_scoreable",
    "observed_days",
    "missing_rate_in_span",
    "long_zero_share",
    "n_long_zero_runs",
    "longest_zero_run",
    "mean_count",
)


def selection_rows(inventory: pd.DataFrame) -> pd.DataFrame:
    """Lignes de la période de sélection, typées pour `decide_status`."""
    sel = inventory[inventory["period_role"] == "selection"].copy()
    for col in NUMERIC:
        sel[col] = pd.to_numeric(sel[col], errors="coerce")
    sel["last_observed"] = pd.to_datetime(sel["last_observed"], utc=True, format="ISO8601")
    sel["period_end"] = pd.to_datetime(sel["period_end"], utc=True, format="ISO8601")
    return sel.reset_index(drop=True)


def base_status(status: str) -> str:
    """Statut avant réservation : un site réservé à E3 était `retained`."""
    return STATUS_RETAINED if status in (STATUS_DEV_NEW, STATUS_TEST_NEW) else status


def status_with(row: pd.Series, criteria: SelectionCriteria, share: float | None) -> str:
    """Statut avec l'option 1 (`share=None`) ou l'option 2 (seuil `share`)."""
    r = row.copy()
    if share is not None and not r["long_zero_share"] > share:
        r["n_long_zero_runs"] = 0  # la règle « suite de zéros » ne s'applique pas
    return decide_status(r, r["period_end"], criteria)[0]


def compare_options(
    inventory: pd.DataFrame,
    criteria: SelectionCriteria | None = None,
    thresholds=DEFAULT_THRESHOLDS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(effectifs par option, compteurs dont le statut change selon le seuil)."""
    c = criteria or SelectionCriteria()
    sel = selection_rows(inventory)
    out = sel[["counter_id", "counter_name", "selection_status", "long_zero_share"]].copy()
    out["n_long_zero_runs"] = sel["n_long_zero_runs"].astype(int)
    out["base_status"] = sel["selection_status"].map(base_status)
    out["option_1"] = [status_with(r, c, None) for _, r in sel.iterrows()]
    for s in thresholds:
        out[f"option_2_{s:g}"] = [status_with(r, c, s) for _, r in sel.iterrows()]
    options = ["option_1"] + [f"option_2_{s:g}" for s in thresholds]
    summary = pd.DataFrame({o: out[o].value_counts() for o in options}).fillna(0).astype(int)
    summary.insert(0, "inventaire", out["base_status"].value_counts())
    summary = summary.fillna(0).astype(int)
    changed = out[(out[options].nunique(axis=1) > 1)]
    return summary, changed.sort_values("long_zero_share", ascending=False)


def criteria_from_manifest(manifest: dict) -> SelectionCriteria:
    """Critères enregistrés dans le manifeste (ceux qui ont produit l'inventaire)."""
    saved = (manifest.get("quality") or {}).get("criteria") or {}
    names = {f.name for f in dataclasses.fields(SelectionCriteria)}
    return SelectionCriteria(**{k: v for k, v in saved.items() if k in names})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="identifiant d'instantané")
    ap.add_argument("--seuils", type=float, nargs="+", default=list(DEFAULT_THRESHOLDS))
    args = ap.parse_args(argv)
    inventory = pd.read_csv(
        data_path("processed") / args.snapshot / "inventory_quality.csv",
        dtype={"counter_id": str},
    )
    manifest_path = data_path("manifests") / f"{args.snapshot}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary, changed = compare_options(inventory, criteria_from_manifest(manifest), args.seuils)
    print(f"Instantané {args.snapshot} : statuts avant réservation des sites E3")
    print(summary.to_string())
    print("\nCompteurs dont le statut dépend de l'option :")
    print(changed.to_string(index=False) if len(changed) else "aucun")
    print(
        "\nOption 1 = règle actuelle (au moins une suite >= 24 h). Option 2_s = règle "
        "appliquée seulement si la part d'heures en suites de zéros dépasse s. "
        "Le tirage des sites réservés n'est pas refait."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Contrôles à la réception d'une livraison E1.

uv run python -m src.eval.checks.check_e1 [--old inventory_quality_précédent.csv]
"""

import argparse
import hashlib
import json

import pandas as pd

from src.common.config import ROOT, load_config

cfg = load_config()
snapshot = cfg["snapshot_id"]
DATA = ROOT / cfg["paths"]["processed"] / snapshot

ap = argparse.ArgumentParser()
ap.add_argument("--old", help="inventory_quality.csv de la livraison précédente")
args = ap.parse_args()


def say(ok, text):
    print(("OK  " if ok else "!!  ") + text)


print(f"livraison {snapshot}\n")
print("1. Données traitées conformes au manifeste d'E1")
manifest = json.loads(
    (ROOT / cfg["paths"]["manifests"] / f"{snapshot}.json").read_text(encoding="utf-8")
)
for f in manifest["files"]:
    p = ROOT / f["path"]
    if (
        f["path"].startswith(cfg["paths"]["processed"]) and p.exists()
    ):  # seulement les données qu'on utilise
        say(hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"], f["path"])

print("\n2. Vérité de scoring")
counts = pd.read_csv(
    DATA / "counts.csv", dtype={"counter_id": str, "is_observed": str, "is_scoreable": str}
)
observed = counts["is_observed"].str.lower() == "true"
scoreable = counts["is_scoreable"].str.lower() == "true"
n = counts.duplicated(["counter_id", "timestamp"]).sum()
say(n == 0, f"clé (counter_id, timestamp) en double : {n}")
n = (scoreable & ~observed).sum()
say(n == 0, f"heures scorables non observées : {n}")
raw, filled = (
    pd.to_numeric(counts["count_raw"], errors="coerce"),
    pd.to_numeric(counts["count"], errors="coerce"),
)
n = (scoreable & (raw != filled)).sum()
say(n == 0, f"heures scorables où count != count_raw : {n}")

print("\n3. Rôles des compteurs depuis la livraison précédente")
if args.old:
    quality = pd.read_csv(DATA / "inventory_quality.csv", dtype=str)
    old = pd.read_csv(args.old, dtype=str)
    old = old[old["period_role"] == "selection"].set_index("counter_id")["site_role"]
    new = quality[quality["period_role"] == "selection"].set_index("counter_id")["site_role"]
    changed = [(c, old[c], new[c]) for c in old.index.intersection(new.index) if old[c] != new[c]]
    say(not changed, f"compteurs dont le rôle a changé : {len(changed)}")
    for c in changed:
        print("   ", c)
else:
    print("    --old non fourni")

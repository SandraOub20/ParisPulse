"""Contrôles à la réception d'une livraison E1.

uv run python -m src.eval.checks.check_e1 [--old inventory_quality_précédent.csv]
"""

import argparse
import json

import pandas as pd

from src.eval.utils import PROCESSED, ROOT, SNAPSHOT_ID, cfg, say, sha256


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", help="inventory_quality.csv de la livraison précédente")
    args = ap.parse_args()

    print(f"livraison {SNAPSHOT_ID}\n")
    print("1. Données traitées conformes au manifeste d'E1")
    manifest = json.loads(
        (ROOT / cfg["paths"]["manifests"] / f"{SNAPSHOT_ID}.json").read_text(encoding="utf-8")
    )
    for f in manifest["files"]:
        p = ROOT / f["path"]
        if (
            f["path"].startswith(cfg["paths"]["processed"]) and p.exists()
        ):  # seulement ce qu'on utilise
            say(sha256(p) == f["sha256"], f["path"])

    print("\n2. Vérité de scoring")
    counts = pd.read_csv(
        PROCESSED / "counts.csv", dtype={"counter_id": str, "is_observed": str, "is_scoreable": str}
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
    if not args.old:
        print("    --old non fourni")
        return
    quality = pd.read_csv(PROCESSED / "inventory_quality.csv", dtype=str)
    old = pd.read_csv(args.old, dtype=str)
    old = old[old["period_role"] == "selection"].set_index("counter_id")["site_role"]
    new = quality[quality["period_role"] == "selection"].set_index("counter_id")["site_role"]
    changed = [(c, old[c], new[c]) for c in old.index.intersection(new.index) if old[c] != new[c]]
    say(not changed, f"compteurs dont le rôle a changé : {len(changed)}")
    for c in changed:
        print("   ", c)


if __name__ == "__main__":
    main()

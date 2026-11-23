"""Fonctions communes aux scripts E4"""

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from src.common.config import ROOT, load_config

cfg = load_config()
PROTOCOL_ID = cfg["protocol"]["id"]
SNAPSHOT_ID = cfg["snapshot_id"]
PROCESSED = ROOT / cfg["paths"]["processed"] / str(SNAPSHOT_ID)
EVALUATION = ROOT / cfg["paths"]["evaluation"] / str(PROTOCOL_ID)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def say(ok, text):
    print(("OK  " if ok else "!!  ") + text)


def load_cases():
    return pd.read_csv(EVALUATION / "cases.csv", dtype=str)


def load_counts(columns):
    return pd.read_csv(PROCESSED / "counts.csv", usecols=columns, dtype={"counter_id": str})


def expected_cases(cases, delivered_ids):
    """Cas attendus : ceux de cases.csv de même population (scénario, rôle, période) que les cas livrés."""
    population = ["scenario", "spatial_role", "temporal_split"]
    delivered = cases[cases["case_id"].isin(delivered_ids)][population].drop_duplicates()
    return cases.merge(delivered, on=population)


def write_manifest(path, script, inputs, outputs, **extra):
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": script,
        "snapshot_id": SNAPSHOT_ID,
        "protocol_id": PROTOCOL_ID,
        **extra,
        "inputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in inputs},
        "outputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in outputs},
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

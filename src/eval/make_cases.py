"""Génère cases.csv à partir de config/project.yaml et de la livraison E1.

    uv run python -m src.eval.make_cases
"""
import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from src.common.config import ROOT, load_config

cfg = load_config()
proto = cfg["protocol"]
SNAPSHOT_ID = cfg["snapshot_id"]
PROTOCOL_ID = proto["id"]
LAG = proto["publication_lag_hours"]
BUDGETS = proto["local_budget_hours"]
PERIODS = {
    "validation": (str(proto["train_until"]), str(proto["validation_until"])),
    "test": (str(proto["test_start"]), str(proto["test_end"])),
}
# rôle du site (E1) -> (scénario, périodes évaluées)
ROLES = {
    "S_train": ("known_site", ["validation", "test"]),
    "S_dev_new": ("new_site", ["validation"]),
    "S_test_new": ("new_site", ["test"]),
}
COLUMNS = [
    "case_id", "counter_id", "site_group_id", "origin", "scenario",
    "temporal_split", "spatial_role", "local_budget_hours", "support_start",
    "support_end", "protocol_id", "snapshot_id",
]
DATA = ROOT / cfg["paths"]["processed"] / str(SNAPSHOT_ID)
OUT = ROOT / cfg["paths"]["evaluation"] / str(PROTOCOL_ID)


def get_origins(start, end):
    """Un minuit heure de Paris par jour, en UTC."""
    days = pd.date_range(start, end, freq="D")
    return days.tz_localize(cfg["timezone"]).tz_convert("UTC")


def to_text(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def make_case_id(counter_id, origin, scenario, budget):
    b = "" if budget is None else f"_b{budget}"
    return f"{counter_id}_{origin:%Y%m%dT%H}_{scenario}{b}"


def build_cases(selected, counters):
    rows = []
    for _, c in selected.iterrows():
        scenario, splits = ROLES[c["site_role"]]
        for split in splits:
            for origin in get_origins(*PERIODS[split]):
                for budget in (BUDGETS if scenario == "new_site" else [None]):
                    start = end = ""
                    if budget is not None:
                        last = origin - pd.Timedelta(hours=LAG)
                        start, end = to_text(last - pd.Timedelta(hours=budget)), to_text(last)
                    rows.append({
                        "case_id": make_case_id(c["counter_id"], origin, scenario, budget),
                        "counter_id": c["counter_id"],
                        "origin": to_text(origin),
                        "scenario": scenario,
                        "temporal_split": split,
                        "spatial_role": c["site_role"],
                        "local_budget_hours": "" if budget is None else budget,
                        "support_start": start,
                        "support_end": end,
                        "protocol_id": PROTOCOL_ID,
                        "snapshot_id": SNAPSHOT_ID,
                    })
    cases = pd.DataFrame(rows).merge(counters[["counter_id", "site_group_id"]], on="counter_id", how="left")
    return cases[COLUMNS]


def check_cases(cases, e1_groups, last_data):
    """Chaque valeur doit être 0."""
    reserved = set(e1_groups["dev_new"]) | set(e1_groups["test_new"])
    train = cases[cases["spatial_role"] == "S_train"]
    last_target = pd.to_datetime(cases["origin"], utc=True) + pd.Timedelta(hours=23)
    problems = {
        "case_id en double": cases["case_id"].duplicated().sum(),
        "site_group_id vide": cases["site_group_id"].isna().sum(),
        "groupes à plusieurs rôles": (cases.groupby("site_group_id")["spatial_role"].nunique() > 1).sum(),
        "cas S_train dans un groupe réservé": train["site_group_id"].isin(reserved).sum(),
        "cas dont les 24 h dépassent les données": (last_target > last_data).sum(),
    }
    for name, value in problems.items():
        print(("OK  " if value == 0 else "!!  ") + f"{name}: {int(value)}")
    return problems


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    assert SNAPSHOT_ID, "snapshot_id est vide dans config/project.yaml"
    quality = pd.read_csv(DATA / "inventory_quality.csv", dtype=str)
    counters = pd.read_csv(DATA / "counters.csv", dtype=str)
    e1_groups = json.loads((DATA / "selection_summary.json").read_text(encoding="utf-8"))["site_groups"]
    last_data = pd.to_datetime(pd.read_csv(DATA / "counts.csv", usecols=["timestamp"])["timestamp"], utc=True).max()

    selected = quality[(quality["period_role"] == "selection") & (quality["selection_status"] != "excluded")]
    print(f"{PROTOCOL_ID} (statut : {proto['status']}) sur {SNAPSHOT_ID}")
    print(len(selected), "compteurs :", selected["site_role"].value_counts().to_dict())

    cases = build_cases(selected, counters)
    print(len(cases), "cas\n")
    problems = check_cases(cases, e1_groups, last_data)
    assert not any(problems.values()), "un contrôle a échoué : cases.csv n'est pas écrit"
    print(cases.groupby(["scenario", "temporal_split", "local_budget_hours"], dropna=False).size().to_string())

    OUT.mkdir(parents=True, exist_ok=True)
    cases.to_csv(OUT / "cases.csv", index=False)
    inputs = ["inventory_quality.csv", "counters.csv", "selection_summary.json", "counts.csv"]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "src/eval/make_cases.py",
        "snapshot_id": SNAPSHOT_ID,
        "protocol_id": PROTOCOL_ID,
        "periods": PERIODS,
        "publication_lag_hours": LAG,
        "budgets": BUDGETS,
        "n_cases": len(cases),
        "last_data_timestamp": str(last_data),
        "inputs_sha256": {name: sha256(DATA / name) for name in inputs},
        "cases_sha256": sha256(OUT / "cases.csv"),
    }
    (OUT / "cases_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("\nécrit :", OUT / "cases.csv")

"""GABARIT À COMPLÉTER - E4 avec E1/E2/E3

Fixer les cas attendus et les informations autorisées.

Entrées et sorties : voir doc/CONTRATS.md et doc/templates/.

À faire :
1. Proposer périodes, origines, sites entiers réservés et budgets locaux.
2. Faire valider le protocole par le professeur avant les comparaisons de sélection.
3. Écrire data/evaluation/<protocol_id>/cases.csv avant de connaître la réussite des méthodes.
4. Vérifier coupures, disponibilité, fenêtres chevauchantes et conservation du test final.

Aucune implémentation fournie ; ce fichier contient uniquement des consignes.

New:
Protocole E4 : génère cases.csv, la liste des cas attendus (compteur, origine, budget local).

uv run python -m src.eval.protocol
"""

import json

import pandas as pd

from src.eval.utils import (
    EVALUATION,
    PROCESSED,
    PROTOCOL_ID,
    ROOT,
    SNAPSHOT_ID,
    cfg,
    say,
    write_manifest,
)

proto = cfg["protocol"]
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
]  # fmt: skip


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
                for budget in BUDGETS if scenario == "new_site" else [None]:
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
                    })  # fmt: skip
    cases = pd.DataFrame(rows).merge(
        counters[["counter_id", "site_group_id"]], on="counter_id", how="left"
    )
    return cases[COLUMNS]


def check_cases(cases, e1_groups, last_data):
    """Chaque valeur doit être 0."""
    reserved = set(e1_groups["dev_new"]) | set(e1_groups["test_new"])
    train = cases[cases["spatial_role"] == "S_train"]
    last_target = pd.to_datetime(cases["origin"], utc=True) + pd.Timedelta(hours=23)
    problems = {
        "case_id en double": cases["case_id"].duplicated().sum(),
        "site_group_id vide": cases["site_group_id"].isna().sum(),
        "groupes à plusieurs rôles": (
            cases.groupby("site_group_id")["spatial_role"].nunique() > 1
        ).sum(),
        "cas S_train dans un groupe réservé": train["site_group_id"].isin(reserved).sum(),
        "cas dont les 24 h dépassent les données": (last_target > last_data).sum(),
    }
    for name, value in problems.items():
        say(value == 0, f"{name}: {int(value)}")
    return problems


def main():
    assert SNAPSHOT_ID, "snapshot_id est vide dans config/project.yaml"
    quality = pd.read_csv(PROCESSED / "inventory_quality.csv", dtype=str)
    counters = pd.read_csv(PROCESSED / "counters.csv", dtype=str)
    e1_groups = json.loads((PROCESSED / "selection_summary.json").read_text(encoding="utf-8"))[
        "site_groups"
    ]
    last_data = pd.to_datetime(
        pd.read_csv(PROCESSED / "counts.csv", usecols=["timestamp"])["timestamp"], utc=True
    ).max()

    selected = quality[
        (quality["period_role"] == "selection") & (quality["selection_status"] != "excluded")
    ]
    print(f"{PROTOCOL_ID} (statut : {proto['status']}) sur {SNAPSHOT_ID}")
    print(len(selected), "compteurs :", selected["site_role"].value_counts().to_dict())

    cases = build_cases(selected, counters)
    print(len(cases), "cas\n")
    problems = check_cases(cases, e1_groups, last_data)
    assert not any(problems.values()), "un contrôle a échoué : cases.csv n'est pas écrit"
    print(
        cases.groupby(["scenario", "temporal_split", "local_budget_hours"], dropna=False)
        .size()
        .to_string()
    )

    EVALUATION.mkdir(parents=True, exist_ok=True)
    cases.to_csv(EVALUATION / "cases.csv", index=False)
    write_manifest(
        EVALUATION / "cases_manifest.json",
        "src/eval/protocol.py",
        inputs=[PROCESSED / n for n in ("inventory_quality.csv", "counters.csv", "selection_summary.json", "counts.csv")],
        outputs=[EVALUATION / "cases.csv"],
        periods=PERIODS, publication_lag_hours=LAG, budgets=BUDGETS,
        n_cases=len(cases), last_data_timestamp=str(last_data),
    )  # fmt: skip
    print("\nécrit :", (EVALUATION / "cases.csv").relative_to(ROOT))


if __name__ == "__main__":
    main()

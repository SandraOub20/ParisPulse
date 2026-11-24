"""Contrat d'échange d'un cas interactif entre E4 et les moteurs de prévision."""

from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import date

import pandas as pd

from src.models.schemas import Case, Scenario

LOCAL_TZ = "Europe/Paris"
E3_ROLES = {"S_dev_new", "S_test_new"}
CASE_COLUMNS = (
    "case_id",
    "counter_id",
    "site_group_id",
    "origin",
    "scenario",
    "temporal_split",
    "spatial_role",
    "local_budget_hours",
    "support_start",
    "support_end",
    "protocol_id",
    "snapshot_id",
)


def forecasting_team(case: Case) -> str:
    """Déterminer le moteur à partir du scénario et du rôle spatial du cas."""
    if case.scenario == "known_site" and case.spatial_role == "S_train":
        return "E2"
    if case.scenario == "new_site" and case.spatial_role in E3_ROLES:
        return "E3"
    raise ValueError("Le scénario du cas ne correspond pas au rôle spatial du compteur.")


def interactive_case(
    counter_id: str,
    site_group_id: str | None,
    spatial_role: str,
    day: date,
    snapshot_id: str,
    *,
    local_budget_hours: int | None = None,
    publication_lag_hours: int = 0,
) -> Case:
    """Générer un cas technique indépendant de tout résultat de prévision."""
    origin = pd.Timestamp(day).tz_localize(LOCAL_TZ).tz_convert("UTC")
    identifier = f"tech-{snapshot_id}-{counter_id}-{origin:%Y%m%dT%H%MZ}"
    scenario: Scenario = "new_site" if local_budget_hours is not None else "known_site"
    support_start, support_end = None, None
    if local_budget_hours is not None:
        if local_budget_hours <= 0 or publication_lag_hours < 0:
            raise ValueError("Budget local positif et délai de publication positif ou nul requis.")
        identifier += f"-new-b{local_budget_hours}"
        support_end = origin - pd.Timedelta(hours=publication_lag_hours)
        support_start = support_end - pd.Timedelta(hours=local_budget_hours)
    case = Case(
        case_id=identifier,
        counter_id=counter_id,
        site_group_id=site_group_id,
        origin=origin,
        scenario=scenario,
        protocol_id="technique-e5",
        snapshot_id=snapshot_id,
        temporal_split="technical",
        spatial_role=spatial_role,
        local_budget_hours=local_budget_hours,
        support_start=support_start,
        support_end=support_end,
    )
    forecasting_team(case)
    return case


def case_csv(case: Case) -> str:
    """Sérialiser le cas sélectionné au format E4, sans observation ni prévision."""
    row = asdict(case)
    for name in ("origin", "support_start", "support_end"):
        if row[name] is not None:
            row[name] = row[name].tz_convert("UTC").isoformat()
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CASE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue()

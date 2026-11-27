"""Générer les cas E3 utilisés par l'application E5."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/evaluation/proto-v1/cases.csv"
DESTINATION = ROOT / "src/app/cases-app.csv"

BUDGETS = (24, 72, 168)
KEYS = ["counter_id", "site_group_id"]


def main():
    # Charger les cas officiels de l'équipe 4.
    cases = pd.read_csv(
        SOURCE,
        dtype=str,
        keep_default_na=False,
    )

    # Conserver uniquement les nouveaux sites.
    cases = cases.loc[cases["scenario"].eq("new_site")].copy()

    if cases.empty:
        raise ValueError("Aucun cas E3 disponible.")

    cases["local_budget_hours"] = pd.to_numeric(
        cases["local_budget_hours"],
        errors="raise",
    )

    # Identifier chaque couple compteur-site.
    pairs = cases[KEYS].drop_duplicates().sort_values(KEYS).reset_index(drop=True)

    # Répartir les trois budgets de façon déterministe.
    pairs["local_budget_hours"] = [BUDGETS[i % len(BUDGETS)] for i in range(len(pairs))]

    # Garder les cas officiels correspondant au budget attribué.
    selected = cases.merge(
        pairs,
        on=KEYS + ["local_budget_hours"],
        how="inner",
    )

    # Vérifier que chaque couple est représenté.
    if len(selected[KEYS].drop_duplicates()) != len(pairs):
        raise ValueError("Certains couples ne possèdent pas le budget attribué.")

    # Vérifier qu'un seul budget existe par couple.
    budget_counts = selected.groupby(KEYS)["local_budget_hours"].nunique()

    if not budget_counts.eq(1).all():
        raise ValueError("Plusieurs budgets détectés pour un même couple.")

    # Conserver les identifiants et les dates officiels.
    selected = selected.sort_values(KEYS + ["origin", "case_id"])

    selected.to_csv(DESTINATION, index=False)

    print("Fichier généré :", DESTINATION)
    print("Nombre de couples :", len(pairs))
    print("Nombre de cas :", len(selected))

    print("\nRépartition des budgets :")
    print(pairs["local_budget_hours"].value_counts().sort_index())

    print("\nCorrespondance compteur-site-budget :")
    print(pairs.to_string(index=False))


if __name__ == "__main__":
    main()

from pathlib import Path

import pandas as pd

from src.models.known.predict import (
    counts_history_loader,
    error_result,
    write_predictions,
    write_runs,
)
from src.models.new.predict import predict_24h
from src.models.schemas import Case

snapshot_id = "hist-20261117"
METHOD_RUN_ID = "e3-chronos-2-adapted-v2"
cases_path = Path("data/evaluation/proto-v1/cases.csv")
cases = pd.read_csv(cases_path, dtype=str, keep_default_na=False)

# Validation E3 sur les nouveaux sites, pour les budgets d'un, trois et sept jours.
selection = cases[
    (cases["scenario"] == "new_site")
    & (cases["spatial_role"] == "S_dev_new")
    & (cases["temporal_split"] == "validation")
].copy()
if selection.empty:
    raise ValueError("Aucun cas de validation S_dev_new aux budgets 24 h, 72 h ou 168 h.")

if selection["snapshot_id"].ne(snapshot_id).any():
    snapshots = sorted(selection["snapshot_id"].unique())
    raise ValueError(f"Les cas doivent utiliser {snapshot_id}; snapshots trouvés : {snapshots}")

budget_counts = selection["local_budget_hours"].value_counts().sort_index()
print(f"Cas de validation sélectionnés : {len(selection)}")
print("Cas par budget (heures) :", budget_counts.to_dict())

history_loader = counts_history_loader(snapshot_id)
results = []
for position, (_, row) in enumerate(selection.iterrows(), start=1):
    case = Case.from_row(row)
    try:
        history = history_loader(case.counter_id)
        result = predict_24h(
            case,
            history,
            variant="adapted",
            model_name="chronos-2",
        )
    except Exception as exc:
        result = error_result(case, METHOD_RUN_ID, "adapted", exc)
        print(f"Échec {case.case_id} : {type(exc).__name__}: {exc}")
    results.append(result)

    if position % 25 == 0 or position == len(selection):
        complete = sum(item.is_complete() for item in results)
        print(f"Progression : {position}/{len(selection)} cas; {complete} prévisions complètes")

output_dir = Path("data/prediction_results/EXP-E3")
output_stem = "e3-chronos-2-adapted-v2-validation-b24-b72-b168"
pred_path = write_predictions(results, output_dir / f"{output_stem}.pred.csv")
runs_path = write_runs(results, output_dir / f"{output_stem}.runs.csv")
print(f"Prévisions : {pred_path}")
print(f"Exécutions : {runs_path}")

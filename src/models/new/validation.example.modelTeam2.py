from pathlib import Path

import pandas as pd

from src.common.config import data_path
from src.models.known.predict import (
    counts_history_loader,
    error_result,
    write_predictions,
    write_runs,
)
from src.models.new.predict import predict_24h
from src.models.schemas import Case

SNAPSHOT_ID = "hist-20261117"
BUDGET_HOURS = 168 # model team2 support 84h de mesure au moin donc on part sur une semaine (7jour)
MODEL_NAME = "team2"
METHOD_RUN_ID = "e3-team3-mlp-frozen-v1"
CASES_PATH = Path("data/evaluation/proto-v1/cases.csv")

cases = pd.read_csv(CASES_PATH, dtype=str, keep_default_na=False)
budget_hours = pd.to_numeric(cases["local_budget_hours"], errors="coerce")
selection = cases.loc[
    (cases["scenario"] == "new_site")
    & (cases["spatial_role"] == "S_dev_new")
    & (cases["temporal_split"] == "validation")
    & budget_hours.eq(BUDGET_HOURS)
].copy()
if selection.empty:
    raise ValueError(
        "Aucun cas de validation S_dev_new avec un budget local de 168 heures."
    )

if selection["snapshot_id"].ne(SNAPSHOT_ID).any():
    snapshots = sorted(selection["snapshot_id"].unique())
    raise ValueError(f"Les cas doivent utiliser {SNAPSHOT_ID}; snapshots trouvés : {snapshots}")

print(f"Cas de validation sélectionnés (budget {BUDGET_HOURS} h) : {len(selection)}")

context_path = data_path("processed") / SNAPSHOT_ID / "context.csv"
if not context_path.exists():
    raise FileNotFoundError(f"Contexte introuvable : {context_path}")
context = pd.read_csv(context_path, dtype=str)
history_loader = counts_history_loader(SNAPSHOT_ID)

results = []
for position, (_, row) in enumerate(selection.iterrows(), start=1):
    case = Case.from_row(row)
    try:
        history = history_loader(case.counter_id)
        result = predict_24h(
            case,
            history,
            variant="frozen",
            model_name=MODEL_NAME,
            context=context,
        )
    except Exception as exc:
        result = error_result(case, METHOD_RUN_ID, "frozen", exc)
        print(f"Échec {case.case_id} : {type(exc).__name__}: {exc}")
    results.append(result)

    if position % 25 == 0 or position == len(selection):
        complete = sum(item.is_complete() for item in results)
        print(f"Progression : {position}/{len(selection)} cas; {complete} prévisions complètes")

output_dir = Path("data/prediction_results/EXP-E3")
suffix = f"validation-b-{BUDGET_HOURS}"
pred_path = write_predictions(
    results,
    output_dir / f"{METHOD_RUN_ID}-{suffix}.pred.csv",
)
runs_path = write_runs(
    results,
    output_dir / f"{METHOD_RUN_ID}-{suffix}.runs.csv",
)
print(f"Prévisions : {pred_path}")
print(f"Exécutions : {runs_path}")

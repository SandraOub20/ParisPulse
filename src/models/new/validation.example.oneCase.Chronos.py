"""Lancer Chronos-2 sur le premier cas de validation E3 uniquement."""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.known.predict import (  # noqa: E402
    counts_history_loader,
    error_result,
    write_predictions,
    write_runs,
)
from src.models.new.predict import predict_24h  # noqa: E402
from src.models.schemas import Case  # noqa: E402

SNAPSHOT_ID = "hist-20261117"
METHOD_RUN_ID = "e3-chronos-2-frozen-v1"
CASES_PATH = PROJECT_ROOT / "data/evaluation/proto-v1/cases.csv"
OUTPUT_DIR = PROJECT_ROOT / "data/prediction_results/EXP-E3"


def main() -> int:
    cases = pd.read_csv(CASES_PATH, dtype=str, keep_default_na=False)
    selection = cases[
        (cases["scenario"] == "new_site")
        & (cases["spatial_role"] == "S_dev_new")
        & (cases["temporal_split"] == "validation")
    ].copy()
    if selection.empty:
        raise ValueError("Aucun cas de validation S_dev_new dans ce fichier.")
    if selection["snapshot_id"].ne(SNAPSHOT_ID).any():
        snapshots = sorted(selection["snapshot_id"].unique())
        raise ValueError(
            f"Les cas doivent utiliser {SNAPSHOT_ID}; snapshots trouvés : {snapshots}"
        )

    row = selection.iloc[0]
    case = Case.from_row(row)
    print(f"Cas exécuté : {case.case_id}")

    history_loader = counts_history_loader(SNAPSHOT_ID)
    try:
        result = predict_24h(
            case,
            history_loader(case.counter_id),
            variant="frozen",
            model_name="chronos-2",
        )
    except Exception as exc:
        result = error_result(case, METHOD_RUN_ID, "frozen", exc)
        print(f"Échec {case.case_id} : {type(exc).__name__}: {exc}")

    output_suffix = "validation-one-case"
    pred_path = write_predictions(
        [result],
        OUTPUT_DIR / f"e3-chronos-2-frozen-v1-{output_suffix}.pred.csv",
    )
    runs_path = write_runs(
        [result],
        OUTPUT_DIR / f"e3-chronos-2-frozen-v1-{output_suffix}.runs.csv",
    )
    print(f"Prévisions : {pred_path} (24 lignes pour un cas)")
    print(f"Exécutions : {runs_path} (1 ligne)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

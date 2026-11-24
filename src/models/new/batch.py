"""Exécuter les méthodes E3 sur les cas du protocole et écrire leurs résultats."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.common.config import data_path
from src.models.known.predict import (
    counts_history_loader,
    error_result,
    write_predictions,
    write_runs,
)
from src.models.new.predict import (
    CHRONOS_MODEL_NAME,
    RUN_IDS,
    SUPPORTED_MODELS,
    TEAM2_MODEL_NAME,
    predict_24h,
)
from src.models.schemas import Case


def main(argv: list[str] | None = None) -> int:
    """Produire des prévisions E3 et leurs coûts à partir des cas d'un protocole."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--model", choices=sorted(SUPPORTED_MODELS), default=CHRONOS_MODEL_NAME)
    parser.add_argument("--variant", choices=("frozen", "adapted", "both"), default="both")
    parser.add_argument("--budget", type=int, choices=(24, 72, 168))
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--allow-test", action="store_true")
    args = parser.parse_args(argv)
    if args.split == "test" and not args.allow_test:
        parser.error("Le bloc test est réservé à la mesure finale après gel (--allow-test).")

    data = pd.read_csv(args.cases, dtype=str, keep_default_na=False)
    selected = data.loc[
        data["scenario"].eq("new_site")
        & data["snapshot_id"].eq(args.snapshot)
        & data["temporal_split"].eq(args.split)
    ]
    if args.budget is not None:
        selected = selected.loc[selected["local_budget_hours"].eq(str(args.budget))]
    if selected.empty:
        parser.error("Aucun cas E3 ne correspond à l’instantané, au bloc et au budget choisis.")
    cases = [Case.from_row(row) for row in selected.to_dict("records")]

    history_for = counts_history_loader(args.snapshot)
    context = None
    if args.model == TEAM2_MODEL_NAME:
        path = data_path("processed") / args.snapshot / "context.csv"
        context = pd.read_csv(path, dtype="string") if path.is_file() else None
    variants = ("frozen", "adapted") if args.variant == "both" else (args.variant,)
    output = data_path("predictions") / args.experiment
    for variant in variants:
        run_id = RUN_IDS[args.model].replace("-frozen-", f"-{variant}-")
        results = []
        for case in cases:
            try:
                result = predict_24h(
                    case, history_for(case.counter_id), variant, args.model, context=context
                )
            except (KeyError, TypeError, ValueError, OSError, RuntimeError) as error:
                result = error_result(case, run_id, variant, error)
            results.append(result)
        write_predictions(results, output / f"{run_id}.pred.csv")
        write_runs(results, output / f"{run_id}.runs.csv")
        adaptations = {
            item.case.case_id: {"adaptation_id": item.adaptation_id, **item.adaptation}
            for item in results
            if item.adaptation is not None
        }
        if adaptations:
            (output / f"{run_id}.adaptations.json").write_text(
                json.dumps(adaptations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
    print(f"{len(cases)} cas E3 · {', '.join(variants)} · {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

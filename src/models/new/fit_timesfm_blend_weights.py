"""Apprendre un poids de mélange par budget sur les sites de développement TimesFM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.new.adapt import (
    _TIMESFM_BLEND_WEIGHTS_PATH,
    blend_forecast,
    hourly_profile,
    profile_values,
)
from src.models.new.predict import predict_24h, prepare_inputs
from src.models.schemas import Case

GRID = np.round(np.linspace(0.0, 1.0, 21), 2)
OUT = _TIMESFM_BLEND_WEIGHTS_PATH
EXPECTED_BUDGETS = {24, 72, 168}
MODEL_NAME = "google_TimesFM_2.5"


def build_rows(cases: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    counts = counts.copy()
    counts["timestamp"] = pd.to_datetime(counts["timestamp"], utc=True)
    by_counter = {counter_id: group for counter_id, group in counts.groupby("counter_id")}
    rows = []
    skipped = 0

    for _, raw in cases.iterrows():
        case = Case.from_row(raw)
        history = by_counter.get(case.counter_id)
        if history is None:
            print(f"[skip] {case.case_id}: aucun historique pour {case.counter_id}")
            skipped += 1
            continue

        try:
            result = predict_24h(case, history, "frozen", MODEL_NAME)
            inputs, _, _ = prepare_inputs(case, history, None)
        except Exception as exc:
            print(f"[skip] {case.case_id}: {type(exc).__name__}: {exc}")
            skipped += 1
            continue

        predictions = result.predictions
        profile = profile_values(hourly_profile(inputs.history), predictions["target_timestamp"])
        actual = history.set_index("timestamp")["count"].reindex(
            pd.to_datetime(predictions["target_timestamp"], utc=True)
        )
        rows.append(
            pd.DataFrame(
                {
                    "case_id": case.case_id,
                    "site": case.site_group_id or case.counter_id,
                    "budget": case.local_budget_hours,
                    "p": predictions["y_pred"].to_numpy(dtype=float),
                    "q": profile,
                    "y": pd.to_numeric(actual, errors="coerce").to_numpy(dtype=float),
                }
            )
        )

    print(f"Cas ignorés : {skipped}")
    if not rows:
        raise ValueError("Aucune ligne de prévision évaluable n'a été produite.")
    return pd.concat(rows, ignore_index=True).dropna(subset=["y"])


def mae(predictions: np.ndarray, actuals: np.ndarray) -> float:
    return float(np.mean(np.abs(predictions - actuals)))


def rmse(predictions: np.ndarray, actuals: np.ndarray) -> float:
    return float(np.sqrt(np.mean((predictions - actuals) ** 2)))


def best_weight(rows: pd.DataFrame) -> float:
    scores = [
        mae(
            blend_forecast(rows.p.to_numpy(), rows.q.to_numpy(), weight),
            rows.y.to_numpy(),
        )
        for weight in GRID
    ]
    return float(GRID[int(np.argmin(scores))])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--counts", required=True)
    parser.add_argument("--cache", default=None)
    args = parser.parse_args()

    cache_path = Path(args.cache) if args.cache else None
    if cache_path is not None and cache_path.exists():
        rows = pd.read_csv(cache_path)
    else:
        cases = pd.read_csv(args.cases)
        cases = cases[
            (cases.scenario == "new_site") & (cases.spatial_role == "S_dev_new")
        ]
        rows = build_rows(cases, pd.read_csv(args.counts))
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            rows.to_csv(cache_path, index=False)

    available_budgets = {int(budget) for budget in rows.budget.unique()}
    missing_budgets = EXPECTED_BUDGETS - available_budgets
    if missing_budgets:
        raise ValueError(f"Aucun résultat en cache pour les budgets : {sorted(missing_budgets)}")

    weights = {}
    report = []
    per_site = []
    for budget, budget_rows in rows.groupby("budget"):
        sites = budget_rows.site.unique()
        loso = np.empty(len(budget_rows))
        for site in sites:
            test = budget_rows.site.eq(site).to_numpy()
            weight = best_weight(budget_rows.loc[~test]) if len(sites) > 1 else 1.0
            loso[test] = blend_forecast(
                budget_rows.loc[test, "p"].to_numpy(),
                budget_rows.loc[test, "q"].to_numpy(),
                weight,
            )

        actuals = budget_rows.y.to_numpy()
        frozen = budget_rows.p.to_numpy()
        profile_only = blend_forecast(frozen, budget_rows.q.to_numpy(), 0.0)
        report.append(
            {
                "budget": int(budget),
                "sites": len(sites),
                "heures": len(budget_rows),
                "MAE_frozen": mae(frozen, actuals),
                "MAE_profil": mae(profile_only, actuals),
                "MAE_blend_LOSO": mae(loso, actuals),
                "RMSE_frozen": rmse(frozen, actuals),
                "RMSE_profil": rmse(profile_only, actuals),
                "RMSE_blend_LOSO": rmse(loso, actuals),
            }
        )
        weights[str(int(budget))] = best_weight(budget_rows)

        for site in sites:
            site_rows = budget_rows.loc[budget_rows.site.eq(site)]
            site_mask = budget_rows.site.eq(site).to_numpy()
            per_site.append(
                {
                    "budget": int(budget),
                    "site": site,
                    "MAE_frozen": mae(site_rows.p.to_numpy(), site_rows.y.to_numpy()),
                    "MAE_blend_LOSO": mae(loso[site_mask], site_rows.y.to_numpy()),
                }
            )

    pd.set_option("display.float_format", "{:.2f}".format)
    print(pd.DataFrame(report).to_string(index=False))
    site_scores = pd.DataFrame(per_site)
    site_scores["delta"] = site_scores.MAE_blend_LOSO - site_scores.MAE_frozen
    print("\nPire dégradation par site (delta MAE > 0 = pire que frozen) :")
    print(site_scores.sort_values("delta", ascending=False).head(10).to_string(index=False))
    print(f"\nSites dégradés : {(site_scores.delta > 0).sum()} / {len(site_scores)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"weights": weights, "grid": GRID.tolist()}, indent=2),
        encoding="utf-8",
    )
    print(f"\nPoids écrits dans {OUT} : {weights}")


if __name__ == "__main__":
    main()

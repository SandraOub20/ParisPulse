"""Stabilité statistique, coûts et perturbation des entrées (E4)"""

import argparse

import numpy as np
import pandas as pd

import src.eval.metrics as mt
from src.eval.utils import EVALUATION, PROTOCOL_ID, ROOT, SNAPSHOT_ID, cfg

PRED_DIR = ROOT / cfg["paths"]["predictions"]


def bootstrap_stability(
    err_df: pd.DataFrame, cov_df: pd.DataFrame, budget=None, n_boot=2000, seed=42, split=None
):
    """Bootstrap sur 2 axes (compteurs x jours) sur les cas complets communs."""
    if split is not None:
        cov_df = cov_df[cov_df["temporal_split"] == split]
        err_df = err_df[err_df["case_id"].isin(cov_df["case_id"])]
    if budget is not None and "local_budget_hours" in cov_df.columns:
        cov_df = cov_df[
            pd.to_numeric(cov_df["local_budget_hours"], errors="coerce") == float(budget)
        ]
        err_df = err_df[err_df["case_id"].isin(cov_df["case_id"])]

    ok = (
        (err_df["is_scoreable"].astype(str).str.lower() == "true")
        & err_df["y_true"].notna()
        & err_df["y_pred"].notna()
    )
    e = err_df[ok].copy()
    e["abs_err"] = (pd.to_numeric(e["y_pred"]) - pd.to_numeric(e["y_true"])).abs()
    methods = sorted(e["method_run_id"].dropna().unique())
    if len(methods) < 2:
        return pd.DataFrame(), pd.DataFrame()

    # Garder uniquement les cas complets (24h) présents pour toutes les méthodes
    comp = cov_df[cov_df["is_complete_24h"].astype(str).str.lower() == "true"]
    common = comp.groupby("case_id")["method_run_id"].nunique()
    e = e[e["case_id"].isin(common[common == len(methods)].index)].copy()
    e["day"] = e["case_id"].astype(str).str.extract(r"_(\d{8}T\d{2})_")[0]

    # Matrices (compteurs x jours x méthodes) : somme des erreurs S et nb d'heures N
    counters, days = sorted(e["counter_id"].unique()), sorted(e["day"].unique())
    S = np.zeros((len(counters), len(days), len(methods)))
    N = np.zeros((len(counters), len(days), len(methods)))
    for k, m in enumerate(methods):
        sub = e[e["method_run_id"] == m]
        S[:, :, k] = (
            sub.pivot_table(index="counter_id", columns="day", values="abs_err", aggfunc="sum")
            .reindex(index=counters, columns=days)
            .fillna(0)
        )
        N[:, :, k] = (
            sub.pivot_table(index="counter_id", columns="day", values="abs_err", aggfunc="count")
            .reindex(index=counters, columns=days)
            .fillna(0)
        )

    def macro_mae(s_mat, n_mat):
        den = n_mat.sum(axis=1)
        per_counter = np.where(den > 0, s_mat.sum(axis=1) / np.where(den > 0, den, 1), np.nan)
        return np.nanmean(per_counter, axis=0)

    base = macro_mae(S, N)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        ci = rng.integers(0, len(counters), len(counters))
        di = rng.integers(0, len(days), len(days))
        boot.append(macro_mae(S[ci][:, di], N[ci][:, di]))
    boot = np.array(boot)

    pairs = [
        {
            "budget_hours": budget,
            "method_a": methods[i],
            "method_b": methods[j],
            "diff_point_a_minus_b": float(base[i] - base[j]),
            "ci95_low": float(np.percentile(boot[:, i] - boot[:, j], 2.5)),
            "ci95_high": float(np.percentile(boot[:, i] - boot[:, j], 97.5)),
            "p_a_beats_b": float(np.mean(boot[:, i] < boot[:, j])),
        }
        for i in range(len(methods))
        for j in range(i + 1, len(methods))
    ]
    rk = boot.argsort(axis=1).argsort(axis=1) + 1
    ranks = [
        {
            "budget_hours": budget,
            "method_run_id": m,
            "point_mae_macro": float(base[k]),
            **{
                f"rank_{r}_pct": float(100.0 * np.mean(rk[:, k] == r))
                for r in range(1, len(methods) + 1)
            },
        }
        for k, m in enumerate(methods)
    ]
    return pd.DataFrame(pairs), pd.DataFrame(ranks)


def build_costs(exp_id: str) -> pd.DataFrame:
    """Somme les temps d'exécution (*.runs.csv) et mesure la taille des prédictions."""
    files = [
        f
        for f in sorted((PRED_DIR / exp_id).glob("*.runs.csv"))
        if not f.name.endswith("-one-case.runs.csv")
    ]
    rows = []
    for f in files:
        df = pd.read_csv(f)
        stem = f.name.removesuffix(".runs.csv")
        pf = PRED_DIR / exp_id / f"{stem}.pred.csv"
        rows.append(
            {
                "experiment_id": exp_id,
                "method_run_id": df["method_run_id"].iloc[0] if "method_run_id" in df else stem,
                "n_rows": len(df),
                **{
                    f"total_{k}_s": pd.to_numeric(df[f"{k}_seconds"], errors="coerce").sum()
                    if f"{k}_seconds" in df
                    else np.nan
                    for k in ("preparation", "inference", "adaptation", "wait")
                },
                "pred_file_mb": round(pf.stat().st_size / 1e6, 2) if pf.exists() else np.nan,
                "protocol_id": PROTOCOL_ID,
                "snapshot_id": SNAPSHOT_ID,
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out.to_csv(EVALUATION / exp_id / "costs.csv", index=False)
    return out


def macro_by_method(sub: pd.DataFrame) -> pd.DataFrame:
    """MAE macro et erreur relative (moyenne de MAE / niveau du compteur sur les mêmes heures)."""
    keys = ["temporal_split", "method_run_id", "budget"]
    by_cnt = sub.groupby([*keys, "counter_id"], dropna=False, as_index=False).agg(
        mae=("abs_err", "mean"), mean_y=("y_true", "mean"), n_cases=("case_id", "nunique")
    )
    by_cnt = by_cnt[by_cnt["mean_y"] > 0]
    by_cnt["rel"] = by_cnt["mae"] / by_cnt["mean_y"]
    return by_cnt.groupby(keys, dropna=False, as_index=False).agg(
        n_counters=("counter_id", "nunique"),
        n_cases=("n_cases", "sum"),
        mae_macro=("mae", "mean"),
        rel_error=("rel", "mean"),
    )


def factor_tables(err_df, cases, ctx_df, qual):
    """Scores par situation (condition vraie / fausse) et par famille de compteurs."""
    scoreable = err_df["is_scoreable"].astype(str).str.lower() == "true"
    e = err_df[scoreable & err_df["y_true"].notna() & err_df["y_pred"].notna()].copy()
    e["abs_err"] = (pd.to_numeric(e["y_pred"]) - pd.to_numeric(e["y_true"])).abs()
    e["budget"] = e["case_id"].str.extract(r"_b(\d+)$")[0].astype(float)
    e = e.merge(cases[["case_id", "temporal_split"]], on="case_id", how="left")

    ctx_rows = []
    for key in mt.CONTEXT_KEYS if not ctx_df.empty else ["is_weekend"]:
        cids = set(mt.selection_cases_from_context(cases, ctx_df, key)["case_id"])
        mask = e["case_id"].isin(cids)
        for level, sub in [("True", e[mask]), ("False", e[~mask])]:
            if not sub.empty:
                ctx_rows.append(macro_by_method(sub).assign(context=key, level=level))

    fam_rows = []
    for col in ["volume_class", "profile_type", "zone", "selection_status"]:
        if col in qual.columns:
            value = e["counter_id"].map(
                qual.drop_duplicates("counter_id").set_index("counter_id")[col]
            )
            for v, sub in e.groupby(value):
                fam_rows.append(macro_by_method(sub).assign(family_type=col, family_value=v))
    return ctx_rows, fam_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("experiments", nargs="*", default=["EXP-E2", "EXP-E3"])
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()

    processed = ROOT / cfg["paths"]["processed"] / SNAPSHOT_ID
    qual = pd.read_csv(processed / "inventory_quality.csv", dtype={"counter_id": str})
    qual = qual[qual["period_role"] == "selection"]
    cases = pd.read_csv(EVALUATION / "cases.csv", dtype={"case_id": str, "counter_id": str})
    ctx_path = processed / "context.csv"
    ctx_df = pd.read_csv(ctx_path, dtype=str) if ctx_path.exists() else pd.DataFrame()

    for exp_id in args.experiments:
        exp_dir = EVALUATION / exp_id
        err_path = exp_dir / "errors.csv"
        if not err_path.exists():
            err_path = exp_dir / "errors.csv.zip"
        cov_path = exp_dir / "coverage.csv"

        if err_path.exists() and cov_path.exists():
            err_df = pd.read_csv(err_path, dtype={"counter_id": str, "case_id": str})
            cov_df = pd.read_csv(cov_path, dtype={"counter_id": str, "case_id": str})
            cov_df = cov_df.merge(cases[["case_id", "temporal_split"]], on="case_id", how="left")
            budgets = [24.0, 72.0, 168.0] if exp_id == "EXP-E3" else [None]
            pairs_all, ranks_all = [], []
            for split in sorted(cov_df["temporal_split"].dropna().unique()):
                for b in budgets:
                    p_df, r_df = bootstrap_stability(
                        err_df, cov_df, budget=b, n_boot=args.n_boot, split=split
                    )
                    if not p_df.empty:
                        pairs_all.append(p_df.assign(temporal_split=split))
                    if not r_df.empty:
                        ranks_all.append(r_df.assign(temporal_split=split))
            if pairs_all:
                pd.concat(pairs_all, ignore_index=True).to_csv(
                    exp_dir / "paired_bootstrap.csv", index=False
                )
            if ranks_all:
                pd.concat(ranks_all, ignore_index=True).to_csv(
                    exp_dir / "rank_stability.csv", index=False
                )

            ctx_rows, fam_rows = factor_tables(err_df, cases, ctx_df, qual)
            if ctx_rows:
                pd.concat(ctx_rows, ignore_index=True).to_csv(
                    exp_dir / "scores_by_context.csv", index=False
                )
            if fam_rows:
                pd.concat(fam_rows, ignore_index=True).to_csv(
                    exp_dir / "scores_by_family.csv", index=False
                )

        build_costs(exp_id)


if __name__ == "__main__":
    main()

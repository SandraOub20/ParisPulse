"""
Exécuter les cas communs et examiner la fiabilité.

1. Appeler les calculs des partenaires ou lire leurs CSV conformes.
2. Enregistrer erreurs, scores et couverture sous data/evaluation/<protocol_id>/<experiment_id>/.
3. Mesurer les coûts et une perturbation des entrées ou la couverture effective d’intervalles.
4. Transmettre un diagnostic, vérifier la correction et garder le test final pour la version figée.

"""

from pathlib import Path

import numpy as np
import pandas as pd

import src.eval.metrics as mt
from src.common.config import ROOT, load_config
from src.eval.utils import write_manifest

# CONFIGURATION
cfg = load_config()

PROTOCOLE_ID = cfg["protocol"]["id"]
SNAPSHOT_ID = cfg["snapshot_id"]
EXP_ID = ["EXP-E2", "EXP-E3"]

EVAL = ROOT / cfg["paths"]["evaluation"]
PRED = ROOT / cfg["paths"]["predictions"]
DATA = ROOT / cfg["paths"]["processed"]


# COLONNES DES FICHIERS DE SORTIE
COLUMNS_ERROR = [
    "case_id",
    "counter_id",
    "horizon",
    "target_timestamp",
    "method_run_id",
    "variant",
    "y_true",
    "y_pred",
    "is_scoreable",
    "signed_error",
    "absolute_error",
    "squared_error",
    "MAE",
    "MAPE",
    "R2",
    "RMSE",
    "protocol_id",
    "snapshot_id",
]

COLUMNS_SCORES = [
    "experiment_id",
    "scenario",
    "temporal_split",
    "method_run_id",
    "variant",
    "local_budget_hours",
    "comparison_population_id",
    "n_expected_cases",
    "n_complete_cases",
    "n_compared_cases",
    "n_compared_hours",
    "n_evaluable_counters",
    "mae_macro",
    "rmse",
    "r2",
    "bias",
    "coverage_24h",
    "n_fallback_cases",
    "protocol_id",
    "snapshot_id",
]

COLUMNS_COVERAGE = [
    "case_id",
    "counter_id",
    "origin",
    "scenario",
    "method_run_id",
    "variant",
    "local_budget_hours",
    "coverage_status",
    "n_predicted_hours",
    "is_complete_24h",
    "status_reason",
    "protocol_id",
    "snapshot_id",
]


###################################################################################################################################


# VALIDATION
def _check_forecast_file(forecast):
    """
    Vérifie que le fichier de prévisions contient
    les colonnes nécessaires à l'évaluation.
    """

    required_columns = [
        "case_id",
        "method_run_id",
        "counter_id",
        "horizon",
        "target_timestamp",
        "y_pred",
        "variant",
        "prediction_status",
    ]

    missing = set(required_columns) - set(forecast.columns)

    if missing:
        raise ValueError(f"Colonnes manquantes dans le fichier de prévisions : {sorted(missing)}")

    if forecast.empty:
        raise ValueError("Le fichier de prévisions est vide.")

    if (
        forecast["method_run_id"].isna().any()
        or forecast["method_run_id"].astype(str).str.strip().eq("").any()
        or forecast["method_run_id"].nunique(dropna=False) != 1
    ):
        raise ValueError(
            "Un fichier de prévisions doit contenir une seule méthode (method_run_id)."
        )


def _prepare_observations(cases, observations):
    """
    Sélectionne les observations correspondant aux compteurs
    des cas à évaluer.
    """

    counter_ids = cases["counter_id"].astype(str).unique()

    obs = observations[observations["counter_id"].astype(str).isin(counter_ids)].copy()

    return obs


def _get_case_groups(cases, forecast):
    """
    Associe les prévisions aux informations des cas
    afin de récupérer le scénario et le découpage temporel.
    """

    info_cols = ["case_id", "scenario", "temporal_split"]
    if "local_budget_hours" in cases.columns:
        info_cols.append("local_budget_hours")

    case_info = cases[info_cols].drop_duplicates()

    groups = forecast[["case_id", "method_run_id", "variant"]].drop_duplicates()

    groups = groups.merge(
        case_info,
        on="case_id",
        how="left",
        validate="many_to_one",
    )

    if groups[["scenario", "temporal_split"]].isna().any().any():
        raise ValueError(
            "Impossible de retrouver le scénario ou le découpage temporel de certains cas."
        )

    if "local_budget_hours" not in groups.columns:
        groups["local_budget_hours"] = np.nan

    return groups


def get_time_interval(df):
    """
    Retourne les bornes temporelles (début et fin) des origines d'un sous-ensemble de cas.
    """
    origins = pd.to_datetime(df["origin"], utc=True)
    return {
        "start": f"{origins.min():%Y%m%dT%H}",
        "end": f"{origins.max():%Y%m%dT%H}",
    }


# --------------------------------------------------------------------------------------------------------------------------------------


# ERREURS HORAIRES
def make_error(cases, forecast, observations, path):
    """
    Calcule les erreurs horaires et les métriques par cas.

    Les prévisions et observations sont alignées sur la grille
    théorique des 24 heures.

    Les métriques MAE, MAPE, R² et RMSE sont calculées par cas,
    puis ajoutées aux lignes horaires correspondantes.
    """

    _check_forecast_file(forecast)

    # cases appearing in the forecast given
    c_fc = cases.loc[cases["case_id"].isin(forecast["case_id"]), :].copy()

    # observations appearing in the forecast given
    obs_fc = _prepare_observations(c_fc, observations)

    # general evaluations
    c, p, o = mt._prepare_inputs(c_fc, forecast, obs_fc)

    evaluation = mt._build_evaluation(c, p, o)

    # general metrics
    metrics = mt.calculate_metrics_by_case(evaluation)

    # create error
    error = evaluation[
        [
            "case_id",
            "counter_id",
            "horizon",
            "expected_timestamp",
            "method_run_id",
            "variant",
            "count",
            "y_pred",
            "is_scoreable",
            "is_evaluable",
        ]
    ].copy()

    error = error.rename(
        columns={
            "expected_timestamp": "target_timestamp",
            "count": "y_true",
        }
    )

    # Ajouter les métriques calculées par cas
    metric_columns = [
        "case_id",
        "counter_id",
        "method_run_id",
        "variant",
        "MAE",
        "MAPE",
        "R2",
        "RMSE",
    ]

    error = error.merge(
        metrics[metric_columns],
        on=[
            "case_id",
            "counter_id",
            "method_run_id",
            "variant",
        ],
        how="left",
        validate="many_to_one",
    )

    # Calculer les erreurs individuelles uniquement pour les heures évaluables
    error["signed_error"] = np.nan
    error["absolute_error"] = np.nan
    error["squared_error"] = np.nan

    valid = error["is_evaluable"].fillna(False).astype(bool)

    error.loc[valid, "signed_error"] = error.loc[valid, "y_pred"] - error.loc[valid, "y_true"]

    error.loc[valid, "absolute_error"] = error.loc[valid, "signed_error"].abs()

    error.loc[valid, "squared_error"] = error.loc[valid, "signed_error"] ** 2

    # Ajouter les identifiants du protocole et du snapshot
    error["protocol_id"] = PROTOCOLE_ID
    error["snapshot_id"] = SNAPSHOT_ID

    # y_true seulement les heures réellement mesurées
    error["y_true"] = error["y_true"].where(error["is_scoreable"].fillna(False).astype(bool))
    error["is_scoreable"] = error["is_evaluable"].fillna(False).astype(bool)

    # Conserver les colonnes de sortie
    error = error[COLUMNS_ERROR]

    # create csv
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    error.to_csv(path, index=False)

    return error


# --------------------------------------------------------------------------------------------------------------------------------------


# SCORES
def make_scores(cases, forecast, observations, exp_id, path):
    """
    Calcule les scores agrégés pour chaque scénario,
    découpage temporel, méthode et variante.

    Les métriques globales sont calculées sur les heures évaluables.
    La MAE macro correspond à la moyenne des MAE calculées par compteur.
    """

    _check_forecast_file(forecast)

    # cases appearing in the forecast given
    groups = _get_case_groups(cases, forecast)

    score_results = []
    counter_results = []

    # Calculer les scores pour chaque groupe
    group_columns = [
        "scenario",
        "temporal_split",
        "method_run_id",
        "variant",
        "local_budget_hours",
    ]

    for keys, group in groups.groupby(group_columns, dropna=False):
        scenario, temp_split, method, variant, local_budget = keys

        # cases expected for the scenario, temporal split and budget
        mask = (cases["scenario"] == scenario) & (cases["temporal_split"] == temp_split)
        if "local_budget_hours" in cases.columns:
            mask = mask & (
                cases["local_budget_hours"].isna()
                if pd.isna(local_budget)
                else (cases["local_budget_hours"] == local_budget)
            )
        c_expected = cases[mask].copy()

        # population id
        time = get_time_interval(c_expected)
        budget_tag = f"_b{int(local_budget)}" if pd.notna(local_budget) else ""
        comp_popID = f"{scenario}{budget_tag}_{time['start']}-{time['end']}_self"

        # Prévisions correspondant au groupe
        case_ids = group["case_id"].unique()

        forecast_group = forecast[
            forecast["case_id"].isin(case_ids)
            & (forecast["method_run_id"] == method)
            & (forecast["variant"].fillna("").astype(str).str.strip() == variant)
        ].copy()

        # observations corresponding to the expected cases
        obs_group = _prepare_observations(c_expected, observations)

        # general evaluation
        c, p, o = mt._prepare_inputs(
            c_expected,
            forecast_group,
            obs_group,
        )

        evaluation = mt._build_evaluation(c, p, o)

        # general metrics
        valid = evaluation[evaluation["is_evaluable"].fillna(False).astype(bool)]

        # MAE macro et métriques par compteur (incluant le biais)
        metrics_counter = mt.calculate_by_counter(evaluation)

        if metrics_counter.empty:
            mae_macro = np.nan
        else:
            mae_macro = metrics_counter["MAE"].mean()
            counter_results.append(
                metrics_counter.assign(
                    experiment_id=exp_id,
                    scenario=scenario,
                    temporal_split=temp_split,
                    local_budget_hours=local_budget,
                    comparison_population_id=comp_popID,
                    protocol_id=PROTOCOLE_ID,
                    snapshot_id=SNAPSHOT_ID,
                )
            )

        # metrics complémentaires
        metrics = mt.calculate_metrics(
            valid["count"],
            valid["y_pred"],
        )

        # coverage
        coverage = mt.calculate_coverage(evaluation)

        # expected cases
        exp_c = len(c_expected)

        # completed cases
        complete_c = int(coverage["is_complete_24h"].sum())

        # coverage 24h
        cov_24 = complete_c / exp_c if exp_c > 0 else np.nan

        # compared cases
        comp_c = int(valid["case_id"].nunique())

        # evaluated counters
        eval_counters = int(valid["counter_id"].nunique())

        # fallbacks
        n_fallbacks = (
            int(
                coverage.loc[
                    coverage["n_fallback_hours"] > 0,
                    "case_id",
                ].nunique()
            )
            if "n_fallback_hours" in coverage.columns
            else 0
        )

        # assemble df
        score_results.append(
            {
                "experiment_id": exp_id,
                "scenario": scenario,
                "temporal_split": temp_split,
                "method_run_id": method,
                "variant": variant,
                "local_budget_hours": local_budget,
                "comparison_population_id": comp_popID,
                "n_expected_cases": exp_c,
                "n_complete_cases": complete_c,
                "n_compared_cases": comp_c,
                "n_compared_hours": metrics["n_predictions"],
                "n_evaluable_counters": eval_counters,
                "mae_macro": mae_macro,
                "rmse": metrics["RMSE"],
                "r2": metrics["R2"],
                "bias": metrics["bias"],
                "coverage_24h": cov_24,
                "n_fallback_cases": n_fallbacks,
                "protocol_id": PROTOCOLE_ID,
                "snapshot_id": SNAPSHOT_ID,
            }
        )

    score = pd.DataFrame(
        score_results,
        columns=COLUMNS_SCORES,
    )

    counter_df = (
        pd.concat(counter_results, ignore_index=True) if counter_results else pd.DataFrame()
    )

    # make csv
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    score.to_csv(path, index=False)

    return score, counter_df


def make_common_scores(cases, forecasts_list, observations, exp_id):
    """
    Calcule les scores sur l'intersection des cas complets communs
    entre toutes les méthodes/variantes d'une même population.
    """

    all_fc = pd.concat(forecasts_list, ignore_index=True)
    all_fc = all_fc.drop_duplicates(subset=["case_id", "method_run_id", "variant", "horizon"])
    groups = _get_case_groups(cases, all_fc)
    common_results = []

    pop_cols = ["scenario", "temporal_split", "local_budget_hours"]
    for (scenario, temp_split, local_budget), pop_grp in groups.groupby(pop_cols, dropna=False):
        if len(pop_grp[["method_run_id", "variant"]].drop_duplicates()) < 2:
            continue

        mask = (cases["scenario"] == scenario) & (cases["temporal_split"] == temp_split)
        if "local_budget_hours" in cases.columns:
            mask = mask & (
                cases["local_budget_hours"].isna()
                if pd.isna(local_budget)
                else (cases["local_budget_hours"] == local_budget)
            )
        c_expected = cases[mask].copy()
        fc_pop = all_fc[all_fc["case_id"].isin(c_expected["case_id"])].copy()
        obs_pop = _prepare_observations(c_expected, observations)

        c, p, o = mt._prepare_inputs(c_expected, fc_pop, obs_pop)
        evaluation = mt._build_evaluation(c, p, o)
        coverage = mt.calculate_coverage(evaluation)
        comparable = mt.filter_common_complete_cases(evaluation, coverage)

        time = get_time_interval(c_expected)
        budget_tag = f"_b{int(local_budget)}" if pd.notna(local_budget) else ""
        comp_popID = f"{scenario}{budget_tag}_{time['start']}-{time['end']}_common_complete"

        for (method, variant), grp in comparable.groupby(
            ["method_run_id", "variant"], dropna=False
        ):
            by_cnt = mt.calculate_by_counter(grp)
            metrics = mt.calculate_metrics(grp["count"], grp["y_pred"])
            comp_c = int(grp["case_id"].nunique())

            common_results.append(
                {
                    "experiment_id": exp_id,
                    "scenario": scenario,
                    "temporal_split": temp_split,
                    "method_run_id": method,
                    "variant": variant,
                    "local_budget_hours": local_budget,
                    "comparison_population_id": comp_popID,
                    "n_expected_cases": len(c_expected),
                    "n_complete_cases": comp_c,
                    "n_compared_cases": comp_c,
                    "n_compared_hours": metrics["n_predictions"],
                    "n_evaluable_counters": int(grp["counter_id"].nunique()),
                    "mae_macro": by_cnt["MAE"].mean() if not by_cnt.empty else np.nan,
                    "rmse": metrics["RMSE"],
                    "r2": metrics["R2"],
                    "bias": metrics["bias"],
                    "coverage_24h": comp_c / len(c_expected) if len(c_expected) > 0 else np.nan,
                    "n_fallback_cases": np.nan,
                    "protocol_id": PROTOCOLE_ID,
                    "snapshot_id": SNAPSHOT_ID,
                }
            )

    return pd.DataFrame(common_results, columns=COLUMNS_SCORES)


# --------------------------------------------------------------------------------------------------------------------------------------


# COUVERTURE DES PREVISIONS
def make_coverage(cases, forecast, observations, path):
    """
    Calcule la couverture des prévisions pour chaque cas,
    méthode et variante.

    Les cas attendus sont déterminés à partir du scénario
    et du découpage temporel.
    """

    _check_forecast_file(forecast)

    # expected cases for the scenario in the forecast given
    groups = _get_case_groups(cases, forecast)

    coverage_results = []

    group_columns = [
        "scenario",
        "temporal_split",
        "method_run_id",
        "variant",
        "local_budget_hours",
    ]

    for keys, group in groups.groupby(group_columns, dropna=False):
        scenario, temp_split, method, variant, local_budget = keys

        # cases expected for the scenario, temporal split and budget
        mask = (cases["scenario"] == scenario) & (cases["temporal_split"] == temp_split)
        if "local_budget_hours" in cases.columns:
            mask = mask & (
                cases["local_budget_hours"].isna()
                if pd.isna(local_budget)
                else (cases["local_budget_hours"] == local_budget)
            )
        c_expected = cases[mask].copy()

        # Prévisions correspondant au groupe
        case_ids = group["case_id"].unique()

        forecast_group = forecast[
            forecast["case_id"].isin(case_ids)
            & (forecast["method_run_id"] == method)
            & (forecast["variant"].fillna("").astype(str).str.strip() == variant)
        ].copy()

        # observations corresponding to the expected cases
        obs_group = _prepare_observations(c_expected, observations)

        # general evaluation
        c, p, o = mt._prepare_inputs(
            c_expected,
            forecast_group,
            obs_group,
        )

        evaluation = mt._build_evaluation(c, p, o)

        # coverage based on evaluation function
        cov = mt.calculate_coverage(evaluation)

        # Ajouter les informations des cas
        coverage = c_expected.merge(
            cov[
                [
                    "case_id",
                    "coverage_status",
                    "is_complete_24h",
                    "n_predicted_hours",
                    "status_reason",
                ]
            ],
            on="case_id",
            how="left",
            validate="one_to_one",
        )

        reasons = (
            forecast_group.dropna(subset=["status_reason"])
            .groupby("case_id")["status_reason"]
            .first()
        )
        coverage["status_reason"] = coverage["case_id"].map(reasons)

        # Ajouter les identifiants du protocole et du snapshot
        coverage["protocol_id"] = PROTOCOLE_ID
        coverage["snapshot_id"] = SNAPSHOT_ID

        # Conserver les colonnes de sortie
        coverage_results.append(
            coverage.assign(
                method_run_id=method,
                variant=variant,
            )
        )

    if coverage_results:
        coverage = pd.concat(
            coverage_results,
            ignore_index=True,
        )
    else:
        coverage = pd.DataFrame(columns=COLUMNS_COVERAGE)

    # Conserver les colonnes de sortie
    coverage = coverage[COLUMNS_COVERAGE]

    # make csv
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    coverage.to_csv(path, index=False)

    return coverage


##############################################################################################################################

if __name__ == "__main__":
    # CHARGEMENT DES DONNEES
    cases_path = EVAL / PROTOCOLE_ID / "cases.csv"
    counts_path = DATA / SNAPSHOT_ID / "counts.csv"

    cases = pd.read_csv(
        cases_path,
        dtype={"case_id": str, "counter_id": str},
    )

    counts = pd.read_csv(
        counts_path,
        dtype={"counter_id": str},
    )

    # EXECUTION DES EVALUATIONS
    for e in EXP_ID:
        folder = PRED
        out = EVAL / PROTOCOLE_ID

        if e is not None:
            folder = folder / e
            out = out / e

        out.mkdir(parents=True, exist_ok=True)

        prediction_files = sorted(
            f for f in Path(folder).glob("*.pred.csv") if not f.name.endswith("-one-case.pred.csv")
        )

        if not prediction_files:
            print(f"Aucun fichier de prévisions trouvé dans {folder}.")
            continue

        all_forecasts = []
        all_errors = []
        all_scores = []
        all_coverage = []
        all_counters = []

        for f in prediction_files:
            f_df = pd.read_csv(
                f,
                dtype={
                    "case_id": str,
                    "counter_id": str,
                },
            )
            all_forecasts.append(f_df)

            print(f"\nMaking evaluation files for {f}.....\n")

            all_errors.append(make_error(cases, f_df, counts, out / "errors.csv"))
            print("Error Completed...")

            scr_df, cnt_df = make_scores(cases, f_df, counts, e, out / "scores.csv")
            all_scores.append(scr_df)
            all_counters.append(cnt_df)
            print("Scores Completed..")

            all_coverage.append(make_coverage(cases, f_df, counts, out / "coverage.csv"))
            print("Coverage Completed.")

        if all_forecasts:
            all_scores.append(make_common_scores(cases, all_forecasts, counts, e))

        output_files = {
            "errors.csv": pd.concat(all_errors, ignore_index=True),
            "scores.csv": pd.concat(all_scores, ignore_index=True),
            "coverage.csv": pd.concat(all_coverage, ignore_index=True),
            "scores_by_counter.csv": pd.concat(all_counters, ignore_index=True),
        }

        for filename, df_out in output_files.items():
            df_out.to_csv(out / filename, index=False)

        write_manifest(
            out / "scoring_manifest.json",
            "src/eval/backtest.py",
            inputs=[cases_path, counts_path, *prediction_files],
            outputs=[out / filename for filename in output_files],
            experiment_id=e,
        )

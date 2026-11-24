
import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


 #CONSTANTES
N_EXPECTED_HOURS = 24

VALID_STATUSES = {"ok", "fallback"}


#VALIDATION
def _check_columns(df, required_columns, name):
    """Vérifie que les colonnes nécessaires sont présentes."""

    missing = set(required_columns) - set(df.columns)

    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {name} : {sorted(missing)}"
        )


def _to_bool(series):
    """Convertit proprement une colonne en booléens."""

    if series.dtype == bool:
        return series

    values = series.astype(str).str.lower()

    return values.isin(["true", "1", "yes", "oui"])


def _prepare_inputs(cases, forecasts, observations):
    """
    Prépare les trois DataFrames et vérifie les doublons,
    les identifiants et les timestamps.
    """

    _check_columns(
        cases,
        ["case_id", "counter_id", "origin", "scenario"],
        "cases"
    )

    _check_columns(
        forecasts,
        [
            "case_id", "method_run_id", "counter_id",
            "horizon", "target_timestamp", "y_pred",
            "variant", "prediction_status"
        ],
        "forecasts"
    )

    _check_columns(
        observations,
        [
            "counter_id", "timestamp", "count",
            "is_observed", "is_scoreable"
        ],
        "observations"
    )

    cases = cases.copy()
    forecasts = forecasts.copy()
    observations = observations.copy()

     #Conversion des timestamps en UTC
    cases["origin"] = pd.to_datetime(
        cases["origin"], utc=True
    )

    forecasts["target_timestamp"] = pd.to_datetime(
        forecasts["target_timestamp"], utc=True
    )

    observations["timestamp"] = pd.to_datetime(
        observations["timestamp"], utc=True
    )

     #Vérification des identifiants de cas
    if cases["case_id"].duplicated().any():
        raise ValueError("Des case_id sont dupliqués dans cases.")

    unknown_cases = (
        set(forecasts["case_id"]) - set(cases["case_id"])
    )

    if unknown_cases:
        raise ValueError(
            f"Prévisions associées à des cas inconnus : {unknown_cases}"
        )

     #Vérification des doublons de prévisions
    forecast_keys = [
        "case_id", "method_run_id", "variant", "horizon"
    ]

    if forecasts.duplicated(forecast_keys).any():
        raise ValueError(
            "Des prévisions sont dupliquées pour un même "
            "cas, méthode, variante et horizon."
        )

     #Vérification des doublons d'observations
    observation_keys = ["counter_id", "timestamp"]

    if observations.duplicated(observation_keys).any():
        raise ValueError(
            "Des observations sont dupliquées pour un même "
            "compteur et timestamp."
        )

     #Vérification des horizons
    if not forecasts["horizon"].between(1, 24).all():
        raise ValueError("Les horizons doivent être compris entre 1 et 24.")

     #Conversion des indicateurs
    observations["is_observed"] = _to_bool(
        observations["is_observed"]
    )

    observations["is_scoreable"] = _to_bool(
        observations["is_scoreable"]
    )

    return cases, forecasts, observations


#CALCUL DES METRIQUES
def calculate_metrics(y_true, y_pred):
    """
    Calcule MAE, MAPE, RMSE et R².
    Seules les paires de valeurs finies sont conservées.
    Les valeurs réelles égales à zéro sont exclues du MAPE.
    """

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if len(y_true) != len(y_pred):
        raise ValueError(
            "y_true et y_pred doivent avoir la même taille."
        )

    valid = np.isfinite(y_true) & np.isfinite(y_pred)

    y_true = y_true[valid]
    y_pred = y_pred[valid]

    n = len(y_true)

    if n == 0:
        return {
            "n_predictions": 0,
            "n_mape_predictions": 0,
            "MAE": np.nan,
            "MAPE": np.nan,
            "RMSE": np.nan,
            "R2": np.nan,
            "bias": np.nan
        }

    mae = mean_absolute_error(y_true, y_pred)

    nonzero = y_true != 0

    if nonzero.any():
        mape = np.mean(
            np.abs(
                (y_true[nonzero] - y_pred[nonzero])
                / y_true[nonzero]
            )
        ) * 100
    else:
        mape = np.nan

    rmse = np.sqrt(
        mean_squared_error(y_true, y_pred)
    )

    if n >= 2 and np.var(y_true) > 0:
        r2 = r2_score(y_true, y_pred)
    else:
        r2 = np.nan

    bias = np.mean(y_pred - y_true)

    return {
        "n_predictions": n,
        "n_mape_predictions": int(nonzero.sum()),
        "MAE": mae,
        "MAPE": mape,
        "RMSE": rmse,
        "R2": r2,
        "bias": bias
    }


#CONSTRUCTION DES DONNEES D'EVALUATION
def _build_evaluation(cases, forecasts, observations):
    """
    Construit une grille de 24 heures pour chaque cas,
    méthode et variante.
    Les prévisions et observations sont alignées par timestamp.
    Une observation absente n'est jamais remplacée par zéro.
    """

    methods = forecasts[
        ["method_run_id", "variant"]
    ].drop_duplicates()

     #Associer chaque cas à chaque méthode et variante
    base = cases.assign(_key=1).merge(
        methods.assign(_key=1),
        on="_key"
    ).drop(columns="_key")

     #Créer les 24 horizons attendus
    horizons = pd.DataFrame({
        "horizon": range(1, N_EXPECTED_HOURS + 1)
    })

    evaluation = base.assign(_key=1).merge(
        horizons.assign(_key=1),
        on="_key"
    ).drop(columns="_key")

     #Timestamp théorique de chaque prévision
    evaluation["expected_timestamp"] = (
        evaluation["origin"]
        + pd.to_timedelta(
            evaluation["horizon"] - 1,
            unit="h"
        )
    )

    forecast_columns = [
        "case_id", "method_run_id", "variant", "horizon",
        "counter_id", "target_timestamp", "y_pred",
        "prediction_status", "status_reason"
    ]

    available_columns = [
        col for col in forecast_columns
        if col in forecasts.columns
    ]

     #Récupérer les prévisions correspondantes
    evaluation = evaluation.merge(
        forecasts[available_columns],
        on=["case_id", "method_run_id", "variant", "horizon"],
        how="left",
        suffixes=("", "_forecast"),
        validate="one_to_one"
    )

     #Vérifier la cohérence du compteur
    mismatch = (
        evaluation["counter_id_forecast"].notna()
        & (
            evaluation["counter_id_forecast"]
            != evaluation["counter_id"]
        )
    ) if "counter_id_forecast" in evaluation.columns else False

    if isinstance(mismatch, pd.Series) and mismatch.any():
        raise ValueError(
            "Une prévision est associée au mauvais compteur."
        )

    if "counter_id_forecast" in evaluation.columns:
        evaluation = evaluation.drop(
            columns="counter_id_forecast"
        )

     #Vérifier l'alignement temporel
    mismatch = (
        evaluation["target_timestamp"].notna()
        & (
            evaluation["target_timestamp"]
            != evaluation["expected_timestamp"]
        )
    )

    if mismatch.any():
        raise ValueError(
            "Certaines prévisions ne correspondent pas "
            "au timestamp attendu pour leur horizon."
        )

     #Associer les observations réelles
    evaluation = evaluation.merge(
        observations[
            [
                "counter_id", "timestamp", "count",
                "is_observed", "is_scoreable"
            ]
        ],
        left_on=["counter_id", "expected_timestamp"],
        right_on=["counter_id", "timestamp"],
        how="left",
        validate="many_to_one"
    )

     #Une observation absente n'est pas une observation valide
    evaluation["is_observed"] = (
        evaluation["is_observed"].fillna(False)
    )

    evaluation["is_scoreable"] = (
        evaluation["is_scoreable"].fillna(False)
    )

    evaluation["is_observed"] = _to_bool(
        evaluation["is_observed"]
    )

    evaluation["is_scoreable"] = _to_bool(
        evaluation["is_scoreable"]
    )

     #Vérifier la validité des prévisions
    evaluation["y_pred"] = pd.to_numeric(
        evaluation["y_pred"], errors="coerce"
    )

    evaluation["count"] = pd.to_numeric(
        evaluation["count"], errors="coerce"
    )

    evaluation["is_valid_prediction"] = (
        evaluation["prediction_status"].isin(VALID_STATUSES)
        & np.isfinite(evaluation["y_pred"])
        & (evaluation["y_pred"] >= 0)
    )

     #Une heure est évaluable uniquement si la prévision et l'observation réelle sont valides
    evaluation["is_evaluable"] = (
        evaluation["is_valid_prediction"]
        & evaluation["is_observed"]
        & evaluation["is_scoreable"]
        & np.isfinite(evaluation["count"])
        & (evaluation["count"] >= 0)
    )

    return evaluation


#EVALUATION PAR CAS
def evaluate_model_case(case, model, y_true, y_pred, is_scoreable):
    """
    Calcule les métriques d'un cas à partir des heures évaluables.
    Cette fonction conserve l'interface historique du gabarit.
    """

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    is_scoreable = np.asarray(is_scoreable, dtype=bool)

    if not (
        len(y_true) == len(y_pred) == len(is_scoreable)
    ):
        raise ValueError(
            "Les tableaux doivent avoir la même taille."
        )

    valid = (
        is_scoreable
        & np.isfinite(y_true)
        & np.isfinite(y_pred)
        & (y_true >= 0)
        & (y_pred >= 0)
    )

    metrics = calculate_metrics(
        y_true[valid],
        y_pred[valid]
    )

    hourly_mae = np.full(len(y_true), np.nan)
    hourly_rmse = np.full(len(y_true), np.nan)

    hourly_mae[valid] = np.abs(
        y_true[valid] - y_pred[valid]
    )

    hourly_rmse[valid] = np.abs(
        y_true[valid] - y_pred[valid]
    )

    return {
        "case": case,
        "model": model,
        "is_scoreable": is_scoreable.tolist(),
        "n_compared_hours": metrics["n_predictions"],
        "MAE": metrics["MAE"],
        "MAPE": metrics["MAPE"],
        "RMSE": metrics["RMSE"],
        "R2": metrics["R2"],
        "hourly_MAE": hourly_mae.tolist(),
        "hourly_RMSE": hourly_rmse.tolist()
    }


def calculate_metrics_by_case(evaluation):
    """
    Calcule les métriques pour chaque cas, méthode et variante.
    Les métriques sont calculées sur toutes les heures
    réellement évaluables, même si le cas est incomplet.
    """

    results = []

    group_columns = [
        "case_id", "counter_id", "method_run_id", "variant"
    ]

    for keys, group in evaluation.groupby(
        group_columns,
        dropna=False
    ):
        valid = group[group["is_evaluable"]]

        metrics = calculate_metrics(
            valid["count"],
            valid["y_pred"]
        )

        result = dict(zip(group_columns, keys))

         #Conserver le contexte du cas
        for column in [
            "scenario", "spatial_role", "origin",
            "site_group_id", "local_budget_hours"
        ]:
            if column in group.columns:
                result[column] = group.iloc[0][column]

        result.update(metrics)

        result["n_predicted_hours"] = int(
            group["is_valid_prediction"].sum()
        )

        result["n_evaluable_hours"] = len(valid)

        results.append(result)

    return pd.DataFrame(results)


#COUVERTURE DES PREVISIONS
def calculate_coverage(evaluation):
    """
    Vérifie la couverture des 24 prévisions attendues
    pour chaque cas, méthode et variante.
    La couverture concerne les prévisions, pas les observations.
    """

    results = []

    group_columns = [
        "case_id", "counter_id", "method_run_id", "variant"
    ]

    for keys, group in evaluation.groupby(
        group_columns,
        dropna=False
    ):
        n_predicted = int(
            group["is_valid_prediction"].sum()
        )

        n_fallback = int(
            (
                group["prediction_status"] == "fallback"
            ).sum()
        )

        n_missing = N_EXPECTED_HOURS - n_predicted

        is_complete = (
            n_predicted == N_EXPECTED_HOURS
        )

        if is_complete and n_fallback > 0:
            status = "fallback_complete"
        elif is_complete:
            status = "complete"
        elif n_predicted > 0:
            status = "partial"
        elif group["prediction_status"].notna().any():
            status = "error"
        else:
            status = "no_forecast"

        result = dict(zip(group_columns, keys))

        for column in [
            "scenario", "spatial_role", "origin",
            "local_budget_hours"
        ]:
            if column in group.columns:
                result[column] = group.iloc[0][column]

        result.update({
            "n_expected_hours": N_EXPECTED_HOURS,
            "n_predicted_hours": n_predicted,
            "n_missing_forecast_hours": n_missing,
            "n_fallback_hours": n_fallback,
            "is_complete_24h": is_complete,
            "coverage_status": status
        })

        results.append(result)

    return pd.DataFrame(results)


#METRIQUES PAR COMPTEUR
def calculate_by_counter(evaluation):
    """
    Calcule les métriques par compteur, méthode et variante.
    Les calculs sont réalisés à partir des heures évaluables,
    et non à partir d'une moyenne des métriques par cas.
    """

    valid = evaluation[
        evaluation["is_evaluable"]
    ].copy()

    if valid.empty:
        return pd.DataFrame()

    results = []

    group_columns = [
        "counter_id", "method_run_id", "variant"
    ]

    for keys, group in valid.groupby(group_columns):
        metrics = calculate_metrics(
            group["count"],
            group["y_pred"]
        )

        result = dict(zip(group_columns, keys))
        result.update(metrics)

        results.append(result)

    return pd.DataFrame(results)


#METRIQUES GLOBALES
def calculate_global_metrics(results_df):
    """
    Calcule la moyenne non pondérée des métriques entre compteurs.
    Chaque compteur possède le même poids, quel que soit
    son nombre d'heures évaluables.
    """

    if results_df.empty:
        return pd.DataFrame()

    metric_columns = ["MAE", "MAPE", "RMSE", "R2"]

    group_columns = ["method_run_id", "variant"]

    global_results = (
        results_df
        .groupby(group_columns)[metric_columns]
        .mean()
        .reset_index()
    )

    for metric in metric_columns:
        counts = (
            results_df
            .groupby(group_columns)[metric]
            .count()
            .rename(f"n_counters_{metric}")
            .reset_index()
        )

        global_results = global_results.merge(
            counts,
            on=group_columns
        )

    return global_results


#COMPARAISON SUR LES MEMES CAS COMPLETS
def filter_common_complete_cases(evaluation, coverage):
    """
    Conserve les cas complets pour toutes les méthodes
    et variantes présentes dans les données.
    Les heures réellement mesurées restent communes
    à toutes les méthodes pour un même cas.
    """

    if coverage.empty:
        return evaluation.iloc[0:0].copy()

    methods = coverage[
        ["method_run_id", "variant"]
    ].drop_duplicates()

    n_methods = len(methods)

    complete_counts = (
        coverage[coverage["is_complete_24h"]]
        .groupby("case_id")
        .size()
    )

    common_cases = complete_counts[
        complete_counts == n_methods
    ].index

    comparable = evaluation[
        evaluation["case_id"].isin(common_cases)
        & evaluation["is_evaluable"]
    ].copy()

     #Ne garder que les timestamps évaluables pour toutes les méthodes et variantes du cas
    hour_counts = (
        comparable
        .groupby(["case_id", "expected_timestamp"])
        [["method_run_id", "variant"]]
        .apply(lambda x: len(x.drop_duplicates()))
    )

    common_hours = hour_counts[
        hour_counts == n_methods
    ].index

    common_index = pd.MultiIndex.from_frame(
        comparable[
            ["case_id", "expected_timestamp"]
        ]
    )

    return comparable[
        common_index.isin(common_hours)
    ].copy()


#EVALUATION PRINCIPALE
def evaluate_cases(cases, forecasts, observations):
    """
    Evalue les cas fournis.
    Retourne les métriques par cas.
    """

    cases, forecasts, observations = _prepare_inputs(
        cases, forecasts, observations
    )

    evaluation = _build_evaluation(
        cases, forecasts, observations
    )

    return calculate_metrics_by_case(evaluation)


def evaluate_all(cases, forecasts, observations):
    """
    Lance l'ensemble de l'évaluation.
    Retourne les métriques par cas, par compteur,
    la couverture et les métriques globales.
    """

    cases, forecasts, observations = _prepare_inputs(
        cases, forecasts, observations
    )

    evaluation = _build_evaluation(
        cases, forecasts, observations
    )

    metrics_by_case = calculate_metrics_by_case(
        evaluation
    )

    coverage = calculate_coverage(evaluation)

    metrics_by_counter = calculate_by_counter(
        evaluation
    )

    global_metrics = calculate_global_metrics(
        metrics_by_counter
    )

    comparable = filter_common_complete_cases(
        evaluation, coverage
    )

    metrics_comparable = calculate_by_counter(
        comparable
    )

    global_comparable = calculate_global_metrics(
        metrics_comparable
    )

    return {
        "metrics_by_case": metrics_by_case,
        "coverage": coverage,
        "metrics_by_counter": metrics_by_counter,
        "global_metrics": global_metrics,
        "metrics_comparable": metrics_comparable,
        "global_comparable": global_comparable
    }


#CHARGEMENT DES FICHIERS CSV
def evaluation_cases_from_forecasts(forecasts_csv, cases_csv, observations_csv):
    """
    Charge les fichiers CSV et évalue les cas présents
    dans forecasts.csv.
    """

    cases = pd.read_csv(cases_csv)
    forecasts = pd.read_csv(forecasts_csv)
    observations = pd.read_csv(observations_csv)

    case_ids = forecasts["case_id"].unique()

    selected_cases = cases[
        cases["case_id"].isin(case_ids)
    ].copy()

    counter_ids = selected_cases["counter_id"].unique()

    selected_observations = observations[
        observations["counter_id"].isin(counter_ids)
    ].copy()

    return evaluate_all(
        selected_cases,
        forecasts,
        selected_observations
    )


def evaluation_cases_from_cases(cases_csv, forecasts_csv, observations_csv):
    """
    Charge les fichiers CSV et évalue les cas sélectionnés
    dans cases.csv.
    """

    cases = pd.read_csv(cases_csv)
    all_forecasts = pd.read_csv(forecasts_csv)
    all_observations = pd.read_csv(observations_csv)

    forecasts = all_forecasts[
        all_forecasts["case_id"].isin(cases["case_id"])
    ].copy()

    counter_ids = cases["counter_id"].unique()

    observations = all_observations[
        all_observations["counter_id"].isin(counter_ids)
    ].copy()

    return evaluate_all(
        cases, forecasts, observations
    )


def selection_cases_from_context(cases, context, context_searched):
    """
    Select the cases from the cases dataframe that match the context passed in parameter.
    
    Parameters
    ----------
    cases : str
        csv containing all the cases
    context : str
        csv containing the context 
    context_searched : str ("temp_prev_hot", "temp_prev_cold", "rain_prev", "wind_prev", "temp_obs_hot", "temp_obs_cold", "rain_obs", "wind_obs", "is_holiday", "is_school_holiday", "is_strike")
        a context to evaluate the model on 
    Returns
    ----------
    pandas.DataFrame
        cases dataframe filtered by the context passed 
    """

    cases = pd.read_csv(cases)
    context = pd.read_csv(context)

    if context_searched not in ["is_holiday", "is_school_holiday", "temp_prev_hot", "temp_prev_cold",
         "rain_prev", "wind_prev", "temp_obs_hot", "temp_obs_cold", "rain_obs", "wind_obs", "is_strike"]:
        raise ValueError(f"Unknown context: {context_searched}")


    #for is_holiday, is_school_holiday, is_strike, 
    #filter the context dataframe to keep only the cases where the value is true
    if context_searched in ["is_holiday", "is_school_holiday", "is_strike"]:
        selected = context[
            context["variable"] == context_searched
        ].copy()
        selected = selected[selected["value"] == "true"].copy()
        
        cases["origin"] = cases["origin"].apply(lambda x: x.split("T")[0])
        selected_cases = cases[
            cases["origin"].isin(selected["local_date"])
        ].copy()

    #for temp_prev, rain_prev, wind_prev, temp_obs, rain_obs, wind_obs, 
    #select a threshold then filter the context dataframe to keep only the cases that match the threshold

    if context_searched in ["temp_prev_hot", "temp_prev_cold", "rain_prev", "wind_prev", "temp_obs_hot", "temp_obs_cold", "rain_obs", "wind_obs"]:
        threshold = {"rain_prev" : 2, 
                "wind_prev" : 5, 
                "temp_prev_hot" : 28, 
                "temp_prev_cold" : 5, 
                "rain_obs" : 2, 
                "wind_obs" : 5, 
                "temp_obs_hot" : 28, 
                "temp_obs_cold" : 5, }


        if context_searched in ["temp_prev_cold", "temp_obs_cold"]:
            threshold=threshold[context_searched]
            context_searched = context_searched.replace("_cold", "")
            selected = context[
                context["variable"] == context_searched
            ].copy()
            selected = selected[selected["value"].astype(float) <= threshold].copy()
        elif context_searched in ["temp_prev_hot", "temp_obs_hot"]:
            threshold=threshold[context_searched]
            context_searched = context_searched.replace("_hot", "")
            selected = context[
                context["variable"] == context_searched
            ].copy()
            selected = selected[selected["value"].astype(float) >= threshold].copy()
        else :
            selected = context[
                context["variable"] == context_searched
            ].copy()
            selected = selected[selected["value"].astype(float) >= threshold[context_searched]].copy()
        
        cases["origin"] = cases["origin"].apply(lambda x: x.split("T")[0])
        selected["valid_time"] = selected["valid_time"].apply(lambda x: x.split("T")[0])
        selected_cases = cases[
            cases["origin"].isin(selected["valid_time"])
        ].copy()

    return selected_cases

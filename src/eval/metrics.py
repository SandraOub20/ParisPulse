"""GABARIT À COMPLÉTER - E4

Calculer des scores comparables sans masquer les refus.

Entrées et sorties : voir doc/CONTRATS.md et doc/templates/.

À faire :
1. Vérifier alignement, doublons et présence des 24 prévisions par cas.
2. Comparer sur les mêmes cas complets et les mêmes heures réellement mesurées.
3. Calculer MAE par compteur puis moyenne non pondérée ; rapporter les dénominateurs.
4. Séparer sites connus/nouveaux et modèle brut/système après repli ; conserver les échecs.

Aucune implémentation fournie ; ce fichier contient uniquement des consignes.
"""


#MAE
#MAPE
#RSME
#R²
#MAE, MAPE, RSME, R² global


import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


def calculate_metrics(y_true, y_pred):
    """
    Calcule MAE, MAPE, RMSE et R².

    y_true : valeurs réellement observées
    y_pred : valeurs prédites
    """

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    #Vérification taille des y_pred et y_true
    if len(y_true) != len(y_pred):
        raise ValueError("y_true et y_pred doivent avoir la même taille.")

    #Seules les paires valides retenue
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
            "R2": np.nan
        }

    #MAE
    mae = mean_absolute_error(y_true, y_pred)

    #MAPE (exclure les valeurs réelles égales à zéro)
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

    #RMSE
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    #R²
    if n >= 2 and np.var(y_true) > 0:
        r2 = r2_score(y_true, y_pred)
    else:
        r2 = np.nan

    return {
        "n_predictions": n,
        "n_mape_predictions": int(nonzero.sum()),
        "MAE": mae,
        "MAPE": mape,
        "RMSE": rmse,
        "R2": r2
    }


def calculate_by_counter(df):
    """
    Calcule les métriques pour chaque compteur et chaque modèle.
    """

    results = []

    for (model, counter_id), group in df.groupby(
        ["model", "counter_id"]
    ):

        metrics = calculate_metrics(
            group["y_true"],
            group["y_pred"]
        )

        results.append({
            "model": model,
            "counter_id": counter_id,
            **metrics
        })

    return pd.DataFrame(results)


def calculate_global_metrics(results_df):
    """
    Calcule la moyenne des métriques entre les compteurs,
    séparément pour chaque modèle.
    """

    metric_columns = ["MAE", "MAPE", "RMSE", "R2"]

    global_results = (
        results_df
        .groupby("model")[metric_columns]
        .mean()
        .reset_index()
    )

    #Nombre de compteurs ayant contribué à chaque métrique
    for metric in metric_columns:
        counts = (
            results_df.groupby("model")[metric]
            .count()
            .rename(f"n_counters_{metric}")
        )

        global_results = global_results.merge(
            counts,
            on="model"
        )

    return global_results



def evaluate_model_case(case, model ,y_true, y_pred, is_scoreable):
    """
    Evaluate a model with a case (counter + context) given 
    
    Parameters
    ---------

    case :
        a counter + a context = case

    model : str,
        model to evaluate (obtained from forecasts.csv)
    
    y_true : array, (shape (24xnb_counters_considered,nb_models)) 
        real values for all models (obtained from counts.csv)
    
    y_pred : array, (shape (24)) 
        model predictions 

    is_scoreable : array(bool)
        if some values are missing


    Returns
    ---------
    case : case passed in parameter
    model : model passed in parameter
    is_scoreable : is_scoreable passed in parameter
    n_compared_hours : nomber of hours used for the MAE computed
    R2 : mean R² over all the predictions from the chosen model
    MAE : mean MAE over all the predictions from the chosen model
    RMSE : mean RMSE over all the predictions from the chosen model
    hourly_MAE : array with the MAEs over hour from the chosen model 
    hourly_RMSE : array with the RMSEs over hour from the chosen model 
    """

    if is_scoreable == [False]*24:
        return {
            "case": case,
            "model": model,
            "is_scoreable": is_scoreable,
            "n_predictions": 0,
            "R2": np.nan,
            "MAE": np.nan,
            "MAPE": np.nan,
            "RMSE": np.nan,
            "hourly_MAE": np.nan,
            "hourly_RMSE": np.nan
        }
    
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    y_true_scoreable = y_true[is_scoreable]
    y_pred_scoreable = y_pred[is_scoreable]

    global_metrics=calculate_metrics(y_true_scoreable,y_pred_scoreable)

    hourly_MAE=[]
    hourly_RMSE=[]

    for i in range(len(y_true)):
        if is_scoreable[i]:
            hourly_metrics=calculate_metrics(y_true[i],y_pred[i])
            hourly_MAE.append(hourly_metrics["MAE"])
            hourly_RMSE.append(hourly_metrics["RMSE"])
        else:
            hourly_MAE.append(hourly_metrics["MAE"])
            hourly_RMSE.append(hourly_metrics["RMSE"])


    return {
        "case": case,
        "model": model,
        "is_scoreable": is_scoreable,
        "n_compared_hours" : global_metrics["n_predictions"],
        "R2": global_metrics["R2"],
        "MAE": global_metrics["MAE"],
        "RMSE": global_metrics["RMSE"],
        "hourly_MAE": hourly_MAE,
        "hourly_RMSE": hourly_RMSE
    }



def evaluate_model(cases, model, forecasts, observations):
    """
    Evaluate a model on some cases (counter + context) given
    
    Parameters
    ---------

    cases :
        some cases to evaluate with the given model

    model : str,
        model to evaluate (obtained from pred.csv)

    forecasts : pddataframe, (obtained from forecasts.csv) 
        all models predictions 
    
    observations : pddataframe, (obtained from counts.csv) 
        all real values 


    Returns
    ---------
    counter_id : the id of the counter of this case
    origin : the origin of the case, used for the compute of the MAE on the case associated
    case : case passed in parameter
    model : model passed in parameter
    is_scoreable : is_scoreable passed in parameter
    n_compared_hours : nomber of hours used for the MAE computed
    R2 : mean R² over all the predictions from the chosen model
    MAE : mean MAE over all the predictions from the chosen model
    RMSE : mean RMSE over all the predictions from the chosen model
    hourly_MAE : array with the MAEs over hour from the chosen model 
    hourly_RMSE : array with the RMSEs over hour from the chosen model 
    """

    errors=[]
    
    for _,case in cases.iterrows():
        case_id=case["case_id"]
        counter_id=case["counter_id"]
        case_origin=case["origin"]
        origin = pd.to_datetime(case["origin"],utc=True)

        forecasts["target_timestamp"] = pd.to_datetime(
            forecasts["target_timestamp"], utc=True
        )

        observations["target_timestamp"] = pd.to_datetime(
            observations["target_timestamp"], utc=True
        )

        end = origin + pd.Timedelta(hours=24)

        #model_run_id or method_run_id ?
        pred = forecasts.loc[
            (forecasts["method_run_id"] == model) &
            (forecasts["counter_id"] == counter_id) &
            (forecasts["target_timestamp"] >= origin) &
            (forecasts["target_timestamp"] < end)
        ].sort_values("target_timestamp")

        obs = observations.loc[
            (observations["counter_id"] == counter_id) &
            (observations["timestamp"] >= origin) &
            (observations["timestamp"] < end)
        ].sort_values("timestamp")

        y_pred = pred["y_pred"].to_numpy()
        y_true = obs["count"].to_numpy()

        # Check scoreability
        is_scoreable=[]
        for _,obs in obs.iterrows():
                is_scoreable.append(obs["is_scoreable"])
        for i in range(len(y_pred)):
            if is_scoreable[i]==True and y_pred[i]==None:
                is_scoreable[i]=False

        if len(y_true) != len(y_pred):
            raise ValueError("Observations and forecasts have different dimensions")
        else:
            model_result=evaluate_model_case(case_id,model,y_true,y_pred,is_scoreable)
        model_result["origin"]=case_origin
        model_result["counter_id"]=counter_id
        errors.append()

    return pd.DataFrame(errors)



def evaluate_cases(cases,forecasts,observations):
    """
    Evaluate all the cases given, given forecasts and observations. Basically, g2 pass
    all the cases/forecasts/observations from known_site, g3 from new_site, g5 for one case
    (from cases.csv) 

    Parameters
    ----------
    cases : dataframe,
        the cases (counter + origin) that we want to evaluate
    forecasts : dataframe
        the forecasts from the same scenario (known_site/new_site) (at least those for these cases)
    observations : dataframe
        the observations associated to these forecasts (at least)  

    Returns
    --------
    scenario : scenario associated to this counter (known_site/new_site) 
    counter_id : the id of the counter of this case
    origin : the origin of the case, used for the compute of the MAE on the case associated
    case : case passed in parameter
    model : model passed in parameter
    is_scoreable : is_scoreable passed in parameter
    n_compared_hours : nomber of hours used for the MAE computed
    R2 : mean R² over all the predictions from the chosen model
    MAE : mean MAE over all the predictions from the chosen model
    RMSE : mean RMSE over all the predictions from the chosen model
    hourly_MAE : array with the MAEs over hour from the chosen model 
    hourly_RMSE : array with the RMSEs over hour from the chosen model 
    """

    # Check that all cases belong to the same scenario
    scenarios = cases["scenario"].unique()

    if len(scenarios) != 1:
        raise ValueError(
            "Cases must have the same scenario "
            "(known_site or new_site)."
        )

    scenario = scenarios[0]

    if scenario not in ["known_site", "new_site"]:
        raise ValueError(f"Unknown scenario: {scenario}")

    models=forecasts["method_run_id"].loc["scenario"==scenario]

    selected_models = models.loc[
        models["scenario"] == scenario,
        "method_run_id"
    ].unique()

    errors = []

    for model in selected_models:

        model_results = evaluate_model(
            cases, model, forecasts, observations
        )
        model_results["scenario"]=scenario

        errors.append(model_results)

    return pd.DataFrame(errors)




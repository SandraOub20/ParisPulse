import src.eval.Metric as mt 
import numpy as np
import pandas as pd

import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
while not (ROOT / "src").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from src.common.config import ROOT, load_config


cgf = load_config()

PROTOCOLE_ID = cgf["protocol"]["id"]
SNAPSHOT_ID = cgf["snapshot_id"]
HORIZON_HR = cgf["protocol"]["horizon_hours"]
EXP_ID = ["EXP-001","EXP-E3"]
BUDGET = cgf["protocol"]["local_budget_hours"]

EVAL = ROOT / cgf["paths"]["evaluation"]
PRED = ROOT / cgf["paths"]["predictions"]
DATA = ROOT / cgf["paths"]["processed"]

COLUMNS_ERROR = ["case_id","counter_id","horizon","target_timestamp",
                 "method_run_id","y_true","y_pred","is_scoreable","MAE",
                 "R2","RMSE","absolute_error","protocol_id","snapshot_id"]

COLUMNS_SCORES = ["experiment_id","scenario","temporal_split","method_run_id","comparison_population_id","n_expected_cases",
                  "n_complete_cases","n_compared_cases","n_compared_hours","n_evaluable_counters","mae_macro","rmse", "r2","bias","coverage_24h",
                  "n_fallback_cases","protocol_id","snapshot_id"]

COLUMNS_COVERAGE = ["case_id","counter_id","origin","scenario","method_run_id","local_budget_hours","coverage_status",
                    "n_predicted_hours", "is_complete_24h","status_reason","protocol_id","snapshot_id"]


###################################################################################################################################


def make_error(cases, forecast, observations, path):

    # cases appearing in the forecast given
    c_fc = cases.loc[cases['case_id'].isin(forecast['case_id']),:]  
    
    # observations appearing in the forecast given 
    obs_fc = observations.loc[observations['counter_id'].isin(forecast['counter_id']) & observations['timestamp'].isin(forecast['target_timestamp']), :]
    obs_fc['timestamp'] = pd.to_datetime(obs_fc['timestamp'], utc=True)
    obs_fc = obs_fc.rename(columns={"count" : "y_true", "timestamp" : 'target_timestamp'})
 

    # general evaluations
    c, p, o = mt._prepare_inputs(c_fc, forecast, observations)
    eval = mt._build_evaluation(c, p, o)
    eval_err = eval[[col for col in COLUMNS_ERROR if col in eval]]

    # general metrics
    metrics = mt.evaluate_cases(c_fc, forecast, observations)
    metrics_err = metrics[[col for col in metrics if (col in COLUMNS_ERROR and col not in eval_err.columns) or col == 'case_id']]

    # create error
    error = metrics_err.merge(eval_err, how='inner', on='case_id')
    error = error.merge(obs_fc[['counter_id', 'target_timestamp', 'y_true']], on=["counter_id", "target_timestamp"], how='left')
    error["y_true"] = pd.to_numeric(error["y_true"])
    error["absolute_error"] = (error["y_pred"] - error["y_true"]).abs()
    error = error[COLUMNS_ERROR]

    # create csv
    # error.to_csv(path)

    return error

# --------------------------------------------------------------------------------------------------------------------------------------

def check_horizon(forecast):
    cases = forecast["case_id"]

    size_hz = forecast.groupby(['case_id'])["y_pred"].count() == 24
    hz_mask = forecast["horizon"].between(1, 24)
    all_hz = forecast.groupby(cases)["horizon"].apply(lambda h: hz_mask.loc[h.index].sum()) == 24

    return (all_hz & size_hz)

def make_scores(cases, forecast, observations, exp_id, path):
    budget = (forecast["scenario"].unique()[0] == 'new_site')

    # cases appearing in the forecast given
    c_fc = cases.loc[cases['case_id'].isin(forecast['case_id']),:]  
    # observations appearing in the forecast given 
    obs_fc = observations.loc[observations['counter_id'].isin(forecast['counter_id']) & observations['timestamp'].isin(forecast['target_timestamp']), :]
    obs_fc['timestamp'] = pd.to_datetime(obs_fc['timestamp'], utc=True)
    obs_fc = obs_fc.rename(columns={"count" : "y_true"})

    # scenario used for the prediction
    scenario = forecast["scenario"].unique()[0]
    # prediction values
    y_pred = forecast["y_pred"]
    y_true = obs_fc["y_true"].repeat(1 + budget*2)
    # method
    method = forecast["method_run_id"].unique()[0]
    # cases that fit the temporary split 
    temp_split = forecast.merge(c_fc, how="inner", on="case_id")["temporal_split"].unique()[0]

    # general metrics
    metrics = mt.calculate_metrics(y_pred, y_true)

    # expected cases
    exp_c = len(c_fc[(c_fc["scenario"] == scenario)&(c_fc["temporal_split"] == temp_split)].index)

    # completed cases
    complete_c = check_horizon(forecast).sum()

    # compared cases
    fc_count = forecast.groupby(['case_id'])["y_pred"].count()
    comp_c = (fc_count > 0).sum()

    # evaluated counters
    eval_counters = len(forecast["counter_id"].unique())

    # fallbacks
    n_fallbacks = forecast['prediction_status'].ne("ok").groupby(forecast['case_id']).all().sum()

    # assemble df
    score =  [{"experiment_id" : exp_id,
              "scenario" : scenario,
              "temporal_split" : temp_split,
              "method_run_id" : method,
              "comparison_population_id" : np.nan,
              "n_expected_cases" : exp_c,
              "n_complete_cases" : complete_c,
              "n_compared_cases" : comp_c,
              "n_compared_hours" : metrics["n_predictions"],
              "n_evaluable_counters" : eval_counters,
              "mae_macro" : metrics["MAE"],
              "rmse" : metrics["RMSE"], 
              "r2" : metrics["R2"],
              "bias" : metrics["bias"],
              "coverage_24h" : np.nan,
              "n_fallback_cases" : n_fallbacks,
              "protocol_id" : PROTOCOLE_ID,
              "snapshot_id" : SNAPSHOT_ID}]

    score = pd.DataFrame(score)

    # make csv
    score.to_csv(path, index = False)

    return score

# --------------------------------------------------------------------------------------------------------------------------------------

def make_coverage(cases, forecast, observations, path):
    
    # cases appearing in the forecast given
    c_fc = cases.loc[cases['case_id'].isin(forecast['case_id']),:]  
    # general evaluation
    c, p, o = mt._prepare_inputs(c_fc, forecast, observations)
    eval = mt._build_evaluation(c, p, o)
    # only keep last prediction, just to make the merging easier
    fc = forecast[forecast["horizon"] == 24].copy()
    # coverage based on evaluation function
    cov = mt.calculate_coverage(eval)

    coverage = c_fc.merge(fc[['case_id','method_run_id']], on='case_id', how="left")
    coverage = coverage.merge(cov[['case_id','coverage_status', 'is_complete_24h', 'n_predicted_hours']], on='case_id', how='left')
    coverage['status_reason'] = np.nan


    coverage = coverage[COLUMNS_COVERAGE]

    coverage.to_csv(path)

    return coverage
   ##############################################################################################################################
 

if __name__ == "__main__":

    cases = pd.read_csv(EVAL / PROTOCOLE_ID / "cases.csv")
    counts = pd.read_csv(DATA / SNAPSHOT_ID / "counts.csv")
    
    for e in EXP_ID:

        folder = PRED 
        out = EVAL / PROTOCOLE_ID

        if e is not None :
            folder = folder / e
            out = out / e

        error = out / "error.csv"
        scores = out / "scores.csv"
        coverage = out / "coverage.csv"

        for f in sorted(Path(folder).glob("*.pred.csv")) : 
            f_df = pd.read_csv(f)
            print("\nMaking evaluation files for {f}.....\n")
            make_error(cases, f_df, counts, error)
            print("Error Completed...")
            make_scores(cases, f_df, counts, e, scores)
            print("Scores Completed..")
            make_coverage(cases, f_df, counts, coverage)
            print("Coverage Completed.")
        
        
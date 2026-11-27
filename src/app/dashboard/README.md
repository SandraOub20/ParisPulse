
# ParisPulse - Dashboard Visualizations (Team 5)

## Overview

This folder contains the five visualization modules developed by Team 5, Person 3.

These modules display historical observations, 24-hour forecasts, missing data, prediction errors, and model comparisons.

The modules only display and analyze data supplied by the application service. They do not train models or calculate official evaluation metrics.

## Modules

### 1. history.py

Function:
`show_history(data: pd.DataFrame) -> None`

Displays historical bicycle observations.

Required columns:
- `timestamp`
- `count`

### 2. predictions.py

Function:
`show_predictions(predictions, load_observations=None, case_id=None) -> bool`

Displays the next 24 hours of forecasts and allows users to reveal actual observations on demand.

Required forecast columns:
- `horizon`
- `target_timestamp`
- `y_pred`

Observation columns:
- `target_timestamp`
- `y_true`

Important:
Actual observations must only be loaded after the user activates the reveal control.

### 3. missing_data.py

Function:
`show_missing_data(data: pd.DataFrame) -> None`

Displays missing observations and genuine zero counts.

Required columns:
- `timestamp`
- `count`

A genuine zero is not considered missing data.

### 4. errors.py

Function:
`show_errors(errors, mae_macro=None, mae_by_counter=None) -> None`

Displays prediction errors, actual-versus-predicted curves, and MAE results supplied by Team 4.

Required columns:
- `target_timestamp`
- `signed_error`
- `absolute_error`

Optional columns:
- `y_true`
- `y_pred`
- `is_scoreable`

When `is_scoreable` is available, only scoreable rows are displayed.

### 5. comparison.py

Displays the official Team 4 evaluation. Every value comes from `scores.csv`,
`coverage.csv` and `scoring_manifest.json`, loaded and checked by
`src/app/evaluation_service.py`. No metric is computed here.

Functions:

- `show_official_evaluation(results=None, *, root=None) -> None`
  Global "Évaluation officielle E4" section with two separate views (E2 · known sites,
  E3 · new sites). Without `results`, it calls `evaluation_service.load_official_results(root)`.
  If one team's files are missing or invalid, its view shows the error and the other
  team stays visible.
- `show_team_evaluation(results: TeamResults, *, key=None) -> None`
  One team's view. E3 offers a choice of local history budget (24 h, 72 h, 168 h). Both
  teams offer a choice of comparison population.
- `show_model_comparison(scores, *, coverage_summary=None, key="model_comparison") -> None`
  Original API, still compatible: compares any score rows that follow the `scores.csv`
  contract. The two new arguments are optional.

Required columns for `show_model_comparison`:
- `method_run_id`
- `mae_macro`
- `scenario`
- `temporal_split`
- `comparison_population_id`
- `protocol_id`
- `snapshot_id`

Rules:
- Models are only compared within a single `comparison_population_id` that has the same
  scenario, temporal split, protocol and snapshot (`evaluation_service.select_population`).
- `self` population: each method is scored on its own cases. Different sample sizes
  only trigger a warning, because the comparison is indicative.
- `common_complete` population: the same complete cases for every method, which is the
  comparison to prefer. Different sample sizes are reported as an error and no
  ranking is shown.
- Displayed metrics: macro MAE, RMSE, R², bias, compared cases and hours, evaluable
  counters, 24 h coverage and fallback cases.
- Coverage keeps these notions separate: expected, predicted (at least one forecast hour),
  complete (24 hours, fallback included), evaluable (taken from `n_compared_cases`),
  errors, partial, no forecast.
- A missing value is shown as « non disponible », never as 0. A method without an
  official MAE stays in the table but is excluded from the chart and the ranking.
- Identifiers (population, protocol, snapshot, budget) and provenance (manifest, script,
  generation date) are displayed.

Local score versus official evaluation:
- The study of one case (`streamlit_app.show_study` / `show_comparison`) shows an
  indicative MAE over the 24 hours of that single case (`v1_service.evaluate_local`),
  labelled « MAE sur ce cas (indicatif) ».
- The « Évaluation officielle E4 » tab shows the Team 4 scores over every protocol case.
  The two never replace each other.

## Dependencies

- pandas
- plotly
- streamlit

## Integration

The modules are designed to be called from:

`src/app/streamlit_app.py`

Data loading and orchestration should be handled by:

`src/app/service.py` (forecasts of one case) and `src/app/evaluation_service.py`
(official Team 4 evaluation).

Main navigation in `streamlit_app.main()`:
- « Prévision par compteur »: the existing flow (map, 24 h forecast, history, missing
  data, E1 context), unchanged and moved into `show_counter_explorer()`.
- « Évaluation officielle E4 »: `show_e4_evaluation()` → `show_official_evaluation()`.
  It is reachable without selecting a counter or installing an E1 snapshot.

Both tabs run on every interaction, so the selected counter and the computed forecast
are kept while browsing the E4 tab.

Caching: `official_results_cached(root, version)` uses `st.cache_data`. `version` is the
signature (modification time and size) of `scores.csv`, `coverage.csv` and
`scoring_manifest.json` for E2 and E3 (`e4_version`). A file republished by Team 4
changes the signature and is reloaded automatically.

The application service must respect the official contracts defined in `doc/CONTRATS.md`.

## Testing

Temporary demonstration scripts are located at the repository root:

- test_history.py
- test_predictions.py
- test_missing_data.py
- test_errors.py
- test_comparison.py

All demonstration values are fictitious and must not be treated as real ParisPulse results.

Automated tests:

- `tests/test_e5_evaluation_service.py`: loading and checking the official E4 files.
- `tests/test_e5_dashboard_comparison.py`: filters, missing values, incompatible
  populations, coverage and the original API of `comparison.py`.
- `tests/test_e5_streamlit_navigation.py`: main navigation, cache, and non-regression of
  the counter flow (on a mini E1 snapshot).

## Current status

All five visualization modules have been tested individually using Streamlit demonstration data.

The official Team 4 evaluation (`comparison.py`) is integrated in the application through
the « Évaluation officielle E4 » tab. The other modules (`history.py`, `predictions.py`,
`missing_data.py`, `errors.py`) are not yet called by `streamlit_app.py`.

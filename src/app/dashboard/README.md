
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

Function:
`show_model_comparison(scores: pd.DataFrame) -> None`

Compares forecasting methods using evaluation scores supplied by Team 4.

Required columns:
- `method_run_id`
- `mae_macro`
- `scenario`
- `temporal_split`
- `comparison_population_id`
- `protocol_id`
- `snapshot_id`

Models must be compared under identical evaluation conditions.

## Dependencies

- pandas
- plotly
- streamlit

## Integration

The modules are designed to be called from:

`src/app/streamlit_app.py`

Data loading and orchestration should be handled by:

`src/app/service.py`

The application service must respect the official contracts defined in `doc/CONTRATS.md`.

## Testing

Temporary demonstration scripts are located at the repository root:

- test_history.py
- test_predictions.py
- test_missing_data.py
- test_errors.py
- test_comparison.py

All demonstration values are fictitious and must not be treated as real ParisPulse results.

## Current status

All five visualization modules have been tested individually using Streamlit demonstration data.

Integration with the real application service and datasets remains to be completed.

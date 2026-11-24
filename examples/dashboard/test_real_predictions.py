
"""Analyze real E2 predictions against original E1 observations."""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.app.dashboard.predictions import show_predictions

# ---------------------------------------------------------
# 1. PROJECT PATHS AND REAL DATA SOURCES
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data" / "prediction_results" / "E2-TECH-001"

E1_DATA_DIR = ROOT / "data" / "processed" / "hist-20261117"
E1_COUNTS_PATH = E1_DATA_DIR / "counts.csv"

FILES = {
    "e2-reference-measured": (
        DATA_DIR / "e2-reference-measured.pred.csv"
    ),
    "e2-reference_profile-measured": (
        DATA_DIR / "e2-reference_profile-measured.pred.csv"
    ),
}

EXPECTED_ROWS_PER_FILE = 260592

REQUIRED_COLUMNS = {
    "case_id",
    "method_run_id",
    "model_run_id",
    "counter_id",
    "origin",
    "scenario",
    "horizon",
    "target_timestamp",
    "y_pred",
    "variant",
    "method_used",
    "prediction_status",
    "status_reason",
    "snapshot_id",
    "protocol_id",
}

E1_REQUIRED_COLUMNS = [
    "counter_id",
    "timestamp",
    "count_raw",
    "is_observed",
    "is_scoreable",
]


# ---------------------------------------------------------
# 2. LOAD THE COMPLETE E2 DATASETS
# ---------------------------------------------------------

@st.cache_data(show_spinner="Loading complete E2 datasets...")
def load_all_predictions() -> pd.DataFrame:
    """Load both complete E2 prediction datasets."""

    datasets = []

    for expected_run_id, file_path in FILES.items():

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Prediction file not found: {file_path}"
            )

        data = pd.read_csv(
            file_path,
            low_memory=False,
            dtype={
                "case_id": "string",
                "method_run_id": "string",
                "model_run_id": "string",
                "counter_id": "string",
                "scenario": "string",
                "variant": "string",
                "method_used": "string",
                "prediction_status": "string",
                "snapshot_id": "string",
                "protocol_id": "string",
            },
        )

        missing = REQUIRED_COLUMNS - set(data.columns)

        if missing:
            raise ValueError(
                f"{file_path.name}: missing columns {sorted(missing)}"
            )

        if not data["method_run_id"].eq(expected_run_id).all():
            raise ValueError(
                f"Unexpected method_run_id in {file_path.name}"
            )

        if len(data) != EXPECTED_ROWS_PER_FILE:
            st.warning(
                f"{file_path.name}: {len(data):,} rows found; "
                f"{EXPECTED_ROWS_PER_FILE:,} were expected "
                "in E2-TECH-001."
            )

        datasets.append(data)

    # Retain all rows from both original prediction files.
    return pd.concat(
        datasets,
        ignore_index=True,
    )


# ---------------------------------------------------------
# 2B. LOAD ORIGINAL SCOREABLE E1 OBSERVATIONS
# ---------------------------------------------------------

@st.cache_data(max_entries=20, show_spinner=False)
def load_counter_scoreable_actuals(
    counts_path: str,
    counter_id: str,
    file_size: int,
    modified_ns: int,
) -> pd.DataFrame:
    """Load all original scoreable observations for one counter.

    E1 replacements and non-scoreable measurements are excluded.
    Genuine measured zeros are retained.
    """

    matching_chunks = []

    for chunk in pd.read_csv(
        counts_path,
        usecols=E1_REQUIRED_COLUMNS,
        dtype={"counter_id": "string"},
        chunksize=250_000,
        low_memory=False,
    ):
        selected = chunk.loc[
            chunk["counter_id"].eq(counter_id)
        ].copy()

        if selected.empty:
            continue

        observed = (
            selected["is_observed"]
            .astype("string")
            .str.strip()
            .str.lower()
            .eq("true")
            .fillna(False)
        )

        scoreable = (
            selected["is_scoreable"]
            .astype("string")
            .str.strip()
            .str.lower()
            .eq("true")
            .fillna(False)
        )

        raw_counts = pd.to_numeric(
            selected["count_raw"],
            errors="coerce",
        )

        valid_raw_counts = (
            raw_counts.notna()
            & np.isfinite(raw_counts.fillna(0))
            & raw_counts.ge(0)
        )

        timestamps = pd.to_datetime(
            selected["timestamp"],
            utc=True,
            errors="coerce",
        )

        eligible = (
            observed
            & scoreable
            & valid_raw_counts
            & timestamps.notna()
        )

        if eligible.any():
            matching_chunks.append(
                pd.DataFrame(
                    {
                        "target_timestamp": timestamps.loc[eligible],
                        "y_true": raw_counts.loc[eligible],
                    }
                )
            )

    if not matching_chunks:
        return pd.DataFrame(
            {
                "target_timestamp": pd.Series(
                    dtype="datetime64[ns, UTC]"
                ),
                "y_true": pd.Series(dtype="float64"),
            }
        )

    actuals = pd.concat(
        matching_chunks,
        ignore_index=True,
    )

    if actuals["target_timestamp"].duplicated().any():
        raise ValueError(
            f"Duplicate scoreable actual timestamps detected "
            f"for counter {counter_id}."
        )

    return actuals.sort_values(
        "target_timestamp"
    ).reset_index(drop=True)


def load_case_actuals(
    counter_id: str,
    target_timestamps: pd.Series,
) -> pd.DataFrame:
    """Return E1 actual observations matching a forecast's targets."""

    if not E1_COUNTS_PATH.is_file():
        raise FileNotFoundError(
            f"E1 historical counts file not found: {E1_COUNTS_PATH}"
        )

    file_info = E1_COUNTS_PATH.stat()

    # The complete scoreable history is cached per counter.
    actuals = load_counter_scoreable_actuals(
        str(E1_COUNTS_PATH),
        counter_id,
        file_info.st_size,
        file_info.st_mtime_ns,
    )

    targets = pd.to_datetime(
        target_timestamps,
        utc=True,
        errors="coerce",
    ).dropna().drop_duplicates()

    # Keep only the exact 24 forecast target timestamps.
    return actuals.loc[
        actuals["target_timestamp"].isin(targets)
    ].copy()


# ---------------------------------------------------------
# 3. PREPARE VALIDATION FIELDS
# ---------------------------------------------------------

def prepare_predictions(data: pd.DataFrame) -> pd.DataFrame:
    """Prepare numerical values and validation flags."""

    result = data.copy()

    result["horizon_numeric"] = pd.to_numeric(
        result["horizon"],
        errors="coerce",
    )

    result["y_pred_numeric"] = pd.to_numeric(
        result["y_pred"],
        errors="coerce",
    )

    result["status_normalized"] = (
        result["prediction_status"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    result["valid_horizon"] = (
        result["horizon_numeric"].notna()
        & result["horizon_numeric"].between(1, 24)
        & result["horizon_numeric"].mod(1).eq(0)
    )

    result["valid_prediction"] = (
        result["status_normalized"].isin(["ok", "fallback"])
        & result["y_pred_numeric"].notna()
        & np.isfinite(result["y_pred_numeric"])
        & result["y_pred_numeric"].ge(0)
        & result["valid_horizon"]
    )

    return result


# ---------------------------------------------------------
# 4. BUILD CASE-LEVEL QUALITY STATISTICS
# ---------------------------------------------------------

def build_case_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Build completeness and quality statistics for every case."""

    grouped = data.groupby(
        ["method_run_id", "case_id"],
        dropna=False,
    )

    summary = grouped.agg(
        counter_id=("counter_id", "first"),
        origin=("origin", "first"),
        number_of_rows=("horizon", "size"),
        distinct_horizons=("horizon_numeric", "nunique"),
        valid_hours=("valid_prediction", "sum"),
        fallback_hours=(
            "status_normalized",
            lambda values: values.eq("fallback").sum(),
        ),
        unavailable_hours=(
            "status_normalized",
            lambda values: values.eq("unavailable").sum(),
        ),
        error_hours=(
            "status_normalized",
            lambda values: values.eq("error").sum(),
        ),
    ).reset_index()

    summary["is_complete_24h"] = (
        summary["number_of_rows"].eq(24)
        & summary["distinct_horizons"].eq(24)
        & summary["valid_hours"].eq(24)
    )

    return summary


# ---------------------------------------------------------
# 5. STREAMLIT PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="ParisPulse - Real E2 Data",
    page_icon="🚲",
    layout="wide",
)

st.title("ParisPulse — Real Prediction Analysis")

st.warning(
    "Real E2 experimental predictions | "
    "Protocol proto-v0 | Snapshot hist-20261117. "
    "These are technical experiment results, not final evaluation scores."
)


# ---------------------------------------------------------
# 6. LOAD AND VALIDATE ALL DATA
# ---------------------------------------------------------

try:
    raw_data = load_all_predictions()
    all_data = prepare_predictions(raw_data)
    case_summary = build_case_summary(all_data)

except Exception as error:
    st.error(f"Data loading or validation failed: {error}")
    st.stop()


# ---------------------------------------------------------
# 7. GLOBAL DATASET OVERVIEW
# ---------------------------------------------------------

st.header("1. Complete dataset overview")

total_rows = len(all_data)
total_cases = len(case_summary)
total_counters = all_data["counter_id"].nunique()

complete_cases = int(
    case_summary["is_complete_24h"].sum()
)

incomplete_cases = total_cases - complete_cases

valid_predictions = int(
    all_data["valid_prediction"].sum()
)

c1, c2, c3 = st.columns(3)
c4, c5, c6 = st.columns(3)

c1.metric("Total prediction rows", f"{total_rows:,}")
c2.metric("Method-case combinations", f"{total_cases:,}")
c3.metric("Distinct counters", f"{total_counters:,}")

c4.metric("Complete 24h cases", f"{complete_cases:,}")
c5.metric("Incomplete cases", f"{incomplete_cases:,}")
c6.metric("Valid prediction rows", f"{valid_predictions:,}")

st.caption(
    "Both complete E2 prediction CSV files are loaded. "
    "No cases have been randomly sampled or removed."
)


# ---------------------------------------------------------
# 8. PREDICTION STATUS ANALYSIS
# ---------------------------------------------------------

st.header("2. Prediction status analysis")

status_summary = (
    all_data.groupby(
        ["method_run_id", "status_normalized"],
        dropna=False,
    )
    .size()
    .reset_index(name="number_of_hours")
)

st.dataframe(
    status_summary,
    use_container_width=True,
    hide_index=True,
)

status_pivot = status_summary.pivot(
    index="method_run_id",
    columns="status_normalized",
    values="number_of_hours",
).fillna(0)

st.bar_chart(status_pivot)


# ---------------------------------------------------------
# 9. EFFECTIVE METHODS ANALYSIS
# ---------------------------------------------------------

st.header("3. Effective methods actually used")

method_summary = (
    all_data.groupby(
        ["method_run_id", "method_used"],
        dropna=False,
    )
    .size()
    .reset_index(name="number_of_hours")
)

st.dataframe(
    method_summary,
    use_container_width=True,
    hide_index=True,
)

method_pivot = method_summary.pivot(
    index="method_run_id",
    columns="method_used",
    values="number_of_hours",
).fillna(0)

st.bar_chart(method_pivot)


# ---------------------------------------------------------
# 10. CASE COMPLETENESS
# ---------------------------------------------------------

st.header("4. Case completeness")

completeness_summary = (
    case_summary.groupby(
        "method_run_id",
        dropna=False,
    )
    .agg(
        total_cases=("case_id", "size"),
        complete_cases=("is_complete_24h", "sum"),
    )
    .reset_index()
)

completeness_summary["incomplete_cases"] = (
    completeness_summary["total_cases"]
    - completeness_summary["complete_cases"]
)

st.dataframe(
    completeness_summary,
    use_container_width=True,
    hide_index=True,
)

if incomplete_cases > 0:
    st.warning("Some method-case combinations are incomplete.")

    st.dataframe(
        case_summary.loc[
            ~case_summary["is_complete_24h"]
        ],
        use_container_width=True,
    )
else:
    st.success(
        "All method-case combinations have 24 valid predictions."
    )


# ---------------------------------------------------------
# 11. INTERACTIVE EXPLORATION OF ALL CASES
# ---------------------------------------------------------

st.header("5. Explore individual predictions")

available_methods = sorted(
    all_data["method_run_id"].dropna().unique().tolist()
)

selected_method = st.selectbox(
    "Choose a baseline method",
    available_methods,
)

method_cases = case_summary.loc[
    case_summary["method_run_id"].eq(selected_method)
].copy()

case_labels = {
    str(row.case_id): (
        f"{row.case_id} | Counter: {row.counter_id} | "
        f"Fallback: {row.fallback_hours} | "
        f"Unavailable: {row.unavailable_hours}"
    )
    for row in method_cases.itertuples()
}

available_cases = method_cases["case_id"].astype(str).tolist()

selected_case = st.selectbox(
    f"Choose a case ({len(available_cases):,} available)",
    available_cases,
    format_func=lambda value: case_labels[value],
)

selected_predictions = all_data.loc[
    all_data["method_run_id"].eq(selected_method)
    & all_data["case_id"].eq(selected_case)
].copy()

selected_predictions = selected_predictions.sort_values(
    "horizon_numeric"
)


# ---------------------------------------------------------
# 12. DISPLAY SELECTED CASE DETAILS
# ---------------------------------------------------------

st.header("6. Selected forecast")

selected_info = method_cases.loc[
    method_cases["case_id"].astype(str).eq(selected_case)
].iloc[0]

c1, c2, c3, c4 = st.columns(4)

c1.metric("Counter", str(selected_info["counter_id"]))
c2.metric("Prediction rows", int(selected_info["number_of_rows"]))
c3.metric("Fallback hours", int(selected_info["fallback_hours"]))
c4.metric("Valid hours", int(selected_info["valid_hours"]))

st.write("**Case ID:**", selected_case)
st.write("**Method run:**", selected_method)
st.write("**Origin (UTC):**", selected_info["origin"])

st.subheader("Hourly forecast details")

display_columns = [
    "horizon",
    "target_timestamp",
    "y_pred",
    "method_used",
    "prediction_status",
    "status_reason",
]

st.dataframe(
    selected_predictions[display_columns],
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# 13. CONNECT E2 PREDICTIONS TO E1 ACTUAL OBSERVATIONS
# ---------------------------------------------------------

st.header("7. Forecast and actual observation comparison")

selected_counter_ids = (
    selected_predictions["counter_id"]
    .dropna()
    .astype(str)
    .unique()
)

observations_loader = None

if len(selected_counter_ids) == 1 and E1_COUNTS_PATH.is_file():
    selected_counter_id = selected_counter_ids[0]

    def load_selected_observations() -> pd.DataFrame:
        """Load E1 actual values for the selected forecast case."""

        return load_case_actuals(
            selected_counter_id,
            selected_predictions["target_timestamp"],
        )

    observations_loader = load_selected_observations

elif not E1_COUNTS_PATH.is_file():
    st.warning(
        "E1 historical data is unavailable. "
        "Actual observations cannot be displayed."
    )

else:
    st.warning(
        "The selected forecast does not correspond to exactly "
        "one counter. Actual observations cannot be matched safely."
    )

st.caption(
    "Actual values are taken from E1 count_raw and must satisfy "
    "is_observed=True and is_scoreable=True. "
    "E1 replacements and non-scoreable values are excluded."
)

show_predictions(
    predictions=selected_predictions,
    load_observations=observations_loader,
    case_id=f"{selected_method}:{selected_case}",
)


# ---------------------------------------------------------
# 14. DATA PROVENANCE
# ---------------------------------------------------------

with st.expander("Dataset provenance and technical information"):

    st.write("**Prediction experiment:** E2-TECH-001")
    st.write("**Protocol:** proto-v0")
    st.write("**Snapshot:** hist-20261117")

    st.write("**Prediction files:**")

    for method_id, file_path in FILES.items():
        st.write(f"- {method_id}: `{file_path.name}`")

    st.write("**Historical observations:**")
    st.write("- E1 snapshot: `hist-20261117`")
    st.write(f"- Actual data file: `{E1_COUNTS_PATH.name}`")
    st.write(
        "- Ground truth: original scoreable count_raw measurements."
    )

    st.write(
        "**Important:** These are technical experimental results, "
        "not final evaluation scores."
    )

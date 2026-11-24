
"""Test the historical dashboard with the real E1 hist-20261117 dataset."""

from pathlib import Path

import pandas as pd
import streamlit as st

from src.app.dashboard.history import show_history
from src.app.dashboard.missing_data import show_missing_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data" / "processed" / "hist-20261117"
COUNTS_PATH = DATA_DIR / "counts.csv"
COUNTERS_PATH = DATA_DIR / "counters.csv"

REQUIRED_COLUMNS = [
    "counter_id",
    "timestamp",
    "count_raw",
    "count",
    "is_observed",
    "is_scoreable",
]

OPTIONAL_COLUMNS = [
    "quality_flags",
    "source_file_id",
]


@st.cache_data(show_spinner=False)
def load_counter_history(
    counts_path: str,
    counter_id: str,
    columns: tuple[str, ...],
    file_size: int,
    modified_ns: int,
) -> pd.DataFrame:
    """Load every historical row for one counter using CSV chunks."""

    matching_chunks = []

    for chunk in pd.read_csv(
        counts_path,
        usecols=list(columns),
        dtype={"counter_id": "string"},
        chunksize=250_000,
        low_memory=False,
    ):
        selected = chunk.loc[
            chunk["counter_id"].eq(counter_id)
        ]

        if not selected.empty:
            matching_chunks.append(selected)

    if not matching_chunks:
        return pd.DataFrame(columns=columns)

    return pd.concat(
        matching_chunks,
        ignore_index=True,
    )


def format_counter(counter_id: str, counters: pd.DataFrame) -> str:
    """Build a readable counter label from E1 metadata."""

    matching = counters.loc[
        counters["counter_id"].eq(counter_id)
    ]

    if matching.empty:
        return counter_id

    row = matching.iloc[0]
    details = []

    for column in ["site_name", "counter_name", "site_id"]:
        if column in counters.columns:
            value = row[column]

            if pd.notna(value) and str(value).strip():
                details.append(str(value).strip())

    description = " — ".join(details)

    if description:
        return f"{description} ({counter_id})"

    return counter_id


def main() -> None:
    st.set_page_config(
        page_title="ParisPulse — Real Historical Data",
        layout="wide",
    )

    st.title("ParisPulse — Historical Data")
    st.caption(
        "Real E1 dataset: hist-20261117. "
        "All historical rows are retained for the selected counter."
    )

    if not COUNTS_PATH.exists():
        st.error(f"Historical counts file not found: {COUNTS_PATH}")
        return

    if not COUNTERS_PATH.exists():
        st.error(f"Counter inventory file not found: {COUNTERS_PATH}")
        return

    counters = pd.read_csv(
        COUNTERS_PATH,
        dtype={"counter_id": "string"},
    )

    if "counter_id" not in counters.columns:
        st.error("The E1 counters.csv file has no counter_id column.")
        return

    counters = counters.dropna(subset=["counter_id"]).copy()

    available_ids = sorted(
        counters["counter_id"].astype(str).unique().tolist()
    )

    if not available_ids:
        st.error("No counters were found in counters.csv.")
        return

    header = pd.read_csv(
        COUNTS_PATH,
        nrows=0,
    ).columns.tolist()

    missing = set(REQUIRED_COLUMNS) - set(header)

    if missing:
        st.error(
            "Required E1 columns are missing: "
            + ", ".join(sorted(missing))
        )
        return

    columns = REQUIRED_COLUMNS + [
        column
        for column in OPTIONAL_COLUMNS
        if column in header
    ]

    selected_counter = st.selectbox(
        "Select a counter",
        options=available_ids,
        format_func=lambda counter_id: format_counter(
            counter_id,
            counters,
        ),
    )

    st.divider()

    file_info = COUNTS_PATH.stat()

    with st.spinner(
        "Reading the complete E1 history for this counter..."
    ):
        history = load_counter_history(
            str(COUNTS_PATH),
            selected_counter,
            tuple(columns),
            file_info.st_size,
            file_info.st_mtime_ns,
        )

    if history.empty:
        st.warning(
            "No historical rows were found for this counter."
        )
        return

    st.success(
        f"Loaded {len(history):,} historical rows "
        f"for counter {selected_counter}. No sampling was applied."
    )

    # Display both visualizations using the same loaded data.
    tab_history, tab_missing = st.tabs(
        [
            "Historical observations",
            "Missing data analysis",
        ]
    )

    with tab_history:
        show_history(history)

    with tab_missing:
        show_missing_data(history)


if __name__ == "__main__":
    main()

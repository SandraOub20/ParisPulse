"""Variables E2 f1.0 : calendrier, historique, contexte, causalité et égalité des deux chemins.

Cas construit : compteur C-1, mesures horaires du 01/02 au 10/04/2025, origine
2025-03-29T23:00Z (minuit à Paris le 30/03, jour du passage à l'heure d'été), latence 24 h,
donc coupure 2025-03-28T23:00Z. Le 30/03 local n'a que 23 heures : h24 tombe le 31/03 local.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.known import baseline, features
from src.models.known.features import (
    CONTEXT_GROUPS,
    FEATURE_VERSION,
    META_COLUMNS,
    build_feature_frame,
    build_training_frame,
    calendar_features,
    feature_columns,
    training_counters,
    training_origins,
)
from src.models.known.predict import build_inputs
from src.models.schemas import Case, ForecastInputs, target_timestamps

LAG = 24
ORIGIN = pd.Timestamp("2025-03-29T23:00:00Z")
CUTOFF = ORIGIN - pd.Timedelta(hours=LAG)
H1_SOURCE = "2025-03-22T23:00:00+00:00"  # t - 168 h de h1 : zéro mesuré
H2_SOURCE = "2025-03-23T00:00:00+00:00"  # t - 168 h de h2 : absent (estimé par E1)
ZERO_RUN = pd.date_range("2025-03-28T18:00", "2025-03-28T22:00", freq="h", tz="UTC")
NOT_SCOREABLE = "2025-03-30T05:00:00+00:00"
FIT_CUTOFF = pd.Timestamp("2025-04-08T22:00:00Z")


def iso(ts: pd.DatetimeIndex) -> pd.Index:
    return ts.map(pd.Timestamp.isoformat)


def make_counts() -> pd.DataFrame:
    """Colonnes de counts.csv, dates en texte ISO comme le fichier livré."""
    ts = pd.date_range("2025-02-01T00:00", "2025-04-10T23:00", freq="h", tz="UTC")
    counts = pd.DataFrame(
        {
            "counter_id": "C-1",
            "timestamp": iso(ts),
            "interval_end": iso(ts + pd.Timedelta(hours=1)),
            "count_raw": (np.arange(len(ts)) % 97 + 10).astype(float),
            "is_observed": True,
            "is_scoreable": True,
        }
    )
    counts["count"] = counts["count_raw"]
    counts.loc[counts["timestamp"] == H1_SOURCE, ["count_raw", "count"]] = 0.0
    missing = counts["timestamp"] == H2_SOURCE
    counts.loc[missing, ["count_raw", "is_observed", "is_scoreable"]] = [np.nan, False, False]
    counts.loc[missing, "count"] = 999.0  # estimation E1 : ne doit jamais servir
    counts.loc[counts["timestamp"].isin(iso(ZERO_RUN)), ["count_raw", "count"]] = 0.0
    counts.loc[counts["timestamp"] == NOT_SCOREABLE, "is_scoreable"] = False
    return counts


def measured_history(counts: pd.DataFrame) -> pd.DataFrame:
    """Même règle que counts_history_loader(values="measured")."""
    history = counts.copy()
    history["count"] = history["count_raw"].where(history["is_observed"])
    return history


def make_context() -> pd.DataFrame:
    rows = []
    for day in pd.date_range("2025-02-01", "2025-04-15", freq="D"):
        date = day.strftime("%Y-%m-%d")
        for source, variable, value in [
            ("jours_feries", "is_holiday", date == "2025-03-30"),
            ("vacances_zone_c", "is_school_holiday", False),
        ]:
            rows.append(
                dict(
                    context_source_id=source,
                    variable=variable,
                    local_date=date,
                    valid_time=None,
                    value=str(value).lower(),
                    role="known_calendar",
                    available_at=None,
                )
            )
        # Grève : connue à minuit (Paris) du jour - 24 h.
        midnight = pd.Timestamp(date).tz_localize("Europe/Paris").tz_convert("UTC")
        rows.append(
            dict(
                context_source_id="greves_idf",
                variable="is_strike",
                local_date=date,
                valid_time=None,
                value=str(date == "2025-03-31").lower(),
                role="known_calendar",
                available_at=(midnight - pd.Timedelta(hours=24)).isoformat(),
            )
        )
    for i, valid in enumerate(pd.date_range("2025-02-01", "2025-04-12", freq="h", tz="UTC")):
        available = valid - pd.Timedelta(hours=42)
        if valid == ORIGIN + pd.Timedelta(hours=5):  # bulletin de h5 publié trop tard
            available = ORIGIN + pd.Timedelta(hours=1)
        for source, variable, role in [
            ("meteo_prevue", "temp_prev", "forecast_bulletin"),
            ("meteo_observee", "temp_obs", "past_observation"),
        ]:
            rows.append(
                dict(
                    context_source_id=source,
                    variable=variable,
                    local_date=None,
                    valid_time=valid.isoformat(),
                    value=str(float(i)),
                    role=role,
                    available_at=available.isoformat(),
                )
            )
    return pd.DataFrame(rows)


def make_case(origin: pd.Timestamp = ORIGIN) -> Case:
    return Case(
        case_id="K1",
        counter_id="C-1",
        site_group_id="G-1",
        origin=origin,
        scenario="known_site",
        protocol_id="P-test",
        snapshot_id="S-test",
    )


@pytest.fixture(scope="module")
def counts() -> pd.DataFrame:
    return make_counts()


@pytest.fixture(scope="module")
def context() -> pd.DataFrame:
    return make_context()


@pytest.fixture(scope="module")
def frame(counts, context) -> pd.DataFrame:
    inputs = build_inputs(make_case(), measured_history(counts), context, LAG)
    return build_feature_frame(inputs)


def test_calendar_features_across_dst():
    targets = target_timestamps(ORIGIN)["target_timestamp"]
    cal = calendar_features(targets)
    assert cal["hour_local"].tolist() == [0, 1] + list(range(3, 24)) + [0]
    assert cal["dow_local"].iloc[0] == 6 and cal["is_weekend"].iloc[0] == 1
    assert cal["dow_local"].iloc[-1] == 0 and cal["is_weekend"].iloc[-1] == 0
    assert set(cal["month_local"]) == {3}


def test_frame_shape_columns_and_trace(frame):
    assert len(frame) == 24
    assert frame["horizon"].tolist() == list(range(1, 25))
    assert (
        frame["target_timestamp"].tolist() == target_timestamps(ORIGIN)["target_timestamp"].tolist()
    )
    expected = META_COLUMNS + [c for c in feature_columns(CONTEXT_GROUPS) if c != "horizon"]
    assert frame.columns.tolist() == expected
    assert (frame["feature_version"] == FEATURE_VERSION).all()
    assert frame["max_input_available_at"].notna().all()
    assert (frame["max_input_available_at"] <= ORIGIN).all()
    assert "temp_obs" not in frame.columns


def test_history_matches_references(counts, context, frame):
    inputs = build_inputs(make_case(), measured_history(counts), context, LAG)
    admissible = baseline.admissible_history(inputs.history, CUTOFF, counter_id="C-1")
    targets = target_timestamps(ORIGIN)["target_timestamp"]
    lag = baseline.lookup_lagged(admissible, targets, pd.Timedelta(hours=168))
    np.testing.assert_allclose(frame["lag_168h"], lag.to_numpy(), equal_nan=True)

    profile = baseline.weekly_profile_reference(inputs).predictions
    ok = (profile["method_used"] == baseline.PROFILE_METHOD_NAME).to_numpy()
    assert ok.sum() == 24
    np.testing.assert_allclose(frame["profile_median_4w"][ok], profile["y_pred"][ok], rtol=1e-6)


def test_zero_and_missing_stay_distinct(frame):
    h1, h2 = frame.iloc[0], frame.iloc[1]
    assert h1["lag_168h"] == 0.0 and h1["lag_168h_missing"] == 0.0
    assert np.isnan(h2["lag_168h"]) and h2["lag_168h_missing"] == 1.0  # jamais 999 (E1)
    assert h2["profile_n_weeks"] == 3


def test_recent_statistics_by_hand(counts, frame):
    measured = measured_history(counts).set_index(pd.to_datetime(counts["timestamp"], utc=True))
    last = CUTOFF - pd.Timedelta(hours=1)
    day = measured.loc[last - pd.Timedelta(hours=23) : last, "count"]
    week = measured.loc[last - pd.Timedelta(hours=167) : last, "count"]
    prev = measured.loc[last - pd.Timedelta(hours=335) : last - pd.Timedelta(hours=168), "count"]
    row = frame.iloc[0]
    assert row["level_24h"] == pytest.approx(day.mean(), rel=1e-6)
    assert row["level_168h"] == pytest.approx(week.mean(), rel=1e-6)
    assert row["missing_share_168h"] == pytest.approx(week.isna().mean())
    assert row["trend_7d_log"] == pytest.approx(
        np.log1p(week.mean()) - np.log1p(prev.mean()), rel=1e-5
    )
    assert row["zero_run_hours"] == 5  # 18:00 à 22:00 UTC le 28/03
    assert row["hours_since_last_obs"] == LAG  # dernière mesure finit à la coupure
    # Variables de l'origine : identiques pour les 24 horizons.
    assert frame["level_24h"].nunique() == 1


def test_future_values_do_not_change_features(counts, context, frame):
    future = counts.copy()
    after = pd.to_datetime(future["interval_end"], utc=True) > CUTOFF
    future.loc[after, "count_raw"] = future.loc[after, "count_raw"] * 10 + 7
    late_context = context.copy()
    late = pd.to_datetime(late_context["available_at"], utc=True, format="ISO8601") > ORIGIN
    late_context.loc[late, "value"] = "12345"
    # Sans passer par build_inputs : le calcul doit filtrer lui-même.
    raw = ForecastInputs(
        case=make_case(),
        history=measured_history(future),
        information_cutoff=CUTOFF,
        context=late_context,
    )
    pd.testing.assert_frame_equal(build_feature_frame(raw), frame)


def test_context_join_by_local_date_and_interval_end(frame, context):
    holiday = frame["is_holiday"].tolist()
    assert holiday == [1.0] * 23 + [0.0]  # 30/03 local a 23 heures ; h24 = 31/03 00:00
    assert frame["is_strike"].tolist() == [0.0] * 23 + [1.0]
    assert (frame["is_school_holiday"] == 0).all()
    weather = context.loc[context["variable"] == "temp_prev"].set_index("valid_time")["value"]
    for h in (1, 12, 24):
        valid = (ORIGIN + pd.Timedelta(hours=h)).isoformat()  # interval_end de la cible
        assert frame.loc[h - 1, "temp_prev"] == pytest.approx(float(weather[valid]))
    assert np.isnan(frame.loc[4, "temp_prev"])  # h5 : bulletin publié après l'origine
    assert frame["rain_prev"].isna().all() and frame["wind_prev"].isna().all()


def test_late_strike_announcement_is_masked(counts, context):
    late = context.copy()
    strike = (late["variable"] == "is_strike") & (late["local_date"] == "2025-03-31")
    late.loc[strike, "available_at"] = (ORIGIN + pd.Timedelta(hours=2)).isoformat()
    raw = ForecastInputs(
        case=make_case(), history=measured_history(counts), information_cutoff=CUTOFF, context=late
    )
    assert np.isnan(build_feature_frame(raw)["is_strike"].iloc[-1])


def test_duplicate_context_key_is_refused(counts, context):
    duplicated = pd.concat([context, context.loc[context["variable"] == "is_holiday"].head(1)])
    inputs = build_inputs(make_case(), measured_history(counts), duplicated, LAG)
    with pytest.raises(ValueError, match="double"):
        build_feature_frame(inputs)


def test_ablation_removes_only_context_columns(counts, context, frame):
    inputs = build_inputs(make_case(), measured_history(counts), context, LAG)
    without = build_feature_frame(inputs, use_context=False)
    context_columns = [v for vs in CONTEXT_GROUPS.values() for v in vs]
    assert without.columns.tolist() == [c for c in frame.columns if c not in context_columns]
    shared = [c for c in without.columns if c != "max_input_available_at"]
    pd.testing.assert_frame_equal(without[shared], frame[shared])

    calendar_only = build_feature_frame(inputs, context_groups=["calendar"])
    added = [c for c in calendar_only.columns if c not in without.columns]
    assert added == CONTEXT_GROUPS["calendar"]
    with pytest.raises(ValueError, match="inconnus"):
        build_feature_frame(inputs, context_groups=["meteo_observee"])


def test_training_frame_equals_per_case_frames(counts, context):
    origins = training_origins(counts, ["C-1"], FIT_CUTOFF, publication_lag_hours=LAG)
    X, y = build_training_frame(counts, origins, context, FIT_CUTOFF, publication_lag_hours=LAG)
    history = measured_history(counts)
    compared = [c for c in X.columns if c not in ("case_id", "counter_id")]
    for origin in [ORIGIN, origins["origin"].iloc[0], origins["origin"].iloc[-1]]:
        case = build_feature_frame(build_inputs(make_case(origin), history, context, LAG))
        bulk = X.loc[X["origin"] == origin].set_index("target_timestamp")
        per_case = case.set_index("target_timestamp").loc[bulk.index]
        assert len(bulk) >= 23
        pd.testing.assert_frame_equal(
            bulk[[c for c in compared if c != "target_timestamp"]],
            per_case[[c for c in compared if c != "target_timestamp"]],
        )


def test_training_labels(counts, context):
    origins = training_origins(counts, ["C-1"], FIT_CUTOFF, publication_lag_hours=LAG)
    X, y = build_training_frame(counts, origins, context, FIT_CUTOFF, publication_lag_hours=LAG)
    assert len(X) == len(y) and y.notna().all()
    raw = counts.set_index(pd.to_datetime(counts["timestamp"], utc=True))["count_raw"]
    np.testing.assert_allclose(y, raw.loc[X["target_timestamp"]].to_numpy())
    targets = set(X["target_timestamp"].map(pd.Timestamp.isoformat))
    assert NOT_SCOREABLE not in targets and H2_SOURCE not in targets
    assert H1_SOURCE in targets and (y == 0).any()  # zéro mesuré gardé comme cible
    assert (X["target_timestamp"] + pd.Timedelta(hours=1 + LAG) <= FIT_CUTOFF).all()
    assert (X["max_input_available_at"] <= X["origin"]).all()


def test_training_origins_are_local_midnights(counts):
    origins = training_origins(counts, ["C-1"], FIT_CUTOFF, publication_lag_hours=LAG)
    local = origins["origin"].dt.tz_convert("Europe/Paris")
    assert (local.dt.hour == 0).all() and local.is_unique
    first = pd.Timestamp("2025-02-01T00:00Z")
    assert origins["origin"].min() >= first + pd.Timedelta(hours=4 * 168 + LAG)
    assert origins["origin"].max() + pd.Timedelta(hours=24 + LAG) <= FIT_CUTOFF
    assert {ORIGIN, pd.Timestamp("2025-03-30T22:00Z")} <= set(origins["origin"])


def test_training_counters_exclude_reserved_groups():
    inventory = pd.DataFrame(
        {
            "counter_id": ["A", "B", "C", "D", "A"],
            "site_group_id": ["G1", "G2", "G3", "G4", "G1"],
            "site_role": ["S_train", "S_train", "S_dev_new", None, "S_train"],
            "selection_status": [
                "retained",
                "robustness",
                "reserved_dev_new",
                "excluded",
                "retained",
            ],
            "period_role": ["selection"] * 4 + ["full_snapshot"],
        }
    )
    assert training_counters(inventory) == ["A", "B"]
    assert training_counters(inventory, include_robustness=False) == ["A"]
    inventory.loc[2, "site_group_id"] = "G1"
    with pytest.raises(ValueError, match="réservés"):
        training_counters(inventory)


def test_timestamps_without_timezone_are_refused():
    with pytest.raises(ValueError, match="fuseau"):
        features._to_hours(pd.Series(["2025-03-01T00:00:00"]), "timestamp")

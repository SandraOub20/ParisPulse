"""Référence hebdomadaire E2 sur un petit cas construit à la main (données synthétiques).

Ces données vérifient le code ; elles ne mesurent aucune performance sur Paris.

Cas principal : origine 2025-03-29T23:00Z (minuit local du dimanche 30 mars 2025, jour du
passage à l'heure d'été), latence simulée de 24 h, donc coupure d'information 2025-03-28T23:00Z.
Chaque comptage vaut MDDHH de son heure UTC (ex. 23 mars 11:00Z -> 32311) pour lire la source
de chaque prévision. Valeurs attendues calculées à la main :

| h  | cible UTC         | source t-168 h        | attendu                                   |
| 1  | 2025-03-29 23:00  | 2025-03-22 23:00      | 32223, ok                                 |
| 7  | 2025-03-30 05:00  | 2025-03-23 05:00 = 0  | 0.0, ok (zéro observé conservé)           |
| 12 | 2025-03-30 10:00  | count manquant        | repli : dimanche 12:00 locale =           |
|    |                   |                       | 23/03 11Z, 16/03 11Z, 09/03 11Z, 02/03 11Z |
|    |                   |                       | médiane(32311, 31611, 30911, 30211)=31261 |
| 17 | 2025-03-30 15:00  | ligne absente         | repli : dimanche 17:00 locale = 16Z       |
|    |                   |                       | médiane(32316, 31616, 30916, 30216)=31266 |
| 24 | 2025-03-30 22:00  | 2025-03-23 22:00      | 32322, ok                                 |

Le repli suit l'heure locale (11Z en CET) alors que la valeur principale suit 168 h UTC
(10Z) : c'est le décalage I3 rendu visible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.known import baseline
from src.models.known.predict import write_predictions, write_runs
from src.models.schemas import (
    CASE_RUNS_COLUMNS,
    FORECAST_COLUMNS,
    Case,
    ForecastInputs,
    target_timestamps,
)

UTC = "UTC"
ORIGIN = pd.Timestamp("2025-03-29T23:00", tz=UTC)
LAG = pd.Timedelta(hours=24)
FUTURE_VALUE = 777_777.0


def encoded(ts: pd.Timestamp) -> float:
    return float(ts.month * 10_000 + ts.day * 100 + ts.hour)


def make_case(case_id: str = "C1", origin: pd.Timestamp = ORIGIN) -> Case:
    return Case(
        case_id=case_id,
        counter_id="TEST-1",
        site_group_id="G-TEST",
        origin=origin,
        scenario="known_site",
        protocol_id="P-test",
        snapshot_id="S-synthetic",
    )


def make_history() -> pd.DataFrame:
    """Grille horaire du 22/02 23Z au 30/03 22Z, future comprise pour tester la causalité."""
    timestamps = pd.date_range("2025-02-22T23:00", "2025-03-30T22:00", freq="h", tz=UTC)
    counts = [encoded(ts) for ts in timestamps]
    history = pd.DataFrame(
        {
            "counter_id": "TEST-1",
            "timestamp": timestamps,
            "interval_end": timestamps + pd.Timedelta(hours=1),
            "count": counts,
            "is_observed": True,
        }
    )
    at = history["timestamp"]
    history.loc[at == pd.Timestamp("2025-03-23T05:00", tz=UTC), "count"] = 0.0
    missing = at == pd.Timestamp("2025-03-23T10:00", tz=UTC)
    history.loc[missing, ["count", "is_observed"]] = [np.nan, False]
    history = history.loc[at != pd.Timestamp("2025-03-23T15:00", tz=UTC)]
    # Le jour cible lui-même est présent dans le fichier mais jamais admissible.
    history.loc[history["timestamp"] >= ORIGIN, "count"] = FUTURE_VALUE
    return history.reset_index(drop=True)


def make_inputs(history: pd.DataFrame, case: Case | None = None) -> ForecastInputs:
    case = case or make_case()
    return ForecastInputs(case=case, history=history, information_cutoff=case.origin - LAG)


def by_horizon(result) -> pd.DataFrame:
    return result.predictions.set_index("horizon")


def test_hand_computed_values():
    result = baseline.weekly_reference(make_inputs(make_history()))
    preds = by_horizon(result)

    assert preds.loc[1, "y_pred"] == 32223.0
    assert preds.loc[7, "y_pred"] == 0.0
    assert preds.loc[7, "prediction_status"] == "ok"
    assert preds.loc[12, "y_pred"] == 31261.0
    assert preds.loc[12, "method_used"] == baseline.FALLBACK_DOW_HOUR
    assert preds.loc[17, "y_pred"] == 31266.0
    assert preds.loc[17, "prediction_status"] == "fallback"
    assert preds.loc[24, "y_pred"] == 32322.0

    assert preds["prediction_status"].value_counts().to_dict() == {"ok": 22, "fallback": 2}
    assert result.status == "fallback"
    assert result.is_complete()


def test_all_targets_use_lag_168h_by_timestamp():
    result = baseline.weekly_reference(make_inputs(make_history()))
    ok = result.predictions[result.predictions["prediction_status"] == "ok"]
    expected = [
        0.0 if src.hour == 5 and src.day == 23 else encoded(src)
        for src in ok["target_timestamp"] - pd.Timedelta(hours=168)
    ]
    assert ok["y_pred"].tolist() == expected


def test_future_rows_are_never_used():
    history = make_history()
    reference = baseline.weekly_reference(make_inputs(history)).predictions["y_pred"]

    perturbed = history.copy()
    after_cutoff = perturbed["interval_end"] > ORIGIN - LAG
    perturbed.loc[after_cutoff, "count"] = -1.0
    changed = baseline.weekly_reference(make_inputs(perturbed)).predictions["y_pred"]

    pd.testing.assert_series_equal(reference, changed)
    assert FUTURE_VALUE not in reference.tolist()


def test_hour_profile_fallback_when_weekday_absent():
    # Origine jeudi 16/01 00:00 locale ; historique lundi 13 et mardi 14 seulement.
    origin = pd.Timestamp("2025-01-15T23:00", tz=UTC)
    timestamps = pd.date_range("2025-01-12T23:00", "2025-01-14T22:00", freq="h", tz=UTC)
    local_day = timestamps.tz_convert("Europe/Paris").day
    history = pd.DataFrame(
        {"timestamp": timestamps, "count": np.where(local_day == 13, 10.0, 20.0)}
    )
    result = baseline.weekly_reference(make_inputs(history, make_case(origin=origin)))

    assert (result.predictions["y_pred"] == 15.0).all()
    assert (result.predictions["method_used"] == baseline.FALLBACK_HOUR).all()
    assert result.is_complete()


def test_no_history_gives_explicit_unavailable_not_zero():
    history = pd.DataFrame({"timestamp": pd.DatetimeIndex([], tz=UTC), "count": []})
    result = baseline.weekly_reference(make_inputs(history))

    assert result.predictions["y_pred"].isna().all()
    assert (result.predictions["prediction_status"] == "unavailable").all()
    assert (result.predictions["status_reason"] == baseline.REASON_NO_FALLBACK).all()
    assert result.status == "unavailable"
    assert not result.is_complete()


def test_fallback_value_matches_reference_path():
    history = make_history()
    target = pd.Timestamp("2025-03-30T10:00", tz=UTC)
    assert baseline.fallback_value(history, target, ORIGIN - LAG) == 31261.0


def test_lookup_lagged_joins_on_timestamp_not_position():
    history = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2025-01-01T00:00Z", "2025-01-01T02:00Z"], utc=True
            ),  # 01:00 absente de la grille
            "count": [5.0, 7.0],
        }
    )
    targets = pd.Series(pd.to_datetime(["2025-01-01T01:00Z", "2025-01-01T03:00Z"], utc=True))
    lagged = baseline.lookup_lagged(history, targets, pd.Timedelta(hours=1))
    assert lagged.tolist() == [5.0, 7.0]


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda h: pd.concat([h, h.iloc[[0]]]), "double"),
        (lambda h: h.assign(timestamp=h["timestamp"].dt.tz_localize(None)), "fuseau"),
        (lambda h: h.assign(counter_id="OTHER"), "compteurs"),
    ],
)
def test_invalid_history_is_refused(mutate, message):
    with pytest.raises(ValueError, match=message):
        baseline.weekly_reference(make_inputs(mutate(make_history())))


def test_cutoff_after_origin_is_refused():
    case = make_case()
    inputs = ForecastInputs(case=case, history=make_history(), information_cutoff=ORIGIN + LAG)
    with pytest.raises(ValueError, match="postérieure"):
        baseline.weekly_reference(inputs)


def test_horizons_cross_dst_as_24_elapsed_hours():
    targets = target_timestamps(ORIGIN)["target_timestamp"]
    assert targets.diff().dropna().eq(pd.Timedelta(hours=1)).all()
    local = targets.dt.tz_convert("Europe/Paris")
    assert local.iloc[0].hour == 0 and local.iloc[-1].hour == 0  # 23 h civiles + 1


def test_exports_follow_templates(tmp_path):
    ok = baseline.weekly_reference(make_inputs(make_history()), method_run_id="e2-ref-test")
    empty = pd.DataFrame({"timestamp": pd.DatetimeIndex([], tz=UTC), "count": []})
    missing = baseline.weekly_reference(
        make_inputs(empty, make_case("C2")), method_run_id="e2-ref-test"
    )

    pred_path = write_predictions([ok, missing], tmp_path / "EXP" / "e2-ref-test.pred.csv")
    runs_path = write_runs([ok, missing], tmp_path / "EXP" / "e2-ref-test.runs.csv")

    pred = pd.read_csv(pred_path, dtype=str, keep_default_na=False)
    assert list(pred.columns) == FORECAST_COLUMNS
    assert len(pred) == 48
    assert pred.groupby("case_id")["horizon"].nunique().eq(24).all()
    assert pred.loc[0, "origin"] == "2025-03-29T23:00:00+00:00"
    assert pred.loc[0, "target_timestamp"] == "2025-03-29T23:00:00+00:00"
    c2 = pred[pred["case_id"] == "C2"]
    assert (c2["y_pred"] == "").all() and (c2["prediction_status"] == "unavailable").all()
    assert pred.loc[(pred["case_id"] == "C1") & (pred["horizon"] == "7"), "y_pred"].item() == "0.0"

    runs = pd.read_csv(runs_path, dtype=str, keep_default_na=False)
    assert list(runs.columns) == CASE_RUNS_COLUMNS
    assert runs["case_id"].tolist() == ["C1", "C2"]
    assert runs["status"].tolist() == ["fallback", "unavailable"]
    assert set(runs["cache_hit"]) == {"false"}


def test_profile_hand_computed_values():
    """Médiane de t-168, t-336, t-504, t-672 h (sources UTC, mêmes données que ci-dessus).

    h1  : 22/03 23Z, 15/03 23Z, 08/03 23Z, 01/03 23Z -> médiane(32223, 31523, 30823, 30123)
          = (30823 + 31523) / 2 = 31173
    h7  : 23/03 05Z = 0, 31605, 30905, 30205 -> médiane = (30205 + 30905) / 2 = 30555
    h12 : 23/03 10Z manquant, 31610, 30910, 30210 -> médiane de 3 = 30910, sans repli
    h17 : 23/03 15Z absent de la grille, 31615, 30915, 30215 -> 30915, sans repli
    """
    result = baseline.weekly_profile_reference(make_inputs(make_history()))
    preds = by_horizon(result)

    assert preds.loc[1, "y_pred"] == 31173.0
    assert preds.loc[7, "y_pred"] == 30555.0
    assert preds.loc[12, "y_pred"] == 30910.0
    assert preds.loc[17, "y_pred"] == 30915.0
    assert (preds["prediction_status"] == "ok").all()
    assert (preds["method_used"] == baseline.PROFILE_METHOD_NAME).all()
    assert result.variant == baseline.PROFILE_VARIANT
    assert result.method_run_id == "weekly_profile_median-0.1.0"
    assert result.status == "ok" and result.is_complete()


def test_profile_with_one_week_equals_weekly_naive():
    history = make_history()
    naive = baseline.weekly_reference(make_inputs(history)).predictions["y_pred"]
    profile = baseline.weekly_profile_reference(make_inputs(history), n_weeks=1)
    pd.testing.assert_series_equal(naive, profile.predictions["y_pred"])


def test_profile_falls_back_then_reports_unavailable():
    origin = pd.Timestamp("2025-01-15T23:00", tz=UTC)
    timestamps = pd.date_range("2025-01-12T23:00", "2025-01-14T22:00", freq="h", tz=UTC)
    history = pd.DataFrame({"timestamp": timestamps, "count": 15.0})
    result = baseline.weekly_profile_reference(make_inputs(history, make_case(origin=origin)))
    assert (result.predictions["method_used"] == baseline.FALLBACK_HOUR).all()
    assert (result.predictions["status_reason"] == baseline.REASON_PROFILE_MISSING).all()

    empty = pd.DataFrame({"timestamp": pd.DatetimeIndex([], tz=UTC), "count": []})
    result = baseline.weekly_profile_reference(make_inputs(empty))
    assert result.status == "unavailable" and result.predictions["y_pred"].isna().all()


def test_profile_ignores_future_rows():
    history = make_history()
    reference = baseline.weekly_profile_reference(make_inputs(history)).predictions["y_pred"]
    perturbed = history.copy()
    perturbed.loc[perturbed["interval_end"] > ORIGIN - LAG, "count"] = -1.0
    changed = baseline.weekly_profile_reference(make_inputs(perturbed)).predictions["y_pred"]
    pd.testing.assert_series_equal(reference, changed)


def test_export_refuses_duplicate_case(tmp_path):
    result = baseline.weekly_reference(make_inputs(make_history()))
    with pytest.raises(ValueError, match="double"):
        write_predictions([result, result], tmp_path / "dup.pred.csv")

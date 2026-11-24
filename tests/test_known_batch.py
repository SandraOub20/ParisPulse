"""Calcul en bloc (batch.py) : mêmes sorties que le calcul cas par cas (synthétique)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.known import batch as B
from src.models.known import features as F
from src.models.known import neural as N
from src.models.known import predict as P
from src.models.known import train
from src.models.schemas import Case

PARIS = "Europe/Paris"
LAG = 24
CUTOFF = pd.Timestamp("2026-07-01 00:00", tz=PARIS).tz_convert("UTC")
START = pd.Timestamp("2026-04-06 00:00", tz=PARIS).tz_convert("UTC")
END = pd.Timestamp("2026-07-25 00:00", tz=PARIS).tz_convert("UTC")
LEVELS = {"A-1": 100.0, "A-2": 20.0, "A-3": 300.0}
FAST = {"hidden": 16, "layers": 1, "lr": 3e-3, "batch_size": 64, "max_epochs": 4, "patience": 4}


def _paris(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz=PARIS).tz_convert("UTC")


def _series(counter_id: str, level: float, start=START) -> pd.DataFrame:
    hours = pd.date_range(start, END, freq="h", inclusive="left")
    local = hours.tz_convert(PARIS)
    hour = local.hour.to_numpy(dtype=float)
    weekday = local.dayofweek.to_numpy() < 5
    commute = np.exp(-(((hour - 8) / 1.5) ** 2)) + np.exp(-(((hour - 18) / 1.8) ** 2))
    value = np.round(level * np.where(weekday, 0.15 + 1.6 * commute, 0.3), 1)
    return pd.DataFrame(
        {
            "counter_id": counter_id,
            "timestamp": hours,
            "interval_end": hours + pd.Timedelta(hours=1),
            "count": value,
            "count_raw": value,
            "is_observed": True,
            "is_scoreable": True,
        }
    )


def _context() -> pd.DataFrame:
    days = pd.date_range("2026-04-01", "2026-07-30", freq="D")
    midnights = days.tz_localize(PARIS).tz_convert("UTC")
    daily = [
        pd.DataFrame(
            {
                "variable": variable,
                "local_date": days.strftime("%Y-%m-%d"),
                "valid_time": None,
                "value": np.where(days == "2026-07-14", "true", "false")
                if variable == "is_holiday"
                else "false",
                "available_at": (midnights - pd.Timedelta(hours=24)).map(pd.Timestamp.isoformat)
                if variable == "is_strike"
                else None,
                "role": "known_calendar",
            }
        )
        for variable in ("is_holiday", "is_school_holiday", "is_strike")
    ]
    valid = pd.date_range(START, END + pd.Timedelta(days=3), freq="h")
    hourly = [
        pd.DataFrame(
            {
                "variable": variable,
                "local_date": None,
                "valid_time": valid.map(pd.Timestamp.isoformat),
                "value": values.astype(str),
                # bulletin publié 42 h avant ; un trou de bulletin le 12/07 : contexte inconnu
                "available_at": (valid - pd.Timedelta(hours=42)).map(pd.Timestamp.isoformat),
                "role": "forecast_bulletin",
            }
        ).loc[lambda d, v=valid: ~((v >= _paris("2026-07-12")) & (v < _paris("2026-07-13")))]
        for variable, values in (
            ("temp_prev", 15 + 5 * np.sin(2 * np.pi * valid.hour.to_numpy() / 24)),
            ("rain_prev", np.zeros(len(valid))),
            ("wind_prev", np.full(len(valid), 3.0)),
        )
    ]
    return pd.concat(daily + hourly, ignore_index=True)


@pytest.fixture(scope="module")
def counts() -> pd.DataFrame:
    frames = [_series(c, level) for c, level in LEVELS.items()]
    frames.append(_series("A-4", 50.0, start=_paris("2026-07-10")))  # installé le 10/07
    out = pd.concat(frames, ignore_index=True)
    # A-2 : panne de 120 h avant l'origine du 09/07 (fenêtre trop vide pour le seuil de 84 h)
    gap = (out["counter_id"] == "A-2") & out["timestamp"].between(
        _paris("2026-07-02 22:00"), _paris("2026-07-07 21:00")
    )
    out.loc[gap, ["count", "count_raw"]] = np.nan
    out.loc[gap, ["is_observed", "is_scoreable"]] = False
    return out


def _model(counts: pd.DataFrame, use_context: bool) -> train.TrainedModel:
    learn = counts.loc[counts["counter_id"].isin(list(LEVELS))]
    config = train.TrainConfig(
        method="mlp",
        fit_cutoff=CUTOFF,
        use_context=use_context,
        hyperparameters=N.mlp_hyperparameters(**FAST),
    )
    origins = F.training_origins(learn, sorted(LEVELS), CUTOFF, publication_lag_hours=LAG)
    net = N.fit_mlp(config, learn, _context() if use_context else None, origins)
    return train.TrainedModel(
        model_run_id="e2-mlp-test",
        config=config,
        estimator=net,
        donor_site_groups=[],
        label_interval=(CUTOFF, CUTOFF),
        train_seconds=0.0,
    )


@pytest.fixture(scope="module")
def model(counts) -> train.TrainedModel:
    return _model(counts, use_context=False)


@pytest.fixture(scope="module")
def ctx_model(counts) -> train.TrainedModel:
    return _model(counts, use_context=True)


def _cases() -> list[Case]:
    cases = []
    for counter in ("A-1", "A-2", "A-3", "A-4"):
        for day in range(3, 16):
            cases.append(_case(counter, _paris(f"2026-07-{day:02d}")))
    cases.append(_case("A-1", _paris("2026-07-05 06:00")))  # hors minuit
    cases.append(_case("A-1", _paris("2026-06-25")))  # avant la coupure
    return cases


def _case(counter: str, origin: pd.Timestamp) -> Case:
    return Case(
        case_id=f"T|{counter}|{origin.isoformat()}",
        counter_id=counter,
        site_group_id=None,
        origin=origin,
        scenario="known_site",
        protocol_id="test",
        snapshot_id="synthetic",
    )


def _one_by_one(cases, counts, context, model, **kw):
    values, reasons = [], []
    for case in cases:
        history = counts.loc[counts["counter_id"] == case.counter_id]
        inputs = P.build_inputs(case, history, context, publication_lag_hours=LAG)
        out = N.predict_mlp(model.estimator, inputs, fit_cutoff=model.config.fit_cutoff, **kw)
        values.append(out.values if out.ok else np.full(24, np.nan))
        reasons.append(out.reason)
    return np.array(values), reasons


def _check_same(batch, single):
    (bv, br), (sv, sr) = batch, single
    assert br == sr
    np.testing.assert_allclose(bv, sv, rtol=0, atol=1e-3, equal_nan=True)


def test_bloc_egal_cas_par_cas_sans_contexte(counts, model):
    cases = _cases()
    batch = B.batch_raw_mlp(cases, counts, None, model, publication_lag_hours=LAG)
    single = _one_by_one(cases, counts, None, model)
    _check_same(batch, single)
    reasons = set(batch[1])
    # tous les motifs sont couverts par ce jeu de cas
    assert {
        None,
        N.REFUSE_SPARSE,
        N.REFUSE_NO_HISTORY,
        N.REFUSE_NOT_MIDNIGHT,
        N.REFUSE_BEFORE_CUTOFF,
    } <= reasons


def test_bloc_egal_cas_par_cas_avec_contexte(counts, ctx_model):
    cases = _cases()
    context = _context()
    batch = B.batch_raw_mlp(cases, counts, context, ctx_model, publication_lag_hours=LAG)
    single = _one_by_one(cases, counts, context, ctx_model)
    _check_same(batch, single)
    assert N.REFUSE_CONTEXT in batch[1]  # trou de bulletin du 12/07


def test_bloc_sans_contexte_pour_un_modele_avec_contexte(counts, ctx_model):
    cases = _cases()[:5]
    _, reasons = B.batch_raw_mlp(cases, counts, None, ctx_model, publication_lag_hours=LAG)
    assert set(reasons) == {N.REFUSE_CONTEXT}


def test_bloc_seuil_remplace_comme_cas_par_cas(counts, model):
    cases = _cases()
    batch = B.batch_raw_mlp(
        cases, counts, None, model, min_observed_hours=24, publication_lag_hours=LAG
    )
    single = _one_by_one(cases, counts, None, model, min_observed_hours=24)
    _check_same(batch, single)
    assert N.REFUSE_SPARSE not in batch[1]  # la panne de A-2 est servie au seuil de 24 h


def test_bloc_refuse_une_autre_latence(counts, model):
    with pytest.raises(ValueError, match="latence"):
        B.batch_raw_mlp(_cases()[:2], counts, None, model, publication_lag_hours=48)


def test_bloc_vide(counts, model):
    values, reasons = B.batch_raw_mlp([], counts, None, model, publication_lag_hours=LAG)
    assert values.shape == (0, 24) and reasons == []


# --- HGB -----------------------------------------------------------------------------------


def _hgb(counts: pd.DataFrame, use_context: bool) -> train.TrainedModel:
    from src.models.known import tabular as T

    learn = counts.loc[counts["counter_id"].isin(list(LEVELS))]
    config = train.TrainConfig(
        method="hgb",
        fit_cutoff=CUTOFF,
        use_context=use_context,
        hyperparameters=T.hgb_hyperparameters(max_iter=20, min_samples_leaf=5, patience=20),
        feature_version=F.FEATURE_VERSION,
    )
    origins = F.training_origins(learn, sorted(LEVELS), CUTOFF, publication_lag_hours=LAG)
    estimator = T.fit_hgb(config, learn, _context() if use_context else None, origins)
    return train.TrainedModel(
        model_run_id="e2-hgb-test",
        config=config,
        estimator=estimator,
        donor_site_groups=[],
        label_interval=(CUTOFF, CUTOFF),
        train_seconds=0.0,
    )


def _one_by_one_hgb(cases, counts, context, model):
    from src.models.known import tabular as T

    values, reasons = [], []
    for case in cases:
        history = counts.loc[counts["counter_id"] == case.counter_id]
        inputs = P.build_inputs(case, history, context, publication_lag_hours=LAG)
        out = T.predict_hgb(model.estimator, inputs)
        values.append(out.values if out.ok else np.full(24, np.nan))
        reasons.append(out.reason)
    return np.array(values), reasons


@pytest.mark.parametrize("use_context", [False, True])
def test_hgb_bloc_egal_cas_par_cas(counts, use_context):
    from src.models.known import tabular as T

    model = _hgb(counts, use_context)
    context = _context() if use_context else None
    cases = _cases()
    batch = B.batch_raw_hgb(cases, counts, context, model, publication_lag_hours=LAG)
    single = _one_by_one_hgb(cases, counts, context, model)
    (bv, br), (sv, sr) = batch, single
    assert br == sr
    np.testing.assert_allclose(bv, sv, rtol=0, atol=1e-9, equal_nan=True)
    # le HGB sert la semaine trouée de A-2 ; il refuse le compteur pas encore installé
    assert T.REFUSE_NO_HISTORY in br and T.REFUSE_NOT_MIDNIGHT in br
    assert {r for r, c in zip(br, cases, strict=True) if c.counter_id == "A-2"} <= {None}


def test_hgb_bloc_sans_contexte_pour_un_modele_avec_contexte(counts):
    from src.models.known import tabular as T

    model = _hgb(counts, use_context=True)
    _, reasons = B.batch_raw_hgb(_cases()[:5], counts, None, model, publication_lag_hours=LAG)
    assert set(reasons) == {T.REFUSE_CONTEXT}


def test_hgb_bloc_refuse_une_autre_latence(counts):
    model = _hgb(counts, use_context=False)
    with pytest.raises(ValueError, match="latence"):
        B.batch_raw_hgb(_cases()[:2], counts, None, model, publication_lag_hours=48)

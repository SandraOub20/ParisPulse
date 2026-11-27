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


# --- run_experiment_batch : mêmes fichiers que run_experiment -------------------------------

COST_COLUMNS = ["preparation_seconds", "inference_seconds", "wait_seconds", "memory_mb"]


def _cases_frame() -> pd.DataFrame:
    rows = []
    for case in _cases() + [_case("Z-9", _paris("2026-07-05"))]:  # Z-9 : compteur inconnu
        rows.append(
            {
                "case_id": case.case_id,
                "counter_id": case.counter_id,
                "site_group_id": "G",
                "origin": case.origin.isoformat(),
                "scenario": "known_site",
                "temporal_split": "validation",
                "spatial_role": "S_train",
                "local_budget_hours": "",
                "support_start": "",
                "support_end": "",
                "protocol_id": "test",
                "snapshot_id": "synthetic",
            }
        )
    return pd.DataFrame(rows)


def _loader(counts: pd.DataFrame):
    by_counter = {k: v.reset_index(drop=True) for k, v in counts.groupby("counter_id")}

    def load(counter_id: str) -> pd.DataFrame:
        if counter_id not in by_counter:
            raise ValueError(f"compteur {counter_id} absent")
        return by_counter[counter_id]

    return load


def _both(tmp_path, monkeypatch, counts, model, variant, context=None, **kw):
    import dataclasses

    model = dataclasses.replace(model, donor_site_groups=["G"])
    monkeypatch.setattr(P, "_load_model", lambda v, run_id: model)
    cases = _cases_frame()
    args = (cases, _loader(counts), variant, "EXP-test", "run-test")
    single = P.run_experiment(
        *args, context=context, root=tmp_path / "un", publication_lag_hours=LAG, **kw
    )
    bloc = B.run_experiment_batch(
        *args, context=context, root=tmp_path / "bloc", publication_lag_hours=LAG, **kw
    )
    read = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in (*single, *bloc)]
    return read  # pred_un, runs_un, pred_bloc, runs_bloc


def _assert_same_files(pred_un, runs_un, pred_bloc, runs_bloc):
    assert list(pred_un.columns) == list(pred_bloc.columns)
    other = [c for c in pred_un.columns if c != "y_pred"]
    pd.testing.assert_frame_equal(pred_un[other], pred_bloc[other])
    y_un = pd.to_numeric(pred_un["y_pred"].replace("", np.nan))
    y_bloc = pd.to_numeric(pred_bloc["y_pred"].replace("", np.nan))
    np.testing.assert_allclose(y_bloc, y_un, rtol=0, atol=1e-3, equal_nan=True)
    assert (pred_un["y_pred"] == "").equals(pred_bloc["y_pred"] == "")  # mêmes cases vides
    keep = [c for c in runs_un.columns if c not in COST_COLUMNS]
    pd.testing.assert_frame_equal(runs_un[keep], runs_bloc[keep])


def test_fichiers_mlp_identiques(tmp_path, monkeypatch, counts, ctx_model):
    files = _both(tmp_path, monkeypatch, counts, ctx_model, "mlp", context=_context())
    _assert_same_files(*files)
    runs = files[1].set_index("case_id")
    statuses = set(runs["status"])
    assert {"ok", "fallback", "error"} <= statuses  # servis, repliés, compteur inconnu
    assert "absent" in runs.loc[runs.index.str.startswith("T|Z-9"), "status_reason"].iloc[0]


def test_fichiers_mlp_seuil_remplace_identiques(tmp_path, monkeypatch, counts, model):
    files = _both(tmp_path, monkeypatch, counts, model, "mlp", min_observed_hours=24)
    _assert_same_files(*files)


@pytest.mark.parametrize("use_context", [False, True])
def test_fichiers_hgb_identiques(tmp_path, monkeypatch, counts, use_context):
    context = _context() if use_context else None
    files = _both(tmp_path, monkeypatch, counts, _hgb(counts, use_context), "hgb", context)
    _assert_same_files(*files)


def test_reference_passe_par_le_cas_par_cas(tmp_path, counts):
    cases = _cases_frame()
    args = (cases, _loader(counts), "reference", "EXP-test", "ref")
    single = P.run_experiment(*args, root=tmp_path / "un", publication_lag_hours=LAG)
    bloc = B.run_experiment_batch(*args, root=tmp_path / "bloc", publication_lag_hours=LAG)
    a, b = (pd.read_csv(p, dtype=str, keep_default_na=False) for p in (single[0], bloc[0]))
    pd.testing.assert_frame_equal(a, b)


def test_commande_batch(tmp_path, monkeypatch, counts, model):
    import dataclasses

    model = dataclasses.replace(model, donor_site_groups=["G"])
    monkeypatch.setattr(P, "_load_model", lambda v, run_id: model)
    monkeypatch.setattr(
        P, "counts_history_loader", lambda snapshot, values="measured": _loader(counts)
    )
    monkeypatch.setattr(P, "train_site_counters", lambda snapshot: {"A-1", "A-2", "A-3", "A-4"})
    monkeypatch.setattr(P, "load_context", lambda snapshot, path=None: None)
    monkeypatch.setattr(P, "default_publication_lag", lambda: LAG)
    monkeypatch.setattr(P, "data_path", lambda key: tmp_path)
    cases = _cases_frame()
    cases.to_csv(tmp_path / "cases.csv", index=False)
    argv = ["--cases", str(tmp_path / "cases.csv"), "--snapshot", "synthetic"]
    argv += ["--experiment", "EXP-test", "--variant", "mlp", "--batch"]
    assert P.main(argv) == 0
    selection = (tmp_path / "EXP-test").glob("*.selection.json")
    import json

    report = json.loads(next(selection).read_text(encoding="utf-8"))
    assert report["mode"] == "batch"


def test_historique_passe_une_seule_fois_par_compteur(tmp_path, monkeypatch, counts, model):
    """Garde-fou mémoire : l'historique d'un compteur n'est pas recopié pour chaque cas."""
    import dataclasses

    seen = {}
    original = B.RAW_BATCH["mlp"]

    def spy(cases, counts_arg, *args, **kwargs):
        seen["rows"] = len(counts_arg)
        seen["duplicates"] = int(counts_arg.duplicated(["counter_id", "timestamp"]).sum())
        return original(cases, counts_arg, *args, **kwargs)

    model = dataclasses.replace(model, donor_site_groups=["G"])
    monkeypatch.setattr(P, "_load_model", lambda v, run_id: model)
    monkeypatch.setitem(B.RAW_BATCH, "mlp", spy)
    B.run_experiment_batch(
        _cases_frame(),
        _loader(counts),
        "mlp",
        "EXP-test",
        "run",
        root=tmp_path,
        publication_lag_hours=LAG,
    )
    assert seen["duplicates"] == 0
    assert seen["rows"] <= len(counts)  # au plus une copie de chaque compteur


# --- EXP-E2-05 : dégradation de la semaine visible -------------------------------------


def test_positions_effacees_par_niveau():
    case = _case("A-1", _paris("2026-07-09"))
    assert B.erased_positions(case, "d0").size == 0
    np.testing.assert_array_equal(B.erased_positions(case, "panne-48"), np.arange(120, 168))
    assert B.erased_positions(case, "panne-144").min() == 24  # il reste les 24 plus anciennes
    holes = B.erased_positions(case, "trous-50")
    assert holes.size == 84 and np.unique(holes).size == 84
    np.testing.assert_array_equal(holes, B.erased_positions(case, "trous-50"))  # même graine
    other = B.erased_positions(_case("A-2", _paris("2026-07-09")), "trous-50")
    assert not np.array_equal(holes, other)  # chaque cas a ses propres trous
    with pytest.raises(ValueError, match="inconnu"):
        B.erased_positions(case, "panne-12")


def test_semaine_visible_finit_a_origine_moins_latence():
    case = _case("A-1", _paris("2026-07-09"))
    week = B.visible_week(case, LAG)
    assert len(week) == 168
    assert week[-1] == case.origin - pd.Timedelta(hours=LAG + 1)  # dernière heure publiée
    assert week[0] == case.origin - pd.Timedelta(hours=LAG + 168)


@pytest.mark.parametrize("level", ["panne-48", "panne-144", "trous-50"])
def test_degrade_history_vide_sans_zero_et_garde_les_cibles(counts, level):
    case = _case("A-1", _paris("2026-07-09"))
    history = counts.loc[counts["counter_id"] == "A-1"].reset_index(drop=True)
    before = history.copy()
    out = B.degrade_history(history, case, level, LAG)
    pd.testing.assert_frame_equal(history, before)  # l'original ne change pas
    hit = out["timestamp"].isin(B.erased_hours(case, level, LAG))
    assert hit.sum() == {"panne-48": 48, "panne-144": 144, "trous-50": 84}[level]
    assert out.loc[hit, ["count", "count_raw"]].isna().all().all()
    assert not out.loc[hit, "is_observed"].any()
    assert (out["count"] == 0).sum() == (history["count"] == 0).sum()  # aucun 0 inventé
    pd.testing.assert_frame_equal(out[~hit], history[~hit])  # cibles et reste intacts
    targets = out["timestamp"] >= case.origin
    assert not (hit & targets).any()


def test_bloc_d0_egal_sans_degradation(counts, model):
    cases = _cases()
    plain = B.batch_raw_mlp(cases, counts, None, model, publication_lag_hours=LAG)
    d0 = B.batch_raw_mlp(cases, counts, None, model, publication_lag_hours=LAG, degrade="d0")
    assert plain[1] == d0[1]
    np.testing.assert_allclose(d0[0], plain[0], rtol=0, atol=1e-6, equal_nan=True)


@pytest.mark.parametrize("threshold", [None, 24])
@pytest.mark.parametrize("level", ["panne-96", "trous-50"])
def test_bloc_degrade_egal_cas_par_cas_sur_historique_efface(counts, model, level, threshold):
    """La fenêtre effacée en bloc = predict_mlp sur l'historique effacé, cas par cas."""
    cases = [c for c in _cases() if c.counter_id != "A-4"][:20]
    kw = {} if threshold is None else {"min_observed_hours": threshold}
    bloc = B.batch_raw_mlp(
        cases, counts, None, model, publication_lag_hours=LAG, degrade=level, **kw
    )
    values, reasons = [], []
    for case in cases:
        history = counts.loc[counts["counter_id"] == case.counter_id]
        history = B.degrade_history(history, case, level, LAG)
        inputs = P.build_inputs(case, history, None, publication_lag_hours=LAG)
        out = N.predict_mlp(model.estimator, inputs, fit_cutoff=model.config.fit_cutoff, **kw)
        values.append(out.values if out.ok else np.full(24, np.nan))
        reasons.append(out.reason)
    _check_same(bloc, (np.array(values), reasons))
    if level == "panne-96" and threshold is None:  # 72 h restantes < 84 : refus
        assert all(r is not None for r in bloc[1])
    if threshold == 24:
        assert any(r is None for r in bloc[1])  # servis avec le seuil abaissé


def test_fichiers_degrades_repli_et_reference_sur_la_meme_semaine(
    tmp_path, monkeypatch, counts, model
):
    import dataclasses

    model = dataclasses.replace(model, donor_site_groups=["G"])
    monkeypatch.setattr(P, "_load_model", lambda v, run_id: model)
    cases = _cases_frame()
    loader = _loader(counts)
    pred_mlp, _ = B.run_experiment_batch(
        cases,
        loader,
        "mlp",
        "EXP",
        "mlp-p96",
        root=tmp_path / "m",
        publication_lag_hours=LAG,
        degrade="panne-96",
    )
    pred_ref, _ = B.run_experiment_batch(
        cases,
        loader,
        "reference",
        "EXP",
        "ref-p96",
        root=tmp_path / "r",
        publication_lag_hours=LAG,
        degrade="panne-96",
    )
    mlp = pd.read_csv(pred_mlp, keep_default_na=False)
    ref = pd.read_csv(pred_ref, keep_default_na=False)
    # seuil 84 : le MLP refuse tout, son repli = la référence sur la même semaine effacée
    served = mlp[mlp["prediction_status"] == "fallback"]
    assert len(served) > 0
    merged = served.merge(ref, on=["case_id", "horizon"], suffixes=("_m", "_r"))
    np.testing.assert_allclose(
        pd.to_numeric(merged["y_pred_m"]), pd.to_numeric(merged["y_pred_r"]), atol=1e-9
    )
    # la référence effacée diffère de la référence normale sur au moins un cas
    normal, _ = P.run_experiment(
        cases, loader, "reference", "EXP", "ref", root=tmp_path / "n", publication_lag_hours=LAG
    )
    plain = pd.read_csv(normal, keep_default_na=False)
    assert not plain["y_pred"].equals(ref["y_pred"])


def test_degradation_refusee_pour_hgb_et_niveau_inconnu(tmp_path, counts):
    cases = _cases_frame()
    with pytest.raises(ValueError, match="hgb"):
        B.run_experiment_batch(
            cases, _loader(counts), "hgb", "EXP", "h", root=tmp_path, degrade="panne-48"
        )
    with pytest.raises(ValueError, match="inconnu"):
        B.run_experiment_batch(
            cases, _loader(counts), "reference", "EXP", "r", root=tmp_path, degrade="panne-12"
        )


def test_commande_degrade(tmp_path, monkeypatch, counts):
    import json

    monkeypatch.setattr(
        P, "counts_history_loader", lambda snapshot, values="measured": _loader(counts)
    )
    monkeypatch.setattr(P, "train_site_counters", lambda snapshot: {"A-1", "A-2", "A-3", "A-4"})
    monkeypatch.setattr(P, "default_publication_lag", lambda: LAG)
    monkeypatch.setattr(P, "data_path", lambda key: tmp_path)
    _cases_frame().to_csv(tmp_path / "cases.csv", index=False)
    argv = ["--cases", str(tmp_path / "cases.csv"), "--snapshot", "synthetic"]
    argv += ["--experiment", "EXP-5/panne-48", "--variant", "reference", "--degrade", "panne-48"]
    with pytest.raises(SystemExit):  # sans --batch : refusé
        P.main(argv)
    assert P.main([*argv, "--batch"]) == 0
    out = tmp_path / "EXP-5" / "panne-48"
    report = json.loads((out / "e2-reference-measured_panne-48.selection.json").read_text())
    assert report["degrade"] == "panne-48"
    assert (out / "e2-reference-measured_panne-48.pred.csv").exists()

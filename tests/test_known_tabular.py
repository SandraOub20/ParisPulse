"""Apprentissage (fit_hgb) et prévision (predict_hgb) du HGB sites connus - MOD-009.

Données synthétiques : elles vérifient le code, pas une performance sur Paris.
Même construction que tests/test_known_neural_fit.py (sans dépendre de torch) : trois
compteurs (20, 100 et 300 vélos/h en moyenne) suivent un profil hebdomadaire fixe, de
sorte que la référence « même heure la semaine précédente » est parfaite.

Période : du 06/04 au 20/07/2026 (aucun changement d'heure), coupure fit_cutoff au
01/07/2026 minuit à Paris. Latence de publication : 24 h.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src.models.known import features as F
from src.models.known import predict as P
from src.models.known import tabular as T
from src.models.known import train
from src.models.schemas import Case, ForecastInputs

PARIS = "Europe/Paris"
LAG = 24
CUTOFF = pd.Timestamp("2026-07-01 00:00", tz=PARIS).tz_convert("UTC")  # 30/06 22:00Z
START = pd.Timestamp("2026-04-06 00:00", tz=PARIS).tz_convert("UTC")
END = pd.Timestamp("2026-07-20 00:00", tz=PARIS).tz_convert("UTC")
LEVELS = {"A-1": 100.0, "A-2": 20.0, "A-3": 300.0}
FAST = {"max_iter": 60, "min_samples_leaf": 5, "patience": 60}
INVENTORY = pd.DataFrame(
    {
        "counter_id": ["A-1", "A-2", "A-3", "R-1"],
        "site_group_id": ["G-1", "G-2", "G-3", "G-R"],
        "site_role": ["S_train", "S_train", "S_train", "S_test_new"],
        "selection_status": ["retained", "retained", "robustness", "reserved_test_new"],
        "period_role": ["selection"] * 4,
    }
)


def _profile(stamps: pd.DatetimeIndex) -> np.ndarray:
    local = stamps.tz_convert(PARIS)
    hour = local.hour.to_numpy(dtype=float)
    weekday = local.dayofweek.to_numpy() < 5
    commute = np.exp(-(((hour - 8) / 1.5) ** 2)) + np.exp(-(((hour - 18) / 1.8) ** 2))
    leisure = np.exp(-(((hour - 15) / 3.0) ** 2))
    return np.where(weekday, 0.15 + 1.6 * commute, 0.15 + 0.9 * leisure)


def _counts(levels: dict[str, float] = LEVELS) -> pd.DataFrame:
    hours = pd.date_range(START, END, freq="h", inclusive="left")
    frames = []
    for counter_id, level in levels.items():
        value = np.round(level * _profile(hours), 1)
        frames.append(
            pd.DataFrame(
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
        )
    return pd.concat(frames, ignore_index=True)


def _context() -> pd.DataFrame:
    """Contexte complet au format context.csv, tout connu à minuit pour la journée prévue."""
    days = pd.date_range("2026-04-01", "2026-07-25", freq="D")
    midnights = days.tz_localize(PARIS).tz_convert("UTC")
    daily = []
    for variable in ("is_holiday", "is_school_holiday", "is_strike"):
        value = np.where((variable == "is_holiday") & (days == "2026-05-14"), "true", "false")
        available = (midnights - pd.Timedelta(hours=24)).map(lambda t: t.isoformat())
        daily.append(
            pd.DataFrame(
                {
                    "variable": variable,
                    "local_date": days.strftime("%Y-%m-%d"),
                    "valid_time": None,
                    "value": value,
                    "available_at": available if variable == "is_strike" else None,
                    "role": "known_calendar",
                }
            )
        )
    valid = pd.date_range(START, END + pd.Timedelta(days=3), freq="h")
    weather = {
        "temp_prev": 15 + 5 * np.sin(2 * np.pi * valid.hour.to_numpy() / 24),
        "rain_prev": np.zeros(len(valid)),
        "wind_prev": np.full(len(valid), 3.0),
    }
    hourly = [
        pd.DataFrame(
            {
                "variable": variable,
                "local_date": None,
                "valid_time": valid.map(lambda t: t.isoformat()),
                "value": values.astype(str),
                "available_at": (valid - pd.Timedelta(hours=42)).map(lambda t: t.isoformat()),
                "role": "forecast_bulletin",
            }
        )
        for variable, values in weather.items()
    ]
    return pd.concat(daily + hourly, ignore_index=True)


def _config(use_context: bool = False, seed: int = 0, **hp) -> train.TrainConfig:
    return train.TrainConfig(
        method="hgb",
        fit_cutoff=CUTOFF,
        use_context=use_context,
        hyperparameters=T.hgb_hyperparameters(**{**FAST, **hp}),
        seed=seed,
        feature_version=F.FEATURE_VERSION,
    )


def _origins(counts: pd.DataFrame) -> pd.DataFrame:
    return F.training_origins(counts, sorted(LEVELS), CUTOFF, publication_lag_hours=LAG)


def _fit(counts: pd.DataFrame, context=None, **kwargs) -> T.HGBModel:
    return T.fit_hgb(_config(**kwargs), counts, context, _origins(counts))


def _paris(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz=PARIS).tz_convert("UTC")


def _inputs(
    counts: pd.DataFrame, origin: str, counter: str = "A-1", context=None, lag: int = LAG
) -> ForecastInputs:
    case = Case(
        case_id=f"T|{counter}|{origin}",
        counter_id=counter,
        site_group_id=None,
        origin=_paris(origin),
        scenario="known_site",
        protocol_id="test",
        snapshot_id="synthetic",
    )
    history = counts.loc[counts["counter_id"] == counter]
    return P.build_inputs(case, history, context, publication_lag_hours=lag)


@pytest.fixture(scope="module")
def counts() -> pd.DataFrame:
    return _counts()


@pytest.fixture(scope="module")
def model(counts) -> T.HGBModel:
    return _fit(counts)


# --------------------------------------------------------------------------- déclaration


def test_hgb_declare_dans_le_registre():
    """Importer tabular déclare la méthode « hgb » avec model.joblib."""
    backend = train.get_backend("hgb")
    assert backend.weights_file == T.WEIGHTS_FILE
    assert backend.fit is T.fit_hgb


def test_codes_de_refus_distincts_et_prefixes():
    """Codes stables, préfixés hgb_ et distincts de ceux du MLP."""
    codes = [
        T.REFUSE_NOT_MIDNIGHT,
        T.REFUSE_BEFORE_CUTOFF,
        T.REFUSE_NO_HISTORY,
        T.REFUSE_CONTEXT,
        T.REFUSE_NON_FINITE,
    ]
    assert len(set(codes)) == len(codes)
    assert all(code.startswith("hgb_") for code in codes)


# --------------------------------------------------------------------------- réglages


def test_reglages_complets_et_cle_inconnue_refusee():
    """hgb_hyperparameters() rend toutes les clés ; une faute de frappe lève ValueError."""
    hp = T.hgb_hyperparameters(learning_rate=1)
    assert list(hp) == list(T.DEFAULT_HYPERPARAMETERS)
    assert hp["learning_rate"] == 1.0 and isinstance(hp["learning_rate"], float)
    with pytest.raises(ValueError, match="inconnus"):
        T.hgb_hyperparameters(max_iters=10)


@pytest.mark.parametrize(
    "overrides",
    [
        {"loss": "huber"},
        {"max_iter": 0},
        {"learning_rate": 0},
        {"max_bins": 256},
        {"max_leaf_nodes": True},
        {"l2_regularization": -1.0},
        {"categorical": 1},
        {"context_groups": "calendar"},
        {"context_groups": ["meteo"]},
        {"context_groups": []},
    ],
)
def test_reglages_hors_domaine_refuses(overrides):
    """Valeurs hors domaine ou de mauvais type : ValueError."""
    with pytest.raises(ValueError):
        T.hgb_hyperparameters(**overrides)


def test_groupes_de_contexte_ordonnes_et_contradiction_refusee():
    """context_groups est rangé dans l'ordre de CONTEXT_GROUPS ; avec use_context=False, refusé."""
    hp = T.hgb_hyperparameters(context_groups=["weather_forecast", "calendar"])
    assert hp["context_groups"] == ["calendar", "weather_forecast"]
    with pytest.raises(ValueError, match="contradictoire"):
        T.resolve_groups(_config(use_context=False), hp)
    assert T.resolve_groups(_config(use_context=True), hp) == ("calendar", "weather_forecast")
    assert T.resolve_groups(_config(use_context=False), T.hgb_hyperparameters()) == ()


# --------------------------------------------------------------------------- apprentissage


def test_origine_dont_les_cibles_sont_publiees_apres_la_coupure_refusee(counts):
    """Une origine avec origine + 24 h + latence > fit_cutoff lève ValueError (fuite)."""
    origins = _origins(counts)
    late = pd.DataFrame({"counter_id": ["A-1"], "origin": [_paris("2026-06-30 00:00")]})
    with pytest.raises(ValueError, match="fuite"):
        T.fit_hgb(_config(), counts, None, pd.concat([origins, late], ignore_index=True))


def test_origine_hors_minuit_ou_en_double_refusee(counts):
    """Origines d'apprentissage : minuit à Paris, une seule fois par compteur."""
    origins = _origins(counts)
    shifted = origins.assign(origin=origins["origin"] - pd.Timedelta(hours=1))
    with pytest.raises(ValueError, match="minuit"):
        T.fit_hgb(_config(), counts, None, shifted)
    doubled = pd.concat([origins, origins.iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="double"):
        T.fit_hgb(_config(), counts, None, doubled)


def test_contexte_demande_mais_absent_refuse(counts):
    with pytest.raises(ValueError, match="sans contexte"):
        _fit(counts, None, use_context=True)


def test_modifier_le_futur_ne_change_pas_le_modele(counts, model):
    """Changer les comptages après fit_cutoff donne des prévisions identiques."""
    future = counts.copy()
    late = future["timestamp"] >= CUTOFF
    future.loc[late, ["count", "count_raw"]] = 5_000.0
    other = _fit(future)
    inputs = _inputs(counts, "2026-07-08 00:00")
    assert np.array_equal(T.predict_hgb(model, inputs).values, T.predict_hgb(other, inputs).values)


def test_meme_graine_meme_modele(counts, model):
    """Deux apprentissages avec la même graine donnent les mêmes prévisions."""
    again = _fit(counts)
    inputs = _inputs(counts, "2026-07-09 00:00", counter="A-3")
    assert np.array_equal(T.predict_hgb(model, inputs).values, T.predict_hgb(again, inputs).values)
    assert again.training_report["n_trees"] == model.training_report["n_trees"]


def test_holdout_temporel_journees_entieres(counts):
    """Les 24 heures d'une origine sont du même côté ; le holdout couvre 4 semaines avant la coupure."""
    X, _ = F.build_training_frame(counts, _origins(counts), None, CUTOFF, False)
    train_mask, hold_mask = T._split_holdout(X, CUTOFF, 4)
    assert not (train_mask & hold_mask).any() and (train_mask | hold_mask).all()
    side = pd.Series(hold_mask).groupby([X["counter_id"].astype(str), X["origin"]]).nunique()
    assert (side == 1).all()
    start = T._holdout_start(CUTOFF, 4)
    assert start == _paris("2026-06-03 00:00")
    assert X.loc[hold_mask, "origin"].min() == start
    assert X.loc[train_mask, "origin"].max() < start
    assert X.loc[hold_mask, "origin"].max() + pd.Timedelta(hours=24 + LAG) <= CUTOFF
    with pytest.raises(ValueError, match="arrêt anticipé"):
        T._split_holdout(X.loc[train_mask], CUTOFF, 4)


def test_sans_holdout_tous_les_arbres(counts):
    fitted = _fit(counts, holdout_weeks=0, max_iter=15)
    assert fitted.training_report["n_trees"] == 15
    assert fitted.training_report["holdout_metrics"] is None


def test_latence_differente_de_la_configuration_refusee(counts):
    """train.fit(..., publication_lag_hours=48) lève ValueError (D-22)."""
    with pytest.raises(ValueError, match="latence"):
        train.fit(_config(), counts, None, INVENTORY, publication_lag_hours=48)


def test_bilan_complet_et_serialisable(model):
    """training_report passe json.dumps et contient effectifs, arbres, holdout_metrics."""
    report = model.training_report
    json.dumps(report)
    assert report["examples"]["train"]["counters"] == 3
    assert report["examples"]["holdout"]["rows"] > 0
    assert 1 <= report["n_trees"] <= FAST["max_iter"]
    metrics = report["holdout_metrics"]
    assert metrics["cells"] > 0
    # Le profil est parfaitement hebdomadaire : lag_168h est exact sur le holdout.
    assert metrics["mae_lag_168h"] == 0.0
    assert metrics["mae_hgb"] < 0.2 * np.mean(list(LEVELS.values()))


# --------------------------------------------------------------------------- prévision


def test_refus_attendus(counts, model):
    """Hors minuit, avant fit_cutoff, sans historique."""
    assert T.predict_hgb(model, _inputs(counts, "2026-07-08 01:00")).reason == (
        T.REFUSE_NOT_MIDNIGHT
    )
    assert T.predict_hgb(model, _inputs(counts, "2026-06-20 00:00")).reason == (
        T.REFUSE_BEFORE_CUTOFF
    )
    empty = counts.assign(count=np.nan)
    assert T.predict_hgb(model, _inputs(empty, "2026-07-08 00:00")).reason == (T.REFUSE_NO_HISTORY)


def test_modele_avec_contexte_refuse_sans_contexte(counts):
    context = _context()
    with_ctx = _fit(counts, context, use_context=True, max_iter=20)
    assert with_ctx.use_context
    ok = T.predict_hgb(with_ctx, _inputs(counts, "2026-07-08 00:00", context=context))
    assert ok.ok
    refused = T.predict_hgb(with_ctx, _inputs(counts, "2026-07-08 00:00"))
    assert refused.reason == T.REFUSE_CONTEXT


def test_fenetre_clairsemee_prevue_et_non_refusee(counts, model):
    """Le HGB prévoit malgré des NaN dans l'historique (différence avec le MLP)."""
    sparse = counts.copy()
    hole = sparse["timestamp"] >= _paris("2026-06-24 00:00")
    sparse.loc[hole, "count"] = np.nan
    forecast = T.predict_hgb(model, _inputs(sparse, "2026-07-08 00:00"))
    assert forecast.ok and np.isfinite(forecast.values).all()


def test_latence_du_cas_differente_leve_valueerror(counts, model):
    """Une latence du cas différente de celle de l'apprentissage est une erreur de config."""
    with pytest.raises(ValueError, match="latence"):
        T.predict_hgb(model, _inputs(counts, "2026-07-08 00:00", lag=48))


def test_calcul_en_bloc_egal_au_cas_par_cas(counts, model):
    """predict_frame(build_training_frame) == predict_hgb cas par cas, mêmes cellules."""
    days = ["2026-07-06 00:00", "2026-07-08 00:00", "2026-07-11 00:00"]
    origins = pd.DataFrame(
        [(c, _paris(d)) for c in sorted(LEVELS) for d in days], columns=["counter_id", "origin"]
    )
    X, _ = F.build_training_frame(counts, origins, None, END + pd.Timedelta(days=3), False)
    bloc = T.predict_frame(model, X)
    for counter in sorted(LEVELS):
        for day in days:
            rows = (X["counter_id"].astype(str) == counter) & (X["origin"] == _paris(day))
            single = T.predict_hgb(model, _inputs(counts, day, counter=counter)).values
            np.testing.assert_allclose(bloc[rows.to_numpy()], single, rtol=0, atol=1e-9)


def test_sorties_positives_et_24_horizons(counts, model):
    """24 valeurs finies >= 0, dans l'ordre des horizons."""
    for counter in LEVELS:
        forecast = T.predict_hgb(model, _inputs(counts, "2026-07-12 00:00", counter=counter))
        assert forecast.ok and forecast.values.shape == (24,)
        assert (forecast.values >= 0).all()


def test_predict_frame_refuse_une_autre_version_de_variables(counts, model):
    X = F.build_feature_frame(_inputs(counts, "2026-07-08 00:00"), False)
    with pytest.raises(ValueError, match="réentraîner"):
        T.predict_frame(model, X.assign(feature_version="f0.9"))


# --------------------------------------------------------------------------- sauvegarde


def test_aller_retour_sauvegarde_identique(counts, tmp_path):
    """train.fit, save_model puis load_model : mêmes prévisions, metadata complet."""
    trained = train.fit(_config(max_iter=20), counts, None, INVENTORY)
    folder = train.save_model(trained, tmp_path)
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert meta["model_name"] == "hgb" and meta["weights_path"] == T.WEIGHTS_FILE
    assert meta["excluded_site_groups"] == ["G-R"]
    assert meta["feature_version"] == F.FEATURE_VERSION
    loaded = train.load_model(trained.model_run_id, tmp_path)
    inputs = _inputs(counts, "2026-07-08 00:00")
    assert np.array_equal(
        T.predict_hgb(trained.estimator, inputs).values,
        T.predict_hgb(loaded.estimator, inputs).values,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"feature_version": "f0.9"},
        {"file_format": 99},
        {"feature_columns": ["horizon"]},
        {"publication_lag_hours": 48},
    ],
)
def test_modele_incompatible_refuse(model, tmp_path, change):
    """Autre format, autre version de variables, autres colonnes ou autre latence : refus."""
    altered = T.HGBModel(**{**model.__dict__, **change})
    path = tmp_path / T.WEIGHTS_FILE
    T.save_hgb(altered, path)
    with pytest.raises(ValueError):
        T.load_hgb(path)


@pytest.mark.parametrize("content", [{"pas": "un modèle"}, ["liste"]])
def test_objet_qui_n_est_pas_un_modele_refuse(tmp_path, content):
    path = tmp_path / T.WEIGHTS_FILE
    joblib.dump(content, path)
    with pytest.raises(ValueError, match="HGBModel"):
        T.load_hgb(path)


def test_fichier_sans_classe_du_module(model, tmp_path):
    """model.joblib ne contient aucune classe de tabular.py : il reste lisible même s'il a
    été écrit par « python -m src.models.known.tabular » (module nommé __main__)."""
    path = tmp_path / T.WEIGHTS_FILE
    T.save_hgb(model, path)
    saved = joblib.load(path)
    assert isinstance(saved, dict) and set(saved) == set(T.SAVED_FIELDS)
    assert type(saved["estimator"]).__module__.startswith("sklearn.")
    reloaded = T.load_hgb(path)
    assert reloaded.fit_cutoff == model.fit_cutoff
    assert reloaded.context_groups == model.context_groups

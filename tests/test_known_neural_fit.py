"""Apprentissage (fit_mlp) et prévision (predict_mlp) du MLP sites connus - MOD-008.

Données synthétiques : elles vérifient le code, pas une performance sur Paris.
Trois compteurs (20, 100 et 300 vélos/h en moyenne) suivent un profil hebdomadaire fixe :
deux pointes les jours ouvrés, une bosse l'après-midi le week-end. D'une semaine à
l'autre, la même heure du même jour a exactement la même valeur, si bien que la
référence « même heure la semaine précédente » est parfaite : elle sert de témoin.

Période : du 06/04 au 20/07/2026 (aucun changement d'heure), coupure fit_cutoff au
01/07/2026 minuit à Paris, comme le protocole proposé. Latence de publication : 24 h.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.known import features as F
from src.models.known import neural as N
from src.models.known import predict as P
from src.models.known import train
from src.models.schemas import Case, ForecastInputs

PARIS = "Europe/Paris"
LAG = 24
CUTOFF = pd.Timestamp("2026-07-01 00:00", tz=PARIS).tz_convert("UTC")  # 30/06 22:00Z
START = pd.Timestamp("2026-04-06 00:00", tz=PARIS).tz_convert("UTC")
END = pd.Timestamp("2026-07-20 00:00", tz=PARIS).tz_convert("UTC")
LEVELS = {"A-1": 100.0, "A-2": 20.0, "A-3": 300.0}
# Petit réseau, assez d'époques pour apprendre le profil ; patience = plafond : pas d'arrêt.
FAST = {
    "hidden": 32,
    "layers": 2,
    "dropout": 0.1,
    "lr": 3e-3,
    "batch_size": 32,
    "max_epochs": 60,
    "patience": 60,
}
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
    """Contexte complet au format context.csv : calendrier et grèves par jour, météo prévue.

    Grève connue 24 h avant le jour, bulletin météo publié 42 h avant l'heure prévue
    (comme les règles d'E1) : tout est connu à minuit pour les 24 heures à prévoir.
    """
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
        method="mlp",
        fit_cutoff=CUTOFF,
        use_context=use_context,
        hyperparameters=N.mlp_hyperparameters(**{**FAST, **hp}),
        seed=seed,
    )


def _origins(counts: pd.DataFrame) -> pd.DataFrame:
    return F.training_origins(counts, sorted(LEVELS), CUTOFF, publication_lag_hours=LAG)


def _fit(counts: pd.DataFrame, context=None, **kwargs) -> N.MLPNet:
    return N.fit_mlp(_config(**kwargs), counts, context, _origins(counts))


def _same_weights(a: N.MLPNet, b: N.MLPNet) -> bool:
    left, right = a.state_dict(), b.state_dict()
    return left.keys() == right.keys() and all(torch.equal(left[k], right[k]) for k in left)


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
def model(counts) -> train.TrainedModel:
    """MLP sans contexte, appris par le socle commun train.fit (chemin réel de l'équipe)."""
    return train.fit(_config(), counts, None, INVENTORY, publication_lag_hours=LAG)


@pytest.fixture(scope="module")
def ctx_model(counts) -> train.TrainedModel:
    return train.fit(_config(use_context=True), counts, _context(), INVENTORY)


# --- Réglages --------------------------------------------------------------------------------


def test_reglages_par_defaut_complets_et_traces():
    hp = N.mlp_hyperparameters()
    assert hp == N.DEFAULT_HYPERPARAMETERS and list(hp) == list(N.DEFAULT_HYPERPARAMETERS)
    changed = N.mlp_hyperparameters(hidden=64, lr=1)
    assert changed["hidden"] == 64 and changed["lr"] == 1.0 and isinstance(changed["lr"], float)
    assert changed["patience"] == N.DEFAULT_HYPERPARAMETERS["patience"]  # le reste est écrit


@pytest.mark.parametrize(
    "bad",
    [
        {"hiden": 64},  # faute de frappe : jamais ignorée en silence
        {"hidden": 0},
        {"hidden": True},
        {"layers": -1},
        {"dropout": 1.0},
        {"lr": 0},
        {"weight_decay": -0.1},
        {"batch_size": 0},
        {"max_epochs": 1.5},
        {"holdout_weeks": -1},
        {"loss_weighting": "mse"},
    ],
)
def test_reglages_inconnus_ou_invalides_refuses(bad):
    with pytest.raises(ValueError):
        N.mlp_hyperparameters(**bad)


# --- Apprentissage -----------------------------------------------------------------------------


def test_apprend_le_profil_hebdomadaire(model):
    net = model.estimator
    holdout = net.training_report["holdout_metrics"]
    # témoin : prévoir le niveau de la semaine pour chaque heure (« prévision plate »)
    hold_start = pd.Timestamp(net.training_report["holdout_start"])
    origins = _origins(_counts())
    w = N.build_windows(_counts(), origins[origins["origin"] >= hold_start], use_context=False)
    flat = np.abs(w.scale[:, None] * (1 - w.target))[w.target_mask].mean()
    assert holdout["mlp"]["mae_macro"] < 0.1 * flat
    # la référence hebdomadaire est parfaite sur ce profil : son calcul est donc juste
    assert holdout["weekly_naive_on_compared"]["mae_macro"] < 0.01
    assert holdout["compared_cells"] == holdout["mlp"]["cells"] == 81 * 24


def test_bilan_effectifs_et_dates(model):
    report = model.estimator.training_report
    assert report["examples"] == {
        "total": 168,  # 56 jours (05/05 -> 29/06) x 3 compteurs
        "excluded_not_usable": 0,
        "excluded_context_missing": 0,
        "excluded_no_target": 0,
        "train": 87,  # 05/05 -> 02/06 : 29 jours x 3
        "holdout": 81,  # 03/06 -> 29/06 : 27 jours x 3
        "train_target_cells": 87 * 24,
        "holdout_target_cells": 81 * 24,
        "counters": 3,
    }
    assert report["holdout_start"] == _paris("2026-06-03 00:00").isoformat()
    assert report["origins"]["train"] == [
        _paris("2026-05-05 00:00").isoformat(),
        _paris("2026-06-02 00:00").isoformat(),
    ]
    assert report["origins"]["holdout"] == [
        _paris("2026-06-03 00:00").isoformat(),
        _paris("2026-06-29 00:00").isoformat(),  # dernière origine : cibles publiées au 01/07
    ]
    assert report["publication_lag_hours"] == LAG and report["use_context"] is False
    assert report["hyperparameters"] == model.config.hyperparameters
    assert report["epochs_run"] == FAST["max_epochs"] and not report["stopped_early"]
    assert report["n_parameters"] == sum(p.numel() for p in model.estimator.parameters())
    json.dumps(report)  # que des types simples : relisible en JSON et avec weights_only


def test_arret_anticipe_rend_la_meilleure_epoque(counts):
    net = _fit(counts, patience=2, max_epochs=60, lr=0.05)  # pas trop grand : progrès heurtés
    report = net.training_report
    best = report["best_epoch"]
    assert report["stopped_early"] and report["epochs_run"] == best + 2
    losses = [e["holdout_loss"] for e in report["history"]]
    assert losses[best - 1] == min(losses)
    # le réseau rendu est bien celui de la meilleure époque, pas celui de la dernière
    w = N.build_windows(counts, _origins(counts), use_context=False)
    rows = np.flatnonzero(np.asarray(w.origin >= pd.Timestamp(report["holdout_start"])))
    hold = N._tensors(w.X, w, w.scale, rows)
    assert N._objective(net, hold) == pytest.approx(losses[best - 1], rel=1e-6)


def test_limite_d_arret_anticipe_en_dates_locales():
    # la limite reste minuit à Paris même si un changement d'heure (25/10) est traversé
    cutoff = _paris("2026-11-10 00:00")
    assert N._holdout_start(cutoff, 4) == _paris("2026-10-13 00:00")
    assert N._holdout_start(cutoff, 0) is None


def test_meme_graine_memes_poids_sans_toucher_au_hasard_global(counts):
    state = torch.random.get_rng_state()
    a = _fit(counts, max_epochs=5)
    assert torch.equal(torch.random.get_rng_state(), state)  # graine locale à fit_mlp
    assert _same_weights(a, _fit(counts, max_epochs=5))
    assert not _same_weights(a, _fit(counts, max_epochs=5, seed=1))


def test_futur_non_publie_sans_effet_sur_l_apprentissage(counts):
    base = _fit(counts, max_epochs=5)
    # tout ce qui est publié après fit_cutoff : heure + 1 h + 24 h > 01/07 minuit
    late = counts.copy()
    unpublished = late["timestamp"] >= CUTOFF - pd.Timedelta(hours=LAG)
    late.loc[unpublished, ["count", "count_raw"]] = 99999.0
    assert _same_weights(base, _fit(late, max_epochs=5))
    # témoin : retirer une cible publiée change le réseau (le test sait voir un effet).
    # Gonfler la cible ne suffirait pas toujours : avec la L1, seul le signe de l'erreur
    # compte (voir test_perte_l1_masquee_ponderee_et_robuste).
    seen = counts.copy()
    target = (seen["counter_id"] == "A-1") & (seen["timestamp"] == _paris("2026-05-12 08:00"))
    seen.loc[target, "is_scoreable"] = False
    assert not _same_weights(base, _fit(seen, max_epochs=5))


def test_perte_l1_masquee_ponderee_et_robuste():
    pred = torch.tensor([[1.0, 2.0, 3.0], [1.0, 1.0, 1.0]], requires_grad=True)
    target = torch.tensor([[2.0, 2.5, 100.0], [0.5, 0.5, 0.5]])
    mask = torch.tensor([[1.0, 1.0, 0.0], [1.0, 0.0, 0.0]])  # 0 = cible non mesurée
    level = torch.tensor([10.0, 100.0])  # niveau de chaque fenêtre (vélos/h)
    total, weight = N._masked_l1(pred, target, mask, level)
    # erreurs en vélos/h : 10 x 1 + 10 x 0,5 + 100 x 0,5 ; la cellule masquée (97) ignorée
    assert total.item() == pytest.approx(65.0) and weight.item() == pytest.approx(120.0)
    total.backward()
    grad = pred.grad.clone()
    assert grad[0, 2] == 0 and grad[1, 1] == 0  # aucune influence des cibles masquées
    # robustesse : une cible gonflée du même côté de la prévision ne change pas le gradient
    pred.grad = None
    inflated = target.clone()
    inflated[0, 1] = 5000.0  # 2,5 -> 5000 : la prévision (2) reste en dessous
    N._masked_l1(pred, inflated, mask, level)[0].backward()
    assert torch.equal(pred.grad, grad)


def test_cibles_non_mesurees_et_fenetres_trop_vides_sans_effet(counts):
    data = counts.copy()
    # 1. heures non évaluables (valeurs remplies par E1) : jamais dans la perte
    filled = (data["counter_id"] == "A-3") & data["timestamp"].between(
        _paris("2026-05-20 00:00"), _paris("2026-05-21 00:00"), inclusive="left"
    )
    data.loc[filled, "is_scoreable"] = False
    # 2. dix jours sans mesure : les fenêtres qui les couvrent sont inutilisables
    gap = (data["counter_id"] == "A-2") & data["timestamp"].between(
        _paris("2026-05-15 00:00"), _paris("2026-05-25 00:00"), inclusive="left"
    )
    data.loc[gap, "count"] = np.nan
    windows = N.build_windows(data, _origins(data), use_context=False)
    unusable = windows.origin[~windows.usable]
    assert len(unusable) > 0 and set(windows.counter_id[~windows.usable]) == {"A-2"}
    base = _fit(data, max_epochs=5)
    assert base.training_report["examples"]["excluded_not_usable"] == len(unusable)

    changed = data.copy()
    changed.loc[filled, "count_raw"] = 1e6  # valeur non évaluable modifiée
    for origin in unusable:  # cibles des exemples inutilisables modifiées
        day = (changed["counter_id"] == "A-2") & changed["timestamp"].between(
            origin, origin + pd.Timedelta(hours=23)
        )
        changed.loc[day, "count_raw"] = 1e6
    assert _same_weights(base, _fit(changed, max_epochs=5))


def test_sites_reserves_jamais_appris(counts):
    reserved = _counts({"R-1": 50.0})
    with_r = pd.concat([counts, reserved], ignore_index=True)
    garbage = with_r.copy()
    garbage.loc[garbage["counter_id"] == "R-1", ["count", "count_raw"]] = 12345.0
    config = _config(max_epochs=5)
    a = train.fit(config, with_r, None, INVENTORY)
    b = train.fit(config, garbage, None, INVENTORY)
    assert _same_weights(a.estimator, b.estimator)
    assert a.excluded_site_groups == ["G-R"]


@pytest.mark.parametrize(
    "extra, message",
    [
        ("2026-06-30 00:00", "publiées"),  # cibles du 30/06 publiées le 02/07 > coupure
        ("2026-06-10 06:00", "minuit"),  # la sortie k ne serait plus la k-ième heure du jour
        ("2026-06-10 00:00", "double"),  # déjà présente : compterait deux fois
    ],
)
def test_origines_refusees_avant_toute_lecture(counts, extra, message):
    origins = _origins(counts)
    added = pd.DataFrame({"counter_id": ["A-1"], "origin": [_paris(extra)]})
    with pytest.raises(ValueError, match=message):
        N.fit_mlp(_config(), counts, None, pd.concat([origins, added], ignore_index=True))


def test_contexte_obligatoire_si_use_context(counts):
    with pytest.raises(ValueError, match="contexte"):
        N.fit_mlp(_config(use_context=True), counts, None, _origins(counts))


def test_arret_anticipe_obligatoire_ou_explicitement_retire(counts):
    early = _origins(counts)
    early = early.loc[early["origin"] < _paris("2026-06-01 00:00")]
    with pytest.raises(ValueError, match="arrêt anticipé"):
        N.fit_mlp(_config(), counts, None, early)
    net = N.fit_mlp(_config(holdout_weeks=0, max_epochs=4), counts, None, early)
    report = net.training_report
    assert report["holdout_metrics"] is None and report["holdout_start"] is None
    assert report["best_epoch"] == report["epochs_run"] == 4
    assert all(e["holdout_loss"] is None for e in report["history"])


def test_perte_relative_disponible(counts):
    net = _fit(counts, max_epochs=3, loss_weighting="none")
    assert net.training_report["hyperparameters"]["loss_weighting"] == "none"
    assert np.isfinite([e["train_loss"] for e in net.training_report["history"]]).all()


def test_contexte_appris_et_trou_de_contexte_exclu(counts, ctx_model):
    report = ctx_model.estimator.training_report
    assert report["use_context"] is True and report["examples"]["excluded_context_missing"] == 0
    assert ctx_model.estimator.arch["n_inputs"] == 419
    # un jour sans bulletin météo : ses 3 exemples (un par compteur) sont écartés, pas mis à 0
    context = _context()
    hole = (context["variable"] == "temp_prev") & pd.to_datetime(
        context["valid_time"], utc=True, format="ISO8601"
    ).between(_paris("2026-05-20 01:00"), _paris("2026-05-21 00:00"))
    net = _fit(counts, context.loc[~hole], use_context=True, max_epochs=2)
    assert net.training_report["examples"]["excluded_context_missing"] == 3


# --- Prévision ---------------------------------------------------------------------------------


def test_prevision_24_valeurs_positives_proches_de_la_verite(counts, model):
    inputs = _inputs(counts, "2026-07-06 00:00")  # lundi, après la coupure
    result = N.predict_mlp(model.estimator, inputs, fit_cutoff=model.config.fit_cutoff)
    assert result.ok and result.reason is None and result.observed_hours == 168
    assert result.values.shape == (24,) and (result.values >= 0).all()
    truth = counts.loc[
        (counts["counter_id"] == "A-1")
        & counts["timestamp"].between(
            inputs.case.origin, inputs.case.origin + pd.Timedelta(hours=23)
        ),
        "count_raw",
    ].to_numpy()
    assert np.abs(result.values - truth).mean() < 0.1 * truth.mean()


def test_prevision_cas_par_cas_egale_au_calcul_en_bloc(counts, model):
    stamps = [f"2026-07-{d:02d} 00:00" for d in range(6, 13)]
    origins = pd.DataFrame(
        [(c, _paris(s)) for c in sorted(LEVELS) for s in stamps], columns=["counter_id", "origin"]
    )
    bloc = N.predict_windows(model.estimator, N.build_windows(counts, origins, use_context=False))
    for i, (counter, stamp) in enumerate((c, s) for c in sorted(LEVELS) for s in stamps):
        one = N.predict_mlp(model.estimator, _inputs(counts, stamp, counter))
        np.testing.assert_allclose(one.values, bloc[i], rtol=1e-5, atol=1e-4)


def test_prevision_ignore_les_lignes_futures(counts, model):
    clean = _inputs(counts, "2026-07-08 00:00")
    history = counts.loc[counts["counter_id"] == "A-1"].copy()
    history.loc[history["timestamp"] >= clean.information_cutoff, ["count", "count_raw"]] = 9e5
    dirty = ForecastInputs(clean.case, history, clean.information_cutoff)  # non filtré
    a, b = N.predict_mlp(model.estimator, clean), N.predict_mlp(model.estimator, dirty)
    np.testing.assert_array_equal(a.values, b.values)


def _sparse(counts: pd.DataFrame) -> pd.DataFrame:
    data = counts.copy()
    gap = data["timestamp"].between(
        _paris("2026-06-28 00:00"), _paris("2026-07-03 00:00"), inclusive="left"
    )
    data.loc[gap, "count"] = np.nan  # 120 h manquantes sur les 168 visibles le 06/07
    return data


@pytest.mark.parametrize(
    "case, expected",
    [
        ("trou", N.REFUSE_SPARSE),
        ("niveau", N.REFUSE_LOW_LEVEL),
        ("avant_coupure", N.REFUSE_BEFORE_CUTOFF),
        ("hors_minuit", N.REFUSE_NOT_MIDNIGHT),
        ("sans_historique", N.REFUSE_NO_HISTORY),
    ],
)
def test_prevision_refus_motives(counts, model, case, expected):
    if case == "trou":
        inputs = _inputs(_sparse(counts), "2026-07-06 00:00")
    elif case == "niveau":
        inputs = _inputs(_counts({"BAS": 0.5}), "2026-07-06 00:00", counter="BAS")
    elif case == "avant_coupure":
        inputs = _inputs(counts, "2026-06-20 00:00")  # le modèle a appris sur cette journée
    elif case == "hors_minuit":
        inputs = _inputs(counts, "2026-07-06 06:00")
    else:
        inputs = _inputs(counts.iloc[:0], "2026-07-06 00:00")
    result = N.predict_mlp(model.estimator, inputs, fit_cutoff=model.config.fit_cutoff)
    assert not result.ok and result.values is None and result.reason == expected


def test_motifs_de_refus_identiques_en_bloc_et_cas_par_cas(counts, model):
    # un compteur normal et un compteur à 0,5 vélo/h, tous deux sans mesure du 28/06 au 03/07 ;
    # le 06/07, « BAS » est à la fois trop vide et trop bas : le trou l'emporte
    data = _sparse(pd.concat([counts, _counts({"BAS": 0.5})], ignore_index=True))
    stamps = ["2026-07-06 00:00", "2026-07-13 00:00"]  # le 13/07, le trou est sorti de la fenêtre
    pairs = [(c, s) for c in ("A-1", "BAS") for s in stamps]
    origins = pd.DataFrame([(c, _paris(s)) for c, s in pairs], columns=["counter_id", "origin"])
    windows = N.build_windows(data, origins, use_context=False)
    in_bloc = N.refusal_reasons(windows)
    one_by_one = [N.predict_mlp(model.estimator, _inputs(data, s, c)).reason for c, s in pairs]
    assert list(in_bloc) == one_by_one
    assert one_by_one == [N.REFUSE_SPARSE, None, N.REFUSE_SPARSE, N.REFUSE_LOW_LEVEL]
    served = ~np.isnan(N.predict_windows(model.estimator, windows)).any(axis=1)
    assert served.tolist() == [reason is None for reason in one_by_one]


def test_coupure_du_modele_lue_dans_son_bilan(counts, model):
    inputs = _inputs(counts, "2026-06-20 00:00")
    # sans argument fit_cutoff : le réseau entraîné connaît sa coupure et refuse quand même
    assert N.predict_mlp(model.estimator, inputs).reason == N.REFUSE_BEFORE_CUTOFF
    fresh = N.MLPNet(model.estimator.arch["n_inputs"], hidden=8, layers=1)  # jamais entraîné
    assert N.predict_mlp(fresh, inputs).ok  # pas de bilan : aucune coupure connue


def test_prevision_refuse_une_latence_differente(counts, model):
    inputs = _inputs(counts, "2026-07-06 00:00", lag=48)
    with pytest.raises(ValueError, match="latence"):
        N.predict_mlp(model.estimator, inputs)


def test_prevision_avec_contexte(counts, ctx_model):
    net, cutoff = ctx_model.estimator, ctx_model.config.fit_cutoff
    context = _context()
    assert N.predict_mlp(
        net, _inputs(counts, "2026-07-06 00:00", context=context), fit_cutoff=cutoff
    ).ok
    # contexte absent, ou bulletin météo manquant pour la journée : refus, jamais « 0 °C »
    absent = N.predict_mlp(net, _inputs(counts, "2026-07-06 00:00"), fit_cutoff=cutoff)
    assert absent.reason == N.REFUSE_CONTEXT
    day = (context["variable"] == "temp_prev") & pd.to_datetime(
        context["valid_time"], utc=True, format="ISO8601"
    ).between(_paris("2026-07-06 01:00"), _paris("2026-07-07 00:00"))
    hole = N.predict_mlp(
        net, _inputs(counts, "2026-07-06 00:00", context=context.loc[~day]), fit_cutoff=cutoff
    )
    assert hole.reason == N.REFUSE_CONTEXT


# --- Sauvegarde, rechargement, socle commun ------------------------------------------------------


def test_sauvegarde_puis_rechargement_memes_previsions(counts, model, tmp_path):
    out = train.save_model(model, tmp_path)
    back = train.load_model(model.model_run_id, tmp_path)
    assert back.estimator.input_layout == model.estimator.input_layout
    assert back.estimator.input_layout["publication_lag_hours"] == LAG
    assert back.estimator.training_report == model.estimator.training_report
    inputs = _inputs(counts, "2026-07-09 00:00")
    np.testing.assert_array_equal(
        N.predict_mlp(back.estimator, inputs).values, N.predict_mlp(model.estimator, inputs).values
    )
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert meta["parameters"] == N.mlp_hyperparameters(**FAST)  # tous les réglages écrits
    assert torch.load(out / "weights.pt", weights_only=True)["format"] == N.FILE_FORMAT


def test_lecture_d_un_fichier_au_format_1(tmp_path):
    net = N.MLPNet(2 * N.WINDOW_HOURS + 8, hidden=8, layers=1)
    old_layout = {
        "use_context": False,
        "window_hours": N.WINDOW_HOURS,
        "horizon_hours": 24,
        "calendar_columns": N.calendar_columns(False),
    }
    path = tmp_path / "weights.pt"
    torch.save(
        {"format": 1, "arch": net.arch, "layout": old_layout, "state_dict": net.state_dict()}, path
    )
    back = N.load_mlp(path)
    assert back.input_layout["publication_lag_hours"] == 24 and back.training_report is None


def test_sauvegarde_refuse_un_use_context_contradictoire(model, tmp_path):
    with pytest.raises(ValueError, match="use_context"):
        N.save_mlp(model.estimator, tmp_path / "weights.pt", use_context=True)


def test_train_fit_refuse_une_latence_hors_configuration(counts):
    with pytest.raises(ValueError, match="latence de la configuration"):
        train.fit(_config(), counts, None, INVENTORY, publication_lag_hours=48)

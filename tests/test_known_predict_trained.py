"""Branchement des modèles entraînés dans predict.py (synthétique, sans torch ni vrais poids)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.models.known import baseline, predict
from src.models.known.train import (
    MethodBackend,
    TrainConfig,
    TrainedModel,
    make_model_run_id,
    register_backend,
    save_model,
)
from src.models.schemas import Case

CUTOFF = pd.Timestamp("2026-06-30 22:00", tz="UTC")
LOADS: list[Path] = []  # chemins relus par le faux backend : compte les chargements


def _save_json(estimator, path: Path) -> None:
    path.write_text(json.dumps(estimator), encoding="utf-8")


def _load_json(path: Path):
    LOADS.append(path)
    return json.loads(path.read_text(encoding="utf-8"))


BACKEND = MethodBackend("weights.json", save=_save_json, load=_load_json)
register_backend("fakepred", BACKEND)
register_backend("fakeother", BACKEND)


def _saved(root: Path, method: str = "fakepred") -> str:
    config = TrainConfig(method=method, fit_cutoff=CUTOFF, feature_version="f1.0")
    model = TrainedModel(
        model_run_id=make_model_run_id(config),
        config=config,
        estimator={"weights": [1.0, 2.0]},
        donor_site_groups=["G-1"],
        label_interval=(pd.Timestamp("2023-11-14 23:00", tz="UTC"), CUTOFF),
        train_seconds=1.0,
    )
    save_model(model, root)
    return model.model_run_id


@pytest.fixture(autouse=True)
def fake_variants(monkeypatch):
    """Variantes de test : leur « module » est json, importable sans effet."""
    monkeypatch.setitem(predict.TRAINED_VARIANTS, "fakepred", "json")
    monkeypatch.setitem(predict.TRAINED_VARIANTS, "fakeother", "json")
    monkeypatch.setattr(predict, "_MODEL_CACHE", {})
    LOADS.clear()


def test_charge_le_modele_et_le_garde_en_memoire(tmp_path):
    run_id = _saved(tmp_path)
    first = predict.load_trained(run_id, "fakepred", tmp_path)
    second = predict.load_trained(run_id, "fakepred", tmp_path)
    assert first is second
    assert first.estimator == {"weights": [1.0, 2.0]}
    assert len(LOADS) == 1  # un seul chargement depuis le disque


def test_refuse_un_modele_d_une_autre_methode_sans_le_charger(tmp_path):
    run_id = _saved(tmp_path, method="fakeother")
    with pytest.raises(ValueError, match="est un modèle 'fakeother', pas 'fakepred'"):
        predict.load_trained(run_id, "fakepred", tmp_path)
    assert LOADS == []  # refus lu dans metadata.json, avant tout chargement


def test_refuse_aussi_quand_le_modele_est_deja_en_memoire(tmp_path):
    run_id = _saved(tmp_path, method="fakeother")
    predict.load_trained(run_id, "fakeother", tmp_path)
    with pytest.raises(ValueError, match="pas 'fakepred'"):
        predict.load_trained(run_id, "fakepred", tmp_path)


def test_refuse_une_variante_sans_modele_et_un_modele_absent(tmp_path):
    with pytest.raises(ValueError, match="sans modèle entraîné"):
        predict.load_trained("e2-x", "reference", tmp_path)
    with pytest.raises(FileNotFoundError, match="introuvable"):
        predict.load_trained("e2-fakepred-absent", "fakepred", tmp_path)


def test_poids_modifies_refuses_par_load_model(tmp_path):
    run_id = _saved(tmp_path)
    (tmp_path / run_id / "weights.json").write_text('{"weights": [9]}', encoding="utf-8")
    with pytest.raises(ValueError, match="modifiés depuis la sauvegarde"):
        predict.load_trained(run_id, "fakepred", tmp_path)


def test_vrais_modeles_du_depot_declares():
    assert predict.TRAINED_VARIANTS["mlp"] == "src.models.known.neural"
    assert predict.TRAINED_VARIANTS["hgb"] == "src.models.known.tabular"


# --- trained_forecast : prévision du modèle ou repli ------------------------------------

ORIGIN = "2026-07-01T22:00:00+00:00"  # minuit local du 2 juillet 2026
HGB_ID = "e2-hgb-ctx-20260701-s0-b357"  # modèle réel du dépôt (MOD-010)


def _case(real: bool = False, **overrides) -> Case:
    """Cas synthétique ; real=True : instantané et groupe de site du vrai HGB du dépôt."""
    row = {
        "case_id": "K1",
        "counter_id": "C-1",
        "site_group_id": "100003096" if real else "G-1",
        "origin": ORIGIN,
        "scenario": "known_site",
        "temporal_split": "validation",
        "spatial_role": "S_train",
        "local_budget_hours": "",
        "support_start": "",
        "support_end": "",
        "protocol_id": "P-test",
        "snapshot_id": "hist-20261117" if real else "S-test",
    }
    row.update(overrides)
    return Case.from_row(row)


def _history(measured: bool = True) -> pd.DataFrame:
    """Trois semaines horaires du compteur C-1 ; valeur = rang de l'heure (ou rien)."""
    ts = pd.date_range("2026-06-10T00:00", "2026-07-03T23:00", freq="h", tz="UTC")
    values = np.arange(len(ts), dtype=float) if measured else np.full(len(ts), np.nan)
    return pd.DataFrame(
        {
            "counter_id": "C-1",
            "timestamp": ts,
            "interval_end": ts + pd.Timedelta(hours=1),
            "count_raw": values,
            "count": values,
            "is_observed": measured,
            "is_scoreable": measured,
        }
    )


def _model(fallback: str | None = "reference") -> TrainedModel:
    config = TrainConfig(method="fakepred", fit_cutoff=CUTOFF, feature_version="f1.0")
    return TrainedModel(
        model_run_id="e2-fakepred-test",
        config=config,
        estimator=None,
        donor_site_groups=["G-1"],
        label_interval=(CUTOFF, CUTOFF),
        train_seconds=0.0,
        fallback=fallback,
    )


def _raw(monkeypatch, values=None, reason=None):
    out = SimpleNamespace(ok=values is not None, values=values, reason=reason)
    monkeypatch.setattr(predict, "_raw_forecast", lambda variant, model, inputs: out)


def test_modele_qui_prevoit(monkeypatch):
    _raw(monkeypatch, values=np.arange(24, dtype=float))
    inputs = predict.build_inputs(_case(), _history())
    result = predict.trained_forecast(inputs, "fakepred", _model())
    preds = result.predictions
    assert preds["y_pred"].tolist() == list(range(24))
    assert set(preds["method_used"]) == {"fakepred"}
    assert set(preds["prediction_status"]) == {"ok"} and result.status == "ok"
    assert result.model_run_id == result.method_run_id == "e2-fakepred-test"
    assert result.fit_cutoff == CUTOFF and result.feature_version == "f1.0"
    assert result.is_complete()


def test_refus_repli_sur_la_reference_et_code_trace(monkeypatch):
    _raw(monkeypatch, reason="mlp_window_too_sparse")
    inputs = predict.build_inputs(_case(), _history())
    result = predict.trained_forecast(inputs, "fakepred", _model(), method_run_id="run-1")
    ref = baseline.weekly_reference(inputs)
    preds = result.predictions
    assert preds["y_pred"].tolist() == ref.predictions["y_pred"].tolist()
    # méthode réellement employée : celle de la référence, pas le modèle
    assert preds["method_used"].tolist() == ref.predictions["method_used"].tolist()
    assert set(preds["prediction_status"]) == {"fallback"} and result.status == "fallback"
    assert all(r.startswith("mlp_window_too_sparse") for r in preds["status_reason"])
    assert result.status_reason.startswith("mlp_window_too_sparse")
    assert result.method_run_id == "run-1" and result.model_run_id == "e2-fakepred-test"
    assert result.is_complete()


def test_refus_sans_historique_reste_vide_jamais_zero(monkeypatch):
    _raw(monkeypatch, reason="mlp_no_history")
    inputs = predict.build_inputs(_case(), _history(measured=False))
    result = predict.trained_forecast(inputs, "fakepred", _model())
    assert result.predictions["y_pred"].isna().all()
    assert set(result.predictions["prediction_status"]) == {"unavailable"}
    assert result.status == "unavailable" and not result.is_complete()


def test_repli_inconnu_refuse(monkeypatch):
    _raw(monkeypatch, reason="mlp_no_history")
    inputs = predict.build_inputs(_case(), _history())
    with pytest.raises(ValueError, match="repli None inconnu"):
        predict.trained_forecast(inputs, "fakepred", _model(fallback=None))


def test_vrai_hgb_sans_contexte_se_replie(monkeypatch):
    """Chaîne réelle : load_trained + predict_hgb ; sans contexte, refus hgb_context_missing."""
    monkeypatch.setattr(predict, "_MODEL_CACHE", {})
    root = predict.data_path("models")
    if not (root / HGB_ID).exists():
        pytest.skip("modèle HGB du dépôt absent")
    model = predict.load_trained(HGB_ID, "hgb")
    inputs = predict.build_inputs(_case(real=True), _history())
    result = predict.trained_forecast(inputs, "hgb", model)
    assert result.status == "fallback"
    assert result.status_reason.startswith("hgb_context_missing")
    assert result.model_run_id == HGB_ID and result.is_complete()


# --- predict_24h : variantes mlp / hgb ---------------------------------------------------


def test_predict_24h_exige_un_model_run_id_sans_modele_par_defaut():
    with pytest.raises(ValueError, match="model_run_id obligatoire"):
        predict.predict_24h(_case(), _history(), variant="fakepred")


def test_modeles_par_defaut_declares():
    assert predict.DEFAULT_MODEL_RUN_IDS == {
        "mlp": "e2-mlp-ctx-20260701-s0-9ce9",
        "hgb": "e2-hgb-ctx-20260701-s0-b357",
    }
    assert set(predict.SUPPORTED_VARIANTS) == {"reference", "reference_profile", "mlp", "hgb"}


def test_predict_24h_liste_toutes_les_variantes():
    with pytest.raises(ValueError, match="indisponible.*'hgb'.*'mlp'"):
        predict.predict_24h(_case(), _history(), variant="gbm")


def test_predict_24h_branche_le_modele_entraine(monkeypatch, tmp_path):
    run_id = _saved(tmp_path)
    monkeypatch.setattr(predict, "data_path", lambda key: tmp_path)
    _raw(monkeypatch, values=np.full(24, 5.0))
    result = predict.predict_24h(_case(), _history(), variant="fakepred", model_run_id=run_id)
    assert result.status == "ok" and result.model_run_id == run_id
    assert result.predictions["y_pred"].tolist() == [5.0] * 24
    assert result.cost.preparation_seconds > 0


def test_predict_24h_reference_inchangee():
    result = predict.predict_24h(_case(), _history())
    ref = baseline.weekly_reference(predict.build_inputs(_case(), _history()))
    assert result.predictions["y_pred"].tolist() == ref.predictions["y_pred"].tolist()
    assert result.model_run_id is None


def _context() -> pd.DataFrame:
    """Contexte au format context.csv (calendrier, grèves, météo prévue), connu à l'origine."""
    days = pd.date_range("2026-06-01", "2026-07-05", freq="D")
    available = (days.tz_localize("Europe/Paris").tz_convert("UTC") - pd.Timedelta(hours=24)).map(
        pd.Timestamp.isoformat
    )
    daily = [
        pd.DataFrame(
            {
                "variable": variable,
                "local_date": days.strftime("%Y-%m-%d"),
                "valid_time": None,
                "value": "false",
                "available_at": available if variable == "is_strike" else None,
                "role": "known_calendar",
                "context_version": "e1-context/0.3.0",
            }
        )
        for variable in ("is_holiday", "is_school_holiday", "is_strike")
    ]
    valid = pd.date_range("2026-06-01", "2026-07-05", freq="h", tz="UTC")
    hourly = [
        pd.DataFrame(
            {
                "variable": variable,
                "local_date": None,
                "valid_time": valid.map(pd.Timestamp.isoformat),
                "value": value,
                "available_at": (valid - pd.Timedelta(hours=42)).map(pd.Timestamp.isoformat),
                "role": "forecast_bulletin",
                "context_version": "e1-context/0.3.0",
            }
        )
        for variable, value in (("temp_prev", "18.0"), ("rain_prev", "0.0"), ("wind_prev", "3.0"))
    ]
    return pd.concat(daily + hourly, ignore_index=True)


def test_vrai_hgb_prevoit_et_ne_lit_pas_le_futur(monkeypatch):
    """Modèle réel du dépôt, avec contexte : servi (ok), et changer les heures publiées
    après la coupure (origine - 24 h) ne change pas sa prévision."""
    monkeypatch.setattr(predict, "_MODEL_CACHE", {})
    if not (predict.data_path("models") / HGB_ID).exists():
        pytest.skip("modèle HGB du dépôt absent")
    history = _history()
    future = history["interval_end"] > pd.Timestamp(ORIGIN) - pd.Timedelta(hours=24)
    changed = history.copy()
    changed.loc[future, ["count", "count_raw"]] = 1e6
    ctx = _context()
    a = predict.predict_24h(_case(real=True), history, "hgb", context=ctx, model_run_id=HGB_ID)
    b = predict.predict_24h(_case(real=True), changed, "hgb", context=ctx, model_run_id=HGB_ID)
    assert a.status == "ok" and set(a.predictions["method_used"]) == {"hgb"}
    assert a.is_complete()
    assert a.predictions["y_pred"].tolist() == b.predictions["y_pred"].tolist()
    # témoin positif : changer la dernière semaine visible change bien la prévision
    seen = changed.copy()
    seen.loc[~future, ["count", "count_raw"]] = seen.loc[~future, "count"] * 3
    c = predict.predict_24h(_case(real=True), seen, "hgb", context=ctx)  # modèle par défaut
    assert c.predictions["y_pred"].tolist() != a.predictions["y_pred"].tolist()


# --- run_experiment et commande main -------------------------------------------------------


def test_run_experiment_transmet_le_modele(monkeypatch, tmp_path):
    run_id = _saved(tmp_path)
    monkeypatch.setattr(predict, "data_path", lambda key: tmp_path)
    _raw(monkeypatch, values=np.full(24, 7.0))
    row = _case()
    cases = pd.DataFrame(
        [
            {
                "case_id": row.case_id,
                "counter_id": row.counter_id,
                "site_group_id": "G-1",
                "origin": ORIGIN,
                "scenario": "known_site",
                "temporal_split": "validation",
                "spatial_role": "S_train",
                "local_budget_hours": "",
                "support_start": "",
                "support_end": "",
                "protocol_id": "P-test",
                "snapshot_id": "S-test",
            }
        ]
    )
    pred_path, runs_path = predict.run_experiment(
        cases,
        lambda counter_id: _history(),
        "fakepred",
        "EXP-test",
        "run-fake",
        root=tmp_path / "out",
        model_run_id=run_id,
    )
    pred = pd.read_csv(pred_path, dtype=str, keep_default_na=False)
    runs = pd.read_csv(runs_path, dtype=str, keep_default_na=False)
    assert len(pred) == 24 and set(pred["y_pred"]) == {"7.0"}
    assert set(pred["model_run_id"]) == {run_id} and set(pred["method_used"]) == {"fakepred"}
    assert runs.loc[0, "status"] == "ok" and runs.loc[0, "model_run_id"] == run_id


def test_load_context_lit_tout_en_texte(tmp_path):
    path = tmp_path / "context.csv"
    _context().to_csv(path, index=False)
    ctx = predict.load_context("S-test", path=path)
    assert all(ctx[c].map(lambda v: isinstance(v, str) or pd.isna(v)).all() for c in ctx)
    assert set(ctx["value"]) >= {"false", "18.0"}
    with pytest.raises(FileNotFoundError, match="context.csv introuvable"):
        predict.load_context("S-test", path=tmp_path / "absent.csv")


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--variant", "hgb", "--model-run-id", "x", "--values", "e1_filled"], "mesures seules"),
        (["--variant", "reference", "--model-run-id", "x"], "sans objet"),
    ],
)
def test_main_refuse_les_appels_incoherents(extra, message, capsys):
    base = ["--cases", "c.csv", "--snapshot", "S", "--experiment", "E"]
    with pytest.raises(SystemExit):
        predict.main(base + extra)
    assert message in capsys.readouterr().err


# --- contrôles d'éligibilité communs (proposés par E5) --------------------------


def _eligible_model(**config_changes):
    config = TrainConfig(
        method="fakepred",
        fit_cutoff=CUTOFF,
        feature_version="f1.0",
        snapshot_id="S-test",
        use_context=True,
        context_version="ctx-1",
    )
    for key, value in config_changes.items():
        setattr(config, key, value)
    return TrainedModel(
        model_run_id="e2-fakepred-test",
        config=config,
        estimator=None,
        donor_site_groups=["G-1"],
        excluded_site_groups=["R-1"],
        label_interval=(CUTOFF, CUTOFF),
        train_seconds=0.0,
    )


@pytest.mark.parametrize(
    ("case_changes", "config_changes", "context_version", "code"),
    [
        ({}, {}, "ctx-1", None),
        ({"snapshot_id": "autre"}, {}, "ctx-1", "fakepred_snapshot_incompatible"),
        (
            {},
            {"fit_cutoff": pd.Timestamp(ORIGIN) + pd.Timedelta(hours=1)},
            "ctx-1",
            "fakepred_origin_before_fit_cutoff",
        ),
        ({"site_group_id": "G-2"}, {}, "ctx-1", "fakepred_site_not_in_training"),
        ({}, {}, None, "fakepred_context_missing"),
        ({}, {}, "ctx-2", "fakepred_context_incompatible"),
    ],
)
def test_eligibilite_site_connu(case_changes, config_changes, context_version, code):
    inputs = predict.build_inputs(_case(**case_changes), _history())
    inputs.context_version = context_version
    model = _eligible_model(**config_changes)
    assert predict.eligibility_reason(inputs, model, "fakepred") == code


def test_eligibilite_nouveau_site_doit_etre_reserve():
    """Nouveau site (E3) : seulement un groupe exclu de l'apprentissage et déclaré réservé."""
    model = _eligible_model()
    inputs = predict.build_inputs(_case(), _history())
    inputs.context_version = "ctx-1"
    for site, code in (
        ("R-1", None),
        ("G-1", "fakepred_site_not_confirmed_reserved"),
        ("X-9", "fakepred_site_not_confirmed_reserved"),
    ):
        inputs.case = replace(inputs.case, scenario="new_site", site_group_id=site)
        assert predict.eligibility_reason(inputs, model, "fakepred") == code


def test_refus_d_eligibilite_trace_sans_appeler_le_modele(monkeypatch):
    monkeypatch.setattr(
        predict, "_raw_forecast", lambda *a: pytest.fail("modèle appelé malgré le refus")
    )
    inputs = predict.build_inputs(_case(site_group_id="G-2"), _history())
    result = predict.trained_forecast(inputs, "fakepred", _model())
    assert result.status == "fallback"
    assert result.status_reason == "fakepred_site_not_in_training"
    assert result.predictions["status_reason"].eq("fakepred_site_not_in_training").all()

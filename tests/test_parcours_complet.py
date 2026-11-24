"""Tests de parcours complet E5 : contrôle → prévision → export masqué → révélation → export.

Trois parcours, comme dans l'application :
- cas normal (site connu, historique complet) ;
- cas difficile (site connu, panne de capteur avant l'origine et heure cible manquante) ;
- nouveau site (support local limité).
Données synthétiques uniquement, séparées des performances réelles.
"""

import io
import json
from zipfile import ZipFile

import pandas as pd
import pytest

from src.app import reliability, service
from src.app.export import study_zip
from src.models.schemas import HORIZON_HOURS

LAG = 24
DAY = pd.Timestamp("2026-10-20").date()
HIDDEN_FILES = {"observations.csv", "errors.csv"}


def make_case(role="S_train", budget=None):
    counter = pd.Series({"counter_id": "001", "site_group_id": "01", "site_role": role})
    if budget is None:
        return service.technical_case(counter, DAY, "test")
    return service.technical_new_case(counter, DAY, "test", budget, LAG)


def make_history(case, past=10.0, target=25.0):
    hours = pd.date_range(
        case.origin - pd.Timedelta(days=35),
        case.origin + pd.Timedelta(hours=HORIZON_HOURS),
        freq="h",
        inclusive="left",
    )
    history = pd.DataFrame(
        {
            "counter_id": case.counter_id,
            "timestamp": hours,
            "interval_end": hours + pd.Timedelta(hours=1),
            "count_raw": past,
            "count": past,
            "is_observed": True,
            "is_scoreable": True,
        }
    )
    history.loc[history["timestamp"].ge(case.origin), ["count_raw", "count"]] = target
    return history


def zip_names(study, evaluation=None):
    with ZipFile(io.BytesIO(study_zip(study, evaluation))) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        return set(archive.namelist()), manifest


def run_journey(case, history, method):
    """Rejouer le parcours de l'interface et renvoyer chaque étape."""
    history_check = reliability.check_history(case, history, LAG, method)
    (study,) = service.run_studies(case, method, None, history, None, LAG)
    forecast_check = reliability.check_forecast(study.forecast)
    hidden_files, hidden_manifest = zip_names(study)
    evaluation = service.reveal(study, history)
    revealed_files, revealed_manifest = zip_names(study, evaluation)
    return {
        "history": history_check,
        "study": study,
        "forecast": forecast_check,
        "hidden_files": hidden_files,
        "hidden_manifest": hidden_manifest,
        "evaluation": evaluation,
        "revealed_files": revealed_files,
        "revealed_manifest": revealed_manifest,
    }


def assert_reveal_rule(journey):
    """Règle commune aux trois parcours : aucune cible avant révélation."""
    assert not HIDDEN_FILES & journey["hidden_files"]
    assert journey["hidden_manifest"]["targets_revealed"] is False
    assert "evaluation" not in journey["hidden_manifest"]
    assert "observations.csv" in journey["revealed_files"]
    assert journey["revealed_manifest"]["targets_revealed"] is True


# --------------------------------------------------------------------------
# Parcours 1 : cas normal
# --------------------------------------------------------------------------


def test_parcours_cas_normal():
    case = make_case()
    journey = run_journey(case, make_history(case), "reference")

    assert journey["history"].level == reliability.LEVEL_OK
    assert journey["forecast"].is_complete
    assert journey["forecast"].n_fallback == 0
    assert journey["study"].forecast["y_pred"].tolist() == [10.0] * HORIZON_HOURS
    assert_reveal_rule(journey)
    assert journey["evaluation"]["n_compared_hours"] == 24
    assert journey["evaluation"]["mae"] == pytest.approx(15.0)


def test_revelation_ne_recalcule_pas_la_prevision():
    case = make_case()
    history = make_history(case)
    (study,) = service.run_studies(case, "reference", None, history, None, LAG)
    before = study.forecast.copy()

    service.reveal(study, history)

    pd.testing.assert_frame_equal(study.forecast, before)


# --------------------------------------------------------------------------
# Parcours 2 : cas difficile
# --------------------------------------------------------------------------


def test_parcours_cas_difficile_panne_et_cible_manquante():
    case = make_case()
    history = make_history(case)
    # Panne de 6 heures, une semaine avant les 6 premières heures cibles : t-168 h manque.
    outage = case.origin - pd.Timedelta(hours=168)
    rows = history["timestamp"].ge(outage) & history["timestamp"].lt(outage + pd.Timedelta(hours=6))
    history.loc[rows, ["count_raw", "count"]] = None
    history.loc[rows, "is_observed"] = False
    # Une heure cible non mesurée : elle ne doit pas devenir une erreur nulle.
    missing_target = case.origin + pd.Timedelta(hours=10)
    history.loc[history["timestamp"].eq(missing_target), ["count_raw", "count"]] = None
    history.loc[history["timestamp"].eq(missing_target), "is_scoreable"] = False

    journey = run_journey(case, history, "reference")

    assert journey["history"].level == reliability.LEVEL_PARTIAL
    assert "162 heures mesurées sur 168" in journey["history"].message
    assert journey["forecast"].is_complete  # le repli comble les heures manquantes
    assert journey["forecast"].n_fallback == 6
    reasons = journey["study"].forecast["status_reason"].map(reliability.explain_reason)
    assert reasons.str.contains("repli").sum() == 6
    assert_reveal_rule(journey)
    assert journey["evaluation"]["n_compared_hours"] == 23


def test_parcours_compteur_sans_historique():
    case = make_case()
    history = make_history(case)
    history = history.loc[history["timestamp"].ge(case.origin)]  # seulement le futur

    check = reliability.check_history(case, history, LAG, "reference")
    assert not check.can_forecast

    # Si le calcul est tout de même lancé, les 24 heures restent vides et expliquées.
    (study,) = service.run_studies(case, "reference", None, history, None, LAG)
    result = reliability.check_forecast(study.forecast)
    assert not result.is_complete
    assert result.n_valid == 0
    assert study.forecast["prediction_status"].eq("unavailable").all()
    assert result.problems == (
        "Sans prévision (h1–h24) : Mesure de la semaine précédente manquante : valeur de "
        "repli utilisée ; Aucune mesure historique à cette heure pour calculer un repli.",
    )


# --------------------------------------------------------------------------
# Parcours 3 : nouveau site
# --------------------------------------------------------------------------


def test_parcours_nouveau_site_support_local():
    case = make_case(role="S_dev_new", budget=168)
    journey = run_journey(case, make_history(case), service.LOCAL_REFERENCE)

    assert journey["history"].required_hours == 168
    assert journey["history"].level == reliability.LEVEL_OK
    assert journey["forecast"].is_complete
    assert_reveal_rule(journey)


def test_nouveau_site_support_trop_court():
    case = make_case(role="S_dev_new", budget=24)
    history = make_history(case)

    check = reliability.check_history(case, history, LAG)
    assert check.required_hours == 24
    (study,) = service.run_studies(case, service.LOCAL_REFERENCE, None, history, None, LAG)
    result = reliability.check_forecast(study.forecast)
    # 24 h de support ne contiennent pas t-168 h : les 24 heures passent par le repli.
    assert result.is_complete
    assert result.n_fallback == HORIZON_HOURS
    assert study.forecast["status_reason"].eq("lag168_missing").all()

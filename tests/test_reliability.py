"""Tests du module de fiabilité E5 (src/app/reliability.py).

Historique suffisant ou non, prévisions incomplètes et messages d'erreur.
Données synthétiques uniquement.
"""

import pandas as pd
import pytest

from src.app import reliability, service
from src.models.schemas import HORIZON_HOURS, target_timestamps

LAG = 24
DAY = pd.Timestamp("2026-10-20").date()


def known_case():
    counter = pd.Series({"counter_id": "001", "site_group_id": "01", "site_role": "S_train"})
    return service.technical_case(counter, DAY, "test")


def new_case(budget=168):
    counter = pd.Series({"counter_id": "002", "site_group_id": "02", "site_role": "S_dev_new"})
    return service.technical_new_case(counter, DAY, "test", budget, LAG)


def make_history(case, days=35, value=10.0):
    """Historique horaire complet jusqu'à la fin des 24 heures cibles incluses."""
    hours = pd.date_range(
        case.origin - pd.Timedelta(days=days),
        case.origin + pd.Timedelta(hours=HORIZON_HOURS),
        freq="h",
        inclusive="left",
    )
    return pd.DataFrame(
        {
            "counter_id": case.counter_id,
            "timestamp": hours,
            "interval_end": hours + pd.Timedelta(hours=1),
            "count_raw": value,
            "count": value,
            "is_observed": True,
            "is_scoreable": True,
        }
    )


def blank(history, start, end):
    """Rendre absentes (non mesurées) les heures de [start, end)."""
    rows = history["timestamp"].ge(start) & history["timestamp"].lt(end)
    history.loc[rows, ["count_raw", "count"]] = None
    history.loc[rows, "is_observed"] = False
    return history


def make_forecast(case, statuses=None, values=None, reasons=None):
    frame = target_timestamps(case.origin)
    frame["y_pred"] = values if values is not None else [5.0] * HORIZON_HOURS
    frame["prediction_status"] = statuses if statuses is not None else ["ok"] * HORIZON_HOURS
    frame["status_reason"] = reasons if reasons is not None else [None] * HORIZON_HOURS
    return frame


# --------------------------------------------------------------------------
# Historique suffisant
# --------------------------------------------------------------------------


def test_heures_requises_selon_la_methode():
    assert reliability.required_history_hours(known_case(), "reference") == 168
    assert reliability.required_history_hours(known_case(), "reference_profile") == 4 * 168
    assert reliability.required_history_hours(known_case(), service.COMPARE_REFERENCES) == 672
    assert reliability.required_history_hours(new_case(72), None) == 72


def test_historique_complet_est_suffisant():
    case = known_case()
    check = reliability.check_history(case, make_history(case), LAG, "reference")

    assert check.level == reliability.LEVEL_OK
    assert check.observed_hours == check.required_hours == 168
    assert check.can_forecast
    assert check.window_end == case.origin - pd.Timedelta(hours=LAG)


def test_historique_partiel_donne_un_avertissement():
    case = known_case()
    cutoff = case.origin - pd.Timedelta(hours=LAG)
    history = blank(make_history(case), cutoff - pd.Timedelta(hours=48), cutoff)

    check = reliability.check_history(case, history, LAG, "reference")

    assert check.level == reliability.LEVEL_PARTIAL
    assert check.observed_hours == 120
    assert check.can_forecast
    assert "120 heures mesurées sur 168" in check.message


def test_compteur_sans_historique_bloque_le_calcul():
    case = known_case()
    history = make_history(case).iloc[0:0]

    check = reliability.check_history(case, history, LAG, "reference")

    assert check.level == reliability.LEVEL_NONE
    assert not check.can_forecast
    assert "Historique insuffisant" in check.message


def test_historique_trop_court_pour_le_profil_quatre_semaines():
    case = known_case()
    history = make_history(case, days=10)

    assert reliability.check_history(case, history, LAG, "reference").level == "ok"
    profile = reliability.check_history(case, history, LAG, "reference_profile")
    assert profile.level == reliability.LEVEL_PARTIAL


def test_zero_observe_compte_comme_une_mesure():
    case = known_case()
    check = reliability.check_history(case, make_history(case, value=0.0), LAG, "reference")
    assert check.level == reliability.LEVEL_OK


def test_le_futur_n_est_jamais_compte():
    """Les heures cibles et la période non publiée ne comptent pas dans l'historique."""
    case = known_case()
    history = make_history(case, days=0)  # seulement les 24 heures cibles
    history = pd.concat([history, make_history(case, days=1).iloc[:LAG]])

    check = reliability.check_history(case, history, LAG, "reference")
    assert check.observed_hours == 0


def test_nouveau_site_limite_au_support_local():
    case = new_case(budget=72)
    check = reliability.check_history(case, make_history(case), LAG)

    assert check.required_hours == 72
    assert check.observed_hours == 72  # les semaines antérieures au support sont ignorées
    assert check.level == reliability.LEVEL_OK


def test_nouveau_site_sans_budget_refuse():
    case = new_case()
    case = case.__class__(**{**case.__dict__, "local_budget_hours": None})
    with pytest.raises(ValueError):
        reliability.check_history(case, make_history(case), LAG)


# --------------------------------------------------------------------------
# Prévisions incomplètes
# --------------------------------------------------------------------------


def test_prevision_complete():
    check = reliability.check_forecast(make_forecast(known_case()))

    assert check.is_complete
    assert check.n_valid == 24
    assert check.problems == ()


def test_repli_reste_une_prevision_valide():
    statuses = ["fallback"] * 3 + ["ok"] * 21
    check = reliability.check_forecast(make_forecast(known_case(), statuses=statuses))

    assert check.is_complete
    assert check.n_fallback == 3


def test_heures_en_echec_sont_detaillees():
    statuses = ["ok"] * 20 + ["error"] * 4
    values = [5.0] * 20 + [None] * 4
    reasons = [None] * 20 + ["lag168_missing;no_fallback_history"] * 4
    check = reliability.check_forecast(
        make_forecast(known_case(), statuses=statuses, values=values, reasons=reasons)
    )

    assert not check.is_complete
    assert check.n_valid == 20
    assert check.n_failed == 4
    assert len(check.problems) == 1
    assert "h21–h24" in check.problems[0]
    assert "Aucune mesure historique" in check.problems[0]


def test_horizon_absent_detecte():
    forecast = make_forecast(known_case()).drop(index=[0, 1, 9])
    check = reliability.check_forecast(forecast)

    assert not check.is_complete
    assert check.missing_horizons == (1, 2, 10)
    assert "h1–h2, h10" in check.problems[0]


def test_horizon_en_double_detecte():
    forecast = make_forecast(known_case())
    forecast = pd.concat([forecast, forecast.iloc[[5]]], ignore_index=True)
    check = reliability.check_forecast(forecast)

    assert not check.is_complete
    assert check.duplicate_horizons == (6,)


@pytest.mark.parametrize("bad", [None, -1.0])
def test_valeur_absente_ou_negative_non_valide(bad):
    values = [5.0] * 23 + [bad]
    check = reliability.check_forecast(make_forecast(known_case(), values=values))

    assert not check.is_complete
    assert check.n_valid == 23


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (None, ""),
        (float("nan"), ""),
        ("", ""),
        ("lag168_missing", "Mesure de la semaine précédente manquante"),
        ("profile_weeks_missing;no_fallback_history", "quatre semaines ; Aucune mesure"),
        ("ValueError: compteur 9 absent", "Erreur de calcul : compteur 9 absent"),
        ("code_inconnu", "code_inconnu"),
    ],
)
def test_explain_reason(reason, expected):
    assert expected in reliability.explain_reason(reason)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FileNotFoundError("weights.pt"), "fichier ou une ressource est introuvable"),
        (KeyError("count_raw"), "colonne ou une donnée attendue est absente (count_raw)"),
        (RuntimeError("timeout"), "le calcul a été interrompu"),
        (AttributeError("no attribute 'METHOD_RUN_ID'"), "pas utilisable dans cette version"),
        (ImportError("torch"), "pas utilisable dans cette version"),
        (ValueError("Le cas E3 doit préciser un budget"), "Le cas E3 doit préciser un budget"),
    ],
)
def test_explain_error(error, expected):
    message = reliability.explain_error(error)
    assert message.startswith("Prévision indisponible")
    assert expected in message

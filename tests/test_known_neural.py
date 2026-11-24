"""Préparation des exemples du MLP (build_windows) sur un petit cas construit à la main.

Données synthétiques : elles vérifient le code, pas une performance sur Paris.
Chaque comptage vaut 100 + (heure UTC du jour), pour savoir d'où vient chaque valeur.
"""

from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.known import neural as N
from src.models.known import train

LAG = 24
ORIGIN = pd.Timestamp("2026-03-10 00:00", tz="Europe/Paris").tz_convert("UTC")  # 23:00Z


def _counts(start="2026-02-20", end="2026-03-12", counter="A-1", factor=1.0) -> pd.DataFrame:
    hours = pd.date_range(start, end, freq="h", tz="UTC", inclusive="left")
    value = (100 + hours.hour).to_numpy(dtype=float) * factor
    return pd.DataFrame(
        {
            "counter_id": counter,
            "timestamp": hours,
            "count": value,
            "count_raw": value,
            "is_scoreable": True,
        }
    )


def _origins(*stamps, counter="A-1") -> pd.DataFrame:
    return pd.DataFrame({"counter_id": counter, "origin": list(stamps) or [ORIGIN]})


def test_fenetre_finit_24h_avant_l_origine():
    w = N.build_windows(_counts(), _origins(), use_context=False)
    assert w.series.shape == (1, 168) and w.mask.shape == (1, 168)
    # sans contexte : jour de la semaine (7) + dst_shift (1), une seule fois
    assert w.calendar.shape == (1, 8) and w.n_inputs == 168 + 168 + 8
    assert w.calendar_columns == [f"dow_{d}" for d in range(7)] + ["dst_shift"]
    assert w.calendar[0].tolist() == [0, 1, 0, 0, 0, 0, 0, 0]  # mardi, jour normal
    # dernière heure visible : origine - 24 h - 1 h = 08/03 22:00Z -> 100 + 22 = 122
    raw = w.series[0] * w.scale[0]
    assert raw[-1] == pytest.approx(122)
    assert raw[0] == pytest.approx(100 + 23)  # 01/03 23:00Z, 168 h plus tôt
    assert w.scale[0] == pytest.approx(111.5)  # moyenne de 100..123
    # cibles : 09/03 23:00Z (h1) puis 10/03 00:00Z ...
    assert (w.target[0] * w.scale[0])[:3] == pytest.approx([123, 100, 101])


def test_modifier_le_futur_ne_change_pas_les_entrees():
    counts = _counts()
    before = N.build_windows(counts, _origins(), use_context=False)
    late = counts["timestamp"] >= ORIGIN - pd.Timedelta(hours=LAG)  # pas encore publié
    changed = counts.copy()
    changed.loc[late, ["count", "count_raw"]] = 99999.0
    after = N.build_windows(changed, _origins(), use_context=False)
    np.testing.assert_array_equal(before.series, after.series)
    np.testing.assert_array_equal(before.mask, after.mask)
    assert before.scale[0] == after.scale[0]


def test_manquant_contre_zero_mesure():
    counts = _counts()
    last = ORIGIN - pd.Timedelta(hours=LAG + 1)
    counts.loc[counts["timestamp"] == last, "count"] = np.nan  # heure non mesurée
    counts.loc[counts["timestamp"] == last - pd.Timedelta(hours=1), "count"] = 0.0  # vrai zéro
    counts = counts.loc[counts["timestamp"] != last - pd.Timedelta(hours=2)]  # ligne absente
    w = N.build_windows(counts, _origins(), use_context=False)
    assert w.mask[0, -1] == 0 and w.series[0, -1] == 0  # manquante
    assert w.mask[0, -2] == 1 and w.series[0, -2] == 0  # zéro mesuré : gardé
    assert w.mask[0, -3] == 0  # ligne absente = manquante, jamais zéro


def test_cibles_seulement_les_vraies_mesures():
    counts = _counts()
    first_target = counts["timestamp"] == ORIGIN
    counts.loc[first_target, "is_scoreable"] = False  # valeur remplie par E1
    w = N.build_windows(counts, _origins(), use_context=False)
    assert not w.target_mask[0, 0] and w.target[0, 0] == 0
    assert w.target_mask[0, 1:].all()


def test_fenetre_trop_vide_non_utilisable():
    counts = _counts()
    window = (counts["timestamp"] < ORIGIN - pd.Timedelta(hours=LAG)) & (
        counts["timestamp"] >= ORIGIN - pd.Timedelta(hours=LAG + 100)
    )
    counts.loc[window, "count"] = np.nan  # 100 h manquantes sur 168
    w = N.build_windows(counts, _origins(), use_context=False)
    assert not w.usable[0] and np.isnan(w.scale[0])


def test_invariance_d_echelle():
    a = N.build_windows(_counts(), _origins(), use_context=False)
    b = N.build_windows(_counts(factor=10.0), _origins(), use_context=False)
    np.testing.assert_allclose(a.series, b.series, rtol=1e-6)
    np.testing.assert_allclose(a.target, b.target, rtol=1e-6)
    assert b.scale[0] == pytest.approx(10 * a.scale[0])


def test_en_bloc_egal_cas_par_cas():
    counts = pd.concat([_counts(), _counts(counter="B-2", factor=3.0)], ignore_index=True)
    stamps = [ORIGIN - pd.Timedelta(days=d) for d in range(3)]
    origins = pd.concat([_origins(*stamps), _origins(*stamps, counter="B-2")], ignore_index=True)
    bloc = N.build_windows(counts, origins, use_context=False)
    for i, row in origins.iterrows():
        one = N.build_windows(counts, origins.iloc[[i]], use_context=False)
        np.testing.assert_array_equal(bloc.X[i], one.X[0])
        np.testing.assert_array_equal(bloc.target[i], one.target[0])
        assert bloc.counter_id[i] == row["counter_id"]


def test_changement_d_heure_signale_une_fois():
    counts = _counts(start="2026-03-01", end="2026-04-01")
    spring = pd.Timestamp("2026-03-29 00:00", tz="Europe/Paris").tz_convert("UTC")  # 23 h
    normal = pd.Timestamp("2026-03-24 00:00", tz="Europe/Paris").tz_convert("UTC")
    w = N.build_windows(counts, _origins(spring, normal), use_context=False)
    col = {name: i for i, name in enumerate(w.calendar_columns)}
    assert w.calendar[0, col["dst_shift"]] == -1  # dimanche 29/03 : 2 h n'existe pas
    assert w.calendar[0, col["dow_6"]] == 1  # dimanche
    assert w.calendar[1, col["dst_shift"]] == 0 and w.calendar[1, col["dow_1"]] == 1


def _context() -> pd.DataFrame:
    day = "2026-03-10"
    weather_hours = pd.date_range(ORIGIN, periods=24, freq="h") + pd.Timedelta(hours=1)
    return pd.DataFrame(
        {
            "variable": ["is_strike", "is_holiday"] + ["temp_prev"] * 24,
            "local_date": [day, day] + [None] * 24,
            "valid_time": [None, None] + [t.isoformat() for t in weather_hours],  # interval_end
            "value": ["true", "true"] + [str(10.0 + h) for h in range(24)],
            "available_at": [
                (ORIGIN + pd.Timedelta(hours=1)).isoformat(),  # grève annoncée après l'origine
                None,  # férié connu à l'avance
            ]
            + [(ORIGIN - pd.Timedelta(hours=18)).isoformat()] * 24,  # bulletin J-2 publié
            "role": ["known_calendar", "known_calendar"] + ["forecast_bulletin"] * 24,
        }
    )


def test_contexte_journee_une_fois_meteo_heure_par_heure():
    w = N.build_windows(_counts(), _origins(), _context(), use_context=True)
    columns = w.calendar_columns
    assert len(columns) == 8 + 3 + 3 * 24 and w.n_inputs == 168 + 168 + 83
    assert columns[8:11] == ["is_holiday", "is_school_holiday", "is_strike"]
    col = {name: i for i, name in enumerate(columns)}
    cal = w.calendar[0]
    assert cal[col["is_holiday"]] == 1  # férié connu à l'avance
    assert cal[col["is_strike"]] == 0  # grève publiée trop tard : invisible
    # température heure par heure : 10 + h, divisée par 10, dans l'ordre des sorties
    temps = [cal[col[f"temp_prev_h{h:02d}"]] for h in range(1, 25)]
    assert temps == pytest.approx([(10.0 + h) / 10 for h in range(24)])


def test_compteur_absent_refuse():
    with pytest.raises(ValueError, match="absents"):
        N.build_windows(_counts(), _origins(counter="Z-9"), use_context=False)


# --- Sauvegarde et chargement du réseau ---------------------------------------------------


def _net(use_context=False, seed=0) -> N.MLPNet:
    torch.manual_seed(seed)
    n_inputs = 2 * N.WINDOW_HOURS + len(N.calendar_columns(use_context))
    return N.MLPNet(n_inputs, hidden=16, layers=2, dropout=0.2)


def _same_outputs(a: N.MLPNet, b: N.MLPNet) -> bool:
    x = torch.randn(5, a.arch["n_inputs"])
    a.eval()
    with torch.no_grad():
        return torch.equal(a(x), b(x))


def test_forme_du_reseau():
    net = _net(use_context=True)
    assert net.arch["n_inputs"] == 419
    assert net(torch.zeros(3, 419)).shape == (3, 24)


def test_aller_retour_meme_prevision(tmp_path):
    net = _net()
    N.save_mlp(net, tmp_path / "weights.pt", use_context=False)
    back = N.load_mlp(tmp_path / "weights.pt")
    assert back.arch == net.arch
    assert not back.training  # rechargé en mode évaluation (dropout coupé)
    assert _same_outputs(net, back)


def test_aller_retour_par_train_save_model(tmp_path):
    net = _net(use_context=True)
    config = train.TrainConfig(
        method="mlp",
        fit_cutoff=pd.Timestamp("2026-06-30 22:00", tz="UTC"),
        hyperparameters={"hidden": 16, "layers": 2, "dropout": 0.2},
    )
    model = train.TrainedModel(
        model_run_id=train.make_model_run_id(config),
        config=config,
        estimator=net,
        donor_site_groups=["G-A"],
        label_interval=(pd.Timestamp("2023-11-14 23:00", tz="UTC"), config.fit_cutoff),
        train_seconds=1.0,
    )
    out = train.save_model(model, tmp_path)
    assert (out / "weights.pt").exists()
    back = train.load_model(model.model_run_id, tmp_path)
    assert back.minimum_history_hours is None or back.minimum_history_hours == 192
    assert _same_outputs(net, back.estimator)


def test_refus_entrees_rangees_autrement(tmp_path):
    path = tmp_path / "weights.pt"
    N.save_mlp(_net(), path, use_context=False)
    saved = torch.load(path, weights_only=True)
    saved["layout"]["window_hours"] = 336  # réseau appris sur deux semaines
    torch.save(saved, path)
    with pytest.raises(ValueError, match="réentraîner"):
        N.load_mlp(path)


class _Piege:
    """Objet Python arbitraire : un fichier piégé pourrait exécuter du code au chargement."""


def test_chargement_refuse_le_code(tmp_path):
    path = tmp_path / "weights.pt"
    torch.save({"format": 1, "objet": _Piege()}, path)
    with pytest.raises(pickle.UnpicklingError):
        N.load_mlp(path)


def test_mlp_declare_et_entrainable():
    # MOD-008 : ce test vérifiait jusqu'ici que le MLP ne savait pas encore apprendre
    # (fit=None). L'apprentissage est branché ; il est testé dans test_known_neural_fit.py.
    assert train.get_backend("mlp").weights_file == "weights.pt"
    assert train.get_backend("mlp").minimum_history_hours == 192
    assert train.get_backend("mlp").fit is N.fit_mlp

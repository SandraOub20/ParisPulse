"""EXP-E2-05 : seuil d'heures mesurées et masquage des fenêtres à l'apprentissage (synthétique)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.known import features as F
from src.models.known import neural as N
from src.models.known import predict as P
from src.models.known import train
from src.models.schemas import Case

PARIS = "Europe/Paris"
LAG = 24
CUTOFF = pd.Timestamp("2026-07-01 00:00", tz=PARIS).tz_convert("UTC")
START = pd.Timestamp("2026-04-06 00:00", tz=PARIS).tz_convert("UTC")
END = pd.Timestamp("2026-07-20 00:00", tz=PARIS).tz_convert("UTC")
LEVELS = {"A-1": 100.0, "A-2": 20.0, "A-3": 300.0}
FAST = {"hidden": 16, "layers": 1, "lr": 3e-3, "batch_size": 64, "max_epochs": 6, "patience": 6}


def _counts() -> pd.DataFrame:
    hours = pd.date_range(START, END, freq="h", inclusive="left")
    local = hours.tz_convert(PARIS)
    hour = local.hour.to_numpy(dtype=float)
    weekday = local.dayofweek.to_numpy() < 5
    commute = np.exp(-(((hour - 8) / 1.5) ** 2)) + np.exp(-(((hour - 18) / 1.8) ** 2))
    profile = np.where(weekday, 0.15 + 1.6 * commute, 0.2 + 0.9 * np.exp(-(((hour - 15) / 3) ** 2)))
    frames = []
    for counter_id, level in LEVELS.items():
        value = np.round(level * profile, 1)
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


def _origins(counts: pd.DataFrame) -> pd.DataFrame:
    return F.training_origins(counts, sorted(LEVELS), CUTOFF, publication_lag_hours=LAG)


def _config(seed: int = 0, **hp) -> train.TrainConfig:
    return train.TrainConfig(
        method="mlp",
        fit_cutoff=CUTOFF,
        use_context=False,
        hyperparameters=N.mlp_hyperparameters(**{**FAST, **hp}),
        seed=seed,
    )


def _fit(counts: pd.DataFrame, seed: int = 0, **hp) -> N.MLPNet:
    return N.fit_mlp(_config(seed, **hp), counts, None, _origins(counts))


def _same_weights(a: N.MLPNet, b: N.MLPNet) -> bool:
    left, right = a.state_dict(), b.state_dict()
    return left.keys() == right.keys() and all(torch.equal(left[k], right[k]) for k in left)


@pytest.fixture(scope="module")
def counts() -> pd.DataFrame:
    return _counts()


@pytest.fixture(scope="module")
def windows(counts) -> N.Windows:
    return N.build_windows(counts, _origins(counts), None, use_context=False)


# --- réglages ----------------------------------------------------------------------------


def test_reglages_neutres_par_defaut():
    hp = N.mlp_hyperparameters()
    assert hp["min_observed_hours"] == 84 and hp["mask_prob"] == 0.0
    assert (hp["mask_min_hours"], hp["mask_max_hours"]) == (24, 144)


@pytest.mark.parametrize(
    "bad",
    [
        {"mask_prob": 1.0},
        {"mask_prob": -0.1},
        {"mask_min_hours": 100, "mask_max_hours": 50},
        {"mask_max_hours": 200},
        {"min_observed_hours": 0},
        {"min_observed_hours": 169},
    ],
)
def test_reglages_de_masquage_invalides_refuses(bad):
    with pytest.raises(ValueError):
        N.mlp_hyperparameters(**bad)


# --- mask_windows ------------------------------------------------------------------------


def test_masquage_efface_un_bloc_sans_inventer_de_zero_et_garde_les_cibles(windows):
    rows = np.arange(len(windows))
    out = N.mask_windows(
        windows, rows, np.random.default_rng(0), prob=1.0, min_hours=24, max_hours=144
    )
    changed = (out.mask != windows.mask).any(axis=1)
    assert changed.any()
    lost = (windows.mask == 1) & (out.mask == 0)
    # un seul bloc continu effacé par ligne, de 24 à 144 h
    for r in np.flatnonzero(changed)[:50]:
        idx = np.flatnonzero(lost[r])
        assert 1 <= idx.size <= 144 and np.all(np.diff(idx) == 1)
    # heures effacées : masque 0 et série 0 ; jamais une heure « mesurée » ajoutée
    assert (out.series[out.mask == 0] == 0).all()
    assert not ((windows.mask == 0) & (out.mask == 1)).any()
    # cibles réelles (vélos/h) et leur masque inchangés
    before = windows.target * windows.scale[:, None]
    after = out.target * out.scale[:, None]
    np.testing.assert_allclose(after, before, rtol=1e-4, atol=1e-3)
    assert (out.target_mask == windows.target_mask).all()
    # niveau recalculé = moyenne des heures restantes
    r = np.flatnonzero(changed)[0]
    kept = out.mask[r] == 1
    raw = windows.series[r] * windows.scale[r]
    assert out.scale[r] == pytest.approx(raw[kept].mean(), rel=1e-4)


def test_masquage_ne_touche_que_les_lignes_donnees_et_pas_l_original(windows):
    rows = np.arange(0, len(windows), 2)
    copy = windows.mask.copy()
    out = N.mask_windows(
        windows, rows, np.random.default_rng(1), prob=1.0, min_hours=24, max_hours=144
    )
    others = np.setdiff1d(np.arange(len(windows)), rows)
    assert (out.mask[others] == windows.mask[others]).all()
    assert (windows.mask == copy).all()  # windows n'est pas modifié


def test_meme_graine_memes_masques(counts):
    # configuration de B : seuil 24 h, donc un bloc de 144 h laisse assez d'heures
    windows = N.build_windows(
        counts, _origins(counts), None, use_context=False, min_observed_hours=24
    )
    rows = np.arange(len(windows))
    kwargs = dict(prob=0.25, min_hours=24, max_hours=144)
    a = N.mask_windows(windows, rows, np.random.default_rng(7), **kwargs)
    b = N.mask_windows(windows, rows, np.random.default_rng(7), **kwargs)
    c = N.mask_windows(windows, rows, np.random.default_rng(8), **kwargs)
    assert (a.mask == b.mask).all()
    assert not (a.mask == c.mask).all()
    share = (a.mask != windows.mask).any(axis=1).mean()
    assert 0.15 < share < 0.35  # environ prob


def test_seuil_84_limite_le_masquage_aux_blocs_courts(windows):
    """Avec le seuil de 84 h, un bloc de plus de 84 h rendrait la ligne inutilisable :
    elle n'est pas masquée. D'où min_observed_hours=24 pour B (EXP-E2-05)."""
    rows = np.arange(len(windows))
    out = N.mask_windows(
        windows, rows, np.random.default_rng(0), prob=1.0, min_hours=24, max_hours=144
    )
    lost = ((windows.mask == 1) & (out.mask == 0)).sum(axis=1)
    assert lost.max() <= 168 - 84
    share = (lost > 0).mean()
    assert 0.3 < share < 0.7  # environ la moitié des blocs (<= 84 h) passent


def test_ligne_qui_deviendrait_inutilisable_non_masquee(counts):
    strict = N.build_windows(
        counts, _origins(counts), None, use_context=False, min_observed_hours=160
    )
    rows = np.flatnonzero(strict.usable)
    out = N.mask_windows(
        strict, rows, np.random.default_rng(0), prob=1.0, min_hours=24, max_hours=144
    )
    assert (out.mask == strict.mask).all()  # 168 - 24 < 160 : aucune ligne masquée


# --- fit_mlp -----------------------------------------------------------------------------


def test_sans_masquage_poids_identiques_quels_que_soient_les_reglages_du_bloc(counts):
    a = _fit(counts)
    b = _fit(counts, mask_min_hours=48, mask_max_hours=100)  # ignorés si mask_prob = 0
    assert _same_weights(a, b)
    assert "masking" not in a.training_report


def test_masquage_seulement_sur_l_apprentissage_jamais_sur_le_holdout(counts, monkeypatch):
    seen = []
    original = N.mask_windows

    def spy(windows, rows, rng, **kw):
        seen.append(np.asarray(rows).copy())
        return original(windows, rows, rng, **kw)

    monkeypatch.setattr(N, "mask_windows", spy)
    net = _fit(counts, mask_prob=0.25, min_observed_hours=24)  # configuration de B
    windows = N.build_windows(counts, _origins(counts), None, use_context=False)
    holdout_start = N._holdout_start(CUTOFF, N.mlp_hyperparameters()["holdout_weeks"])
    hold_rows = np.flatnonzero(np.asarray(windows.origin >= holdout_start))
    assert len(seen) == net.training_report["epochs_run"]  # un tirage par époque
    assert all(np.intersect1d(rows, hold_rows).size == 0 for rows in seen)
    masking = net.training_report["masking"]
    assert 0.15 < masking["masked_share_mean"] < 0.35


def test_masquage_meme_graine_memes_poids(counts):
    a = _fit(counts, mask_prob=0.25)
    b = _fit(counts, mask_prob=0.25)
    c = _fit(counts, mask_prob=0.25, seed=1)
    assert _same_weights(a, b) and not _same_weights(a, c)


# --- seuil en prévision ------------------------------------------------------------------


def _short_inputs(counts: pd.DataFrame, visible_hours: int):
    """Cas du 08/07 où seules les visible_hours dernières heures publiées existent."""
    origin = pd.Timestamp("2026-07-08 00:00", tz=PARIS).tz_convert("UTC")
    cutoff = origin - pd.Timedelta(hours=LAG)
    history = counts.loc[counts["counter_id"] == "A-1"]
    history = history.loc[history["timestamp"] >= cutoff - pd.Timedelta(hours=visible_hours)]
    case = Case(
        case_id="T|A-1|short",
        counter_id="A-1",
        site_group_id=None,
        origin=origin,
        scenario="known_site",
        protocol_id="test",
        snapshot_id="synthetic",
    )
    return P.build_inputs(case, history, None, publication_lag_hours=LAG)


def test_seuil_84_refuse_24_h_et_seuil_24_les_sert(counts):
    net = _fit(counts)  # réseau d'avant : seuil appris 84 h
    inputs = _short_inputs(counts, 30)
    refused = N.predict_mlp(net, inputs)
    assert refused.reason == N.REFUSE_SPARSE
    served = N.predict_mlp(net, inputs, min_observed_hours=24)  # bras A′
    assert served.ok and served.values.shape == (24,) and (served.values >= 0).all()


def test_seuil_appris_relu_dans_le_bilan(counts):
    net = _fit(counts, min_observed_hours=24)
    assert N._min_observed_of(net) == 24
    assert N.predict_mlp(net, _short_inputs(counts, 30)).ok
    old = _fit(counts)
    old.training_report["hyperparameters"].pop("min_observed_hours")  # réseau d'avant
    assert N._min_observed_of(old) == 84


def test_seuil_84_redonne_les_previsions_actuelles(counts):
    net = _fit(counts)
    inputs = _short_inputs(counts, 168)
    a = N.predict_mlp(net, inputs)
    b = N.predict_mlp(net, inputs, min_observed_hours=84)
    assert a.ok and np.array_equal(a.values, b.values)

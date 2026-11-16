"""Tests E1 du traitement des longues suites de zéros (EXP-E1-04), sur données synthétiques.

Les données synthétiques vérifient le code ; elles ne mesurent rien sur Paris.
"""

import numpy as np
import pandas as pd
import pytest

from src.data import zeros
from src.data import zeros_experiment as ze

START = pd.Timestamp("2026-01-05T00:00:00+00:00")  # lundi
LAG = 24


def frame(cid: str, values, start: pd.Timestamp = START) -> pd.DataFrame:
    """Format de quality.load_counts ; NaN = heure absente (non observée)."""
    values = np.asarray(values, dtype=float)
    ts = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    observed = ~np.isnan(values)
    return pd.DataFrame(
        {
            "counter_id": cid,
            "ts": ts,
            "count": values,
            "is_observed": observed,
            "is_scoreable": observed,
        }
    )


def with_zeros(n_before: int, n_zero: int, n_after: int, level: float = 10.0) -> np.ndarray:
    return np.r_[np.full(n_before, level), np.zeros(n_zero), np.full(n_after, level)]


def far_cutoff(df: pd.DataFrame) -> pd.Timestamp:
    """Coupure après toutes les heures, délai compris."""
    return df["ts"].max() + pd.Timedelta(hours=1 + LAG)


# ----------------------------------------------------------------- détection (traitement B)
def test_suite_de_24_h_ecartee_mais_pas_23_h():
    df = pd.concat(
        [frame("c24", with_zeros(10, 24, 10)), frame("c23", with_zeros(10, 23, 10))],
        ignore_index=True,
    )
    m = zeros.long_zero_mask(df, far_cutoff(df), LAG)
    assert m[df["counter_id"] == "c24"].sum() == 24
    assert m[df["counter_id"] == "c23"].sum() == 0


def test_heure_absente_coupe_la_suite():
    values = with_zeros(5, 30, 5)
    values[5 + 15] = np.nan  # 15 zéros, une absence, 14 zéros : aucune suite de 24 h
    df = frame("c", values)
    assert zeros.long_zero_mask(df, far_cutoff(df), LAG).sum() == 0


def test_ligne_manquante_dans_la_grille_coupe_la_suite():
    df = frame("c", with_zeros(5, 30, 5))
    df = df.drop(index=5 + 15).reset_index(drop=True)  # heure supprimée, pas seulement vide
    assert zeros.long_zero_mask(df, far_cutoff(df), LAG).sum() == 0


def test_aucune_fuite_modifier_le_futur_ne_change_rien():
    df = frame("c", with_zeros(48, 40, 200))
    cutoff = START + pd.Timedelta(hours=150)
    before = zeros.long_zero_mask(df, cutoff, LAG)
    futur = df["ts"] + pd.Timedelta(hours=1 + LAG) > cutoff
    changed = df.copy()
    changed.loc[futur, "count"] = 0.0  # le futur devient une longue suite de zéros
    after = zeros.long_zero_mask(changed, cutoff, LAG)
    pd.testing.assert_series_equal(before, after)
    assert not after[futur].any()


def test_delai_de_publication_respecte():
    # 30 zéros juste avant la coupure : seules les heures publiées à la coupure comptent
    df = frame("c", with_zeros(48, 30, 0))
    cutoff = df["ts"].max() + pd.Timedelta(hours=1)  # fin de la dernière heure
    assert zeros.long_zero_mask(df, cutoff, 0).sum() == 30
    assert zeros.long_zero_mask(df, cutoff, LAG).sum() == 0  # 6 zéros publiés seulement
    assert zeros.long_zero_mask(df, cutoff + pd.Timedelta(hours=18), LAG).sum() == 24


def test_traitements_A_et_B_et_count_intact():
    df = frame("c", with_zeros(30, 26, 30))
    original = df.copy()
    cutoff = far_cutoff(df)
    a = zeros.training_mask(df, cutoff, "keep", LAG)
    b = zeros.training_mask(df, cutoff, "drop", LAG)
    assert a.sum() == len(df)
    assert b.sum() == len(df) - 26
    assert (b <= a).all()  # B ne fait que retirer
    pd.testing.assert_frame_equal(df, original)  # count jamais modifié
    with pytest.raises(ValueError):
        zeros.training_mask(df, cutoff, "autre", LAG)


def test_resume_par_compteur():
    df = frame("c", with_zeros(10, 25, 10, level=5.0))
    s = zeros.excluded_summary(df, far_cutoff(df), LAG)
    assert s.iloc[0]["n_runs"] == 1 and s.iloc[0]["n_hours_dropped"] == 25


# ----------------------------------------------------------------- comparaison
def test_cas_de_24_heures_au_passage_a_l_heure_d_hiver():
    cases = ze.expected_cases(["c"], "2026-10-25", "2026-10-26")
    counts = frame("c", np.ones(60), start=pd.Timestamp("2026-10-24T00:00:00+00:00"))
    t = ze.case_targets(cases, counts)
    assert len(t) == 24 and t["ts"].is_unique
    assert t["ts"].iloc[0] == pd.Timestamp("2026-10-24T22:00:00+00:00")  # minuit à Paris
    assert (t["ts"].diff().dropna() == pd.Timedelta(hours=1)).all()


def test_meme_masque_et_intersection_des_cas_complets():
    cases = ze.expected_cases(["c"], "2026-01-06", "2026-01-08")  # 2 cas
    counts = frame("c", np.full(24 * 5, 10.0))
    counts.loc[counts.index[30], ["count", "is_scoreable"]] = [np.nan, False]
    t = ze.case_targets(cases, counts)
    pa = t[["case_id", "counter_id", "horizon"]].assign(y_pred=12.0)
    pb = pa.assign(y_pred=11.0)
    pb.loc[pb.index[-1], "y_pred"] = np.nan  # B incomplet sur le 2e cas
    groups = {"c": "concerned"}
    days = pd.Series({"c": 40})
    res = ze.compare(t, pa, pb, groups, days, days)
    assert res["n_complete_a"] == 2 and res["n_complete_b"] == 1
    assert res["n_compared_cases"] == 1  # le cas incomplet sort pour A ET B
    assert (
        res["n_compared_hours"]
        == 24 - t[t["case_id"] == t["case_id"].iloc[0]]["is_scoreable"].eq(False).sum()
    )
    g = res["groups"]["concerned"]
    assert g["mae_macro_a"] == pytest.approx(2.0) and g["mae_macro_b"] == pytest.approx(1.0)


def test_un_zero_observe_reste_une_cible_evaluable():
    cases = ze.expected_cases(["c"], "2026-01-06", "2026-01-07")
    values = np.full(24 * 3, 10.0)
    values[23 + 3] = 0.0  # zéro observé dans la journée cible (origine = 05/01 23:00 UTC)
    t = ze.case_targets(cases, frame("c", values))
    assert (t["y_true"] == 0).sum() == 1  # le zéro est bien une cible
    assert t.loc[t["y_true"] == 0, "is_scoreable"].all()
    pa = t[["case_id", "counter_id", "horizon"]].assign(y_pred=10.0)
    res = ze.compare(t, pa, pa, {"c": "concerned"}, pd.Series({"c": 40}), pd.Series({"c": 40}))
    assert res["groups"]["concerned"]["mae_zero_targets_a"] == pytest.approx(10.0)


def test_B_ne_retire_que_des_cibles_les_entrees_restent_identiques():
    df = pd.concat(
        [frame("z", with_zeros(48, 30, 48)), frame("t", np.full(126, 7.0))], ignore_index=True
    )
    cutoff = far_cutoff(df)
    a = ze.training_frame(df, {"z", "t"}, cutoff, "keep", LAG)
    b = ze.training_frame(df, {"z", "t"}, cutoff, "drop", LAG)
    cols = ["counter_id", "ts", "count"]
    pd.testing.assert_frame_equal(a[cols], b[cols])  # même historique transmis au modèle
    assert a["is_target"].sum() - b["is_target"].sum() == 30
    assert (b.loc[~b["is_target"], "counter_id"] == "z").all()


def test_cas_sans_observation_compte_et_compteur_sans_mae():
    cases = ze.expected_cases(["c", "s"], "2026-01-06", "2026-01-08")
    stopped = np.full(24 * 5, np.nan)
    stopped[:10] = 5.0  # compteur arrêté avant les heures cibles
    counts = pd.concat([frame("c", np.full(24 * 5, 10.0)), frame("s", stopped)], ignore_index=True)
    t = ze.case_targets(cases, counts)
    p = t[["case_id", "counter_id", "horizon"]].assign(y_pred=10.0)
    days = pd.Series({"c": 40, "s": 40})
    res = ze.compare(t, p, p, {"c": "control", "s": "other_robustness"}, days, days)
    assert res["n_compared_cases"] == 4  # les cas sans mesure ne disparaissent pas
    assert res["n_compared_cases_without_observation"] == 2
    g = res["groups"]["other_robustness"]
    assert g["n_counters"] == 1 and g["n_evaluable_counters"] == 0
    assert np.isnan(g["mae_macro_a"])  # pas de MAE, et surtout pas une MAE de zéro
    assert ze.decide(res)[1].startswith("règle non applicable")  # aucun compteur concerné


def test_regle_de_decision():
    def result(a_c, b_c, a_t, b_t, ua=10, ub=10):
        return {
            "groups": {
                "concerned": {"mae_macro_a": a_c, "mae_macro_b": b_c},
                "control": {"mae_macro_a": a_t, "mae_macro_b": b_t},
            },
            "usable_counters_a": ua,
            "usable_counters_b": ub,
        }

    assert ze.decide(result(10, 9, 10, 10))[0].startswith("B")  # -10 %, témoins stables
    assert ze.decide(result(10, 9.8, 10, 10))[0].startswith("A")  # -2 % seulement
    assert ze.decide(result(10, 9, 10, 10.2))[0].startswith("A")  # témoins +2 %
    assert ze.decide(result(10, 9, 10, 10, ub=9))[0].startswith("A")  # compteur perdu


def test_experience_complete_sur_reseau_synthetique():
    n = 24 * 70
    rng = np.random.default_rng(0)
    base = rng.poisson(20, n).astype(float)
    concerned = base.copy()
    concerned[24 * 10 : 24 * 20] = 0.0  # 10 jours de zéros dans l'apprentissage
    counts = pd.concat(
        [frame("z", concerned), frame("t", base), frame("r", base)], ignore_index=True
    )
    inventory = pd.DataFrame(
        {
            "counter_id": ["z", "t", "r", "e"],
            "period_role": "selection",
            "site_role": ["S_train", "S_train", "S_train", "S_test_new"],
            "selection_status": ["robustness", "retained", "robustness", "reserved_test_new"],
        }
    )
    cutoff = zeros.local_midnight("2026-02-20")
    res = ze.run_experiment(
        counts, inventory, ze.ProfileModel, cutoff, "2026-02-21", "2026-03-01", LAG
    )
    assert res["n_expected_cases"] == 3 * 8  # le site réservé à E3 n'entre pas
    assert res["groups"]["concerned"]["n_counters"] == 1
    assert res["groups"]["control"]["n_counters"] == 1
    assert res["groups"]["other_robustness"]["n_counters"] == 1
    assert res["n_compared_cases"] == res["n_expected_cases"]


def test_sensibilite_au_seuil_memes_groupes_moins_d_heures_retirees():
    n = 24 * 70
    base = np.random.default_rng(1).poisson(20, n).astype(float)
    z = base.copy()
    z[24 * 5 : 24 * 5 + 30] = 0.0  # suite de 30 h : retirée à 24 h, gardée à 48 h
    z[24 * 15 : 24 * 15 + 80] = 0.0  # suite de 80 h : retirée à 24, 48 et 72 h
    counts = pd.concat([frame("z", z), frame("t", base)], ignore_index=True)
    inventory = pd.DataFrame(
        {
            "counter_id": ["z", "t"],
            "period_role": "selection",
            "site_role": "S_train",
            "selection_status": ["robustness", "retained"],
        }
    )
    cutoff = zeros.local_midnight("2026-02-20")
    dropped = {}
    for seuil in (24, 48, 72):
        b = ze.training_frame(counts, {"z", "t"}, cutoff, "drop", LAG, seuil)
        dropped[seuil] = int((~b["is_target"]).sum())
        res = ze.run_experiment(
            counts, inventory, ze.ProfileModel, cutoff, "2026-02-21", "2026-02-24", LAG, seuil
        )
        assert res["groups"]["concerned"]["n_counters"] == 1  # groupes fixés à 24 h
        assert res["min_run_hours"] == seuil
    assert dropped == {24: 110, 48: 80, 72: 80}


def test_historique_a_l_origine_publie_seulement_et_identique_pour_A_et_B():
    df = frame("z", with_zeros(48, 30, 200))
    hist = ze.with_availability(df, LAG)
    origin = START + pd.Timedelta(hours=150)
    seen = ze.history_at(hist, origin)
    assert (seen["ts"] + pd.Timedelta(hours=1 + LAG) <= origin).all()  # rien de non publié
    assert len(seen) == 150 - LAG  # les 24 dernières heures ne sont pas encore publiées

    class Spy:
        def __init__(self):
            self.history = None

        def fit(self, train):
            pass

        def predict(self, targets, history):
            self.history = history
            return np.ones(len(targets))

    cases = ze.expected_cases(["z"], "2026-01-10", "2026-01-11")
    t = ze.case_targets(cases, df)
    cutoff = START + pd.Timedelta(hours=100)
    spies = {}
    for treatment in ("keep", "drop"):
        spies[treatment] = Spy()
        ze.run_variant(spies[treatment], df, {"z"}, t, cutoff, treatment, LAG)
    pd.testing.assert_frame_equal(spies["keep"].history, spies["drop"].history)
    assert (spies["keep"].history["count"] == 0).sum() == 30  # les zéros restent des entrées

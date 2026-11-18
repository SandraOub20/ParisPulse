"""Tests E1 du traitement des longues suites de zéros (EXP-E1-04), sur données synthétiques.

Les données synthétiques vérifient le code ; elles ne mesurent rien sur Paris.
A = garder les zéros ; C = remplacer les suites longues par l'année d'avant.
"""

import numpy as np
import pandas as pd
import pytest

from src.data import zeros
from src.data import zeros_experiment as ze

START = pd.Timestamp("2026-01-05T00:00:00+00:00")  # lundi
LAG = 24
YEAR_START = pd.Timestamp("2025-03-01T00:00:00+00:00")
YEAR_END = pd.Timestamp("2026-04-30T23:00:00+00:00")


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


def frame_years(cid: str, runs=(("2026-03-10", 30),), level: float = 10.0, override=None):
    """Quatorze mois d'heures (01/03/2025 - 30/04/2026) : l'année d'avant d'une suite de
    mars 2026 est dans l'instantané. `runs` : (début UTC, heures de zéros)."""
    ts = pd.date_range(YEAR_START, YEAR_END, freq="h")
    values = pd.Series(level, index=ts)
    for start, hours in runs:
        first = pd.Timestamp(start, tz="UTC")
        values[first : first + pd.Timedelta(hours=hours - 1)] = 0.0
    for t, v in (override or {}).items():
        values[pd.Timestamp(t, tz="UTC")] = v
    return frame(cid, values.to_numpy(), start=YEAR_START)


def with_zeros(n_before: int, n_zero: int, n_after: int, level: float = 10.0) -> np.ndarray:
    return np.r_[np.full(n_before, level), np.zeros(n_zero), np.full(n_after, level)]


def far_cutoff(df: pd.DataFrame) -> pd.Timestamp:
    """Coupure après toutes les heures, délai compris."""
    return df["ts"].max() + pd.Timedelta(hours=1 + LAG)


# ----------------------------------------------------------------- détection des suites
def test_suite_de_24_h_detectee_mais_pas_23_h():
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


def test_aucune_fuite_pour_C_modifier_le_futur_ne_change_rien():
    df = frame_years("c")
    cutoff = pd.Timestamp("2026-03-20T00:00:00+00:00")
    before = zeros.year_before_values(df, cutoff, LAG)
    futur = df["ts"] + pd.Timedelta(hours=1 + LAG) > cutoff
    changed = df.copy()
    changed.loc[futur, "count"] = 0.0
    after = zeros.year_before_values(changed, cutoff, LAG)
    pd.testing.assert_series_equal(before, after)
    assert before.notna().sum() == 30 and not after[futur].notna().any()


def test_delai_de_publication_respecte():
    # 30 zéros juste avant la coupure : seules les heures publiées à la coupure comptent
    df = frame("c", with_zeros(48, 30, 0))
    cutoff = df["ts"].max() + pd.Timedelta(hours=1)  # fin de la dernière heure
    assert zeros.long_zero_mask(df, cutoff, 0).sum() == 30
    assert zeros.long_zero_mask(df, cutoff, LAG).sum() == 0  # 6 zéros publiés seulement
    assert zeros.long_zero_mask(df, cutoff + pd.Timedelta(hours=18), LAG).sum() == 24


# ----------------------------------------------------------------- traitements A et C
def test_traitements_A_et_C_et_counts_intact():
    # un an avant : un 0 à 05:00 et une case vide à 06:00 -> le 0 est gardé
    df = frame_years("c", override={"2025-03-10 05:00": 0.0, "2025-03-10 06:00": np.nan})
    original = df.copy()
    cutoff = far_cutoff(df)
    a = zeros.treated_counts(df, cutoff, "keep", LAG)
    c = zeros.treated_counts(df, cutoff, "year", LAG)
    pd.testing.assert_frame_equal(a, original)  # A ne change rien
    run = c.set_index("ts").loc["2026-03-10 00:00":"2026-03-11 05:00"]  # les 30 h
    assert (run["count"] == 10.0).sum() == 28
    assert run.loc["2026-03-10 05:00", "count"] == 0 and run.loc["2026-03-10 06:00", "count"] == 0
    assert not run.loc[run["count"] > 0, "is_scoreable"].any()  # valeurs remplacées : pas cibles
    assert run.loc[run["count"] == 0, "is_scoreable"].all()  # zéros gardés : restent cibles
    mask_a = zeros.training_mask(df, cutoff, "keep", LAG)
    mask_c = zeros.training_mask(df, cutoff, "year", LAG)
    assert mask_a.sum() - mask_c.sum() == 28 and (mask_c <= mask_a).all()
    pd.testing.assert_frame_equal(df, original)  # counts.csv (ici df) jamais modifié
    with pytest.raises(ValueError):
        zeros.treated_counts(df, cutoff, "autre", LAG)


def test_C_sans_annee_d_avant_ne_change_rien():
    df = frame("c", with_zeros(30, 26, 30))  # quatre jours : pas d'année d'avant
    cutoff = far_cutoff(df)
    pd.testing.assert_frame_equal(
        zeros.treated_counts(df, cutoff, "year", LAG), zeros.treated_counts(df, cutoff, "keep", LAG)
    )


def test_resume_par_compteur():
    df = frame("c", with_zeros(10, 25, 10, level=5.0))
    s = zeros.treated_summary(df, far_cutoff(df), LAG)
    assert s.iloc[0]["n_runs"] == 1 and s.iloc[0]["n_hours_in_runs"] == 25
    assert s.iloc[0]["n_hours_replaced_c"] == 0  # pas d'année d'avant
    s = zeros.treated_summary(frame_years("c"), far_cutoff(frame_years("c")), LAG)
    assert s.iloc[0]["n_hours_in_runs"] == 30 and s.iloc[0]["n_hours_replaced_c"] == 30


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
    pc = pa.assign(y_pred=11.0)
    pc.loc[pc.index[-1], "y_pred"] = np.nan  # C incomplet sur le 2e cas
    groups = {"c": "concerned"}
    days = pd.Series({"c": 40})
    res = ze.compare(t, pa, pc, groups, days, days)
    assert res["n_complete_a"] == 2 and res["n_complete_c"] == 1
    assert res["n_compared_cases"] == 1  # le cas incomplet sort pour A ET C
    assert (
        res["n_compared_hours"]
        == 24 - t[t["case_id"] == t["case_id"].iloc[0]]["is_scoreable"].eq(False).sum()
    )
    g = res["groups"]["concerned"]
    assert g["mae_macro_a"] == pytest.approx(2.0) and g["mae_macro_c"] == pytest.approx(1.0)


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


def test_C_remplace_les_entrees_et_les_retire_des_cibles():
    df = pd.concat([frame_years("z"), frame_years("t", runs=())], ignore_index=True)
    cutoff = far_cutoff(df)
    a = ze.training_frame(zeros.treated_counts(df, cutoff, "keep", LAG), {"z", "t"}, cutoff, LAG)
    c = ze.training_frame(zeros.treated_counts(df, cutoff, "year", LAG), {"z", "t"}, cutoff, LAG)
    pd.testing.assert_frame_equal(a[["counter_id", "ts"]], c[["counter_id", "ts"]])  # mêmes heures
    diff = a["count"].ne(c["count"])
    assert diff.sum() == 30 and (a.loc[diff, "counter_id"] == "z").all()
    assert (a.loc[diff, "count"] == 0).all() and (c.loc[diff, "count"] == 10.0).all()
    assert a["is_target"].sum() - c["is_target"].sum() == 30
    assert not c.loc[diff, "is_target"].any()


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
    def result(a_c, c_c, a_t, c_t, ua=10, uc=10):
        return {
            "groups": {
                "concerned": {"mae_macro_a": a_c, "mae_macro_c": c_c},
                "control": {"mae_macro_a": a_t, "mae_macro_c": c_t},
            },
            "usable_counters_a": ua,
            "usable_counters_c": uc,
        }

    assert ze.decide(result(10, 9, 10, 10))[0].startswith("C")  # -10 %, témoins stables
    assert ze.decide(result(10, 9.8, 10, 10))[0].startswith("A")  # -2 % seulement
    assert ze.decide(result(10, 9, 10, 10.2))[0].startswith("A")  # témoins +2 %
    assert ze.decide(result(10, 9, 10, 10, uc=9))[0].startswith("A")  # compteur perdu


def test_analyse_sans_un_compteur_concerne():
    per_counter = pd.DataFrame(
        {
            "counter_id": ["j", "c1", "c2", "t"],
            "group": ["concerned", "concerned", "concerned", "control"],
            "mae_a": [100.0, 10.0, 20.0, 5.0],
            "mae_c": [40.0, 12.0, 18.0, 5.0],
        }
    )
    res = {"per_counter": per_counter}
    tous = ze.concerned_without(res, set())
    assert tous["n_evaluable_counters"] == 3
    assert tous["mae_macro_a"] == pytest.approx(130 / 3)
    sans = ze.concerned_without(res, {"j"})  # l'effet venait surtout de "j"
    assert sans["n_evaluable_counters"] == 2  # le témoin "t" n'entre jamais
    assert sans["mae_macro_a"] == pytest.approx(15.0)
    assert sans["mae_macro_c"] == pytest.approx(15.0)
    assert sans["variation"] == pytest.approx(0.0)
    assert sans["n_improved"] == 1 and sans["n_degraded"] == 1
    vide = ze.concerned_without(res, {"j", "c1", "c2"})
    assert vide["n_evaluable_counters"] == 0 and np.isnan(vide["variation"])  # jamais zéro


def test_experience_complete_sur_reseau_synthetique():
    counts = pd.concat(
        [
            frame_years("z", runs=(("2026-03-01", 240),)),
            frame_years("t", runs=()),
            frame_years("r", runs=()),
        ],
        ignore_index=True,
    )
    inventory = pd.DataFrame(
        {
            "counter_id": ["z", "t", "r", "e"],
            "period_role": "selection",
            "site_role": ["S_train", "S_train", "S_train", "S_test_new"],
            "selection_status": ["robustness", "retained", "robustness", "reserved_test_new"],
        }
    )
    cutoff = zeros.local_midnight("2026-04-01")
    res = ze.run_experiment(
        counts, inventory, ze.ProfileModel, cutoff, "2026-04-02", "2026-04-10", LAG
    )
    assert res["n_expected_cases"] == 3 * 8  # le site réservé à E3 n'entre pas
    assert res["groups"]["concerned"]["n_counters"] == 1
    assert res["groups"]["control"]["n_counters"] == 1
    assert res["groups"]["other_robustness"]["n_counters"] == 1
    assert res["n_compared_cases"] == res["n_expected_cases"]
    assert res["n_hours_replaced_c"] == 240  # 10 jours remplacés par l'année d'avant


def test_sensibilite_au_seuil_memes_groupes_moins_d_heures_remplacees():
    # suite de 30 h : remplacée à 24 h, gardée à 48 h ; suite de 80 h : remplacée partout
    z = frame_years("z", runs=(("2026-03-05", 30), ("2026-03-15", 80)))
    counts = pd.concat([z, frame_years("t", runs=())], ignore_index=True)
    inventory = pd.DataFrame(
        {
            "counter_id": ["z", "t"],
            "period_role": "selection",
            "site_role": "S_train",
            "selection_status": ["robustness", "retained"],
        }
    )
    cutoff = zeros.local_midnight("2026-04-01")
    replaced = {}
    for seuil in (24, 48, 72):
        replaced[seuil] = int(zeros.year_before_values(counts, cutoff, LAG, seuil).notna().sum())
        res = ze.run_experiment(
            counts, inventory, ze.ProfileModel, cutoff, "2026-04-02", "2026-04-05", LAG, seuil
        )
        assert res["groups"]["concerned"]["n_counters"] == 1  # groupes fixés à 24 h
        assert res["min_run_hours"] == seuil
        assert res["n_hours_replaced_c"] == replaced[seuil]
    assert replaced == {24: 110, 48: 80, 72: 80}


def test_historique_a_l_origine_publie_seulement():
    df = frame("z", with_zeros(48, 30, 200))
    hist = ze.with_availability(df, LAG)
    origin = START + pd.Timedelta(hours=150)
    seen = ze.history_at(hist, origin)
    assert (seen["ts"] + pd.Timedelta(hours=1 + LAG) <= origin).all()  # rien de non publié
    assert len(seen) == 150 - LAG  # les 24 dernières heures ne sont pas encore publiées


def test_historique_transmis_au_modele_A_garde_les_zeros_C_l_annee_d_avant():
    class Spy:
        def __init__(self):
            self.history = None

        def fit(self, train):
            pass

        def predict(self, targets, history):
            self.history = history
            return np.ones(len(targets))

    df = frame_years("z")
    cases = ze.expected_cases(["z"], "2026-03-21", "2026-03-22")
    t = ze.case_targets(cases, df)
    cutoff = pd.Timestamp("2026-03-20T00:00:00+00:00")
    spies = {}
    for treatment in ("keep", "year"):
        spies[treatment] = Spy()
        ze.run_variant(spies[treatment], df, {"z"}, t, cutoff, treatment, LAG)
    ha, hc = spies["keep"].history, spies["year"].history
    cols = ["counter_id", "ts", "available_at"]
    pd.testing.assert_frame_equal(ha[cols], hc[cols])  # mêmes heures, même publication
    diff = ha["count"].ne(hc["count"])
    assert diff.sum() == 30
    assert (ha.loc[diff, "count"] == 0).all()  # A : les zéros restent des entrées
    assert (hc.loc[diff, "count"] == 10.0).all()  # C : l'année d'avant

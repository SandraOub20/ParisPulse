"""Tests E1 de l'inventaire sur un petit réseau synthétique construit à la main.

Les données synthétiques vérifient le code ; elles ne mesurent rien sur Paris.
"""

import numpy as np
import pandas as pd
import pytest

from src.data import quality as q

START = pd.Timestamp("2026-01-05T00:00:00+00:00")  # lundi
N_DAYS = 70
SEL_END = START + pd.Timedelta(days=56)  # 8 semaines de sélection, 2 de « test »


def daily_pattern(n_hours: int, level: float) -> np.ndarray:
    """Profil pendulaire simple : pointes à 8 h et 18 h UTC, moins le week-end."""
    ts = pd.date_range(START, periods=n_hours, freq="h", tz="UTC")
    hour = ts.tz_convert(q.TZ_LOCAL).hour
    base = np.where(np.isin(hour, [7, 8, 9, 17, 18, 19]), 3 * level, level)
    weekend = np.asarray(ts.tz_convert(q.TZ_LOCAL).dayofweek >= 5)
    return np.where(weekend, base * 0.5, base).astype(float)


def series(cid: str, values: np.ndarray, start: pd.Timestamp = START) -> pd.DataFrame:
    """Lignes au format texte de counts.csv ; NaN = heure absente (is_observed=false)."""
    ts = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    observed = ~np.isnan(values)
    return pd.DataFrame(
        {
            "counter_id": cid,
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "count": values,
            "is_observed": np.where(observed, "true", "false"),
            "is_scoreable": np.where(observed, "true", "false"),
        }
    )


def counter_row(cid, site, lat, lon, direction="N-S"):
    return {
        "counter_id": cid,
        "site_id": site,
        "site_group_id": site,
        "counter_name": f"Compteur {cid}",
        "site_name": f"Site {site}",
        "latitude": lat,
        "longitude": lon,
        "direction": direction,
        "installation_date": "2020-01-01",
        "snapshot_id": "test",
    }


@pytest.fixture
def network():
    n = N_DAYS * 24
    frames, rows = [], []
    # 8 sites sains à 2 directions, répartis entre centre et périphérie
    for k in range(8):
        lat = 48.8566 + (0.005 if k % 2 else 0.06) * (1 + k % 3)
        for d in ("a", "b"):
            cid = f"ok{k}{d}"
            frames.append(series(cid, daily_pattern(n, 10 + 15 * k)))
            rows.append(counter_row(cid, f"S{k}", lat, 2.3522 + 0.01 * k))
    # Manques : 30 % d'heures absentes dispersées -> robustesse
    v = daily_pattern(n, 20)
    v[np.arange(n) % 10 < 3] = np.nan
    frames.append(series("gappy", v))
    rows.append(counter_row("gappy", "G", 48.87, 2.30))
    # Suite de zéros de 72 h -> robustesse ; zéros conservés, pas transformés en manques
    v = daily_pattern(n, 20)
    v[24 * 10 : 24 * 13] = 0.0
    frames.append(series("zeros", v))
    rows.append(counter_row("zeros", "Z", 48.83, 2.40))
    # Série presque entièrement à zéro -> exclue
    v = np.zeros(n)
    v[:24] = 5.0
    frames.append(series("dead", v))
    rows.append(counter_row("dead", "D", 48.84, 2.33))
    # Installé tard : 20 jours d'historique avant la fin de sélection -> exclu
    late_start = SEL_END - pd.Timedelta(days=20)
    frames.append(series("late", daily_pattern(24 * 34, 30), start=late_start))
    rows.append(counter_row("late", "L", 48.88, 2.36))
    # Alias possible : deux site_id différents au même endroit
    frames.append(series("alias1", daily_pattern(n, 40)))
    rows.append(counter_row("alias1", "A1", 48.8600, 2.3400))
    frames.append(series("alias2", daily_pattern(n, 40)))
    rows.append(counter_row("alias2", "A2", 48.86001, 2.34001))
    # Sans coordonnées : reste inventorié
    frames.append(series("nocoord", daily_pattern(n, 25)))
    rows.append(counter_row("nocoord", "N", np.nan, np.nan))

    counts = q.normalize_counts(pd.concat(frames, ignore_index=True))
    counters = pd.DataFrame(rows)
    return counts, counters


def build(network, **kw):
    counts, counters = network
    return q.build_inventory(counts, counters, "test", SEL_END, q.SelectionCriteria(**kw))


def sel_rows(inv):
    return inv[inv["period_role"] == q.PERIOD_SELECTION].set_index("counter_id")


def test_colonnes_du_gabarit_en_tete(network):
    inv, _ = build(network)
    assert list(inv.columns[: len(q.TEMPLATE_COLUMNS)]) == q.TEMPLATE_COLUMNS
    assert set(inv["period_role"]) == {q.PERIOD_SELECTION, q.PERIOD_FULL}
    assert len(inv) == 2 * len(network[1])


def test_comptes_sur_la_grille_de_selection(network):
    s = sel_rows(build(network)[0])
    assert s.loc["ok0a", "n_expected"] == 56 * 24
    assert s.loc["ok0a", "n_missing"] == 0
    assert s.loc["gappy", "n_missing"] == pytest.approx(0.3 * 56 * 24, abs=3)
    # Installé tard : les heures avant la première mesure sont manquantes sur la période
    assert s.loc["late", "n_observed"] == 20 * 24
    assert s.loc["late", "missing_rate_in_span"] == 0


def test_suite_de_zeros_mesuree_et_conservee(network):
    s = sel_rows(build(network)[0])
    assert s.loc["zeros", "longest_zero_run"] == 72
    assert s.loc["zeros", "n_long_zero_runs"] == 1
    assert s.loc["zeros", "n_missing"] == 0  # zéros != manques
    assert s.loc["zeros", "n_zeros"] >= 72


def test_statuts_et_raisons(network):
    s = sel_rows(build(network, full_history_days=50)[0])
    assert s.loc["dead", "selection_status"] == q.STATUS_EXCLUDED
    assert "suites de zéros" in s.loc["dead", "status_reason"]
    assert s.loc["late", "selection_status"] == q.STATUS_EXCLUDED
    assert "historique observé" in s.loc["late", "status_reason"]
    assert s.loc["gappy", "selection_status"] == q.STATUS_ROBUSTNESS
    assert "manques" in s.loc["gappy", "status_reason"]
    assert s.loc["zeros", "selection_status"] == q.STATUS_ROBUSTNESS
    assert s.loc["nocoord", "selection_status"] in {
        q.STATUS_RETAINED,
        q.STATUS_DEV_NEW,
        q.STATUS_TEST_NEW,
    }
    assert any("coordonnées absentes" in u for u in s.loc["nocoord", "uncertainties"])


def test_directions_et_alias_restent_ensemble(network):
    inv, summary = build(network, full_history_days=50)
    s = sel_rows(inv)
    for k in range(8):
        assert s.loc[f"ok{k}a", "site_role"] == s.loc[f"ok{k}b", "site_role"]
    assert s.loc["alias1", "candidate_group_id"] == s.loc["alias2", "candidate_group_id"]
    assert s.loc["alias1", "site_role"] == s.loc["alias2", "site_role"]
    assert summary["possible_alias_groups"] == [s.loc["alias1", "candidate_group_id"]]
    groups = summary["site_groups"]
    assert groups["test_new"] and groups["dev_new"]
    assert not set(groups["train"]) & (set(groups["test_new"]) | set(groups["dev_new"]))
    assert not set(groups["test_new"]) & set(groups["dev_new"])


def test_reservation_deterministe(network):
    a = build(network, full_history_days=50)[1]["site_groups"]
    b = build(network, full_history_days=50)[1]["site_groups"]
    assert a == b


def test_statut_independant_du_futur_du_test(network):
    """Modifier les heures après la fin de sélection ne change aucun statut."""
    counts, counters = network
    base = sel_rows(q.build_inventory(counts, counters, "t", SEL_END)[0])
    changed = counts.copy()
    future = changed["ts"] >= SEL_END
    changed.loc[future, "count"] = 0.0
    changed.loc[future & (changed["counter_id"] == "ok0a"), "is_observed"] = False
    other = sel_rows(q.build_inventory(changed, counters, "t", SEL_END)[0])
    cols = ["selection_status", "status_reason", "site_role", "n_observed", "mean_count"]
    pd.testing.assert_frame_equal(base[cols], other[cols])


def test_statut_recopie_sur_la_periode_complete(network):
    inv, _ = build(network)
    full = inv[inv["period_role"] == q.PERIOD_FULL].set_index("counter_id")
    s = sel_rows(inv)
    assert (full["selection_status"] == s["selection_status"]).all()
    assert (full["n_expected"] > s["n_expected"]).all()


def test_cle_dupliquee_refusee(network):
    counts, _ = network
    raw = pd.DataFrame(
        {
            "counter_id": ["x", "x"],
            "timestamp": ["2026-01-05T00:00:00+00:00"] * 2,
            "count": [1.0, 2.0],
            "is_observed": ["true", "true"],
            "is_scoreable": ["true", "true"],
        }
    )
    with pytest.raises(ValueError, match="dupliquées"):
        q.normalize_counts(raw)


def test_true_runs():
    assert q.true_runs(np.array([1, 1, 0, 1, 0, 0, 1, 1, 1], bool)).tolist() == [2, 1, 3]
    assert q.true_runs(np.array([], bool)).tolist() == []


def test_jour_changement_heure_incomplet_signale():
    """Le 25/10/2026 compte 25 h locales ; une heure absente est signalée, pas supprimée."""
    start = pd.Timestamp("2026-10-23T22:00:00+00:00")
    grid = q.hour_grid(start, start + pd.Timedelta(days=4))
    values = np.full(len(grid), 10.0)
    values[grid.get_loc(pd.Timestamp("2026-10-25T01:00:00+00:00"))] = np.nan
    s = q.normalize_counts(series("dst", values, start=start))
    m = q.counter_metrics(s, grid)
    assert m["n_dst_days_incomplete"] == 1
    assert m["n_missing"] == 1


def test_deux_sens_a_80_m_restent_ensemble():
    """Cas réel du Pont National : deux site_id à 57 m pour les deux sens."""
    counters = pd.DataFrame(
        [
            counter_row("p1", "P1", 48.8300, 2.3800),
            counter_row("p2", "P2", 48.8300, 2.3811),  # ~80 m plus à l'est
            counter_row("far", "F", 48.8400, 2.3800),  # ~1,1 km
        ]
    )
    groups = q.candidate_groups(counters, q.SelectionCriteria().alias_distance_m)
    cand = groups.set_index("site_group_id")["candidate_group_id"]
    assert cand["P1"] == cand["P2"] != cand["F"]


def test_voisins_en_dictionnaire_avec_distance():
    """alias_candidates (< 100 m) et nearby_sites_300m (< 300 m) : {site: mètres}."""
    counters = pd.DataFrame(
        [
            counter_row("p1", "P1", 48.8300, 2.3800),
            counter_row("p2", "P2", 48.8300, 2.3811),  # ~80 m à l'est de P1
            counter_row("m", "M", 48.8300, 2.3830),  # ~220 m de P1, ~140 m de P2
            counter_row("far", "F", 48.8400, 2.3800),  # ~1,1 km
        ]
    )
    g = q.candidate_groups(counters, 100.0, 300.0).set_index("site_group_id")
    alias, near = g["alias_candidates"], g["nearby_sites_300m"]
    # Distance attendue calculée indépendamment (formule de haversine)
    d12 = round(q.haversine_km(48.83, 2.38, 48.83, 2.3811) * 1000)
    assert 75 <= d12 <= 85
    assert alias["P1"] == {"P2": d12} and alias["P2"] == {"P1": d12}
    assert alias["M"] == {} and alias["F"] == {}
    # 300 m : alias compris, du plus proche au plus loin, sans le site lui-même
    assert list(near["P1"]) == ["P2", "M"] and near["P1"]["P2"] == d12
    assert 210 <= near["P1"]["M"] <= 230
    assert list(near["M"]) == ["P2", "P1"]
    assert near["F"] == {}
    # Le seuil de 300 m n'agrandit pas les groupes : M reste seul
    cand = g["candidate_group_id"]
    assert cand["P1"] == cand["P2"] != cand["M"]


def test_colonnes_voisinage_ecrites_en_json(network):
    """Dans le CSV, les deux colonnes sont des objets JSON {site: mètres}."""
    import json

    inv, _ = build(network)
    table = q.inventory_table(inv)
    row = table[(table["counter_id"] == "alias1") & (table["period_role"] == q.PERIOD_SELECTION)]
    alias = json.loads(row["alias_candidates"].iloc[0])
    near = json.loads(row["nearby_sites_300m"].iloc[0])
    assert list(alias) == ["A2"] and isinstance(alias["A2"], int)
    assert alias.items() <= near.items()


def test_trou_commun_au_reseau_detecte(network):
    counts, _ = network
    day = (counts["ts"] >= START + pd.Timedelta(days=30)) & (
        counts["ts"] < START + pd.Timedelta(days=31)
    )
    holed = counts.copy()
    holed.loc[day, "is_observed"] = False
    gaps = q.network_gaps(holed)
    assert [g["hours"] for g in gaps] == [24]
    assert gaps[0]["start"] == q._iso(START + pd.Timedelta(days=30))
    assert q.network_gaps(counts) == []


def test_counters_csv_recoit_les_groupes_candidats(network):
    """Étape 3 : site_group_id de counters.csv = groupe candidat, seule colonne modifiée."""
    inv, summary = build(network)
    raw = network[1].astype(str)
    new = q.counters_with_groups(raw, inv).set_index("counter_id")
    assert new.loc["alias1", "site_group_id"] == new.loc["alias2", "site_group_id"] == "A1"
    for k in range(8):
        assert new.loc[f"ok{k}a", "site_group_id"] == new.loc[f"ok{k}b", "site_group_id"]
    assert new.loc["gappy", "site_group_id"] == "G"
    others = [c for c in raw.columns if c != "site_group_id"]
    pd.testing.assert_frame_equal(new.reset_index()[raw.columns][others], raw[others])
    assert summary["n_site_groups"] == new["site_group_id"].nunique()
    sel = sel_rows(inv)
    assert (sel["site_group_id"] == sel["candidate_group_id"]).all()


def test_relancer_donne_le_meme_resultat(network, tmp_path):
    """Après réécriture de counters.csv, une 2e exécution ne change plus rien."""
    counts, counters = network
    path = tmp_path / "counters.csv"
    counters.to_csv(path, index=False)

    def once():
        inv, summary = q.build_inventory(counts, q.load_counters(path), "t", SEL_END)
        return inv, summary, q.write_site_groups(path, inv), path.read_bytes()

    inv1, sum1, changed1, bytes1 = once()
    inv2, sum2, changed2, bytes2 = once()
    assert changed1 and not changed2
    assert bytes1 == bytes2
    pd.testing.assert_frame_equal(q.inventory_table(inv1), q.inventory_table(inv2))
    assert sum1 == sum2

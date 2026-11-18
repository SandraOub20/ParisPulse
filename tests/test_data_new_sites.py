"""Sites réservés à E3 rendus « nouveaux » (src/data/new_sites.py)."""

import pandas as pd

from src.data.new_sites import install_time, make_new_sites, reserved_counters, update_counters

LAG = 24


def inventory():
    rows = [
        ("a1", "reserved_test_new", "A"),
        ("a2", "reserved_test_new", "A"),  # autre sens du même site
        ("b1", "reserved_test_new", "B"),
        ("c1", "reserved_test_new", "C"),
        ("d1", "reserved_dev_new", "D"),
        ("k1", "retained", "K"),
    ]
    inv = pd.DataFrame(rows, columns=["counter_id", "selection_status", "candidate_group_id"])
    inv["period_role"] = "selection"
    full = inv.assign(period_role="full_snapshot", selection_status="retained")
    return pd.concat([inv, full], ignore_index=True)


def counts(ids):
    ts = pd.date_range("2026-06-01", "2026-11-14 22:00", freq="h", tz="UTC")
    rows = [
        pd.DataFrame(
            {
                "counter_id": cid,
                "ts": ts,
                "count": 5.0,
                "count_raw": "5.0",
                "is_observed": True,
                "is_scoreable": True,
                "quality_flags": [[] for _ in ts],
            }
        )
        for cid in ids
    ]
    return pd.concat(rows, ignore_index=True)


def test_compteurs_reserves_seulement():
    r = reserved_counters(inventory())
    assert set(r["counter_id"]) == {"a1", "a2", "b1", "c1", "d1"}  # jamais les retained
    assert r.set_index("counter_id").loc["a2", "group"] == "A"


def test_installation_au_debut_du_support_de_la_premiere_origine():
    # test : origine 01/10/2026 00:00 Paris = 30/09 22:00 UTC ; - 24 h - 7 jours
    assert install_time("reserved_test_new", 7, LAG) == pd.Timestamp("2026-09-22 22:00", tz="UTC")
    # dev : origine 01/07/2026 00:00 Paris = 30/06 22:00 UTC ; - 24 h - 1 jour
    assert install_time("reserved_dev_new", 1, LAG) == pd.Timestamp("2026-06-28 22:00", tz="UTC")


def test_historique_vide_avant_installation_memes_sites_dans_chaque_version():
    ids = ["a1", "a2", "b1", "c1", "d1", "k1"]
    reserved = reserved_counters(inventory())
    for days in (1, 3, 7):
        out, plan, rep = make_new_sites(counts(ids), reserved, days, LAG)
        assert set(plan["counter_id"]) == {"a1", "a2", "b1", "c1", "d1"}  # mêmes sites
        assert (plan["budget_days"] == days).all()  # seul le budget change
        for r in plan.itertuples():
            g = out[out["counter_id"] == r.counter_id]
            assert g.loc[g["is_observed"], "ts"].min() == install_time(r.status, days, LAG)
            hidden = g[~g["is_observed"]]
            assert hidden["count"].isna().all() and (hidden["count_raw"] == "").all()
            assert not hidden["is_scoreable"].any()
            assert all(f == ["missing"] for f in hidden["quality_flags"])
        assert out[out["counter_id"] == "k1"]["is_observed"].all()  # non réservé intact
        assert rep["n_counters"] == 5 and rep["n_sites"] == 4 and rep["budget_days"] == days


def test_budget_publie_a_la_premiere_origine():
    # à l'origine, avec 24 h de délai, le site a exactement le budget en heures publiées
    out, plan, _ = make_new_sites(counts(["a1"]), reserved_counters(inventory()), 3, LAG)
    origin = pd.Timestamp("2026-09-30 22:00", tz="UTC")
    published = out[(out["ts"] + pd.Timedelta(hours=1 + LAG) <= origin) & out["is_observed"]]
    assert len(published) == 3 * 24


def test_date_d_installation_fictive_dans_counters():
    _, plan, _ = make_new_sites(counts(["a1"]), reserved_counters(inventory()), 7, LAG)
    counters = pd.DataFrame({"counter_id": ["a1", "k1"], "installation_date": ["2015-01-01"] * 2})
    out = update_counters(counters, plan).set_index("counter_id")["installation_date"]
    assert out["a1"] == "2026-09-23" and out["k1"] == "2015-01-01"  # 23/09 00:00 Paris

"""Sites réservés à E3 rendus « nouveaux » (src/data/new_sites.py)."""

import pandas as pd

from src.data.new_sites import (
    assign_budgets,
    install_time,
    make_new_sites,
    reference_time,
    update_counters,
)


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
    # dernière heure : 14/11/2026 22:00 UTC = 23 h à Paris -> référence 15/11 00:00 Paris
    ts = pd.date_range("2026-10-01", "2026-11-14 22:00", freq="h", tz="UTC")
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


def test_budgets_par_site_et_par_statut():
    plan = assign_budgets(inventory()).set_index("counter_id")
    assert set(plan.index) == {"a1", "a2", "b1", "c1", "d1"}  # jamais les retained
    assert plan.loc["a1", "budget_days"] == plan.loc["a2", "budget_days"]  # même site
    test = plan[plan["status"] == "reserved_test_new"].drop_duplicates("group")
    assert sorted(test["budget_days"]) == [1, 3, 7]  # 3 sites, 3 budgets
    assert plan.loc["d1", "budget_days"] == 1  # dev : tirage séparé, commence à 1
    assert plan.equals(assign_budgets(inventory()).set_index("counter_id"))  # reproductible


def test_installation_avant_la_fin_de_l_instantane():
    c = counts(["a1"])
    ref = reference_time(c)
    assert ref == pd.Timestamp("2026-11-14 23:00", tz="UTC")  # 15/11 00:00 Paris
    assert install_time(ref, 7) == pd.Timestamp("2026-11-07 23:00", tz="UTC")


def test_historique_vide_avant_installation():
    ids = ["a1", "a2", "b1", "c1", "d1", "k1"]
    plan = assign_budgets(inventory())
    out, plan, rep = make_new_sites(counts(ids), plan)
    budget = dict(zip(plan["counter_id"], plan["budget_days"]))
    for cid, days in budget.items():
        g = out[out["counter_id"] == cid]
        assert g["is_observed"].sum() == 24 * days  # seulement les k derniers jours
        hidden = g[~g["is_observed"]]
        assert hidden["count"].isna().all() and (hidden["count_raw"] == "").all()
        assert not hidden["is_scoreable"].any()
        assert all(f == ["missing"] for f in hidden["quality_flags"])
    k = out[out["counter_id"] == "k1"]
    assert k["is_observed"].all()  # compteur non réservé intact
    assert rep["n_counters"] == 5 and rep["n_sites"] == 4


def test_date_d_installation_fictive_dans_counters():
    plan = assign_budgets(inventory())
    _, plan, _ = make_new_sites(counts(["a1"]), plan)
    counters = pd.DataFrame({"counter_id": ["a1", "k1"], "installation_date": ["2015-01-01"] * 2})
    out = update_counters(counters, plan).set_index("counter_id")["installation_date"]
    days = int(plan.set_index("counter_id").loc["a1", "budget_days"])
    expected = (pd.Timestamp("2026-11-15") - pd.Timedelta(days=days)).date().isoformat()
    assert out["a1"] == expected and out["k1"] == "2015-01-01"

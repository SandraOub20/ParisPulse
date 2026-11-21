"""Comparaison des critères des zéros (src/data/zeros_criteria.py), sur un inventaire synthétique."""

import pandas as pd

from src.data.quality import SelectionCriteria
from src.data.zeros_criteria import base_status, compare_options, criteria_from_manifest

END = "2026-09-30T22:00:00+00:00"


def row(cid, status, share, runs, **kw):
    base = {
        "counter_id": cid,
        "counter_name": cid,
        "period_role": "selection",
        "selection_status": status,
        "n_scoreable": 8000,
        "observed_days": 340.0,
        "missing_rate_in_span": 0.01,
        "long_zero_share": share,
        "n_long_zero_runs": runs,
        "longest_zero_run": 30 if runs else 0,
        "mean_count": 50.0,
        "last_observed": "2026-09-30T21:00:00+00:00",
        "period_end": END,
    }
    base.update(kw)
    return base


def inventory():
    rows = [
        row("ok", "retained", 0.0, 0),
        row("res", "reserved_test_new", 0.0, 0),
        row("petit", "robustness", 0.02, 1),  # seulement des zéros, part faible
        row("gros", "robustness", 0.30, 2),  # seulement des zéros, part forte
        row("faible", "robustness", 0.02, 1, mean_count=2.0),  # zéros + faible volume
        row("vide", "excluded", 1.0, 3),
    ]
    inv = pd.DataFrame(rows)
    full = inv.assign(period_role="full_snapshot", selection_status="retained")
    return pd.concat([inv, full], ignore_index=True)  # deux lignes par compteur


def test_option_1_retrouve_l_inventaire():
    summary, _ = compare_options(inventory(), thresholds=(0.05,))
    assert summary["option_1"].equals(summary["inventaire"])
    assert summary.loc["robustness", "option_1"] == 3


def test_option_2_ne_retire_que_la_regle_des_zeros():
    _, changed = compare_options(inventory(), thresholds=(0.05,))
    got = dict(zip(changed["counter_id"], changed["option_2_0.05"]))
    assert got == {"petit": "retained"}  # « faible » reste robustness, « gros » aussi


def test_seuil_exclusion_inchange():
    _, changed = compare_options(inventory(), thresholds=(0.99,))
    assert "vide" not in set(changed["counter_id"])  # 100 % de zéros : toujours exclu


def test_site_reserve_compte_comme_retained():
    assert base_status("reserved_dev_new") == "retained"
    assert base_status("robustness") == "robustness"


def test_criteres_lus_dans_le_manifeste():
    c = criteria_from_manifest({"quality": {"criteria": {"low_volume_mean": 7.0, "inconnu": 1}}})
    assert c.low_volume_mean == 7.0
    assert c.min_observed_days == SelectionCriteria().min_observed_days

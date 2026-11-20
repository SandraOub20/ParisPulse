"""Examen des alertes du manifeste (src/data/alerts_review.py), sur données synthétiques."""

import numpy as np
import pandas as pd

from src.data.alerts_review import review

DST_ALERT = "Jour de changement d'heure 2025-10-26 : {} heures observées (perte possible)."
PEAK_ALERT = "Pics en semaine à 12 h et 18 h (attendu ~8 h et ~18 h) : vérifier le fuseau."


def counts_frame(ids, start="2025-10-20", end="2025-11-02", hole=None, peak=None):
    """Comptages horaires : profil 8 h / 18 h par défaut ; `peak` = {id: heure du matin}."""
    ts = pd.date_range(start, end, freq="h", tz="UTC", inclusive="left")
    rows = []
    for cid in ids:
        hour = ts.tz_convert("Europe/Paris").hour
        am = (peak or {}).get(cid, 8)
        count = np.where((hour == am) | (hour == 18), 100.0, 10.0)
        observed = np.ones(len(ts), dtype=bool)
        if hole is not None:
            for t in hole.get(cid, []):
                observed[ts == pd.Timestamp(t, tz="UTC")] = False
        count = np.where(observed, count, np.nan)
        rows.append(
            pd.DataFrame(
                {
                    "counter_id": cid,
                    "ts": ts,
                    "count": count,
                    "is_observed": observed,
                    "is_scoreable": observed,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def counters_frame(sites):
    return pd.DataFrame({"counter_id": list(sites), "site_id": list(sites.values())})


def inventory_frame(ids, mean=50.0, share=0.0):
    return pd.DataFrame(
        {
            "counter_id": ids,
            "counter_name": ids,
            "period_role": "selection",
            "mean_count": mean,
            "long_zero_share": share,
        }
    )


def manifest(alerts):
    return {"counters": {cid: {"alerts": a} for cid, a in alerts.items()}}


def test_heure_repetee_perdue_sur_tout_le_reseau():
    lost = "2025-10-26 00:00"  # 2 h heure d'été, première des deux « 2 h »
    ids = ["a", "b", "c"]
    counts = counts_frame(ids, hole={i: [lost] for i in ids})
    m = manifest({i: [DST_ALERT.format("24/25")] for i in ids})
    res = review(m, counts, counters_frame(dict.fromkeys(ids, "")), inventory_frame(ids))
    assert set(res["category"]) == {"dst_hour_lost_network"}


def test_heure_manquante_propre_au_compteur():
    ids = ["a", "b", "c"]
    counts = counts_frame(ids, hole={"a": ["2025-10-26 05:00"]})
    m = manifest({"a": [DST_ALERT.format("24/25")]})
    res = review(m, counts, counters_frame(dict.fromkeys(ids, "")), inventory_frame(ids))
    assert list(res["category"]) == ["dst_counter"]
    assert res["action"].iloc[0].startswith("à examiner")


def test_journee_non_publiee():
    ids = ["a", "b"]
    # journée de 25 h à Paris : du 25/10 22:00 UTC au 26/10 23:00 UTC (exclu)
    day = pd.date_range("2025-10-25 22:00", "2025-10-26 23:00", freq="h", inclusive="left")
    counts = counts_frame(ids, hole={i: [str(t) for t in day] for i in ids})
    m = manifest({"a": [DST_ALERT.format("0/25")]})
    res = review(m, counts, counters_frame(dict.fromkeys(ids, "")), inventory_frame(ids))
    assert list(res["category"]) == ["dst_day_not_published"]


def test_pic_du_soir_explique_par_l_autre_sens():
    counts = counts_frame(["aller", "retour"], peak={"aller": 12})
    m = manifest({"aller": [PEAK_ALERT]})
    sites = counters_frame({"aller": "s1", "retour": "s1"})
    res = review(m, counts, sites, inventory_frame(["aller", "retour"]))
    assert list(res["category"]) == ["peak_evening_direction"]


def test_pic_faible_volume_et_panne():
    counts = counts_frame(["faible", "panne"], peak={"faible": 12, "panne": 12})
    m = manifest({"faible": [PEAK_ALERT], "panne": [PEAK_ALERT]})
    sites = counters_frame({"faible": "s1", "panne": "s2"})
    inv = pd.concat([inventory_frame(["faible"], mean=2.0), inventory_frame(["panne"], share=0.9)])
    res = review(m, counts, sites, inv).set_index("counter_id")
    assert res.loc["faible", "category"] == "peak_low_volume"
    assert res.loc["panne", "category"] == "peak_broken"


def test_alerte_inconnue_a_examiner():
    counts = counts_frame(["a"])
    m = manifest({"a": ["2 valeurs distinctes de counter_name pour ce compteur.", "autre"]})
    res = review(m, counts, counters_frame({"a": ""}), inventory_frame(["a"]))
    assert list(res["category"]) == ["metadata", "other"]

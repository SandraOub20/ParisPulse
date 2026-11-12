"""Tests E1 sur un petit jeu synthétique construit à la main.

Les données synthétiques vérifient le code ; elles ne mesurent rien sur Paris.
"""

import datetime as dt
import json

import pandas as pd
import pytest

from src.common.config import ROOT
from src.data import acquire, prepare

CID = "999-test"


def raw_frame(rows):
    """Brut au format de l'export API : (date, valeur) en texte."""
    return pd.DataFrame(
        {
            "id_compteur": CID,
            "nom_compteur": "Compteur test S-N",
            "id": "999",
            "name": "Site test",
            "sum_counts": [v for _, v in rows],
            "date": [d for d, _ in rows],
            "installation_date": "2020-01-01",
            "coordinates": "48.85, 2.35",
        }
    )


def by_hour(prepared):
    return prepared.counts.set_index(prepared.counts["ts"].dt.strftime("%Y-%m-%dT%H"))


@pytest.fixture
def mixed():
    rows = [
        ("2026-03-02T00:00:00+00:00", "5.0"),
        ("2026-03-02T01:00:00+00:00", "0.0"),  # zéro observé
        # 02:00 absente
        ("2026-03-02T03:00:00+00:00", "7.0"),  # doublon en conflit
        ("2026-03-02T03:00:00+00:00", "9.0"),
        ("2026-03-02T04:00:00+00:00", "3.0"),  # doublon identique
        ("2026-03-02T04:00:00+00:00", "3.0"),
        ("2026-03-02T05:00:00+00:00", "-1.0"),  # négatif
    ]
    return prepare.normalize(raw_frame(rows), CID)


def test_zero_observe_reste_zero(mixed):
    h = by_hour(mixed).loc["2026-03-02T01"]
    assert h["count"] == 0 and h["count_raw"] == 0
    assert h["is_observed"] and h["is_scoreable"]
    assert h["flags"] == []


def test_heure_absente_inseree(mixed):
    assert len(mixed.counts) == 6  # grille complète 00..05
    h = by_hour(mixed).loc["2026-03-02T02"]
    assert pd.isna(h["count"]) and pd.isna(h["count_raw"])
    assert not h["is_observed"] and not h["is_scoreable"]
    assert h["flags"] == [prepare.FLAG_MISSING]


def test_doublon_en_conflit_signale_sans_choix(mixed):
    h = by_hour(mixed).loc["2026-03-02T03"]
    assert pd.isna(h["count"]) and pd.isna(h["count_raw"])
    assert h["is_observed"] and not h["is_scoreable"]
    assert h["flags"] == [prepare.FLAG_CONFLICT]
    audit = mixed.audit[mixed.audit["resolution"] == prepare.FLAG_CONFLICT]
    assert sorted(audit["count_source"]) == ["7.0", "9.0"]
    assert mixed.report["n_conflict_hours"] == 1


def test_doublon_identique_conserve(mixed):
    h = by_hour(mixed).loc["2026-03-02T04"]
    assert h["count"] == 3 and h["is_scoreable"]
    assert h["flags"] == [prepare.FLAG_DUPLICATE]


def test_negatif_non_evaluable(mixed):
    h = by_hour(mixed).loc["2026-03-02T05"]
    assert h["count_raw"] == -1 and pd.isna(h["count"])
    assert h["is_observed"] and not h["is_scoreable"]
    assert h["flags"] == [prepare.FLAG_NEGATIVE]


def test_longue_suite_de_zeros_signalee_mais_conservee():
    start = pd.Timestamp("2026-03-02T00:00:00+00:00")
    values = (
        ["0.0"] * prepare.LONG_ZERO_RUN_HOURS
        + ["4.0"]
        + ["0.0"] * (prepare.LONG_ZERO_RUN_HOURS - 1)
    )
    rows = [((start + pd.Timedelta(hours=i)).isoformat(), v) for i, v in enumerate(values)]
    c = prepare.normalize(raw_frame(rows), CID).counts
    long_flag = c["flags"].map(lambda f: prepare.FLAG_LONG_ZERO_RUN in f)
    assert long_flag[: prepare.LONG_ZERO_RUN_HOURS].all()
    assert not long_flag[prepare.LONG_ZERO_RUN_HOURS :].any()  # suite de 23 h non signalée
    assert (c["count"].iloc[: prepare.LONG_ZERO_RUN_HOURS] == 0).all()
    assert c["is_scoreable"].all()


def test_heure_ambigue_naive_conservee_et_signalee():
    rows = [
        ("2025-10-26T01:00:00", "10.0"),
        ("2025-10-26T02:00:00", "11.0"),  # heure d'été
        ("2025-10-26T02:00:00", "12.0"),  # heure d'hiver
        ("2025-10-26T03:00:00", "13.0"),
    ]
    p = prepare.normalize(raw_frame(rows), CID)
    c = p.counts
    assert list(c["ts"].dt.strftime("%Y-%m-%dT%H:%M")) == [
        "2025-10-25T23:00",
        "2025-10-26T00:00",
        "2025-10-26T01:00",
        "2025-10-26T02:00",
    ]
    assert list(c["count"]) == [10, 11, 12, 13]
    assert c["is_observed"].all()
    assert [prepare.FLAG_DST_AMBIGUOUS in f for f in c["flags"]] == [False, True, True, False]
    assert p.report["n_dst_ambiguous_rows"] == 2


def test_heure_inexistante_naive_decalee_et_signalee():
    rows = [("2026-03-29T01:00:00", "1.0"), ("2026-03-29T02:00:00", "2.0")]
    c = prepare.normalize(raw_frame(rows), CID).counts
    assert list(c["ts"].dt.strftime("%H:%M")) == ["00:00", "01:00"]
    assert c["flags"].iloc[1] == [prepare.FLAG_DST_NONEXISTENT]


def test_jour_de_25_heures_detecte_en_utc():
    ts = pd.date_range("2025-10-23T22:00Z", "2025-10-28T22:00Z", freq="h")
    rows = [(t.isoformat(), "1.0") for t in ts]
    c = prepare.normalize(raw_frame(rows), CID).counts
    assert prepare.dst_days(c) == {dt.date(2025, 10, 26): (25, 25)}


def test_pics_attendus():
    ts = pd.date_range("2026-03-02T00:00Z", periods=24 * 7, freq="h")
    local_hour = ts.tz_convert(prepare.TZ_LOCAL).hour
    values = [100.0 if h in (8, 18) else 10.0 for h in local_hour]
    rows = [(t.isoformat(), str(v)) for t, v in zip(ts, values)]
    profile = prepare.hourly_profile(prepare.normalize(raw_frame(rows), CID).counts)
    assert prepare.check_peaks(profile) == (8, 18, None)


def _template_header(name):
    return (ROOT / "doc" / "templates" / name).read_text(encoding="utf-8").splitlines()[0]


def test_colonnes_et_format_conformes_aux_gabarits(mixed, tmp_path):
    written = prepare.write_outputs(mixed, "flux-20260101", "src-file", tmp_path)
    counts_text = (tmp_path / "counts.csv").read_text(encoding="utf-8").splitlines()
    counters_text = (tmp_path / "counters.csv").read_text(encoding="utf-8").splitlines()
    assert counts_text[0] == _template_header("counts.csv")
    assert counters_text[0] == _template_header("counters.csv")
    assert prepare.COUNTS_COLUMNS == _template_header("counts.csv").split(",")
    assert prepare.COUNTERS_COLUMNS == _template_header("counters.csv").split(",")

    c = pd.read_csv(tmp_path / "counts.csv", dtype=str, keep_default_na=False)
    assert c["timestamp"].iloc[0] == "2026-03-02T00:00:00+00:00"
    assert c["interval_end"].iloc[0] == "2026-03-02T01:00:00+00:00"
    assert set(c["is_observed"]) | set(c["is_scoreable"]) <= {"true", "false"}
    missing = c[c["timestamp"] == "2026-03-02T02:00:00+00:00"].iloc[0]
    assert missing["count"] == "" and missing["is_observed"] == "false"
    assert json.loads(missing["quality_flags"]) == ["missing"]
    zero = c[c["timestamp"] == "2026-03-02T01:00:00+00:00"].iloc[0]
    assert zero["count"] == "0.0" and json.loads(zero["quality_flags"]) == []
    assert c[["counter_id", "timestamp"]].duplicated().sum() == 0

    k = written["counters"].iloc[0]
    assert k["site_group_id"] == k["site_id"] == "999"
    assert k["latitude"] == "48.85" and k["direction"] == ""


def test_ajout_d_un_second_compteur_sans_ecraser(mixed, tmp_path):
    prepare.write_outputs(mixed, "s", "f", tmp_path)
    other = raw_frame([("2026-03-02T00:00:00+00:00", "1.0")]).assign(id_compteur="888-test")
    prepare.write_outputs(prepare.normalize(other, "888-test"), "s", "g", tmp_path)
    prepare.write_outputs(mixed, "s", "f", tmp_path)  # relance : pas de doublon
    c = pd.read_csv(tmp_path / "counts.csv", dtype=str)
    assert c["counter_id"].value_counts().to_dict() == {CID: 6, "888-test": 1}


def test_acquire_identifiants_et_bom(tmp_path):
    assert acquire.snapshot_id_for(dt.datetime(2026, 11, 12, 23, 30, tzinfo=dt.timezone.utc)) == (
        "flux-20261112"
    )
    url, params = acquire.export_url("100057445-104057445")
    assert params["timezone"] == "UTC"
    assert "id_compteur%3D%22100057445-104057445%22" in url
    raw = tmp_path / "brut.csv"
    raw.write_bytes("﻿id_compteur;sum_counts;date\nX;0.0;2026-01-01T00:00:00+00:00\n".encode())
    df = acquire.read_raw(raw)
    assert list(df.columns) == ["id_compteur", "sum_counts", "date"]
    assert df["sum_counts"].iloc[0] == "0.0"
    assert acquire.raw_stats(raw)["n_rows"] == 1
    assert len(acquire.sha256_file(raw)) == 64

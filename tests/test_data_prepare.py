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
    assert k["latitude"] == "48.85" and k["direction"] == "S-N"


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


# ----------------------------------------------------------------- décisions E1 du 15/11
def test_direction_tiree_du_nom():
    assert prepare.direction_from_name("Totem 73 boulevard de Sébastopol S-N") == "S-N"
    assert prepare.direction_from_name("Pont National SO-NE") == "SO-NE"
    assert prepare.direction_from_name("Quai d'Orsay") is None
    assert prepare.direction_from_name("Boulevard Saint-Michel") is None  # pas un sens
    assert prepare.opposite("SO-NE") == "NE-SO"


def test_compteur_arrete_garde_ses_heures_jusqu_a_la_fin():
    """Grille commune : un compteur arrêté a des lignes manquantes jusqu'à la fin."""
    rows = [("2026-03-02T00:00:00+00:00", "5.0"), ("2026-03-02T01:00:00+00:00", "6.0")]
    grid = (pd.Timestamp("2026-03-01T22:00Z"), pd.Timestamp("2026-03-02T05:00Z"))
    p = prepare.normalize(raw_frame(rows), CID, grid)
    c = p.counts
    assert len(c) == 8  # 22:00 -> 05:00
    after = c[c["ts"] > pd.Timestamp("2026-03-02T01:00Z")]
    before = c[c["ts"] < pd.Timestamp("2026-03-02T00:00Z")]
    for part in (after, before):
        assert not part["is_observed"].any() and part["count"].isna().all()
        assert all(f == [prepare.FLAG_MISSING] for f in part["flags"])
    assert p.report["last_observed"] == "2026-03-02T01:00:00+00:00"
    assert p.report["grid"] == "commune à l'instantané"


def test_mesures_hors_fenetre_comptees_pas_sur_la_grille():
    """La fenêtre commune est la même pour tous : ce qui est hors fenêtre est compté."""
    rows = [
        ("2026-03-02T00:00:00+00:00", "5.0"),
        ("2026-03-02T02:00:00+00:00", "7.0"),
        ("2026-03-02T09:00:00+00:00", "6.0"),
    ]
    grid = (pd.Timestamp("2026-03-02T02:00Z"), pd.Timestamp("2026-03-02T03:00Z"))
    p = prepare.normalize(raw_frame(rows), CID, grid)
    assert len(p.counts) == 2 and p.counts["is_observed"].sum() == 1
    assert p.report["n_hours_outside_window"] == 2


def _network(tmp_path, monkeypatch, n_sites=5, alias=False):
    """Brut complet : n_sites x 2 sens + un compteur arrêté, sur 4 jours ; jour 2 vide.

    Sites à environ 1 km les uns des autres ; `alias` ajoute un compteur d'un autre
    site_id à environ 45 m du site s0 (même lieu probable).
    """
    start = pd.Timestamp("2026-08-21T00:00Z")
    hours = pd.date_range(start, periods=96, freq="h")
    # Premier jour du brut rogné par la source : quelques heures d'un seul compteur
    rogne = pd.date_range(start - pd.Timedelta(days=1), periods=24, freq="h")[::4]
    gap = (hours >= start + pd.Timedelta(days=1)) & (hours < start + pd.Timedelta(days=2))
    frames = []

    def add(cid, site, name, ts, coords="48.85, 2.35"):
        frames.append(
            pd.DataFrame(
                {
                    "id_compteur": cid,
                    "nom_compteur": name,
                    "id": site,
                    "name": f"Site {site}",
                    "sum_counts": "4.0",
                    "date": [t.isoformat() for t in ts],
                    "installation_date": "2020-01-01",
                    "coordinates": coords,
                }
            )
        )

    for k in range(n_sites):
        coords = f"{48.80 + 0.01 * k:.4f}, 2.35"
        first_ts = rogne.append(hours[~gap]) if k == 0 else hours[~gap]
        add(f"c{k}a", f"s{k}", f"Rue {k} N-S", first_ts, coords)
        add(f"c{k}b", f"s{k}", f"Rue {k} S-N", hours[~gap], coords)
    add("stop", "z", "Rue arrêtée E-O", hours[:12], "48.95, 2.45")  # s'arrête le premier jour
    if alias:
        add("al", "s9", "Rue 0 bis N-S", hours[~gap], "48.8004, 2.35")
    raw = pd.concat(frames, ignore_index=True)

    for mod in (prepare, acquire):
        monkeypatch.setattr(mod, "data_path", lambda key: tmp_path / key)
        monkeypatch.setattr(mod, "relative_to_root", lambda p: str(p))
    snap = tmp_path / "history" / "flux-test"
    snap.mkdir(parents=True)
    raw.to_csv(snap / acquire.RAW_ALL_FILENAME, sep=";", index=False, encoding="utf-8-sig")
    return start, hours, gap


def test_preparation_de_tout_le_flux(tmp_path, monkeypatch):
    start, hours, gap = _network(tmp_path, monkeypatch)
    items = prepare.prepare_all("flux-test")
    assert len(items) == 11

    c = pd.read_csv(tmp_path / "processed" / "flux-test" / "counts.csv", dtype=str)
    assert c.groupby("counter_id").size().eq(96).all()  # même grille pour tous
    assert c[["counter_id", "timestamp"]].duplicated().sum() == 0
    stop = c[c["counter_id"] == "stop"]
    assert (stop["is_observed"].iloc[12:] == "false").all()  # heures gardées après l'arrêt

    flags = c["quality_flags"].map(json.loads)
    in_gap = c["timestamp"].isin(hours[gap].strftime("%Y-%m-%dT%H:%M:%S+00:00"))
    is_stop = c["counter_id"] == "stop"
    assert all(f == ["missing", "network_gap"] for f in flags[in_gap & ~is_stop])
    # Arrêté avant la panne : l'heure manque à cause du compteur, pas du réseau
    assert all(f == ["missing"] for f in flags[in_gap & is_stop])
    assert not any("network_gap" in f for f in flags[~in_gap])

    k = pd.read_csv(tmp_path / "processed" / "flux-test" / "counters.csv", dtype=str)
    assert len(k) == 11 and k["direction"].notna().all()
    manifest = json.loads((tmp_path / "manifests" / "flux-test.json").read_text())
    assert manifest["grid"]["n_hours"] == 96
    assert manifest["network_gap"]["n_hours"] == 24
    checks = manifest["direction_checks"]
    assert checks["n_with_direction"] == 11 and checks["sites_not_opposite"] == []
    assert checks["n_sites_with_several_counters"] == 5
    assert manifest["files"][0]["n_rows"] == 11 * 96


def test_sens_non_opposes_signales(tmp_path, monkeypatch):
    _network(tmp_path, monkeypatch, n_sites=1)
    items = prepare.prepare_all("flux-test")
    items[0].counter["direction"] = "N-S"
    items[1].counter["direction"] = "N-S"
    assert prepare.direction_checks(items)["sites_not_opposite"] == [
        {"site_id": "s0", "directions": ["N-S", "N-S"]}
    ]


# ----------------------------------------------------------------- relecture du 16/11 (Tasnim)
def _counter(cid, site, name, ts, hours, empty_hours=()):
    """Compteur préparé sur la grille commune `hours` ; valeur vide aux `empty_hours`."""
    rows = [(t.isoformat(), "" if t in empty_hours else "5.0") for t in ts]
    raw = raw_frame(rows).assign(id_compteur=cid, id=site, nom_compteur=name)
    return prepare.normalize(raw, cid, (hours[0], hours[-1]))


def test_network_gap_seulement_sur_les_compteurs_actifs():
    hours = pd.date_range("2026-03-02T00:00Z", periods=48, freq="h")
    gap = hours[20:24]
    ok = hours[~hours.isin(gap)]
    items = [_counter(f"c{i}", f"s{i}", f"Rue {i} N-S", ok, hours) for i in range(10)]
    items.append(_counter("vide", "sv", "Rue V N-S", hours, hours, empty_hours=set(gap)))
    items.append(_counter("tard", "st", "Rue T N-S", hours[30:], hours))  # installé après
    assert list(prepare.mark_network_gaps(items)) == list(gap)

    def gap_flags(p):
        return p.counts.loc[p.counts["ts"].isin(gap), "flags"].tolist()

    assert gap_flags(items[0]) == [["missing", "network_gap"]] * 4
    # Valeur vide pendant la panne : 'network_gap' avec 'empty_value', sans 'missing'
    assert gap_flags(items[-2]) == [["empty_value", "network_gap"]] * 4
    # Pas encore installé : pas de 'network_gap'
    assert gap_flags(items[-1]) == [["missing"]] * 4
    assert items[-1].report["n_network_gap_hours"] == 0


def test_direction_checks_site_avec_un_sens_manquant_et_site_vide():
    hours = pd.date_range("2026-03-02T00:00Z", periods=3, freq="h")
    items = [
        _counter("a", "s1", "Rue A N-S", hours, hours),
        _counter("b", "s1", "Rue A", hours, hours),  # pas de sens dans le nom
        _counter("c", "", "Rue C N-S", hours, hours),  # site inconnu
        _counter("d", "", "Rue D N-S", hours, hours),  # site inconnu
    ]
    checks = prepare.direction_checks(items)
    assert checks["without_direction"] == ["b"]
    assert checks["n_sites_with_several_counters"] == 1  # s1 seul ; "" n'est pas un site
    assert checks["sites_not_opposite"] == [{"site_id": "s1", "directions": ["N-S", None]}]


def test_changement_d_heure_pas_controle_apres_l_arret():
    hours = pd.date_range("2026-03-25T00:00Z", "2026-04-02T00:00Z", freq="h")
    stopped = _counter("arret", "s1", "Rue A N-S", hours[hours < "2026-03-27"], hours)
    assert prepare.dst_days(stopped.counts) == {}
    running = _counter("actif", "s2", "Rue B N-S", hours, hours)
    assert prepare.dst_days(running.counts) == {dt.date(2026, 3, 29): (23, 23)}


def test_grille_commune_dates_sans_fuseau_en_heure_de_paris():
    raw = pd.DataFrame(
        {
            "id_compteur": CID,
            "date": ["2026-03-02T01:00:00", "2026-03-02T05:00:00"],  # sans fuseau (UTC+1)
        }
    )
    assert prepare.snapshot_range(raw) == (
        pd.Timestamp("2026-03-02T00:00Z"),
        pd.Timestamp("2026-03-02T04:00Z"),
    )


def test_acquire_export_complet_sans_filtre():
    url, params = acquire.export_url()
    assert "where" not in params and "where" not in url
    assert params["timezone"] == "UTC"
    assert params["select"].split(",") == acquire.EXPORT_COLUMNS
    assert {prepare.COLUMN_MAP[c] for c in acquire.EXPORT_COLUMNS} >= prepare.REQUIRED_COLUMNS


# ----------------------------------------------------------------- corrections du 15/11 au soir
def test_groupes_de_sites_ecrits_par_prepare(tmp_path, monkeypatch):
    """counters.csv contient les groupes dès prepare --tout, comme quality.py les écrirait."""
    from src.data import quality

    _network(tmp_path, monkeypatch, alias=True)
    prepare.prepare_all("flux-test")
    out = tmp_path / "processed" / "flux-test"
    k = pd.read_csv(out / "counters.csv", dtype=str).set_index("counter_id")
    assert k.loc["al", "site_group_id"] == k.loc["c0a", "site_group_id"] == "s0"  # 45 m
    assert k.loc["c1a", "site_group_id"] == k.loc["c1b", "site_group_id"] == "s1"
    assert k["site_group_id"].nunique() == 6  # s0 (+ s9), s1..s4, z
    # même règle que quality.py : relancer quality ne changerait rien
    expected = quality.candidate_site_groups(quality.load_counters(out / "counters.csv"))
    assert (k["site_group_id"] == expected.reindex(k.index)).all()
    manifest = json.loads((tmp_path / "manifests" / "flux-test.json").read_text())
    assert manifest["site_groups"]["n_groups"] == 6
    assert not any(x.startswith("site_group_id = site_id") for x in manifest["known_limitations"])
    assert not any(
        "relancer quality.py" in a for r in manifest["counters"].values() for a in r["alerts"]
    )


def test_manifeste_indique_le_brut_utilise(tmp_path, monkeypatch):
    _network(tmp_path, monkeypatch, n_sites=1)
    path = tmp_path / "manifests" / "flux-test.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    old = {"path": "data/history/flux-test/ancien_essai.csv", "role": "raw", "sha256": "x"}
    path.write_text(json.dumps({"snapshot_id": "flux-test", "files": [old], "sources": []}))
    prepare.prepare_all("flux-test")
    manifest = json.loads(path.read_text())
    assert manifest["raw_used_by_prepare"].endswith(acquire.RAW_ALL_FILENAME)
    raws = {f["path"]: f["used_by_prepare"] for f in manifest["files"] if f["role"] == "raw"}
    assert raws["data/history/flux-test/ancien_essai.csv"] is False


def test_telechargement_refuse_si_le_nom_n_est_pas_la_date_du_jour(tmp_path, monkeypatch):
    monkeypatch.setattr(acquire, "data_path", lambda key: tmp_path / key)
    monkeypatch.setattr(acquire, "relative_to_root", lambda p: str(p))

    def no_download(*args, **kwargs):
        raise AssertionError("aucun téléchargement ne doit partir")

    monkeypatch.setattr(acquire, "download", no_download)
    with pytest.raises(ValueError, match="Refusé"):
        acquire.acquire_all("flux-20000101")


def test_un_seul_seuil_network_gap():
    from src.data import quality

    assert prepare.NETWORK_GAP_SHARE == quality.SelectionCriteria.network_gap_share


# ----------------------------------------------------------------- fenêtre (17/11, Nihed)
def test_premier_jour_du_brut_ecarte(tmp_path, monkeypatch):
    """Le premier jour UTC du brut, rogné par la source, n'est pas sur la grille."""
    _network(tmp_path, monkeypatch)
    prepare.prepare_all("flux-test")
    c = pd.read_csv(tmp_path / "processed" / "flux-test" / "counts.csv", dtype=str)
    assert c["timestamp"].min() == "2026-08-21T00:00:00+00:00"
    assert c.groupby("counter_id").size().eq(96).all()
    assert not c["timestamp"].str.startswith("2026-08-20").any()
    grid = json.loads((tmp_path / "manifests" / "flux-test.json").read_text())["grid"]
    assert grid["raw_first_timestamp"] == "2026-08-20T00:00:00+00:00"
    assert grid["first_timestamp"] == "2026-08-21T00:00:00+00:00"
    assert grid["n_source_hours_outside_window"] == 6  # les 6 heures rognées de c0a
    assert "premier jour UTC" in grid["window_rule"]


def test_fenetre_commence_au_jour_suivant_minuit_utc():
    raw = pd.DataFrame(
        {"id_compteur": CID, "date": ["2026-03-02T16:00:00+00:00", "2026-03-05T22:00:00+00:00"]}
    )
    first, last, raw_first = prepare.grid_window(raw)
    assert raw_first == pd.Timestamp("2026-03-02T16:00Z")
    assert first == pd.Timestamp("2026-03-03T00:00Z")
    assert last == pd.Timestamp("2026-03-05T22:00Z")
    one_day = pd.DataFrame({"id_compteur": CID, "date": ["2026-03-02T16:00:00+00:00"]})
    with pytest.raises(ValueError):
        prepare.grid_window(one_day)

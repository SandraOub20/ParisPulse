"""Tests des archives annuelles (src/data/archives.py), sans réseau."""

import gzip
import io
import zipfile

import pandas as pd
import pytest

from src.data import archives as ar

HEADER = (
    "Identifiant du compteur,Nom du compteur,Identifiant du site de comptage,"
    "Nom du site de comptage,Comptage horaire,Date et heure de comptage\n"
)


def archive_bytes(rows: list[str], encoding: str = "latin-1") -> bytes:
    return (HEADER + "".join(r + "\n" for r in rows)).encode(encoding)


def write_zip(path, data: bytes) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("2024_comptage-velo-donnees-compteurs.csv", data)
    path.write_bytes(buf.getvalue())


ROWS = [
    "c1,Boulevard Sébastopol S-N,s1,Sébastopol,12,2024-03-01T10:00:00+01:00",
    "c1,Boulevard Sébastopol S-N,s1,Sébastopol,15,2024-03-01T11:00:00+01:00",
    "c1,Boulevard Sébastopol S-N,s1,Sébastopol,15,2024-03-01T11:00:00+01:00",
    "c2,Rue X,s2,Rue X,3,2024-03-01T10:00:00+01:00",
    "c2,Rue X,s2,Rue X,4,2024-03-01T10:00:00+01:00",
    "c2,Rue X,s2,Rue X,,2024-03-01T11:00:00+01:00",
]


def test_lit_un_zip_latin1_virgule_et_renomme_les_colonnes(tmp_path):
    p = tmp_path / "a.zip"
    write_zip(p, archive_bytes(ROWS))
    df, fmt = ar.read_archive(p)
    assert fmt["container"] == "zip" and fmt["encoding"] == "latin-1" and fmt["separator"] == ","
    assert {"counter_id", "count", "date_source", "counter_name"} <= set(df.columns)
    assert df["counter_name"].iloc[0] == "Boulevard Sébastopol S-N"
    assert fmt["unmapped_columns"] == []


def test_accepte_un_chemin_en_texte(tmp_path):
    p = tmp_path / "a.zip"
    write_zip(p, archive_bytes(ROWS))
    df, _ = ar.read_archive(str(p))
    assert len(df) == len(ROWS)


def test_lit_un_gzip_utf8_point_virgule(tmp_path):
    data = archive_bytes(ROWS, "utf-8").replace(b",", b";")
    p = tmp_path / "a.csv.gz"
    p.write_bytes(gzip.compress(data))
    df, fmt = ar.read_archive(p)
    assert fmt["container"] == "gzip" and fmt["separator"] == ";"
    assert fmt["encoding"].startswith("utf-8")
    assert len(df) == len(ROWS)


def test_inventaire_compte_doublons_conflits_et_vides(tmp_path):
    p = tmp_path / "a.zip"
    write_zip(p, archive_bytes(ROWS))
    df, _ = ar.read_archive(p)
    rep = ar.archive_report(df)
    assert rep["n_rows"] == 6 and rep["n_counters"] == 2
    assert rep["n_duplicate_keys"] == 2
    assert rep["n_duplicate_same_value"] == 1
    assert rep["n_duplicate_conflicts"] == 1
    assert rep["n_empty_counts"] == 1
    assert rep["n_dates_without_offset"] == 0
    assert rep["first_timestamp"] == "2024-03-01T09:00:00+00:00"


def test_dates_sans_fuseau_signalees():
    df = pd.DataFrame(
        {"counter_id": ["c1"], "count": ["2"], "date_source": ["2024-03-01 10:00:00"]}
    )
    rep = ar.archive_report(df)
    assert rep["n_dates_without_offset"] == 1
    assert rep["first_timestamp"] == "2024-03-01T09:00:00+00:00"
    assert rep["alerts"]


def test_virgule_decimale_acceptee():
    n = ar.parse_counts(pd.Series(["12,0", "3", "", "x"]))
    assert n.iloc[0] == 12 and n.iloc[1] == 3
    assert n.iloc[2:].isna().all()


def test_separateur_de_milliers_accepte():
    n = ar.parse_counts(pd.Series(["1\xa0007", "2\u202f491", "1 048"]))
    assert n.tolist() == [1007, 2491, 1048]


def test_choix_du_fichier_par_compteur_de_l_annee():
    atts = [
        {"title": "2024_comptage-velo-donnees-sites-comptage.zip", "href": "u1"},
        {"title": "2024_comptage-velo-donnees-compteurs.zip", "href": "u2"},
        {"title": "2025_comptage-velo-donnees-compteurs.zip", "href": "u3"},
    ]
    assert ar.pick_year(atts, 2024)["href"] == "u2"
    with pytest.raises(ValueError):
        ar.pick_year(atts, 2019)


def test_comparaison_avec_le_flux_sur_les_heures_communes():
    arc = pd.DataFrame(
        {
            "counter_id": ["c1", "c1", "c2", "c2"],
            "count": ["10", "20", "5", "0"],
            "date_source": [
                "2025-12-01T10:00:00+01:00",
                "2025-12-01T11:00:00+01:00",
                "2025-12-01T10:00:00+01:00",
                "2025-12-01T11:00:00+01:00",
            ],
        }
    )
    flux = pd.DataFrame(
        {
            "counter_id": ["c1", "c1", "c2", "c2"],
            "timestamp": [
                "2025-12-01T09:00:00+00:00",
                "2025-12-01T10:00:00+00:00",
                "2025-12-01T09:00:00+00:00",
                "2025-12-01T10:00:00+00:00",
            ],
            "count": ["10", "20", "10", "8"],
        }
    )
    cmp = ar.compare_with_flux(arc, flux).set_index("counter_id")
    assert cmp.loc["c1", "identical_share"] == 1.0
    assert cmp.loc["c2", "identical_share"] == 0.0
    assert cmp.loc["c2", "common_hours"] == 2
    assert cmp.loc["c2", "median_ratio"] == pytest.approx(0.25)


def test_deux_cycles_avant_le_flux():
    start, end = ar.history_window(pd.Timestamp("2025-10-16T00:00:00Z"), 2)
    assert start == pd.Timestamp("2023-10-16T00:00:00Z")
    assert end == pd.Timestamp("2025-10-16T00:00:00Z")
    assert ar.years_for(start, end) == [2023, 2024, 2025]


def test_un_cycle_qui_finit_le_31_decembre_ne_demande_pas_l_annee_suivante():
    start, end = ar.history_window(pd.Timestamp("2026-01-01T00:00:00Z"), 1)
    assert ar.years_for(start, end) == [2025]
    with pytest.raises(ValueError):
        ar.history_window(pd.Timestamp("2026-01-01T00:00:00Z"), 0)


# ----------------------------------------------------------------- assemblage
def _setup_history(tmp_path, monkeypatch):
    """Archives sur 4 jours (jumeau dès le jour 3, une ligne sans id, un ancien compteur),
    puis un flux de 2 jours qui publie la somme ; cycles d'un jour remplacés par 3 jours."""
    import json

    from src.data import acquire, prepare

    for mod in (ar, acquire, prepare):
        monkeypatch.setattr(mod, "data_path", lambda key: tmp_path / key)
        monkeypatch.setattr(mod, "relative_to_root", lambda p: str(p))
    monkeypatch.setattr(
        ar,
        "history_window",
        lambda flux_start, cycles: (flux_start - pd.Timedelta(days=3), flux_start),
    )
    t0 = pd.Timestamp("2025-10-13T00:00Z")
    hours = pd.date_range(t0, periods=5 * 24, freq="h")  # 13/10 -> 17/10 inclus
    flux_start = pd.Timestamp("2025-10-16T00:00Z")
    twin_from = pd.Timestamp("2025-10-15T00:00Z")
    rows = []
    for t in hours:
        d = t.tz_convert("Europe/Paris").strftime("%Y-%m-%d %H:%M:%S.000 %z")
        rows.append(f"s1-103,Quai A,s1,Quai,5,{d}")
        if t >= twin_from:
            rows.append(f"s1-101,Quai A bis,s1,Quai,2,{d}")
        rows.append(f"s2-104,Rue B,s2,Rue B,3,{d}")
        if t < twin_from:
            rows.append(f"vieux-1,Ancien,s9,Ancien,1,{d}")
            rows.append(f"s3-109,Voie C,s3,Voie C,8,{d}")
        else:
            rows.append(f"s3-101,Voie C,s3,Voie C,8,{d}")
        rows.append(f",,,,999,{d}")
    arch = tmp_path / "history" / "archive-test" / "archives"
    arch.mkdir(parents=True)
    write_zip(arch / "2025-comptage-velo-donnees-compteurs.zip", archive_bytes(rows))

    flux_hours = hours[hours >= flux_start]
    raw = []
    for cid, site, name, n in (
        ("s1-103", "s1", "Quai A N-S", 7),
        ("s2-104", "s2", "Rue B S-N", 3),
        ("s3-109", "s3", "Voie C E-O", 8),
    ):
        for t in flux_hours:
            raw.append([cid, name, site, name, str(n), t.isoformat(), "2020-01-01", "48.8, 2.3"])
    raw = pd.DataFrame(raw, columns=ar.RAW_COLUMNS)
    fdir = tmp_path / "history" / "flux-test"
    fdir.mkdir(parents=True)
    raw.to_csv(fdir / "comptage-velo-donnees-compteurs__complet.csv", sep=";", index=False)
    counts = raw.rename(
        columns={"id_compteur": "counter_id", "date": "timestamp", "sum_counts": "count"}
    )
    pdir = tmp_path / "processed" / "flux-test"
    pdir.mkdir(parents=True)
    counts[["counter_id", "timestamp", "count"]].to_csv(pdir / "counts.csv", index=False)
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests" / "flux-test.json").write_text(
        json.dumps(
            {
                "grid": {
                    "first_timestamp": flux_start.isoformat(),
                    "last_timestamp": flux_hours[-1].isoformat(),
                },
                "files": [],
            }
        )
    )
    return hours, flux_start, twin_from


def test_assemblage_somme_jumeaux_ecarte_sans_id_et_anciens(tmp_path, monkeypatch):
    import json

    hours, flux_start, twin_from = _setup_history(tmp_path, monkeypatch)
    out = ar.assemble_history("hist-test", "archive-test", "flux-test", cycles=1)
    m = json.loads((tmp_path / "manifests" / "hist-test.json").read_text())["history"]
    assert m["twins"] == {"s1-103": "s1-101"}
    assert m["renames"] == {"s3-109": "s3-101"}
    assert m["n_rows_without_counter_id"] == len(hours)
    assert [d["counter_id"] for d in m["excluded_archive_only"]] == ["vieux-1"]

    a = pd.read_csv(out, sep=";", dtype=str)
    a["ts"] = pd.to_datetime(a["date"], utc=True, format="ISO8601")
    s1 = a[a["id_compteur"] == "s1-103"].set_index("ts")["sum_counts"].astype(int)
    start = flux_start - pd.Timedelta(days=3)
    assert s1.index.min() == start
    assert (s1[s1.index < twin_from] == 5).all()  # avant le jumeau : canal seul
    hist_part = s1[(s1.index >= twin_from) & (s1.index < flux_start)]
    assert (hist_part == 7).all()  # 5 + 2, comme le flux
    assert (s1[s1.index >= flux_start] == 7).all()
    assert set(a["id_compteur"]) == {"s1-103", "s2-104", "s3-109"}
    s3 = a[a["id_compteur"] == "s3-109"].set_index("ts")["sum_counts"].astype(int)
    assert len(s3[s3.index < flux_start]) == 3 * 24  # 109 puis 101 : historique complet
    assert (s3 == 8).all()


def test_assemblage_puis_preparation_sur_toute_la_fenetre(tmp_path, monkeypatch):
    from src.data import prepare

    hours, flux_start, _ = _setup_history(tmp_path, monkeypatch)
    ar.assemble_history("hist-test", "archive-test", "flux-test", cycles=1)
    items = prepare.prepare_all("hist-test")
    c = pd.read_csv(tmp_path / "processed" / "hist-test" / "counts.csv", dtype=str)
    n_hours = 3 * 24 + 2 * 24  # 3 jours d'archives + 2 jours de flux, sans jour écarté
    assert len(items) == 3
    assert c.groupby("counter_id").size().eq(n_hours).all()
    assert c["timestamp"].min() == (flux_start - pd.Timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )
    assert (c["is_observed"] == "true").all()

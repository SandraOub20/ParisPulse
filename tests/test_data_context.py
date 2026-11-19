"""Tests de src/data/context.py sur des sources synthétiques au format réel."""

from __future__ import annotations

import datetime as dt
import gzip
import json

import pandas as pd
import pytest

from src.data import context as c

TZ = "Europe/Paris"


# ----------------------------------------------------------------- sources synthétiques
def holidays_json() -> bytes:
    return json.dumps(
        {"2026-07-14": "14 juillet", "2026-11-01": "1er novembre", "2026-11-11": "11 novembre"}
    ).encode()


def school_csv() -> bytes:
    rows = [
        # Toussaint 2025, zone C, Paris : du samedi 18/10 au lundi 03/11 (reprise)
        (
            "Vacances de la Toussaint",
            "-",
            "2025-10-17T22:00:00+00:00",
            "2025-11-02T23:00:00+00:00",
            "Paris",
            "Zone C",
            "2025-2026",
        ),
        # même période pour une autre académie de la zone C : doublon à supprimer
        (
            "Vacances de la Toussaint",
            "-",
            "2025-10-17T22:00:00+00:00",
            "2025-11-02T23:00:00+00:00",
            "Créteil",
            "Zone C",
            "2025-2026",
        ),
        # dates différentes pour Créteil : ignorées car Paris existe cette année-là
        (
            "Vacances d'Hiver",
            "-",
            "2026-02-06T23:00:00+00:00",
            "2026-02-22T23:00:00+00:00",
            "Créteil",
            "Zone C",
            "2025-2026",
        ),
        (
            "Vacances d'Hiver",
            "-",
            "2026-02-20T23:00:00+00:00",
            "2026-03-08T23:00:00+00:00",
            "Paris",
            "Zone C",
            "2025-2026",
        ),
        # enseignants et zone A : exclus
        (
            "Pré-rentrée",
            "Enseignants",
            "2026-08-30T22:00:00+00:00",
            "2026-08-31T22:00:00+00:00",
            "Paris",
            "Zone C",
            "2026-2027",
        ),
        (
            "Vacances d'Hiver",
            "-",
            "2026-02-06T23:00:00+00:00",
            "2026-02-22T23:00:00+00:00",
            "Lyon",
            "Zone A",
            "2025-2026",
        ),
    ]
    head = "description;population;start_date;end_date;location;zones;annee_scolaire"
    return ("﻿" + head + "\n" + "\n".join(";".join(r) for r in rows)).encode()


def forecast_json(start: str, hours: int, lead: int, wind_unit: str = "m/s") -> bytes:
    times = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    return json.dumps(
        {
            "hourly_units": {f"wind_speed_10m_previous_day{lead}": wind_unit},
            "hourly": {
                "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
                f"temperature_2m_previous_day{lead}": [10.0 + i % 5 for i in range(hours)],
                f"precipitation_previous_day{lead}": [0.0] * hours,
                f"wind_speed_10m_previous_day{lead}": [3.0] * hours,
            },
        }
    ).encode()


def meteofrance_gz(start: str, hours: int) -> bytes:
    times = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    lines = ["NUM_POSTE;NOM_USUEL;AAAAMMJJHH;RR1;T;FF"]
    for i, t in enumerate(times):
        lines.append(f"75114001;PARIS-MONTSOURIS;{t:%Y%m%d%H};0,2;{12 + i % 3},5;4,1")
        lines.append(f"75106001;LUXEMBOURG;{t:%Y%m%d%H};9;99;9")
    return gzip.compress("\n".join(lines).encode())


# ----------------------------------------------------------------- calendrier
def test_jours_feries_une_seule_ligne_par_jour_avec_le_nom():
    days = c.local_dates(dt.date(2026, 7, 13), dt.date(2026, 7, 15))
    ctx = c._frame(c.holiday_rows(c.parse_holidays(holidays_json()), days))
    c.validate_context(ctx)
    assert len(ctx) == 3  # une ligne par jour, plus de ligne holiday_name
    assert set(ctx["variable"]) == {"is_holiday"}
    by_day = ctx.set_index("local_date")
    assert by_day["value"].to_dict() == {
        "2026-07-13": "false",
        "2026-07-14": "true",
        "2026-07-15": "false",
    }
    assert by_day["label"].to_dict() == {
        "2026-07-13": "",
        "2026-07-14": "14 juillet",
        "2026-07-15": "",
    }
    assert set(ctx["role"]) == {c.ROLE_CALENDAR} and set(ctx["available_at"]) == {""}


def test_vacances_zone_c_filtres_et_jour_de_reprise_exclu():
    periods, alerts = c.parse_school(school_csv())
    assert alerts == []
    # Toussaint (doublon fusionné) + hiver de Paris ; ni enseignants, ni zone A, ni Créteil
    assert len(periods) == 2
    days = c.local_dates(dt.date(2025, 10, 17), dt.date(2025, 11, 3))
    ctx = c._frame(c.school_rows(periods, days))
    flags = ctx[ctx["variable"] == "is_school_holiday"].set_index("local_date")["value"]
    assert flags["2025-10-17"] == "false"  # vendredi, dernier jour de classe
    assert flags["2025-10-18"] == "true"
    assert flags["2025-10-26"] == "true"  # jour de passage à l'heure d'hiver
    assert flags["2025-11-02"] == "true"
    assert flags["2025-11-03"] == "false"  # jour de reprise
    labels = ctx.set_index("local_date")["label"]
    assert labels["2025-10-18"] == "Vacances de la Toussaint"
    assert labels["2025-11-03"] == ""
    assert set(ctx["variable"]) == {"is_school_holiday"}
    hiver = c._frame(
        c.school_rows(periods, c.local_dates(dt.date(2026, 2, 9), dt.date(2026, 2, 9)))
    )
    assert hiver.loc[hiver["variable"] == "is_school_holiday", "value"].item() == "false"


# ----------------------------------------------------------------- météo prévue
@pytest.mark.parametrize("lead, all_admissible", [(2, True), (1, False)])
def test_prevision_disponible_avant_l_origine_sur_24_horizons(lead, all_admissible):
    origin = pd.Timestamp("2026-06-10", tz=TZ).tz_convert("UTC")  # minuit local
    rows, info, alerts = c.parse_forecast(forecast_json("2026-06-08", 24 * 5, lead), lead)
    ctx = c._frame(rows)
    targets = ctx[
        pd.to_datetime(ctx["valid_time"], utc=True).between(
            origin + pd.Timedelta(hours=1), origin + pd.Timedelta(hours=24)
        )
    ]
    assert targets["valid_time"].nunique() == 24
    ok = pd.to_datetime(targets["available_at"], utc=True) <= origin
    assert bool(ok.all()) is all_admissible
    assert set(targets["role"]) == {c.ROLE_FORECAST} and set(targets["issued_at"]) == {""}


def test_prevision_unite_du_vent_controlee():
    with pytest.raises(ValueError, match="Unité du vent"):
        c.parse_forecast(forecast_json("2026-06-08", 24, 2, wind_unit="km/h"), 2)


# ----------------------------------------------------------------- météo observée
def test_observations_station_utc_unites_et_disponibilite():
    rows, info = c.parse_observed(meteofrance_gz("2026-06-10", 3))
    ctx = c._frame(rows)
    assert info["n_station_rows"] == 3  # Luxembourg exclu
    temp = ctx[ctx["variable"] == "temp_obs"]
    assert temp["value"].tolist() == ["12.5", "13.5", "14.5"]  # virgule décimale lue
    assert temp["valid_time"].iloc[0] == "2026-06-10T00:00:00+00:00"
    assert temp["available_at"].iloc[0] == "2026-06-11T00:00:00+00:00"
    assert set(ctx["unit"]) == {"degC", "mm", "m/s"}


def test_le_futur_ne_change_pas_le_contexte_admissible():
    origin = pd.Timestamp("2026-06-12", tz=TZ).tz_convert("UTC")
    ctx = c._frame(c.parse_observed(meteofrance_gz("2026-06-09", 24 * 5))[0])
    futur = ctx.copy()
    after = pd.to_datetime(futur["available_at"], utc=True) > origin
    futur.loc[after, "value"] = "999.0"
    assert c.admissible_context(ctx, origin).equals(c.admissible_context(futur, origin))
    admissible = c.admissible_context(ctx, origin)
    assert (pd.to_datetime(admissible["available_at"], utc=True) <= origin).all()


# ----------------------------------------------------------------- jointure
def counts_frame(start_local: str, hours: int, counters=("A", "B")) -> pd.DataFrame:
    start = pd.Timestamp(start_local, tz=TZ).tz_convert("UTC")
    ts = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    rows = []
    for cid in counters:
        for t in ts:
            rows.append(
                {
                    "counter_id": cid,
                    "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "interval_end": (t + pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                }
            )
    return pd.DataFrame(rows)


def test_jointure_ni_creation_ni_perte_jour_de_25_heures():
    counts = counts_frame("2026-10-25", 25)  # journée locale de 25 h
    days = c.local_dates(dt.date(2026, 10, 24), dt.date(2026, 10, 26))
    ctx = c._frame(
        c.holiday_rows(c.parse_holidays(holidays_json()), days)
        + c.parse_observed(meteofrance_gz("2026-10-24T20:00", 40))[0]
    )
    joined, audit = c.join_context(counts, ctx)
    assert len(joined) == len(counts) == audit["n_rows_after"]
    assert (joined["local_date"] == "2026-10-25").all()  # les deux heures « 2 h » comprises
    assert audit["is_holiday"]["n_unmatched"] == 0
    assert audit["is_holiday_label"]["n_unmatched"] == 0
    assert audit["temp_obs"]["n_unmatched"] == 0
    # la météo décrit la même heure que le comptage : jointure sur interval_end
    first = joined.iloc[0]
    assert first["interval_end"] == "2026-10-24T23:00:00+00:00"


def test_jointure_signale_les_heures_sans_contexte():
    counts = counts_frame("2026-06-10", 48)
    ctx = c._frame(c.parse_observed(meteofrance_gz("2026-06-09T23:00", 24))[0])
    _, audit = c.join_context(counts, ctx)
    assert audit["temp_obs"]["n_unmatched"] == 2 * 24
    assert audit["temp_obs"]["unmatched_share"] == 0.5


def test_jointure_donne_le_nom_du_jour_ferie():
    counts = counts_frame("2026-07-14", 2)
    days = c.local_dates(dt.date(2026, 7, 14), dt.date(2026, 7, 14))
    ctx = c._frame(c.holiday_rows(c.parse_holidays(holidays_json()), days))
    joined, _ = c.join_context(counts, ctx)
    assert set(joined["is_holiday"]) == {"true"}
    assert set(joined["is_holiday_label"]) == {"14 juillet"}


def test_migration_de_l_ancien_format():
    def old_row(src, day, var, value, unit):
        return {
            "context_source_id": src,
            "location_id": "L",
            "valid_time": "",
            "local_date": day,
            "variable": var,
            "value": value,
            "unit": unit,
            "role": c.ROLE_CALENDAR,
            "issued_at": "",
            "available_at": "",
            "context_version": "e1-context/0.1.0",
        }

    old = pd.DataFrame(
        [
            old_row(c.SRC_HOLIDAYS, "2025-11-01", "is_holiday", "true", "bool"),
            old_row(c.SRC_HOLIDAYS, "2025-11-01", "holiday_name", "Toussaint", "text"),
            old_row(c.SRC_HOLIDAYS, "2025-11-02", "is_holiday", "false", "bool"),
            old_row(c.SRC_HOLIDAYS, "2025-11-02", "holiday_name", "", "text"),
            old_row(c.SRC_SCHOOL, "2025-11-01", "is_school_holiday", "true", "bool"),
            old_row(c.SRC_SCHOOL, "2025-11-01", "school_holiday_name", "Vacances", "text"),
            {
                **old_row("meteo_observee", "", "temp_obs", "12.5", "degC"),
                "valid_time": "2025-11-01T00:00:00+00:00",
                "role": c.ROLE_OBSERVATION,
            },
        ]
    )
    new = c.migrate_calendar(old)
    c.validate_context(new)
    assert list(new.columns) == c.CONTEXT_COLUMNS
    assert len(new) == 4  # les 3 lignes de nom sont retirées
    lab = new.set_index(["variable", "local_date"])["label"]
    assert lab[("is_holiday", "2025-11-01")] == "Toussaint"
    assert lab[("is_holiday", "2025-11-02")] == ""
    assert lab[("is_school_holiday", "2025-11-01")] == "Vacances"
    assert lab[("temp_obs", "")] == ""
    assert set(new["context_version"]) == {c.CONTEXT_VERSION}
    assert new["value"].tolist() == ["true", "false", "true", "12.5"]  # valeurs inchangées


def test_contexte_en_double_refuse():
    rows = c.holiday_rows(c.parse_holidays(holidays_json()), [dt.date(2026, 7, 14)])
    with pytest.raises(ValueError, match="en double"):
        c.validate_context(c._frame(rows + rows))


def test_colonnes_conformes_au_gabarit():
    from pathlib import Path

    header = (Path(c.__file__).parents[2] / "doc/templates/context.csv").read_text().strip()
    assert header.split(",") == c.CONTEXT_COLUMNS


# ----------------------------------------------------------------- chaîne complète hors ligne
def test_build_context_hors_ligne(monkeypatch, tmp_path):
    listing = {
        "resources": [
            {"title": "HOR_departement_75_periode_2025-2026", "url": "mf-2025"},
            {"title": "HOR_departement_75_periode_2010-2019", "url": "mf-2010"},
            {"title": "HOR_departement_92_periode_2025-2026", "url": "mf-92"},
        ]
    }
    payload = {
        c.URL_HOLIDAYS: holidays_json(),
        c.URL_SCHOOL: school_csv(),
        c.URL_FORECAST: forecast_json("2026-07-12", 24 * 5, 2),
        c.URL_METEOFRANCE_DATASET: json.dumps(listing).encode(),
        "mf-2025": meteofrance_gz("2026-07-12", 24 * 5),
    }
    asked = []

    def fake_fetch(url, dest, params=None, force=False):
        asked.append(url)
        return payload[url]

    monkeypatch.setattr(c, "fetch", fake_fetch)
    monkeypatch.setattr(c, "context_dir", lambda sid: tmp_path)
    monkeypatch.setattr(c, "relative_to_root", lambda p: str(p))
    start = pd.Timestamp("2026-07-13", tz=TZ).tz_convert("UTC")
    end = pd.Timestamp("2026-07-15", tz=TZ).tz_convert("UTC")
    ctx, sheets, raw = c.build_context("test", start, end)
    assert "mf-2010" not in asked and "mf-92" not in asked
    assert set(ctx["context_source_id"]) == set(c.SOURCES)
    assert set(sheets) == set(c.SOURCES)
    assert ctx.loc[ctx["variable"] == "is_holiday", "local_date"].nunique() == 3
    weather = pd.to_datetime(ctx.loc[ctx["valid_time"] != "", "valid_time"], utc=True)
    assert weather.min() >= start and weather.max() <= end + pd.Timedelta(hours=1)


# ----------------------------------------------------------------- hypothèses de disponibilité
def test_hypotheses_lues_dans_la_configuration(monkeypatch):
    monkeypatch.setattr(
        c,
        "load_config",
        lambda: {
            "context": {
                "forecast_lead_days": 3,
                "run_publication_delay_hours": 12,
                "obs_publication_lag_hours": 48,
            }
        },
    )
    s = c.availability_settings()
    assert (
        s["forecast_lead_days"],
        s["run_publication_delay_hours"],
        s["obs_publication_lag_hours"],
    ) == (3, 12, 48)
    assert "12 h" in c.availability_text(c.SRC_FORECAST, s)


def test_hypotheses_par_defaut_sans_section_context(monkeypatch):
    monkeypatch.setattr(c, "load_config", lambda: {})
    s = c.availability_settings()
    assert (s["forecast_lead_days"], s["run_publication_delay_hours"]) == (2, 6)
    assert s["obs_publication_lag_hours"] == 24


def test_delai_de_publication_applique():
    rows, _, _ = c.parse_forecast(forecast_json("2026-06-10", 24, 2), 2, run_delay_h=12)
    first = c._frame(rows).iloc[0]
    assert first["valid_time"] == "2026-06-10T00:00:00+00:00"
    assert first["available_at"] == "2026-06-08T12:00:00+00:00"  # -48 h + 12 h
    obs, _ = c.parse_observed(meteofrance_gz("2026-06-10", 1), lag_h=48)
    assert c._frame(obs).iloc[0]["available_at"] == "2026-06-12T00:00:00+00:00"


def test_prevision_jma_avant_2024_puis_modele_par_defaut():
    segs = c.forecast_segments(dt.date(2023, 10, 16), dt.date(2026, 11, 14))
    assert [s["model"] for s in segs] == ["jma_gsm", None]
    assert segs[0]["start"] == dt.date(2023, 10, 15) and segs[0]["end"] == dt.date(2024, 3, 1)
    assert segs[1]["start"] == dt.date(2024, 1, 1) and segs[1]["end"] == dt.date(2026, 11, 14)
    assert segs[0]["location_id"] != segs[1]["location_id"]
    seul = c.forecast_segments(dt.date(2025, 10, 16), dt.date(2026, 11, 14))
    assert len(seul) == 1 and seul[0]["model"] is None and seul[0]["start"] == dt.date(2025, 10, 15)
    assert c.forecast_params(dt.date(2023, 1, 1), dt.date(2023, 1, 2), 2, "jma_gsm")["models"] == (
        "jma_gsm"
    )
    assert "models" not in c.forecast_params(dt.date(2025, 1, 1), dt.date(2025, 1, 2), 2)


def test_cles_suffixees_par_le_modele_acceptees():
    import json as js

    raw = js.dumps(
        {
            "hourly": {
                "time": ["2023-12-01T10:00"],
                "temperature_2m_previous_day2_jma_gsm": [5.0],
                "precipitation_previous_day2_jma_gsm": [0.2],
                "wind_speed_10m_previous_day2_jma_gsm": [3.0],
            },
            "hourly_units": {"wind_speed_10m_previous_day2_jma_gsm": "m/s"},
        }
    ).encode()
    rows, _, _ = c.parse_forecast(raw, 2, location_id="x", model="jma_gsm")
    assert {r["variable"] for r in rows} == {"temp_prev", "rain_prev", "wind_prev"}
    assert all(r["location_id"] == "x" for r in rows)


def test_bascule_unique_vers_le_modele_par_defaut():
    def r(t, loc):
        return {"valid_time": t, "location_id": loc, "variable": "temp_prev", "value": 1.0}

    jma = [r(f"2024-01-{d:02d}T00:00:00+00:00", "jma") for d in range(1, 26)]
    defaut = [r(f"2024-01-{d:02d}T00:00:00+00:00", "def") for d in range(21, 26)]
    rows, switch = c.merge_forecast_segments(jma, defaut)
    assert switch == "2024-01-21T00:00:00+00:00"
    assert [x["location_id"] for x in rows].count("jma") == 20
    assert len({x["valid_time"] for x in rows}) == len(rows) == 25
    assert c.merge_forecast_segments(jma, []) == (jma, None)


# ----------------------------------------------------------------- grèves (B4)
def strikes_files() -> tuple[bytes, bytes]:
    daily = "date,greve\n2026-11-04,false\n2026-11-05,true\n2026-11-06,false\n"
    sources = (
        "date,scope,networks,severity,description,announced_on,source_url,confidence\n"
        "2026-11-05,interprofessionnel,metro;rer,forte,texte,,https://exemple,haute\n"
    )
    return daily.encode(), sources.encode()


def test_greves_une_ligne_par_jour_connue_24_h_avant():
    strikes = c.parse_strikes(*strikes_files())
    days = [dt.date(2026, 11, d) for d in (3, 4, 5, 6)]
    ctx = c._frame(c.strike_rows(strikes, days))
    assert ctx["local_date"].tolist() == ["2026-11-04", "2026-11-05", "2026-11-06"]  # 03 inconnu
    row = ctx.set_index("local_date").loc["2026-11-05"]
    assert row["value"] == "true" and row["label"] == "interprofessionnel, forte (metro;rer)"
    # minuit le 05/11 à Paris = 04/11 23:00 UTC ; connu 24 h avant
    assert row["available_at"] == "2026-11-03T23:00:00+00:00"
    assert ctx.set_index("local_date").loc["2026-11-04", "label"] == ""
    c.validate_context(ctx)


def test_greve_admissible_seulement_24_h_avant():
    ctx = c._frame(c.strike_rows(c.parse_strikes(*strikes_files()), [dt.date(2026, 11, 5)]))
    hol = c._frame(c.holiday_rows(c.parse_holidays(holidays_json()), [dt.date(2026, 11, 11)]))
    both = pd.concat([ctx, hol], ignore_index=True)
    j_moins_2 = pd.Timestamp("2026-11-03", tz=TZ).tz_convert("UTC")
    j_moins_1 = pd.Timestamp("2026-11-04", tz=TZ).tz_convert("UTC")
    assert set(c.admissible_context(both, j_moins_2)["variable"]) == {"is_holiday"}
    assert set(c.admissible_context(both, j_moins_1)["variable"]) == {"is_holiday", "is_strike"}


def test_jointure_greves_sur_la_date_de_paris():
    days = [dt.date(2026, 11, 4), dt.date(2026, 11, 5)]
    ctx = c._frame(c.strike_rows(c.parse_strikes(*strikes_files()), days))
    counts = counts_frame("2026-11-04 22:00", 3)  # 22 h, 23 h le 04, puis 00 h le 05 (Paris)
    out, audit = c.join_context(counts, ctx)
    assert audit["n_rows_before"] == audit["n_rows_after"]
    a = out[out["counter_id"] == "A"]["is_strike"].tolist()
    assert a == ["false", "false", "true"]

"""Vérification de la livraison hist-20261117, côté consommateur - E1, Tasnim (24/11/2026).

Contrôle, sur les fichiers du zip seuls, chaque affirmation du message de livraison
(livraison/README.md) : grille, remplacements J-7 et année d'avant, masque is_scoreable,
network_gap, statuts, sites réservés à E3, contexte, empreintes du manifeste, et
continuité avec flux-20261115 s'il est présent. N'écrit rien : affiche OK ou ÉCART.

Fiche : reports/experiments/E1-verification-livraison.md

Usage (à la racine du dépôt, après unzip de livraison/hist-20261117.zip) :
  uv run python -m src.data.verify_delivery
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
D = ROOT / "data/processed/hist-20261117"
TZ = "Europe/Paris"
R = {}


def ok(name, cond, detail=""):
    R[name] = (bool(cond), detail)
    print(("OK  " if cond else "ÉCART ") + name + (f" : {detail}" if detail else ""))


# --- empreintes
man = json.loads((ROOT / "data/manifests/hist-20261117.json").read_text())
for f in man["files"]:
    p = ROOT / f["path"]
    if p.exists():
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        ok(f"sha256 {p.name}", h == f["sha256"])
    else:
        print(f"--  absent localement : {f['path']}")

# --- counts
c = pd.read_csv(D / "counts.csv", dtype=str, keep_default_na=False)
ok("toutes les heures en UTC (+00:00)", c["timestamp"].str.endswith("+00:00").all())
c["ts"] = pd.to_datetime(c["timestamp"], utc=True, format="ISO8601")
c["cnt"] = pd.to_numeric(c["count"].replace("", np.nan))
c["raw"] = pd.to_numeric(c["count_raw"].replace("", np.nan))
c["obs"] = c["is_observed"].eq("true")
c["sc"] = c["is_scoreable"].eq("true")
fl = c["quality_flags"].map(json.loads)
for f in ["missing", "empty_value", "long_zero_run", "network_gap"]:
    c[f] = fl.map(lambda flags, f=f: f in flags)
print("drapeaux présents :", sorted({x for flags in fl for x in flags}))

n_ctr, n_h = c["counter_id"].nunique(), c["ts"].nunique()
ok("113 compteurs", n_ctr == 113, n_ctr)
ok("27 023 heures", n_h == 27023, n_h)
ok("3 053 599 lignes", len(c) == 3053599, len(c))
ok(
    "grille complète, sans doublon",
    not c.duplicated(["counter_id", "ts"]).any() and len(c) == n_ctr * n_h,
)
ok(
    "début 16/10/2023 00:00 UTC",
    c["ts"].min() == pd.Timestamp("2023-10-16", tz="UTC"),
    c["ts"].min(),
)
ok(
    "fin 14/11/2026 22:00 UTC",
    c["ts"].max() == pd.Timestamp("2026-11-14 22:00", tz="UTC"),
    c["ts"].max(),
)
ok(
    "grille horaire régulière",
    (pd.Series(sorted(c["ts"].unique())).diff().dropna() == pd.Timedelta(hours=1)).all(),
)
ok(
    "interval_end = timestamp + 1 h",
    (
        pd.to_datetime(c["interval_end"], utc=True, format="ISO8601") - c["ts"]
        == pd.Timedelta(hours=1)
    ).all(),
)

# --- remplacements
j7 = ~c["obs"] & c["cnt"].notna()
yr = c["obs"] & ~c["sc"] & c["cnt"].gt(0) & c["raw"].eq(0)
ok("18 385 heures remplies par J-7", j7.sum() == 18385, int(j7.sum()))
ok("J-7 : drapeau missing ou empty_value", (c.loc[j7, "missing"] | c.loc[j7, "empty_value"]).all())
ok(
    "J-7 : count_raw vide, is_scoreable faux",
    c.loc[j7, "raw"].isna().all() and (~c.loc[j7, "sc"]).all(),
)
# valeur = même heure de Paris 7 jours avant, mesurée
wall = c.loc[j7, "ts"].dt.tz_convert(TZ).dt.tz_localize(None) - pd.Timedelta(days=7)
prev = wall.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
key = c.set_index(["counter_id", "ts"])
look = key.reindex(pd.MultiIndex.from_arrays([c.loc[j7, "counter_id"], prev]))
# J-7 lit les données d'origine : un zéro de J-7 remplacé ensuite par l'année d'avant
# garde son 0 d'origine (count_raw) dans l'heure remplie.
orig_sc = look["sc"].fillna(False) | (look["obs"].fillna(False) & look["raw"].eq(0))
ok(
    "J-7 : valeur = mesure d'origine de J-7 (count_raw)",
    np.array_equal(look["raw"].to_numpy(), c.loc[j7, "cnt"].to_numpy()),
)
ok("J-7 : la source J-7 est une vraie mesure", orig_sc.all())
print(
    "   dont J-7 = zéro remplacé depuis par l'année d'avant :",
    int((look["cnt"].to_numpy() != c.loc[j7, "cnt"].to_numpy()).sum()),
)

ok("17 965 heures remplacées par l'année d'avant", yr.sum() == 17965, int(yr.sum()))
ok("année d'avant : drapeau long_zero_run", c.loc[yr, "long_zero_run"].all())


def shift_year(t):
    w = t.tz_convert(TZ).tz_localize(None) - pd.DateOffset(years=1)
    return w.tz_localize(TZ, ambiguous=True, nonexistent="shift_forward").tz_convert("UTC")


prev_y = pd.Series([shift_year(t) for t in c.loc[yr, "ts"]])
look_y = key.reindex(pd.MultiIndex.from_arrays([c.loc[yr, "counter_id"].to_numpy(), prev_y]))
ok(
    "année d'avant : valeur = même date/heure de Paris N-1",
    np.allclose(look_y["cnt"].to_numpy(), c.loc[yr, "cnt"].to_numpy()),
)
lzr_kept = c["long_zero_run"] & ~yr
ok(
    "suites non remplacées : le 0 reste et reste cible",
    c.loc[lzr_kept, "cnt"].eq(0).all() and c.loc[lzr_kept, "sc"].all(),
    int(lzr_kept.sum()),
)
ok("long_zero_run : count_raw = 0", c.loc[c["long_zero_run"], "raw"].eq(0).all())
filled = j7 | yr
ok("36 350 valeurs remplacées", filled.sum() == 36350, int(filled.sum()))
ok("remplacées : jamais is_scoreable", (~c.loc[filled, "sc"]).all())
real = c["obs"] & c["cnt"].notna() & (c["cnt"] == c["raw"])
ok("is_scoreable vrai ⇔ vraie mesure (count = count_raw, observée)", (c["sc"] == real).all())
ok(
    "zéros mesurés évaluables",
    c.loc[c["sc"] & c["raw"].eq(0)].shape[0] > 0,
    int((c["sc"] & c["raw"].eq(0)).sum()),
)
ok(
    "aucun count non vide qui ne soit ni mesure ni remplacement",
    (c["cnt"].notna() == (real | filled)).all(),
)
noval = (c["missing"] | c["empty_value"]) & c["cnt"].isna()
print("heures sans mesure restées vides :", int(noval.sum()))

# --- network_gap
ng_hours = c.loc[c["network_gap"], "ts"].nunique()
ok("104 heures network_gap", ng_hours == 104, ng_hours)
ok("network_gap jamais sur une vraie mesure", (~c.loc[c["network_gap"], "obs"]).all())
print(
    "network_gap remplies par J-7 :",
    int((c["network_gap"] & j7).sum()),
    "/",
    int(c["network_gap"].sum()),
)

# --- statuts
inv = pd.read_csv(D / "inventory_quality.csv", dtype=str, keep_default_na=False)
sel = inv[inv["period_role"] == "selection"]
st = sel["selection_status"].value_counts().to_dict()
ok(
    "statuts 67/30/5/10/1",
    st
    == {
        "retained": 67,
        "robustness": 30,
        "reserved_dev_new": 5,
        "reserved_test_new": 10,
        "excluded": 1,
    },
    st,
)
sites = sel.groupby("selection_status")["candidate_group_id"].nunique().to_dict()
ok(
    "4 sites dev, 5 sites test",
    sites["reserved_dev_new"] == 4 and sites["reserved_test_new"] == 5,
    sites,
)
print(
    "exclu :",
    sel.loc[sel["selection_status"] == "excluded", ["counter_id", "counter_name"]].values.tolist(),
)

# --- sites réservés
ctr = pd.read_csv(D / "counters.csv", dtype=str, keep_default_na=False).set_index("counter_id")
origin = {
    "reserved_dev_new": pd.Timestamp("2026-07-01", tz=TZ),
    "reserved_test_new": pd.Timestamp("2026-10-01", tz=TZ),
}
inst = {"reserved_dev_new": "2026-06-23", "reserved_test_new": "2026-09-23"}
rows = []
for _, r in sel[sel["selection_status"].isin(origin)].iterrows():
    cid, s = r["counter_id"], r["selection_status"]
    g = c[c["counter_id"] == cid]
    start = pd.Timestamp(inst[s], tz=TZ).tz_convert("UTC")
    o = origin[s].tz_convert("UTC")
    before = g[g["ts"] < start]
    known = g[(g["ts"] >= start) & (g["ts"] < o - pd.Timedelta(hours=24))]
    rows.append(
        {
            "counter_id": cid,
            "status": s,
            "installation_date": ctr.loc[cid, "installation_date"],
            "avant_vide": bool(
                before["cnt"].isna().all() and before["raw"].isna().all() and (~before["obs"]).all()
            ),
            "1re_mesure": g.loc[g["obs"], "ts"].min(),
            "mesures_connues_a_l_origine": int(known["sc"].sum()),
            "heures_support": len(known),
            "remplies_J7_dans_support": int((known["cnt"].notna() & ~known["obs"]).sum()),
        }
    )
res = pd.DataFrame(rows)
print(res.to_string())
ok(
    "installation_date = 23/06 ou 23/09",
    (res["installation_date"] == res["status"].map(inst)).all(),
)
ok("historique vidé avant installation", res["avant_vide"].all())
ok("support = 7 jours (168 h)", (res["heures_support"] == 168).all())
ok(
    "7 jours de MESURES connues à la 1re origine",
    (res["mesures_connues_a_l_origine"] == 168).all(),
    res.groupby("status")["mesures_connues_a_l_origine"].agg(["min", "max"]).to_dict("index"),
)

# --- contexte
ctx = pd.read_csv(D / "context.csv", dtype=str, keep_default_na=False)
cal = ctx[ctx["role"] == "known_calendar"]
for src in ["jours_feries", "vacances_zone_c", "greves_idf"]:
    s = cal[cal["context_source_id"] == src]
    ok(
        f"{src} : une ligne par jour",
        not s["local_date"].duplicated().any(),
        f"{len(s)} jours, {s['local_date'].min()} → {s['local_date'].max()}",
    )
    pos = s[s["value"].str.lower().eq("true")]
    print(
        f"   {src} : {len(pos)} jours vrais, label rempli {pos['label'].ne('').mean():.0%}, ex. {pos['label'].drop_duplicates().head(3).tolist()}"
    )
ok(
    "calendrier fériés/vacances : available_at vide",
    cal[cal["context_source_id"] != "greves_idf"]["available_at"].eq("").all(),
)
gr = cal[cal["context_source_id"] == "greves_idf"]
d_gr = (
    pd.to_datetime(gr["local_date"]).dt.tz_localize(TZ)
    - pd.to_datetime(gr["available_at"], utc=True)
).dt.total_seconds() / 3600
ok(
    "grèves : available_at = 24 h avant (minuit de Paris)",
    d_gr.eq(24).all(),
    d_gr.value_counts().to_dict(),
)
obs = ctx[ctx["role"] == "past_observation"]
d_obs = (
    pd.to_datetime(obs["available_at"], utc=True) - pd.to_datetime(obs["valid_time"], utc=True)
).dt.total_seconds() / 3600
ok(
    "météo observée : available_at = valid_time + 24 h",
    d_obs.eq(24).all(),
    d_obs.value_counts().head(3).to_dict(),
)
fc = ctx[ctx["role"] == "forecast_bulletin"]
d_fc = (
    pd.to_datetime(fc["valid_time"], utc=True) - pd.to_datetime(fc["available_at"], utc=True)
).dt.total_seconds() / 3600
print(
    "météo prévue : écart valid_time - available_at (h) :",
    d_fc.describe()[["min", "50%", "max"]].to_dict(),
)
d_iss = (
    pd.to_datetime(fc["valid_time"], utc=True) - pd.to_datetime(fc["issued_at"], utc=True)
).dt.total_seconds() / 3600
print(
    "météo prévue : écart valid_time - issued_at (h) :",
    d_iss.describe()[["min", "50%", "max"]].to_dict(),
)
print(
    "météo : heures par variable",
    ctx[ctx["role"] != "known_calendar"].groupby("variable").size().to_dict(),
)
grid_dates = sorted(set(c["ts"].drop_duplicates().dt.tz_convert(TZ).dt.date.astype(str)))
extra = sorted(set(cal["local_date"]) - set(grid_dates))
ok(
    "calendrier = dates de la grille",
    not extra and len(set(cal["local_date"])) == len(grid_dates),
    f"{len(grid_dates)} dates de grille ; en plus : {extra}",
)

# --- continuité archive / flux
ts_obs = c[c["obs"]].groupby("ts").size()
jx = ts_obs.loc["2025-10-14":"2025-10-18"]
print(
    "compteurs mesurés par heure autour de la jonction (min par jour) :",
    jx.groupby(jx.index.tz_convert(TZ).date).min().to_dict(),
)
flux = D.parent / "flux-20261115" / "counts.csv"
if flux.exists():
    fman = json.loads((ROOT / "data/manifests/flux-20261115.json").read_text())
    print(
        "flux-20261115 local :",
        fman.get("normalization_version"),
        "début",
        fman["grid"].get("first_timestamp"),
    )
    f = pd.read_csv(
        flux, dtype=str, keep_default_na=False, usecols=["counter_id", "timestamp", "count_raw"]
    )
    f["ts"] = pd.to_datetime(f["timestamp"], utc=True, format="ISO8601")
    reserved = set(res["counter_id"])
    m = c[["counter_id", "ts", "raw"]].merge(
        f[["counter_id", "ts", "count_raw"]], on=["counter_id", "ts"]
    )
    m["fr"] = pd.to_numeric(m["count_raw"].replace("", np.nan))
    m = m[~m["counter_id"].isin(reserved)]
    same = (m["raw"] == m["fr"]) | (m["raw"].isna() & m["fr"].isna())
    ok(
        "count_raw = flux-20261115 sur la période commune (hors sites réservés)",
        same.all(),
        f"{len(m)} lignes communes, {int((~same).sum())} différences, période {m['ts'].min()} → {m['ts'].max()}",
    )
    if (~same).any():
        print(m[~same].head(10).to_string())
        print(m[~same].groupby(m.loc[~same, "ts"].dt.date).size().head(10))
    ok(
        "mêmes compteurs que flux-20261115",
        set(f["counter_id"]) == set(c["counter_id"]),
        f"{f['counter_id'].nunique()} dans flux",
    )

fails = [k for k, (v, _) in R.items() if not v]
print("\nBILAN :", len(R) - len(fails), "OK,", len(fails), "écarts :", fails)

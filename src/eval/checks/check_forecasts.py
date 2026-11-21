"""Contrôles d'un fichier de prévisions d'E2 / E3.

    uv run python -m src.eval.check_forecasts fichier1.pred.csv [fichier2.pred.csv ...]
    e.g. uv run python -m src.eval.check_forecasts data/prediction_results/EXP-001/e2-reference_profile-measured.pred.csv data/prediction_results/EXP-001/e2-reference-measured.pred.csv
"""
import argparse

import pandas as pd

from src.common.config import ROOT, load_config

cfg = load_config()
cases_path = ROOT / cfg["paths"]["evaluation"] / cfg["protocol"]["id"] / "cases.csv"
counts_path = ROOT / cfg["paths"]["processed"] / cfg["snapshot_id"] / "counts.csv"
template_path = ROOT / "doc" / "templates" / "forecasts.csv"

ap = argparse.ArgumentParser()
ap.add_argument("preds", nargs="+")
args = ap.parse_args()


def say(ok, text):
    print(("OK  " if ok else "!!  ") + text)


cases = pd.read_csv(cases_path, dtype=str)
cases["origin"] = pd.to_datetime(cases["origin"], utc=True)
counts = pd.read_csv(counts_path, usecols=["counter_id", "timestamp"], dtype=str)
counts["timestamp"] = pd.to_datetime(counts["timestamp"], utc=True)
counts["in_counts"] = True
pred = pd.concat([pd.read_csv(p, dtype={"counter_id": str}) for p in args.preds], ignore_index=True)

print("1. Colonnes")
template = list(pd.read_csv(template_path).columns)
say(not [c for c in template if c not in pred.columns], f"manquantes : {[c for c in template if c not in pred.columns]}")
say(not [c for c in pred.columns if c not in template], f"en plus : {[c for c in pred.columns if c not in template]}")
empty = [c for c in pred.columns if pred[c].isna().all()]
print("    colonnes vides partout :", empty)

for col in ["origin", "target_timestamp", "fit_cutoff"]:
    pred[col] = pd.to_datetime(pred[col], utc=True)
pred["y_pred"] = pd.to_numeric(pred["y_pred"], errors="coerce")

print("\n2. Doublons et cas complets (par méthode)")
n = pred.duplicated(["case_id", "method_run_id", "horizon"]).sum()
say(n == 0, f"doublons (case_id, méthode, horizon) : {n}")
expected = set(cases["case_id"])
pred["has_value"] = pred["y_pred"].notna()
hours = pred.groupby(["method_run_id", "case_id"])["has_value"].sum().reset_index(name="h")
table = []
for run, g in hours.groupby("method_run_id"):
    table.append({"méthode": run, "attendus": len(expected), "sans ligne": len(expected - set(g["case_id"])),
                  "tous vides": int((g["h"] == 0).sum()), "partiels": int(((g["h"] > 0) & (g["h"] < 24)).sum()),
                  "complets": int((g["h"] == 24).sum())})
print(pd.DataFrame(table).to_string(index=False))
n = len(set(pred["case_id"]) - expected)
say(n == 0, f"cas livrés absents de cases.csv : {n}")
say(not (pred["y_pred"] < 0).any(), f"y_pred négatifs : {int((pred['y_pred'] < 0).sum())}")
print("    prediction_status :", pred["prediction_status"].value_counts(dropna=False).to_dict())
print("    method_used :", pred["method_used"].value_counts(dropna=False).to_dict())
print("    raisons :", pred["status_reason"].value_counts(dropna=False).head(4).to_dict())

print("\n3. Origines et heures")
m = pred.merge(cases[["case_id", "origin"]], on="case_id", how="left", suffixes=("", "_attendue"))
n = ((m["origin"] != m["origin_attendue"]) & m["origin_attendue"].notna()).sum()
say(n == 0, f"origine différente de cases.csv : {n}")
h1 = pred[pred["horizon"] == 1]
n = (h1["target_timestamp"] != h1["origin"]).sum()
say(n == 0, f"horizon 1 qui ne commence pas à l'origine : {n}")
bad = 0
for _, g in pred.groupby(["case_id", "method_run_id"]):
    if not (g.sort_values("horizon")["target_timestamp"].diff().dropna() == pd.Timedelta(hours=1)).all():
        bad += 1
say(bad == 0, f"cas dont les heures ne se suivent pas : {bad}")
j = pred.merge(counts, how="left", left_on=["counter_id", "target_timestamp"], right_on=["counter_id", "timestamp"])
n = j["in_counts"].isna().sum()
say(n == 0, f"heures prévues absentes de counts.csv : {n}")

print("\n4. Information disponible et séparation")
n = (pred["fit_cutoff"] > pred["origin"]).sum()
say(n == 0, f"fit_cutoff après l'origine : {n}")
n = pred["fit_cutoff"].isna().sum()
say(n == 0, f"fit_cutoff vide : {n} lignes")
test = cases[cases["temporal_split"] == "test"]
rows = pred[pred["case_id"].isin(test["case_id"])]
n = (rows["fit_cutoff"] > test["origin"].min()).sum()
say(n == 0, f"prévisions de test d'un modèle ajusté après le début du test : {n}")

print("\n5. Mêmes informations pour toutes les méthodes")
for col in ["snapshot_id", "protocol_id"]:
    n = (~pred[col].astype(str).isin(cases[col])).sum()
    say(n == 0, f"{col} différent de cases.csv : {n} lignes (valeurs : {sorted(pred[col].astype(str).unique())})")
new_sites = pred[pred["scenario"] == "new_site"]
if len(new_sites):
    n = (new_sites.groupby("case_id")["support_id"].nunique() > 1).sum()
    say(n == 0, f"cas de nouveaux sites avec plusieurs supports : {n}")

print("\n6. Couverture de cases.csv")
done = set(pred["case_id"])
for (scenario, split), g in cases.groupby(["scenario", "temporal_split"]):
    ids = set(g["case_id"])
    print(f"    {scenario}/{split} : {len(ids & done)} / {len(ids)}")

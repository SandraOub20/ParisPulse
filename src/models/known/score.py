"""Score des expériences E2, recalculable : appelle evaluate_all d'E4 sans le recopier.

Le calcul officiel reste celui d'E4 (src/eval/metrics.py) : MAE par compteur, puis moyenne
non pondérée entre compteurs, sur l'intersection des cas complets pour toutes les méthodes.
Ce module ne fait que charger les fichiers, appeler ce calcul et résumer le résultat, pour
qu'une expérience puisse être rescorée devant n'importe qui à partir des .pred.csv commités.

Deux lectures, comme dans les fiches :
- « système » : les replis comptent comme des prévisions (ce que voit l'application) ;
- « brut » : un repli d'un modèle appris devient une prévision absente (le modèle seul).
Les références (reference, reference_profile) n'ont pas de version brute distincte.

Exemple :
    python -m src.models.known.score --experiment EXP-E2
lit data/prediction_results/EXP-E2/ (les .pred.csv, ou à défaut ceux du zip), les cas de
validation known_site de proto-v1 et les mesures de l'instantané, puis écrit scores.json.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.eval import metrics

REFERENCE_VARIANTS = frozenset({"reference", "reference_profile"})
FORECAST_USECOLS = [
    "case_id",
    "method_run_id",
    "counter_id",
    "horizon",
    "target_timestamp",
    "y_pred",
    "variant",
    "prediction_status",
]
OBSERVATION_USECOLS = ["counter_id", "timestamp", "count", "is_observed", "is_scoreable"]


def load_cases(
    protocol_id: str = "proto-v1",
    *,
    scenario: str = "known_site",
    split: str = "validation",
    root: Path | None = None,
) -> pd.DataFrame:
    """Cas d'E4 d'un scénario et d'une période (validation ou test), en texte brut."""
    path = Path(root or data_path("evaluation")) / protocol_id / "cases.csv"
    cases = pd.read_csv(path, dtype=str, keep_default_na=False)
    chosen = cases[(cases["scenario"] == scenario) & (cases["temporal_split"] == split)]
    if chosen.empty:
        raise ValueError(f"aucun cas {scenario} / {split} dans {path}")
    return chosen.reset_index(drop=True)


def load_forecasts(experiment_dir: Path, methods: list[str] | None = None) -> pd.DataFrame:
    """Toutes les prévisions d'un dossier d'expérience.

    Lit les <method_run_id>.pred.csv du dossier ; s'il n'y en a aucun, les lit directement
    dans les .zip du dossier (la livraison commitée), sans rien extraire sur le disque.
    """
    experiment_dir = Path(experiment_dir)
    frames = []
    for path in sorted(experiment_dir.glob("*.pred.csv")):
        frames.append(_read_forecasts(path))
    if not frames:
        for archive in sorted(experiment_dir.glob("*.zip")):
            with zipfile.ZipFile(archive) as zf:
                for name in sorted(n for n in zf.namelist() if n.endswith(".pred.csv")):
                    with zf.open(name) as handle:
                        frames.append(_read_forecasts(handle))
    if not frames:
        raise FileNotFoundError(f"aucun .pred.csv (ni zip) dans {experiment_dir}")
    forecasts = pd.concat(frames, ignore_index=True)
    if methods:
        unknown = set(methods) - set(forecasts["method_run_id"])
        if unknown:
            raise ValueError(f"méthodes absentes du dossier : {sorted(unknown)}")
        forecasts = forecasts[forecasts["method_run_id"].isin(methods)]
    return forecasts.reset_index(drop=True)


def _read_forecasts(source) -> pd.DataFrame:
    return pd.read_csv(
        source,
        usecols=FORECAST_USECOLS,
        dtype={"case_id": str, "counter_id": str, "method_run_id": str, "variant": str},
        keep_default_na=False,
        na_values={"y_pred": [""]},
    )


def load_observations(
    cases: pd.DataFrame, snapshot_id: str | None = None, *, root: Path | None = None
) -> pd.DataFrame:
    """Mesures de l'instantané, limitées aux compteurs des cas et aux 24 h qui suivent.

    Le filtre ne sert qu'à la mémoire : evaluate_all ne lit que les heures cibles.
    """
    snapshot_id = snapshot_id or _single(cases["snapshot_id"], "snapshot_id")
    path = Path(root or data_path("processed")) / snapshot_id / "counts.csv"
    obs = pd.read_csv(path, usecols=OBSERVATION_USECOLS, dtype={"counter_id": str})
    origins = pd.to_datetime(cases["origin"], utc=True)
    stamps = pd.to_datetime(obs["timestamp"], utc=True)
    keep = (
        obs["counter_id"].isin(set(cases["counter_id"]))
        & (stamps >= origins.min())
        & (stamps < origins.max() + pd.Timedelta(hours=metrics.N_EXPECTED_HOURS))
    )
    return obs[keep].reset_index(drop=True)


def _single(values: pd.Series, name: str) -> str:
    distinct = sorted(set(values))
    if len(distinct) != 1:
        raise ValueError(f"{name} doit être unique, trouvé : {distinct}")
    return distinct[0]


def as_raw(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Lecture « modèle brut » : un repli d'un modèle appris devient une prévision absente.

    Exemple : une heure HGB en statut fallback (valeur de la référence) passe à y_pred vide
    et statut unavailable ; les heures des références ne changent pas.
    """
    out = forecasts.copy()
    replaced = ~out["variant"].isin(REFERENCE_VARIANTS) & out["prediction_status"].eq("fallback")
    out.loc[replaced, "y_pred"] = np.nan
    out.loc[replaced, "prediction_status"] = "unavailable"
    return out


def score(cases: pd.DataFrame, forecasts: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par méthode, sur les cas complets communs : le calcul de make_common_scores d'E4.

    Mêmes fonctions d'E4 (src/eval/metrics.py), dans le même ordre que leur backtest :
    - mae_macro : MAE par compteur, puis moyenne non pondérée (la métrique de décision) ;
    - bias, rmse : sur toutes les heures évaluables mises ensemble, comme scores.csv d'E4 ;
    - n_counters, n_compared_cases : compteurs et cas qui ont au moins une heure évaluable ;
    - coverage_24h : part des cas complets pour la méthode, sur tous les cas donnés ;
    - n_fallback_cases : cas dont au moins une heure vient du repli.
    """
    forecasts = forecasts[forecasts["case_id"].isin(set(cases["case_id"]))]
    c, p, o = metrics._prepare_inputs(cases.copy(), forecasts.copy(), observations.copy())
    evaluation = metrics._build_evaluation(c, p, o)
    coverage = metrics.calculate_coverage(evaluation)
    comparable = metrics.filter_common_complete_cases(evaluation, coverage)
    rows = {}
    for method, group in comparable.groupby("method_run_id"):
        by_counter = metrics.calculate_by_counter(group)
        pooled = metrics.calculate_metrics(group["count"], group["y_pred"])
        rows[method] = {
            "variant": group["variant"].iloc[0],
            "mae_macro": by_counter["MAE"].mean() if not by_counter.empty else np.nan,
            "bias": pooled["bias"],
            "rmse": pooled["RMSE"],
            "n_counters": int(group["counter_id"].nunique()),
            "n_compared_cases": int(group["case_id"].nunique()),
        }
    table = pd.DataFrame.from_dict(rows, orient="index")
    by_method = coverage.groupby("method_run_id")
    table["coverage_24h"] = by_method["is_complete_24h"].mean()
    table["n_fallback_cases"] = by_method["n_fallback_hours"].apply(lambda s: int((s > 0).sum()))
    table.index.name = "method_run_id"
    return table.sort_values("mae_macro")


def score_experiment(
    experiment_dir: Path,
    *,
    protocol_id: str = "proto-v1",
    scenario: str = "known_site",
    split: str = "validation",
    methods: list[str] | None = None,
    cases_root: Path | None = None,
    processed_root: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Les deux lectures d'un dossier d'expérience : {"système": table, "brut": table}."""
    cases = load_cases(protocol_id, scenario=scenario, split=split, root=cases_root)
    forecasts = load_forecasts(experiment_dir, methods)
    forecasts = forecasts[forecasts["case_id"].isin(set(cases["case_id"]))]
    if forecasts.empty:
        raise ValueError(f"aucune prévision de {experiment_dir} sur les cas {scenario} / {split}")
    cases = cases[cases["case_id"].isin(set(forecasts["case_id"]))]
    observations = load_observations(cases, root=processed_root)
    return {
        "système": score(cases, forecasts, observations),
        "brut": score(cases, as_raw(forecasts), observations),
    }


def to_json(tables: dict[str, pd.DataFrame]) -> dict:
    """Tables -> dictionnaire JSON (valeurs arrondies à 4 décimales, NaN -> null)."""
    out = {}
    for name, table in tables.items():
        rounded = table.round(4).astype(object).where(table.notna(), None)
        out[name] = rounded.to_dict(orient="index")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--experiment", required=True, help="ex. EXP-E2, EXP-E2-04")
    parser.add_argument("--level", help="sous-dossier (niveau de dégradation d'EXP-E2-05)")
    parser.add_argument("--split", default="validation", choices=["validation", "test"])
    parser.add_argument("--scenario", default="known_site")
    parser.add_argument("--protocol", default="proto-v1")
    parser.add_argument("--methods", nargs="+", help="method_run_id à garder (défaut : tous)")
    parser.add_argument("--out", type=Path, help="fichier JSON (défaut : scores.json du dossier)")
    args = parser.parse_args(argv)

    folder = data_path("predictions") / args.experiment
    if args.level:
        folder = folder / args.level
    tables = score_experiment(
        folder,
        protocol_id=args.protocol,
        scenario=args.scenario,
        split=args.split,
        methods=args.methods,
    )
    with pd.option_context("display.width", 140, "display.max_columns", 20):
        for name, table in tables.items():
            print(f"\n=== {name} ({args.experiment}, {args.scenario} / {args.split}) ===")
            print(table.round(3).to_string())
    out = args.out or folder / f"scores_{args.scenario}_{args.split}.json"
    payload = {
        "experiment": args.experiment,
        "level": args.level,
        "protocol_id": args.protocol,
        "scenario": args.scenario,
        "split": args.split,
        "scores": to_json(tables),
    }
    Path(out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nécrit : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

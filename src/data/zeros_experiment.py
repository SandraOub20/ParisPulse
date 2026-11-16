"""Comparaison A (garder) / B (écarter) des longues suites de zéros - E1, avec E2/E4.

Fiche : reports/experiments/E1-zeros-apprentissage.md (EXP-E1-04). Protocole PROPOSÉ,
à valider par E4 avant toute comparaison servant à décider.

Un seul facteur change : les heures d'apprentissage (src/data/zeros.py). Le modèle, les
cas et le masque d'évaluation sont identiques. Règles reprises de PROTOCOLE_EVALUATION.md
§6 : cas complets = 24 prévisions finies et non négatives ; comparaison sur l'intersection
des cas complets de A et B ; heures réellement mesurées (`is_scoreable`) ; MAE par compteur
puis moyenne non pondérée ; un zéro observé reste une cible évaluable.

Seules les CIBLES d'apprentissage sont retirées par B : l'historique publié à la coupure
est transmis intact au modèle (mêmes entrées pour A et B), avec un drapeau `is_target`.

Entrées au moment de prévoir (PROTOCOLE_EVALUATION.md §3 : « les observations d'entrée
peuvent s'actualiser à chaque origine même si le modèle reste gelé ») : `predict` reçoit
aussi `history`, tous les comptages avec leur `available_at` (fin de l'heure + délai de
publication). Pour une origine, le modèle ne lit que `history_at(history, origine)`. Cet
historique est le même pour A et B : un zéro observé reste une entrée.

Modèle : tout objet ayant `fit(train)` et `predict(targets, history) -> y_pred` (voir `Model`).
Interface PROVISOIRE, à convenir avec E2 (src/models/registry.py) quand son modèle
existera. `ProfileModel` sert seulement de TEST TECHNIQUE du script : ses chiffres ne
décident rien.

Usage (après validation du protocole) :
  uv run python -m src.data.zeros_experiment --snapshot flux-20261115 \
      --coupure 2026-07-01 --debut 2026-07-01 --fin 2026-09-01 --modele profil
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Protocol

import numpy as np
import pandas as pd

from src.common.config import data_path
from src.data import zeros
from src.data.quality import TZ_LOCAL, load_counts

HORIZON = 24
# Même seuil et même définition que quality.py (observed_days = heures / 24, exclu si < 28)
MIN_TRAINING_DAYS = 28
GROUPS = ("concerned", "control", "other_robustness")
# Règle de décision de la fiche (seuils proposés, à valider par E4)
MIN_GAIN_CONCERNED = 0.05
MAX_LOSS_CONTROL = 0.01


class Model(Protocol):
    def fit(self, train: pd.DataFrame) -> None:
        """`train` : counter_id, ts (UTC), count, is_target.

        Toutes les heures publiées à la coupure, identiques pour A et B (entrées
        possibles). N'apprendre que sur les lignes `is_target` : seul ce drapeau change.
        """

    def predict(self, targets: pd.DataFrame, history: pd.DataFrame) -> np.ndarray:
        """`targets` : case_id, counter_id, origin, horizon, ts ; une prévision par ligne.

        `history` : counter_id, ts, count, available_at. Pour chaque origine, n'utiliser
        que `history_at(history, origin)` (comptages publiés à l'origine).
        """


def with_availability(counts: pd.DataFrame, lag_hours: int | None = None) -> pd.DataFrame:
    """Comptages et heure de publication : fin de l'heure + délai (`publication_lag_hours`)."""
    lag = zeros.publication_lag_hours() if lag_hours is None else lag_hours
    out = counts[["counter_id", "ts", "count"]].copy()
    out["available_at"] = out["ts"] + pd.Timedelta(hours=1 + lag)
    return out


def history_at(history: pd.DataFrame, origin: pd.Timestamp) -> pd.DataFrame:
    """Comptages publiés à l'origine : seule entrée admissible pour prévoir depuis `origin`."""
    return history[history["available_at"] <= origin]


class ProfileModel:
    """TEST TECHNIQUE : médiane par compteur, heure locale et type de jour (profil gelé).

    N'utilise pas `history` : le profil est appris une fois à la coupure.
    """

    def fit(self, train: pd.DataFrame) -> None:
        train = train[train["is_target"]]
        self.table = train.groupby(self._key(train))["count"].median()

    def predict(self, targets: pd.DataFrame, history: pd.DataFrame | None = None) -> np.ndarray:
        idx = pd.MultiIndex.from_arrays(self._key(targets))
        return self.table.reindex(idx).to_numpy(dtype=float)

    @staticmethod
    def _key(df: pd.DataFrame) -> list[pd.Series]:
        local = df["ts"].dt.tz_convert(TZ_LOCAL)
        return [
            df["counter_id"].rename("counter_id"),
            pd.Series(local.dt.hour, index=df.index, name="hour"),
            pd.Series(local.dt.dayofweek >= 5, index=df.index, name="weekend"),
        ]


# ----------------------------------------------------------------- cas et cibles
def expected_cases(counter_ids, start_day: str, end_day: str) -> pd.DataFrame:
    """Un cas par compteur et par origine à 00:00 heure de Paris, jours de [début, fin)."""
    days = pd.date_range(start_day, end_day, freq="D", inclusive="left")
    origins = [d.tz_localize(TZ_LOCAL).tz_convert("UTC") for d in days]
    rows = [(cid, o) for cid in sorted(counter_ids) for o in origins]
    cases = pd.DataFrame(rows, columns=["counter_id", "origin"])
    cases["case_id"] = cases["counter_id"] + "|" + cases["origin"].map(pd.Timestamp.isoformat)
    return cases[["case_id", "counter_id", "origin"]]


def case_targets(cases: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    """24 heures cibles par cas (heures écoulées depuis l'origine) et leur observation."""
    t = cases.loc[cases.index.repeat(HORIZON)].reset_index(drop=True)
    t["horizon"] = np.tile(np.arange(1, HORIZON + 1), len(cases))
    t["ts"] = t["origin"] + pd.to_timedelta(t["horizon"] - 1, unit="h")
    obs = counts[["counter_id", "ts", "count", "is_scoreable"]]
    t = t.merge(obs, on=["counter_id", "ts"], how="left")
    t["is_scoreable"] = t["is_scoreable"].eq(True)  # cible absente de counts.csv : non évaluable
    t["y_true"] = t["count"].where(t["is_scoreable"])
    return t.drop(columns="count")


# ----------------------------------------------------------------- une variante
def training_frame(
    counts: pd.DataFrame,
    train_ids: set[str],
    cutoff: pd.Timestamp,
    treatment: str,
    lag_hours: int | None = None,
    min_run: int = zeros.MIN_RUN_HOURS,
) -> pd.DataFrame:
    """Historique publié à la coupure (identique pour A et B) et drapeau `is_target`."""
    lag = zeros.publication_lag_hours() if lag_hours is None else lag_hours
    avail = counts["counter_id"].isin(train_ids)
    avail &= zeros.available_at_cutoff(counts["ts"], cutoff, lag)
    train = counts.loc[avail, ["counter_id", "ts", "count"]].copy()
    train["is_target"] = zeros.training_mask(counts, cutoff, treatment, lag, min_run)[avail]
    return train


def run_variant(
    model: Model,
    counts: pd.DataFrame,
    train_ids: set[str],
    targets: pd.DataFrame,
    cutoff: pd.Timestamp,
    treatment: str,
    lag_hours: int | None = None,
    min_run: int = zeros.MIN_RUN_HOURS,
) -> tuple[pd.DataFrame, pd.Series]:
    """Apprend avec le traitement donné, prévoit les cibles.

    Renvoie les prévisions et, par compteur, les jours d'apprentissage (heures cibles / 24).
    """
    train = training_frame(counts, train_ids, cutoff, treatment, lag_hours, min_run)
    model.fit(train)
    preds = targets[["case_id", "counter_id", "horizon"]].copy()
    history = with_availability(counts[counts["counter_id"].isin(train_ids)], lag_hours)
    preds["y_pred"] = model.predict(targets, history)  # même historique pour A et B
    days = train[train["is_target"]].groupby("counter_id").size() / 24
    return preds, days


def complete_cases(preds: pd.DataFrame) -> set[str]:
    """Cas dont les 24 horizons ont une prévision finie et non négative."""
    ok = np.isfinite(preds["y_pred"]) & (preds["y_pred"] >= 0)
    n = ok.groupby(preds["case_id"]).sum()
    return set(n.index[n == HORIZON])


# ----------------------------------------------------------------- comparaison
def compare(
    targets: pd.DataFrame,
    preds_a: pd.DataFrame,
    preds_b: pd.DataFrame,
    groups: dict[str, str],
    days_a: pd.Series,
    days_b: pd.Series,
) -> dict:
    """Mesures de la fiche, sur l'intersection des cas complets et le même masque."""
    n_expected = targets["case_id"].nunique()
    comp_a, comp_b = complete_cases(preds_a), complete_cases(preds_b)
    common = comp_a & comp_b
    key = ["case_id", "horizon"]
    d = targets[targets["case_id"].isin(common) & targets["is_scoreable"]]
    d = d.merge(preds_a[key + ["y_pred"]], on=key).rename(columns={"y_pred": "pred_a"})
    d = d.merge(preds_b[key + ["y_pred"]], on=key).rename(columns={"y_pred": "pred_b"})
    d["err_a"] = (d["pred_a"] - d["y_true"]).abs()
    d["err_b"] = (d["pred_b"] - d["y_true"]).abs()
    d["group"] = d["counter_id"].map(groups)

    per_counter = d.groupby("counter_id")[["err_a", "err_b"]].mean()
    per_counter.columns = ["mae_a", "mae_b"]
    per_counter["group"] = per_counter.index.map(groups)
    per_counter["n_hours"] = d.groupby("counter_id").size()

    def usable(days: pd.Series, complete: set[str]) -> int:
        with_case = {c.split("|")[0] for c in complete}
        return sum(
            1 for cid in groups if days.get(cid, 0) >= MIN_TRAINING_DAYS and cid in with_case
        )

    by_group = {}
    for g in GROUPS:
        pc = per_counter[per_counter["group"] == g]
        zero = d[(d["group"] == g) & (d["y_true"] == 0)]
        by_group[g] = {
            "n_counters": sum(1 for v in groups.values() if v == g),
            "n_evaluable_counters": int(len(pc)),  # sans heure évaluable : pas de MAE, pas 0
            "mae_macro_a": float(pc["mae_a"].mean()) if len(pc) else np.nan,
            "mae_macro_b": float(pc["mae_b"].mean()) if len(pc) else np.nan,
            "n_improved": int((pc["mae_b"] < pc["mae_a"]).sum()),
            "n_degraded": int((pc["mae_b"] > pc["mae_a"]).sum()),
            "mae_zero_targets_a": float(zero["err_a"].mean()) if len(zero) else np.nan,
            "mae_zero_targets_b": float(zero["err_b"].mean()) if len(zero) else np.nan,
        }
    return {
        "n_expected_cases": n_expected,
        "n_complete_a": len(comp_a),
        "n_complete_b": len(comp_b),
        "n_compared_cases": len(common),
        # Cas comparés sans aucune heure mesurée (trou du réseau, compteur arrêté) : comptés
        "n_compared_cases_without_observation": len(common - set(d["case_id"])),
        "n_compared_hours": int(len(d)),
        "coverage_24h_a": len(comp_a) / n_expected if n_expected else np.nan,
        "coverage_24h_b": len(comp_b) / n_expected if n_expected else np.nan,
        "usable_counters_a": usable(days_a, comp_a),
        "usable_counters_b": usable(days_b, comp_b),
        "groups": by_group,
        "per_counter": per_counter.reset_index(),
    }


def decide(result: dict) -> tuple[str, str]:
    """Règle de décision fixée dans la fiche avant les résultats."""
    c, t = result["groups"]["concerned"], result["groups"]["control"]
    maes = [c["mae_macro_a"], c["mae_macro_b"], t["mae_macro_a"], t["mae_macro_b"]]
    if not all(np.isfinite(m) for m in maes) or c["mae_macro_a"] == 0 or t["mae_macro_a"] == 0:
        return "A (garder)", "règle non applicable : groupe sans MAE calculable"
    gain = 1 - c["mae_macro_b"] / c["mae_macro_a"]
    loss = t["mae_macro_b"] / t["mae_macro_a"] - 1
    no_loss = result["usable_counters_b"] >= result["usable_counters_a"]
    ok = gain >= MIN_GAIN_CONCERNED and loss <= MAX_LOSS_CONTROL and no_loss
    reason = (
        f"gain concernés {gain:.1%} (seuil {MIN_GAIN_CONCERNED:.0%}), "
        f"variation témoins {loss:+.1%} (max {MAX_LOSS_CONTROL:+.0%}), "
        f"compteurs utilisables A={result['usable_counters_a']} B={result['usable_counters_b']}"
    )
    return ("B (écarter)" if ok else "A (garder)"), reason


# ----------------------------------------------------------------- ensemble
def comparison_groups(inventory: pd.DataFrame, dropped_ids: set[str]) -> dict[str, str]:
    """Compteurs de S_train, répartis entre concernés, témoins et autres robustness."""
    sel = inventory[
        (inventory["period_role"] == "selection") & (inventory["site_role"] == "S_train")
    ]
    groups = {}
    for cid, status in zip(sel["counter_id"].astype(str), sel["selection_status"]):
        if cid in dropped_ids:
            groups[cid] = "concerned"
        elif status == "retained":
            groups[cid] = "control"
        else:
            groups[cid] = "other_robustness"
    return groups


def run_experiment(
    counts: pd.DataFrame,
    inventory: pd.DataFrame,
    model_factory: Callable[[], Model],
    cutoff: pd.Timestamp,
    start_day: str,
    end_day: str,
    lag_hours: int | None = None,
    min_run: int = zeros.MIN_RUN_HOURS,
) -> dict:
    """A et B avec deux instances neuves du même modèle, mêmes cas et mêmes cibles.

    Les groupes (concernés, témoins, autres) sont TOUJOURS définis avec la règle
    principale de 24 h, pour que les variantes de sensibilité (`min_run` = 48 ou 72 h,
    qui ne change que ce que B retire) soient comparées sur les mêmes compteurs.
    """
    main_rule = zeros.long_zero_mask(counts, cutoff, lag_hours, zeros.MIN_RUN_HOURS)
    groups = comparison_groups(inventory, set(counts.loc[main_rule, "counter_id"]))
    targets = case_targets(expected_cases(groups, start_day, end_day), counts)
    ids = set(groups)
    args = (counts, ids, targets, cutoff)
    preds_a, days_a = run_variant(model_factory(), *args, "keep", lag_hours, min_run)
    preds_b, days_b = run_variant(model_factory(), *args, "drop", lag_hours, min_run)
    result = compare(targets, preds_a, preds_b, groups, days_a, days_b)
    result["min_run_hours"] = min_run
    return result


MODELS = {"profil": ProfileModel}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--coupure", required=True, help="coupure d'apprentissage, AAAA-MM-JJ")
    ap.add_argument("--debut", required=True, help="première origine, AAAA-MM-JJ")
    ap.add_argument("--fin", required=True, help="fin des origines (exclue), AAAA-MM-JJ")
    ap.add_argument("--modele", choices=sorted(MODELS), default="profil")
    ap.add_argument(
        "--seuil",
        type=int,
        default=zeros.MIN_RUN_HOURS,
        help="longueur minimale (h) des suites retirées par B : 24 (décision), 48 ou 72 "
        "(sensibilité, ne décide rien)",
    )
    args = ap.parse_args(argv)
    folder = data_path("processed") / args.snapshot
    counts = load_counts(folder / "counts.csv")
    inventory = pd.read_csv(folder / "inventory_quality.csv", dtype={"counter_id": str})
    res = run_experiment(
        counts,
        inventory,
        MODELS[args.modele],
        zeros.local_midnight(args.coupure),
        args.debut,
        args.fin,
        min_run=args.seuil,
    )
    if args.modele == "profil":
        print("TEST TECHNIQUE (ProfileModel) : chiffres non utilisables pour décider.")
    if args.seuil != zeros.MIN_RUN_HOURS:
        print(f"SENSIBILITÉ (suites >= {args.seuil} h) : la décision se prend à 24 h seulement.")
    for k, v in res.items():
        if k not in ("groups", "per_counter"):
            print(f"{k} : {v}")
    print(pd.DataFrame(res["groups"]).T.to_string())
    print("Décision selon la règle de la fiche :", *decide(res), sep="\n- ")
    return 0


if __name__ == "__main__":
    sys.exit(main())

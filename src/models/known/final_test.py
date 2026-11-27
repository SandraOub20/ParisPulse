"""Lecture du test final (D-07), fixée et commitée avant de lire le test.

Gain du HGB et du MLP A face aux deux références, au total et par période (normale,
transition, vacances de la Toussaint), avec le bootstrap sur les jours ; tranches horaires ;
diagnostics fériés, grèves et pluie prévue. Rien n'est réglé d'après ce résultat.

Commande : python -m src.models.known.final_test (après le calcul de EXP-E2-TEST).
"""

from __future__ import annotations

import pandas as pd

from src.models.known import demo as D
from src.models.known import predict as P
from src.models.known import robustness as R
from src.models.known import score as S

M = {
    "e2-hgb-ctx-20260701-s0-b357": "HGB",
    "e2-mlp-ctx-20260701-s0-9ce9": "MLP A",
    "e2-mlp-ctx-20260701-s0-37f5": "MLP B",
    "e2-reference_profile-measured": "Médiane 4 sem.",
    "e2-reference-measured": "Même heure J-7",
}
REFS = ["e2-reference_profile-measured", "e2-reference-measured"]


def period(day):
    if "2026-10-14" <= day <= "2026-10-20" or "2026-11-02" <= day <= "2026-11-08":
        return "transition"
    if "2026-10-21" <= day <= "2026-11-01":
        return "vacances"
    return "normale"


def main() -> int:
    cases = S.load_cases(split="test")
    fc = S.load_forecasts(S.data_path("predictions") / "EXP-E2-TEST", list(M))
    wide = R.paired_hours(fc, S.load_observations(cases), list(M))
    wide["période"] = wide.day.map(period)
    pd.set_option("display.width", 220)
    print("jours par période :", wide.groupby("période").day.nunique().to_dict())
    rows = []
    for label, part in [("ensemble", wide), *wide.groupby("période")]:
        for model in ["e2-hgb-ctx-20260701-s0-b357", "e2-mlp-ctx-20260701-s0-9ce9"]:
            for ref in REFS:
                b = R.bootstrap_gain(part, model, ref)
                rows.append(
                    {
                        "période": label,
                        "modèle": M[model],
                        "référence": M[ref],
                        "MAE modèle": R.macro_mae(part, model),
                        "MAE réf.": R.macro_mae(part, ref),
                        "gain": b["gain"],
                        "IC bas": b["low"],
                        "IC haut": b["high"],
                        "jours": b["days"],
                    }
                )
    print(pd.DataFrame(rows).round(3).to_string())
    print(
        R.by_band(wide, list(M))
        .rename(columns=lambda c: " ".join(M.get(x, x) for x in c.split()))
        .round(2)
        .to_string()
    )
    context = P.load_context("hist-20261117")
    labels = {
        "fériés (01/11, 11/11)": wide.day.isin(["2026-11-01", "2026-11-11"]),
        "grèves": wide.day.isin(
            [
                d
                for d in context[
                    (context.variable == "is_strike") & (context.value == "true")
                ].local_date
            ]
        ),
        "pluie prévue >= 1 mm": wide.day.isin(D.rainy_days(context)),
    }
    for name, mask in labels.items():
        part = wide[mask]
        if part.empty:
            continue
        print(
            name, part.day.nunique(), "jours :", {M[m]: round(R.macro_mae(part, m), 2) for m in M}
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

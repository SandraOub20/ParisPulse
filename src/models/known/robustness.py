"""Solidité d'un gain : tranches horaires, WAPE, mois et intervalle de confiance par jour.

Lecture des prévisions déjà notées : rien ne change dans les décisions des fiches.
- paired_hours : les heures où la vérité est évaluable et où toutes les méthodes prévoient ;
- by_band : MAE et WAPE par tranche horaire (nuit, pointes, journée) ;
- macro_mae / by_month : MAE par compteur puis moyenne, comme E4, au total ou par mois ;
- bootstrap_gain : intervalle de confiance du gain d'un modèle sur une référence, en tirant
  des **jours** avec remise (les heures d'un même jour sont corrélées, pas les jours
  entre eux, ou beaucoup moins).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LOCAL_TZ = "Europe/Paris"
BANDS = {
    "nuit 0-6 h": range(0, 6),
    "pointe matin 7-9 h": range(7, 9),
    "pointe soir 17-19 h": range(17, 19),
}
OTHER_BAND = "reste de la journée"


def paired_hours(
    forecasts: pd.DataFrame, observations: pd.DataFrame, methods: list[str]
) -> pd.DataFrame:
    """Une ligne par heure cible commune : case_id, counter_id, t, day (local), truth, méthodes.

    forecasts : case_id, counter_id, target_timestamp, y_pred, method_run_id.
    observations : counter_id, timestamp, count_raw (ou count, comme E4), is_scoreable.
    Une heure sans vérité évaluable ou sans prévision d'une des méthodes est retirée : les
    méthodes sont comparées sur exactement les mêmes heures.
    """
    fc = forecasts[forecasts["method_run_id"].isin(methods)].copy()
    fc["t"] = pd.to_datetime(fc["target_timestamp"], utc=True)
    obs = observations[observations["is_scoreable"].astype(bool)].copy()
    obs["t"] = pd.to_datetime(obs["timestamp"], utc=True)
    value = "count_raw" if "count_raw" in obs.columns else "count"  # count : lecture d'E4
    obs = obs.rename(columns={value: "truth"})[["counter_id", "t", "truth"]]
    wide = fc.pivot_table(
        index=["case_id", "counter_id", "t"], columns="method_run_id", values="y_pred"
    ).reset_index()
    wide = wide.merge(obs, on=["counter_id", "t"]).dropna(subset=[*methods, "truth"])
    origins = wide["case_id"].str.extract(r"_(\d{8}T\d{2})_")[0]
    origin = pd.to_datetime(origins, format="%Y%m%dT%H", utc=True)
    wide["day"] = origin.dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d")  # minuit, Paris
    return wide.reset_index(drop=True)


def band_of(t: pd.Series) -> pd.Series:
    """Tranche horaire de chaque heure cible, à l'heure de Paris (début d'intervalle)."""
    hour = t.dt.tz_convert(LOCAL_TZ).dt.hour
    out = pd.Series(OTHER_BAND, index=t.index)
    for name, hours in BANDS.items():
        out[hour.isin(list(hours))] = name
    return out


def by_band(wide: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """MAE et WAPE de chaque méthode, toutes heures puis par tranche (heures mises ensemble)."""
    bands = band_of(wide["t"])
    rows = []
    for name, part in [("toutes les heures", wide), *wide.groupby(bands)]:
        row = {"tranche": name, "heures": len(part), "vélos/h moyen": part["truth"].mean()}
        for m in methods:
            err = (part[m] - part["truth"]).abs()
            row[f"MAE {m}"] = err.mean()
            row[f"WAPE {m}"] = err.sum() / part["truth"].sum()
        rows.append(row)
    return pd.DataFrame(rows).set_index("tranche")


def macro_mae(wide: pd.DataFrame, method: str) -> float:
    """MAE par compteur, puis moyenne non pondérée entre compteurs (comme E4)."""
    err = (wide[method] - wide["truth"]).abs()
    return float(err.groupby(wide["counter_id"]).mean().mean())


def by_month(wide: pd.DataFrame, model: str, reference: str) -> pd.DataFrame:
    """MAE macro du modèle et de la référence, et gain, mois par mois (mois de l'origine)."""
    month = wide["day"].str[:7]
    rows = []
    for name, part in wide.groupby(month):
        a, b = macro_mae(part, model), macro_mae(part, reference)
        rows.append(
            {
                "mois": name,
                "jours": part["day"].nunique(),
                "MAE modèle": a,
                "MAE référence": b,
                "gain": 1 - a / b,
            }
        )
    return pd.DataFrame(rows).set_index("mois")


def bootstrap_gain(
    wide: pd.DataFrame,
    model: str,
    reference: str,
    *,
    n_boot: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> dict[str, float]:
    """Gain 1 - MAEmacro(modèle) / MAEmacro(référence) et son intervalle, jours tirés avec remise.

    Pour chaque tirage, chaque jour reçoit un poids (nombre de fois où il est tiré) ; la MAE
    de chaque compteur est recalculée avec ces poids, puis moyennée entre compteurs.
    Exemple de lecture : {"gain": 0.18, "low": 0.16, "high": 0.20} veut dire 18 % de mieux,
    entre 16 et 20 % avec 95 % de confiance si l'on avait observé d'autres jours semblables.
    """
    days = np.array(sorted(wide["day"].unique()))
    counters = np.array(sorted(wide["counter_id"].unique()))
    d = np.searchsorted(days, wide["day"].to_numpy())
    c = np.searchsorted(counters, wide["counter_id"].to_numpy())
    shape = (len(days), len(counters))

    def sums(method):
        s = np.zeros(shape)
        np.add.at(s, (d, c), (wide[method] - wide["truth"]).abs().to_numpy())
        return s

    hours = np.zeros(shape)
    np.add.at(hours, (d, c), 1.0)
    s_model, s_ref = sums(model), sums(reference)

    def gain(weights):
        n = weights @ hours
        with np.errstate(invalid="ignore", divide="ignore"):
            a = np.nanmean(np.where(n > 0, (weights @ s_model) / n, np.nan), axis=-1)
            b = np.nanmean(np.where(n > 0, (weights @ s_ref) / n, np.nan), axis=-1)
        return 1 - a / b

    rng = np.random.default_rng(seed)
    draws = rng.multinomial(len(days), np.full(len(days), 1 / len(days)), size=n_boot)
    boot = gain(draws.astype(float))
    alpha = (1 - level) / 2
    return {
        "gain": float(gain(np.ones(len(days)))),
        "low": float(np.quantile(boot, alpha)),
        "high": float(np.quantile(boot, 1 - alpha)),
        "days": int(len(days)),
        "n_boot": int(n_boot),
    }

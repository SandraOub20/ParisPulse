"""Démonstration d'un cas : les fonctions appelées par les notebooks E2 (notebooks/E2_*.ipynb).

Les notebooks n'ont pas de logique propre : ils appellent ce module, predict.py et score.py.
- find_case : retrouve un cas d'E4 par compteur et par jour ;
- forecast_case : le prévoit avec plusieurs méthodes, par predict_24h (le code de l'appli) ;
- case_view : la semaine visible à l'origine et la vérité des 24 heures suivantes ;
- plot_case : le graphique de la semaine, de la vérité et des prévisions.
La vérité ne sert qu'au graphique : elle n'est jamais donnée aux méthodes.
"""

from __future__ import annotations

import pandas as pd

from src.models.known import predict as P
from src.models.schemas import Case

LOCAL_TZ = "Europe/Paris"


def find_case(cases: pd.DataFrame, counter_id: str, day: str) -> Case:
    """Le cas d'E4 du compteur dont l'origine est le jour local day (minuit, Paris).

    Exemple : find_case(cases, "100057445-104057445", "2026-07-14") renvoie le cas du
    14 juillet, origine 2026-07-13T22:00Z.
    """
    origin = pd.Timestamp(day, tz=LOCAL_TZ).tz_convert("UTC")
    rows = cases[
        (cases["counter_id"] == counter_id)
        & (pd.to_datetime(cases["origin"], utc=True) == origin)
        & (cases["scenario"] == "known_site")
    ]
    if rows.empty:
        raise ValueError(f"aucun cas known_site pour {counter_id} le {day}")
    return Case.from_row(rows.iloc[0])


def forecast_case(
    case: Case,
    history: pd.DataFrame,
    variants: dict[str, dict],
    *,
    context: pd.DataFrame | None = None,
    publication_lag_hours: int | None = None,
) -> pd.DataFrame:
    """Les 24 prévisions du cas pour chaque méthode, en format long.

    variants : {nom affiché: arguments de predict_24h}, par exemple
    {"HGB": {"variant": "hgb"}, "MLP": {"variant": "mlp"}, "Médiane 4 sem.":
    {"variant": "reference_profile"}}. Colonnes rendues : method, target_timestamp,
    y_pred, prediction_status, status_reason.
    """
    frames = []
    for name, kwargs in variants.items():
        kwargs = dict(kwargs)
        variant = kwargs.pop("variant")
        uses_model = variant in P.TRAINED_VARIANTS
        result = P.predict_24h(
            case,
            history,
            variant,
            context=context if uses_model else None,
            publication_lag_hours=publication_lag_hours,
            **kwargs,
        )
        frame = result.to_forecast_frame()[
            ["target_timestamp", "y_pred", "prediction_status", "status_reason"]
        ]
        frames.append(frame.assign(method=name))
    out = pd.concat(frames, ignore_index=True)
    out["target_timestamp"] = pd.to_datetime(out["target_timestamp"], utc=True)
    return out


def case_view(
    case: Case, history: pd.DataFrame, publication_lag_hours: int | None = None
) -> dict[str, pd.DataFrame]:
    """La semaine visible (mesures publiées à l'origine) et la vérité des 24 heures.

    {"visible": timestamp, count (vide si non mesurée) ; "truth": timestamp, count}.
    """
    lag = P.default_publication_lag() if publication_lag_hours is None else publication_lag_hours
    origin = pd.Timestamp(case.origin).tz_convert("UTC")
    stamps = pd.to_datetime(history["timestamp"], utc=True)
    published = origin - pd.Timedelta(hours=lag)
    week = (stamps >= published - pd.Timedelta(hours=168)) & (stamps < published)
    target = (stamps >= origin) & (stamps < origin + pd.Timedelta(hours=24))
    measured = history["count_raw"].where(history["is_observed"].astype(bool))
    return {
        "visible": pd.DataFrame({"timestamp": stamps[week], "count": history.loc[week, "count"]}),
        "truth": pd.DataFrame({"timestamp": stamps[target], "count": measured[target]}),
    }


def plot_case(view: dict[str, pd.DataFrame], forecasts: pd.DataFrame, ax=None, title: str = ""):
    """Semaine visible (gris), vérité (noir) et prévisions (une couleur par méthode)."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 4))
    local = view["visible"]["timestamp"].dt.tz_convert(LOCAL_TZ)
    ax.plot(local, view["visible"]["count"], color="0.6", lw=1, label="semaine visible")
    truth_t = view["truth"]["timestamp"].dt.tz_convert(LOCAL_TZ)
    ax.plot(truth_t, view["truth"]["count"], color="black", lw=2, label="vérité (cachée)")
    for name, group in forecasts.groupby("method", sort=False):
        status = ", repli" if (group["prediction_status"] == "fallback").any() else ""
        ax.plot(
            group["target_timestamp"].dt.tz_convert(LOCAL_TZ),
            group["y_pred"],
            lw=1.6,
            label=f"{name}{status}",
        )
    ax.set_ylabel("vélos / heure")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    return ax


def rainy_days(context: pd.DataFrame, threshold_mm: float = 1.0) -> set[str]:
    """Jours locaux (AAAA-MM-JJ) dont la pluie prévue (rain_prev) atteint threshold_mm.

    La pluie prévue est sommée heure par heure sur la journée de Paris (EXP-E2-04 :
    seuil de 1 mm, fixé au gel). Sert au diagnostic, jamais d'entrée à une méthode.
    """
    rain = context[context["variable"] == "rain_prev"]
    local = pd.to_datetime(rain["valid_time"], utc=True).dt.tz_convert(LOCAL_TZ)
    daily = pd.to_numeric(rain["value"], errors="coerce").groupby(local.dt.date).sum()
    return {str(day) for day, mm in daily.items() if mm >= threshold_mm}


OBSERVED_BINS = [
    (140, 168, "168-140 h"),
    (84, 139, "139-84 h"),
    (24, 83, "83-24 h"),
    (0, 23, "< 24 h"),
]


def observed_hours_band(
    cases: pd.DataFrame, history_loader, publication_lag_hours: int | None = None
) -> pd.Series:
    """Tranche d'heures mesurées de la semaine visible de chaque cas (EXP-E2-05, pop. 1).

    Une heure compte si sa valeur publiée existe (count non vide) dans les 168 heures qui
    finissent à origin - latence. Index : case_id ; valeurs : OBSERVED_BINS.
    """
    from src.models.known import batch as B

    lag = P.default_publication_lag() if publication_lag_hours is None else publication_lag_hours
    labels = {}
    for _, row in cases.iterrows():
        case = Case.from_row(row)
        history = history_loader(case.counter_id)
        week = B.visible_week(case, lag)
        measured = history.loc[history["timestamp"].isin(week), "count"].notna().sum()
        labels[case.case_id] = next(
            name for low, high, name in OBSERVED_BINS if low <= measured <= high
        )
    return pd.Series(labels, name="observed_band")

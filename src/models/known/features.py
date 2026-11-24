"""Variables causales identiques à l'apprentissage et à l'inférence - E2 avec E1.

Version f1.0 (MOD-006 de reports/teams/E2_SUIVI.md). Trois familles :

- calendrier de base, toujours présent : horizon, heure locale, jour, week-end, mois
  (Europe/Paris, calculés sur l'heure cible) ;
- historique, toujours présent : valeurs à t - 168 h et t - 336 h, médiane des 4 mêmes
  heures des semaines précédentes, niveaux récents, tendance, part de manques, ancienneté de
  la dernière mesure, suite de zéros en cours. Les décalages sont en heures UTC, comme les
  références (I3 ouvert) ;
- contexte, retiré par l'ablation, en groupes séparables (CONTEXT_GROUPS) : calendar
  (férié, vacances zone C), strikes (grève IDF), weather_forecast (météo prévue J-2).
  La météo observée (rôle past_observation) n'est jamais une entrée.

Causalité :
- une mesure est utilisable si interval_end <= origin - latence (règle provisoire C3/M2,
  counts.csv n'a pas de colonne available_at) ; avec 24 h de latence, seuls les décalages
  >= 48 h sont utilisables pour les 24 horizons, d'où 168 h et 336 h ;
- une ligne de contexte est utilisable si available_at est vide (connue à l'avance) ou
  <= origin ; sinon la variable vaut NaN ;
- une valeur absente reste NaN avec un indicateur ; un zéro mesuré reste 0.

Un seul calcul (_history_core, _context_core, _calendar_core) sert aux deux
chemins : build_feature_frame (un cas, inférence) et build_training_frame (tous les
cas d'un compteur en une fois, apprentissage). Le calcul ne lit que le passé admissible même
si on lui donne tout l'historique ; tests/test_known_features.py vérifie que les deux chemins
donnent le même résultat.

Valeurs : entrée = mesure publiée (count_raw si is_observed, D-11) ; cible
d'apprentissage = count_raw si is_scoreable. Les estimations d'E1 et le masque
rétrospectif long_zero_run ne sont pas utilisés.

Pour E3 : le modèle n'a pas l'identifiant du compteur. Avec 7 jours de support local, les
variables à 336 h, la médiane sur 4 semaines (au-delà d'une semaine) et le niveau de la
semaine précédente seront NaN.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.common.config import load_config
from src.models.known import baseline
from src.models.schemas import HORIZON_HOURS, ForecastInputs, target_timestamps

FEATURE_VERSION = "f1.0"
LOCAL_TZ = "Europe/Paris"
HOUR_NS = 3_600_000_000_000
WEEK_HOURS = 168
PROFILE_WEEKS = 4

CALENDAR_COLUMNS = ["horizon", "hour_local", "dow_local", "is_weekend", "month_local"]
HISTORY_COLUMNS = [
    "lag_168h",
    "lag_336h",
    "lag_168h_missing",
    "lag_336h_missing",
    "profile_median_4w",
    "profile_n_weeks",
    "level_24h",
    "level_168h",
    "level_prev_168h",
    "trend_7d_log",
    "missing_share_168h",
    "hours_since_last_obs",
    "zero_run_hours",
]
CONTEXT_GROUPS: dict[str, list[str]] = {
    "calendar": ["is_holiday", "is_school_holiday"],
    "strikes": ["is_strike"],
    "weather_forecast": ["temp_prev", "rain_prev", "wind_prev"],
}
# Variables jointes sur la date locale de l'heure cible ; les autres sur interval_end.
DAILY_VARIABLES = {"is_holiday", "is_school_holiday", "is_strike"}
ALLOWED_ROLES = {"known_calendar", "forecast_bulletin"}
META_COLUMNS = [
    "feature_version",
    "case_id",
    "counter_id",
    "origin",
    "target_timestamp",
    "horizon",
    "max_input_available_at",
]


# --------------------------------------------------------------------------- API publique


def resolve_context_groups(
    use_context: bool = True, context_groups: Iterable[str] | None = None
) -> tuple[str, ...]:
    """Groupes de contexte retenus : tous par défaut, aucun si use_context=False."""
    if not use_context:
        return ()
    if context_groups is None:
        return tuple(CONTEXT_GROUPS)
    groups = tuple(context_groups)
    unknown = set(groups) - set(CONTEXT_GROUPS)
    if unknown:
        raise ValueError(f"groupes de contexte inconnus : {sorted(unknown)}")
    return tuple(g for g in CONTEXT_GROUPS if g in groups)


def feature_columns(context_groups: Iterable[str] = ()) -> list[str]:
    """Colonnes d'entrée du modèle, dans un ordre fixe."""
    columns = CALENDAR_COLUMNS + HISTORY_COLUMNS
    for group in resolve_context_groups(True, context_groups):
        columns = columns + CONTEXT_GROUPS[group]
    return columns


def calendar_features(targets: pd.Series) -> pd.DataFrame:
    """Variables temporelles de base, dérivées du seul timestamp, toujours présentes.

    Heure locale, jour de semaine (0 = lundi), week-end, mois, calculés en Europe/Paris pour
    la cible. Aucune source externe ici : fériés et vacances relèvent de context_features,
    afin que l'ablation avec/sans calendrier officiel ne touche que la source complémentaire.
    L'horizon dépend de l'origine : il est ajouté par build_feature_frame.
    """
    target_h = _to_hours(targets, "targets")
    out = _calendar_core(target_h)
    return pd.DataFrame(out, index=targets.index)


def history_features(inputs: ForecastInputs, targets: pd.Series) -> pd.DataFrame:
    """Variables issues du passé admissible (interval_end <= information_cutoff).

    L'historique est refiltré sur la coupure : une ligne future éventuelle est ignorée.
    """
    origin_h, lag_h, grid = _case_grid(inputs)
    target_h = _to_hours(targets, "targets")
    out = _history_core(grid, np.full(len(target_h), origin_h), target_h, lag_h)
    return pd.DataFrame({c: out[c] for c in HISTORY_COLUMNS}, index=targets.index)


def context_features(
    inputs: ForecastInputs,
    targets: pd.Series,
    context_groups: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Source complémentaire autorisée (context.csv d'E1), seule partie retirée par l'ablation.

    - calendar : jour férié, vacances zone C, joints sur la date locale de la cible ;
    - strikes : grève annoncée, jointe sur la date locale, disponible 24 h avant le jour ;
    - weather_forecast : bulletin J-2 joint sur valid_time = interval_end de la cible.
    Une ligne disponible après l'origine donne NaN. La météo observée (past_observation)
    est ignorée. Une clé de jointure en double lève une erreur (multiplication de lignes).
    """
    groups = resolve_context_groups(True, context_groups)
    origin_h = _hour_of(inputs.case.origin, "origin")
    target_h = _to_hours(targets, "targets")
    prepared = _prepare_context(inputs.context, groups)
    out = _context_core(prepared, np.full(len(target_h), origin_h), target_h, groups)
    columns = [v for g in groups for v in CONTEXT_GROUPS[g]]
    return pd.DataFrame({c: out[c] for c in columns}, index=targets.index)


def build_feature_frame(
    inputs: ForecastInputs,
    use_context: bool = True,
    *,
    context_groups: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Assembler les 24 lignes de variables d'un cas (sans label).

    calendar_features et history_features sont toujours présentes ; use_context=False
    retire toute la source complémentaire, context_groups n'en garde qu'une partie.

    Colonnes de traçabilité : feature_version, case_id, counter_id, origin,
    target_timestamp, horizon, max_input_available_at (<= origin, contrôlé).
    """
    groups = resolve_context_groups(use_context, context_groups)
    case = inputs.case
    origin_h, lag_h, grid = _case_grid(inputs)
    target_h = origin_h + np.arange(HORIZON_HOURS, dtype=np.int64)
    prepared = _prepare_context(inputs.context, groups) if groups else {}
    frame = _assemble(
        grid,
        prepared,
        groups,
        np.full(HORIZON_HOURS, origin_h),
        target_h,
        lag_h,
        case_ids=np.full(HORIZON_HOURS, case.case_id, dtype=object),
        counter_id=case.counter_id,
    )
    expected = target_timestamps(case.origin)["target_timestamp"]
    if not frame["target_timestamp"].reset_index(drop=True).equals(expected):
        raise AssertionError("heures cibles différentes de target_timestamps")
    return frame


def build_training_frame(
    counts: pd.DataFrame,
    origins: pd.DataFrame,
    context: pd.DataFrame | None,
    fit_cutoff: pd.Timestamp,
    use_context: bool = True,
    *,
    context_groups: Iterable[str] | None = None,
    publication_lag_hours: int | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Construire X, y sur des origines d'apprentissage ; labels joints séparément.

    counts : colonnes de counts.csv (counter_id, timestamp, count_raw, is_observed,
    is_scoreable). origins : counter_id, origin et, en option, case_id.

    Chaque fenêtre n'utilise que des entrées disponibles à son origine (même calcul que
    build_feature_frame) et des labels disponibles à fit_cutoff
    (interval_end + latence <= fit_cutoff). Les cibles manquantes (NaN / cellule vide)
    ou non évaluables (is_scoreable faux) sont exclues de y ; les zéros observés sont
    conservés comme cibles valides. X garde les colonnes META_COLUMNS pour la traçabilité :
    utiliser feature_columns(groupes) pour l'entrée du modèle.
    """
    groups = resolve_context_groups(use_context, context_groups)
    lag_h = _default_lag() if publication_lag_hours is None else int(publication_lag_hours)
    cutoff_h = _hour_of(fit_cutoff, "fit_cutoff")
    missing = {"counter_id", "timestamp", "count_raw", "is_observed", "is_scoreable"} - set(
        counts.columns
    )
    if missing:
        raise ValueError(f"colonnes absentes de counts : {sorted(missing)}")
    prepared = _prepare_context(context, groups) if groups else {}
    by_counter = {str(k): v for k, v in counts.groupby(counts["counter_id"].astype(str))}

    frames: list[pd.DataFrame] = []
    labels: list[np.ndarray] = []
    for counter_id, sub in origins.groupby(origins["counter_id"].astype(str), sort=True):
        if counter_id not in by_counter:
            raise ValueError(f"compteur {counter_id} absent de counts")
        rows = by_counter[counter_id]
        hours = _to_hours(rows["timestamp"], "timestamp")
        raw = pd.to_numeric(rows["count_raw"], errors="coerce").to_numpy(dtype=float)
        observed = _as_bool(rows["is_observed"])
        scoreable = _as_bool(rows["is_scoreable"])
        grid = _make_grid(hours, np.where(observed, raw, np.nan))
        label_grid = _make_grid(hours, np.where(scoreable, raw, np.nan), stats=False)

        origin_h = _to_hours(sub["origin"], "origin")
        if "case_id" in sub.columns:
            case_of_origin = sub["case_id"].astype(str).to_numpy()
        else:
            stamps = pd.DatetimeIndex(origin_h * HOUR_NS, tz="UTC").strftime("%Y%m%dT%H%MZ")
            case_of_origin = np.array([f"train|{counter_id}|{s}" for s in stamps], dtype=object)
        origin_r = np.repeat(origin_h, HORIZON_HOURS)
        target_r = origin_r + np.tile(np.arange(HORIZON_HOURS, dtype=np.int64), len(origin_h))
        case_r = np.repeat(case_of_origin, HORIZON_HOURS)

        y = _value_at(label_grid, target_r)
        y[target_r + 1 + lag_h > cutoff_h] = np.nan  # label pas encore publié à fit_cutoff
        keep = ~np.isnan(y)
        if not keep.any():
            continue
        frames.append(
            _assemble(
                grid,
                prepared,
                groups,
                origin_r[keep],
                target_r[keep],
                lag_h,
                case_ids=case_r[keep],
                counter_id=counter_id,
            )
        )
        labels.append(y[keep])

    if not frames:
        columns = META_COLUMNS + [c for c in feature_columns(groups) if c not in META_COLUMNS]
        empty = pd.DataFrame(columns=columns)
        return empty, pd.Series(dtype=float, name="y")
    X = pd.concat(frames, ignore_index=True)
    X["case_id"] = X["case_id"].astype("category")
    X["counter_id"] = X["counter_id"].astype("category")
    y = pd.Series(np.concatenate(labels), name="y")
    return X, y


def training_origins(
    counts: pd.DataFrame,
    counter_ids: Iterable[str],
    fit_cutoff: pd.Timestamp,
    *,
    start: pd.Timestamp | None = None,
    warmup_hours: int = PROFILE_WEEKS * WEEK_HOURS,
    publication_lag_hours: int | None = None,
) -> pd.DataFrame:
    """Origines d'apprentissage : chaque jour à minuit heure de Paris, comme les cas d'E4.

    Première origine : après warmup_hours (4 semaines par défaut) de mesures publiées
    depuis la première mesure du compteur, et après start si donné. Dernière origine :
    ses 24 labels publiés au plus tard à fit_cutoff (origin + 24 h + latence <= fit_cutoff).
    """
    lag_h = _default_lag() if publication_lag_hours is None else int(publication_lag_hours)
    cutoff = _utc(fit_cutoff, "fit_cutoff")
    last_origin = cutoff - pd.Timedelta(hours=HORIZON_HOURS + lag_h)
    out = []
    for counter_id in sorted({str(c) for c in counter_ids}):
        rows = counts.loc[counts["counter_id"].astype(str) == counter_id]
        observed = rows.loc[_as_bool(rows["is_observed"]) & rows["count_raw"].notna()]
        if observed.empty:
            continue
        first = pd.to_datetime(observed["timestamp"], utc=True, format="ISO8601").min()
        earliest = first + pd.Timedelta(hours=warmup_hours + lag_h)
        if start is not None:
            earliest = max(earliest, _utc(start, "start"))
        local_dates = pd.date_range(
            earliest.tz_convert(LOCAL_TZ).date(), last_origin.tz_convert(LOCAL_TZ).date(), freq="D"
        )
        midnights = local_dates.tz_localize(LOCAL_TZ).tz_convert("UTC")
        midnights = midnights[(midnights >= earliest) & (midnights <= last_origin)]
        out.append(pd.DataFrame({"counter_id": counter_id, "origin": midnights}))
    if not out:
        return pd.DataFrame(
            {"counter_id": pd.Series(dtype=str), "origin": pd.Series(dtype="datetime64[ns, UTC]")}
        )
    return pd.concat(out, ignore_index=True)


def training_counters(inventory: pd.DataFrame, include_robustness: bool = True) -> list[str]:
    """Compteurs sites connus (S_train) de l'inventaire E1, période de sélection.

    retained seulement, ou aussi robustness (par défaut). Refuse un compteur dont le
    site_group_id appartient aussi à un groupe réservé à E3 (S_dev_new, S_test_new).
    """
    inv = inventory
    if "period_role" in inv.columns:
        inv = inv.loc[inv["period_role"] == "selection"]
    statuses = {"retained", "robustness"} if include_robustness else {"retained"}
    train = inv.loc[(inv["site_role"] == "S_train") & inv["selection_status"].isin(statuses)]
    reserved = inv.loc[inv["site_role"].isin(["S_dev_new", "S_test_new"]), "site_group_id"]
    overlap = set(train["site_group_id"].dropna()) & set(reserved.dropna())
    if overlap:
        raise ValueError(f"groupes de sites à la fois S_train et réservés : {sorted(overlap)}")
    return sorted(set(train["counter_id"].astype(str)))


# --------------------------------------------------------------------------- calcul commun


@dataclass
class _Grid:
    """Série horaire régulière d'un compteur (NaN = pas de mesure) et cumuls associés."""

    start: int  # heure absolue (heures depuis l'époque Unix) de la première case
    values: np.ndarray
    csum_val: np.ndarray | None = None
    csum_n: np.ndarray | None = None
    last_obs: np.ndarray | None = None
    zero_run: np.ndarray | None = None


def _make_grid(hours: np.ndarray, values: np.ndarray, stats: bool = True) -> _Grid:
    if len(hours) == 0:
        empty = np.empty(0)
        return _Grid(0, empty, np.zeros(1), np.zeros(1, dtype=np.int64), empty, empty)
    if len(np.unique(hours)) != len(hours):
        raise ValueError("timestamp en double : jointure ambiguë")
    start = int(hours.min())
    arr = np.full(int(hours.max()) - start + 1, np.nan)
    arr[hours - start] = values
    if not stats:
        return _Grid(start, arr)
    observed = ~np.isnan(arr)
    csum_val = np.concatenate([[0.0], np.cumsum(np.where(observed, arr, 0.0))])
    csum_n = np.concatenate([[0], np.cumsum(observed)])
    last_obs = np.maximum.accumulate(np.where(observed, np.arange(len(arr)), -1))
    # Suite de zéros mesurés consécutifs (heures sans mesure ignorées), à chaque mesure.
    zero_run = np.full(len(arr), np.nan)
    idx = np.flatnonzero(observed)
    is_zero = arr[idx] == 0
    groups = np.cumsum(~is_zero)
    zero_run[idx] = pd.Series(is_zero.astype(np.int64)).groupby(groups).cumsum().to_numpy()
    return _Grid(start, arr, csum_val, csum_n, last_obs, zero_run)


def _value_at(grid: _Grid, hours: np.ndarray) -> np.ndarray:
    rel = hours - grid.start
    out = np.full(len(rel), np.nan)
    ok = (rel >= 0) & (rel < len(grid.values))
    out[ok] = grid.values[rel[ok]]
    return out


def _window(grid: _Grid, end_hours: np.ndarray, length: int) -> tuple[np.ndarray, np.ndarray]:
    """Moyenne et nombre de mesures sur les length heures finissant à end_hours (inclus)."""
    n = len(grid.values)
    b = np.clip(end_hours - grid.start + 1, 0, n)
    a = np.clip(end_hours - grid.start + 1 - length, 0, n)
    count = grid.csum_n[b] - grid.csum_n[a]
    total = grid.csum_val[b] - grid.csum_val[a]
    mean = np.full(len(end_hours), np.nan)
    np.divide(total, count, out=mean, where=count > 0)
    return mean, count


def _last_observed(grid: _Grid, end_hours: np.ndarray) -> np.ndarray:
    """Position relative de la dernière mesure <= end_hours, -1 si aucune."""
    rel = end_hours - grid.start
    out = np.full(len(rel), -1, dtype=np.int64)
    ok = (rel >= 0) & (len(grid.values) > 0)
    out[ok] = grid.last_obs[np.minimum(rel[ok], len(grid.values) - 1)]
    return out


def _history_core(
    grid: _Grid, origin_h: np.ndarray, target_h: np.ndarray, lag_h: int
) -> dict[str, np.ndarray]:
    """Variables d'historique ; ne lit que les heures dont interval_end <= origin - lag."""
    last = origin_h - lag_h - 1  # dernière heure (début d'intervalle) admissible
    lagged = []
    for k in range(1, PROFILE_WEEKS + 1):
        source = target_h - k * WEEK_HOURS
        value = _value_at(grid, source)
        value[source > last] = np.nan
        lagged.append(value)
    stack = np.vstack(lagged)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # médiane d'une colonne vide -> NaN
        profile = np.nanmedian(stack, axis=0)
    level_24, _ = _window(grid, last, 24)
    level_168, n_168 = _window(grid, last, WEEK_HOURS)
    level_prev, _ = _window(grid, last - WEEK_HOURS, WEEK_HOURS)
    with np.errstate(invalid="ignore"):
        trend = np.log1p(level_168) - np.log1p(level_prev)
    pos = _last_observed(grid, last)
    has_obs = pos >= 0
    last_end = np.where(has_obs, grid.start + pos + 1, -1)
    zero_run = np.full(len(pos), np.nan)
    zero_run[has_obs] = grid.zero_run[pos[has_obs]]
    return {
        "lag_168h": stack[0],
        "lag_336h": stack[1],
        "lag_168h_missing": np.isnan(stack[0]).astype(float),
        "lag_336h_missing": np.isnan(stack[1]).astype(float),
        "profile_median_4w": profile,
        "profile_n_weeks": (~np.isnan(stack)).sum(axis=0).astype(float),
        "level_24h": level_24,
        "level_168h": level_168,
        "level_prev_168h": level_prev,
        "trend_7d_log": trend,
        "missing_share_168h": 1.0 - n_168 / WEEK_HOURS,
        "hours_since_last_obs": np.where(has_obs, origin_h - last_end, np.nan).astype(float),
        "zero_run_hours": zero_run,
        # Interne : disponibilité de la dernière mesure lue (règle provisoire end + latence).
        "_available_h": np.where(has_obs, last_end + lag_h, np.nan).astype(float),
    }


def _calendar_core(target_h: np.ndarray) -> dict[str, np.ndarray]:
    unique, inverse = np.unique(target_h, return_inverse=True)
    local = pd.DatetimeIndex(unique * HOUR_NS, tz="UTC").tz_convert(LOCAL_TZ)
    dow = local.dayofweek.to_numpy()
    return {
        "hour_local": local.hour.to_numpy()[inverse].astype(float),
        "dow_local": dow[inverse].astype(float),
        "is_weekend": (dow >= 5)[inverse].astype(float),
        "month_local": local.month.to_numpy()[inverse].astype(float),
    }


def _prepare_context(
    context: pd.DataFrame | None, groups: Iterable[str]
) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Tables de jointure par variable : valeur et disponibilité (heures), clé unique."""
    variables = [v for g in groups for v in CONTEXT_GROUPS[g]]
    if context is None or not variables or context.empty:
        return {}
    ctx = context.loc[context["variable"].isin(variables)]
    if "role" in ctx.columns:
        ctx = ctx.loc[ctx["role"].isin(ALLOWED_ROLES)]
    tables: dict[str, tuple[pd.Series, pd.Series]] = {}
    for variable, sub in ctx.groupby("variable"):
        if variable in DAILY_VARIABLES:
            key = sub["local_date"].astype(str).to_numpy()
        else:
            key = _to_hours(sub["valid_time"], "valid_time")
        if len(pd.unique(key)) != len(key):
            raise ValueError(f"contexte {variable} : clé de jointure en double")
        available = pd.to_datetime(sub["available_at"], utc=True, format="ISO8601")
        available_h = available.dt.as_unit("ns").astype("int64").to_numpy() / HOUR_NS
        available_h = np.where(available.isna().to_numpy(), np.nan, available_h)
        tables[variable] = (
            pd.Series(_parse_values(sub["value"]), index=key),
            pd.Series(available_h, index=key),
        )
    return tables


def _context_core(
    tables: dict[str, tuple[pd.Series, pd.Series]],
    origin_h: np.ndarray,
    target_h: np.ndarray,
    groups: Iterable[str],
) -> dict[str, np.ndarray]:
    unique, inverse = np.unique(target_h, return_inverse=True)
    local_dates = (
        pd.DatetimeIndex(unique * HOUR_NS, tz="UTC").tz_convert(LOCAL_TZ).strftime("%Y-%m-%d")
    )
    out: dict[str, np.ndarray] = {}
    max_available = np.full(len(target_h), np.nan)
    for group in groups:
        for variable in CONTEXT_GROUPS[group]:
            if variable not in tables:
                out[variable] = np.full(len(target_h), np.nan)
                continue
            values, available = tables[variable]
            keys = local_dates if variable in DAILY_VARIABLES else unique + 1  # interval_end
            value = values.reindex(keys).to_numpy(dtype=float)[inverse]
            avail = available.reindex(keys).to_numpy(dtype=float)[inverse]
            late = ~np.isnan(avail) & (avail > origin_h)
            value[late] = np.nan
            used = ~np.isnan(value) & ~np.isnan(avail)
            max_available = np.where(used, np.fmax(max_available, avail), max_available)
            out[variable] = value
    out["_available_h"] = max_available
    return out


def _assemble(
    grid: _Grid,
    tables: dict[str, tuple[pd.Series, pd.Series]],
    groups: tuple[str, ...],
    origin_h: np.ndarray,
    target_h: np.ndarray,
    lag_h: int,
    *,
    case_ids: np.ndarray,
    counter_id: str,
) -> pd.DataFrame:
    """Calcul commun aux deux chemins : mêmes fonctions, mêmes types, même ordre."""
    history = _history_core(grid, origin_h, target_h, lag_h)
    calendar = _calendar_core(target_h)
    context = _context_core(tables, origin_h, target_h, groups) if groups else {}
    available = np.fmax(history["_available_h"], context.get("_available_h", np.nan))
    if (available > origin_h).any():
        raise AssertionError("entrée disponible après l'origine : fuite")

    frame = pd.DataFrame(
        {
            "feature_version": FEATURE_VERSION,
            "case_id": case_ids,
            "counter_id": counter_id,
            "origin": pd.DatetimeIndex(origin_h * HOUR_NS, tz="UTC"),
            "target_timestamp": pd.DatetimeIndex(target_h * HOUR_NS, tz="UTC"),
            "horizon": (target_h - origin_h + 1).astype(np.int16),
            "max_input_available_at": pd.to_datetime(available, unit="h", utc=True),
        }
    )
    for column in feature_columns(groups):
        if column == "horizon":
            continue
        source = calendar if column in calendar else history if column in history else context
        frame[column] = source[column].astype(np.float32)
    return frame


# --------------------------------------------------------------------------- utilitaires


def _case_grid(inputs: ForecastInputs) -> tuple[int, int, _Grid]:
    """Origine, latence et grille du passé admissible d'un cas."""
    origin_h = _hour_of(inputs.case.origin, "origin")
    cutoff_h = _hour_of(inputs.information_cutoff, "information_cutoff")
    lag_h = origin_h - cutoff_h
    if lag_h < 0:
        raise ValueError("information_cutoff postérieure à l'origine")
    history = baseline.admissible_history(
        inputs.history, inputs.information_cutoff, counter_id=inputs.case.counter_id
    )
    hours = _to_hours(history["timestamp"], "timestamp")
    values = pd.to_numeric(history["count"], errors="coerce").to_numpy(dtype=float)
    return origin_h, lag_h, _make_grid(hours, values)


def _to_hours(values: pd.Series | pd.Index | Iterable, name: str) -> np.ndarray:
    """Timestamps avec fuseau -> heures entières depuis l'époque Unix (UTC)."""
    series = pd.Series(values)
    if series.empty:
        return np.empty(0, dtype=np.int64)
    if pd.api.types.is_datetime64_any_dtype(series):
        if series.dt.tz is None:
            raise ValueError(f"{name} : timestamps sans fuseau")
        stamps = series.dt.tz_convert("UTC")
    else:
        text = series.astype(str)
        if not text.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True).all():
            raise ValueError(f"{name} : timestamps sans fuseau")
        stamps = pd.to_datetime(series, utc=True, format="ISO8601")
    ns = stamps.dt.as_unit("ns").astype("int64").to_numpy()
    if (ns % HOUR_NS != 0).any():
        raise ValueError(f"{name} : timestamps non alignés sur l'heure")
    return ns // HOUR_NS


def _hour_of(value: pd.Timestamp, name: str) -> int:
    return int(_to_hours(pd.Series([_utc(value, name)]), name)[0])


def _utc(value: pd.Timestamp, name: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError(f"{name} doit porter un fuseau")
    return stamp.tz_convert("UTC")


def _as_bool(values: pd.Series) -> np.ndarray:
    if values.dtype == bool:
        return values.to_numpy()
    text = values.astype(str).str.strip().str.lower()
    return text.isin(["true", "1", "1.0"]).to_numpy()


def _parse_values(values: pd.Series) -> np.ndarray:
    text = values.astype(str).str.strip().str.lower()
    numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    return np.where(text == "true", 1.0, np.where(text == "false", 0.0, numeric))


def _default_lag() -> int:
    """Latence simulée de config/project*.yaml (protocol.publication_lag_hours)."""
    protocol = load_config().get("protocol") or {}
    return int(protocol.get("publication_lag_hours", 24))

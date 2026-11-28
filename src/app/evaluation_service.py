"""Lecture des résultats officiels E4 (scores et couverture) pour le tableau de bord E5.

Ce module ne calcule aucune métrique : il lit ``scores.csv``, ``coverage.csv`` et
``scoring_manifest.json`` produits par ``src/eval/backtest.py`` sous
``data/evaluation/<protocol_id>/EXP-E2|EXP-E3/``, vérifie leur contrat et leur
intégrité, puis les met à disposition de ``src/app/dashboard/comparison.py``.

Conventions reprises d'E4 :
- colonnes : ``backtest.COLUMNS_SCORES`` et ``backtest.COLUMNS_COVERAGE`` ;
- populations : ``<scenario>[_b<budget>]_<début>-<fin>_self`` (chaque méthode sur ses
  propres cas) et ``..._common_complete`` (cas complets communs à toutes les méthodes) ;
- statuts de couverture : ceux de ``metrics.calculate_coverage`` ;
- une valeur absente reste absente (``NaN`` / ``<NA>``) : jamais remplacée par zéro.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import data_path, load_config
from src.eval.backtest import COLUMNS_COVERAGE, COLUMNS_SCORES, EXP_ID

_CONFIG = load_config()
PROTOCOL_ID: str = _CONFIG["protocol"]["id"]
LOCAL_BUDGETS: tuple[int, ...] = tuple(int(b) for b in _CONFIG["protocol"]["local_budget_hours"])

EXPERIMENTS: dict[str, str] = {experiment.removeprefix("EXP-"): experiment for experiment in EXP_ID}
TEAMS: tuple[str, ...] = tuple(EXPERIMENTS)
SCENARIOS: dict[str, str] = {"E2": "known_site", "E3": "new_site"}

SCORE_COLUMNS: tuple[str, ...] = tuple(COLUMNS_SCORES)
COVERAGE_COLUMNS: tuple[str, ...] = tuple(COLUMNS_COVERAGE)
COMPARISON_METADATA: tuple[str, ...] = (
    "scenario",
    "temporal_split",
    "comparison_population_id",
    "protocol_id",
    "snapshot_id",
)
SCORES_FILE = "scores.csv"
COVERAGE_FILE = "coverage.csv"
MANIFEST_FILE = "scoring_manifest.json"

POPULATION_SELF = "self"
POPULATION_COMMON = "common_complete"
POPULATION_KINDS: tuple[str, ...] = (POPULATION_SELF, POPULATION_COMMON)

# Statuts produits par src/eval/metrics.calculate_coverage.
COMPLETE_STATUSES = frozenset({"complete", "fallback_complete"})
COVERAGE_STATUSES = COMPLETE_STATUSES | {"partial", "error", "no_forecast"}

_TEXT_SCORE_COLUMNS = (
    "experiment_id",
    "method_run_id",
    "variant",
    *COMPARISON_METADATA,
)
# Comptages toujours renseignés par E4.
_REQUIRED_COUNTS = (
    "n_expected_cases",
    "n_complete_cases",
    "n_compared_cases",
    "n_compared_hours",
    "n_evaluable_counters",
)
# Métriques pouvant légitimement manquer (aucune heure évaluable, population commune...).
_OPTIONAL_METRICS = ("mae_macro", "rmse", "r2", "bias", "coverage_24h")
_SCORE_KEY = ("method_run_id", "variant", "comparison_population_id")
_COVERAGE_KEY = ("method_run_id", "variant", "local_budget_hours")


class EvaluationDataError(ValueError):
    """Un fichier officiel E4 est présent mais ne respecte pas son contrat."""


# --------------------------------------------------------------------- fichiers


def experiment_dir(team: str, root: Path | None = None) -> Path:
    """Dossier ``<root>/EXP-<team>`` ; ``root`` vaut ``data/evaluation/<protocol_id>``."""
    if team not in EXPERIMENTS:
        raise ValueError(f"Équipe inconnue {team!r} : attendu l'une de {list(TEAMS)}.")
    base = Path(root) if root is not None else data_path("evaluation") / PROTOCOL_ID
    return base / EXPERIMENTS[team]


def _required_file(team: str, name: str, root: Path | None) -> Path:
    path = experiment_dir(team, root) / name
    if not path.is_file():
        raise FileNotFoundError(f"Résultat officiel E4 absent pour {team} : {path}")
    return path


def load_manifest(team: str, root: Path | None = None) -> dict:
    """Lire ``scoring_manifest.json`` et contrôler l'expérience déclarée."""
    path = _required_file(team, MANIFEST_FILE, root)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise EvaluationDataError(f"{path} : JSON illisible ({error}).") from error
    missing = {"experiment_id", "protocol_id", "snapshot_id", "outputs_sha256"} - set(manifest)
    if missing:
        raise EvaluationDataError(f"{path} : champs manquants {sorted(missing)}.")
    if manifest["experiment_id"] != EXPERIMENTS[team]:
        raise EvaluationDataError(
            f"{path} : experiment_id {manifest['experiment_id']!r} au lieu de "
            f"{EXPERIMENTS[team]!r}."
        )
    return manifest


def _declared_hashes(manifest: dict) -> dict[str, str]:
    # E4 écrit des chemins « / » ou « \ » selon le poste : seul le nom du fichier compte.
    return {re.split(r"[\\/]", key)[-1]: value for key, value in manifest["outputs_sha256"].items()}


def _same_content(path: Path, expected: str) -> bool:
    """Comparer l'empreinte en tolérant la conversion LF/CRLF faite par Git ou OneDrive."""
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    candidates = (raw, lf, lf.replace(b"\n", b"\r\n"))
    return any(hashlib.sha256(data).hexdigest() == expected for data in candidates)


def verify_outputs(team: str, root: Path | None = None) -> dict[str, str]:
    """État de chaque sortie déclarée : ``conforme``, ``modifié`` ou ``absent``."""
    manifest = load_manifest(team, root)
    folder = experiment_dir(team, root)
    states = {}
    for name, expected in _declared_hashes(manifest).items():
        path = folder / name
        if not path.is_file():
            states[name] = "absent"
        else:
            states[name] = "conforme" if _same_content(path, expected) else "modifié"
    return states


def _read_official_csv(
    team: str, name: str, columns: tuple[str, ...], root: Path | None, verify: bool
) -> tuple[pd.DataFrame, dict, Path]:
    path = _required_file(team, name, root)
    manifest = load_manifest(team, root)
    if verify:
        expected = _declared_hashes(manifest).get(name)
        if expected is None:
            raise EvaluationDataError(f"{name} n'est pas déclaré dans le manifeste {team}.")
        if not _same_content(path, expected):
            raise EvaluationDataError(
                f"{path} diffère de l'empreinte du manifeste E4 : fichier modifié ou périmé."
            )
    table = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in columns if column not in table.columns]
    if missing:
        raise EvaluationDataError(f"{path} : colonnes manquantes {missing}.")
    for column in table.columns:
        table[column] = table[column].str.strip()
    return table, manifest, path


# ------------------------------------------------------------- conversions


def _rows(mask: pd.Series) -> str:
    lines = (mask[mask].index + 2).tolist()  # +2 : en-tête et numérotation à partir de 1
    return ", ".join(map(str, lines[:10])) + (" ..." if len(lines) > 10 else "")


def _numeric(
    table: pd.DataFrame,
    column: str,
    path: Path,
    *,
    required: bool = False,
    integer: bool = False,
    minimum: float | None = None,
    maximum: float | None = None,
) -> pd.Series:
    """Convertir sans jamais transformer une cellule vide en zéro ni ignorer un texte."""
    text = table[column]
    missing = text.eq("")
    values = pd.to_numeric(text.mask(missing), errors="coerce").astype(float)
    invalid = ~missing & (values.isna() | ~np.isfinite(values))
    if invalid.any():
        raise EvaluationDataError(
            f"{path} : {column} non numérique ou infini (lignes {_rows(invalid)})."
        )
    if required and missing.any():
        raise EvaluationDataError(f"{path} : {column} vide (lignes {_rows(missing)}).")
    if minimum is not None and (values < minimum).any():
        raise EvaluationDataError(
            f"{path} : {column} inférieur à {minimum} (lignes {_rows(values < minimum)})."
        )
    if maximum is not None and (values > maximum).any():
        raise EvaluationDataError(
            f"{path} : {column} supérieur à {maximum} (lignes {_rows(values > maximum)})."
        )
    if integer:
        fractional = values.notna() & values.ne(values.round())
        if fractional.any():
            raise EvaluationDataError(f"{path} : {column} non entier (lignes {_rows(fractional)}).")
        return values.astype("Int64")
    return values


def _boolean(table: pd.DataFrame, column: str, path: Path) -> pd.Series:
    text = table[column].str.lower()
    known = text.isin(["true", "false"])
    if not known.all():
        raise EvaluationDataError(
            f"{path} : {column} doit valoir True ou False (lignes {_rows(~known)})."
        )
    return text.eq("true")


def _check_identity(table: pd.DataFrame, manifest: dict, team: str, path: Path) -> None:
    for column in ("protocol_id", "snapshot_id"):
        wrong = table[column].ne(str(manifest[column]))
        if wrong.any():
            raise EvaluationDataError(
                f"{path} : {column} différent du manifeste {manifest[column]!r} "
                f"(lignes {_rows(wrong)})."
            )
    wrong = table["scenario"].ne(SCENARIOS[team])
    if wrong.any():
        raise EvaluationDataError(
            f"{path} : scénario autre que {SCENARIOS[team]!r} pour {team} (lignes {_rows(wrong)})."
        )


def _check_budgets(table: pd.DataFrame, team: str, path: Path) -> None:
    budgets = table["local_budget_hours"]
    if team == "E2":
        wrong = budgets.notna()
        message = "un cas E2 ne déclare pas de budget local"
    else:
        wrong = ~budgets.isin(LOCAL_BUDGETS) | budgets.isna()
        message = f"budget E3 attendu parmi {list(LOCAL_BUDGETS)}"
    if wrong.any():
        raise EvaluationDataError(f"{path} : {message} (lignes {_rows(wrong.fillna(True))}).")


# ------------------------------------------------------------------ scores


def population_kind(population_id: str) -> str:
    """Type de population E4 : ``self`` ou ``common_complete``."""
    for kind in POPULATION_KINDS:
        if str(population_id).endswith(f"_{kind}"):
            return kind
    raise EvaluationDataError(f"Population de comparaison inconnue : {population_id!r}.")


def load_scores(team: str, root: Path | None = None, *, verify: bool = True) -> pd.DataFrame:
    """Lire les scores officiels d'une équipe, typés et contrôlés.

    Retourne les colonnes de ``backtest.COLUMNS_SCORES`` (plus ``team`` et
    ``population_kind``). Les métriques absentes restent ``NaN``, les comptages et budgets
    sont des entiers nullables (``Int64``).
    """
    raw, manifest, path = _read_official_csv(team, SCORES_FILE, SCORE_COLUMNS, root, verify)
    scores = raw.copy()

    empty_text = raw[list(_TEXT_SCORE_COLUMNS)].eq("")
    if empty_text.any().any():
        columns = empty_text.columns[empty_text.any()].tolist()
        raise EvaluationDataError(f"{path} : identifiants vides dans {columns}.")
    wrong = raw["experiment_id"].ne(EXPERIMENTS[team])
    if wrong.any():
        raise EvaluationDataError(f"{path} : experiment_id inattendu (lignes {_rows(wrong)}).")
    _check_identity(raw, manifest, team, path)

    for column in _REQUIRED_COUNTS:
        scores[column] = _numeric(raw, column, path, required=True, integer=True, minimum=0)
    scores["n_fallback_cases"] = _numeric(raw, "n_fallback_cases", path, integer=True, minimum=0)
    scores["local_budget_hours"] = _numeric(
        raw, "local_budget_hours", path, integer=True, minimum=1
    )
    scores["mae_macro"] = _numeric(raw, "mae_macro", path, minimum=0)
    scores["rmse"] = _numeric(raw, "rmse", path, minimum=0)
    scores["r2"] = _numeric(raw, "r2", path, maximum=1)
    scores["bias"] = _numeric(raw, "bias", path)
    scores["coverage_24h"] = _numeric(raw, "coverage_24h", path, minimum=0, maximum=1)
    _check_budgets(scores, team, path)

    too_many = scores["n_complete_cases"].gt(scores["n_expected_cases"]) | scores[
        "n_compared_cases"
    ].gt(scores["n_expected_cases"])
    if too_many.any():
        raise EvaluationDataError(
            f"{path} : plus de cas complets ou comparés que de cas attendus "
            f"(lignes {_rows(too_many)})."
        )
    # E4 laisse la MAE vide seulement quand aucune heure n'est évaluable.
    incoherent = scores["mae_macro"].isna() != scores["n_compared_hours"].eq(0)
    if incoherent.any():
        raise EvaluationDataError(
            f"{path} : mae_macro incohérente avec n_compared_hours (lignes {_rows(incoherent)})."
        )

    scores["population_kind"] = scores["comparison_population_id"].map(population_kind)
    if team == "E3":
        tags = "_b" + scores["local_budget_hours"].astype(str) + "_"
        wrong = ~pd.Series(
            [tag in pid for tag, pid in zip(tags, scores["comparison_population_id"])],
            index=scores.index,
        )
        if wrong.any():
            raise EvaluationDataError(
                f"{path} : population sans le budget déclaré (lignes {_rows(wrong)})."
            )
    duplicated = scores.duplicated(list(_SCORE_KEY), keep=False)
    if duplicated.any():
        raise EvaluationDataError(
            f"{path} : plusieurs scores pour une même méthode et population "
            f"(lignes {_rows(duplicated)})."
        )
    scores.insert(0, "team", team)
    return scores.reset_index(drop=True)


def available_budgets(table: pd.DataFrame) -> list[int]:
    """Budgets historiques E3 présents dans une table de scores ou de couverture."""
    return sorted(int(b) for b in table["local_budget_hours"].dropna().unique())


def filter_budget(table: pd.DataFrame, budget: int) -> pd.DataFrame:
    """Garder les lignes E3 d'un budget historique (24, 72 ou 168 h)."""
    if int(budget) not in LOCAL_BUDGETS:
        raise ValueError(f"Budget {budget} h inconnu : attendu l'un de {list(LOCAL_BUDGETS)}.")
    if table["scenario"].ne(SCENARIOS["E3"]).any():
        raise ValueError("Le filtre de budget historique ne s'applique qu'aux résultats E3.")
    return table.loc[table["local_budget_hours"].eq(int(budget))].reset_index(drop=True)


def comparison_groups(scores: pd.DataFrame) -> pd.DataFrame:
    """Combinaisons de métadonnées disponibles, avec le nombre de méthodes de chacune."""
    columns = [*COMPARISON_METADATA, "local_budget_hours", "population_kind"]
    return (
        scores.groupby(columns, dropna=False)
        .agg(n_methods=("method_run_id", "nunique"))
        .reset_index()
        .sort_values(columns, na_position="first")
        .reset_index(drop=True)
    )


def select_population(scores: pd.DataFrame, comparison_population_id: str) -> pd.DataFrame:
    """Scores d'une seule population E4, comparables entre méthodes.

    Refuse une population inconnue, mêlant plusieurs protocoles, instantanés, scénarios
    ou découpages temporels, ou contenant deux lignes pour une même méthode.
    """
    rows = scores.loc[scores["comparison_population_id"].eq(comparison_population_id)]
    if rows.empty:
        raise ValueError(f"Population de comparaison absente : {comparison_population_id!r}.")
    for column in COMPARISON_METADATA:
        if rows[column].nunique(dropna=False) != 1:
            raise EvaluationDataError(
                f"La population {comparison_population_id!r} mélange plusieurs {column}."
            )
    if rows.duplicated(["method_run_id", "variant"]).any():
        raise EvaluationDataError(
            f"La population {comparison_population_id!r} contient une méthode en double."
        )
    return rows.reset_index(drop=True)


def ranked_methods(population: pd.DataFrame) -> pd.DataFrame:
    """Trier une population par MAE macro officielle ; les MAE absentes restent en fin."""
    return population.sort_values(
        ["mae_macro", "method_run_id"], na_position="last", kind="stable"
    ).reset_index(drop=True)


# ---------------------------------------------------------------- couverture


def load_coverage(team: str, root: Path | None = None, *, verify: bool = True) -> pd.DataFrame:
    """Lire la couverture officielle par cas, méthode et variante."""
    raw, manifest, path = _read_official_csv(team, COVERAGE_FILE, COVERAGE_COLUMNS, root, verify)
    coverage = raw.copy()
    _check_identity(raw, manifest, team, path)

    unknown = ~raw["coverage_status"].isin(COVERAGE_STATUSES)
    if unknown.any():
        raise EvaluationDataError(f"{path} : coverage_status inconnu (lignes {_rows(unknown)}).")
    coverage["n_predicted_hours"] = _numeric(
        raw, "n_predicted_hours", path, required=True, integer=True, minimum=0, maximum=24
    )
    coverage["local_budget_hours"] = _numeric(
        raw, "local_budget_hours", path, integer=True, minimum=1
    )
    coverage["is_complete_24h"] = _boolean(raw, "is_complete_24h", path)
    coverage["origin"] = pd.to_datetime(raw["origin"], format="ISO8601", utc=True)
    _check_budgets(coverage, team, path)

    complete = coverage["is_complete_24h"]
    incoherent = (complete != coverage["coverage_status"].isin(COMPLETE_STATUSES)) | (
        complete != coverage["n_predicted_hours"].eq(24)
    )
    if incoherent.any():
        raise EvaluationDataError(
            f"{path} : is_complete_24h, coverage_status et n_predicted_hours incohérents "
            f"(lignes {_rows(incoherent)})."
        )
    duplicated = coverage.duplicated(["case_id", "method_run_id", "variant"], keep=False)
    if duplicated.any():
        raise EvaluationDataError(f"{path} : cas en double (lignes {_rows(duplicated)}).")
    coverage.insert(0, "team", team)
    return coverage.reset_index(drop=True)


def summarize_coverage(coverage: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Résumer la couverture par méthode, variante et budget sans confondre les notions.

    - ``n_predicted_cases`` : au moins une heure prévue (couverture E4) ;
    - ``n_complete_cases`` : les 24 heures prévues, repli compris (couverture E4) ;
    - ``n_evaluable_cases`` : au moins une heure prévue *et* mesurée, repris tel quel de
      ``n_compared_cases`` dans la population ``_self`` de ``scores.csv``.
    ``matches_scores`` signale un écart entre ``coverage.csv`` et ``scores.csv``.
    """
    keys = list(_COVERAGE_KEY)
    status = coverage["coverage_status"]
    counts = (
        coverage.assign(
            _predicted=coverage["n_predicted_hours"].gt(0),
            _fallback=status.eq("fallback_complete"),
            _partial=status.eq("partial"),
            _error=status.eq("error"),
            _empty=status.eq("no_forecast"),
        )
        .groupby(keys, dropna=False)
        .agg(
            n_coverage_cases=("case_id", "size"),
            n_predicted_cases=("_predicted", "sum"),
            n_complete_cases=("is_complete_24h", "sum"),
            n_fallback_complete_cases=("_fallback", "sum"),
            n_partial_cases=("_partial", "sum"),
            n_error_cases=("_error", "sum"),
            n_no_forecast_cases=("_empty", "sum"),
        )
        .reset_index()
    )
    official = scores.loc[
        scores["population_kind"].eq(POPULATION_SELF),
        [
            *keys,
            *COMPARISON_METADATA,
            "n_expected_cases",
            "n_complete_cases",
            "n_compared_cases",
            "coverage_24h",
        ],
    ].rename(
        columns={
            "n_complete_cases": "scores_n_complete_cases",
            "n_compared_cases": "n_evaluable_cases",
        }
    )
    if official.duplicated(keys).any():
        raise EvaluationDataError(
            "Plusieurs populations _self par méthode : coverage.csv ne permet pas de les séparer."
        )
    summary = counts.merge(official, on=keys, how="left", validate="one_to_one")
    summary["matches_scores"] = summary["n_coverage_cases"].eq(
        summary["n_expected_cases"]
    ) & summary["n_complete_cases"].eq(summary["scores_n_complete_cases"])
    summary["matches_scores"] = summary["matches_scores"].fillna(False).astype(bool)
    order = [
        *keys,
        *COMPARISON_METADATA,
        "n_expected_cases",
        "n_coverage_cases",
        "n_predicted_cases",
        "n_complete_cases",
        "n_fallback_complete_cases",
        "n_partial_cases",
        "n_error_cases",
        "n_no_forecast_cases",
        "n_evaluable_cases",
        "coverage_24h",
        "matches_scores",
    ]
    return summary[order].sort_values(keys).reset_index(drop=True)


# ------------------------------------------------------------- ensemble E2/E3


@dataclass
class TeamResults:
    team: str
    scores: pd.DataFrame
    coverage: pd.DataFrame
    manifest: dict

    def coverage_summary(self) -> pd.DataFrame:
        return summarize_coverage(self.coverage, self.scores)


@dataclass
class OfficialResults:
    """Résultats E2 et E3 séparés ; ``problems`` explique une équipe indisponible."""

    teams: dict[str, TeamResults] = field(default_factory=dict)
    problems: dict[str, str] = field(default_factory=dict)

    def scores(self, team: str) -> pd.DataFrame:
        if team in self.teams:
            return self.teams[team].scores
        return pd.DataFrame(columns=["team", *SCORE_COLUMNS, "population_kind"])


def load_team_results(team: str, root: Path | None = None, *, verify: bool = True) -> TeamResults:
    return TeamResults(
        team,
        load_scores(team, root, verify=verify),
        load_coverage(team, root, verify=verify),
        load_manifest(team, root),
    )


def load_official_results(root: Path | None = None, *, verify: bool = True) -> OfficialResults:
    """Charger E2 et E3 indépendamment : l'échec de l'une n'empêche pas l'autre."""
    results = OfficialResults()
    for team in TEAMS:
        try:
            results.teams[team] = load_team_results(team, root, verify=verify)
        except (FileNotFoundError, EvaluationDataError) as error:
            results.problems[team] = str(error)
    return results

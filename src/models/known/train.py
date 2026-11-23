"""Apprentissage et comparaison des méthodes sur sites connus - E2.

À faire :
1. Lire les cas et séparations proposés par E4, puis utiliser le protocole validé.
2. Exclure les sites réservés d'E3 ; vérifier la disponibilité des labels à la coupure.
3. Comparer au moins une variante explicative et coordonner l'expérience DL collective.
4. Sauvegarder paramètres, provenance, coût et poids dans artifacts/models/ ; préserver le test final.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.config import ROOT, data_path, load_config
from src.models.known.features import LOCAL_TZ, _default_lag, training_counters, training_origins
from src.models.schemas import HORIZON_HOURS

METHOD_NAME = "known_site_model"
RUN_ID_PREFIX = "e2"
CONFIG_HASH_CHARS = 4
METADATA_FILE = "metadata.json"
METADATA_SCHEMA_VERSION = 2
# Lecture de counts.csv : mêmes colonnes et mêmes politiques que predict.py.
VALUE_POLICIES = ("measured", "e1_filled")
COUNT_COLUMNS = [
    "counter_id",
    "timestamp",
    "interval_end",
    "count_raw",
    "count",
    "is_observed",
    "is_scoreable",
]


@dataclass
class TrainConfig:
    """Réglages figés avant toute mesure sur la période de test."""

    method: str  # ex. "hgb", "mlp"
    fit_cutoff: pd.Timestamp
    train_start: pd.Timestamp | None = None  # None = depuis le début des données
    use_context: bool = True
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    protocol_id: str | None = None
    snapshot_id: str | None = None
    context_version: str | None = None
    feature_version: str | None = None


def config_fingerprint(config: TrainConfig) -> str:
    """Empreinte SHA-256 de tous les réglages : un réglage différent donne une empreinte différente.

    Le JSON est trié et sans espaces pour qu'une même config donne toujours les mêmes octets.
    """
    payload = {
        "method": config.method,
        "fit_cutoff": pd.Timestamp(config.fit_cutoff).tz_convert("UTC").isoformat(),
        "train_start": _iso_utc_or_none(config.train_start),
        "use_context": config.use_context,
        "hyperparameters": config.hyperparameters,
        "seed": config.seed,
        "protocol_id": config.protocol_id,
        "snapshot_id": config.snapshot_id,
        "context_version": config.context_version,
        "feature_version": config.feature_version,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_model_run_id(config: TrainConfig) -> str:
    """Nom lisible et unique d'un modèle entraîné.

    Format : e2-<méthode>-<ctx|noctx>-<coupure AAAAMMJJ, heure de Paris>-s<graine>-<empreinte>
    Exemple : e2-mlp-ctx-20260701-s0-a3f9
    """
    method = re.sub(r"[^a-z0-9]+", "-", config.method.lower()).strip("-")
    if not method:
        raise ValueError(f"nom de méthode invalide : {config.method!r}")
    cutoff = pd.Timestamp(config.fit_cutoff)
    if cutoff.tzinfo is None:
        raise ValueError("fit_cutoff doit porter un fuseau horaire (UTC)")
    cutoff_day = cutoff.tz_convert(LOCAL_TZ).strftime("%Y%m%d")
    context = "ctx" if config.use_context else "noctx"
    short_hash = config_fingerprint(config)[:CONFIG_HASH_CHARS]
    return f"{RUN_ID_PREFIX}-{method}-{context}-{cutoff_day}-s{config.seed}-{short_hash}"


@dataclass
class TrainedModel:
    """Modèle entraîné et métadonnées (doc/templates/model_metadata.example.json)."""

    model_run_id: str
    config: TrainConfig
    estimator: Any
    donor_site_groups: list[str]
    label_interval: tuple[pd.Timestamp, pd.Timestamp]
    train_seconds: float
    hardware: str | None = None
    excluded_site_groups: list[str] = field(default_factory=list)
    minimum_history_hours: int | None = None
    fallback: str | None = "reference"
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MethodBackend:
    """Ce qu'une méthode (hgb, mlp...) fournit pour apprendre, être sauvegardée et rechargée.

    Tout le modèle tient dans un seul fichier (weights_file) : pour le MLP, la
    normalisation est rangée dans le réseau lui-même.
    """

    weights_file: str  # ex. "model.joblib", "weights.pt"
    save: Callable[[Any, Path], None]  # écrit l'estimateur dans ce chemin
    load: Callable[[Path], Any]  # relit l'estimateur depuis ce chemin
    # fit(config, counts, context, origins) -> estimateur ; origins fixées par train.fit
    fit: Callable[[TrainConfig, pd.DataFrame, pd.DataFrame | None, pd.DataFrame], Any] | None = None
    minimum_history_hours: int | None = None  # historique nécessaire pour prévoir un cas


_BACKENDS: dict[str, MethodBackend] = {}


def register_backend(method: str, backend: MethodBackend) -> None:
    """Déclarer une méthode ; tabular.py et neural.py l'appellent à l'import."""
    if method in _BACKENDS and _BACKENDS[method] is not backend:
        raise ValueError(f"méthode {method!r} déjà déclarée")
    _BACKENDS[method] = backend


def get_backend(method: str) -> MethodBackend:
    """Retrouver une méthode déclarée, ou expliquer laquelle manque."""
    if method not in _BACKENDS:
        raise KeyError(f"méthode {method!r} inconnue ; déclarées : {sorted(_BACKENDS)}")
    return _BACKENDS[method]


@dataclass
class TrainingData:
    """Les trois tables d'E1 dont fit a besoin, lues depuis un même instantané."""

    snapshot_id: str
    counts: pd.DataFrame  # une ligne par compteur et par heure
    context: pd.DataFrame  # calendrier, grèves, météo (format long d'E1)
    inventory: pd.DataFrame  # rôle et groupe de site de chaque compteur
    context_version: str | None = None


def load_training_data(
    snapshot_id: str | None = None,
    *,
    root: Path | None = None,
    values: str = "measured",
) -> TrainingData:
    """Lire counts.csv, context.csv et inventory_quality.csv d'un instantané E1.

    values="measured" (défaut, D-11) : la colonne count ne garde que les vraies mesures
    publiées (count_raw si is_observed) ; les valeurs remplies par E1 (J-7, année d'avant)
    sont mises de côté. Même règle que predict.counts_history_loader, pour que
    l'apprentissage et la prévision voient les mêmes entrées. values="e1_filled" garde
    la valeur livrée par E1.
    """
    if values not in VALUE_POLICIES:
        raise ValueError(f"values doit valoir {VALUE_POLICIES}, reçu {values!r}")
    snapshot_id = snapshot_id or load_config().get("snapshot_id")
    if not snapshot_id:
        raise ValueError("snapshot_id absent : le passer en argument ou le fixer dans la config")
    folder = Path(root) if root else data_path("processed") / snapshot_id
    for name in ("counts.csv", "context.csv", "inventory_quality.csv"):
        if not (folder / name).exists():
            raise FileNotFoundError(f"{name} introuvable dans {folder}")

    counts = pd.read_csv(
        folder / "counts.csv",
        usecols=COUNT_COLUMNS,
        dtype={"counter_id": "category", "count_raw": "float32", "count": "float32"},
    )
    for column in ("timestamp", "interval_end"):
        counts[column] = pd.to_datetime(counts[column], utc=True, format="ISO8601")
    for column in ("is_observed", "is_scoreable"):
        counts[column] = counts[column].astype(str).str.strip().str.lower().eq("true")
    counts = counts.rename(columns={"count": "count_e1"})
    if values == "measured":
        counts["count"] = counts["count_raw"].where(counts["is_observed"])
    else:
        counts["count"] = counts["count_e1"]

    # Texte partout : la colonne value mêle nombres et booléens ; features la convertit.
    context = pd.read_csv(folder / "context.csv", dtype=str)
    inventory = pd.read_csv(folder / "inventory_quality.csv", dtype=str)
    version = None
    if "context_version" in context.columns and context["context_version"].notna().any():
        version = str(context["context_version"].dropna().iloc[0])
    return TrainingData(snapshot_id, counts, context, inventory, version)


def exclude_reserved_sites(
    counts: pd.DataFrame, inventory: pd.DataFrame, include_robustness: bool = True
) -> pd.DataFrame:
    """Garder seulement les compteurs d'apprentissage (S_train) de counts.

    Délègue à features.training_counters, qui retire toutes les directions des groupes
    réservés à E3 et refuse un groupe à la fois S_train et réservé.
    """
    keep = set(training_counters(inventory, include_robustness))
    return counts.loc[counts["counter_id"].astype(str).isin(keep)]


def fit(
    config: TrainConfig,
    counts: pd.DataFrame,
    context: pd.DataFrame | None,
    inventory: pd.DataFrame,
    *,
    include_robustness: bool = True,
    publication_lag_hours: int | None = None,
) -> TrainedModel:
    """Entraîner la méthode de config.method sur les sites connus.

    Partie commune, faite une seule fois ici pour que toutes les méthodes apprennent
    sur les mêmes compteurs et les mêmes origines :
    1. compteurs S_train (sites E3 exclus) ;
    2. origines d'apprentissage entre config.train_start et config.fit_cutoff ;
    3. groupes de sites donneurs et exclus, gardés comme preuve dans metadata.json ;
    4. apprentissage par la méthode (backend.fit), chronométré.

    publication_lag_hours doit valoir la latence de la configuration (ou None) : les
    méthodes construisent leurs entrées avec cette latence-là (MOD-008).
    """
    backend = get_backend(config.method)
    if backend.fit is None:
        raise NotImplementedError(f"la méthode {config.method!r} ne sait pas encore apprendre")
    model_run_id = make_model_run_id(config)  # vérifie aussi le fuseau de fit_cutoff
    _check_publication_lag(publication_lag_hours)

    counters = training_counters(inventory, include_robustness)
    train_counts = exclude_reserved_sites(counts, inventory, include_robustness)
    origins = training_origins(
        train_counts,
        counters,
        config.fit_cutoff,
        start=config.train_start,
        publication_lag_hours=publication_lag_hours,
    )
    if origins.empty:
        raise ValueError("aucune origine d'apprentissage : vérifier train_start et fit_cutoff")

    donor, excluded = _site_groups(inventory, counters)
    started = time.perf_counter()
    estimator = backend.fit(config, train_counts, context, origins)
    train_seconds = time.perf_counter() - started

    first_origin = origins["origin"].min()
    last_target_end = origins["origin"].max() + pd.Timedelta(hours=HORIZON_HOURS)
    return TrainedModel(
        model_run_id=model_run_id,
        config=config,
        estimator=estimator,
        donor_site_groups=donor,
        label_interval=(first_origin, last_target_end),
        train_seconds=train_seconds,
        hardware=_hardware(),
        excluded_site_groups=excluded,
        minimum_history_hours=backend.minimum_history_hours,
    )


def _check_publication_lag(publication_lag_hours: int | None) -> None:
    """Refuser une latence différente de celle de la configuration (MOD-008).

    backend.fit ne reçoit pas la latence : build_training_frame (HGB) et build_windows
    (MLP) prennent celle de la configuration. Une autre valeur ici ne déplacerait que les
    origines, pas les fenêtres : une entrée pas encore publiée pourrait alors être lue.
    Pour une sensibilité à 48 h, changer protocol.publication_lag_hours dans la configuration.
    """
    if publication_lag_hours is None:
        return
    expected = _default_lag()
    if int(publication_lag_hours) != expected:
        raise ValueError(
            f"publication_lag_hours={publication_lag_hours} différent de la latence de la "
            f"configuration ({expected} h), seule transmise aux méthodes : modifier "
            "protocol.publication_lag_hours dans config/project.yaml"
        )


def _site_groups(inventory: pd.DataFrame, counters: list[str]) -> tuple[list[str], list[str]]:
    """Groupes de sites des compteurs appris, et groupes réservés à E3 (exclus)."""
    inv = inventory
    if "period_role" in inv.columns:
        inv = inv.loc[inv["period_role"] == "selection"]
    groups = inv["site_group_id"].astype(str)
    donor = sorted(set(groups[inv["counter_id"].astype(str).isin(counters)]))
    excluded = sorted(set(groups[inv["site_role"].isin(["S_dev_new", "S_test_new"])]))
    return donor, excluded


def _hardware() -> str:
    """Description courte de la machine, pour comparer les coûts d'apprentissage."""
    cpu = platform.processor() or platform.machine()
    return f"{cpu}, {os.cpu_count()} threads, {platform.system()}"


def compare_variants(configs: list[TrainConfig], validation_cases: pd.DataFrame) -> pd.DataFrame:
    """Comparer des variantes sur la validation (jamais sur le test final).

    Ex. même modèle avec/sans contexte ; local vs partagé ; autre fonction de perte.
    Les scores officiels restent calculés par E4.
    """
    raise NotImplementedError("E2 avec E4 : ablation d'information")


def save_model(model: TrainedModel, root: Path | None = None) -> Path:
    """Écrire artifacts/models/<model_run_id>/ : le fichier de poids et metadata.json.

    1. Refuse d'écraser un modèle existant.
    2. Écrit tout dans un dossier temporaire, puis le renomme : un plantage ne laisse
       jamais de modèle à moitié écrit sous le vrai nom.
    3. Enregistre le SHA-256 des poids, vérifié ensuite par load_model.
    """
    backend = get_backend(model.config.method)
    root = Path(root) if root else data_path("models")
    final_dir = root / model.model_run_id
    if final_dir.exists():
        raise FileExistsError(f"le modèle {model.model_run_id} existe déjà : {final_dir}")

    tmp_dir = root / f".tmp-{model.model_run_id}-{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True)
    try:
        weights_path = tmp_dir / backend.weights_file
        backend.save(model.estimator, weights_path)
        metadata = _metadata(model, backend.weights_file, _sha256_file(weights_path))
        (tmp_dir / METADATA_FILE).write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        tmp_dir.rename(final_dir)
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return final_dir


def _metadata(model: TrainedModel, weights_file: str, weights_sha256: str) -> dict[str, Any]:
    """metadata.json au format de doc/templates/model_metadata.example.json."""
    config = model.config
    start, end = model.label_interval
    return {
        "schema_version": METADATA_SCHEMA_VERSION,
        "model_run_id": model.model_run_id,
        "model_name": config.method,
        "variant": "ctx" if config.use_context else "noctx",
        "fit_cutoff": _iso_utc(config.fit_cutoff),
        "train_start": _iso_utc_or_none(config.train_start),
        "training_target_start": _iso_utc(start),
        "training_target_end": _iso_utc(end),
        "training_site_groups": sorted(model.donor_site_groups),
        "excluded_site_groups": sorted(model.excluded_site_groups),
        "snapshot_id": config.snapshot_id,
        "context_version": config.context_version,
        "protocol_id": config.protocol_id,
        "feature_version": config.feature_version,
        "parameters": config.hyperparameters,
        "seed": config.seed,
        "config_fingerprint": config_fingerprint(config),
        "code_version": _code_version(),
        "weights_path": weights_file,
        "weights_sha256": weights_sha256,
        "training_seconds": round(model.train_seconds, 3),
        "hardware": model.hardware or platform.processor() or platform.machine(),
        "minimum_history_hours": model.minimum_history_hours,
        "supported_scenarios": ["known_site"],
        "fallback": model.fallback,
        "pretraining_provenance": None,
        "limitations": model.limitations,
    }


def _sha256_file(path: Path) -> str:
    """SHA-256 d'un fichier, lu par morceaux pour ne pas tout charger en mémoire."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_version() -> str | None:
    """Commit git du code qui a entraîné le modèle (suffixe -dirty si modifs non commitées)."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{commit}-dirty" if dirty else commit


def _iso_utc(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).tz_convert("UTC").isoformat()


def _iso_utc_or_none(value: pd.Timestamp | None) -> str | None:
    return None if value is None else _iso_utc(value)


def load_model(
    model_run_id: str,
    root: Path | None = None,
    *,
    expected_feature_version: str | None = None,
) -> TrainedModel:
    """Recharger un modèle sauvegardé par save_model, après quatre contrôles.

    1. Le dossier existe et sa fiche porte bien ce model_run_id.
    2. Les poids n'ont pas changé depuis la sauvegarde (SHA-256).
    3. La fiche n'a pas été retouchée (empreinte de la config recalculée).
    4. Si demandé, les variables du modèle sont celles du code actuel (feature_version).
    """
    root = Path(root) if root else data_path("models")
    model_dir = root / model_run_id
    metadata_path = model_dir / METADATA_FILE
    if not metadata_path.exists():
        raise FileNotFoundError(f"modèle {model_run_id} introuvable : {metadata_path}")
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))

    # 1. La fiche correspond au dossier.
    if meta.get("model_run_id") != model_run_id:
        raise ValueError(
            f"la fiche de {model_dir} annonce {meta.get('model_run_id')!r}, pas {model_run_id!r}"
        )

    # 2. Les poids sont intacts. weights_path doit être un simple nom de fichier du dossier.
    weights_name = meta["weights_path"]
    if Path(weights_name).name != weights_name:
        raise ValueError(f"weights_path doit être un nom de fichier, reçu {weights_name!r}")
    weights_path = model_dir / weights_name
    actual_sha = _sha256_file(weights_path)
    if actual_sha != meta["weights_sha256"]:
        raise ValueError(
            f"poids de {model_run_id} modifiés depuis la sauvegarde : "
            f"SHA-256 {actual_sha[:12]}… au lieu de {meta['weights_sha256'][:12]}…"
        )

    # 3. Les réglages relus redonnent la même empreinte.
    config = TrainConfig(
        method=meta["model_name"],
        fit_cutoff=pd.Timestamp(meta["fit_cutoff"]),
        train_start=None if meta.get("train_start") is None else pd.Timestamp(meta["train_start"]),
        use_context=meta["variant"] == "ctx",
        hyperparameters=meta["parameters"],
        seed=meta["seed"],
        protocol_id=meta["protocol_id"],
        snapshot_id=meta["snapshot_id"],
        context_version=meta["context_version"],
        feature_version=meta["feature_version"],
    )
    if config_fingerprint(config) != meta["config_fingerprint"]:
        raise ValueError(f"fiche de {model_run_id} incohérente : les réglages ont été modifiés")

    # 4. Les variables attendues par le modèle sont celles du code.
    if expected_feature_version is not None and config.feature_version != expected_feature_version:
        raise ValueError(
            f"{model_run_id} a appris sur les variables {config.feature_version!r}, "
            f"le code fournit {expected_feature_version!r} : réentraîner le modèle"
        )

    estimator = get_backend(config.method).load(weights_path)
    return TrainedModel(
        model_run_id=model_run_id,
        config=config,
        estimator=estimator,
        donor_site_groups=list(meta["training_site_groups"]),
        label_interval=(
            pd.Timestamp(meta["training_target_start"]),
            pd.Timestamp(meta["training_target_end"]),
        ),
        train_seconds=float(meta["training_seconds"]),
        hardware=meta.get("hardware"),
        excluded_site_groups=list(meta.get("excluded_site_groups", [])),
        minimum_history_hours=meta.get("minimum_history_hours"),
        fallback=meta.get("fallback"),
        limitations=list(meta.get("limitations", [])),
    )

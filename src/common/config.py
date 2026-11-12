"""Configuration commune, chargée de manière portable (E1–E5).

Les chemins sont résolus depuis la racine du dépôt, jamais depuis un dossier
personnel. `config/project.yaml` est utilisé s'il existe, sinon le gabarit
`config/project.example.yaml`.

Reste à faire (autres équipes) : validation du protocole, budgets et groupes de
sites ; ce module ne présume aucune approbation.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "config" / "project.yaml"
CONFIG_EXAMPLE = ROOT / "config" / "project.example.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Lit project.yaml, ou le gabarit à défaut."""
    path = CONFIG_FILE if CONFIG_FILE.exists() else CONFIG_EXAMPLE
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def data_path(key: str) -> Path:
    """Chemin absolu d'une entrée de `paths` (history, processed, manifests...)."""
    paths = load_config().get("paths") or {}
    if key not in paths:
        raise KeyError(f"Chemin '{key}' absent de la section paths de la configuration")
    return ROOT / paths[key]


def relative_to_root(path: Path) -> str:
    """Chemin relatif à la racine, en notation POSIX, pour les manifestes."""
    return Path(path).resolve().relative_to(ROOT).as_posix()

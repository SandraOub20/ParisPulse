"""Extraction des sources et provenance - E1.

Télécharge un compteur du flux courant Open Data Paris
(`comptage-velo-donnees-compteurs`), dépose le CSV brut intact dans
`data/history/<snapshot_id>/` et décrit l'extraction dans
`data/manifests/<snapshot_id>.json`. Enchaîne ensuite la préparation
(`src/data/prepare.py`), sauf `--sans-preparation`.

Identifiant d'instantané
------------------------
`flux-AAAAMMJJ` : préfixe de la source (`flux` = jeu courant 13 mois glissants)
puis date UTC de l'extraction. Plusieurs compteurs extraits le même jour
partagent l'instantané ; chaque source garde son propre `retrieved_at`.
Les archives annuelles prendront un préfixe distinct (`archive-...`).
Un fichier déjà présent dans l'instantané n'est jamais retéléchargé sans
`--force`, pour que l'instantané reste stable.

Usage, depuis la racine du dépôt :
  uv run python -m src.data.acquire --lister
  uv run python -m src.data.acquire --compteur 100057445-104057445
  uv run python -m src.data.acquire --compteur ID --fichier export_manuel.csv

Logique reprise de l'ancien script de l'équipe (parispulse-equipe01,
commit 5488590, src/phase0.py).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

import httpx
import pandas as pd

from src.common.config import data_path, relative_to_root

API_BASE = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets"
DATASET_FLUX = "comptage-velo-donnees-compteurs"
DATASET_PAGE = f"https://opendata.paris.fr/explore/dataset/{DATASET_FLUX}/information/"
LICENSE = "Open Database License (ODbL)"
LICENSE_URL = "https://opendatacommons.org/licenses/odbl/"
ATTRIBUTION = (
    "Ville de Paris - Direction de la Voirie et des Déplacements, "
    "jeu « Comptage vélo - Données compteurs », opendata.paris.fr"
)
SCHEMA_VERSION = 2
SNAPSHOT_PREFIX = "flux"
RAW_SEPARATOR = ";"
RAW_ENCODING = "utf-8-sig"  # l'export Open Data Paris commence par un BOM
HTTP_TIMEOUT = httpx.Timeout(30.0, read=300.0)


# ----------------------------------------------------------------- identifiants
def snapshot_id_for(when: dt.datetime, prefix: str = SNAPSHOT_PREFIX) -> str:
    """`flux-AAAAMMJJ` à partir d'une date UTC d'extraction."""
    return f"{prefix}-{when.astimezone(dt.timezone.utc):%Y%m%d}"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def raw_filename(counter_id: str) -> str:
    return f"{DATASET_FLUX}__{safe_name(counter_id)}.csv"


def source_file_id(raw_path: Path) -> str:
    """Identifiant de fichier source repris dans counts.csv."""
    return raw_path.stem


def export_url(counter_id: str) -> tuple[str, dict]:
    """URL exacte de l'export CSV filtré, et ses paramètres."""
    params = {
        "where": f'id_compteur="{counter_id}"',
        "delimiter": RAW_SEPARATOR,
        "timezone": "UTC",
    }
    return f"{API_BASE}/{DATASET_FLUX}/exports/csv?{urllib.parse.urlencode(params)}", params


# ----------------------------------------------------------------- fichiers bruts
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_raw(path: Path) -> pd.DataFrame:
    """Lit un brut en texte, sans conversion ni valeur absente implicite."""
    return pd.read_csv(
        path, sep=RAW_SEPARATOR, dtype=str, keep_default_na=False, encoding=RAW_ENCODING
    )


def raw_stats(path: Path) -> dict:
    """Effectif et bornes temporelles (UTC) d'un brut du flux."""
    raw = read_raw(path)
    stats = {"n_rows": int(len(raw)), "first_timestamp": None, "last_timestamp": None}
    if "date" in raw.columns and len(raw):
        ts = pd.to_datetime(raw["date"], utc=True, format="ISO8601", errors="coerce")
        if ts.notna().any():
            stats["first_timestamp"] = ts.min().isoformat()
            stats["last_timestamp"] = ts.max().isoformat()
    return stats


def download(url: str, dest: Path) -> None:
    """Écrit les octets reçus tels quels (fichier temporaire puis renommage)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, timeout=HTTP_TIMEOUT, follow_redirects=True) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    tmp.replace(dest)


def fetch_dataset_meta() -> dict:
    """Métadonnées du jeu (date de mise à jour, licence) ; vide si indisponible."""
    try:
        resp = httpx.get(f"{API_BASE}/{DATASET_FLUX}", timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        meta = resp.json().get("metas", {}).get("default", {})
    except (httpx.HTTPError, ValueError):
        return {}
    return {
        "dataset_data_processed": meta.get("data_processed"),
        "dataset_modified": meta.get("modified"),
        "dataset_timezone": meta.get("timezone"),
        "dataset_license": meta.get("license"),
        "dataset_publisher": meta.get("publisher"),
        "dataset_records_count": meta.get("records_count"),
    }


# ----------------------------------------------------------------- manifeste
def manifest_path(snapshot_id: str) -> Path:
    return data_path("manifests") / f"{snapshot_id}.json"


def load_manifest(snapshot_id: str) -> dict:
    path = manifest_path(snapshot_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "retrieved_at": None,
        "sources": [],
        "files": [],
        "source_time_semantics": None,
        "normalization_version": None,
        "duplicate_resolution": None,
        "known_limitations": [],
    }


def write_manifest(manifest: dict) -> Path:
    path = manifest_path(manifest["snapshot_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def upsert(items: list[dict], entry: dict, key: str) -> None:
    """Remplace l'élément de même clé, sinon l'ajoute."""
    for i, item in enumerate(items):
        if item.get(key) == entry.get(key):
            items[i] = entry
            return
    items.append(entry)


def file_entry(path: Path, role: str, **extra) -> dict:
    entry = {"path": relative_to_root(path), "role": role, "sha256": sha256_file(path)}
    entry.update(extra)
    return entry


# ----------------------------------------------------------------- extraction
def acquire_counter(
    counter_id: str,
    snapshot_id: str | None = None,
    fichier: Path | None = None,
    force: bool = False,
) -> tuple[str, Path]:
    """Dépose le brut d'un compteur et met à jour le manifeste."""
    now = dt.datetime.now(dt.timezone.utc)
    snapshot_id = snapshot_id or snapshot_id_for(now)
    dest = data_path("history") / snapshot_id / raw_filename(counter_id)
    url, params = export_url(counter_id)

    manifest = load_manifest(snapshot_id)
    if dest.exists() and not force:
        print(f"Brut déjà présent, réutilisé sans téléchargement : {relative_to_root(dest)}")
        return snapshot_id, dest

    if fichier:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fichier, dest)
        source = {
            "source_id": source_file_id(dest),
            "url": None,
            "manual_file": Path(fichier).name,
            "dataset_page": DATASET_PAGE,
            "filters": {"id_compteur": counter_id, "note": "export manuel, filtre à vérifier"},
        }
    else:
        print(f"Téléchargement : {url}")
        download(url, dest)
        source = {
            "source_id": source_file_id(dest),
            "url": url,
            "dataset_id": DATASET_FLUX,
            "dataset_page": DATASET_PAGE,
            "filters": params,
            **fetch_dataset_meta(),
        }
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    source.update(
        {
            "retrieved_at": retrieved_at,
            "license": LICENSE,
            "license_url": LICENSE_URL,
            "attribution": ATTRIBUTION,
        }
    )
    upsert(manifest["sources"], source, "source_id")
    upsert(manifest["files"], file_entry(dest, "raw", **raw_stats(dest)), "path")
    manifest["retrieved_at"] = max(s["retrieved_at"] for s in manifest["sources"])
    write_manifest(manifest)
    print(
        f"Brut : {relative_to_root(dest)}\nManifeste : {relative_to_root(manifest_path(snapshot_id))}"
    )
    return snapshot_id, dest


def list_counters(n: int = 30) -> pd.DataFrame:
    """Classement des compteurs du flux par volume total (aide au choix)."""
    params = {
        "select": "id_compteur, nom_compteur, sum(sum_counts) as total, count(*) as n_heures",
        "group_by": "id_compteur, nom_compteur",
        "order_by": "total desc",
        "limit": n,
    }
    resp = httpx.get(f"{API_BASE}/{DATASET_FLUX}/records", params=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json()["results"])
    df["moy_horaire"] = (df["total"] / df["n_heures"]).round(1)
    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--compteur", help="id_compteur à extraire")
    ap.add_argument("--lister", action="store_true", help="classer les compteurs par volume")
    ap.add_argument("--snapshot", help="identifiant d'instantané (défaut : flux-<date UTC>)")
    ap.add_argument("--fichier", type=Path, help="CSV exporté à la main si l'API ne répond pas")
    ap.add_argument("--force", action="store_true", help="retélécharger un brut déjà présent")
    ap.add_argument("--sans-preparation", action="store_true", help="ne pas lancer prepare")
    args = ap.parse_args(argv)

    if args.lister:
        print(list_counters().to_string(index=False))
        print("\nChoisir un compteur à fort volume et n_heures proche du maximum.")
        return 0
    if not args.compteur:
        ap.error("--compteur est obligatoire (ou --lister)")

    snapshot_id, _ = acquire_counter(args.compteur, args.snapshot, args.fichier, args.force)
    if not args.sans_preparation:
        from src.data.prepare import prepare_counter

        prepare_counter(snapshot_id, args.compteur)
    return 0


if __name__ == "__main__":
    sys.exit(main())

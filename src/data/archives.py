"""Archives annuelles des comptages vélo - E1 (historique, étape T2-T3).

Télécharge, une seule fois, les fichiers annuels du jeu historique Open Data Paris
(`comptage-velo-historique-donnees-compteurs`, pièces jointes « par compteur et par
heure ») dans `data/history/<snapshot_id>/archives/`, les décrit dans
`data/manifests/<snapshot_id>.json`, puis fait l'inventaire de chaque année : format,
période, compteurs, dates sans fuseau, doublons, et recouvrement avec le flux.

Historique en cycles annuels complets : avec `--cycles N`, l'historique retenu commence
N années avant le début de la grille du flux (16/10/2025 pour `flux-20261115`, donc
16/10/2023 pour 2 cycles), au lieu du 1er janvier. Les fichiers annuels sont téléchargés
entiers et restent intacts ; seul l'inventaire indique ce qui tombe dans la fenêtre.

Assemblage (`--assembler hist-AAAAMMJJ`, décisions E1 du 17/11/2026) : un instantané
`hist-…` réunit l'historique des archives (N cycles avant le flux) et le flux, sur une
seule grille UTC, puis `prepare.py` le prépare comme le flux.

- R1 : depuis janvier 2024, l'archive publie certains sens en deux canaux ; le flux en
  publie la somme sous l'ancien identifiant. Chaque compteur du flux = son canal + son
  canal jumeau, jumeau trouvé sur la période commune archive / flux (au moins 99 %
  d'heures identiques). Avant l'apparition du jumeau, le canal seul.
- R2 : les lignes sans identifiant de compteur (une par heure dans les archives 2024
  et 2025 ; agrégat de nature inconnue, ce n'est pas la somme des compteurs : vérifié
  le 18/11/2026, fiche E1-historique, A4) sont écartées et comptées.
- R3 (option A) : seuls les compteurs du flux sont gardés ; les compteurs présents
  seulement dans l'archive sont listés dans le manifeste, hors grille.
- Les archives ne servent qu'avant le début du flux ; le flux fait foi ensuite.

Le brut assemblé est écrit dans `data/history/hist-…/`, avec la provenance de chaque
fichier source ; les archives et le brut du flux restent intacts.

Identifiant d'instantané : `archive-AAAAMMJJ` (date UTC du téléchargement). Un fichier
déjà présent n'est jamais retéléchargé sans `--force`.

Usage, depuis la racine du dépôt :
  uv run python -m src.data.archives --lister
  uv run python -m src.data.archives --snapshot archive-20261117 --cycles 2 \
      --comparer flux-20261115
  uv run python -m src.data.archives --assembler hist-20261117 \
      --snapshot archive-20261117 --comparer flux-20261115 --cycles 2
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import httpx
import pandas as pd

from src.common.config import data_path, relative_to_root
from src.data.acquire import (
    API_BASE,
    ATTRIBUTION,
    HTTP_TIMEOUT,
    LICENSE,
    LICENSE_URL,
    download,
    file_entry,
    load_manifest,
    safe_name,
    snapshot_id_for,
    upsert,
    write_manifest,
)
from src.data.prepare import COLUMN_MAP, parse_timestamps

DATASET_HIST = "comptage-velo-historique-donnees-compteurs"
DATASET_HIST_PAGE = f"https://opendata.paris.fr/explore/dataset/{DATASET_HIST}/information/"
SNAPSHOT_PREFIX = "archive"
HIST_PREFIX = "hist"
HIST_RAW_FILENAME = "historique_assemble.csv.gz"
ARCHIVES_VERSION = "e1-archives/0.3.0"
TWIN_MIN_IDENTICAL = 0.99
RAW_COLUMNS = [
    "id_compteur",
    "nom_compteur",
    "id",
    "name",
    "sum_counts",
    "date",
    "installation_date",
    "coordinates",
]
ASSEMBLY_RULES = {
    "R1_canaux_jumeaux": (
        "Depuis janvier 2024, l'archive publie certains sens en deux canaux ; le flux en "
        "publie la somme. Compteur = canal + jumeau (jumeau trouvé sur la période commune "
        "archive / flux, au moins 99 % d'heures identiques) ; avant l'apparition du "
        "jumeau, le canal seul ; après, une heure où un des deux manque reste manquante."
    ),
    "R1bis_renommages": (
        "Si l'archive publie un compteur du flux sous un autre identifiant (même site, "
        "au moins 99 % d'heures identiques au flux), ses heures manquantes sont prises "
        "sous cet autre identifiant."
    ),
    "R2_sans_identifiant": "Lignes de l'archive sans identifiant de compteur écartées.",
    "R3_compteurs_du_flux": (
        "Seuls les compteurs du flux sont gardés ; ceux présents seulement dans les "
        "archives sont listés (excluded_archive_only), hors grille."
    ),
    "priorite": "Archives avant le début de la grille du flux ; le flux ensuite.",
}


# ----------------------------------------------------------------- pièces jointes
def list_attachments() -> list[dict]:
    """Pièces jointes du jeu historique : [{title, href}]."""
    resp = httpx.get(f"{API_BASE}/{DATASET_HIST}/attachments", timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    items = body.get("attachments", body.get("results", []))
    out = []
    for a in items:
        title = (a.get("metas") or {}).get("title") or a.get("title") or a.get("id") or ""
        out.append({"title": str(title), "href": a.get("href") or a.get("url") or ""})
    return out


def pick_year(attachments: list[dict], year: int) -> dict:
    """Le fichier « par compteur » (pas « par site ») d'une année."""
    found = [
        a
        for a in attachments
        if str(year) in a["title"]
        and re.search(r"compteur", a["title"], re.I)
        and not re.search(r"site", a["title"], re.I)
    ]
    if len(found) != 1:
        titles = [a["title"] for a in attachments]
        raise ValueError(
            f"{len(found)} fichier(s) « par compteur » pour {year} (1 attendu). "
            f"Pièces jointes : {titles}"
        )
    return found[0]


# ----------------------------------------------------------------- lecture
def decode_bytes(raw: bytes) -> tuple[bytes, str]:
    """Décompresse zip ou gzip si besoin. Retourne (octets CSV, conteneur)."""
    if raw[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(raw))
        names = [n for n in z.namelist() if not n.endswith("/")]
        if len(names) != 1:
            raise ValueError(f"Le zip contient {len(names)} fichiers : {names}")
        return z.read(names[0]), "zip"
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw), "gzip"
    return raw, "csv"


def sniff_format(data: bytes) -> tuple[str, str]:
    """(encodage, séparateur) : UTF-8 sinon latin-1 ; `;` ou `,` selon l'en-tête."""
    try:
        data.decode("utf-8")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        encoding = "latin-1"
    header = data.split(b"\n", 1)[0]
    sep = ";" if header.count(b";") > header.count(b",") else ","
    return encoding, sep


def read_archive(path: Path | str) -> tuple[pd.DataFrame, dict]:
    """Lit une archive en texte et renomme ses colonnes comme le flux.

    Retourne (table, format) ; aucune valeur n'est convertie ni modifiée.
    """
    data, container = decode_bytes(Path(path).read_bytes())
    encoding, sep = sniff_format(data)
    df = pd.read_csv(io.BytesIO(data), sep=sep, dtype=str, keep_default_na=False, encoding=encoding)
    original = [str(c) for c in df.columns]
    df = df.rename(columns=lambda c: COLUMN_MAP.get(str(c).strip().lstrip("﻿"), c))
    fmt = {
        "container": container,
        "encoding": encoding,
        "separator": sep,
        "columns": original,
        "unmapped_columns": [c for c in df.columns if c not in COLUMN_MAP.values()],
    }
    return df, fmt


def parse_counts(values: pd.Series) -> pd.Series:
    """Comptage en nombre ; NaN si illisible ou vide.

    Accepte la virgule décimale et les séparateurs de milliers (espace, espace
    insécable `\xa0` ou fine `\u202f`, présents dans l'archive 2025 : « 1 007 »).
    """
    text = values.astype(str).str.strip().str.replace(r"[\s\u00a0\u202f]", "", regex=True)
    return pd.to_numeric(text.str.replace(",", "."), errors="coerce")


# ----------------------------------------------------------------- inventaire
def archive_report(df: pd.DataFrame) -> dict:
    """Inventaire d'une archive lue par `read_archive`."""
    missing = {"counter_id", "count", "date_source"} - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes introuvables : {sorted(missing)} ; lues : {list(df.columns)}")
    ts, _, alerts = parse_timestamps(df["date_source"])
    n = parse_counts(df["count"])
    key = pd.DataFrame({"id": df["counter_id"].str.strip(), "ts": ts, "n": n})
    ok = key["ts"].notna()
    dup = key[ok].duplicated(["id", "ts"], keep=False)
    groups = key[ok][dup].groupby(["id", "ts"])["n"].nunique(dropna=False)
    s = df["date_source"].astype(str).str.strip()
    has_offset = s.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
    return {
        "n_rows": int(len(df)),
        "n_counters": int(key["id"].nunique()),
        "first_timestamp": ts.min().isoformat() if ok.any() else None,
        "last_timestamp": ts.max().isoformat() if ok.any() else None,
        "date_example": s.iloc[0] if len(s) else None,
        "n_dates_without_offset": int((~has_offset & s.ne("")).sum()),
        "n_unreadable_dates": int((~ok & s.ne("")).sum()),
        "n_empty_counts": int(df["count"].astype(str).str.strip().eq("").sum()),
        "n_invalid_counts": int((n.isna() & df["count"].astype(str).str.strip().ne("")).sum()),
        "n_negative_counts": int((n < 0).sum()),
        "n_duplicate_keys": int(len(groups)),
        "n_duplicate_same_value": int((groups == 1).sum()),
        "n_duplicate_conflicts": int((groups > 1).sum()),
        "alerts": alerts,
    }


def compare_with_flux(arc: pd.DataFrame, flux_counts: pd.DataFrame) -> pd.DataFrame:
    """Par compteur commun, sur les heures UTC communes : part de valeurs identiques.

    `flux_counts` : counts.csv préparé (counter_id, timestamp, count).
    """
    ts, _, _ = parse_timestamps(arc["date_source"])
    a = pd.DataFrame({"counter_id": arc["counter_id"].str.strip(), "ts": ts})
    a["n_archive"] = parse_counts(arc["count"])
    a = a.dropna(subset=["ts"]).drop_duplicates(["counter_id", "ts"])
    f = flux_counts[["counter_id", "timestamp", "count"]].copy()
    f["ts"] = pd.to_datetime(f["timestamp"], utc=True, format="ISO8601")
    f["n_flux"] = pd.to_numeric(f["count"], errors="coerce")
    m = a.merge(f[["counter_id", "ts", "n_flux"]], on=["counter_id", "ts"])
    m = m.dropna(subset=["n_archive", "n_flux"])
    if m.empty:
        return pd.DataFrame(
            columns=["counter_id", "common_hours", "identical_share", "median_ratio"]
        )
    m["same"] = m["n_archive"] == m["n_flux"]
    m["ratio"] = m["n_archive"] / m["n_flux"].where(m["n_flux"] > 0)
    out = m.groupby("counter_id").agg(
        common_hours=("same", "size"),
        identical_share=("same", "mean"),
        median_ratio=("ratio", "median"),
    )
    return out.round(3).reset_index().sort_values("identical_share")


# ----------------------------------------------------------------- cycles
def history_window(flux_start: pd.Timestamp, cycles: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Fenêtre de l'historique : `cycles` années pleines juste avant le début du flux.

    Retourne (début inclus, fin exclue), en UTC.
    """
    if cycles < 1:
        raise ValueError("Il faut au moins un cycle.")
    start = flux_start - pd.DateOffset(years=cycles)
    return start, flux_start


def years_for(start: pd.Timestamp, end: pd.Timestamp) -> list[int]:
    """Années civiles à télécharger pour couvrir [start, end[."""
    last = (end - pd.Timedelta(hours=1)).year
    return list(range(start.year, last + 1))


def flux_grid_start(flux_snapshot: str) -> pd.Timestamp:
    """Début de la grille commune du flux, lu dans son manifeste."""
    path = data_path("manifests") / f"{flux_snapshot}.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    first = (manifest.get("grid") or {}).get("first_timestamp")
    if not first:
        raise ValueError(f"Pas de grid.first_timestamp dans {relative_to_root(path)}")
    return pd.Timestamp(first).tz_convert("UTC")


# ----------------------------------------------------------------- extraction
def acquire_years(snapshot_id: str, years: list[int], force: bool = False) -> list[Path]:
    """Télécharge les archives demandées et les déclare au manifeste."""
    folder = data_path("history") / snapshot_id / "archives"
    attachments = list_attachments()
    manifest = load_manifest(snapshot_id)
    paths = []
    for year in years:
        att = pick_year(attachments, year)
        dest = folder / safe_name(att["title"])
        if dest.exists() and not force:
            print(f"{year} : déjà présent, non retéléchargé ({relative_to_root(dest)})")
        else:
            print(f"{year} : téléchargement de {att['title']}…")
            download(att["href"], dest)
            upsert(
                manifest["sources"],
                {
                    "source_id": f"archive_{year}",
                    "dataset": DATASET_HIST,
                    "dataset_page": DATASET_HIST_PAGE,
                    "attachment_title": att["title"],
                    "url": att["href"],
                    "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "license": LICENSE,
                    "license_url": LICENSE_URL,
                    "attribution": ATTRIBUTION,
                },
                "source_id",
            )
        upsert(manifest["files"], file_entry(dest, "archive", year=year), "path")
        paths.append(dest)
    write_manifest(manifest)
    return paths


def inventory(
    paths: list[Path],
    flux_snapshot: str | None = None,
    window: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> dict:
    """Inventaire de chaque archive, plus comparaison avec le flux si demandé."""
    flux = None
    if flux_snapshot:
        flux = pd.read_csv(
            data_path("processed") / flux_snapshot / "counts.csv",
            dtype=str,
            keep_default_na=False,
            usecols=["counter_id", "timestamp", "count"],
        )
    result = {"archives_version": ARCHIVES_VERSION, "files": {}}
    if window is not None:
        result["history_window"] = {"start": window[0].isoformat(), "end": window[1].isoformat()}
    for path in paths:
        df, fmt = read_archive(path)
        rep = archive_report(df)
        entry = {**fmt, **rep}
        if window is not None:
            ts, _, _ = parse_timestamps(df["date_source"])
            inside = (ts >= window[0]) & (ts < window[1])
            entry["n_rows_in_window"] = int(inside.sum())
            entry["n_counters_in_window"] = int(df.loc[inside, "counter_id"].nunique())
        if flux is not None:
            ids_a, ids_f = set(df["counter_id"].str.strip()), set(flux["counter_id"])
            cmp = compare_with_flux(df, flux)
            entry["counters_common_with_flux"] = len(ids_a & ids_f)
            entry["counters_only_in_archive"] = len(ids_a - ids_f)
            entry["counters_only_in_flux"] = len(ids_f - ids_a)
            entry["overlap_counters"] = int(len(cmp))
            entry["overlap_identical_ge_95pct"] = int((cmp["identical_share"] >= 0.95).sum())
            entry["overlap_different"] = cmp[cmp["identical_share"] < 0.95].to_dict("records")
        result["files"][relative_to_root(path)] = entry
    return result


def print_inventory(inv: dict) -> None:
    if "history_window" in inv:
        w = inv["history_window"]
        print(f"Fenêtre de l'historique (UTC) : {w['start']} -> {w['end']} (fin exclue)")
    for name, e in inv["files"].items():
        print(f"\n=== {name}")
        print(f"Format : {e['container']}, {e['encoding']}, séparateur « {e['separator']} »")
        print(f"Colonnes : {e['columns']}")
        if e["unmapped_columns"]:
            print(f"Colonnes non reconnues : {e['unmapped_columns']}")
        print(f"Lignes : {e['n_rows']} ; compteurs : {e['n_counters']}")
        print(f"Période UTC : {e['first_timestamp']} -> {e['last_timestamp']}")
        print(f"Exemple de date : {e['date_example']}")
        print(
            f"Dates sans fuseau : {e['n_dates_without_offset']} ; "
            f"illisibles : {e['n_unreadable_dates']}"
        )
        print(
            f"Comptages vides : {e['n_empty_counts']} ; invalides : {e['n_invalid_counts']} ; "
            f"négatifs : {e['n_negative_counts']}"
        )
        print(
            f"Doublons (compteur, heure) : {e['n_duplicate_keys']} "
            f"(mêmes valeurs : {e['n_duplicate_same_value']}, "
            f"conflits : {e['n_duplicate_conflicts']})"
        )
        if "n_rows_in_window" in e:
            print(
                f"Dans la fenêtre : {e['n_rows_in_window']} lignes, "
                f"{e['n_counters_in_window']} compteurs"
            )
        for a in e["alerts"]:
            print(f"Alerte : {a}")
        if "counters_common_with_flux" in e:
            print(
                f"Avec le flux : {e['counters_common_with_flux']} compteurs communs, "
                f"{e['counters_only_in_archive']} seulement dans l'archive, "
                f"{e['counters_only_in_flux']} seulement dans le flux"
            )
            print(
                f"Recouvrement : {e['overlap_counters']} compteurs comparés, "
                f"{e['overlap_identical_ge_95pct']} identiques à 95 % ou plus"
            )
            for r in e["overlap_different"]:
                print(
                    f"  différent : {r['counter_id']} ({r['common_hours']} h, "
                    f"identiques {r['identical_share']:.0%}, rapport médian {r['median_ratio']})"
                )


# ----------------------------------------------------------------- assemblage
def archive_long(paths: list[Path]) -> tuple[pd.DataFrame, dict]:
    """Toutes les lignes des archives : id, ts (UTC), n. Écarte les lignes sans id (R2).

    Retourne (table, compteurs) ; un doublon (id, heure) de valeurs différentes devient
    une valeur manquante.
    """
    parts, stats = [], {"n_rows_without_counter_id": 0, "n_conflicts": 0}
    for path in paths:
        df, _ = read_archive(path)
        ids = df["counter_id"].astype(str).str.strip()
        stats["n_rows_without_counter_id"] += int(ids.eq("").sum())
        df = df[ids.ne("")]
        ts, _, _ = parse_timestamps(df["date_source"])
        parts.append(
            pd.DataFrame(
                {
                    "id": ids[ids.ne("")].reset_index(drop=True),
                    "ts": ts.reset_index(drop=True),
                    "n": parse_counts(df["count"]).reset_index(drop=True),
                }
            )
        )
    out = pd.concat(parts, ignore_index=True).dropna(subset=["ts"])
    out = out.drop_duplicates(["id", "ts", "n"])
    dup = out.duplicated(["id", "ts"], keep=False)
    if dup.any():
        stats["n_conflicts"] = int(out[dup].groupby(["id", "ts"]).ngroups)
        out.loc[dup, "n"] = float("nan")
        out = out.drop_duplicates(["id", "ts"])
    return out.reset_index(drop=True), stats


def find_twins(
    arc: pd.DataFrame,
    flux_counts: pd.DataFrame,
    min_identical: float = TWIN_MIN_IDENTICAL,
) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    """Canal jumeau (R1) ou ancien nom (R1 bis) de chaque compteur du flux.

    Sur les heures communes archive / flux, pour chaque compteur du flux, on essaie :
    son canal seul ; son canal + un autre canal du même site (jumeau : l'archive coupe
    le sens en deux) ; un autre canal seul (renommage : l'archive publie le compteur
    sous un autre identifiant). Les autres canaux ne sont jamais des compteurs du flux.
    Retenu si au moins `min_identical` des heures sont identiques.

    `arc` : id, ts, n ; `flux_counts` : counter_id, ts, n (préparé).
    Retourne ({compteur: jumeau}, {compteur: autre identifiant}, détail par compteur).
    """
    flux_ids = set(flux_counts["counter_id"])
    common = arc["ts"].isin(set(flux_counts["ts"]))
    table = arc[common].pivot_table(index="ts", columns="id", values="n")
    twins, renames, detail = {}, {}, []
    for fid in sorted(flux_ids):
        f = flux_counts.loc[flux_counts["counter_id"] == fid].set_index("ts")["n"].dropna()
        site = fid.split("-")[0]
        candidates = [
            c for c in table.columns if c.startswith(site + "-") and c not in flux_ids
        ]
        trials = []
        if fid in table.columns:
            trials.append(("seul", None, [fid]))
            trials += [("jumeau", c, [fid, c]) for c in candidates]
        trials += [("renommage", c, [c]) for c in candidates]
        best = ("absent", None, -1.0, 0)
        for kind, other, cols in trials:
            s = table[cols].sum(axis=1, min_count=len(cols))
            idx = s.dropna().index.intersection(f.index)
            share = float((s.loc[idx] == f.loc[idx]).mean()) if len(idx) else 0.0
            if share > best[2]:
                best = (kind, other, share, len(idx))
        kind, other, share, n = best
        ok = share >= min_identical
        detail.append(
            {
                "counter_id": fid,
                "rule": kind if ok or kind == "absent" else f"{kind} (non retenu)",
                "other_id": other,
                "identical_share": round(max(share, 0.0), 4),
                "hours": n,
            }
        )
        if ok and kind == "jumeau":
            twins[fid] = other
        elif ok and kind == "renommage":
            renames[fid] = other
    used = pd.Series([*twins.values(), *renames.values()])
    if used.duplicated().any():
        raise ValueError(f"Un canal sert deux compteurs : {sorted(used[used.duplicated()])}")
    return twins, renames, detail


def counter_series(
    arc: pd.DataFrame,
    counter_id: str,
    twin: str | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    alias: str | None = None,
) -> pd.Series:
    """Série horaire d'un compteur dans [start, end[ ; heures inconnues absentes.

    R1 : avec `twin`, canal + jumeau depuis l'apparition du jumeau. R1 bis : avec
    `alias`, les heures où le compteur manque sont prises sous son autre identifiant.
    """
    window = (arc["ts"] >= start) & (arc["ts"] < end)
    main = arc[window & arc["id"].eq(counter_id)].set_index("ts")["n"].dropna()
    if alias is not None:
        other_name = arc[window & arc["id"].eq(alias)].set_index("ts")["n"].dropna()
        main = main.combine_first(other_name)
    if twin is None:
        return main.sort_index()
    other = arc[arc["id"].eq(twin)]
    if other.empty:
        return main.sort_index()
    twin_start = other["ts"].min()
    other = other[(other["ts"] >= start) & (other["ts"] < end)].set_index("ts")["n"]
    both = pd.concat([main.rename("a"), other.rename("b")], axis=1).astype(float)
    before = both.index < twin_start
    value = both["a"].copy()
    value[~before] = both["a"][~before] + both["b"][~before]
    return value.dropna().sort_index()


def _format_count(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def assemble_history(
    hist_snapshot: str, archive_snapshot: str, flux_snapshot: str, cycles: int = 2
) -> Path:
    """Écrit le brut assemblé de `hist_snapshot` et son manifeste (bloc `history`)."""
    if not hist_snapshot.startswith(f"{HIST_PREFIX}-"):
        raise ValueError(f"L'instantané assemblé doit commencer par {HIST_PREFIX}-")
    flux_manifest = json.loads(
        (data_path("manifests") / f"{flux_snapshot}.json").read_text(encoding="utf-8")
    )
    grid = flux_manifest["grid"]
    flux_start = pd.Timestamp(grid["first_timestamp"]).tz_convert("UTC")
    flux_end = pd.Timestamp(grid["last_timestamp"]).tz_convert("UTC")
    start, _ = history_window(flux_start, cycles)

    paths = sorted((data_path("history") / archive_snapshot / "archives").glob("*"))
    if not paths:
        raise FileNotFoundError(f"Aucune archive dans data/history/{archive_snapshot}/archives")
    arc, stats = archive_long(paths)

    counts = pd.read_csv(
        data_path("processed") / flux_snapshot / "counts.csv",
        dtype=str,
        keep_default_na=False,
        usecols=["counter_id", "timestamp", "count"],
    )
    counts["ts"] = pd.to_datetime(counts["timestamp"], utc=True, format="ISO8601")
    counts["n"] = pd.to_numeric(counts["count"], errors="coerce")
    twins, renames, detail = find_twins(arc, counts)

    flux_raw_path = data_path("history") / flux_snapshot / "comptage-velo-donnees-compteurs__complet.csv"
    header = pd.read_csv(flux_raw_path, sep=";", nrows=0, encoding="utf-8-sig").columns
    usecols = [c for c in RAW_COLUMNS if c in header]
    flux_raw = pd.read_csv(
        flux_raw_path,
        sep=";",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
        usecols=usecols,
    )
    flux_ts, _, _ = parse_timestamps(flux_raw["date"])
    meta = flux_raw.drop_duplicates("id_compteur").set_index("id_compteur")
    flux_ids = sorted(meta.index)

    rows = []
    for cid in flux_ids:
        s = counter_series(arc, cid, twins.get(cid), start, flux_start, renames.get(cid))
        if s.empty:
            continue
        part = pd.DataFrame(
            {
                "id_compteur": cid,
                "sum_counts": [_format_count(v) for v in s.to_numpy()],
                "date": s.index.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            }
        )
        for col in usecols:
            if col not in part.columns:
                part[col] = meta.at[cid, col]
        rows.append(part[usecols])
    in_flux = (flux_ts >= flux_start) & (flux_ts <= flux_end)
    assembled = pd.concat([*rows, flux_raw[in_flux.to_numpy()][usecols]], ignore_index=True)

    out_dir = data_path("history") / hist_snapshot
    out = out_dir / HIST_RAW_FILENAME
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    assembled.to_csv(tmp, sep=";", index=False, encoding="utf-8", compression="gzip")
    tmp.replace(out)

    arc_ids = set(arc["id"])
    archive_only = sorted(arc_ids - set(flux_ids) - set(twins.values()) - set(renames.values()))
    last_seen = arc[arc["id"].isin(archive_only)].groupby("id")["ts"].agg(["min", "max"])
    archive_manifest = load_manifest(archive_snapshot)
    manifest = load_manifest(hist_snapshot)
    manifest["retrieved_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest["sources"] = [
        {"source_id": f"archives:{archive_snapshot}", "files": archive_manifest.get("files", [])},
        {
            "source_id": f"flux:{flux_snapshot}",
            "files": [
                f for f in flux_manifest.get("files", []) if f.get("role") == "raw"
            ],
        },
    ]
    upsert(manifest["files"], file_entry(out, "raw", n_rows=int(len(assembled))), "path")
    manifest["history"] = {
        "assembly_version": ARCHIVES_VERSION,
        "raw_file": HIST_RAW_FILENAME,
        "archive_snapshot": archive_snapshot,
        "flux_snapshot": flux_snapshot,
        "cycles": cycles,
        "start": start.isoformat(),
        "flux_start": flux_start.isoformat(),
        "end": flux_end.isoformat(),
        "window_rule": (
            f"Grille commune du {start:%d/%m/%Y} au {flux_end:%d/%m/%Y %H:%M} UTC : "
            f"{cycles} cycles d'un an issus des archives, puis la grille de {flux_snapshot}."
        ),
        "rules": ASSEMBLY_RULES,
        "twins": twins,
        "renames": renames,
        "twin_detail": detail,
        "n_rows_without_counter_id": stats["n_rows_without_counter_id"],
        "n_archive_conflicts": stats["n_conflicts"],
        "n_rows_from_archives": int(sum(len(r) for r in rows)),
        "n_rows_from_flux": int(in_flux.sum()),
        "excluded_archive_only": [
            {"counter_id": i, "first": r["min"].isoformat(), "last": r["max"].isoformat()}
            for i, r in last_seen.iterrows()
        ],
    }
    write_manifest(manifest)
    return out


def print_assembly(hist_snapshot: str) -> None:
    m = load_manifest(hist_snapshot)["history"]
    print(f"\n=== Assemblage {hist_snapshot}")
    print(f"Fenêtre : {m['start']} -> {m['end']} (flux à partir de {m['flux_start']})")
    print(f"Canaux jumeaux additionnés (R1) : {len(m['twins'])}")
    print(f"Compteurs renommés dans l'archive, raccordés (R1 bis) : {len(m['renames'])}")
    for k, v in m["renames"].items():
        print(f"  {k} <- {v}")
    weak = [
        d
        for d in m["twin_detail"]
        if d["identical_share"] < TWIN_MIN_IDENTICAL and d["rule"] != "absent"
    ]
    absent = [d["counter_id"] for d in m["twin_detail"] if d["rule"] == "absent"]
    print(f"Compteurs du flux absents de la période commune des archives : {len(absent)}")
    print(f"Compteurs sous {TWIN_MIN_IDENTICAL:.0%} d'heures identiques au flux : {len(weak)}")
    for d in weak:
        print(f"  {d}")
    print(f"Lignes sans identifiant écartées (R2) : {m['n_rows_without_counter_id']}")
    print(f"Conflits dans les archives : {m['n_archive_conflicts']}")
    print(f"Compteurs seulement dans les archives, hors grille (R3) : {len(m['excluded_archive_only'])}")
    print(f"Lignes : {m['n_rows_from_archives']} des archives, {m['n_rows_from_flux']} du flux")


# ----------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--lister", action="store_true", help="lister les pièces jointes et quitter")
    ap.add_argument("--snapshot", help="identifiant archive-AAAAMMJJ (défaut : aujourd'hui UTC)")
    ap.add_argument("--annees", type=int, nargs="+", help="années civiles (sinon : --cycles)")
    ap.add_argument(
        "--cycles", type=int, default=2, help="années pleines avant le début du flux (défaut 2)"
    )
    ap.add_argument("--comparer", help="instantané du flux préparé à comparer (ex. flux-20261115)")
    ap.add_argument("--force", action="store_true", help="retélécharger même si présent")
    ap.add_argument(
        "--assembler", metavar="HIST", help="assembler archives + flux dans hist-AAAAMMJJ"
    )
    ap.add_argument(
        "--sans-preparation", action="store_true", help="avec --assembler : ne pas lancer prepare"
    )
    args = ap.parse_args(argv)

    if args.assembler:
        if not (args.snapshot and args.comparer):
            raise SystemExit("--assembler a besoin de --snapshot archive-… et --comparer flux-…")
        assemble_history(args.assembler, args.snapshot, args.comparer, args.cycles)
        print_assembly(args.assembler)
        if not args.sans_preparation:
            from src.data import prepare

            prepare.prepare_all(args.assembler)
        return 0

    if args.lister:
        for a in list_attachments():
            print(f"{a['title']} -> {a['href']}")
        return 0

    snapshot = args.snapshot or snapshot_id_for(dt.datetime.now(dt.timezone.utc), SNAPSHOT_PREFIX)
    if not snapshot.startswith(f"{SNAPSHOT_PREFIX}-"):
        raise SystemExit(f"Refusé : l'instantané d'archives doit commencer par {SNAPSHOT_PREFIX}-")
    window = None
    if args.annees:
        years = sorted(set(args.annees))
    else:
        if not args.comparer:
            raise SystemExit("--cycles a besoin de --comparer flux-AAAAMMJJ (début du flux).")
        window = history_window(flux_grid_start(args.comparer), args.cycles)
        years = years_for(*window)
        print(f"{args.cycles} cycles : {window[0]} -> {window[1]} ; années {years}")
    paths = acquire_years(snapshot, years, force=args.force)
    inv = inventory(paths, args.comparer, window)
    print_inventory(inv)
    out = data_path("processed") / snapshot / "archives_inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, ensure_ascii=False, indent=2, default=str) + "\n", "utf-8")
    print(f"\nInventaire : {relative_to_root(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

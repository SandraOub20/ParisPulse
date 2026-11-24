#!/bin/sh
# Commandes de développement et lancement local de ParisPulse.
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv 0.13.x est requis. Voir doc/ENVIRONNEMENT.md." >&2
    exit 1
fi

COMMAND=${1:-help}
if [ "$#" -gt 0 ]; then shift; fi

case "$COMMAND" in
    setup)
        uv sync --locked "$@"
        ;;
    check)
        uv lock --check
        uv run --locked --no-sync ruff check src tests
        uv run --locked --no-sync ruff format --check src tests
        ;;
    test)
        uv run --locked --no-sync pytest "$@"
        ;;
    notebook)
        uv run --locked --no-sync jupyter lab --ip=127.0.0.1 --no-browser "$@"
        ;;
    app|demo)
        if [ "$COMMAND" = demo ]; then
            snapshot=data/processed/hist-20261117
            archive=livraison/hist-20261117.zip
            if [ ! -s "$snapshot/counts.csv" ] || [ ! -s "$snapshot/counters.csv" ] \
                || [ ! -s "$snapshot/inventory_quality.csv" ] || [ ! -s "$snapshot/context.csv" ]; then
                if ! command -v unzip >/dev/null 2>&1; then
                    echo "unzip est requis pour extraire l’instantané E1." >&2
                    exit 1
                fi
                if ! unzip -Z -1 "$archive" >/dev/null 2>&1; then
                    if ! git lfs version >/dev/null 2>&1; then
                        echo "Installez Git LFS pour télécharger l’instantané E1." >&2
                        exit 1
                    fi
                    git lfs pull --include="$archive" --exclude=""
                fi
                unzip -n "$archive"
                for file in counts.csv counters.csv inventory_quality.csv context.csv; do
                    if [ ! -s "$snapshot/$file" ]; then
                        echo "Instantané E1 incomplet. Vérifiez le fichier $snapshot/$file." >&2
                        exit 1
                    fi
                done
            fi
            uv sync --locked --inexact
        fi
        exec uv run --locked --no-sync python -m streamlit run src/app/streamlit_app.py \
            --server.address=127.0.0.1 "$@"
        ;;
    help|-h|--help)
        cat <<'HELP'
Usage : ./run.sh <commande>
  setup             Créer .venv et installer les dépendances verrouillées
  setup --group dl  Installer aussi PyTorch (CPU Linux/Windows)
  check             Vérifier verrouillage, lint et format Python
  test [options]    Lancer pytest (code 5 si aucun test n'existe encore)
  notebook          Ouvrir JupyterLab localement, avec authentification
  app [options]     Ouvrir l’application ParisPulse V2 sur http://localhost:8501
  demo [options]    Préparer les données et les dépendances, puis ouvrir ParisPulse V2
HELP
        ;;
    *)
        echo "Commande inconnue : $COMMAND. Utiliser ./run.sh help." >&2
        exit 2
        ;;
esac

#!/bin/sh
# Commandes de développement uniquement ; aucun calcul métier ni application.
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
    help|-h|--help)
        cat <<'HELP'
Usage : ./run.sh <commande>
  setup             Créer .venv et installer les dépendances verrouillées
  setup --group dl  Installer aussi PyTorch (CPU Linux/Windows)
  check             Vérifier verrouillage, lint et format Python
  test [options]    Lancer pytest (code 5 si aucun test n'existe encore)
  notebook          Ouvrir JupyterLab localement, avec authentification

L'application et les algorithmes restent à implémenter dans src/.
HELP
        ;;
    *)
        echo "Commande inconnue : $COMMAND. Utiliser ./run.sh help." >&2
        exit 2
        ;;
esac

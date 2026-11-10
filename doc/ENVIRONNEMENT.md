# Environnement de développement

L'environnement est prêt à installer ; les modules de `src/` restent des consignes sans implémentation. Aucun téléchargement de données, apprentissage ou lancement d'application n'est déclenché par l'installation.

## Installation locale - macOS ou Linux

Prérequis : Git, un accès réseau pour la première installation et **uv 0.13.x**. Python **3.11** est téléchargé automatiquement par uv si nécessaire. Il n'est pas nécessaire de modifier le Python du système.

Pour installer la version d'uv utilisée par le Dockerfile :

```sh
curl -LsSf https://astral.sh/uv/0.13.1/install.sh | sh
```

Rouvrir le terminal si `uv` n'est pas encore dans le `PATH`, puis, depuis la racine de ParisPulse :

```sh
./run.sh setup
./run.sh check
./run.sh notebook
```

`setup` crée `.venv/` avec les dépendances verrouillées, y compris les outils de développement. `notebook` lance JupyterLab sur l'interface locale ; ouvrir l'URL avec jeton affichée dans le terminal, puis créer son notebook dans `notebooks/`. Arrêter le serveur avec `Ctrl+C`. Aucun serveur n'est démarré par `setup`.

Les commandes du lanceur fonctionnent aussi depuis un autre répertoire. Pour les commandes uv ci-dessous, se placer à la racine du dépôt.

Sous Windows, utiliser WSL2 pour le lanceur shell, ou les commandes équivalentes dans un terminal disposant d'uv :

```sh
uv sync --locked
uv run --locked ruff check src tests
uv run --locked pytest
uv run --locked jupyter lab
```

## Bibliothèques disponibles

| Usage | Bibliothèques |
| --- | --- |
| Données, CSV et temps | NumPy, pandas, HTTPX, PyYAML |
| Modèles classiques et évaluation | scikit-learn |
| Figures et cartes | Matplotlib, Plotly, Folium |
| Future application | Streamlit, streamlit-folium |
| Développement | JupyterLab, ipykernel, pytest, Ruff |
| Expérience deep learning, installation séparée | PyTorch, groupe `dl` |

Le socle fonctionne sur CPU. PyArrow est aussi installé comme dépendance de Streamlit ; son usage interne reste facultatif. DuckDB et les bibliothèques de modèles supplémentaires pourront être ajoutés si les expériences les justifient.

Pour installer PyTorch :

```sh
./run.sh setup --group dl
uv run --locked --group dl python -c "import torch; print(torch.__version__)"
./run.sh notebook
```

Sous Linux/Windows, le groupe utilise l'index officiel des roues CPU ; sous macOS, la distribution standard est utilisée. Aucun poids préentraîné n'est téléchargé. Les commandes `check`, `test` et `notebook` du lanceur réutilisent l'environnement installé, sans le synchroniser à nouveau. Pour les appels directs à `uv run`, préciser `--group dl` si nécessaire. Relancer `setup` sans ce groupe retire les dépendances propres au deep learning.

## Éditeur et imports

VS Code reçoit des recommandations d'extensions et utilise l'interpréteur de `.venv/`. Si nécessaire, choisir **Python: Select Interpreter**, puis `.venv/bin/python` (Windows : `.venv/Scripts/python.exe`). Pour un notebook, sélectionner ce même environnement comme noyau. Aucun noyau global n'est installé.

`src/` reste le nom du paquet du squelette : les futurs imports pourront prendre la forme `from src.models.known import baseline`. Le lanceur ajoute la racine du dépôt au chemin Python, notamment pour les notebooks créés dans un sous-dossier. Le conteneur fait de même. Lors d'un lancement direct de Jupyter, travailler depuis la racine ou définir le chemin Python vers celle-ci.

## Vérifications

```sh
./run.sh check
./run.sh test
```

`check` vérifie la cohérence du verrouillage, les erreurs Python détectables par Ruff, les imports et le format. Il ne valide pas les résultats scientifiques. `test` lance pytest : **le code de sortie 5 est attendu tant qu'aucun test n'a été écrit**. Les scénarios à implémenter figurent dans [tests/README.md](../tests/README.md).

Pour appliquer volontairement le formatage :

```sh
uv run --locked --no-sync ruff format src tests
```

## Dépendances et reproductibilité

- `pyproject.toml` définit les dépendances directes, les groupes et les outils.
- `uv.lock` verrouille les versions et les distributions ; le versionner avec toute modification des dépendances.
- `requirements.txt` est un **export généré du socle**, sans les outils de développement ni PyTorch. Il permet une installation par pip avec Python 3.11 ; ne pas le modifier à la main.
- `.python-version` impose Python 3.11 ; `.venv/` reste local et ignoré par Git.

Pour ajouter une dépendance justifiée, puis actualiser l'export :

```sh
uv add nom-du-paquet
uv export --locked --no-dev --no-hashes --no-emit-project --output-file requirements.txt
./run.sh check
```

Utiliser `uv add --group dev nom-du-paquet` pour un outil de développement, ou `uv add --group dl nom-du-paquet` pour une dépendance spécifique à l'expérience DL. Le groupe `dev` est installé par défaut. L'installation courante utilise `--locked` et ne met pas spontanément les dépendances à jour. Les mises à jour volontaires se font avec `uv lock --upgrade`, puis synchronisation, export et vérification.

## Docker - environnement de développement

Prérequis : Docker Engine ou Docker Desktop avec Compose v2 en cours d'exécution. Le Dockerfile installe le même socle et les mêmes outils que l'installation locale, sous un utilisateur non privilégié. Les dépendances résident dans `/opt/venv`, séparément de la `.venv/` de l'hôte.

```sh
docker compose build dev
docker compose run --rm --service-ports dev
```

Dans le shell du conteneur :

```sh
./run.sh check
jupyter lab --ip=0.0.0.0 --port=8888 --no-browser
```

Ouvrir ensuite `http://localhost:8888` avec le jeton du serveur. Les ports 8888 et 8501 sont publiés uniquement sur l'interface locale de l'hôte. Le dépôt est monté dans `/workspace` : les fichiers modifiés dans le conteneur sont conservés sur l'hôte. La session se termine avec `exit` ; les modifications du système de fichiers hors du dépôt monté disparaissent. Sous Linux, adapter l'UID du développeur si les permissions du dossier monté l'exigent.

Le groupe `dl` peut être installé pour une session avec `./run.sh setup --group dl`. Il n'est pas inclus dans l'image de base. Le port 8501 est réservé à la future application Streamlit ; aucun service applicatif n'existe encore.

## Configuration scientifique et suite du travail

`config/project.example.yaml` reste un exemple à discuter avec les équipes. Adopter ensuite `config/project.yaml` selon le [guide de configuration](../config/README.md). L'environnement ne crée pas de configuration scientifique validée et ne charge pas encore ce fichier.

E5 devra compléter le lancement applicatif lorsque les modules seront prêts : préparation des ressources, vérification de provenance, appel réel des partenaires, export et installation croisée. Les consignes restent dans [run.sh.example](../run.sh.example) et l'[architecture](ARCHITECTURE.md).

# ParisPulse

Comprendre et prévoir la fréquentation cyclable à l'échelle d'un réseau.

ParisPulse prévoit les **24 prochaines heures** d'un compteur vélo parisien, sur des sites connus (avec historique) et sur de nouveaux sites (avec 1, 3 ou 7 jours d'historique local), puis compare la prévision aux mesures réelles.

Projet étudiant fondé sur le [sujet](ParisPulse_Sujet_etudiants.pdf).

## Lancer l'application

**Prérequis** : Git, Git LFS, [uv 0.13.x](doc/ENVIRONNEMENT.md), unzip et un accès réseau pour la première installation. Python 3.11 est installé par uv si nécessaire.

Depuis la racine du dépôt :

```sh
./run.sh setup --group dl
./run.sh demo
```

La première commande installe les dépendances, dont PyTorch, **nécessaire au démarrage de l'application**. La seconde prépare l'instantané de données `hist-20261117` et ouvre l'application sur [http://localhost:8501](http://localhost:8501). Les fois suivantes, `./run.sh app` suffit.

Sous Windows, utiliser WSL2, ou extraire `livraison/hist-20261117.zip` à la racine puis lancer :

```sh
uv sync --locked --group dl
uv run --locked --group dl python -m streamlit run src/app/streamlit_app.py
```

L'application propose :

- une carte du réseau et le choix du compteur et du sens ;
- sites connus : les deux références hebdomadaires et leur comparaison ;
- nouveaux sites : une référence locale, Chronos-2 en direct (poids téléchargés au premier calcul) et des prévisions archivées ;
- l'historique, les données manquantes, le contexte, l'erreur du cas et un export ZIP.

Détails dans le [guide de l'application](src/app/README.md).

## Résultats de validation

Cas `proto-v1`, origines de juillet et août 2026, instantané `hist-20261117`. MAE en vélos par heure, moyenne entre compteurs : plus bas est meilleur.

**Sites connus** (95 compteurs évaluables), [scores E4](data/evaluation/proto-v1/EXP-E2/scores.csv) :

| Méthode | MAE |
| --- | ---: |
| MLP (graine 0) | 22,23 |
| HGB (gradient boosting) | 22,25 |
| Référence : médiane des 4 semaines précédentes | 27,01 |
| Référence : même heure, semaine précédente | 29,75 |

L'écart entre MLP et HGB est plus petit que l'écart entre trois graines du MLP (0,36) : la règle fixée dans [EXP-E2-03](reports/experiments/EXP-E2-03.md) désigne le **HGB**.

**Nouveaux sites** (5 compteurs, modèles non adaptés au site), [scores E4](data/evaluation/proto-v1/EXP-E3/scores.csv) :

| Historique local | Chronos-2 | TimesFM 2.5 | MLP de l'équipe 2 |
| --- | ---: | ---: | ---: |
| 24 h | 26,09 | 27,98 | non applicable |
| 72 h | 22,83 | 22,55 | non applicable |
| 168 h | 19,67 | 19,79 | 18,80 |

Ces résultats portent sur la **validation** seulement. Le test final (1er octobre au 14 novembre 2026) reste réservé jusqu'au gel des choix.

## État du projet et limites connues

- La validation du protocole par le professeur n'est pas enregistrée (`validated_at: null` dans [config/project.yaml](config/project.yaml)).
- Le HGB et le MLP des sites connus sont utilisables en ligne de commande, mais **pas encore dans l'application**.
- La variante adaptée de Chronos-2 n'est pas encore intégrée.
- Les scores des nouveaux sites ne comprennent pas de référence simple.
- `./run.sh demo` seul échoue sur une copie neuve (`No module named 'torch'`) : lancer d'abord `./run.sh setup --group dl`.
- `python -m src.eval.protocol` échoue (`KeyError: 'status'`). Le fichier `cases.csv` déjà livré reste utilisable.
- `./run.sh check` signale des erreurs de lint et de formatage.

## Recalculer les résultats

Après l'installation ci-dessus et `./run.sh demo` (qui extrait les données), depuis la racine :

```sh
export PYTHONPATH=.

# Prévisions HGB des sites connus, sous un nouveau nom d'expérience (environ 1 min)
uv run --locked --group dl python -m src.models.known.predict \
  --cases data/evaluation/proto-v1/cases.csv --snapshot hist-20261117 \
  --experiment MON-ESSAI --variant hgb --batch
```

Les variantes sont `reference`, `reference_profile`, `mlp` et `hgb` ; `--batch` ne s'applique qu'à `mlp` et `hgb`.

Pour refaire les scores officiels à partir des prévisions livrées (environ 2 min) :

```sh
(cd data/prediction_results && unzip -o EXP-E2/EXP-E2-predictions.zip)
uv run --locked --group dl python -m src.eval.backtest
```

La seconde commande **réécrit** les fichiers de `data/evaluation/proto-v1/EXP-E2/` et `EXP-E3/`. Les prévisions extraites pèsent environ 235 Mo et ne sont pas ignorées par Git : **ne pas les commiter**.

## Développement

```sh
./run.sh setup --group dl   # dépendances, dont celles du deep learning
./run.sh test               # tests
./run.sh check              # verrouillage, lint et format
./run.sh notebook           # JupyterLab local
```

Relancer `./run.sh setup` sans `--group dl` retire PyTorch. Voir [l'environnement de développement](doc/ENVIRONNEMENT.md) pour VS Code, Windows et Docker.

## Organisation

| Équipe | Dossier | Rôle |
| --- | --- | --- |
| E1 - Données et contexte | [src/data](src/data/README.md) | Préparation des comptages, qualité, contexte |
| E2 - Prévision sur sites connus | [src/models/known](src/models/known/README.md) | Références, HGB, MLP |
| E3 - Prévision sur nouveaux sites | [src/models/new](src/models/new/README.md) | Chronos-2, TimesFM, adaptation locale |
| E4 - Évaluation et fiabilité | [src/eval](src/eval/README.md) | Cas attendus, scores, couverture |
| E5 - Application | [src/app](src/app/README.md) | Interface Streamlit et export |

| Données | Emplacement |
| --- | --- |
| Instantané livré | [livraison](livraison/README.md) (Git LFS) |
| Mesures préparées | `data/processed/` |
| Prévisions | `data/prediction_results/` |
| Cas et scores | `data/evaluation/` |
| Modèles entraînés | `artifacts/models/` |

## Documentation

| Document | Contenu |
| --- | --- |
| [Index de la documentation](doc/README.md) | Ordre de lecture et références du dépôt |
| [Architecture](doc/ARCHITECTURE.md) | Fichiers, responsabilités et flux (rédigée avant l'implémentation) |
| [Contrats v2](doc/CONTRATS.md) | Formats communs, cas de prévision, exports et interfaces |
| [Protocole proposé](doc/PROTOCOLE_EVALUATION.md) | Sites connus et nouveaux, information disponible, métriques |
| [Fiches d'expérience](reports/experiments/) | Questions, contrôles, résultats et décisions |
| [Suivi de l'équipe 2](reports/teams/E2_SUIVI.md) | Journal des modifications et décisions |
| [Prise en main de l'équipe 3](reports/teams/E3-DOC-&-PRISE-EN-MAIN.md) | Utiliser les modèles des nouveaux sites |
| [Suivi et remise](doc/SUIVI_ET_REMISE.md) | Livrables, barème et journal individuel |
| [Gabarits](doc/templates/README.md) | Formats d'échange et de suivi |
| [Plan du projet](PLAN_PROJET.md) | Exigences, priorités et risques |
| [Bibliographie](doc/BIBLIOGRAPHIE.md) | Sources de données et lectures |

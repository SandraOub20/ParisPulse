# ParisPulse

Projet de M2 Data Science : prévision de la fréquentation cyclable à Paris.

## Organisation du projet

- `data/history/` : données historiques au format CSV.
- `data/processed/` : données préparées au format CSV, utilisées notamment par les modèles.
- `doc/` : documentation commune aux équipes.
- `notebooks/` : exploration, expérimentations et évaluations des équipes 1 à 4.
- `src/data/` : code de parsing, preprocessing et feature engineering (équipe 1).
- `src/models/` : code des modèles (équipes 2 et 3).
- `src/app/` : interface de l'application finale (équipe 4).
- `artifacts/` : artefacts générés, notamment les modèles entraînés.

L'équipe 5 coordonne l'intégration et la livraison de l'application finale.

## Docker

Construire l'image depuis la racine du dépôt :

```bash
docker build -t parispulse .
```

Le point d'entrée de l'application et la commande de lancement du conteneur
seront à définir lorsque le framework et l'interface de l'équipe 4 seront prêts.

## Dépendances Python

Ajouter les dépendances du projet dans `requirements.txt`.

# Nouveaux sites - équipe 3

## Prévision Chronos-2

`predict.py` fournit `predict_24h(case, history, variant="frozen")` et
`save_forecasts(result, path)`. Chronos-2 et Google TimesFM 2.5 en variante `frozen`
produisent une prévision. Les chemins `adapted` et `team2` sont présents comme points
d'extension et lèvent `NotImplementedError` jusqu'à leur implémentation.

Le cas doit être un `new_site` d'un site réservé (`S_dev_new` ou `S_test_new`) avec un
budget local positif (1, 3 ou 7 jours). L'historique fourni est refiltré sur le compteur, le support du cas et
la coupure `origin - publication_lag_hours`
(24 h par défaut, comme E2). Seules les mesures publiées (`count_raw` avec
`is_observed=true`, ou `count` si `count_raw` est absent) entrent dans le modèle; les
estimations d'E1 ne sont pas utilisées. La médiane Chronos-2 est la prévision ponctuelle;
les valeurs négatives sont ramenées à zéro et marquées dans `status_reason`. Le résultat
suit `ForecastResult` et les colonnes CSV communes; `save_forecasts` réutilise les
exporteurs E2 pour écrire les fichiers `.pred.csv` et `.runs.csv`.

### Installer les dépendances DL

Depuis la racine du dépôt, synchroniser l'environnement verrouillé avec le groupe
deep-learning :

```powershell
py -m uv sync --locked --group dl
```

Cette commande installe notamment PyTorch et `chronos-forecasting` dans l'environnement
du projet. Pour vérifier l'installation :

```powershell
py -m uv run --locked --group dl python -c "import torch, chronos; print(torch.__version__, chronos.__file__)"
```

Les poids `amazon/chronos-2` sont téléchargés au premier chargement du modèle. L'identifiant
de modèle public ne certifie pas l'absence de contamination par les données du projet.

## Lancer la validation Chronos-2

Depuis la racine du dépôt, exécuter :

```
$env:PYTHONPATH = (Get-Location).Path
py -m uv run --locked --group dl python .\src\models\new\validation.example.chronos.py
```

Le script traite tous les cas de validation `S_dev_new` (budgets de 24, 72 et 168 heures)
et écrit les prévisions ainsi que les résultats d'exécution dans
`data/prediction_results/EXP-E3/`, avec le suffixe `validation-all`.

## Tâches à faire

1. Demander à l'équipe 4 un rapport comparant les premières prévisions Chronos-2 à la
   vérité terrain, puis analyser les résultats sur les cas et budgets concernés.
2. À partir de ce rapport, décider si une adaptation de Chronos-2 est justifiée. Si oui,
   l'implémenter sur le support local autorisé, sans utiliser les cibles de validation.
3. Développer la prédiction sur les nouveaux sites avec `google_TimesFM_2.5`, en respectant
   le contrat commun de prévision à 24 heures et les règles de séparation des données.
4. Faire évaluer les méthodes implémentées par l'équipe 4 dans les mêmes conditions et
   transmettre à E5 les résultats, coûts et limites.

## Règles de comparabilité

- Même historique et même contexte entre variantes.
- Aucune normalisation sur les mesures masquées.
- Aucun cumul silencieux de données entre cas.
- Les réglages se choisissent sur des sites de développement distincts du test final.

## Livraisons

- Prévisions et coûts dans `data/prediction_results/`
- Paramètres dans `artifacts/models/`
- `support_id` et `adaptation_id` traçables selon les [contrats](../../../doc/CONTRATS.md)

Les modules présents sont des consignes à compléter ; ils ne remplacent pas le protocole officiel du projet.

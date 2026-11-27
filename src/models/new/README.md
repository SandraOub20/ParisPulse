# Nouveaux sites - équipe 3

## Installation des dépendances pour les prediction new_sites

Depuis la racine du dépôt, synchroniser l'environnement verrouillé avec le groupe
deep-learning :

```powershell
py -m uv sync --locked --group dl
```

Ce groupe installe les dépendances nécessaires au MLP Team2 (dont PyTorch) et à Chronos-2.
Pour vérifier l'installation :

```powershell
py -m uv run --locked --group dl python -c "import torch, chronos; print(torch.__version__, chronos.__file__)"
```

Chronos-2 télécharge ses poids `amazon/chronos-2` lors du premier chargement. 

## Cadre commun de prévision

`predict.py` fournit `predict_24h(case, history, variant="frozen")` et
`save_forecasts(result, path)`. Les cas (cases choisie) doivent être des `new_site` réservés à E3 (`S_dev_new` ou `S_test_new`) avec un budget local positif de 1, 3 ou 7 jours.

L'historique est refiltré sur le compteur, le support local du cas et la coupure
`origin - publication_lag_hours` (24 h par défaut). Seules les mesures publiées
(`count_raw` avec `is_observed=true`, ou `count` si `count_raw` est absent) sont utilisées;
les estimations d'E1 sont exclues. Les résultats suivent le contrat `ForecastResult` et les
colonnes CSV communes. Les fichiers de prévisions et de coûts sont écrits dans
`data/prediction_results/`.

## Prévision Chronos-2

Chronos-2 est disponible en variante `frozen` et en variante `adapted-v2`.
La v2 mélange la médiane des prévisions Chronos-2 avec le profil horaire local
du support autorisé; les poids par budget sont lus dans
`artifacts/models/e3-chronos2-adapted-v2/blend_weights.json`.
Les valeurs négatives sont ramenées à zéro et signalées dans `status_reason`.

### Lancer la validation Chronos-2 (Frozen)

Depuis la racine du dépôt, exécuter :

```powershell
$env:PYTHONPATH = (Get-Location).Path
py -m uv run --locked --group dl python .\src\models\new\validation.example.chronos.py
```

Le script traite tous les cas de validation `S_dev_new` des budgets 24 (1j), 72 (3j) et 168 (7j) heures,
puis écrit les prévisions et les exécutions dans `data/prediction_results/EXP-E3/` avec le
suffixe `validation-all`.

### Lancer la validation Chronos-2 (adapted-v2)

Depuis la racine du dépôt, exécuter :

```powershell
$env:PYTHONPATH = (Get-Location).Path
py -m uv run --locked --group dl python .\src\models\new\validation.example.chronos.adapted.py
```

Le script valide les cas `S_dev_new` de validation de l'instantané `hist-20261117`
et écrit les prévisions et les exécutions dans `data/prediction_results/EXP-E3/`
avec le suffixe `e3-chronos-2-adapted-v2-validation-b24-b72-b168`. Ce nom distinct
préserve les anciens fichiers de résultats v1.

## Prévision MLP Team2

Le MLP de l'équipe 2 est disponible en variante `frozen`. Il utilise le contexte (jour de greve, meteo...) disponible à
l'origine et requiert 7 jours de support local : son entrée couvre 168 heures, dont au
moins 84 doivent être mesurées. Si le MLP refuse un cas, la référence hebdomadaire est
utilisée et le motif du refus est tracé. Voir la
[documentation de l'équipe 2](../../../reports/teams/E2_PRISE_EN_MAIN.md).

### Lancer la validation MLP Team2

Depuis la racine du dépôt, exécuter :

```powershell
$env:PYTHONPATH = (Get-Location).Path
py -m uv run --locked --group dl python .\src\models\new\validation.example.modelTeam2.py
```

Le script sélectionne les cas `S_dev_new` de validation ayant `local_budget_hours = 168`.
Il charge l'historique et le `context.csv` de l'instantané `hist-20261117`, puis écrit les
prévisions et les coûts dans `data/prediction_results/EXP-E3/` avec le suffixe
`validation-budget-168`.

## Prévision Google TimesFM 2.5

le modele publique Google TimesFM 2.5 est un concurrent direct a chronos-2.

### Lancer la validation Google TimesFM 2.5

Depuis la racine du dépôt, exécuter :

```
$env:PYTHONPATH = (Get-Location).Path
py -m uv run --locked --group dl python .\src\models\new\validation.example.google.py
```

---

## Tâches à faire

1. Faire évaluer par l'équipe 4 les prévisions des modèles implémentés et analyser les
   résultats par cas et par budget.
2. À partir de ces résultats, décider si une adaptation est justifiée et, le cas échéant,
   l'implémenter sur le support local autorisé, sans utiliser les cibles de validation.
3. Implémenter Google TimesFM 2.5, puis ajouter son script de validation.
4. Transmettre à E5 les résultats, coûts et limites des méthodes évaluées.

## Règles de comparabilité

- Utiliser le même historique et le même contexte entre variantes.
- Ne pas normaliser à partir des mesures masquées.
- Ne pas cumuler silencieusement les données entre cas.
- Choisir les réglages sur des sites de développement distincts du test final.

## Livrables

- Prévisions et coûts dans `data/prediction_results/`
- (peut etre) Paramètres des modèles dans `artifacts/models/`

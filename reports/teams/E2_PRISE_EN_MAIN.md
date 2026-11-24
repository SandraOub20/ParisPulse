# Prise en main : socle `train.py` et MLP `neural.py`

Pour Ania (HGB) et Esther (entraînement du MLP). Auteur : Idir. Branche `Team2-idir`.

> **Mise à jour du 2026-11-23 (MOD-008, Esther, branche `Team2-Esther`)** : le MLP apprend (`fit_mlp`) et prévoit (`predict_mlp`). Sections modifiées : « Ce qui existe », « Démarrer », « Entraîner un modèle », « MLP : apprentissage et prévision », « Règles à garder », « Points ouverts ». Détail et justification : [E2_SUIVI.md, MOD-008](E2_SUIVI.md#4-journal-des-modifications). Premier essai réel : [E2-TECH-003](../experiments/E2-TECH-003.md).

> **Mise à jour du 2026-11-24 (MOD-011, Idir)** : le HGB existe (`tabular.py`, MOD-010, Ania) et les deux modèles sont branchés dans `predict.py`. Sections modifiées : « Ce qui existe », « Démarrer », « Entraîner un modèle », « Ania : brancher le HGB », « Règles » (graine), « Prévoir un cas », « Prévoir avec `predict_24h` », « Points ouverts ». Détail : [E2_SUIVI.md, MOD-011](E2_SUIVI.md#4-journal-des-modifications).

## Ce qui existe

| Fichier | Fonctions | Rôle |
| --- | --- | --- |
| [train.py](../../src/models/known/train.py) | `load_training_data` | lit `counts.csv`, `context.csv`, l'inventaire ; en entrée, **mesures seules** (`count`), valeur E1 gardée dans `count_e1` |
| | `fit` | partie **commune** : compteurs `S_train` (E3 exclus), origines entre `train_start` et `fit_cutoff`, puis appelle la méthode. Refuse une `publication_lag_hours` différente de la configuration (MOD-008) |
| | `save_model` / `load_model` | dossier `artifacts/models/<model_run_id>/` : poids + `metadata.json` ; refus d'écraser, SHA-256 vérifié |
| | `register_backend` | déclare une méthode (comment apprendre, sauver, relire) |
| [neural.py](../../src/models/known/neural.py) | `build_windows` | fabrique les exemples du MLP (un par compteur × origine) ; signale aussi un contexte inconnu à l'origine (`context_missing`) |
| | `MLPNet`, `save_mlp`, `load_mlp` | réseau (2 couches de 128 par défaut). Le fichier `weights.pt` garde la latence et le bilan d'apprentissage (format 2 ; le format 1 reste lisible) |
| | `mlp_hyperparameters` | tous les réglages, contrôlés (clé inconnue refusée), à passer à `TrainConfig` |
| | `fit_mlp` | apprentissage ; « mlp » est déclaré avec `fit=fit_mlp` |
| | `predict_mlp`, `predict_windows` | prévision d'un cas ou refus motivé ; même calcul pour beaucoup de cas à la fois |
| | `main` | `python -m src.models.known.neural` : apprend, sauvegarde, écrit le bilan en JSON |
| [tabular.py](../../src/models/known/tabular.py) | `fit_hgb`, `predict_hgb`, `save_hgb` / `load_hgb`, `main` | HGB (Ania, MOD-010) : mêmes origines que le MLP, refus `hgb_*` |
| [predict.py](../../src/models/known/predict.py) | `load_trained` | charge **une fois** un modèle `mlp` ou `hgb` ; méthode vérifiée dans `metadata.json` avant tout import (le HGB tourne sans torch) (MOD-011) |
| | `trained_forecast` | prévision du modèle, ou repli tracé sur la référence s'il refuse (MOD-011) |
| | `predict_24h`, `run_experiment`, `main` | variantes `reference`, `reference_profile`, `mlp`, `hgb` ; `model_run_id` obligatoire pour les modèles ; `load_context` lit le contexte E1 (MOD-011) |

Tests : `tests/test_known_train.py`, `tests/test_known_neural.py`, `tests/test_known_neural_fit.py` (MOD-008, 43 tests), `tests/test_known_tabular.py` (MOD-010), `tests/test_known_predict_trained.py` (MOD-011, 21 tests).

## Démarrer

Méthode du projet ([ENVIRONNEMENT.md](../../doc/ENVIRONNEMENT.md)), avec uv 0.13.x :

```bash
./run.sh setup --group dl          # crée .venv avec PyTorch CPU (le groupe dl est indispensable au MLP)
git lfs pull --include="livraison/hist-20261117.zip" && unzip -o livraison/hist-20261117.zip
./run.sh test                      # 371 tests passés attendus (MOD-011)
./run.sh check                     # verrouillage, ruff, format
```

Sans uv (méthode d'Idir, avec pip) :

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu pytest ruff
git lfs pull --include="livraison/hist-20261117.zip" && unzip -o livraison/hist-20261117.zip
.venv/bin/python -m pytest -q
```

## Entraîner un modèle (une méthode qui sait apprendre)

```python
import pandas as pd
from src.models.known import neural, train  # importer neural DÉCLARE la méthode « mlp »

data = train.load_training_data("hist-20261117")
config = train.TrainConfig(
    method="mlp",                                    # ou "hgb" (importer alors tabular)
    fit_cutoff=pd.Timestamp("2026-06-30 22:00", tz="UTC"),   # 01/07 minuit à Paris
    train_start=None,                                # None = depuis le début des données (2023)
    use_context=True,
    hyperparameters=neural.mlp_hyperparameters(),    # TOUS les réglages, écrits dans metadata.json
    seed=0,
    snapshot_id="hist-20261117",
    context_version=data.context_version,
    feature_version=neural.INPUT_VERSION,
)
model = train.fit(config, data.counts, data.context, data.inventory)
train.save_model(model)                  # artifacts/models/e2-mlp-ctx-20260701-s0-xxxx/
model = train.load_model(model.model_run_id)
```

Le nom du modèle contient une empreinte de la config : changer un réglage change le nom, rien n'est écrasé.

**Piège** : sans `import src.models.known.neural`, `train.fit(... method="mlp" ...)` lève `KeyError: méthode 'mlp' inconnue` (la méthode se déclare à l'import du module).

## Ania : brancher le HGB (`tabular.py`) - fait (MOD-010)

Cette section décrit comment une méthode se branche sur `train.fit` ; le HGB est écrit ainsi ([E2-TECH-004](../experiments/E2-TECH-004.md)). Une méthode fournit 4 fonctions et se déclare. `train.fit` lui donne **les mêmes origines qu'au MLP** : la comparaison est équitable.

```python
from src.models.known import features as F
from src.models.known.train import MethodBackend, register_backend

def fit_hgb(config, counts, context, origins):
    X, y = F.build_training_frame(counts, origins, context, config.fit_cutoff, config.use_context)
    ...  # entraîner, renvoyer l'estimateur

register_backend("hgb", MethodBackend(
    "model.joblib", save=lambda est, p: joblib.dump(est, p), load=joblib.load,
    fit=fit_hgb, minimum_history_hours=...,
))
```

`build_training_frame` prend la latence de la configuration, comme `build_windows` : c'est pourquoi `train.fit` refuse désormais une `publication_lag_hours` différente (MOD-008).

## MLP : apprentissage et prévision (fait, MOD-008)

### Apprendre en une commande

```bash
uv run --locked --no-sync --group dl python -m src.models.known.neural \
  --snapshot hist-20261117 --fit-cutoff 2026-06-30T22:00:00+00:00 --seed 0
# options : --no-context, --set hidden=64 --set lr=0.0005, --train-start ..., --no-save
```

La commande écrit `artifacts/models/<model_run_id>/` (`weights.pt`, `metadata.json`, `training_report.json`) et affiche le bilan. Coût mesuré : [E2-TECH-003](../experiments/E2-TECH-003.md).

### Réglages (`neural.mlp_hyperparameters`)

| Réglage | Défaut | Rôle |
| --- | --- | --- |
| `hidden`, `layers`, `dropout` | 128, 2, 0,1 | forme du réseau (`layers=0` : modèle linéaire, **pas** du deep learning) |
| `lr`, `weight_decay` | 0,001, 0,0001 | optimiseur AdamW |
| `batch_size` | 256 | exemples par pas |
| `max_epochs`, `patience` | 100, 8 | plafond d'époques ; arrêt après 8 époques sans progrès |
| `holdout_weeks` | 4 | arrêt anticipé sur les 4 dernières semaines avant `fit_cutoff` (0 : sans) |
| `loss_weighting` | `scale` | `scale` : erreur en vélos/h ; `none` : erreur relative au niveau |

Une clé inconnue (faute de frappe) ou une valeur hors domaine est refusée.

### Ce que fait `fit_mlp`, et pourquoi

1. **Contrôles avant de lire une cible** : chaque origine est à minuit (Paris), sans doublon, et ses 24 cibles sont publiées à `fit_cutoff` (`origine + 24 h + latence <= fit_cutoff`). Sinon `ValueError`. `build_windows` lit les cibles sans regarder `fit_cutoff`, ce contrôle empêche donc la fuite.
2. **Exemples gardés** : fenêtre utilisable, contexte complet (si `use_context`), au moins une vraie cible. Les exclusions sont comptées dans le bilan.
3. **Perte L1 masquée, pondérée par le niveau** (`_masked_l1`) : une heure non mesurée ne compte jamais. Avec la pondération, on minimise l'erreur absolue en vélos/h, la métrique du projet ; c'est la pondération par l'échelle de DeepAR. La L1 traite aussi les cibles extrêmes (≈ 0,1 % au-delà de 59 fois le niveau) : son gradient ne dépend que du **signe** de l'erreur, donc une cible aberrante ne pèse pas plus qu'une autre. Aucun plafond arbitraire.
4. **Arrêt anticipé** sur les origines du 03/06 au 29/06/2026 (pour `fit_cutoff` au 01/07) : elles ne servent qu'à choisir la meilleure époque. Le réseau rendu est celui de cette époque, **sans** réapprentissage sur juin. Juillet-août n'est jamais lu.
5. **Graine** `config.seed` : même graine, mêmes poids **sur la même machine, avec le même nombre de threads torch**. Sur une autre machine, l'ordre des calculs change et l'arrêt anticipé peut choisir une autre époque (contrôle du 2026-11-24 : époque 17 au lieu de 20, MAE de contrôle 17,57 au lieu de 17,51, écart bien plus petit que celui entre graines). Le générateur aléatoire global de torch n'est pas modifié.

### Lire le bilan (`training_report.json` ou `net.training_report`)

| Clé | Ce qu'on y lit |
| --- | --- |
| `examples` | exemples gardés (`train`, `holdout`) et exclus (`excluded_not_usable`, `excluded_context_missing`, `excluded_no_target`) |
| `origins` | première et dernière origine d'apprentissage et d'arrêt anticipé |
| `history`, `best_epoch`, `stopped_early` | perte par époque (apprentissage, arrêt anticipé) ; époque retenue |
| `holdout_metrics` | MAE en vélos/h sur l'arrêt anticipé (juin) ; puis MLP et référence `y(t − 168 h)` sur **les mêmes cellules**. Contrôle technique : un réseau très au-dessus de la référence signale un problème. Ce **n'est pas** la comparaison officielle (validation, scores d'E4) |
| `extreme_targets` | part des exemples dont une cible dépasse 10 fois le niveau de la fenêtre |

### Prévoir un cas

```python
from src.models.known import neural, predict, train

# Plus simple (MOD-011) : predict.predict_24h(case, history, "mlp", context=ctx, model_run_id=...)
# fait tout ci-dessous, avec le repli. Le détail, pour comprendre :
model = predict.load_trained(model_run_id, "mlp")           # charger UNE fois (cache)
inputs = predict.build_inputs(case, history, context)       # passé et contexte connus à l'origine
result = neural.predict_mlp(model.estimator, inputs, fit_cutoff=model.config.fit_cutoff)
if result.ok:
    result.values        # 24 valeurs >= 0 en vélos/h, horizons 1 à 24
else:
    result.reason        # code de refus : le repli sur la référence revient à l'appelant
```

| Code de refus | Cause |
| --- | --- |
| `mlp_origin_not_midnight` | origine hors minuit (Paris) : la sortie k ne serait plus la k-ième heure du jour |
| `mlp_origin_before_fit_cutoff` | origine antérieure à la coupure : le modèle a appris sur cette journée. Le réseau connaît sa coupure (bilan) : refus même sans l'argument |
| `mlp_no_history` | aucune mesure publiée pour ce compteur |
| `mlp_context_missing` | modèle avec contexte, mais contexte absent ou une valeur inconnue à l'origine (jamais remplacée par « 0 °C ») |
| `mlp_window_too_sparse` | moins de 84 h mesurées sur la semaine visible |
| `mlp_level_too_low` | niveau de la fenêtre < 1 vélo/h |
| `mlp_non_finite_output` | sortie non finie (ne devrait jamais arriver) |

Une latence du cas différente de celle de l'apprentissage lève `ValueError` : c'est une erreur de configuration, pas une condition des données. `predict_windows(net, build_windows(...))` fait le même calcul pour beaucoup de cas : un test vérifie que les deux chemins donnent la même chose.

### Prévoir avec `predict_24h` (fait, MOD-011)

```python
from src.models.known import predict

ctx = predict.load_context("hist-20261117")       # contexte E1, lu une fois
result = predict.predict_24h(case, history, "hgb", context=ctx,
                             model_run_id="e2-hgb-ctx-20260701-s0-b357")
```

- Le modèle prévoit : statut `ok`, `method_used` = `mlp` ou `hgb`.
- Il refuse : la référence de sa fiche (`fallback: reference`) prévoit les 24 heures ; statut `fallback`, `status_reason` = code de refus, `method_used` = méthode réellement employée. Une heure sans repli reste vide, jamais 0.
- **Le contexte est obligatoire** : sans `context=`, les deux modèles refusent (`*_context_missing`) et la référence répond.
- Commande pour tous les cas d'un `cases.csv` :

  ```bash
  python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv \
    --snapshot hist-20261117 --experiment <EXP> --variant hgb --model-run-id e2-hgb-ctx-20260701-s0-b357
  ```

  Environ 0,5 s par cas. Refus d'un modèle sans `--model-run-id`, ou avec `--values e1_filled` (D-11).

## Règles à garder

- **Pas de fuite** : la fenêtre finit 24 h avant l'origine ; un test vérifie que modifier le futur ne change rien, à l'apprentissage (poids identiques) comme à la prévision.
- **Vide ≠ 0** : une heure manquante a son masque à 0 ; une prévision absente est vide, jamais 0 ; un contexte inconnu est signalé, jamais pris pour 0.
- **Un seul calcul** : `build_windows` sert à l'apprentissage et à la prévision.
- **Entrées rangées autrement = réentraîner** : `load_mlp` refuse un réseau dont la fenêtre, la latence ou le calendrier ont changé.
- **Origines à minuit (Paris)** pour l'apprentissage comme pour la prévision.
- **Une seule latence** : celle de `config/project*.yaml` ; `train.fit` refuse une autre valeur.
- `build_windows` utilise des fonctions internes de `features.py` (`_calendar_core`, `_prepare_context`, `_context_core`) : prévenir avant de les modifier.

## Points ouverts

- `fit_cutoff` commun au 01/07/2026 et début des données (2023) : à écrire dans `config/project.yaml` (E4).
- Annoncer à E4 et E5 les variantes `mlp` / `hgb`, le contexte obligatoire et les codes de refus (MOD-011).
- Fiches [EXP-E2-03](../experiments/EXP-E2-03.md) (MLP, HGB, références) et [EXP-E2-04](../experiments/EXP-E2-04.md) (avec ou sans contexte) : brouillons à figer **avant** les scores de validation.
- `training_origins` prend environ 70 s sur les données réelles : optimisation possible.

# Prise en main : socle `train.py` et MLP `neural.py`

Pour Ania (HGB) et Esther (entraînement du MLP). Auteur : Idir. Branche `Team2-idir`.

## Ce qui existe

| Fichier | Fonctions | Rôle |
| --- | --- | --- |
| [train.py](../../src/models/known/train.py) | `load_training_data` | lit `counts.csv`, `context.csv`, l'inventaire ; en entrée, **mesures seules** (`count`), valeur E1 gardée dans `count_e1` |
| | `fit` | partie **commune** : compteurs `S_train` (E3 exclus), origines entre `train_start` et `fit_cutoff`, puis appelle la méthode |
| | `save_model` / `load_model` | dossier `artifacts/models/<model_run_id>/` : poids + `metadata.json` ; refus d'écraser, SHA-256 vérifié |
| | `register_backend` | déclare une méthode (comment apprendre, sauver, relire) |
| [neural.py](../../src/models/known/neural.py) | `build_windows` | fabrique les exemples du MLP (un par compteur × origine) |
| | `MLPNet`, `save_mlp`, `load_mlp` | **placeholder** : réseau minimal (2 couches de 128) écrit pour que la sauvegarde fonctionne, architecture à améliorer ; « mlp » déjà déclaré (`fit=None`) |

Tests : `tests/test_known_train.py`, `tests/test_known_neural.py`.

## Démarrer

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu pytest ruff
git lfs pull --include="livraison/hist-20261117.zip" && unzip -o livraison/hist-20261117.zip
.venv/bin/python -m pytest -q
```

## Entraîner un modèle (une méthode qui sait apprendre)

```python
import pandas as pd
from src.models.known import train

data = train.load_training_data("hist-20261117")
config = train.TrainConfig(
    method="hgb",                                    # ou "mlp"
    fit_cutoff=pd.Timestamp("2026-06-30 22:00", tz="UTC"),   # 01/07 minuit à Paris
    train_start=None,                                # None = depuis le début des données (2023)
    use_context=True,
    hyperparameters={...},
    seed=0,
)
model = train.fit(config, data.counts, data.context, data.inventory)
train.save_model(model)                  # artifacts/models/e2-hgb-ctx-20260701-s0-xxxx/
model = train.load_model(model.model_run_id)
```

Le nom du modèle contient une empreinte de la config : changer un réglage change le nom, rien n'est écrasé.

## Ania : brancher le HGB (`tabular.py`)

Une méthode fournit 4 fonctions et se déclare. `train.fit` lui donne **les mêmes origines qu'au MLP** : la comparaison est équitable.

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

## Esther : `fit_mlp` et `predict_mlp` (dans `neural.py`)

`build_windows(counts, origins, context, use_context=...)` renvoie un objet `Windows` :

| Champ | Forme | Contenu |
| --- | --- | --- |
| `X` | (n, 419) ou (n, 344) sans contexte | entrée du réseau |
| `target` | (n, 24) | vraies valeurs / niveau |
| `target_mask` | (n, 24) | `True` = vraie mesure (seules à compter dans la perte) |
| `scale` | (n,) | niveau ; prévision en vélos/h = sortie × `scale` |
| `usable` | (n,) | `False` = fenêtre trop vide → ne pas apprendre dessus, repli en prévision |
| `origin` | (n,) | pour séparer les dernières semaines (arrêt anticipé) |

**`fit_mlp(config, counts, context, origins) -> MLPNet`**
- réglages dans `config.hyperparameters` (`hidden`, `layers`, `dropout`, `lr`, `epochs`…), graine `config.seed` ;
- perte MAE sur les seules cibles `target_mask`, exemples `usable` seulement ;
- arrêt anticipé sur les 4 dernières semaines avant `fit_cutoff`, **jamais** sur juillet-août ;
- cibles extrêmes : environ 0,1 % des exemples dépassent 59 fois le niveau (fenêtres effondrées par des zéros). À plafonner dans la perte, écarter ou traiter par Huber : à décider avant les scores ;
- puis remplacer `fit=None` par `fit=fit_mlp` dans `register_backend` en bas du fichier.

**`predict_mlp(net, inputs, context) -> 24 valeurs ou refus`** : `build_windows` sur le seul cas, `net(X) × scale`, valeurs ≥ 0 ; si `usable` est faux, refuser avec une raison (le repli est géré par `predict.py`).

## Règles à garder

- **Pas de fuite** : la fenêtre finit 24 h avant l'origine ; un test vérifie que modifier le futur ne change rien.
- **Vide ≠ 0** : une heure manquante a son masque à 0 ; une prévision absente est vide, jamais 0.
- **Un seul calcul** : `build_windows` sert à l'apprentissage et à la prévision.
- **Entrées rangées autrement = réentraîner** : `load_mlp` refuse un réseau dont la fenêtre ou le calendrier ont changé.
- `build_windows` utilise des fonctions internes de `features.py` (`_calendar_core`, `_prepare_context`, `_context_core`) : prévenir avant de les modifier.

## Points ouverts

- `fit_cutoff` commun au 01/07/2026 et début des données (2023) : à écrire dans `config/project.yaml` (E4).
- `predict.py` : brancher `variant="model"` (importer `neural.py`, charger une fois, repli sur la référence).
- `training_origins` prend environ 70 s sur les données réelles : optimisation possible.

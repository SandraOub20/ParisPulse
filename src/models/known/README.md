# Sites connus - équipe 2

Prévoir les 24 heures qui suivent une origine (minuit, heure de Paris) pour un compteur déjà présent dans l'apprentissage. Seules les mesures publiées à l'origine sont utilisées : délai de 24 h, et heure manquante ≠ 0. Le suivi complet est dans [E2_SUIVI.md](../../../reports/teams/E2_SUIVI.md), et la prise en main dans [E2_PRISE_EN_MAIN.md](../../../reports/teams/E2_PRISE_EN_MAIN.md).

## Modules

| Fichier | Rôle |
| --- | --- |
| `baseline.py` | Références recalculables : `reference` (même heure, 7 jours avant, puis repli) et `reference_profile` (médiane des 4 dernières semaines) |
| `features.py` | Variables sans information future : calendrier, historique, contexte d'E1 (météo, grèves, vacances) |
| `train.py` | Apprentissage commun jusqu'à la coupure (sites réservés à E3 exclus), sauvegarde et relecture vérifiée des modèles |
| `neural.py` | MLP (expérience de deep learning) : fenêtre d'une semaine normalisée, masque des heures manquantes, masquage à l'apprentissage en option (EXP-E2-05) |
| `tabular.py` | Gradient boosting par histogrammes (HGB), le modèle retenu pour l'application (D-24) |
| `predict.py` | `predict_24h(case, history, variant=...)`, utilisé par E3 et E5 : contrôles d'éligibilité, repli sur la référence, fichiers de résultats |
| `batch.py` | Le même calcul en bloc, pour une expérience entière : les fichiers sont identiques à ceux du calcul cas par cas |
| `score.py` | Score recalculable d'une expérience, avec la fonction d'E4 (`src/eval/metrics.py`) |

Modèles par défaut (`predict.DEFAULT_MODEL_RUN_IDS`) : HGB `e2-hgb-ctx-20260701-s0-b357` et MLP `e2-mlp-ctx-20260701-s0-9ce9`, appris jusqu'au 01/07/2026 et rangés dans `artifacts/models/`.

## Expériences

| Fiche | Question | Prévisions |
| --- | --- | --- |
| [EXP-E2-03](../../../reports/experiments/EXP-E2-03.md) | Quelle méthode pour l'application : MLP, HGB ou référence ? | `data/prediction_results/EXP-E2/` |
| [EXP-E2-04](../../../reports/experiments/EXP-E2-04.md) | Le contexte (météo, grèves, vacances) améliore-t-il la prévision ? | `data/prediction_results/EXP-E2-04/` |
| [EXP-E2-05](../../../reports/experiments/EXP-E2-05.md) | Apprendre avec des fenêtres masquées rend-il le MLP robuste aux pannes ? | `data/prediction_results/EXP-E2-05/<niveau>/` |

Chaque fiche est figée avant le calcul des scores. Les cas viennent d'E4 (`data/evaluation/proto-v1/cases.csv`) : 6 014 cas de validation, soit 97 compteurs sur 62 jours de juillet-août 2026. Le test (octobre-novembre) n'est lu qu'une seule fois, après le gel.

## Refaire les expériences

Prérequis : l'environnement du projet (`doc/ENVIRONNEMENT.md`) et l'instantané `data/processed/hist-20261117/`, préparé par la procédure d'E1. Pour un calcul lourd sur une machine de 8 Go, préfixer la commande par `systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=0`.

1. **Rescorer une expérience, en environ 5 min**. Le score se calcule à partir des prévisions commitées, lues directement dans le zip :

   ```bash
   python -m src.models.known.score --experiment EXP-E2
   ```

   Le résultat redonne les MAE de la fiche, en version « système » (replis compris) et « brut » (modèle seul). Il est écrit dans `scores_known_site_validation.json`.

2. **Recalculer une méthode entière, en 2 à 3 min**, puis la rescorer :

   ```bash
   python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv \
       --snapshot hist-20261117 --experiment EXP-E2-demo --variant hgb --batch
   python -m src.models.known.score --experiment EXP-E2-demo
   ```

3. **Un seul cas, en quelques secondes** : `predict_24h` sur un compteur et une origine au choix. On obtient 24 lignes avec `prediction_status` (`ok` ou `fallback`) et la raison exacte dans `status_reason`. Les notebooks `notebooks/E2_*.ipynb` le montrent avec un graphique.

4. **Réapprendre un modèle**, en option (environ 5 min pour le MLP) :

   ```bash
   python -m src.models.known.neural --snapshot hist-20261117 \
       --fit-cutoff 2026-06-30T22:00:00+00:00 --seed 0 --protocol-id proto-v1 \
       --root tmp/modeles_demo
   ```

   `--root` écrit dans un dossier à part, car un modèle existant n'est jamais écrasé. Les réglages sont ceux de `e2-mlp-ctx-20260701-s0-9ce9`. Seule différence : l'empreinte compte aussi les 4 réglages de masquage ajoutés pour EXP-E2-05, neutres par défaut, si bien que l'identifiant n'est pas le même. Le score de contrôle de juin est très proche de celui du modèle d'origine, sans être identique au bit près d'une machine à l'autre (D-23).

Le bloc test est refusé par `predict` sauf avec `--allow-test`, à n'utiliser qu'une seule fois, après le gel des choix.

## Livraisons

- **À E4** : les `.pred.csv`, `.runs.csv`, `.cases_used.csv` et `.selection.json` de chaque méthode, zippés par expérience.
- **À E5** : `predict_24h` avec les variantes `reference`, `reference_profile`, `hgb` et `mlp`, le contexte (`predict.load_context`), les codes de refus et le repli.
- **À E3** : le MLP et le HGB, avec la liste des sites exclus de leur apprentissage (`excluded_site_groups` dans `metadata.json`).

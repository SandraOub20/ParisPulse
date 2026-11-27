# Équipe 2 - Prévision sur sites connus : document de suivi

> ## ⚠️ À lire avant toute modification de ce fichier
>
> Ce document est la **source de vérité du travail de l'équipe 2** et la matière première du rapport final. Toute personne qui modifie du code, des données, des paramètres ou une décision de l'équipe 2 **doit le mettre à jour dans le même commit**. Pour qu'il reste cohérent :
>
> 1. **Une entrée par modification** dans le [§4 Journal des modifications](#4-journal-des-modifications), ajoutée **en haut** de la liste (la plus récente d'abord). Ne jamais réécrire ni supprimer une entrée passée : pour corriger, ajouter une nouvelle entrée qui renvoie à l'ancienne (`Corrige MOD-xxx`).
> 2. **Identifiant séquentiel** `MOD-NNN` (le suivant du plus grand existant), **date au format ISO** `AAAA-MM-JJ`, **auteur nommé**, branche et commit (Team2).
> 3. **Remplir tous les champs du gabarit d'entrée** (§4) : quoi, pourquoi, fichiers (liens relatifs), impact sur les contrats/partenaires, vérifications réellement effectuées, points ouverts. Écrire `aucun` plutôt que laisser vide.
> 4. **Mettre à jour en même temps** les sections d'état concernées : [§2 État](#2-état-davancement), [§5 Reste à faire](#5-reste-à-faire), [§6 Décisions](#6-décisions-et-points-ouverts), [§7 Expériences](#7-expériences-et-résultats). Cocher une tâche uniquement si elle est **faite et vérifiée**, avec le renvoi `MOD-NNN`.
> 5. **Ne noter que des faits vérifiés.** Un résultat chiffré cite sa source (fichier `.pred.csv`, `scores.csv`, fiche d'expérience). Ne jamais reporter un score mesuré sur le **test final** avant le gel des choix (§6).
> 6. **Français, dates UTC ISO 8601**, noms de fichiers/fonctions entre backticks, liens relatifs depuis ce fichier (`../../src/...`). Pas de chemin personnel (`C:\Users\...`).
> 7. Toute **modification d'interface** (signature, colonnes CSV, statut, nom de méthode) doit être signalée dans le champ *Impact partenaires* et dans le §6, et communiquée à E3/E4/E5 **avant** d'être fusionnée.
> 8. Les journaux individuels restent dans `reports/individual/` ; ce fichier n'en contient qu'une synthèse et un lien.
> 9. **Périmètre E2 uniquement** : ne pas modifier `src/models/new/` (équipe 3) et ne pas y documenter de travail E3. Toute modification d'un fichier partagé (`registry.py`, `schemas.py`) est signalée à E3.

---

## 1. Mission et périmètre

**Question de recherche** (sujet, p. 4 et 6) : comment mieux prévoir les 24 prochaines heures d'un compteur dont on possède déjà un historique ? Quelles données utiliser, quelle méthode retenir, à quel coût ?

| Livrable | Destinataire | Référence |
| --- | --- | --- |
| Référence hebdomadaire recalculable + repli | E4, E5 | [baseline.py](../../src/models/known/baseline.py) |
| Variables causales partagées | E1, E3 | [features.py](../../src/models/known/features.py) |
| Modèle(s) entraîné(s) et comparaison de variantes (dont ablation d'information) | E4 | [train.py](../../src/models/known/train.py) |
| Calcul exécutable `predict_24h` + exports `.pred.csv` / `.runs.csv` | E4, E5 | [predict.py](../../src/models/known/predict.py) |
| Fiches méthode (historique minimal, repli, conditions) | E5 | [registry.py](../../src/models/registry.py) |
| Provenance prouvant l'exclusion des sites réservés (si modèle partagé) | E3 | `artifacts/models/<model_run_id>/metadata.json` |
| Contribution à l'expérience deep learning collective | Collectif | responsabilité à attribuer (§6) |

Documents de référence : [sujet](../../ParisPulse_Sujet_etudiants.pdf), [architecture](../../doc/ARCHITECTURE.md), [contrats](../../doc/CONTRATS.md), [protocole](../../doc/PROTOCOLE_EVALUATION.md), [README E2](../../src/models/known/README.md), [gabarits](../../doc/templates/README.md).

**Hors périmètre** : `src/models/new/` appartient à l'équipe 3 et n'est ni modifié ni suivi ici. Les fichiers partagés (`src/models/registry.py`, `src/models/schemas.py`) sont modifiés en concertation avec E3.

**Membres** : _tout le monde_.

---

## 2. État d'avancement

_Dernière mise à jour : 2026-11-27 - MOD-020._

| Étape (README E2) | État | Renvoi |
| --- | --- | --- |
| 0. Revue de cohérence, squelette `src/models` | ✅ Fait ; incohérences closes ou gardées comme limites (§10) | MOD-001, MOD-002 |
| 1. Série réelle E1 + cas d'E4 | ✅ `hist-20261117` d'E1, cas `proto-v1` d'E4 (protocole non validé par le professeur) | MOD-005, MOD-007 |
| 2. Références et repli (`baseline.py`) | ✅ `reference` et `reference_profile`, repli N = 4 (D-03) | MOD-003, MOD-004 |
| 3. Vérification manuelle + raccord E4/E5 | ✅ Valeurs vérifiées à la main ; prévisions notées par E4 (scores identiques aux nôtres) ; `predict_24h` utilisé par E3 et E5 | MOD-003, MOD-005, MOD-018 |
| 4. Variables communes (`features.py`) | ✅ `f1.0`, sans fuite, utilisées par le HGB et le MLP | MOD-006 |
| 5. Méthode justifiée + variante explicative | ✅ MLP et HGB appris et comparés ([EXP-E2-03](../experiments/EXP-E2-03.md), HGB retenu) ; ablation du contexte ([EXP-E2-04](../experiments/EXP-E2-04.md)) ; robustesse du MLP ([EXP-E2-05](../experiments/EXP-E2-05.md)) | MOD-007 à MOD-019 |
| 6. Calcul exécutable et exports (`predict.py`, `batch.py`, `score.py`) | ✅ Cas par cas (application) et en bloc (expériences), mêmes fichiers ; score recalculable ; notebooks de présentation | MOD-011, MOD-014, MOD-017 à MOD-019 |
| 7. Cas difficile, test final après gel | 🟡 Cas difficiles étudiés (pannes, EXP-E2-05 ; décalage de 2 h dans les données d'E1) ; test final après le gel D-07 | MOD-019 |

Légende : ✅ fait et vérifié · 🟡 en cours · ⏳ bloqué/en attente · 🔲 non commencé.

---

## 3. Architecture du code E2 (état actuel)

```text
src/models/
  schemas.py        Case, ForecastInputs, ForecastResult, RunCost, colonnes CSV,
                    target_timestamps() [implémenté], assert_causal()
                    -> PROPOSITION à migrer vers src/common/contracts.py
  registry.py       ForecastMethod (Protocol), MethodSpec, register/get_method/
                    list_methods/check_eligibility/select_method
  known/
    baseline.py     weekly_reference, lookup_lagged, fallback_value, prophet_reference (optionnel)
    features.py     f1.0 : calendar_features (horizon, heure/jour/week-end/mois locaux),
                    history_features (lags 168/336 h, profil 4 semaines, niveaux, tendance,
                    manques, zéros), context_features par groupes (calendar, strikes,
                    weather_forecast : seule partie retirée par l'ablation),
                    build_feature_frame (un cas), build_training_frame (en bloc, même calcul),
                    training_origins, training_counters
    train.py        TrainConfig (train_start, fit_cutoff…), TrainedModel, registre des méthodes
                    (MethodBackend, register_backend, get_backend), load_training_data,
                    exclude_reserved_sites, fit (partie commune), save_model/load_model,
                    make_model_run_id ; compare_variants à faire
    neural.py       MLP : build_windows (entrées/cibles, même calcul apprentissage et prévision,
                    contexte manquant signalé), MLPNet, mlp_hyperparameters, fit_mlp (perte L1
                    masquée pondérée par le niveau, arrêt anticipé), predict_mlp / predict_windows /
                    refusal_reasons (24 valeurs ou refus motivé), save_mlp/load_mlp (format 2),
                    commande python -m src.models.known.neural
    tabular.py      HGB : hgb_hyperparameters, fit_hgb (variables f1.0, arrêt anticipé sur le
                    nombre d'arbres), predict_hgb / predict_frame / refusal_reason (codes hgb_*),
                    save_hgb/load_hgb, commande python -m src.models.known.tabular (MOD-010)
    predict.py      build_inputs, load_context, predict_24h (signature imposée ; variantes
                    reference, reference_profile, mlp, hgb ; modèles par défaut D-24),
                    load_trained (un chargement par modèle), eligibility_reason,
                    trained_forecast (modèle ou repli tracé, seule implémentation),
                    run_experiment, write_predictions, write_runs, commande (MOD-011, MOD-014)
```

Flux prévu d'un cas :

```text
cases.csv (E4) --Case.from_row--> Case
counts.csv (E1) --build_inputs (available_at <= origin)--> ForecastInputs --assert_causal
  --> predict_24h(case, history, variant, context=...)
        variant="reference"   -> baseline.weekly_reference (+ fallback_value)
        variant="mlp" / "hgb" -> load_trained(model_run_id) -> trained_forecast :
                                 predict_mlp / predict_hgb, ou refus (mlp_*, hgb_*) et
                                 repli sur la référence, statut fallback (MOD-011)
  --> ForecastResult --to_forecast_frame / to_run_row--> <method_run_id>.pred.csv / .runs.csv
```

Fonctions réellement implémentées à ce jour (MOD-003 à MOD-005) : `target_timestamps()`, `Case.from_row`, `assert_causal` ; dans `baseline.py`, `weekly_reference`, `weekly_profile_reference` (MOD-004), `admissible_history`, `lookup_lagged`, `fallback_value` ; dans `schemas.py`, `ForecastResult.is_complete`, `to_forecast_frame`, `to_run_row` ; dans `predict.py`, `counts_history_loader`, `build_inputs`, `predict_24h` (variantes `reference`, `reference_profile`, puis `mlp` et `hgb` en MOD-011), `load_trained`, `trained_forecast`, `load_context` (MOD-011), `run_experiment`, `error_result`, `select_cases`, `train_site_counters`, `write_predictions`, `write_runs` et la commande `main` ; tout `features.py` (MOD-006) ; dans `train.py`, tout sauf `compare_variants`, et dans `neural.py`, `build_windows`, `MLPNet`, `save_mlp`, `load_mlp` (MOD-007), puis tout le reste de `neural.py` : `mlp_hyperparameters`, `fit_mlp`, `predict_mlp`, `predict_windows`, `refusal_reasons` et la commande `main` (MOD-008). Toutes les autres lèvent `NotImplementedError("E2 : ...")`. Tests : [tests/test_known_baseline.py](../../tests/test_known_baseline.py), [tests/test_known_predict.py](../../tests/test_known_predict.py), [tests/test_known_features.py](../../tests/test_known_features.py), [tests/test_known_train.py](../../tests/test_known_train.py), [tests/test_known_neural.py](../../tests/test_known_neural.py), [tests/test_known_neural_fit.py](../../tests/test_known_neural_fit.py), [tests/test_known_predict_trained.py](../../tests/test_known_predict_trained.py).

---

## 4. Journal des modifications

### Gabarit d'entrée (copier en haut de la liste)

```markdown
### MOD-NNN - AAAA-MM-JJ - Titre court
- **Auteur** :
- **Branche / commit** :
- **Quoi** : description précise de la modification.
- **Pourquoi** : motivation, lien avec le sujet, les contrats ou un retour partenaire.
- **Fichiers** : liens relatifs.
- **Impact partenaires / contrats** : signatures, colonnes, statuts modifiés ; équipes prévenues.
- **Vérifications effectuées** : commandes lancées, résultats observés (ou "aucune").
- **Points ouverts** : ce qui reste incertain ou à valider.
```

### MOD-020 - 2026-11-27 - Notebooks de présentation (`demo.py`), score par compteur et par groupe ; suivi remis à jour

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` (commit indiqué dans l'historique de ce fichier).
- **Quoi** :
  - [demo.py](../../src/models/known/demo.py) : `find_case`, `forecast_case` (par `predict_24h`), `case_view`, `plot_case`, `rainy_days` et `observed_hours_band`. Ce sont les seules fonctions appelées par les notebooks, en plus de `predict` et `score`.
  - [score.py](../../src/models/known/score.py) :
    - `score_detail` donne aussi la MAE par compteur ; la commande l'écrit dans `*_by_counter.csv` ;
    - `score_by_group` refait le score sur des groupes de cas (type de jour, tranche d'heures mesurées) ;
    - l'option `--also` lit plusieurs dossiers d'expérience.
  - Notebooks `notebooks/E2_EXP-03_choix_methode.ipynb`, `E2_EXP-04_contexte.ipynb` et `E2_EXP-05_masquage.ipynb` : un cas en direct, les scores, la règle appliquée et les cas d'échec.
  - `baseline.MIN_HISTORY_HOURS`, une constante inutilisée, est retiré (I4).
  - Suivi : §2, §5, §6 (décisions closes), §8 et §10 (incohérences closes ou gardées comme limites).
- **Pourquoi** : présenter les expériences et pouvoir les refaire devant le professeur, sans logique cachée dans les notebooks.
- **Vérifications effectuées** :
  - tests de `demo.py` et `score.py` (petits exemples calculés à la main) ;
  - notebook 03 exécuté du début à la fin : il retrouve les scores d'E4 et la décision HGB.
- **Constat en passant** : un décalage de 2 h dans les mesures d'E1, sur 4 jours de juillet (§8).

### MOD-019 - 2026-11-27 - Dégradation de la semaine visible pour EXP-E2-05 (`batch.py`, `--degrade`)

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` (commit indiqué dans l'historique de ce fichier).
- **Quoi** :
  - [batch.py](../../src/models/known/batch.py) :
    - `erased_positions`, `visible_week`, `erased_hours` : les heures effacées par niveau (`d0`, `panne-48/96/144`, `trous-50`) ;
    - `degrade_history` : passe les heures effacées à « non mesurée » (vide, jamais 0) ;
    - `batch_raw_mlp(..., degrade=)` : chaque cas reçoit sa propre semaine effacée (`_degraded_weeks`) ;
    - `run_experiment_batch(..., degrade=)` : le repli et les références voient la même semaine effacée que le modèle.
  - [predict.py](../../src/models/known/predict.py) : l'option `--degrade` (avec `--batch`) ajoute le niveau en suffixe au `method_run_id`.
- **Pourquoi** : la population 2 d'[EXP-E2-05](../experiments/EXP-E2-05.md), figée le 2026-11-24, précisée au point 8 avant tout score.
- **Fichiers** : [batch.py](../../src/models/known/batch.py), [predict.py](../../src/models/known/predict.py), [test_known_batch.py](../../tests/test_known_batch.py), [EXP-E2-05](../experiments/EXP-E2-05.md).
- **Impact partenaires / contrats** : aucun. Sans `--degrade`, rien ne change.
- **Vérifications effectuées** : 13 tests ajoutés.
  - Positions par niveau : la même graine donne les mêmes trous, et les trous diffèrent d'un cas à l'autre.
  - `degrade_history` : aucun 0 inventé, cibles intactes, original non modifié.
  - `d0` en bloc est identique au calcul sans dégradation.
  - En bloc, le résultat est identique à `predict_mlp` cas par cas sur l'historique effacé (seuils 84 et 24).
  - Le repli du MLP est égal à la référence sur la même semaine effacée.
  - La commande `--degrade` est testée.

### MOD-018 - 2026-11-27 - Score recalculable (`score.py`), nettoyage avant remise

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` (commit indiqué dans l'historique de ce fichier).
- **Quoi** :
  - [score.py](../../src/models/known/score.py) : le score d'une expérience refait le calcul de `make_common_scores` d'E4 avec leurs fonctions de `src/eval/metrics.py`, sans les recopier. Il donne deux lectures, « système » et « brut », et lit les `.pred.csv` d'un dossier, ou directement le zip livré. Commande : `python -m src.models.known.score --experiment EXP-E2`. Il remplace le script hors Git du score provisoire de 03.
  - Chemins personnels retirés :
    - `model_dir` est relatif au dépôt (`train.repo_relative`) dans les bilans d'apprentissage ;
    - les 11 `training_report.json` commités sont corrigés (ils ne sont pas lus au chargement des modèles).
  - Code mort retiré :
    - `train.compare_variants` : les comparaisons passent par les fiches, `batch.py` et `score.py` ;
    - `baseline.prophet_reference` : Prophet est abandonné (D-04, D-10, C5).
  - En-têtes de `baseline.py`, `predict.py` et `train.py` réécrits, puisque les « À faire » du gabarit sont faits. [README du dossier](../../src/models/known/README.md) réécrit : modules, expériences, « Refaire les expériences ».
  - `write_predictions` : le `FutureWarning` de pandas sur les cas en erreur est corrigé (colonnes en objet avant la concaténation).
- **Pourquoi** : remise. La checklist exige « sans chemin personnel » et un calcul recalculable par un tiers (SUIVI_ET_REMISE §2 et §6).
- **Fichiers** : [score.py](../../src/models/known/score.py), [test_known_score.py](../../tests/test_known_score.py), [train.py](../../src/models/known/train.py), [neural.py](../../src/models/known/neural.py), [tabular.py](../../src/models/known/tabular.py), [baseline.py](../../src/models/known/baseline.py), [predict.py](../../src/models/known/predict.py), [README](../../src/models/known/README.md), `artifacts/models/*/training_report.json`.
- **Impact partenaires / contrats** : aucun. Les fonctions retirées n'étaient appelées nulle part (`git grep`) et levaient `NotImplementedError`.
- **Vérifications effectuées** :
  - `score.py` sur EXP-E2-03 redonne **exactement** les scores officiels d'E4 (`data/evaluation/proto-v1/EXP-E2/scores.csv`, ligne `common_complete`) : MAE, RMSE, biais, 5 613 cas, 95 compteurs ;
  - 5 tests calculés à la main : MAE macro, biais, lecture brute, lecture du zip, vide ≠ 0 ;
  - `git grep "/home/"` sur `artifacts/`, `src/`, `reports/` et `tests/` : aucun résultat ;
  - `pytest -q` : 425 tests passent. Le seul test écarté est celui d'E3 qui échoue aussi sur `dev`.

### MOD-017 - 2026-11-24 - Calcul en bloc des prévisions (`batch.py`) ; prévisions d'EXP-E2-03 et score provisoire

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` / `3e96363`, `638d7e9`, `89a76af`, `f3fa188`, `e6df090`.
- **Quoi** :
  - [predict.py](../../src/models/known/predict.py) :
    - `_assemble_result` : le seul code qui écrit statuts, repli et provenance, partagé par le cas par cas et le calcul en bloc ;
    - option `--batch` de la commande.
  - [batch.py](../../src/models/known/batch.py) :
    - `batch_raw_mlp` (`build_windows` / `predict_windows`) et `batch_raw_hgb` (`features._assemble` sans étiquette, puis `predict_frame`) : mêmes contrôles, dans le même ordre, que `predict_mlp` et `predict_hgb` ;
    - `run_experiment_batch` : mêmes paramètres et mêmes fichiers que `run_experiment`, seul le coût diffère.
  - Correctif mémoire : l'historique n'est plus recopié pour chaque cas ni retenu par une vue (`iloc[0:0]`). Le premier essai avait saturé la mémoire de la machine (7 Go). Les calculs suivants ont tourné sous une limite de 3 Go (`systemd-run --user --scope -p MemoryMax=3G`).
  - Prévisions d'EXP-E2-03 : 6 fichiers dans `data/prediction_results/EXP-E2/` (là où les lit `src/eval/backtest.py` d'E4) : `reference`, `reference_profile`, `hgb` (`b357`), `mlp` graines 0, 1, 2.
- **Pourquoi** : le cas par cas coûte environ 0,4 s par cas, soit environ 45 min par modèle ; EXP-E2-03 à 05 demandent des dizaines de passages.
- **Fichiers** : [predict.py](../../src/models/known/predict.py), [batch.py](../../src/models/known/batch.py), [test_known_batch.py](../../tests/test_known_batch.py), [EXP-E2-03](../experiments/EXP-E2-03.md), ce fichier.
- **Impact partenaires / contrats** :
  - Aucun pour E3 et E5 : ils appellent toujours `predict_24h`, inchangé.
  - Pour E4 : les fichiers ont le format du gabarit, une méthode par fichier, et leur `check_forecasts.py` passe sans erreur. `fit_cutoff` est vide pour les références (elles n'apprennent rien).
  - Le coût écrit dans `.runs.csv` en bloc est une part du temps total, pas le coût d'un calcul isolé dans l'application.
- **Vérifications effectuées** :
  - 17 tests ([test_known_batch.py](../../tests/test_known_batch.py)) :
    - sortie brute identique au cas par cas (MLP à 1e-3 près, arrondi float32 ; HGB à 1e-9), avec et sans contexte, avec le seuil remplacé ;
    - fichiers `.pred.csv` / `.runs.csv` identiques hors coût ;
    - commande `--batch` ;
    - garde-fou mémoire.
  - Vrais cas :
    - 205 cas comparés au cas par cas : mêmes refus, écart maximal 0,0003 vélo/h (MLP) et 0 (HGB) ;
    - les 6 014 cas en 2 à 3 min par modèle ;
    - pic de mémoire 1,4 Go.
  - `check_forecasts.py` (E4) sur les 6 fichiers : tout conforme.
  - `pytest -q` : tous les tests E2 passent. Le seul échec reste le test E3, qui échoue aussi sur `dev`.
- **Résultat** (provisoire, code de score d'E4, calculé par E2) : MAE macro système HGB 22,25, MLP 22,23 / 22,35 / 22,59, `reference_profile` 27,01, `reference` 29,75. Selon la règle figée (D-26), les deux modèles passent (environ +17 %) et le **HGB est retenu** (écart MLP − HGB plus petit que l'écart entre graines). Détail dans la fiche.
- **Points ouverts** :
  - livraison à E4 décidée (option A) : un zip de 12,9 Mo commité normalement, `data/prediction_results/EXP-E2/EXP-E2-predictions.zip` (SHA-256 `1619c830917864569a4dcb0bdef9ad24a4659e04f08b23a48abfdc58c483ed88`). Pas de LFS : il aurait fallu modifier `.gitattributes`, un fichier commun, et les 235 Mo risquaient d'épuiser le quota LFS du dépôt. Décompression vérifiée : 18 fichiers identiques. Reste à obtenir `scores.csv` d'E4 ;
  - prévenir E5 du modèle retenu une fois le score confirmé.

### MOD-016 - 2026-11-24 - Seuil d'heures mesurées et masquage des fenêtres pour le MLP ; modèles B d'EXP-E2-05

- **Auteur** : Idir. `fit_mlp` est la fonction d'Esther (MOD-008) : elle est prévenue de la modification, désactivée par défaut.
- **Branche / commit** : `Team2-idir` / `08026ae` (gel de la fiche), `d7c748d` (code).
- **Quoi** ([neural.py](../../src/models/known/neural.py), [predict.py](../../src/models/known/predict.py)) :
  - nouveaux réglages, neutres par défaut : `min_observed_hours=84`, `mask_prob=0.0`, `mask_min_hours=24`, `mask_max_hours=144`, contrôlés dans `mlp_hyperparameters` ;
  - `build_windows(..., min_observed_hours)` : le seuil est rangé dans `Windows`, et `refusal_reasons` applique le même ;
  - `mask_windows` : efface un bloc continu (masque 0, jamais une valeur 0), recalcule le niveau sur les heures restantes et renormalise série et cibles. Les cibles réelles sont intactes. Une ligne qui deviendrait inutilisable n'est pas masquée ;
  - `fit_mlp` : masquage tiré à chaque époque, sur les lignes d'apprentissage seulement, avec un générateur séparé. Le holdout n'est jamais masqué. Bilan `masking` dans `training_report` ;
  - `predict_mlp(..., min_observed_hours)` : seuil appris par le réseau (84 pour un réseau d'avant), remplaçable (bras A′). Transmis par `predict_24h`, `trained_forecast` et la commande (`--min-observed-hours`), pour le MLP seulement.
- **Modèles appris** (`hist-20261117`, coupure au 01/07/2026, `min_observed_hours=24`) : B à `mask_prob=0.10`, `e2-mlp-ctx-20260701-s0-37f5`, `s1-bd12`, `s2-f26e` (retenus) ; B à `mask_prob=0.25`, `s0-a3b2`, `s1-02bb`, `s2-5238` (écartés par le contrôle sur juin, gardés pour la transparence).
- **Contrôle sur juin** (règle écrite au gel) : à 0,25, B fait 18,07 contre 17,68 pour A (écart 0,39, plus que l'étendue 0,29 entre graines de A) ; passage à 0,10 : B fait 17,32. Contrôle seulement : juin sert à l'arrêt anticipé. Détail dans la fiche.
- **Pourquoi** : EXP-E2-05, approfondissement « historique incomplet » (sujet) et fiabilité (PROTOCOLE §7).
- **Fichiers** : [neural.py](../../src/models/known/neural.py), [predict.py](../../src/models/known/predict.py), [test_known_neural_mask.py](../../tests/test_known_neural_mask.py), [test_known_predict_trained.py](../../tests/test_known_predict_trained.py), [EXP-E2-05](../experiments/EXP-E2-05.md), ce fichier.
- **Impact partenaires / contrats** : aucun changement pour les modèles existants : réglages neutres, et `predict_mlp` sans argument se comporte comme avant. Nouvel argument facultatif `min_observed_hours` dans `predict_24h` et `predict_mlp`.
- **Vérifications effectuées** :
  - 19 tests ajoutés. Les points couverts :
    - un bloc continu par ligne ;
    - aucune valeur 0 inventée, cibles intactes ;
    - original non modifié ;
    - même graine = mêmes masques et mêmes poids ;
    - désactivé = poids identiques ;
    - holdout jamais masqué ;
    - seuil 84 qui limite les blocs, seuil 24 qui sert une fenêtre de 24 h ;
    - seuil refusé hors MLP.
  - `pytest -q` : tous les tests E2 passent (le seul échec reste le test E3 qui échoue sur `dev`). `ruff check` sans problème sur les fichiers E2.
  - Sur 23 vrais cas de validation (cibles non lues), le MLP `9ce9` donne exactement les mêmes prévisions et refus avec l'ancien et le nouveau code.
- **Points ouverts** :
  - prévisions et scores d'EXP-E2-05 après le gel d'EXP-E2-03 ;
  - les 3 modèles B à 0,25 peuvent être supprimés une fois la fiche close.

### MOD-015 - 2026-11-24 - Brouillon de la fiche EXP-E2-05 (MLP appris avec fenêtres masquées)

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` / commit de ce brouillon.
- **Quoi** : brouillon de [EXP-E2-05](../experiments/EXP-E2-05.md), **non figé**, résultats vides, aucun code écrit.
  - Question : un MLP appris en voyant des fenêtres trouées prévoit-il mieux les historiques incomplets, sans perdre sur les semaines complètes ?
  - Bras : A (MLP actuel, seuil 84 h), A′ (mêmes poids, seuil 24 h), B (MLP masqué, seuil 24 h, 3 graines), R (`reference_profile`). A′ contre B isole le masquage.
  - Populations : validation naturelle découpée par heures mesurées, et validation dégradée artificiellement (pannes de 48, 96 et 144 h, 50 % de trous), mêmes cibles (PROTOCOLE §7).
  - Masquage proposé : probabilité 0,5, un bloc contigu de 24 à 144 h, holdout jamais masqué.
  - Règle de décision fixée d'avance : B remplace A seulement s'il ne perd pas sur les semaines complètes et gagne nettement sur les pannes.
- **Pourquoi** : approfondissement E2 « historique incomplet » (sujet) et étude de fiabilité (PROTOCOLE §7) ; comparaison individuelle d'Idir.
- **Fichiers** : [EXP-E2-05.md](../experiments/EXP-E2-05.md), ce fichier.
- **Impact partenaires / contrats** : aucun pour l'instant. Le code prévu (`min_observed_hours`, `mask_windows`, masquage dans `fit_mlp`) gardera 84 h par défaut : les modèles existants ne changent pas.
- **Vérifications effectuées** : aucune mesure ; cohérence vérifiée avec PROTOCOLE §6 et §7, D-18, D-23 et EXP-E2-03.
- **Points ouverts** : les 6 points à trancher en fin de fiche, dont le masquage dans `fit_mlp` avec Esther.

### MOD-014 - 2026-11-24 - Reconstruction de `Team2` après le retour arrière de `dev` ; contrôles d'éligibilité et modèles par défaut dans `predict.py`

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` / `8a7c017` (fusion du `dev` propre), `a9a6340` (code).
- **Contexte** :
  - Le commit d'E5 `fdc06c1` (« Refactor E3 model predictions and adaptations ») a été retiré de `dev` par l'équipe, qui est revenue sur `31252da`.
  - Une première version de MOD-014 (`fe2903b`, puis `origin/Team2` en `09d9891`) avait fusionné ce commit et réconcilié notre branchement avec son fichier `src/models/known/mlp_forecast.py`.
  - Cette version est abandonnée. `Team2` est reconstruite à partir de MOD-013 (`ea076f6`), sans `fdc06c1` (vérifié), fusionnée avec le `dev` propre (`8e46f63`, qui contient `31252da`). L'ancienne version est gardée dans la branche locale `sauvegarde/Team2-idir-09d9891`.
- **Quoi** ([predict.py](../../src/models/known/predict.py), dans notre seul dossier, D-25) :
  - `eligibility_reason` : contrôles avant prévision pour le MLP et le HGB : instantané, origine avant la coupure, site connu absent de l'apprentissage, nouveau site non confirmé réservé, version du contexte. Codes `mlp_*` / `hgb_*` : `_snapshot_incompatible`, `_origin_before_fit_cutoff`, `_site_not_in_training`, `_site_not_confirmed_reserved`, `_context_missing`, `_context_incompatible`, `_inputs_incompatible`. L'idée de ces contrôles vient d'E5 (Sandra) ; ils sont réécrits ici.
  - `trained_forecast` : `status_reason` contient exactement le code de refus, pour le cas et pour chaque horizon. L'étiquette `variant` est séparée de la méthode (E3 peut passer `"frozen"`).
  - `DEFAULT_MODEL_RUN_IDS` : modèle servi quand `model_run_id` n'est pas donné (D-24). `SUPPORTED_VARIANTS`, `MLP_VARIANT`, `HGB_VARIANT` exposés. Option `--context` de la commande.
  - Tests ([test_known_predict_trained.py](../../tests/test_known_predict_trained.py)) adaptés aux contrôles, plus 9 cas d'éligibilité.
- **Pourquoi** : `Team2` ne doit pas réintroduire dans `dev` le commit retiré ; nouvelle règle de propriété des dossiers (D-25).
- **Fichiers** : [predict.py](../../src/models/known/predict.py), [test_known_predict_trained.py](../../tests/test_known_predict_trained.py), ce fichier, [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md), [EXP-E2-05](../experiments/EXP-E2-05.md) (repris tel quel).
- **Impact partenaires / contrats** :
  - Tout ce qu'E3 et E5 importent de notre dossier existe, inchangé : `predict_24h`, `default_publication_lag`, `write_predictions`, `write_runs`, `baseline.admissible_history`, `baseline.weekly_reference`, `neural.predict_mlp`, `train.load_model`.
  - `mlp` et `hgb` sont disponibles sans `model_run_id`. Pour les proposer, l'application doit passer `context=predict.load_context(snapshot)`.
  - `Team2` est réécrite : Esther et Ania (prévenues) doivent se resynchroniser.
- **Vérifications effectuées** :
  - `fdc06c1` n'est pas un ancêtre de la branche ; fusion à blanc avec `dev` sans conflit.
  - `pytest -q` : tous les tests E2 passent. Un seul échec, `test_new_predict.py::test_unimplemented_model_variants_load_then_raise[team2-adapted]` (E3) : il échoue **aussi sur `dev` seul**, sans notre code. À signaler à E3.
  - `ruff check` sans problème sur les fichiers E2.
- **Points ouverts** : D-24 à confirmer après EXP-E2-03 ; signaler à E3 le test en échec et `_core.py` (chargement sans import de `neural`).

### MOD-013 - 2026-11-24 - Graines du MLP, modèles sans contexte, contrôle de reproductibilité ; mise à jour des documents E2

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` / `ea076f6`.
- **Quoi** :
  - Modèles appris (code de MOD-008 et MOD-010, inchangé ; `hist-20261117`, coupure au 01/07/2026, réglages par défaut sauf mention) :

    | Modèle | Rôle | Arbres / époque retenus | MAE macro de contrôle (juin) |
    | --- | --- | --- | --- |
    | `e2-mlp-ctx-20260701-s1-9318` | MLP, graine 1 (EXP-E2-03, variabilité) | époque 24 / 32 | 17,60 |
    | `e2-mlp-ctx-20260701-s2-6278` | MLP, graine 2 (EXP-E2-03, variabilité) | époque 24 / 32 | 17,86 |
    | `e2-mlp-noctx-20260701-s0-5114` | MLP sans contexte (EXP-E2-04) | époque 8 / 16 | 19,22 |
    | `e2-hgb-noctx-20260701-s0-0af3` | HGB sans contexte, `max_iter=2000` (EXP-E2-04) | 679 arbres | 18,76 |
    | `e2-hgb-ctx-20260701-s0-8b7a` | HGB avec contexte, `max_iter=2000` (contrôle) | 342 arbres, prévisions identiques à `b357` | 17,86 |
    | `e2-hgb-noctx-20260701-s0-409c` | HGB sans contexte, plafond 500 atteint | 499 / 500 arbres, **écarté** | 18,83 |

    Rappel : `e2-mlp-ctx-20260701-s0-9ce9` (graine 0, Esther) 17,51 ; `e2-hgb-ctx-20260701-s0-b357` (Ania) 17,86. La MAE de contrôle porte sur juin, mois qui sert à l'arrêt anticipé : ce n'est ni un score E4 ni une comparaison.
  - **Contrôle de reproductibilité** : MLP graine 0 réappris sans sauvegarde, code identique à `f07599a`, mêmes exemples. Résultat différent (époque 17 au lieu de 20, MAE 17,57 au lieu de 17,51), dû à la machine (4 cœurs et 2 threads torch, contre 8 et 4). Écart machine (0,06) bien plus petit que l'écart entre graines (étendue 0,29 sur la même machine).
  - Documents mis à jour : [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md) (HGB, branchement MOD-011, règle de la graine, commande de prévision), §3 de ce fichier (`tabular.py`, `predict.py`, flux), §7 (EXP-E2-04), fiches [EXP-E2-03](../experiments/EXP-E2-03.md) et [EXP-E2-04](../experiments/EXP-E2-04.md) (brouillon).
- **Pourquoi** : graines pour la règle de choix d'EXP-E2-03 ; modèles sans contexte pour l'ablation demandée par le sujet (EXP-E2-04) ; plafond d'arbres relevé pour que l'arrêt anticipé décide seul.
- **Fichiers** : `artifacts/models/` (4 dossiers commités : `s1-9318`, `s2-6278`, `noctx-…-5114`, `noctx-…-0af3` ; `409c` et `8b7a` gardés en local, non commités), fiches EXP-E2-03 et EXP-E2-04, [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md), ce fichier.
- **Impact partenaires / contrats** : aucun (pas de code modifié). Les modèles sont commités comme ceux de MOD-008 et MOD-010 : les réapprendre ailleurs ne redonnerait pas exactement les mêmes poids (D-23).
- **Vérifications effectuées** : les 6 modèles se rechargent (`load_trained`, SHA-256) ; `8b7a` et `b357` donnent les mêmes prévisions sur 15 cas de validation tirés au hasard (cibles non lues) ; aucune donnée de juillet-août lue pour apprendre.
- **Points ouverts** : `max_iter=2000` à confirmer par Ania ; `409c` et `8b7a` à supprimer une fois ce choix confirmé ; D-23 ci-dessous à confirmer par l'équipe.

### MOD-012 - 2026-11-24 - Brouillon de la fiche EXP-E2-03 (MLP, HGB, références)

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` / `43739f9` (brouillon), `f9b2b12` (calcul du score par E4).
- **Quoi** : brouillon de [EXP-E2-03](../experiments/EXP-E2-03.md), **non figé**, résultats vides.
  - Un seul facteur : la méthode (`reference`, `reference_profile`, `mlp`, `hgb`), avec contexte. L'ablation du contexte, la loss du HGB et le masquage du MLP auront leur propre fiche.
  - Population fixée d'avance : les 6 014 cas `known_site` de validation de `proto-v1`. Le test n'est pas lu.
  - Deux évaluations : modèles bruts sur l'intersection commune des cas complets ; système (modèle + repli) sur les 6 014 cas. MAE macro, même masque `is_scoreable`.
  - Règle de choix proposée : un modèle est retenu s'il fait au moins 5 % de mieux que la meilleure référence ; entre MLP et HGB, l'écart doit dépasser l'étendue entre 3 graines du MLP, sinon HGB ; MLP en graine 0, déclarée d'avance.
- **Pourquoi** : figer la comparaison avant les scores (sujet, E2 « choisissez les variables et les réglages avant de mesurer » ; PROTOCOLE §6 et §8).
- **Fichiers** : [EXP-E2-03.md](../experiments/EXP-E2-03.md), ce fichier.
- **Impact partenaires / contrats** : aucun code modifié. À E4 : population, masque, intersection commune. À E5 : `model_run_id` choisi selon la règle.
- **Vérifications effectuées** : aucune mesure ; relecture de la cohérence avec PROTOCOLE §3, §6 et §8, et avec D-11, D-17 à D-22.
- **Points ouverts** (à trancher avant le gel) : règle de choix et seuil de 5 % ; réglages du HGB (`categorical`, `refit_on_holdout`, loss avec E4) ; graines 1 et 2 du MLP ; capacité d'E4 à calculer l'intersection commune ; réapprentissage au 01/08 (proposé : non).

### MOD-011 - 2026-11-24 - Branchement des variantes `mlp` et `hgb` dans `predict.py`, avec repli sur la référence

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` / `d07d759`.
- **Quoi** :
  - [predict.py](../../src/models/known/predict.py) :
    - `load_trained(model_run_id, variant)` charge une seule fois un modèle par `train.load_model`. La méthode est lue dans `metadata.json` avant tout import : un identifiant de MLP demandé en `hgb` est refusé sans charger torch.
    - `trained_forecast(inputs, variant, model)` : le modèle prévoit (statut `ok`, `method_used` = `mlp`/`hgb`), ou il refuse et la référence de sa fiche (`fallback: reference`) prévoit les 24 horizons. Statut `fallback`, raison = code de refus (`mlp_*`, `hgb_*`), `method_used` = méthode réellement employée. Un horizon sans repli reste vide (`unavailable`), jamais 0. `model_run_id`, `fit_cutoff` et `feature_version` sont tracés dans les deux cas.
    - `predict_24h` sert `mlp` et `hgb` avec `model_run_id=` obligatoire ; signature imposée par E5 inchangée, `reference` et `reference_profile` inchangées.
    - `load_context(snapshot_id)` lit `context.csv` en texte, comme `train.load_training_data`.
    - `run_experiment(..., model_run_id=)` et la commande : `--variant mlp|hgb --model-run-id ...`, contexte E1 chargé pour les modèles. Refus : modèle sans `--model-run-id`, modèle avec `--values e1_filled` (D-11), `--model-run-id` pour une référence.
  - [tests/test_known_predict_trained.py](../../tests/test_known_predict_trained.py) : 21 tests, faux modèle JSON (sans torch) et vrai HGB du dépôt.
- **Pourquoi** : rendre nos deux modèles calculables par E4 (`.pred.csv` / `.runs.csv`) et appelables par E5 ; recette de [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md) (MOD-008) et point ouvert de MOD-010.
- **Fichiers** : [predict.py](../../src/models/known/predict.py), [test_known_predict_trained.py](../../tests/test_known_predict_trained.py), ce fichier.
- **Impact partenaires / contrats** :
  - Aucune colonne CSV modifiée. Nouvelles variantes `mlp` et `hgb` de `predict_24h`, avec `model_run_id` obligatoire.
  - **Le contexte est nécessaire** : sans `context=`, les deux modèles refusent (`*_context_missing`) et la référence répond. À dire à E5.
  - Codes de refus visibles dans `status_reason` : `mlp_*` (E2-TECH-003) et `hgb_*` (MOD-010). À annoncer à E4 et E5.
  - `predict.py` est le fichier d'Emmanuelle : à la prévenir.
- **Vérifications effectuées** :
  - `pytest -q` : 371 passés. `ruff check` et `ruff format --check` sans problème sur les fichiers E2.
  - Vrai HGB, avec contexte : servi (`ok`) ; changer les heures publiées après `origin - 24 h` ne change pas la prévision ; témoin positif : changer la semaine visible la change.
  - Chaîne réelle sur 25 cas de validation `proto-v1` (3 compteurs × 5 jours), sans lire les cibles : HGB 25 `ok` ; MLP 15 `ok` et 10 `fallback` (`mlp_window_too_sparse`, site `100047545`) ; 600 lignes, aucune valeur vide ; ≈ 0,5 s par cas.
- **Points ouverts** :
  - Coût : ≈ 50 min par modèle pour les 6 014 cas de validation, surtout le refiltrage du contexte à chaque cas ; optimisable.
  - Le chargement du modèle (une fois par expérience) n'est pas compté dans `preparation_seconds`.
  - Désigner le `model_run_id` servi par l'application (E5).
  - Calcul complet de la validation à lancer seulement avec la fiche EXP-E2-03 figée.

### MOD-010 - 2026-11-24 - HGB implémenté (`tabular.py`), tests et premier apprentissage réel (complète MOD-009)

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2` / commité 
- **Quoi** :
  - [tabular.py](../../src/models/known/tabular.py) : toutes les fonctions du squelette MOD-009 sont écrites.
    - `hgb_hyperparameters` contrôle les réglages et refuse une clé inconnue.
    - `fit_hgb` :
      - contrôle les origines avant de lire une cible ;
      - construit les variables avec `build_training_frame` (`f1.0`) ;
      - réserve comme holdout les 4 semaines avant `fit_cutoff`, en journées entières ;
      - choisit le nombre d'arbres sur ce holdout avec `staged_predict` (patience 20) ;
      - réapprend avec ce nombre d'arbres, sur l'apprentissage seul par défaut ;
      - écrit un bilan avec la MAE de contrôle contre `lag_168h` et `profile_median_4w` sur les mêmes cellules.
    - `predict_hgb` refuse avec un code `hgb_*`, sinon passe par `build_feature_frame` et `predict_frame`. Les sorties sont bornées à ≥ 0.
    - `save_hgb` / `load_hgb` (joblib) refusent un format, une version de variables, des colonnes ou une latence différents.
    - La commande `python -m src.models.known.tabular` apprend, sauvegarde et affiche le bilan.
  - [tests/test_known_tabular.py](../../tests/test_known_tabular.py) : 36 tests sur données synthétiques, sans dépendre de torch. Ils couvrent :
    - les réglages et les origines ;
    - la stabilité : changer le futur ou relancer avec la même graine ne change rien ;
    - le holdout en journées entières, la latence et les refus ;
    - une fenêtre clairsemée, qui est prévue et non refusée ;
    - l'égalité du calcul en bloc et du calcul cas par cas ;
    - l'aller-retour `train.save_model` / `load_model` et le refus des modèles incompatibles.
- **Pourquoi** : second modèle sites connus, à comparer au MLP et aux références sur les mêmes origines (EXP-E2-03).
- **Fichiers** : [tabular.py](../../src/models/known/tabular.py), [test_known_tabular.py](../../tests/test_known_tabular.py), ce fichier.
- **Impact partenaires / contrats** :
  - Aucune colonne CSV ni signature partagée modifiée. `predict.py` n'est pas encore branché : la variante `hgb` n'est pas servie par `predict_24h`.
  - Nouveaux codes à annoncer à E4 et E5 avant le branchement : `hgb_origin_not_midnight`, `hgb_origin_before_fit_cutoff`, `hgb_no_history`, `hgb_context_missing`, `hgb_non_finite_output`.
  - Le HGB ne refuse pas une fenêtre clairsemée, contrairement au MLP (`mlp_window_too_sparse`). Sa couverture sera donc plus large : comparer sur les mêmes cas complets.
- **Vérifications effectuées** :
  - `pytest` hors tests du MLP (torch absent du `.venv` local) : 242 passés. `ruff check` et `ruff format --check` sans problème.
  - Données réelles, `hist-20261117`, coupure au 01/07/2026, avec contexte, graine 0, `--no-save`, model_run_id `e2-hgb-ctx-20260701-s0-b357` :
    - effectifs : 97 compteurs ; 2 082 454 lignes et 87 084 origines en apprentissage ; holdout de 61 370 lignes sur 95 compteurs (03/06 au 29/06) ; 9 groupes E3 exclus ;
    - modèle : 342 arbres retenus sur 500 ;
    - temps : 4 min 38 s au total, dont 44 s de variables et 125 s pour les deux apprentissages HGB ;
    - NaN ≤ 0,33 % par colonne.
  - Fiche : [E2-TECH-004](../experiments/E2-TECH-004.md).
  - Contrôle sur le holdout, en MAE macro par compteur sur 61 314 cellules : HGB 17,9 vélos/h, `profile_median_4w` 20,3, `lag_168h` 24,5. Contrôle de bon fonctionnement seulement, ni score E4 ni comparaison officielle. Le MLP donnait 17,5 contre 24,5 pour `lag_168h` (E2-TECH-003), mais sur ses propres cellules : les deux chiffres ne sont pas comparables.
- **Fiche d'essai** : [E2-TECH-004](../experiments/E2-TECH-004.md).
- **Points ouverts** :
  - brancher les variantes `hgb` et `mlp` dans `predict.py` : Idir ;
  - choisir la loss : E4 ; `absolute_error` reste le réglage par défaut d'ici là ;
  - mettre en commun `_check_training_origins` et `_holdout_start` avec `neural.py` (Idir) ;
  - sauvegarder un modèle, puis mesurer la couverture et le coût par cas sur la validation ;
  - ajouter à `BIBLIOGRAPHIE.md` des références sur le gradient boosting, absentes aujourd'hui ;
  - fixer `refit_on_holdout` et `categorical` avant les scores de validation (EXP-E2-03) ;
  - calculer l'importance des variables par permutation, sur la validation.

### MOD-009 - 2026-11-24 - Squelette du HGB (`tabular.py`) et de ses tests

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2` / commité.
- **Quoi** :
  - [tabular.py](../../src/models/known/tabular.py), nouveau : constantes (réglages par défaut, codes de refus `hgb_*`), `HGBModel`, `HGBForecast`, signatures et docstrings de `hgb_hyperparameters`, `resolve_groups`, `fit_hgb` (arrêt anticipé temporel sur les 4 semaines avant `fit_cutoff`, jamais le découpage aléatoire de sklearn), `refusal_reason`, `predict_frame`, `predict_hgb`, `save_hgb` / `load_hgb`, commande `main`. Toutes lèvent `NotImplementedError("E2 (Ania) : ...")` ; « hgb » est déclaré dans le registre à l'import.
  - [tests/test_known_tabular.py](../../tests/test_known_tabular.py), nouveau : 2 tests actifs (déclaration, codes de refus), 17 tests à écrire marqués `skip`.
- **Pourquoi** : étape 5 du README E2 ; second modèle sites connus, comparé au MLP sur les mêmes origines (EXP-E2-03).
- **Fichiers** : [tabular.py](../../src/models/known/tabular.py), [test_known_tabular.py](../../tests/test_known_tabular.py), ce fichier.
- **Impact partenaires / contrats** : aucun pour l'instant (aucune colonne, signature ou variante de `predict_24h` modifiée). L'ablation par groupe passe par `hyperparameters["context_groups"]`, sans changer `TrainConfig`. `_check_training_origins` et `_holdout_start` dupliquent `neural.py` : factorisation à proposer à Idir.
- **Vérifications effectuées** : `pytest` hors tests du MLP (torch absent du `.venv` local) : 208 passés, 17 ignorés ; `ruff check` et `ruff format --check` sans problème.
- **Points ouverts** : loss principale, réapprentissage sur le holdout, variables catégorielles, refus d'une fenêtre très clairsemée ou non.

### MOD-008 - 2026-11-23 - Apprentissage (`fit_mlp`) et prévision (`predict_mlp`) du MLP, essai réel E2-TECH-003

- **Auteur** : Esther (assistée par Claude Code).
- **Branche / commit** : `Team2-Esther` / commité.
- **Quoi** :
  - [neural.py](../../src/models/known/neural.py) :
    - `mlp_hyperparameters` : tous les réglages, contrôlés (clé inconnue ou valeur hors domaine refusées), à passer à `TrainConfig` pour que `metadata.json` et le nom du modèle portent les réglages réellement utilisés ;
    - `fit_mlp`, branché sur le registre (`fit=fit_mlp`) :
      - contrôles des origines avant toute lecture de cible (minuit, doublons, cibles publiées à `fit_cutoff`) ;
      - perte L1 masquée, pondérée par le niveau (`_masked_l1`) ;
      - arrêt anticipé sur les 4 dernières semaines avant `fit_cutoff` (dates locales), meilleure époque rendue ;
      - graine locale (`torch.random.fork_rng`) ;
      - bilan `training_report` : effectifs, exclusions, pertes par époque, contrôle sur l'arrêt anticipé contre `y(t − 168 h)` ;
    - `predict_mlp` → `MLPForecast` (24 valeurs ≥ 0 en vélos/h, ou refus motivé, codes `mlp_*`) :
      - historique refiltré sur `information_cutoff` ;
      - refus d'une origine hors minuit, ou antérieure à la coupure (lue dans le bilan du réseau si l'appelant l'oublie) ;
      - `ValueError` si la latence du cas diffère de celle de l'apprentissage ;
    - `predict_windows` (même calcul pour beaucoup de cas) et `refusal_reasons` (seule source des refus liés aux données de la fenêtre) ;
    - `build_windows` : deux champs ajoutés, `context_missing` (contexte inconnu à l'origine, au lieu d'un 0 silencieux) et `publication_lag_hours` ; valeurs du tableau inchangées ;
    - `weights.pt` au format 2 : latence dans la disposition des entrées, bilan d'apprentissage ; le format 1 reste lisible (latence 24 h) ;
    - commande `python -m src.models.known.neural` : apprend, sauvegarde, écrit `training_report.json`.
  - [train.py](../../src/models/known/train.py) : `fit` refuse une `publication_lag_hours` différente de la configuration (`_check_publication_lag`).
  - Tests :
    - [tests/test_known_neural_fit.py](../../tests/test_known_neural_fit.py), nouveau (44 tests) ;
    - [tests/test_known_neural.py](../../tests/test_known_neural.py) : `test_mlp_declare_mais_pas_encore_entrainable`, qui vérifiait l'état temporaire `fit=None`, devient `test_mlp_declare_et_entrainable`.
  - Essai technique [E2-TECH-003](../experiments/E2-TECH-003.md) ; [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md) mis à jour ; journal [E2-esther.md](../individual/E2-esther.md).
- **Pourquoi** : étape 5 du README E2 et expérience de deep learning obligatoire (sujet p. 4 ; D-05, M3). Le MLP devient entraînable et utilisable avec les mêmes garanties de causalité que les références. Pièges traités :
  - `build_windows` lit les cibles sans regarder `fit_cutoff` ;
  - la latence passée à `train.fit` n'est pas transmise aux méthodes ;
  - une origine hors minuit décalerait les sorties sans erreur visible ;
  - un contexte manquant passerait pour 0 (« 0 °C ») ;
  - une origine antérieure à la coupure serait servie par un modèle qui a appris dessus ;
  - des réglages implicites manqueraient dans `metadata.json` ;
  - `torch.__version__` est refusé au rechargement sécurisé (repéré par un test).
- **Fichiers** : [neural.py](../../src/models/known/neural.py), [train.py](../../src/models/known/train.py), [test_known_neural_fit.py](../../tests/test_known_neural_fit.py), [test_known_neural.py](../../tests/test_known_neural.py), [E2-TECH-003.md](../experiments/E2-TECH-003.md), [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md), [E2-esther.md](../individual/E2-esther.md), ce fichier.
- **Impact partenaires / contrats** :
  - Aucune colonne CSV d'échange modifiée ; `predict.py`, `features.py`, `registry.py` et `schemas.py` non modifiés.
  - `train.fit(..., publication_lag_hours=X)` lève désormais `ValueError` si X diffère de la configuration (aucun effet avec `None` ou 24 h) : prévenir Idir et Ania (HGB).
  - `Windows` gagne deux champs ; `_calendar_block` (interne) renvoie aussi l'indicateur de contexte manquant.
  - `weights.pt` passe au format 2 : l'ancien code ne lit pas un fichier au format 2, le nouveau lit les deux.
  - Signature finale `predict_mlp(net, inputs, *, fit_cutoff=None)` : le contexte est celui de `inputs`, déjà filtré par `build_inputs`, et non un argument séparé comme dans la proposition de la prise en main.
  - Nouveaux codes à communiquer à E4/E5 avant le branchement dans `predict.py` : `mlp_origin_not_midnight`, `mlp_origin_before_fit_cutoff`, `mlp_no_history`, `mlp_context_missing`, `mlp_window_too_sparse`, `mlp_level_too_low`, `mlp_non_finite_output`.
  - Le réseau n'a pas d'identifiant de compteur : réutilisable par E3 (sites E3 exclus, preuve dans `metadata.json`), à lui présenter.
- **Vérifications effectuées** :
  - Avant toute modification : 222 tests passés, point de référence.
  - Après : `./run.sh test` 266 tests passés (222 + 44) ; `./run.sh check` sans problème (Python 3.11.18, torch 2.15.0 CPU).
  - Données réelles (E2-TECH-003) :
    - SHA-256 conformes au manifeste ;
    - 90 736 exemples, comme MOD-007 ; aucun contexte incomplet ;
    - 28 époques, meilleure 20 ; 33 s et 1,25 Go sur CPU ;
    - contrôle sur l'arrêt anticipé (juin) : MAE 17,5 vélos/h contre 24,5 pour `y(t − 168 h)` sur les mêmes cellules. C'est un contrôle de bon fonctionnement, pas une comparaison ;
    - validation : 94,7 % des 6 014 cas servis, 320 refus, tous `mlp_window_too_sparse` ;
    - 40 cas réels : le calcul cas par cas égale le calcul en bloc (écart ≤ 0,0003 vélo/h).
  - Un premier témoin positif a échoué : gonfler une cible de 175 à 5 000 ne changeait pas les poids. C'est une propriété de la L1, désormais testée directement (`test_perte_l1_masquee_ponderee_et_robuste`).
- **Points ouverts** :
  - Brancher la variante MLP dans `predict.py` (recette dans la prise en main), puis l'annoncer à E5.
  - Fiche EXP-E2-03 (MLP, HGB, références ; avec et sans contexte) à figer avant les scores ; variabilité entre graines à mesurer.
  - Réapprendre ou non sur les semaines d'arrêt anticipé (D-20).
  - Coût cas par cas de 0,39 s : mettre en cache le contexte préparé si E5 en a besoin.
  - 4 sites en panne pendant la validation : cas difficile pour l'approfondissement.
  - D-17 toujours à écrire dans `config/project.yaml`.

### MOD-007 - 2026-11-22 - Socle commun `train.py`, préparation et sauvegarde du MLP (`neural.py`)

- **Auteur** : Idir.
- **Branche / commit** : `Team2-idir` / `4684e7c`, fusionné dans `Team2`.
- **Quoi** :
  - [train.py](../../src/models/known/train.py), socle commun à toutes les méthodes :
    - `fit` choisit une seule fois les compteurs (`training_counters`) et les origines (`training_origins` entre `train_start` et `fit_cutoff`), puis appelle la méthode via un registre (`MethodBackend`, `register_backend`, `get_backend`) ;
    - `save_model` / `load_model` : `artifacts/models/<model_run_id>/`, `metadata.json` au format du gabarit, SHA-256 des poids, écriture atomique, refus d'écraser ;
    - `load_training_data` : entrées = mesures seules (D-11), valeur E1 gardée dans `count_e1` ;
    - nommage `make_model_run_id` : `e2-<méthode>-<ctx|noctx>-<coupure>-s<graine>-<empreinte>` ;
    - `TrainConfig.train_start` ajouté ; `exclude_reserved_sites` délègue à `training_counters`.
  - [neural.py](../../src/models/known/neural.py), nouveau :
    - `build_windows` : un exemple par compteur × origine, 419 entrées (344 sans contexte) : 168 h normalisées par leur niveau, 168 masques, la journée à prévoir, la météo prévue heure par heure ; 24 sorties ;
    - `MLPNet` (placeholder minimal, 2 × 128), `save_mlp` / `load_mlp` ;
    - « mlp » déclaré dans le registre, avec `fit=None`.
  - Tests : [test_known_train.py](../../tests/test_known_train.py) (25), [test_known_neural.py](../../tests/test_known_neural.py) (16).
  - Prise en main pour l'équipe : [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md).
- **Pourquoi** : étape 5 du README E2. Faire apprendre le HGB et le MLP sur les mêmes compteurs et les mêmes origines (comparaison équitable), tracer chaque modèle (I2), préparer l'expérience de deep learning (D-05, M3).
- **Fichiers** : [train.py](../../src/models/known/train.py), [neural.py](../../src/models/known/neural.py), [test_known_train.py](../../tests/test_known_train.py), [test_known_neural.py](../../tests/test_known_neural.py), [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md), ce fichier.
- **Impact partenaires / contrats** :
  - Signatures du squelette modifiées : `fit(config, counts, context, inventory, *, include_robustness, publication_lag_hours)`, `load_training_data(snapshot_id, *, root, values)` (sans `protocol_id`), `exclude_reserved_sites(counts, inventory, include_robustness)`.
  - Le HGB doit se brancher par `register_backend("hgb", …)` (exemple dans la prise en main).
  - `neural.py` utilise des fonctions internes de `features.py` (`_calendar_core`, `_prepare_context`, `_context_core`) : prévenir avant de les modifier.
  - `metadata.json` porte `excluded_site_groups` (preuve pour E3).
  - Aucune colonne CSV d'échange modifiée ; `features.py`, `predict.py`, `registry.py` et `schemas.py` non modifiés.
- **Vérifications effectuées** :
  - `pytest` : 222 tests passés, dont 41 nouveaux ; `ruff check` et `ruff format --check` sans problème.
  - Données réelles : `fit` (méthode espion) reçoit 97 compteurs et 90 736 exemples (15/11/2023 → 29/06/2026), 9 groupes E3 exclus ; `build_windows` en 5 s, 97,7 % d'exemples utilisables ; cas Pont National du 10/03/2026 identique au calcul à la main.
  - Tests clés : modifier le futur ne change pas les entrées ; calcul en bloc = cas par cas ; invariance d'échelle ; vide ≠ zéro mesuré ; aller-retour de sauvegarde identique ; refus d'un fichier modifié, d'une fiche retouchée, d'entrées rangées autrement, d'un fichier contenant du code.
  - Contrôle indépendant de `hist-20261117` : grille complète, 0 doublon, raccords janvier 2024 et archives → flux sans cassure.
- **Points ouverts** :
  - `fit_mlp` / `predict_mlp` à écrire (proposés à Esther) ; variante `"model"` à brancher dans `predict.py`.
  - 29 heures aberrantes (> 1 500 vélos/h) gardées comme cibles par E1 ; environ 0,1 % de cibles normalisées très élevées, à traiter dans la perte.
  - Dates d'apprentissage à écrire dans `config/project.yaml` (D-17).
  - `training_origins` prend environ 70 s sur les données réelles.

### MOD-006 - 2026-11-20 - Variables f1.0 (`features.py`), tests et jeu d'apprentissage réel

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2` / commité.
- **Quoi** :
  - [features.py](../../src/models/known/features.py), `FEATURE_VERSION = "f1.0"` :
    - calendrier de base, toujours présent : horizon, heure locale, jour, week-end, mois (Europe/Paris) ;
    - historique, toujours présent : `lag_168h`, `lag_336h` et leurs indicateurs de manque, `profile_median_4w` (même valeur que `reference_profile`), `profile_n_weeks`, `level_24h`, `level_168h`, `level_prev_168h`, `trend_7d_log`, `missing_share_168h`, `hours_since_last_obs`, `zero_run_hours` (zéros mesurés consécutifs, calculés sans regarder le futur) ;
    - contexte en groupes (`CONTEXT_GROUPS`) : `calendar` (férié, vacances zone C, jointure sur la date locale), `strikes` (grève IDF, date locale, disponible 24 h avant le jour), `weather_forecast` (bulletin J−2, jointure `valid_time = interval_end`). Une ligne publiée après l'origine donne NaN ; une clé en double lève une erreur ; la météo observée n'est jamais lue ;
    - traçabilité : `feature_version`, `case_id`, `counter_id`, `origin`, `target_timestamp`, `horizon`, `max_input_available_at` (contrôlé `<= origin`).
  - Un seul calcul pour les deux chemins : `build_feature_frame` (un cas, inférence) et `build_training_frame` (tous les cas d'un compteur en une fois). Le calcul ne lit que le passé admissible même avec l'historique complet.
  - Nouvelles fonctions : `training_origins` (minuit local, 4 semaines de préchauffage, 24 cibles publiées à `fit_cutoff`), `training_counters` (S_train `retained` + `robustness`, refus d'un groupe partagé avec les sites réservés), `resolve_context_groups`, `feature_columns`.
  - [tests/test_known_features.py](../../tests/test_known_features.py) : 15 tests synthétiques, avec le passage à l'heure d'été du 30/03/2025.
  - [registry.py](../../src/models/registry.py) passé au formateur Ruff (mise en forme seulement).
  - Essai technique [E2-TECH-002](../experiments/E2-TECH-002.md) sur `hist-20261117`.
- **Pourquoi** : étape 4 du README E2 ; base du modèle sites connus et de l'ablation calendrier (sujet p. 6, plan §5). Plan validé le 2026-11-20 (décisions D-12 à D-16).
- **Fichiers** : [features.py](../../src/models/known/features.py), [tests/test_known_features.py](../../tests/test_known_features.py), [registry.py](../../src/models/registry.py), [E2-TECH-002.md](../experiments/E2-TECH-002.md), ce fichier.
- **Impact partenaires / contrats** :
  - Signatures modifiées :
    - `context_features(inputs, targets, context_groups=None)` ;
    - `build_feature_frame(inputs, use_context=True, *, context_groups=None)` ;
    - `build_training_frame(..., *, context_groups=None, publication_lag_hours=None)`.
  - `use_context=True` garde le sens « tout le contexte ».
  - À présenter à E3 : bibliothèque partageable, sans identifiant de compteur ; avec 7 jours de support, les variables au-delà d'une semaine valent NaN.
  - À présenter à E1 : lecture de `context.csv` (rôles, météo sur `interval_end`, `available_at` des grèves).
  - Aucune colonne CSV d'échange modifiée.
- **Vérifications effectuées** :
  - `pytest` : 181 tests passés, dont 15 nouveaux. `ruff check src tests` et `ruff format --check src tests` sans problème (Python 3.11, `.venv`).
  - Sur données réelles (E2-TECH-002) : 97 compteurs, 2 075 614 lignes ; aucune entrée disponible après l'origine ; aucune cible publiée après `fit_cutoff`.
  - Égalité exacte des deux chemins sur 12 couples tirés au hasard.
  - 4 lignes vérifiées à la main depuis les CSV.
  - Empreintes SHA-256 conformes au manifeste.
- **Points ouverts** :
  - `fit_cutoff` provisoire (01/06 de `proto-v0` contre 01/07 dans le protocole proposé).
  - I3 (décalages en UTC) non tranché.
  - Construction en 204 s, optimisable si besoin.
  - Ablation à faire seulement après validation du protocole.
  - E3 et E1 à prévenir.

### MOD-005 - 2026-11-19 - Chaîne complète sur données réelles : chargement, filtrage causal, predict_24h, commande (Corrige MOD-004)

- **Auteur** : kid-emmanuelle.
- **Branche / commit** : `Team2` / commité.
- **Quoi** :
  - [schemas.py](../../src/models/schemas.py) : `Case.from_row` (cellules vides = absent, dates avec fuseau obligatoires puis UTC, scénario contrôlé) ; `assert_causal` (coupure ≤ origine, `interval_end` ≤ coupure, `available_at` ≤ origine pour l'historique et le contexte, support local pour un nouveau site).
  - [predict.py](../../src/models/known/predict.py) :
    - `counts_history_loader` lit `counts.csv` une fois. Avec `values="measured"` (D-11), l'entrée vaut la mesure publiée seulement ; la valeur d'E1 est gardée dans `count_e1`.
    - `build_inputs` : coupure = origine − latence de la configuration ; contexte gardé si `available_at` vide ou ≤ origine ; refus de `new_site` (E3).
    - `predict_24h` : variantes `reference` et `reference_profile`, refus explicite des autres, temps de préparation mesuré.
    - `run_experiment` : un cas en échec reste présent, avec 24 lignes vides et le statut `error`.
    - `select_cases` / `train_site_counters` : sites connus `S_train` d'E1 seulement, décompte des cas écartés, `snapshot_id` remplacé par l'instantané lu.
    - Commande `python -m src.models.known.predict`, qui refuse le bloc `test` sauf `--allow-test`.
  - [tests/test_known_predict.py](../../tests/test_known_predict.py) : 8 tests synthétiques (lecture des cas, valeurs mesurées contre estimées, repli sur une estimation E1, filtrage du futur et du contexte tardif, fuites refusées, cas en échec conservé).
  - Essai technique [E2-TECH-001](../experiments/E2-TECH-001.md) : 10 858 cas de validation, pour chaque référence.
  - Corrige MOD-004 : son commit est `8bf5f7f` 
- **Pourquoi** : données d'E1 reçues ; première prévision réelle à transmettre à E4 et E5 (sujet p. 4 et 6).
- **Fichiers** : [schemas.py](../../src/models/schemas.py), [predict.py](../../src/models/known/predict.py), [tests/test_known_predict.py](../../tests/test_known_predict.py), [E2-TECH-001.md](../experiments/E2-TECH-001.md), ce fichier.
- **Impact partenaires / contrats** :
  - `predict_24h` garde la signature imposée et ajoute les arguments nommés `method_run_id=` et `publication_lag_hours=`. L'historique complet du compteur peut lui être passé : il le refiltre.
  - `build_inputs` lit par défaut la latence dans la configuration.
  - À présenter : à E1 D-11 ; à E4 les 3 écarts de `proto-v0` (§8) ; à E5 la commande, les deux variantes et le statut `error`.
- **Vérifications effectuées** :
  - `./run.sh test` : 166 tests passés, dont 26 E2. `ruff check src tests` sans problème ; `ruff format --check` : seul `registry.py` reste non formaté (inchangé).
  - Empreintes SHA-256 des fichiers livrés conformes au manifeste.
  - Sur données réelles : 10 858 cas sur 10 858 complets pour chaque variante, aucune erreur, aucune clé en double, aucune valeur négative. 11 valeurs recalculées indépendamment depuis `counts.csv`, toutes identiques.
  - Bloc test jamais calculé.
- **Points ouverts** :
  - MAE à calculer par E4.
  - D-11 à faire valider par E1/E4.
  - Écarts `proto-v0` à corriger par E4, puis recalcul.
  - C3/M2 (pas d'`available_at` dans `counts.csv`), I3 et l'ajustement au niveau récent restent ouverts.
  - Contexte non utilisé par les références.

### MOD-004 - 2026-11-19 - Seconde référence : médiane hebdomadaire sur 4 semaines (Corrige MOD-003)

- **Auteur** : kid-emmanuelle.
- **Branche / commit** : `Team2` / `8bf5f7f`.
- **Quoi** :
  - [baseline.py](../../src/models/known/baseline.py) : nouvelle référence `weekly_profile_reference` (méthode `weekly_profile_median`, variante `reference_profile`) : médiane de y(t − k × 168 h), k = 1..4, jointure par timestamp, sur les semaines observées et admissibles (zéros compris). Sans aucune des 4 semaines, même chaîne de repli que `weekly_naive`, avec `status_reason` = `profile_weeks_missing`. Le calcul commun aux deux références est factorisé dans `_seasonal_reference` ; `weekly_reference` garde un comportement identique (tests MOD-003 inchangés et passants).
  - [tests/test_known_baseline.py](../../tests/test_known_baseline.py) : valeurs calculées à la main sur le même cas (h1 = 31173, h7 = 30555 avec le zéro observé, h12 = 30910 et h17 = 30915 sur 3 semaines sans repli) ; égalité avec `weekly_naive` pour `n_weeks=1` ; repli puis `unavailable` ; insensibilité aux lignes postérieures à la coupure.
  - Corrige MOD-003 : la docstring du test écrivait 20211 et 20216 pour les comptages du 2 mars (codés 30211 et 30216). Les résultats attendus (31261, 31266) étaient justes, la médiane de 4 valeurs ne dépendant que des deux centrales.
- **Pourquoi** : renforcer la référence (une seule semaine est sensible à une journée atypique) et préparer une échelle de références simples, chaque marche constituant une petite ablation. Prophet écarté comme référence : non vérifiable à la main, ajustement par cas, historique long requis, dépendance supplémentaire (voir D-10).
- **Fichiers** : [baseline.py](../../src/models/known/baseline.py), [tests/test_known_baseline.py](../../tests/test_known_baseline.py), ce fichier.
- **Impact partenaires / contrats** : aucune colonne modifiée. Nouvelles valeurs à communiquer à E4/E5 : `method_used` = `weekly_profile_median`, `variant` = `reference_profile`, `status_reason` = `profile_weeks_missing` (et `profile_weeks_missing;no_fallback_history`). Utilisable par E3 comme référence au même budget local.
- **Vérifications effectuées** : `./run.sh test` : 18 tests passés. `ruff check src tests` : aucun problème ; `ruff format --check` : seul `registry.py` reste non formaté (inchangé). Une première valeur attendue (h7) était fausse dans le test ; la vérification à la main a confirmé la valeur du code (30555). Données synthétiques uniquement.
- **Points ouverts** : nombre de semaines (4) à fixer avant les comparaisons, sur validation ; choix de la référence officielle (`weekly_naive` seule ou les deux) à décider avec E4 ; I3 inchangé (lags en UTC) ; référence ajustée au niveau récent proposée, non codée.

### MOD-003 - 2026-11-19 - Référence hebdomadaire, repli, exports et cas construit à la main (Corrige MOD-001, MOD-002)

- **Auteur** : kid-emmanuelle.
- **Branche / commit** : `Team2` / `e88fb0b`.
- **Quoi** :
  - [baseline.py](../../src/models/known/baseline.py) : `weekly_reference` (y(t − 168 h) par jointure sur timestamp, repli par horizon, statuts `ok` / `fallback` / `unavailable`, coût d'inférence), `admissible_history` (un seul compteur, dates UTC avec fuseau obligatoires, doublons refusés, filtre `interval_end <= information_cutoff`), `lookup_lagged`, `fallback_value`. Repli proposé pour D-03 avec N = 4 : médiane des 4 dernières observations admissibles de même jour et même heure locale, puis moyenne des 28 dernières de même heure locale, sinon `y_pred` vide et statut `unavailable`. Codes stables pour E4/E5 : `method_used` ∈ {`weekly_naive`, `profile_median_dow_hour`, `profile_mean_hour`} ; `status_reason` ∈ {`lag168_missing`, `lag168_missing;no_fallback_history`}. Statut du cas : `unavailable` si un horizon manque, sinon `fallback` si un horizon est en repli, sinon `ok`.
  - [schemas.py](../../src/models/schemas.py) : `ForecastResult.is_complete` (24 horizons distincts, `y_pred` finies ≥ 0), `to_forecast_frame` (colonnes `FORECAST_COLUMNS`), `to_run_row` (colonnes `CASE_RUNS_COLUMNS`). Fichier passé au formateur Ruff.
  - [predict.py](../../src/models/known/predict.py) : `write_predictions` et `write_runs` aux conventions CONTRATS §1 (UTC ISO avec fuseau, `true`/`false`, cellule vide = absent), refus des clés en double et des cas sans 24 lignes.
  - [tests/test_known_baseline.py](../../tests/test_known_baseline.py) : cas synthétique construit à la main (origine 2025-03-29T23:00Z, jour du passage à l'heure d'été) avec zéro observé, `count` manquant, ligne absente de la grille et lignes futures présentes dans le fichier ; valeurs attendues calculées à la main dans la docstring.
  - Correction de MOD-001 et MOD-002 : leur travail est commité dans `690b7bd` sur la branche `Team2` (et non `Team2-squelette` / non commité).
- **Pourquoi** : premier livrable E2 (sujet p. 6 : référence vérifiée sur un petit cas construit, puis raccordée aux données, au score et à l'application), réalisable sans attendre `counts.csv` d'E1.
- **Fichiers** : [baseline.py](../../src/models/known/baseline.py), [schemas.py](../../src/models/schemas.py), [predict.py](../../src/models/known/predict.py), [tests/test_known_baseline.py](../../tests/test_known_baseline.py), ce fichier.
- **Impact partenaires / contrats** : aucune colonne CSV modifiée. Nouveaux arguments nommés optionnels `method_run_id=` et `fallback_weeks=` de `weekly_reference`, `fallback_weeks=` de `fallback_value`. À présenter : à E4 et E5 les codes `method_used` / `status_reason` et la règle de statut du cas ; à E1 la règle d'admissibilité provisoire et le refus des timestamps sans fuseau ou en double ; à E3 la réutilisation possible de `weekly_reference` comme référence au même budget local.
- **Vérifications effectuées** : `./run.sh test` : 14 tests passés (Python 3.11, `.venv` du projet, uv 0.13.1). `ruff check src tests` : aucun problème. `ruff format --check` : seul [registry.py](../../src/models/registry.py) reste non formaté (déjà le cas avant ce changement, non modifié ici). Valeurs vérifiées à la main : h1 = 32223, h7 = 0.0 (zéro observé), h12 = 31261 et h17 = 31266 (replis), h24 = 32322. Une perturbation des lignes postérieures à la coupure ne change aucune prévision. Données synthétiques uniquement : aucune performance sur Paris n'est mesurée.
- **Points ouverts** : N = 4 et la règle de repli à valider avec E4/E5 (D-03) ; I3 (168 h UTC contre heure locale du repli) visible dans le test, non tranché ; règle d'admissibilité provisoire en attendant C3/M2 (D-08) ; les chaînes de dates sans décalage sont lues comme UTC par pandas ; `build_inputs`, `predict_24h`, `Case.from_row` et le raccord réel avec E4/E5 restent à faire.

### MOD-002 - 2026-11-19 - Revue des incohérences critiques ; corrections C1 et C2 (Corrige MOD-001)

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2-squelette` / non commité.
- **Quoi** :
  - Nouvelle revue des squelettes E2 face au sujet, au plan, à CONTRATS, PROTOCOLE, ARCHITECTURE et aux gabarits. **Corrige MOD-001** : la conclusion « aucune incohérence critique » était fausse ; cinq incohérences critiques (C1–C5), cinq importantes (I1–I5) et trois mineures (M1–M3) sont listées au [§10](#10-incohérences-relevées-et-suivi).
  - C1 appliquée : suppression de l'ambiguïté « nul » (zéro ou manquant). Dans [baseline.py](../../src/models/known/baseline.py), un horizon sans repli a `y_pred` manquant (NaN, jamais 0) ; un zéro observé à t−168 h est une prévision valide. Dans [features.py](../../src/models/known/features.py), `build_training_frame` exclut les cibles manquantes et conserve les zéros observés.
  - C2 appliquée : `calendar_features` ne contient plus que heure locale, jour de semaine et week-end (paramètre `calendar` retiré) ; fériés et vacances passent dans `context_features` avec la météo admissible. `use_context=False` retire désormais toute la source complémentaire, et elle seule.
  - [predict.py](../../src/models/known/predict.py) : docstring précisant que la signature `predict_24h` est exigée par E5 et renvoyant à C4.
- **Pourquoi** : C1, un `y_pred = 0` comptait un cas comme complet et faussait la MAE (CONTRATS §7) ; exclure les zéros des cibles contredisait le sujet (p. 3). C2, l'ablation « même modèle avec et sans calendrier » (sujet p. 6, plan §5) gardait les fériés dans les deux variantes.
- **Fichiers** : [baseline.py](../../src/models/known/baseline.py), [features.py](../../src/models/known/features.py), [predict.py](../../src/models/known/predict.py), ce fichier.
- **Impact partenaires / contrats** : signature `calendar_features(targets)` modifiée (paramètre `calendar` retiré) ; à signaler à E3, qui partage la bibliothèque de variables, et à E1 pour le rôle `known_calendar` de `context.csv`. Aucune colonne CSV ni aucun statut modifié.
- **Vérifications effectuées** : import de `src/models/known/{baseline,features,predict,train}` et `src/models/registry` OK après modification, avec Python 3.13.1 système (le projet cible 3.11 : I5). Ruff non exécuté. Aucune logique exécutée : les fonctions restent non implémentées.
- **Points ouverts** : C3, C4 et C5 en suspens selon les décisions D-08 à D-10 ; I1–I5 et M1–M3 non traités (§10).

### MOD-001 - 2026-11-19 - Revue de cohérence et squelette du dossier `src/models`

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2-squelette` / non commité.
- **Quoi** :
  - Revue croisée du sujet (PDF, 12 p.), de [ARCHITECTURE.md](../../doc/ARCHITECTURE.md), de [CONTRATS.md](../../doc/CONTRATS.md), des gabarits CSV et des consignes de `src/models/`. Conclusion : **aucune incohérence critique** ; rôles E2/E3, scénarios `known_site`/`new_site`, format 24 lignes, `.runs.csv`, `support_id`/`adaptation_id` et comparaison gelée/adaptée/référence sont alignés.
  - Création de [schemas.py](../../src/models/schemas.py) : dataclasses `Case` (= une ligne de `cases.csv`), `ForecastInputs` (historique et contexte filtrés à la coupure d'information, `support_id` pour E3), `RunCost` (une ligne `.runs.csv`), `ForecastResult` (24 horizons, statut, provenance, coût) ; constantes `FORECAST_COLUMNS` et `CASE_RUNS_COLUMNS` recopiées des gabarits ; types `Scenario`, `Variant`, `PredictionStatus` ; `target_timestamps(origin)` implémentée (24 heures écoulées UTC, refus d'une origine sans fuseau).
  - Remplacement des consignes de [registry.py](../../src/models/registry.py) par un squelette : protocole `ForecastMethod(inputs, variant) -> ForecastResult`, fiche `MethodSpec` (scénarios, `min_history_hours`, `fit_cutoff`, dépendances, GPU, repli), fonctions de registre et de routage `select_method` avec chaîne de repli déclarée.
  - Squelettes de [baseline.py](../../src/models/known/baseline.py), [features.py](../../src/models/known/features.py), [train.py](../../src/models/known/train.py) et [predict.py](../../src/models/known/predict.py). Les consignes d'origine sont conservées dans les docstrings de module.
- **Pourquoi** : disposer d'interfaces stables avant de coder, conformément à ARCHITECTURE §5 (« interface à convenir avant de coder ») et permettre l'intégration d'une première prévision dès la première matinée.
- **Fichiers** : `src/models/schemas.py` (nouveau), `src/models/registry.py`, `src/models/known/{baseline,features,train,predict}.py`.
- **Impact partenaires / contrats** :
  - `schemas.py` est une **proposition** qui devra migrer dans `src/common/contracts.py` (fichier partagé E1-E5, actuellement vide). À présenter aux autres équipes.
  - `predict_24h(case, history, variant="reference")` conservée telle qu'imposée, avec ajout d'arguments nommés optionnels `context=` et `model_run_id=` (compatibles avec la signature imposée).
  - `src/models/new/` (périmètre E3) n'est pas modifié. `schemas.py` et `registry.py` prévoient `support_id` / `adaptation_id` et le scénario `new_site` pour qu'E3 puisse s'y brancher : à lui présenter.
- **Vérifications effectuées** : import de tous les modules `src/models` OK ; `target_timestamps(2025-03-29T23:00Z)` produit 24 heures UTC consécutives (h1 = 23:00, h24 = 2025-03-30 22:00) à travers le passage à l'heure d'été. Exécuté avec Python 3.13 système (le projet cible 3.11). **ruff non exécuté** : `uv` local en 0.10.9 alors que le projet exige ≥ 0.13.1 (`uv self update`).
- **Points ouverts** : voir §6 (D-01 à D-04).

---

## 5. Reste à faire

_Mis à jour le 2026-11-27. Ce qui est fait se trouve au journal (§4) et dans les fiches._

- [x] Prévisions notées par E4 (EXP-E2-03, `scores.csv` sur `dev`), identiques à notre score. MOD-018
- [x] Modèle de l'application désigné : HGB `e2-hgb-ctx-20260701-s0-b357` (D-24 définitive).
- [x] Score recalculable par un tiers (`score.py`), chemins personnels retirés, README du dossier réécrit. MOD-018
- [x] `Team2` fusionnée dans `dev` sans le commit retiré (MOD-014, MOD-017).
- [x] `max_iter=2000` retenu pour le HGB sans contexte ; modèles écartés `409c` et `8b7a` retirés du dossier des modèles (non commités).
- [ ] EXP-E2-04 : étape 2 (un groupe de contexte retiré à la fois, HGB), déclenchée par la règle du gel.
- [ ] EXP-E2-05 : prévisions (5 niveaux × 10 calculs), scores et décision.
- [ ] Gel final D-07, puis test final (octobre-novembre, 4 365 cas) lu une seule fois ; livraison à E4.
- [ ] Signaler à E1 le décalage de 2 h des mesures des 9, 10, 13 et 15 juillet 2026 (environ 90 compteurs sur 97), et à E4 son effet sur les scores de validation.
- [ ] Installation croisée par une autre équipe (copie neuve, README, `score.py`) et recalcul d'un autre cas avec E5 (SUIVI_ET_REMISE §6).
- [ ] Rapport d'équipe ([E2_RAPPORT.md](E2_RAPPORT.md)) complété avec 04, 05 et le test.

Abandonnés, avec leur raison : Prophet (D-04, D-10) ; migration de `schemas.py` vers `src/common/contracts.py` (I1, fichier commun) ; registre `registry.py` (C4, à retirer avec E5).

---

## 6. Décisions et points ouverts

| ID | Date | Sujet | Statut | Décision / question | Qui |
| --- | --- | --- | --- | --- | --- |
| D-01 | 2026-11-19 | Contrats communs | Clos (limite) | `src/common/contracts.py` est vide ; `schemas.py` proposé comme base. À valider avec les 5 équipes. **2026-11-27** : `src/models/schemas.py` sert de contrat de fait (E2, E3 et E5 l'importent) ; `contracts.py` n'a pas été rempli. Gardé comme limite (I1). | E2 → toutes |
| D-02 | 2026-11-19 | Signature `predict_24h` | Décidé | Signature imposée conservée ; ajout de `context=` (le contrat §5-6 prévoit un contexte admissible absent de la signature). **2026-11-27** : appliqué. E5 et E3 appellent `predict_24h(case, history, variant, context=...)`. | E2, E5 |
| D-03 | 2026-11-19 | Repli de la référence | Décidé | Proposition : médiane même heure locale / même jour sur N semaines admissibles, puis moyenne même heure locale, sinon `unavailable`. Valeur de N à fixer. MOD-003 : implémenté avec N = 4 (moyenne sur 28 observations au second niveau), paramètre `fallback_weeks` ; à valider avec E4/E5. **2026-11-27** : N = 4, utilisé dans toutes les expériences et noté par E4 (EXP-E2-03). | E2, E4, E5 |
| D-04 | 2026-11-19 | Prophet | Abandonné | Variante optionnelle seulement (`prophet_reference`), non déclarée dans `pyproject.toml`, jamais obligatoire. Ajout de la dépendance à décider. **2026-11-27** : Prophet abandonné, `prophet_reference` retiré (MOD-018). L'expérience de deep learning est le MLP. | E2 |
| D-05 | 2026-11-19 | Expérience deep learning | Décidé | Responsabilité E2 ou E3 à attribuer explicitement (ARCHITECTURE §6). `torch` disponible dans le groupe `dl` (CPU). MOD-007 : Idir porte un MLP compact sur CPU (préparation des données, réseau, sauvegarde) ; `fit_mlp` / `predict_mlp` proposés à Esther. Réutilisation possible par E3 comme base apprise ailleurs (sites E3 exclus, preuve dans `metadata.json`). À confirmer avec l'équipe et E3. MOD-008 : apprentissage et prévision écrits par Esther, premier essai réel (E2-TECH-003). **2026-11-27** : l'expérience de deep learning d'E2 est le MLP, comparé dans EXP-E2-03 (noté par E4) et EXP-E2-05. E3 le réutilise (« MLP E2 transféré »). | E2, E3 |
| D-06 | 2026-11-19 | Latence et décalage 168 h | Vérifié | Avec `publication_lag_hours = 24`, y(t−168 h) reste disponible pour les 24 horizons (dernière source disponible à origin − 120 h). | E2 |
| D-07 | 2026-11-27 | Gel des choix avant test final | **Décidé (gel)** | **Gel le 2026-11-27, avant toute lecture du test**, après EXP-E2-03 à 05. Méthodes du test, calculées **une seule fois** sur les 4 365 cas `known_site` / `test` (01/10 → 14/11/2026) : `reference`, `reference_profile`, HGB `e2-hgb-ctx-20260701-s0-b357` (modèle de l'application), MLP A `e2-mlp-ctx-20260701-s0-9ce9` (MLP de l'application, seuil 84 h et repli), et, pour information seulement, le MLP B `e2-mlp-ctx-20260701-s0-37f5` (masqué, seuil 24 h, non servi). Modèles figés au 01/07, sans réapprentissage. Lecture fixée d'avance : score E4 (`score.py --split test`), puis gain face aux deux références par période (semaines normales, vacances de la Toussaint du 17/10 au 01/11, semaines de transition autour du 17/10 et du 02/11), avec le bootstrap sur les jours. Périodes précisées avant la lecture : normale du 01/10 au 13/10 et du 09/11 au 14/11 ; transition du 14/10 au 20/10 et du 02/11 au 08/11 ; vacances du 21/10 au 01/11 (`python -m src.models.known.final_test`) ; diagnostics fériés (01/11, 11/11), grèves (3 jours) et pluie prévue. Aucun réglage n'est changé après la lecture. | E2, E4 |
| D-08 | 2026-11-19 | C3 : `available_at`, latence et `site_group_id` | Reporté | Attendre la version finale des données d'E1 avant de choisir où calculer `available_at` et comment joindre `site_group_id`. MOD-005 : `hist-20261117` n'a toujours pas `available_at` dans `counts.csv` ; règle provisoire `interval_end <= origin − latence` appliquée dans `build_inputs` ; `site_group_id` lu dans `cases.csv`, sites connus filtrés sur `site_role = S_train` de `inventory_quality.csv`. | E2, E1 |
| D-09 | 2026-11-19 | C4 : origine de `predict_24h` | Décidé | La signature `predict_24h(case, history, variant)` est exigée par E5. Sa coexistence avec `ForecastMethod(inputs, variant)` et le double routage seront traités plus tard. **2026-11-27** : `predict_24h` est le seul point d'entrée, utilisé par E3 et E5 ; `registry.py` n'est pas utilisé (proposition à E5 de le retirer, C4). | E2, E5 |
| D-10 | 2026-11-19 | C5 : Prophet | Clos | Tester d'abord Prophet pour juger de sa viabilité ; son intégration au projet (dépendance, module, bibliographie) ne sera discutée qu'ensuite. Précise D-04. **2026-11-27** : non testé, faute de temps ; abandonné (D-04). | E2 |
| D-11 | 2026-11-19 | Valeurs d'entrée des références | Décidé | Entrées = mesure publiée (`count_raw` si `is_observed`), sans les estimations d'E1 (J-7, année précédente) ni le masque rétrospectif `long_zero_run` ; les zéros mesurés restent des entrées. Option `values="e1_filled"` conservée pour l'étude des zéros avec E1. Motif : 5 234 horizons auraient été `ok` sur une estimation (E2-TECH-001). **2026-11-27** : appliqué à toutes les méthodes et à l'apprentissage ; les modèles refusent `--values e1_filled`. | E2, E1, E4 |
| D-12 | 2026-11-20 | Ablation par groupes de contexte | Décidé (A. Garoui) | Contexte découpé en `calendar` (fériés, vacances), `strikes`, `weather_forecast` ; `use_context=True` = tous, `context_groups` pour n'en garder qu'une partie. Permet de tester les fériés sans mélanger avec la météo. MOD-006 | E2 → E3 |
| D-13 | 2026-11-20 | Météo observée | Décidé (A. Garoui) | Jamais en entrée en `f1.0` (rôle `past_observation`) : réservée à l'analyse après coup ; seule la météo prévue J−2 sert. MOD-006 | E2 |
| D-14 | 2026-11-20 | Décalages des variables | Décidé provisoirement (A. Garoui) | Décalages en heures UTC, comme les références ; l'heure locale est une variable. I3 reste ouvert. MOD-006 | E2 |
| D-15 | 2026-11-20 | Identité du compteur | Décidé (A. Garoui) | Pas d'identifiant de compteur dans les variables ; niveaux récents à la place. Modèle partagé, réutilisable par E3. MOD-006 | E2, E3 |
| D-16 | 2026-11-20 | Compteurs d'apprentissage | Décidé (A. Garoui) | Les 97 `S_train` (`retained` + `robustness`) ; option `include_robustness=False` pour les 67 `retained`. MOD-006 | E2, E4 |
| D-17 | 2026-11-22 | Dates d'apprentissage | Décidé | Apprentissage depuis le début des données (16/10/2023, convenu avec E1), coupure `fit_cutoff` au 01/07/2026 pour toutes les méthodes. Non écrit dans `config/project.yaml` d'E4 (pas de date de début), et `PROTOCOLE_EVALUATION.md` indique encore le 11/10/2025. E2-TECH-002 coupe au 01/06 : à aligner. `TrainConfig.train_start` (None = début des données) porte ce choix. MOD-007 **2026-11-27** : E4 a ajouté `train_start: 2023-10-16` dans `config/project.yaml` ; tous les modèles apprennent depuis le début des données. | E2, E4 |
| D-18 | 2026-11-22 | Entrées du MLP | Décidé (Idir) | Normalisation de chaque exemple par la moyenne des heures mesurées de sa fenêtre de 168 h (comme DeepAR), masque des heures manquantes, entrées plafonnées à 10 fois le niveau ; la journée à prévoir donnée une seule fois, la météo prévue heure par heure ; heure implicite dans la position de la sortie. Exemple refusé si moins de 84 h mesurées ou niveau < 1 vélo/h (repli). MOD-007 | E2 |
| D-19 | 2026-11-23 | Perte du MLP et cibles extrêmes | Décidé (Esther), à confirmer par l'équipe | Perte L1 sur les seules vraies mesures, pondérée par le niveau de la fenêtre : on minimise l'erreur absolue en vélos/h, la métrique du projet (pondération par l'échelle, comme DeepAR). Pas de plafond sur les cibles extrêmes (0,74 % des exemples au-delà de 10 fois le niveau, jusqu'à 471 fois) : le gradient de la L1 ne dépend que du signe de l'erreur, ce qui borne leur influence (test dédié). Option `loss_weighting="none"` (erreur relative) gardée pour une comparaison. MOD-008 | E2 |
| D-20 | 2026-11-23 | Arrêt anticipé du MLP | Décidé (Esther), à confirmer par l'équipe | Origines des 4 dernières semaines avant `fit_cutoff` (dates locales : du 03/06 au 29/06 pour une coupure au 01/07), jamais la validation ; patience 8, 100 époques au plus ; réseau rendu = meilleure époque, sans réapprentissage sur ces semaines (choix simple, à rediscuter : ce sont les données les plus récentes). MOD-008 | E2 |
| D-21 | 2026-11-23 | Conditions d'utilisation du MLP | Décidé (Esther) | Origines à minuit (Paris) ; origine ≥ `fit_cutoff`, lue aussi dans le bilan du réseau ; latence du cas égale à celle de l'apprentissage (sinon `ValueError`) ; contexte complet si le modèle l'utilise. Tout autre cas reçoit un refus motivé (codes `mlp_*`), et le repli sur la référence revient à l'appelant (`predict.py`). MOD-008 | E2, E4, E5 |
| D-22 | 2026-11-23 | Une seule latence pour toutes les méthodes | Décidé (Esther), à valider par Idir | `train.fit` refuse une `publication_lag_hours` différente de la configuration : `backend.fit` ne la reçoit pas, et `build_training_frame` comme `build_windows` prennent celle de la configuration. Pour une sensibilité à 48 h, changer `protocol.publication_lag_hours` dans `config/project.yaml`. MOD-008 | E2, E4 |
| D-23 | 2026-11-24 | Reproductibilité des modèles | Décidé | Un modèle ne se reproduit à l'identique que sur la même machine et le même nombre de threads (contrôle MOD-013 : écart de 0,06 vélo/h, plus petit que l'écart entre graines). Le modèle servi est toujours celui déclaré d'avance par son `model_run_id`, jamais un réapprentissage ; la machine est notée dans `metadata.json` (`hardware`). MOD-013 **2026-11-27** : appliqué. Le modèle servi est toujours celui déclaré par son `model_run_id`. | E2, E4 |
| D-24 | 2026-11-24 | Modèles servis par défaut | Décidé (définitif) | Sans `model_run_id`, `mlp` sert `e2-mlp-ctx-20260701-s0-9ce9` et `hgb` sert `e2-hgb-ctx-20260701-s0-b357` (`DEFAULT_MODEL_RUN_IDS`), les versions déclarées dans EXP-E2-03. À revoir selon la règle de choix d'EXP-E2-03. MOD-014 **2026-11-27** : la règle de choix d'EXP-E2-03, appliquée aux scores officiels d'E4, retient le **HGB** pour l'application. Le MLP reste disponible. | E2, E5 |
| D-25 | 2026-11-24 | Propriété des dossiers | Décidé (toutes les équipes) | Chaque équipe ne modifie que ses fichiers : E1 `src/data/`, E2 `src/models/known/`, E3 `src/models/new/`, E4 `src/eval/`, E5 `src/app/`. Pour modifier le fichier d'une autre équipe, la prévenir et se coordonner avant. Les fichiers communs (racine, `src/models/schemas.py`) se modifient après accord. MOD-014 | toutes |
| D-26 | 2026-11-24 | Gel d'EXP-E2-03 | Décidé (équipe E2) | Règle de choix : au moins 5 % de mieux que la meilleure référence et meilleur sur plus de la moitié des compteurs ; entre MLP et HGB, écart plus grand que l'étendue entre graines, sinon HGB ; MLP graine 0. HGB : `absolute_error`, `categorical=False`, `refit_on_holdout=False`, `max_iter=2000`. Pas de réapprentissage au 01/08. Score par E4 (`Metric.py`). [Fiche](../experiments/EXP-E2-03.md) | E2, E4, E5 |

---

## 7. Expériences et résultats

Chaque expérience a sa fiche dans `reports/experiments/` (gabarit [experiment.md](../../doc/templates/experiment.md)). Ne remplir les colonnes de résultats qu'avec des valeurs issues de `scores.csv` d'E4.

| ID | Date | Question | Variantes comparées | Protocole / snapshot | MAE macro | Cas complets / attendus | Coût | Conclusion | Fiche |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E2-TECH-001 | 2026-11-19 | Essai technique : chaîne complète sur données réelles (pas de comparaison) | `weekly_naive`, `weekly_profile_median` | `proto-v0` (non validé) / `hist-20261117`, bloc validation | non calculée (E4) | 10 858 / 10 858 pour chaque variante | ≈ 2 min pour 10 858 cas, CPU portable | Chaîne fonctionnelle ; 6,2 % / 3,5 % d'horizons en repli | [fiche](../experiments/E2-TECH-001.md) |
| E2-TECH-002 | 2026-11-20 | Essai technique : jeu d'apprentissage des variables `f1.0` (pas de modèle) | sans objet | aucun (`fit_cutoff` 01/06/2026 provisoire) / `hist-20261117` | sans objet | 87 826 couples, 2 075 614 lignes | 204 s, 374 Mo | Variables sans fuite, chemins identiques ; prêtes pour un modèle | [fiche](../experiments/E2-TECH-002.md) |
| E2-TECH-003 | 2026-11-23 | Essai technique : premier apprentissage du MLP sur données réelles (pas de comparaison) | `mlp` avec contexte, graine 0 | aucun protocole validé (`fit_cutoff` 01/07/2026, D-17) / `hist-20261117` | non calculée (E4) | 5 694 / 6 014 cas de validation servis par le MLP (94,7 %) | apprentissage 33 s, 1,25 Go, CPU | Apprentissage sans fuite et rapide ; contrôle interne sur juin, hors scores E4 (voir fiche) ; 4 sites en panne pendant la validation | [fiche](../experiments/E2-TECH-003.md) |
| E2-TECH-004 | 2026-11-24 | Essai technique : premier apprentissage du HGB sur données réelles (pas de comparaison) | `hgb` avec contexte, `absolute_error`, graine 0 | aucun protocole validé (`fit_cutoff` 01/07/2026, D-17) / `hist-20261117` | non calculée (E4) | couverture de la validation non mesurée | 278 s au total, dont 125 s pour les deux apprentissages HGB ; CPU | Apprentissage sans fuite ; 342 arbres ; contrôle interne sur juin, hors scores E4 (voir fiche) ; loss à fixer par E4 | [fiche](../experiments/E2-TECH-004.md) |
| EXP-E2-03 | 2026-11-24 | Quelle méthode pour les sites connus ? **Figée le 2026-11-24 (équipe)** | `reference`, `reference_profile`, `mlp` (graine 0, + graines 1-2 pour la variabilité), `hgb` | `proto-v1` (non validé) / `hist-20261117`, validation | à venir (E4) | HGB 22,25 ; MLP 22,23 (graines 0-2 : étendue 0,36) ; `reference_profile` 27,01 ; `reference` 29,75 (**provisoire**, code d'E4) | 6 014 / 6 014 pour toutes | 2 à 3 min par modèle en bloc | HGB retenu (règle D-26) ; à confirmer par E4 | [fiche](../experiments/EXP-E2-03.md) |
| EXP-E2-04 | 2026-11-24 | Le contexte aide-t-il nos modèles ? **Brouillon, non figé** | MLP et HGB, chacun avec et sans contexte (même méthode, même graine) | `proto-v1` (non validé) / `hist-20261117`, validation | à venir (E4) | 6 014 attendus | à mesurer | à venir | [fiche](../experiments/EXP-E2-04.md) |
| EXP-E2-05 | 2026-11-24 | Apprendre avec des fenêtres masquées rend-il le MLP plus robuste ? **Figée pour le code ; modèles B appris** (Idir) | MLP actuel (seuil 84 h et 24 h) contre MLP masqué (3 graines), référence | `proto-v1` (non validé) / `hist-20261117`, validation naturelle et dégradée | à venir (E4) | 6 014 attendus par niveau | B : environ 45 s d'apprentissage par graine | à venir | [fiche](../experiments/EXP-E2-05.md) |

---

## 8. Échanges avec les partenaires

| Date | Équipe | Objet | Résultat / preuve d'usage |
| --- | --- | --- | --- |
| 2026-11-27 | E1, E4 | **Décalage de 2 h dans les mesures** : les 9, 10, 13 et 15 juillet 2026, environ 90 compteurs sur 97 ont un profil horaire avancé de 2 h (le pic du matin à 7 h au lieu de 9 h), et environ la moitié le 16 juillet. Détecté par corrélation avec le profil médian des jours ouvrés | **À transmettre** à E1 (source ou extraction : 2 h, c'est le décalage UTC/Paris en été) et à E4 (effet sur toutes les méthodes, y compris les références). Ce n'est pas corrigé côté E2 : ce sont les vraies données de l'instantané. |
| 2026-11-25 | E4 | Notation des prévisions d'EXP-E2-03 (zip livré) | **Preuve d'usage** : `data/evaluation/proto-v1/EXP-E2/scores.csv`, `scores_by_counter.csv` et `coverage.csv` sur `dev`. Les valeurs sont identiques à notre score (MOD-018). |
| 2026-11-25 | E3, E4, E5 | Message commun : `Team2` saine sur `dev`, prévisions d'EXP-E2-03 livrées, HGB retenu, `predict_24h` avec `hgb` / `mlp` et contexte | E4 a noté les prévisions ; E5 : HGB par défaut (`DEFAULT_MODEL_RUN_IDS`). |
| 2026-11-24 | Toutes | Retour arrière de `dev` sur `31252da` (commit E5 `fdc06c1` retiré), règle de propriété des dossiers (D-25) | `Team2` reconstruite sans `fdc06c1` (MOD-014) ; les contrôles d'éligibilité proposés par E5 sont réécrits dans `predict.py`. Fusion `Team2` → `dev` à faire avec E5. |
| 2026-11-24 | E4 | Lecture de `src/eval/Metric.py` (branche `Team4`, `7a5c3e0`) pour EXP-E2-03 | Même masque, intersection commune et MAE macro présents. **À demander** : version de référence et arrivée sur `dev` ; biais dans la moyenne globale ; accord sur une version « brute » des prévisions (heures `fallback` marquées `unavailable`). |
| 2026-11-24 | E3 | Chargement du MLP E2 dans `src/models/new/` | Sur `Team3` : `train.load_model` appelé sans importer `neural` (`KeyError` vérifié) et `manager` non importé dans `adapt.py` ; toujours présents sur le `dev` propre (`8e46f63`), ainsi que le test `test_new_predict.py::test_unimplemented_model_variants_load_then_raise[team2-adapted]` en échec. **À transmettre** (leur dossier, D-25) ; conditions du MLP (84 h sur 168 h, budgets 24 et 72 h refusés) ; versions sans contexte disponibles. |
| 2026-11-23 | E2 (Idir, Ania) | MOD-008 : contrôle de la latence dans `train.fit` (D-22), format 2 de `weights.pt`, test « pas encore entraînable » remplacé | **À transmettre** ; retour à consigner. |
| 2026-11-23 | E4, E5 | Codes de refus `mlp_*` (D-21), couverture du MLP sur la validation (94,7 %, 4 sites en panne), coût par cas (0,39 s) contre 3,2 s en bloc (E2-TECH-003) | **À transmettre** avant le branchement dans `predict.py`. |
| 2026-11-23 | E3 | MLP sans identifiant de compteur, sites E3 exclus (`excluded_site_groups` de `metadata.json`), réutilisable comme base apprise ailleurs | **À présenter** (D-05). |
| 2026-11-19 | E1 | Réception de `hist-20261117` (merge `origin/Team1`) | Empreintes vérifiées contre le manifeste ; données utilisées par E2-TECH-001. À discuter : D-11 (E2 n'utilise pas les valeurs estimées comme entrées des références). |
| 2026-11-22 | E4 | Lecture de `proto-v1/cases.csv` (branche `Team4`) | 6 014 cas de validation et 4 365 de test `known_site` sur 97 compteurs ; les 3 écarts de `proto-v0` sont corrigés. À demander : une date de début d'apprentissage dans `project.yaml` (D-17). |
| 2026-11-22 | E1 | Contrôle indépendant de `hist-20261117` (MOD-007) | Données saines depuis 2023. À signaler : 29 heures > 1 500 vélos/h sur 5 compteurs gardées comme cibles (par exemple 8 190 à 5 h, rue Lecourbe NE-SO). |
| 2026-11-22 | E5 | Lecture de `prediction_validation.py` (branche `Team5-integration`) | **À transmettre** : `verifier_valeurs` refuse les valeurs vides, alors qu'une heure sans prévision a `y_pred` vide (jamais 0) avec le statut `unavailable`. |
| 2026-11-19 | E4 | Lecture de `proto-v0/cases.csv` (branche `Team4-sher`, `2ac02dd`) | Utilisé par E2-TECH-001. **Écarts à transmettre** : (1) 2 compteurs réservés `S_dev_new` par E1 figurent en `known_site` / `S_train` (244 cas écartés par E2) ; (2) `snapshot_id = flux-20261115` au lieu de `hist-20261117` ; (3) validation à partir du 01/06/2026 alors que le protocole proposé indique juillet–août ; 89 compteurs connus contre 97 `S_train` chez E1. |

---

## 9. Matière pour le rapport final

Notes à enrichir au fil du projet ; elles serviront directement à la rédaction.

- **Question et périmètre** : sites connus, prévision 24 h, information disponible à l'origine uniquement (latence simulée J−1).
- **Choix d'architecture** : interface unique `ForecastInputs → ForecastResult` partagée E2/E3, registre de méthodes avec repli déclaré, séparation sortie brute / résultat système après repli (CONTRATS §7).
- **Garanties de causalité** : jointure par timestamp, `available_at <= origin`, `fit_cutoff < origin`, labels joints séparément, sites réservés exclus par `site_group_id`.
- **Référence** : naïf hebdomadaire 168 h ; justification : saisonnalité hebdomadaire des passages vélo, recalculable sans apprentissage. Seconde référence : médiane des 4 mêmes heures des semaines précédentes, moins sensible à une journée atypique (MOD-004). Prophet écarté comme référence : non vérifiable à la main, ajustement par cas, historique long nécessaire.
- **Méthodes et ablations** :
  - MLP compact (73 368 paramètres) : il lit la dernière semaine publiée, normalisée par son niveau (comme DeepAR), et prévoit les 24 heures d'un coup (MOD-007, MOD-008, D-18 à D-21) ;
  - apprentissage : perte L1 pondérée par le niveau, donc erreur en vélos/h, et arrêt anticipé sur les 4 semaines avant la coupure ;
  - premier apprentissage réel en 33 s sur CPU (E2-TECH-003) ;
  - ablation avec et sans contexte prévue (EXP-E2-03).

  _À compléter._
- **Résultats, limites, coûts** : _à compléter (citer `scores.csv`)_.
- **Ce qui n'a pas marché et pourquoi** : _à compléter - une absence de gain est une conclusion valable_.

---

## 10. Incohérences relevées et suivi

Revue du 2026-11-19 (MOD-002) des squelettes E2 face au [sujet](../../ParisPulse_Sujet_etudiants.pdf), au [plan](../../PLAN_PROJET.md), aux [contrats](../../doc/CONTRATS.md), au [protocole](../../doc/PROTOCOLE_EVALUATION.md), à l'[architecture](../../doc/ARCHITECTURE.md) et aux gabarits. Mettre à jour le statut et le renvoi `MOD-NNN` à chaque traitement ; ne pas supprimer une ligne traitée.

Statuts : ✅ corrigé · ⏸️ reporté (décision prise) · 🔲 à traiter.

### Critiques

| ID | Incohérence | Référence | Décision | Statut |
| --- | --- | --- | --- | --- |
| C1 | « y_pred nul » et « cibles nulles » : confusion possible entre zéro et manquant. Un 0 rendrait le cas complet et fausserait la MAE ; exclure les zéros contredit le sujet. | Sujet p. 3 ; CONTRATS §7 | Appliquer la correction : manquant = NaN, zéro observé conservé. | ✅ MOD-002 |
| C2 | L'ablation calendrier n'est pas isolée : fériés et vacances dans `calendar_features`, alors que `use_context` ne coupe que `context_features`. | Sujet p. 6 ; plan §5 | Appliquer la correction : fériés et vacances déplacés dans `context_features`. | ✅ MOD-002 |
| C3 | `counts.csv` n'a ni `available_at` ni `site_group_id` : `build_inputs` et `exclude_reserved_sites` ne peuvent pas être codées telles quelles ; latence fixée à 24 h en dur au lieu de `config/project.yaml`. | CONTRATS §3, §5 ; gabarit `counts.csv` | Attendre la version finale des données avant de choisir (D-08). | ⏸️ **Limite gardée** (2026-11-27) : `available_at` toujours absent ; latence fixe de 24 h lue dans la configuration, appliquée partout (`interval_end <= origin − 24 h`). Écrit dans les limites du rapport. |
| C4 | Deux points d'entrée (`predict_24h(case, history, …)` et `ForecastMethod(inputs, variant)`), ambiguïté sur qui filtre l'historique, routage en double (`predict_24h` et `select_method`), alors que le sujet confie l'implémentation du routage à E5. | Sujet p. 9 ; CONTRATS §9 | Signature exigée par E5 ; la cohérence sera traitée plus tard (D-09). MOD-011 / MOD-014 : `predict_24h` choisit le modèle et le repli (`trained_forecast`, `eligibility_reason`) ; `registry.py` reste non implémenté et inutilisé. À trancher avec E5 : registre comme couche de routage au-dessus de `predict_24h`, ou suppression. | ✅ **Clos** (2026-11-27) : `predict_24h` est le seul point d'entrée utilisé (E3, E5) ; le choix du modèle et le repli sont dans `trained_forecast` / `eligibility_reason`. `registry.py` (fichier commun) n'est pas utilisé : proposition à E5 de le retirer. |
| C5 | Prophet non déclaré dans `pyproject.toml` (calcul non reproductible par l'enseignant), absent de la bibliographie, placé dans `baseline.py`, et ne compte pas comme expérience DL. | Sujet p. 2, 4, 10 | Tester d'abord sa viabilité ; intégration discutée ensuite (D-10). | ✅ **Clos** (2026-11-27) : Prophet abandonné, `prophet_reference` retiré (MOD-018). |

### Importantes

| ID | Incohérence | Référence | Statut |
| --- | --- | --- | --- |
| I1 | `schemas.py` est dans `src/models/` alors que le contrat commun relève de `src/common/contracts.py` ; risque de divergence si E4 ou E5 définissent leur propre `Case`. | ARCHITECTURE §5 ; D-01 | ⏸️ **Limite gardée** (2026-11-27) : `schemas.py` sert de contrat de fait à E2, E3 et E5 ; le déplacer casserait leurs imports (fichier commun, D-25). |
| I2 | `TrainedModel` ne suit pas `model_metadata.example.json` : noms différents (`donor_site_groups`, `label_interval`, `train_seconds`) ; il manque `excluded_site_groups` (preuve attendue par E3), `weights_sha256`, `minimum_history_hours`, `supported_scenarios`, `fallback`. | CONTRATS §6 ; gabarit métadonnées | ✅ MOD-007 : `TrainedModel` complété, `metadata.json` écrit avec tous les champs du gabarit (vérifié par un test) |
| I3 | Référence décalée de 168 h UTC, mais repli en heure locale, et le plan dit « même heure une semaine avant » : décalage d'une heure en semaine de changement d'heure. Règle à choisir, documenter et tester. | Plan §7 ; PROTOCOLE §2 | ⏸️ **Limite gardée** (2026-11-27) : décalages en UTC (D-14) ; les semaines de changement d'heure (fin mars, fin octobre) décalent la référence d'une heure. Hors validation (juillet-août) ; le test (octobre-novembre) contient le 25/10 : écrit dans les limites. |
| I4 | `MIN_HISTORY_HOURS = 168` est ambigu : avec 24 h de latence, il faut la fenêtre [origin − 168 h, origin − 145 h], pas « 168 h d'historique ». Utilisée par `check_eligibility`, elle refuserait la référence alors que son repli peut répondre. | Sujet p. 2 (méthode simple toujours utilisable) | ✅ **Clos** (2026-11-27) : constante inutilisée retirée de `baseline.py` ; la fenêtre réelle est celle de `build_inputs` / `visible_week` (168 h finissant à origin − 24 h). |
| I5 | MOD-001 concluait « aucune incohérence critique » et a été vérifiée avec Python 3.13 au lieu de 3.11 ; ruff non exécuté. | Règles de ce fichier | ✅ Conclusion corrigée par MOD-002 ; Python 3.11 et ruff utilisés depuis MOD-003, `ruff format --check` sans problème depuis MOD-006 |

### Mineures

| ID | Incohérence | Statut |
| --- | --- | --- |
| M1 | `check_eligibility` exige `fit_cutoff < origin`, le protocole admet `<=` (un modèle gelé au 01/09 00:00 serait refusé pour l'origine du 01/09 00:00) ; `MethodSpec.fit_cutoff` est une chaîne au lieu d'un `Timestamp`. Le §9 de ce fichier reprend aussi `<`. | ✅ **Clos** (2026-11-27) : la règle appliquée est celle du protocole (`eligibility_reason` et `predict_mlp` refusent seulement `origin < fit_cutoff`). `check_eligibility` n'existe plus que dans `registry.py`, non utilisé (C4). |
| M2 | `ForecastInputs.information_cutoff` mal défini : comparé à `available_at` (= `origin`) ou à `interval_end` (= `origin − latence`) selon les docstrings. Lié à C3. | ⏸️ **Limite gardée** (2026-11-27) : `information_cutoff = origin − latence`, comparé à `interval_end`, appliqué partout ; à revoir si E1 ajoute `available_at` (C3). |
| M3 | Expérience deep learning non planifiée concrètement dans le squelette (D-05 ouvert), alors qu'elle est obligatoire. | ✅ **Clos** (2026-11-27) : expérience de deep learning faite : MLP comparé dans EXP-E2-03 (noté par E4) et EXP-E2-05. |

### Points vérifiés cohérents

`FORECAST_COLUMNS` et `CASE_RUNS_COLUMNS` identiques aux gabarits ; champs de `Case` identiques à `cases.csv` ; `target_timestamps` conforme (24 h écoulées UTC) ; note de latence de `baseline.py` exacte (donnée de h = 24 disponible à origin − 120 h) ; jointure par timestamp, exclusion par `site_group_id` et préservation du test final prévues.

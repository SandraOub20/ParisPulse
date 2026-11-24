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

_Dernière mise à jour : 2026-11-24 - MOD-014._

| Étape (README E2) | État | Renvoi |
| --- | --- | --- |
| 0. Revue de cohérence sujet / architecture / contrats / `src/models` | 🟡 Revue faite, incohérences en partie traitées (§10) | MOD-001, MOD-002 |
| 0. Squelette de code `src/models` (signatures, types, docstrings) | ✅ Fait | MOD-001 |
| 1. Série réelle E1 + origine et données autorisées E4 | 🟡 `hist-20261117` d'E1 reçu et vérifié ; `proto-v1` d'E4 (branche `Team4`) corrige les 3 écarts de `proto-v0`, protocole toujours « proposed » (§8) | MOD-005, MOD-007 |
| 2. Référence 168 h + repli causal (`baseline.py`) | ✅ Codée et testée sur cas synthétique ; repli N = 4 provisoire (D-03) ; seconde référence médiane 4 semaines | MOD-003, MOD-004 |
| 3. Vérification manuelle + raccord E4/E5 | 🟡 Vérifié à la main sur cas synthétique et sur 11 valeurs réelles ; consommation par E4/E5 à obtenir | MOD-003, MOD-005 |
| 4. Variables communes (`features.py`) | 🟡 `f1.0` codée, testée, jeu d'apprentissage réel construit (E2-TECH-002) ; à présenter à E3 et E1 | MOD-006 |
| 5. Méthode justifiée + variante explicative (`train.py`) | 🟡 Socle commun `train.py` fait et testé (`fit`, sauvegarde, chargement) ; MLP : apprentissage (`fit_mlp`) et prévision (`predict_mlp`) faits et testés, premier apprentissage réel (E2-TECH-003) ; HGB (`tabular.py`) fait et testé, premier apprentissage réel (E2-TECH-004), loss à fixer par E4 ; 3 graines du MLP et versions sans contexte apprises ; fiches [EXP-E2-03](../experiments/EXP-E2-03.md) (méthodes) et [EXP-E2-04](../experiments/EXP-E2-04.md) (contexte) en brouillon, à figer avant les scores | MOD-007, MOD-008, MOD-010, MOD-012, MOD-013 |
| 6. Calcul exécutable et exports, recalcul autre origine (`predict.py`) | 🟡 Chaîne complète et commande `python -m src.models.known.predict` ; 10 858 cas de validation calculés (E2-TECH-001) ; recalcul par E5 à faire ; variantes `mlp` et `hgb` branchées avec repli sur la référence, vérifiées sur 25 cas réels (calcul complet après la fiche EXP-E2-03) ; réconcilié avec le branchement MLP d'E5 (une seule implémentation, contrôles d'éligibilité, modèles par défaut D-24) ; fusion vers `dev` à faire avec E5 | MOD-003, MOD-005, MOD-008, MOD-011, MOD-014 |
| 7. Cas difficile, extension, test final après gel | 🔲 | - |

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
    mlp_forecast.py points d'entrée MLP de l'application (E5) et d'E3 : load_mlp_artifact,
                    infer_mlp, predict_trained_mlp (délègue à trained_forecast) (MOD-014)
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

### MOD-014 - 2026-11-24 - Réconciliation avec le branchement MLP d'E5 sur `dev` (une seule implémentation pour `mlp` et `hgb`)

- **Auteur** : Idir, avec l'accord de Sandra (E5).
- **Branche / commit** : `Team2-idir` / `fe2903b` (fusion de `origin/dev`, qui contient `fdc06c1`).
- **Quoi** :
  - Sur `dev`, E5 avait branché le MLP dans `predict.py` en parallèle de MOD-011, avec `src/models/known/mlp_forecast.py` (utilisé par l'application et par E3). Conflit résolu avec **une seule implémentation**, `predict.trained_forecast`, pour le MLP et le HGB.
  - Repris d'E5 dans `trained_forecast` : contrôles avant prévision (`eligibility_reason`) étendus au HGB : instantané, origine avant la coupure, site connu absent de l'apprentissage, nouveau site non confirmé réservé, version du contexte. Codes `mlp_*` / `hgb_*` : `_snapshot_incompatible`, `_origin_before_fit_cutoff`, `_site_not_in_training`, `_site_not_confirmed_reserved`, `_context_missing`, `_context_incompatible`, `_inputs_incompatible`. `status_reason` contient exactement le code de refus, pour le cas et pour chaque horizon.
  - Conservé pour l'application et E3, sans changement d'appel : `MLP_VARIANT`, `SUPPORTED_VARIANTS` (avec `hgb`), `mlp_forecast.MLP_MODEL_RUN_ID`, `load_mlp_artifact`, `infer_mlp`, `predict_trained_mlp`. Cette dernière délègue maintenant à `trained_forecast`.
  - `model_run_id` n'est plus obligatoire : modèles par défaut `DEFAULT_MODEL_RUN_IDS` (D-24). Option `--context` de la commande reprise d'E5.
- **Pourquoi** : éviter deux implémentations de la même variante et donner le HGB à l'application et à E3.
- **Fichiers** : [predict.py](../../src/models/known/predict.py), [mlp_forecast.py](../../src/models/known/mlp_forecast.py), [test_known_predict_trained.py](../../tests/test_known_predict_trained.py), [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md), ce fichier.
- **Impact partenaires / contrats** : E5 et E3 : rien à changer ; `hgb` est disponible dans `SUPPORTED_VARIANTS`. Les codes de refus d'éligibilité valent désormais aussi pour le HGB. Le `method_run_id` par défaut d'une variante entraînée est le `model_run_id` (E5 utilisait `<model_run_id>-inference`).
- **Vérifications effectuées** :
  - `pytest -q` : 388 passés, dont les tests d'E5 et d'E3 (`test_known_predict.py`, `test_new_predict.py`) inchangés. Tests E2 adaptés aux contrôles d'éligibilité, plus 9 cas d'éligibilité. `ruff check` sans problème sur les fichiers E2.
  - Vrais cas de validation (cibles non lues) avec les modèles par défaut : site normal, MLP et HGB `ok` ; site `100047545`, MLP `fallback` (`mlp_window_too_sparse`), HGB `ok` ; sans contexte, `fallback` avec `mlp_context_missing`.
- **Points ouverts** : D-24 à confirmer après EXP-E2-03 (le modèle de l'application suit sa règle de choix).

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

Prioriser dans l'ordre. Cocher avec le renvoi `MOD-NNN` uniquement une fois vérifié.

### Immédiat (première matinée)

- [ ] Mettre `uv` à jour, lancer `./run.sh check` et `ruff` sur `src/models`.
- [ ] Faire adopter (ou amender) `schemas.py` par E1/E3/E4/E5 puis le migrer dans `src/common/contracts.py`.
- [x] Obtenir d'E1 un premier `counts.csv` réel et d'E4 un premier `cases.csv`. MOD-005 (`cases.csv` provisoire, `proto-v0`)
- [x] Implémenter `lookup_lagged` (jointure par timestamp, pas par position). MOD-003
- [x] Implémenter `fallback_value` (règle provisoire N = 4, à figer, cf. D-03) et `weekly_reference`. MOD-003
- [x] Implémenter `ForecastResult.is_complete`, `to_forecast_frame`, `to_run_row`. MOD-003
- [x] Implémenter `build_inputs`, `assert_causal`, `predict_24h` (variantes `reference`, `reference_profile`). MOD-005
- [x] Vérifier 3 à 5 valeurs à la main sur un petit cas construit (zéro observé, heure absente, changement d'heure). MOD-003
- [x] Formater [registry.py](../../src/models/registry.py) (`ruff format`), seul fichier qui fait encore échouer `./run.sh check`. MOD-006
- [x] Produire un premier `.pred.csv` / `.runs.csv` sur données réelles. MOD-005 (E2-TECH-001)
- [ ] Le faire consommer par E4 (score) et E5 (affichage) : preuve d'usage à consigner au §8.
- [ ] Transmettre à E4 les 3 écarts de `proto-v0` (§8) et recalculer sur la version corrigée.

### Étude principale

- [x] `features.py` : calendrier de base (heure locale, jour), contexte (fériés, vacances, météo admissible), lags, profils, masques de manque ; `FEATURE_VERSION` incrémentée à chaque changement. MOD-006 (`f1.0`, E2-TECH-002)
- [ ] Présenter les variables `f1.0` et les nouvelles signatures à E3 (bibliothèque partagée) et à E1 (lecture de `context.csv`) ; consigner leur retour au §8.
- [ ] Tester Prophet hors intégration (viabilité, coût par cas) avant toute discussion d'ajout au projet (D-10).
- [ ] Traiter les incohérences restantes du §10 (C3 après version finale des données, C4 avec E5, I1–I5, M1–M3).
- [ ] Choisir une méthode justifiée par la bibliographie (statistique, tabulaire, réseau compact, modèle partagé...). Comparaison préparée : [EXP-E2-03](../experiments/EXP-E2-03.md) (brouillon, MOD-012).
- [ ] Ablation : même modèle avec / sans calendrier ou météo, réglages figés avant le test. Modèles sans contexte appris et fiche [EXP-E2-04](../experiments/EXP-E2-04.md) en brouillon (MOD-013) ; par groupe : HGB seulement (D-12).
- [x] `train.py` : `exclude_reserved_sites` (par `site_group_id`), `fit`, `save_model` avec `metadata.json` + SHA-256. MOD-007
- [x] Brancher le HGB sur `train.fit` (`register_backend("hgb", …)`). MOD-009 (squelette), MOD-010 (implémentation, premier apprentissage réel)
- [x] MLP : `fit_mlp` (perte MAE sur les cibles mesurées, arrêt anticipé sur les 4 semaines avant `fit_cutoff`, cibles extrêmes) et `predict_mlp` (proposés à Esther). MOD-008 (E2-TECH-003)
- [x] `predict.py` : variantes `mlp` et `hgb` (modèle chargé une fois, repli sur la référence). MOD-011
- [ ] Désigner le `model_run_id` utilisé par l'application (avec E5). Provisoire : modèles par défaut (D-24, MOD-014), à revoir selon EXP-E2-03.
- [ ] Fusionner `Team2` dans `dev` avec E5 (PR) : sans conflit depuis MOD-014.
- [ ] Confirmer avec Ania le plafond `max_iter=2000` du HGB, puis supprimer les modèles écartés `e2-hgb-noctx-20260701-s0-409c` et `e2-hgb-ctx-20260701-s0-8b7a` (MOD-013).
- [ ] Fiche EXP-E2-05 (Idir) : MLP appris avec ou sans masquage des fenêtres, sur les historiques incomplets ; écrite avant le code.
- [ ] Présenter MOD-008 à Idir et Ania (contrôle de latence dans `train.fit`, format 2), à E3 (réseau réutilisable), à E4/E5 (codes `mlp_*`, couverture) ; consigner leur retour au §8.
- [x] MLP : apprendre 3 graines pour mesurer la variabilité (contrôle de juin : étendue 0,29 vélo/h). MOD-013 ; la variabilité sur la validation sera lue avec EXP-E2-03.
- [ ] Fiche EXP-E2-03 (MLP contre HGB contre références) avec les décisions figées avant les scores. Brouillon : MOD-012 ; 5 points à trancher en équipe.
- [ ] Enregistrer la référence et les modèles dans le registre (`register_defaults`).
- [ ] Recalcul de la référence sur une autre origine avec E5 (`use_cache=False`).

### Approfondissement et extension

- [ ] Étudier un cas difficile (faibles volumes, météo manquante, rupture, historique incomplet) et une modification ciblée avec son coût.
- [ ] Étendre aux compteurs admissibles ; reporter prévisions non produites et coûts.
- [ ] Mesurer le test final **après gel** des choix.
- [ ] Fiches d'expérience dans `reports/experiments/`, rapport d'équipe final.

---

## 6. Décisions et points ouverts

| ID | Date | Sujet | Statut | Décision / question | Qui |
| --- | --- | --- | --- | --- | --- |
| D-01 | 2026-11-19 | Contrats communs | Ouvert | `src/common/contracts.py` est vide ; `schemas.py` proposé comme base. À valider avec les 5 équipes. | E2 → toutes |
| D-02 | 2026-11-19 | Signature `predict_24h` | Proposé | Signature imposée conservée ; ajout de `context=` (le contrat §5-6 prévoit un contexte admissible absent de la signature). | E2, E5 |
| D-03 | 2026-11-19 | Repli de la référence | Ouvert | Proposition : médiane même heure locale / même jour sur N semaines admissibles, puis moyenne même heure locale, sinon `unavailable`. Valeur de N à fixer. MOD-003 : implémenté avec N = 4 (moyenne sur 28 observations au second niveau), paramètre `fallback_weeks` ; à valider avec E4/E5. | E2, E4, E5 |
| D-04 | 2026-11-19 | Prophet | Proposé | Variante optionnelle seulement (`prophet_reference`), non déclarée dans `pyproject.toml`, jamais obligatoire. Ajout de la dépendance à décider. | E2 |
| D-05 | 2026-11-19 | Expérience deep learning | Proposé | Responsabilité E2 ou E3 à attribuer explicitement (ARCHITECTURE §6). `torch` disponible dans le groupe `dl` (CPU). MOD-007 : Idir porte un MLP compact sur CPU (préparation des données, réseau, sauvegarde) ; `fit_mlp` / `predict_mlp` proposés à Esther. Réutilisation possible par E3 comme base apprise ailleurs (sites E3 exclus, preuve dans `metadata.json`). À confirmer avec l'équipe et E3. MOD-008 : apprentissage et prévision écrits par Esther, premier essai réel (E2-TECH-003). | E2, E3 |
| D-06 | 2026-11-19 | Latence et décalage 168 h | Vérifié | Avec `publication_lag_hours = 24`, y(t−168 h) reste disponible pour les 24 horizons (dernière source disponible à origin − 120 h). | E2 |
| D-07 | - | Gel des choix avant test final | Ouvert | Date de gel à fixer avec E4 ; aucun réglage sur les dates réservées. | E2, E4 |
| D-08 | 2026-11-19 | C3 : `available_at`, latence et `site_group_id` | Reporté | Attendre la version finale des données d'E1 avant de choisir où calculer `available_at` et comment joindre `site_group_id`. MOD-005 : `hist-20261117` n'a toujours pas `available_at` dans `counts.csv` ; règle provisoire `interval_end <= origin − latence` appliquée dans `build_inputs` ; `site_group_id` lu dans `cases.csv`, sites connus filtrés sur `site_role = S_train` de `inventory_quality.csv`. | E2, E1 |
| D-09 | 2026-11-19 | C4 : origine de `predict_24h` | Décidé (origine) / Ouvert (cohérence) | La signature `predict_24h(case, history, variant)` est exigée par E5. Sa coexistence avec `ForecastMethod(inputs, variant)` et le double routage seront traités plus tard. | E2, E5 |
| D-10 | 2026-11-19 | C5 : Prophet | Décidé | Tester d'abord Prophet pour juger de sa viabilité ; son intégration au projet (dépendance, module, bibliographie) ne sera discutée qu'ensuite. Précise D-04. | E2 |
| D-11 | 2026-11-19 | Valeurs d'entrée des références | Proposé | Entrées = mesure publiée (`count_raw` si `is_observed`), sans les estimations d'E1 (J-7, année précédente) ni le masque rétrospectif `long_zero_run` ; les zéros mesurés restent des entrées. Option `values="e1_filled"` conservée pour l'étude des zéros avec E1. Motif : 5 234 horizons auraient été `ok` sur une estimation (E2-TECH-001). | E2, E1, E4 |
| D-12 | 2026-11-20 | Ablation par groupes de contexte | Décidé (A. Garoui) | Contexte découpé en `calendar` (fériés, vacances), `strikes`, `weather_forecast` ; `use_context=True` = tous, `context_groups` pour n'en garder qu'une partie. Permet de tester les fériés sans mélanger avec la météo. MOD-006 | E2 → E3 |
| D-13 | 2026-11-20 | Météo observée | Décidé (A. Garoui) | Jamais en entrée en `f1.0` (rôle `past_observation`) : réservée à l'analyse après coup ; seule la météo prévue J−2 sert. MOD-006 | E2 |
| D-14 | 2026-11-20 | Décalages des variables | Décidé provisoirement (A. Garoui) | Décalages en heures UTC, comme les références ; l'heure locale est une variable. I3 reste ouvert. MOD-006 | E2 |
| D-15 | 2026-11-20 | Identité du compteur | Décidé (A. Garoui) | Pas d'identifiant de compteur dans les variables ; niveaux récents à la place. Modèle partagé, réutilisable par E3. MOD-006 | E2, E3 |
| D-16 | 2026-11-20 | Compteurs d'apprentissage | Décidé (A. Garoui) | Les 97 `S_train` (`retained` + `robustness`) ; option `include_robustness=False` pour les 67 `retained`. MOD-006 | E2, E4 |
| D-17 | 2026-11-22 | Dates d'apprentissage | Proposé | Apprentissage depuis le début des données (16/10/2023, convenu avec E1), coupure `fit_cutoff` au 01/07/2026 pour toutes les méthodes. Non écrit dans `config/project.yaml` d'E4 (pas de date de début), et `PROTOCOLE_EVALUATION.md` indique encore le 11/10/2025. E2-TECH-002 coupe au 01/06 : à aligner. `TrainConfig.train_start` (None = début des données) porte ce choix. MOD-007 | E2, E4 |
| D-18 | 2026-11-22 | Entrées du MLP | Décidé (Idir) | Normalisation de chaque exemple par la moyenne des heures mesurées de sa fenêtre de 168 h (comme DeepAR), masque des heures manquantes, entrées plafonnées à 10 fois le niveau ; la journée à prévoir donnée une seule fois, la météo prévue heure par heure ; heure implicite dans la position de la sortie. Exemple refusé si moins de 84 h mesurées ou niveau < 1 vélo/h (repli). MOD-007 | E2 |
| D-19 | 2026-11-23 | Perte du MLP et cibles extrêmes | Décidé (Esther), à confirmer par l'équipe | Perte L1 sur les seules vraies mesures, pondérée par le niveau de la fenêtre : on minimise l'erreur absolue en vélos/h, la métrique du projet (pondération par l'échelle, comme DeepAR). Pas de plafond sur les cibles extrêmes (0,74 % des exemples au-delà de 10 fois le niveau, jusqu'à 471 fois) : le gradient de la L1 ne dépend que du signe de l'erreur, ce qui borne leur influence (test dédié). Option `loss_weighting="none"` (erreur relative) gardée pour une comparaison. MOD-008 | E2 |
| D-20 | 2026-11-23 | Arrêt anticipé du MLP | Décidé (Esther), à confirmer par l'équipe | Origines des 4 dernières semaines avant `fit_cutoff` (dates locales : du 03/06 au 29/06 pour une coupure au 01/07), jamais la validation ; patience 8, 100 époques au plus ; réseau rendu = meilleure époque, sans réapprentissage sur ces semaines (choix simple, à rediscuter : ce sont les données les plus récentes). MOD-008 | E2 |
| D-21 | 2026-11-23 | Conditions d'utilisation du MLP | Décidé (Esther) | Origines à minuit (Paris) ; origine ≥ `fit_cutoff`, lue aussi dans le bilan du réseau ; latence du cas égale à celle de l'apprentissage (sinon `ValueError`) ; contexte complet si le modèle l'utilise. Tout autre cas reçoit un refus motivé (codes `mlp_*`), et le repli sur la référence revient à l'appelant (`predict.py`). MOD-008 | E2, E4, E5 |
| D-22 | 2026-11-23 | Une seule latence pour toutes les méthodes | Décidé (Esther), à valider par Idir | `train.fit` refuse une `publication_lag_hours` différente de la configuration : `backend.fit` ne la reçoit pas, et `build_training_frame` comme `build_windows` prennent celle de la configuration. Pour une sensibilité à 48 h, changer `protocol.publication_lag_hours` dans `config/project.yaml`. MOD-008 | E2, E4 |
| D-23 | 2026-11-24 | Reproductibilité des modèles | Proposé (Idir) | Un modèle ne se reproduit à l'identique que sur la même machine et le même nombre de threads (contrôle MOD-013 : écart de 0,06 vélo/h, plus petit que l'écart entre graines). Le modèle servi est toujours celui déclaré d'avance par son `model_run_id`, jamais un réapprentissage ; la machine est notée dans `metadata.json` (`hardware`). MOD-013 | E2, E4 |
| D-24 | 2026-11-24 | Modèles servis par défaut | Décidé (Idir, avec Sandra/E5), provisoire | Sans `model_run_id`, `mlp` sert `e2-mlp-ctx-20260701-s0-9ce9` et `hgb` sert `e2-hgb-ctx-20260701-s0-b357` (`DEFAULT_MODEL_RUN_IDS`), les versions déclarées dans EXP-E2-03. À revoir selon la règle de choix d'EXP-E2-03. MOD-014 | E2, E5 |

---

## 7. Expériences et résultats

Chaque expérience a sa fiche dans `reports/experiments/` (gabarit [experiment.md](../../doc/templates/experiment.md)). Ne remplir les colonnes de résultats qu'avec des valeurs issues de `scores.csv` d'E4.

| ID | Date | Question | Variantes comparées | Protocole / snapshot | MAE macro | Cas complets / attendus | Coût | Conclusion | Fiche |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E2-TECH-001 | 2026-11-19 | Essai technique : chaîne complète sur données réelles (pas de comparaison) | `weekly_naive`, `weekly_profile_median` | `proto-v0` (non validé) / `hist-20261117`, bloc validation | non calculée (E4) | 10 858 / 10 858 pour chaque variante | ≈ 2 min pour 10 858 cas, CPU portable | Chaîne fonctionnelle ; 6,2 % / 3,5 % d'horizons en repli | [fiche](../experiments/E2-TECH-001.md) |
| E2-TECH-002 | 2026-11-20 | Essai technique : jeu d'apprentissage des variables `f1.0` (pas de modèle) | sans objet | aucun (`fit_cutoff` 01/06/2026 provisoire) / `hist-20261117` | sans objet | 87 826 couples, 2 075 614 lignes | 204 s, 374 Mo | Variables sans fuite, chemins identiques ; prêtes pour un modèle | [fiche](../experiments/E2-TECH-002.md) |
| E2-TECH-003 | 2026-11-23 | Essai technique : premier apprentissage du MLP sur données réelles (pas de comparaison) | `mlp` avec contexte, graine 0 | aucun protocole validé (`fit_cutoff` 01/07/2026, D-17) / `hist-20261117` | non calculée (E4) | 5 694 / 6 014 cas de validation servis par le MLP (94,7 %) | apprentissage 33 s, 1,25 Go, CPU | Apprentissage sans fuite et rapide ; contrôle interne sur juin, hors scores E4 (voir fiche) ; 4 sites en panne pendant la validation | [fiche](../experiments/E2-TECH-003.md) |
| E2-TECH-004 | 2026-11-24 | Essai technique : premier apprentissage du HGB sur données réelles (pas de comparaison) | `hgb` avec contexte, `absolute_error`, graine 0 | aucun protocole validé (`fit_cutoff` 01/07/2026, D-17) / `hist-20261117` | non calculée (E4) | couverture de la validation non mesurée | 278 s au total, dont 125 s pour les deux apprentissages HGB ; CPU | Apprentissage sans fuite ; 342 arbres ; contrôle interne sur juin, hors scores E4 (voir fiche) ; loss à fixer par E4 | [fiche](../experiments/E2-TECH-004.md) |
| EXP-E2-03 | 2026-11-24 | Quelle méthode pour les sites connus ? **Brouillon, non figé** | `reference`, `reference_profile`, `mlp` (graine 0, + graines 1-2 pour la variabilité), `hgb` | `proto-v1` (non validé) / `hist-20261117`, validation | à venir (E4) | 6 014 attendus | à mesurer | à venir | [fiche](../experiments/EXP-E2-03.md) |
| EXP-E2-04 | 2026-11-24 | Le contexte aide-t-il nos modèles ? **Brouillon, non figé** | MLP et HGB, chacun avec et sans contexte (même méthode, même graine) | `proto-v1` (non validé) / `hist-20261117`, validation | à venir (E4) | 6 014 attendus | à mesurer | à venir | [fiche](../experiments/EXP-E2-04.md) |

---

## 8. Échanges avec les partenaires

| Date | Équipe | Objet | Résultat / preuve d'usage |
| --- | --- | --- | --- |
| 2026-11-24 | E5 (Sandra) | Branchement MLP en double sur `dev` (`fdc06c1`, `mlp_forecast.py`) et MOD-011 sur `Team2` | Réconcilié avec son accord (MOD-014) : une seule implémentation, ses points d'entrée et ses tests conservés, HGB disponible pour l'application ; `method_run_id` par défaut = `model_run_id`. Fusion vers `dev` à faire ensemble. |
| 2026-11-24 | E4 | Lecture de `src/eval/Metric.py` (branche `Team4`, `7a5c3e0`) pour EXP-E2-03 | Même masque, intersection commune et MAE macro présents. **À demander** : version de référence et arrivée sur `dev` ; biais dans la moyenne globale ; accord sur une version « brute » des prévisions (heures `fallback` marquées `unavailable`). |
| 2026-11-24 | E3 | Chargement du MLP E2 dans `src/models/new/` | Sur `Team3` : `train.load_model` appelé sans importer `neural` (`KeyError` vérifié) et `manager` non importé dans `adapt.py` ; corrigés sur `dev` par E5. **À transmettre** : mettre `Team3` à jour depuis `dev` ; conditions du MLP (84 h sur 168 h, budgets 24 et 72 h refusés) ; versions sans contexte disponibles. |
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
| C3 | `counts.csv` n'a ni `available_at` ni `site_group_id` : `build_inputs` et `exclude_reserved_sites` ne peuvent pas être codées telles quelles ; latence fixée à 24 h en dur au lieu de `config/project.yaml`. | CONTRATS §3, §5 ; gabarit `counts.csv` | Attendre la version finale des données avant de choisir (D-08). | ⏸️ En partie levée (MOD-006) : `site_group_id` lu dans `inventory_quality.csv` par `training_counters`, latence lue dans la configuration ; `available_at` toujours absent |
| C4 | Deux points d'entrée (`predict_24h(case, history, …)` et `ForecastMethod(inputs, variant)`), ambiguïté sur qui filtre l'historique, routage en double (`predict_24h` et `select_method`), alors que le sujet confie l'implémentation du routage à E5. | Sujet p. 9 ; CONTRATS §9 | Signature exigée par E5 ; la cohérence sera traitée plus tard (D-09). MOD-011 / MOD-014 : `predict_24h` choisit le modèle et le repli (`trained_forecast`, `eligibility_reason`) ; `registry.py` reste non implémenté et inutilisé. À trancher avec E5 : registre comme couche de routage au-dessus de `predict_24h`, ou suppression. | ⏸️ |
| C5 | Prophet non déclaré dans `pyproject.toml` (calcul non reproductible par l'enseignant), absent de la bibliographie, placé dans `baseline.py`, et ne compte pas comme expérience DL. | Sujet p. 2, 4, 10 | Tester d'abord sa viabilité ; intégration discutée ensuite (D-10). | ⏸️ |

### Importantes

| ID | Incohérence | Référence | Statut |
| --- | --- | --- | --- |
| I1 | `schemas.py` est dans `src/models/` alors que le contrat commun relève de `src/common/contracts.py` ; risque de divergence si E4 ou E5 définissent leur propre `Case`. | ARCHITECTURE §5 ; D-01 | 🔲 |
| I2 | `TrainedModel` ne suit pas `model_metadata.example.json` : noms différents (`donor_site_groups`, `label_interval`, `train_seconds`) ; il manque `excluded_site_groups` (preuve attendue par E3), `weights_sha256`, `minimum_history_hours`, `supported_scenarios`, `fallback`. | CONTRATS §6 ; gabarit métadonnées | ✅ MOD-007 : `TrainedModel` complété, `metadata.json` écrit avec tous les champs du gabarit (vérifié par un test) |
| I3 | Référence décalée de 168 h UTC, mais repli en heure locale, et le plan dit « même heure une semaine avant » : décalage d'une heure en semaine de changement d'heure. Règle à choisir, documenter et tester. | Plan §7 ; PROTOCOLE §2 | 🔲 Écart rendu visible par le test de MOD-003 (repli à 11Z, valeur principale à 10Z) ; règle non tranchée. Les variables `f1.0` suivent l'UTC (D-14) |
| I4 | `MIN_HISTORY_HOURS = 168` est ambigu : avec 24 h de latence, il faut la fenêtre [origin − 168 h, origin − 145 h], pas « 168 h d'historique ». Utilisée par `check_eligibility`, elle refuserait la référence alors que son repli peut répondre. | Sujet p. 2 (méthode simple toujours utilisable) | 🔲 |
| I5 | MOD-001 concluait « aucune incohérence critique » et a été vérifiée avec Python 3.13 au lieu de 3.11 ; ruff non exécuté. | Règles de ce fichier | ✅ Conclusion corrigée par MOD-002 ; Python 3.11 et ruff utilisés depuis MOD-003, `ruff format --check` sans problème depuis MOD-006 |

### Mineures

| ID | Incohérence | Statut |
| --- | --- | --- |
| M1 | `check_eligibility` exige `fit_cutoff < origin`, le protocole admet `<=` (un modèle gelé au 01/09 00:00 serait refusé pour l'origine du 01/09 00:00) ; `MethodSpec.fit_cutoff` est une chaîne au lieu d'un `Timestamp`. Le §9 de ce fichier reprend aussi `<`. | 🔲 MOD-008 : `predict_mlp` applique la règle du protocole (refus si `origin < fit_cutoff`, donc `origin = fit_cutoff` admis) ; `check_eligibility` reste à corriger |
| M2 | `ForecastInputs.information_cutoff` mal défini : comparé à `available_at` (= `origin`) ou à `interval_end` (= `origin − latence`) selon les docstrings. Lié à C3. | 🟡 MOD-003 : `weekly_reference` compare `interval_end` à `information_cutoff` = `origin − latence` (provisoire, à confirmer avec D-08) |
| M3 | Expérience deep learning non planifiée concrètement dans le squelette (D-05 ouvert), alors qu'elle est obligatoire. | 🟡 MOD-007 : `neural.py` créé (données, réseau, sauvegarde) ; apprentissage à écrire. MOD-008 : apprentissage et prévision écrits et testés, premier apprentissage réel (E2-TECH-003) ; la comparaison (EXP-E2-03) reste à faire après validation du protocole, et D-05 à confirmer avec E3. MOD-011 à MOD-014 : MLP branché dans `predict.py` et utilisé par l'application et par E3 (« MLP E2 transféré ») ; 3 graines apprises ; EXP-E2-03 et EXP-E2-04 en brouillon |

### Points vérifiés cohérents

`FORECAST_COLUMNS` et `CASE_RUNS_COLUMNS` identiques aux gabarits ; champs de `Case` identiques à `cases.csv` ; `target_timestamps` conforme (24 h écoulées UTC) ; note de latence de `baseline.py` exacte (donnée de h = 24 disponible à origin − 120 h) ; jointure par timestamp, exclusion par `site_group_id` et préservation du test final prévues.

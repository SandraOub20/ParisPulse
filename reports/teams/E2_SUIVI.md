# Équipe 2 - Prévision sur sites connus : document de suivi

> ## ⚠️ À lire avant toute modification de ce fichier
>
> Ce document est la **source de vérité du travail de l'équipe 2** et la matière première du rapport final. Toute personne qui modifie du code, des données, des paramètres ou une décision de l'équipe 2 **doit le mettre à jour dans le même commit**. Pour qu'il reste cohérent :
>
> 1. **Une entrée par modification** dans le [§4 Journal des modifications](#4-journal-des-modifications), ajoutée **en haut** de la liste (la plus récente d'abord). Ne jamais réécrire ni supprimer une entrée passée : pour corriger, ajouter une nouvelle entrée qui renvoie à l'ancienne (`Corrige MOD-xxx`).
> 2. **Identifiant séquentiel** `MOD-NNN` (le suivant du plus grand existant), **date au format ISO** `AAAA-MM-JJ`, **auteur nommé**, branche et commit (hash court, ou `non commité` à remplacer ensuite).
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

_Dernière mise à jour : 2026-11-20 - MOD-006._

| Étape (README E2) | État | Renvoi |
| --- | --- | --- |
| 0. Revue de cohérence sujet / architecture / contrats / `src/models` | 🟡 Revue faite, incohérences en partie traitées (§10) | MOD-001, MOD-002 |
| 0. Squelette de code `src/models` (signatures, types, docstrings) | ✅ Fait | MOD-001 |
| 1. Série réelle E1 + origine et données autorisées E4 | 🟡 `hist-20261117` d'E1 reçu et vérifié ; cas `proto-v0` d'E4 provisoires, 3 écarts signalés (§8) | MOD-005 |
| 2. Référence 168 h + repli causal (`baseline.py`) | ✅ Codée et testée sur cas synthétique ; repli N = 4 provisoire (D-03) ; seconde référence médiane 4 semaines | MOD-003, MOD-004 |
| 3. Vérification manuelle + raccord E4/E5 | 🟡 Vérifié à la main sur cas synthétique et sur 11 valeurs réelles ; consommation par E4/E5 à obtenir | MOD-003, MOD-005 |
| 4. Variables communes (`features.py`) | 🟡 `f1.0` codée, testée, jeu d'apprentissage réel construit (E2-TECH-002) ; à présenter à E3 et E1 | MOD-006 |
| 5. Méthode justifiée + variante explicative (`train.py`) | 🔲 | - |
| 6. Calcul exécutable et exports, recalcul autre origine (`predict.py`) | 🟡 Chaîne complète et commande `python -m src.models.known.predict` ; 10 858 cas de validation calculés (E2-TECH-001) ; recalcul par E5 à faire | MOD-003, MOD-005 |
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
    train.py        TrainConfig, TrainedModel, exclude_reserved_sites, fit, compare_variants,
                    save_model/load_model
    predict.py      build_inputs, predict_24h (signature imposée), run_experiment,
                    write_predictions, write_runs
```

Flux prévu d'un cas :

```text
cases.csv (E4) --Case.from_row--> Case
counts.csv (E1) --build_inputs (available_at <= origin)--> ForecastInputs --assert_causal
  --> predict_24h(case, history, variant, context=...)
        variant="reference" -> baseline.weekly_reference (+ fallback_value)
        autre variante      -> train.load_model -> modèle ; repli référence si inéligible
  --> ForecastResult --to_forecast_frame / to_run_row--> <method_run_id>.pred.csv / .runs.csv
```

Fonctions réellement implémentées à ce jour (MOD-003 à MOD-005) : `target_timestamps()`, `Case.from_row`, `assert_causal` ; dans `baseline.py`, `weekly_reference`, `weekly_profile_reference` (MOD-004), `admissible_history`, `lookup_lagged`, `fallback_value` ; dans `schemas.py`, `ForecastResult.is_complete`, `to_forecast_frame`, `to_run_row` ; dans `predict.py`, `counts_history_loader`, `build_inputs`, `predict_24h` (variantes `reference`, `reference_profile`), `run_experiment`, `error_result`, `select_cases`, `train_site_counters`, `write_predictions`, `write_runs` et la commande `main` ; tout `features.py` (MOD-006). Toutes les autres lèvent `NotImplementedError("E2 : ...")`. Tests : [tests/test_known_baseline.py](../../tests/test_known_baseline.py), [tests/test_known_predict.py](../../tests/test_known_predict.py), [tests/test_known_features.py](../../tests/test_known_features.py).

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

### MOD-006 - 2026-11-20 - Variables f1.0 (`features.py`), tests et jeu d'apprentissage réel

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2` / non commité.
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
- **Branche / commit** : `Team2` / non commité.
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
  - Corrige MOD-004 : son commit est `8bf5f7f` (et non « non commité »).
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
- [ ] Choisir une méthode justifiée par la bibliographie (statistique, tabulaire, réseau compact, modèle partagé...).
- [ ] Ablation : même modèle avec / sans calendrier ou météo, réglages figés avant le test.
- [ ] `train.py` : `exclude_reserved_sites` (par `site_group_id`), `fit`, `save_model` avec `metadata.json` + SHA-256.
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
| D-05 | 2026-11-19 | Expérience deep learning | Ouvert | Responsabilité E2 ou E3 à attribuer explicitement (ARCHITECTURE §6). `torch` disponible dans le groupe `dl` (CPU). | E2, E3 |
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

---

## 7. Expériences et résultats

Chaque expérience a sa fiche dans `reports/experiments/` (gabarit [experiment.md](../../doc/templates/experiment.md)). Ne remplir les colonnes de résultats qu'avec des valeurs issues de `scores.csv` d'E4.

| ID | Date | Question | Variantes comparées | Protocole / snapshot | MAE macro | Cas complets / attendus | Coût | Conclusion | Fiche |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E2-TECH-001 | 2026-11-19 | Essai technique : chaîne complète sur données réelles (pas de comparaison) | `weekly_naive`, `weekly_profile_median` | `proto-v0` (non validé) / `hist-20261117`, bloc validation | non calculée (E4) | 10 858 / 10 858 pour chaque variante | ≈ 2 min pour 10 858 cas, CPU portable | Chaîne fonctionnelle ; 6,2 % / 3,5 % d'horizons en repli | [fiche](../experiments/E2-TECH-001.md) |
| E2-TECH-002 | 2026-11-20 | Essai technique : jeu d'apprentissage des variables `f1.0` (pas de modèle) | sans objet | aucun (`fit_cutoff` 01/06/2026 provisoire) / `hist-20261117` | sans objet | 87 826 couples, 2 075 614 lignes | 204 s, 374 Mo | Variables sans fuite, chemins identiques ; prêtes pour un modèle | [fiche](../experiments/E2-TECH-002.md) |

---

## 8. Échanges avec les partenaires

| Date | Équipe | Objet | Résultat / preuve d'usage |
| --- | --- | --- | --- |
| 2026-11-19 | E1 | Réception de `hist-20261117` (merge `origin/Team1`) | Empreintes vérifiées contre le manifeste ; données utilisées par E2-TECH-001. À discuter : D-11 (E2 n'utilise pas les valeurs estimées comme entrées des références). |
| 2026-11-19 | E4 | Lecture de `proto-v0/cases.csv` (branche `Team4-sher`, `2ac02dd`) | Utilisé par E2-TECH-001. **Écarts à transmettre** : (1) 2 compteurs réservés `S_dev_new` par E1 figurent en `known_site` / `S_train` (244 cas écartés par E2) ; (2) `snapshot_id = flux-20261115` au lieu de `hist-20261117` ; (3) validation à partir du 01/06/2026 alors que le protocole proposé indique juillet–août ; 89 compteurs connus contre 97 `S_train` chez E1. |

---

## 9. Matière pour le rapport final

Notes à enrichir au fil du projet ; elles serviront directement à la rédaction.

- **Question et périmètre** : sites connus, prévision 24 h, information disponible à l'origine uniquement (latence simulée J−1).
- **Choix d'architecture** : interface unique `ForecastInputs → ForecastResult` partagée E2/E3, registre de méthodes avec repli déclaré, séparation sortie brute / résultat système après repli (CONTRATS §7).
- **Garanties de causalité** : jointure par timestamp, `available_at <= origin`, `fit_cutoff < origin`, labels joints séparément, sites réservés exclus par `site_group_id`.
- **Référence** : naïf hebdomadaire 168 h ; justification : saisonnalité hebdomadaire des passages vélo, recalculable sans apprentissage. Seconde référence : médiane des 4 mêmes heures des semaines précédentes, moins sensible à une journée atypique (MOD-004). Prophet écarté comme référence : non vérifiable à la main, ajustement par cas, historique long nécessaire.
- **Méthodes et ablations** : _à compléter_.
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
| C4 | Deux points d'entrée (`predict_24h(case, history, …)` et `ForecastMethod(inputs, variant)`), ambiguïté sur qui filtre l'historique, routage en double (`predict_24h` et `select_method`), alors que le sujet confie l'implémentation du routage à E5. | Sujet p. 9 ; CONTRATS §9 | Signature exigée par E5 ; la cohérence sera traitée plus tard (D-09). | ⏸️ |
| C5 | Prophet non déclaré dans `pyproject.toml` (calcul non reproductible par l'enseignant), absent de la bibliographie, placé dans `baseline.py`, et ne compte pas comme expérience DL. | Sujet p. 2, 4, 10 | Tester d'abord sa viabilité ; intégration discutée ensuite (D-10). | ⏸️ |

### Importantes

| ID | Incohérence | Référence | Statut |
| --- | --- | --- | --- |
| I1 | `schemas.py` est dans `src/models/` alors que le contrat commun relève de `src/common/contracts.py` ; risque de divergence si E4 ou E5 définissent leur propre `Case`. | ARCHITECTURE §5 ; D-01 | 🔲 |
| I2 | `TrainedModel` ne suit pas `model_metadata.example.json` : noms différents (`donor_site_groups`, `label_interval`, `train_seconds`) ; il manque `excluded_site_groups` (preuve attendue par E3), `weights_sha256`, `minimum_history_hours`, `supported_scenarios`, `fallback`. | CONTRATS §6 ; gabarit métadonnées | 🔲 |
| I3 | Référence décalée de 168 h UTC, mais repli en heure locale, et le plan dit « même heure une semaine avant » : décalage d'une heure en semaine de changement d'heure. Règle à choisir, documenter et tester. | Plan §7 ; PROTOCOLE §2 | 🔲 Écart rendu visible par le test de MOD-003 (repli à 11Z, valeur principale à 10Z) ; règle non tranchée. Les variables `f1.0` suivent l'UTC (D-14) |
| I4 | `MIN_HISTORY_HOURS = 168` est ambigu : avec 24 h de latence, il faut la fenêtre [origin − 168 h, origin − 145 h], pas « 168 h d'historique ». Utilisée par `check_eligibility`, elle refuserait la référence alors que son repli peut répondre. | Sujet p. 2 (méthode simple toujours utilisable) | 🔲 |
| I5 | MOD-001 concluait « aucune incohérence critique » et a été vérifiée avec Python 3.13 au lieu de 3.11 ; ruff non exécuté. | Règles de ce fichier | ✅ Conclusion corrigée par MOD-002 ; Python 3.11 et ruff utilisés depuis MOD-003, `ruff format --check` sans problème depuis MOD-006 |

### Mineures

| ID | Incohérence | Statut |
| --- | --- | --- |
| M1 | `check_eligibility` exige `fit_cutoff < origin`, le protocole admet `<=` (un modèle gelé au 01/09 00:00 serait refusé pour l'origine du 01/09 00:00) ; `MethodSpec.fit_cutoff` est une chaîne au lieu d'un `Timestamp`. Le §9 de ce fichier reprend aussi `<`. | 🔲 |
| M2 | `ForecastInputs.information_cutoff` mal défini : comparé à `available_at` (= `origin`) ou à `interval_end` (= `origin − latence`) selon les docstrings. Lié à C3. | 🟡 MOD-003 : `weekly_reference` compare `interval_end` à `information_cutoff` = `origin − latence` (provisoire, à confirmer avec D-08) |
| M3 | Expérience deep learning non planifiée concrètement dans le squelette (D-05 ouvert), alors qu'elle est obligatoire. | 🔲 |

### Points vérifiés cohérents

`FORECAST_COLUMNS` et `CASE_RUNS_COLUMNS` identiques aux gabarits ; champs de `Case` identiques à `cases.csv` ; `target_timestamps` conforme (24 h écoulées UTC) ; note de latence de `baseline.py` exacte (donnée de h = 24 disponible à origin − 120 h) ; jointure par timestamp, exclusion par `site_group_id` et préservation du test final prévues.

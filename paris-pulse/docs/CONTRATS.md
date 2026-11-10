# ParisPulse - Contrats de données et interfaces v2

Proposition du **10 novembre 2026**, alignée sur le sujet DOCX. Elle remplace v1 : E2 traite les sites connus, E3 les nouveaux sites, et les échanges incluent contexte, adaptation, couverture des cas complets, coût et export. Les fichiers et fonctions ci-dessous sont à implémenter, sans code de départ fourni par le sujet.

## 1. Conventions et identités

| Élément | Règle commune |
| --- | --- |
| `counter_id` | Identifiant de compteur texte, issu de `id_compteur` ; une direction n'est pas un site distinct |
| `site_id` | Identifiant de site source, distinct du compteur |
| `site_group_id` | Groupe physique vérifié utilisé pour les séparations ; rassemble directions et alias confirmés |
| `timestamp` | Début d'intervalle horaire en UTC avec fuseau, après vérification de la source |
| `interval_end` | `timestamp + 1 heure` |
| `origin` | Instant d'émission simulé ; début du premier intervalle à prévoir |
| `horizon` | 1 à 24 ; cible `[origin + (h−1) h, origin + h h)` |
| Affichage et calendrier | `Europe/Paris`, décalage explicite lors des heures répétées |
| Manquant / zéro | `null` pour absence ou invalidité ; zéro observé conservé |
| Unité | Passages/heure ; prévisions finies non négatives, non arrondies pour les scores |
| `scenario` | `known_site` ou `new_site` ; résultats séparés |
| `protocol_id` | Version des périodes, sites, disponibilité, budgets locaux et règles de score |
| `case_id` | Identifie un compteur, une origine et une situation d'information ; indépendant de la méthode |

Une origine peut être proposée à minuit local ; l'horizon reste de **24 heures écoulées UTC**, même si la journée civile dure 23 ou 25 heures. La clé d'un cas inclut `counter_id`, `origin`, `scenario`, `local_budget_hours` si applicable, `protocol_id` et `snapshot_id`.

## 2. Instantané et inventaire - E1 vers toutes

### Manifeste

`data/manifests/<snapshot_id>.json` : version du schéma, sources et URL exactes, filtres, dates d'extraction, licences, attribution, liste de fichiers, SHA-256, schémas, effectifs et bornes temporelles, conventions horaires vérifiées ou incertaines, version des traitements.

`retrieved_at` est l'heure de récupération actuelle, distincte de l'heure à laquelle une valeur aurait été connue dans le passé. Résolution des doublons, priorité archive/flux et rapprochements d'identifiants sont enregistrés.

### Inventaire

`counters.parquet` : `counter_id`, `site_id`, `site_group_id`, noms, latitude/longitude WGS84 nullables, direction validée ou nulle, installation, années/fichiers sources, `snapshot_id` et état des rapprochements.

`inventory_quality.parquet` : par compteur et période, nombre attendu/présent/invalide, taux de manque, suites de zéros, volumes, bornes, raisons d'exclusion et incertitudes. Ces diagnostics peuvent examiner un instantané complet pour décrire le réseau, mais les critères de sélection scientifique et variables prédictives ne consomment pas le futur du test.

Un compteur sans coordonnées peut rester dans l'inventaire tabulaire. Il n'est pas placé arbitrairement sur la carte. Les compteurs inventoriés, chargés et pris en charge sont des ensembles distincts.

## 3. Comptages - E1 vers E2/E3/E4/E5

`counts.parquet`, clé `(counter_id, timestamp)` :

| Colonne | Type logique et règle |
| --- | --- |
| `counter_id` | string, référence de l'inventaire |
| `timestamp`, `interval_end` | datetime UTC, grain horaire confirmé |
| `count_raw` | float nullable, valeur brute auditée |
| `count` | float nullable, nulle si absente ou structurellement invalide |
| `is_observed` | bool, la source contenait une mesure |
| `quality_flags` | liste : manque, négatif, conflit, zéro prolongé suspect, etc. |
| `is_scoreable` | bool, règle structurelle indépendante de la méthode |
| `source_file_id`, `snapshot_id` | provenance |

Une heure de grille insérée a `is_observed=false` et `count=null`. Un pic élevé mais valide et un zéro suspect restent évaluables par défaut ; une analyse de sensibilité peut compléter le score principal. Les cibles ne sont jamais imputées.

Les alertes d'entrée sont calculées causalement à l'origine ; les diagnostics rétrospectifs de qualité ne deviennent pas automatiquement des variables prédictives.

## 4. Contexte - E1 vers E2/E3/E4/E5

Chaque source a une fiche : `context_source_id`, URL/version, licence, unités, géographie, fuseau, `retrieved_at`, règles de jointure et rôle (`known_calendar`, `past_observation`, `forecast_bulletin`, `posthoc_only`).

- Calendrier : une ligne par zone/date locale, puis jointure sur la date locale de la cible ; vérifier unicité et nombre de lignes.
- Observation météo : station/localisation, heure de validité et disponibilité ; aucune observation future dans les entrées.
- Prévision météo : `issued_at`, `available_at`, `valid_time`, station ou grille ; bulletin émis et disponible avant l'origine.
- Une information sans disponibilité historique établie est descriptive ou repose sur une hypothèse explicitement versionnée ; ne pas la présenter comme preuve de connaissance passée.

L'audit de jointure contient nombre de clés avant/après, doublons, lignes non appariées et conversions. La source complémentaire et sa version sont incluses dans les artefacts et les caches, y compris si l'ablation conclut à un gain nul.

## 5. Protocole, cas et support local - E4 vers les autres

`protocol.json` : état de validation professorale, périodes et coupures UTC, groupes de sites, origines, disponibilité, budgets locaux, score, règle de sélection et budget de calcul. Voir [PROTOCOLE_EVALUATION.md](PROTOCOLE_EVALUATION.md).

`cases.parquet` contient `case_id`, compteur/site/groupe, `origin`, `scenario`, split temporel, rôle spatial, budget local, bornes de support, `protocol_id`, `snapshot_id`. La génération des cas ne dépend pas de la réussite future d'un modèle.

Pour E3, `support_manifest` identifie exactement les observations locales autorisées : bornes, masque de manque, nombre de mesures, disponibilité et empreinte. Ni la méthode, ni l'adaptation, ni la normalisation ne voient les autres observations du site. Les trois variantes comparées utilisent le même support.

`available_at = interval_end + publication_lag_hours` peut servir d'hypothèse simulée, par exemple 24 h. Le support de L heures se termine à la coupure d'information admissible, pas automatiquement à l'origine si la latence est positive. Toute autre règle change le protocole.

## 6. Variables et modèles - E2/E3 vers E4/E5

Les variables partagées portent `feature_version`, `case_id`, `target_timestamp`, horizon, calendrier, qualité de l'historique et `max_input_available_at <= origin`. Le module reçoit seulement les entrées autorisées et le contexte admissible ; les labels sont joints séparément pour entraîner ou évaluer.

Les transformations apprises sont figées à la coupure du modèle. Les agrégats locaux et le remplissage restent limités au support autorisé dans le scénario nouveaux sites. Les fenêtres d'apprentissage n'utilisent que des entrées disponibles à leur origine et des labels disponibles à la coupure de l'entraînement.

`models/<model_run_id>/metadata.json` contient :

- nom, architecture/méthode, hyperparamètres, graine, versions du code et dépendances ;
- `fit_cutoff`, intervalle des labels, liste ou empreinte des sites donneurs, exclusion des sites réservés ;
- instantané, contexte, protocole et variables ; historique minimal et gestion des catégories inconnues ;
- temps d'entraînement, matériel, fichier des poids/paramètres et SHA-256 ;
- pour un modèle public : checkpoint et révision, licence des poids, corpus décrit ou inconnu, risque de contamination ;
- scénarios exécutables, conditions d'utilisation et repli.

`fit_cutoff` représente la coupure d'information simulée, distincte de l'heure réelle d'exécution du script. Elle doit précéder toute origine servie par cette version.

Pour une adaptation, enregistrer `adaptation_id`, modèle de base, `support_id`, paramètres modifiés, méthode et réglages figés, `adaptation_cutoff <= origin`, temps et statut. Aucun cumul silencieux des données de plusieurs cas nouveaux sites.

## 7. Prévisions et coût - E2/E3 vers E4/E5

`forecasts.parquet`, clé `(case_id, method_run_id, horizon)` :

| Champs | Règle |
| --- | --- |
| `case_id`, `method_run_id`, `model_run_id` | Cas indépendant de la méthode, exécution et version de modèle identifiées |
| `counter_id`, `origin`, `scenario` | Contexte du cas |
| `horizon`, `target_timestamp` | 24 lignes attendues, timestamps dérivés de l'origine |
| `y_pred` | Finie et non négative, ou `null` avec un échec explicite |
| `variant` | `reference`, `frozen`, `adapted` ou autre variante déclarée |
| `method_used`, `prediction_status` | Méthode réellement employée ; `ok`, `fallback`, `unavailable`, `error` |
| `status_reason` | Historique court, délai, ressource manquante, calcul interrompu, etc. |
| `support_id`, `adaptation_id` | Obligatoires selon le scénario ; même support pour la comparaison E3 |
| `snapshot_id`, `context_version`, `protocol_id`, `feature_version` | Traçabilité |

Un cas n'est **complet** que si ses 24 horizons distincts ont une prévision valide. Les heures manquantes ne sont pas supprimées pour transformer un échec en succès. Séparer la sortie brute d'une méthode et le résultat du système après repli ; le second peut être complet quand le premier échoue.

`case_runs.parquet` enregistre, une fois par exécution de cas : statut, durée de préparation/inférence/adaptation, cache utilisé ou non, temps d'attente, mémoire mesurée si disponible, matériel et message d'erreur. Le coût d'entraînement est enregistré à part ; ne pas l'additionner 24 fois parce qu'il existe 24 lignes de prévision.

## 8. Évaluation et disponibilité - E4 vers E5

Les observations cibles proviennent d'un accès séparé aux comptages et sont absentes des entrées de prévision. E4 joint par compteur et heure, jamais par position de ligne.

`scores` contient : scénario, split temporel/spatial, méthode ou système, population comparée, nombre de cas attendus/complets/sans résultat/comparables, raisons d'échec, nombre d'heures réellement mesurées, MAE par compteur et moyenne entre compteurs. Les détails incluent erreur signée, absolue et quadratique.

La comparaison principale porte sur l'intersection des **cas complets de 24 heures** des méthodes, avec le même masque d'observations réellement mesurées. Rapporter séparément couverture individuelle et système après repli. Aucune heure manquante ne devient une erreur zéro ; si aucun score n'est calculable, valeur `null` et raison.

`coverage.parquet` croise inventaire, scénario, méthode, origine et budget local. Il distingue `inventory_only`, `data_unavailable`, `insufficient_history`, `supported`, `complete`, `partial`, `error` et `fallback_complete`. Les conditions sont explicables à l'utilisateur ; seule la sélection de dates admissibles peut être filtrée sans masquer les lieux inventoriés.

Si des intervalles sont étudiés, ajouter bornes, niveau, calibration et coupure. Évaluer couverture effective, largeur et effectif ; ne pas appliquer une calibration aux dates antérieures à sa disponibilité.

## 9. Service de l'application - E5 appelle les partenaires

Interfaces proposées, à adapter ensemble avant implémentation :

```python
load_inventory(snapshot_id) -> DataFrame
get_capabilities(counter_id, scenario, protocol_id) -> DataFrame
list_cases(counter_id, scenario, local_budget_hours, protocol_id) -> DataFrame
prepare_inputs(case_id) -> ForecastInputs      # passé et contexte autorisés uniquement
predict(case_id, method_name, use_cache=True) -> ForecastResult
get_observations(case_id) -> DataFrame
evaluate_case(case_id, method_run_ids) -> Metrics
export_study(case_id, method_run_ids, reveal_state) -> Path
```

`predict` appelle la référence d'E2, les modèles d'E2/E3 et leurs règles déclarées. La référence est recalculable avec `use_cache=False` pour un cas différent de la démonstration. `get_capabilities` explique l'historique minimal, les ressources et les indisponibilités.

Les scores et observations cibles sont affichés après révélation, sans nouvelle inférence. La visibilité pédagogique ne constitue pas une frontière de sécurité ; la séparation des calculs et les tests de causalité assurent la validité scientifique.

La clé de cache contient instantané, contexte, protocole, cas, modèle, adaptation/support et version du routage. Toute modification invalide le résultat correspondant. Changer de cas, méthode ou budget local réinitialise la révélation.

## 10. Export et acceptation d'une livraison

L'export d'une étude contient prévisions CSV, observations selon l'état de révélation, scores avec dénominateurs, manifeste JSON, méthodes effectives, support local, paramètres/adaptation, versions, temps, périmètre global et refus. Avant révélation, ne pas glisser les cibles cachées dans le fichier exporté.

Chaque producteur fournit un exemple conforme créé par l'équipe, un exemple réel, versions, règles de nullité et commande reproductible. Le consommateur contrôle clés, heures et un cas difficile, puis relie la preuve d'usage dans le suivi commun. Une sortie simplement déposée sans consommateur vérifié ne constitue pas une intégration.

Jeux de contrôle à partager : zéro observé, heure absente, doublon conflictuel, décalage d'une heure, prévision manquante, changement d'heure, site à directions multiples, support local réduit et futur modifié. Les données synthétiques restent séparées des performances sur données réelles.

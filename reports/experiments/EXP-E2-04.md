# EXP-E2-04 - Le contexte (calendrier, grèves, météo prévue) aide-t-il nos modèles ?

> **Statut : brouillon, à figer avant tout score.** Les points marqués « à valider » sont des propositions. Les résultats restent vides jusqu'au gel. Même population et même calcul du score que [EXP-E2-03](EXP-E2-03.md).

- **Date, équipe, responsables et partenaires** :
  - Brouillon le 2026-11-24, E2.
  - Responsable proposée (à valider) : Ania, qui a construit les groupes de contexte (D-12) ; elle pourrait en faire sa comparaison individuelle. Idir : apprentissage des modèles sans contexte et calcul des prévisions.
  - Partenaires : E4 (scores), E1 (sources du contexte, `e1-context/0.3.0`).

- **Question et hypothèse** :
  - Le sujet le demande (E2, « Étude principale ») : « testez l'intérêt des informations ajoutées : par exemple, comparez le même modèle avec et sans calendrier ».
  - Question : à méthode égale, donner le contexte (fériés, vacances, grèves, météo prévue) réduit-il l'erreur sur les sites connus, et pour quels jours ?
  - Hypothèse : un gain modeste en moyenne, concentré sur les jours particuliers (14/07, 15/08, jours de pluie). L'été 2026 contient peu de ces jours, donc l'effet moyen risque d'être faible. « Le contexte n'améliore pas ce modèle sur cette période » est une conclusion valable.

- **Références bibliographiques** : Zeng et al. (références simples) ; Salinas et al., *DeepAR* (covariables connues à l'avance). À compléter avec une référence sur l'effet de la météo sur la fréquentation cyclable, à lire avant le gel.

- **Instantané, protocole validé, code et paramètres** :
  - Identiques à [EXP-E2-03](EXP-E2-03.md) : `hist-20261117`, `proto-v1` (non validé par le professeur), `fit_cutoff` au 2026-06-30T22:00Z, apprentissage depuis le début des données (D-17), latence de 24 h, mesures seules, réglages par défaut, graine 0.
  - Modèles comparés deux à deux (même méthode, seul le contexte change) :

    | Méthode | Avec contexte | Sans contexte |
    | --- | --- | --- |
    | MLP | `e2-mlp-ctx-20260701-s0-9ce9` (419 entrées) | `e2-mlp-noctx-20260701-s0-5114` (344 entrées) |
    | HGB | `e2-hgb-ctx-20260701-s0-b357` (342 arbres) | `e2-hgb-noctx-20260701-s0-0af3` (679 arbres, plafond `max_iter=2000`) |

    Plafond d'arbres : le HGB sans contexte touchait le plafond par défaut (499 arbres sur 500, modèle `409c`, écarté). Il est réappris avec `max_iter=2000` et s'arrête de lui-même à 679. Pour que seul le contexte change, la version avec contexte a été réapprise avec le même plafond (`e2-hgb-ctx-20260701-s0-8b7a`) : elle s'arrête toujours à 342 arbres, et ses prévisions sont **identiques** à celles de `b357` (écart maximal 0,0 vélo/h sur 15 cas de validation tirés au hasard, 2026-11-24). On garde donc `b357`, déjà déclaré dans EXP-E2-03.

  - Étape 2, **HGB seulement** (`context_groups`, D-12 ; le MLP ne sait retirer le contexte que d'un bloc) : retirer un groupe à la fois parmi `calendar`, `strikes`, `weather_forecast`. Elle n'est faite que si l'étape 1 montre un effet supérieur à la variabilité attendue (à valider).

- **Scénario, sites, dates et budget d'information autorisé** : identiques à EXP-E2-03 : 6 014 cas `known_site` de validation (97 compteurs × 62 jours, juillet-août 2026) ; le test n'est pas lu.

- **Facteur modifié et facteurs conservés** :
  - **Facteur modifié** : la présence du contexte en entrée (`use_context`).
  - **Facteurs conservés** : méthode, réglages, graine, cas, coupure, latence, entrées de comptage, masque de score, règle de repli.
  - Effet de bord à signaler : sans contexte, le refus `*_context_missing` ne peut plus arriver. La couverture peut donc changer un peu : elle est rapportée, et la comparaison se fait sur l'intersection.

- **Cas attendus et règle de comparaison** :
  - Les 6 014 cas, comparés **par paire** : MLP avec / MLP sans, et HGB avec / HGB sans. Chaque paire a sa propre intersection des cas complets, avec le même masque. Pas de classement croisé entre les paires.
  - Score : par E4, avec `evaluate_all` de `Metric.py`, comme dans EXP-E2-03. Résultats « modèle brut » et « système ».
  - **Diagnostics prévus, fixés d'avance** :
    - MAE sur les 2 jours fériés (14/07 et 15/08) contre les autres jours ;
    - MAE selon la pluie prévue, jours avec ou sans pluie (seuil à fixer avant les scores, à valider) ;
    - jours de grève éventuels de la période (effectif à compter avant les scores).

    Ils servent à expliquer le résultat, pas à décider.
  - **Lecture du résultat** (à valider) :
    - Pour le MLP, un écart entre avec et sans contexte n'est interprété que s'il dépasse l'étendue entre les 3 graines mesurée dans EXP-E2-03.
    - Le HGB est déterministe : son écart est rapporté tel quel, avec le nombre de compteurs améliorés et dégradés.
  - **Conséquence pour l'application** (à valider) : la version avec contexte n'est gardée que si elle fait mieux que la version sans contexte, selon la lecture ci-dessus. Sinon, on préfère la version sans contexte, qui ne dépend pas de la livraison du contexte et ne se replie jamais pour `context_missing`.

- **Contrôles réalisés** :
  - Code de l'ablation déjà testé (E2-TECH-002, MOD-006 à MOD-010) : sans contexte, aucune colonne de contexte n'est lue.
  - À faire :
    - mêmes `cases_used.csv` pour les 4 modèles ;
    - les modèles sans contexte n'ont aucune colonne de contexte (`metadata.json`, `variant = noctx`) ;
    - mêmes origines et mêmes compteurs à l'apprentissage que les versions avec contexte (bilans d'apprentissage).

- **Résultats mesurés : MAE, cas complets/comparables, échecs et coût** :

  _À remplir avec les valeurs d'E4, après le gel._

  | Paire | MAE macro avec | MAE macro sans | Écart | Cas comparés | Compteurs améliorés / dégradés |
  | --- | --- | --- | --- | --- | --- |
  | MLP | | | | | |
  | HGB | | | | | |

- **Analyse, limites et décision** :

  _À remplir après les scores._

  Limites connues dès maintenant :
  - été seulement : 2 jours fériés, vacances scolaires presque tout le temps, donc la variable change peu ;
  - météo prévue reconstruite par E1 ;
  - une graine par version (variabilité estimée sur la version avec contexte) ;
  - protocole non validé.

- **Lien vers données de résultats et figures** : `data/prediction_results/EXP-E2-04/`. Les prévisions des versions avec contexte sont reprises d'EXP-E2-03 (même calcul, sans recalcul).

- **Retour d'un partenaire et preuve d'utilisation** : à obtenir (E4 : scores ; E5 : version retenue).

## Points à trancher avant le gel

0. ~~Plafond d'arbres du HGB sans contexte~~ : traité le 2026-11-24, `max_iter=2000` (voir le tableau des modèles). À confirmer par Ania comme réglage figé.

1. Responsable de la fiche (proposition : Ania).
2. Seuil de pluie pour le diagnostic, et décompte des jours de grève de la période.
3. Faire l'étape 2 (par groupe, HGB) seulement si l'étape 1 montre un effet, ou dans tous les cas.
4. Règle « sans contexte si pas mieux » pour l'application.

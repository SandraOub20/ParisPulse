# EXP-E2-04 - Le contexte (calendrier, grèves, météo prévue) aide-t-il nos modèles ?

> **Statut : terminée le 2026-11-27.** Figée avant tout score (commit indiqué dans l'historique de cette fiche). Les choix ci-dessous ne changent plus : voir « Décisions du gel » en bas. Même population et même calcul du score que [EXP-E2-03](EXP-E2-03.md).

- **Date, équipe, responsables et partenaires** :
  - Brouillon le 2026-11-24, figée le 2026-11-27, E2.
  - Responsable : Ania, qui a construit les groupes de contexte (D-12). Idir a appris les modèles sans contexte, calculé les prévisions et figé la fiche avec les choix par défaut ci-dessous, pour tenir le calendrier de remise ; Ania est prévenue.
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
    - MAE selon la pluie prévue : jour « pluvieux » si la pluie prévue (`rain_prev`, somme sur la journée locale) atteint **1 mm**. Cela donne 5 jours sur 62, comptés avant les scores ;
    - jours de grève : **aucun** en juillet-août 2026 (`is_strike`, compté avant les scores). Le groupe `strikes` ne peut donc pas montrer d'effet sur cette période, et c'est une limite.

    Ils servent à expliquer le résultat, pas à décider.
  - **Lecture du résultat** :
    - Seuil de bruit : l'étendue entre les 3 graines du MLP mesurée dans EXP-E2-03, soit **0,357** vélo/h (22,589 − 22,232, MAE macro système). Un écart plus petit se lit « pas d'effet mesurable ».
    - Pour le MLP, l'écart avec / sans contexte n'est interprété que s'il dépasse ce seuil.
    - Le HGB est déterministe pour une graine donnée. Son écart est rapporté tel quel, avec le nombre de compteurs améliorés et dégradés. Il n'est interprété que s'il dépasse le même seuil, faute d'une autre mesure du bruit.
  - **Conséquence pour l'application** : le modèle de l'application reste le HGB avec contexte (`b357`, D-24), **sauf** si la version sans contexte fait mieux d'au moins le seuil. Dans ce cas, on passerait à la version sans contexte, qui ne dépend pas de la livraison du contexte. Sur EXP-E2-03, le HGB avec contexte ne se replie jamais, si bien que la dépendance au contexte ne coûte rien de mesurable aujourd'hui.

- **Contrôles réalisés** :
  - Code de l'ablation déjà testé (E2-TECH-002, MOD-006 à MOD-010) : sans contexte, aucune colonne de contexte n'est lue.
  - À faire :
    - mêmes `cases_used.csv` pour les 4 modèles ;
    - les modèles sans contexte n'ont aucune colonne de contexte (`metadata.json`, `variant = noctx`) ;
    - mêmes origines et mêmes compteurs à l'apprentissage que les versions avec contexte (bilans d'apprentissage).

- **Résultats mesurés : MAE, cas complets/comparables, échecs et coût** :

  Score calculé le 2026-11-27 par E2 avec les fonctions d'E4 (`score.py`), qui redonnent exactement les scores officiels d'EXP-E2-03. Validation, 5 613 cas comparés, 95 compteurs. Notebook : [E2_EXP-04_contexte.ipynb](../../notebooks/E2_EXP-04_contexte.ipynb).

  **Étape 1, avec ou sans contexte :**

  | Paire | MAE macro avec | MAE macro sans | Écart (sans − avec) | Biais avec / sans | Cas comparés | Compteurs améliorés / dégradés |
  | --- | --- | --- | --- | --- | --- | --- |
  | MLP (système) | 22,23 | 23,38 | **+1,15** | −0,81 / +2,62 | 5 613 | 88 / 7 |
  | MLP (brut) | 22,20 | 23,36 | +1,16 | | 5 577 | |
  | HGB | 22,25 | 22,90 | **+0,64** | −1,13 / −0,37 | 5 613 | 86 / 9 |

  **Diagnostics par type de jour** (MAE macro ; ils expliquent le résultat, ils ne décident pas) :

  | Jours | HGB avec | HGB sans | Gain du contexte | MLP avec | MLP sans | Gain du contexte |
  | --- | --- | --- | --- | --- | --- | --- |
  | Fériés (14/07, 15/08) | 24,31 | 33,88 | **+9,57** | 22,91 | 28,87 | **+5,96** |
  | Autres jours | 22,20 | 22,53 | +0,34 | 22,21 | 23,20 | +0,98 |
  | Pluie prévue d'au moins 1 mm (5 jours) | 23,79 | 23,15 | **−0,64** | 26,19 | 23,03 | **−3,16** |
  | Jours secs | 22,15 | 22,91 | +0,75 | 21,91 | 23,45 | +1,53 |

  **Étape 2, déclenchée par la règle (écart du HGB > 0,357)** : HGB réappris sans un groupe à la fois, même réglage (`max_iter=2000`), comparé au HGB complet `b357` (22,25) :

  | Modèle | Groupes gardés | MAE macro | Perte sans ce groupe | Lecture |
  | --- | --- | --- | --- | --- |
  | `e2-hgb-ctx-20260701-s0-70b9` | grèves, météo | 22,74 | **+0,48** | le calendrier compte |
  | `e2-hgb-ctx-20260701-s0-55d2` | calendrier, météo | 22,15 | −0,11 | pas d'effet mesurable (aucune grève dans la période) |
  | `e2-hgb-ctx-20260701-s0-6a8b` | calendrier, grèves | 22,42 | +0,17 | pas d'effet mesurable en moyenne |

  Coût : 2 à 3 min de prévision en bloc par modèle ; environ 10 min d'apprentissage par HGB de l'étape 2.

- **Analyse, limites et décision** :

  - **Le contexte aide les deux modèles**, au-delà du seuil de bruit fixé au gel (0,357) : +0,64 pour le HGB et +1,15 pour le MLP. Il améliore presque tous les compteurs (86 et 88 sur 95).
  - **Le gain vient surtout du calendrier.**
    - Les jours fériés, le contexte évite une erreur de 6 à 10 vélos/h : sans lui, un 14 juillet est prévu comme un jour ouvré.
    - Retirer le calendrier coûte 0,48 au HGB, plus que le seuil.
    - Retirer les grèves ne change rien, ce qui est attendu puisqu'il n'y en a aucune en juillet-août.
    - Retirer la météo coûte 0,17, sous le seuil.
  - **La météo prévue ne montre pas d'effet moyen, et elle dégrade les jours de pluie prévue**, surtout pour le MLP (−3,16). Cela ne repose que sur 5 jours, avec une pluie prévue à J−2 et reconstruite par E1 : soit la prévision de pluie se trompe souvent, soit le modèle réagit trop fort à une variable rare en été. Le test d'octobre-novembre, plus pluvieux, dira si l'effet tient.
  - **Décision, selon la règle du gel** : la version sans contexte ne fait pas mieux, donc **le HGB avec contexte (`b357`) reste le modèle de l'application**. On ne retire pas la météo, puisque le modèle sans météo est aussi un peu moins bon en moyenne (22,42).
  - L'étape 2 a appris 3 HGB de plus ; ils sont gardés pour la transparence et ne sont pas servis.

  Limites :
  - été seulement : 2 jours fériés, aucune grève et 5 jours de pluie prévue, donc les diagnostics reposent sur peu de jours ;
  - météo prévue reconstruite par E1 ;
  - une graine par version : le seuil de bruit est emprunté à l'étendue des graines du MLP (EXP-E2-03) ;
  - le décalage de 2 h des mesures d'E1 sur 5 jours de juillet touche les deux versions de la même façon ;
  - protocole non validé.

- **Lien vers données de résultats et figures** : `data/prediction_results/EXP-E2-04/`. Les prévisions des versions avec contexte sont reprises d'EXP-E2-03 (même calcul, sans recalcul).

- **Retour d'un partenaire et preuve d'utilisation** : prévisions à livrer à E4 pour leur score officiel ; E5 : aucun changement, le HGB avec contexte reste servi.

## Décisions du gel (2026-11-27)

0. Plafond d'arbres du HGB : `max_iter=2000` pour les deux versions. Celle avec contexte s'arrête d'elle-même à 342 arbres, avec des prévisions identiques à `b357`.
1. Responsable : Ania.
2. Diagnostics :
   - pluie prévue d'au moins 1 mm par jour (5 jours) ;
   - grèves : aucune dans la période ;
   - fériés : 14/07 et 15/08.
3. Étape 2 (retirer un groupe à la fois, HGB) : seulement si l'étape 1 montre, pour le HGB, un écart supérieur au seuil de 0,357.
4. Application : le HGB avec contexte reste, sauf si la version sans contexte fait mieux d'au moins le seuil.
5. Score calculé par E2 avec les fonctions d'E4 (`python -m src.models.known.score --experiment EXP-E2-04`), qui redonnent exactement les scores officiels d'EXP-E2-03 (MOD-018). Les fichiers sont livrés à E4 pour confirmation.

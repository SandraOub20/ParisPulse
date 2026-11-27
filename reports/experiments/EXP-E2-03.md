# EXP-E2-03 - Quelle méthode pour les sites connus : MLP, HGB ou référence ?

> **Statut : terminée.** Figée le 2026-11-24 et validée par l'équipe E2 (Idir, Esther, Ania ; commit indiqué dans l'historique de cette fiche). Les scores officiels d'E4 (2026-11-25) confirment exactement le score provisoire. **Décision : HGB retenu pour l'application (D-24).**

- **Date, équipe, responsables et partenaires** :
  - Brouillon le 2026-11-24, E2 : Idir, Esther, Ania, Emmanuelle.
  - Rôles : chaque modèle est porté par son auteur, Esther pour le MLP et Ania pour le HGB. Idir porte le calcul des prévisions (`predict.py`, MOD-011) et le contrôle des populations comparées.
  - Partenaires : E4 calcule les scores (`scores.csv`, `errors.csv`) ; E5 reçoit le `model_run_id` retenu pour l'application.

- **Question et hypothèse** :
  - Question : sur les sites connus, un modèle appris sur tout le réseau prévoit-il les 24 prochaines heures mieux que les références simples ? Et lequel des deux, MLP ou HGB, à quelle couverture et à quel coût ?
  - Hypothèse : les deux modèles font mieux que la meilleure référence. Le contrôle sur juin donne environ −12 à −14 % face à la médiane sur 4 semaines (E2-TECH-003, E2-TECH-004), mais ce mois a servi à l'arrêt anticipé, donc ce chiffre est optimiste. L'écart entre MLP et HGB est petit ; le HGB a une meilleure couverture, car il tolère les fenêtres trouées.
  - Une absence de gain est une conclusion valable. Elle sera analysée, pas cachée.

- **Références bibliographiques** :
  - Zeng et al. : se mesurer à des références simples.
  - Salinas et al., *DeepAR* : normalisation par le niveau de la série (MLP, D-18).
  - Hyndman & Athanasopoulos, §5.10 : découpage temporel.
  - Gradient boosting : Friedman (2001), Ke et al. (2017), Makridakis et al. (2022, M5). Ces références sont à lire et à ajouter à [BIBLIOGRAPHIE.md](../../doc/BIBLIOGRAPHIE.md) avant le gel (E2-TECH-004).

- **Instantané, protocole validé, code et paramètres** :
  - Instantané `hist-20261117` (manifeste [hist-20261117.json](../../data/manifests/hist-20261117.json)). Les empreintes SHA-256 seront revérifiées le jour du calcul.
  - Protocole : `proto-v1` d'E4 (`data/evaluation/proto-v1/cases.csv`, branche `Team4`, SHA-256 `2f09e096…` dans `cases_manifest.json`). **Le professeur ne l'a pas encore validé** : tout résultat sera étiqueté « protocole proposé ».
  - Code : `predict.py` (MOD-011), `neural.py` (MOD-008), `tabular.py` (MOD-010), au commit du gel.
  - Modèles, tous figés et sauvegardés avant les scores :

    | Méthode | `model_run_id` | Réglages figés |
    | --- | --- | --- |
    | `reference` (`weekly_naive`) | sans objet | `y(t − 168 h)`, repli D-03 (N = 4) |
    | `reference_profile` (`weekly_profile_median`) | sans objet | médiane de 4 semaines, même repli |
    | `mlp` | `e2-mlp-ctx-20260701-s0-9ce9` (graine 0) | `mlp_hyperparameters()` par défaut ; L1 pondérée par le niveau (D-19) ; arrêt anticipé sur 4 semaines, sans réapprentissage (D-20) ; seuil 84 h (D-18) |
    | `mlp`, graines 1 et 2 | `e2-mlp-ctx-20260701-s1-9318`, `e2-mlp-ctx-20260701-s2-6278` (appris le 2026-11-24, même code que MOD-008) | seulement pour mesurer la variabilité, jamais pour choisir |
    | `hgb` | `e2-hgb-ctx-20260701-s0-b357` | `hgb_hyperparameters()` par défaut ; `loss="absolute_error"` (optimise directement la MAE, proposée à E4) ; `refit_on_holdout=False` (comme D-20 pour le MLP) ; `categorical=False` ; **`max_iter=2000`** pour tous les HGB : l'arrêt anticipé choisit seul le nombre d'arbres. Avec contexte, le modèle réappris à 2 000 (`8b7a`) garde 342 arbres et donne des prévisions identiques à `b357` (0,0 vélo/h sur 15 cas), d'où `b357` conservé |

  - Communs à toutes les méthodes :
    - `fit_cutoff` au 2026-06-30T22:00Z, apprentissage depuis le début des données (D-17) ;
    - latence de 24 h (D-22) ;
    - entrées : mesures seules (D-11) ;
    - contexte complet `e1-context/0.3.0` pour les deux modèles ;
    - 97 compteurs `S_train`, groupes E3 exclus.
  - **Réglages : valeurs par défaut, sans recherche.**
    - Aucune validation croisée ni recherche d'hyperparamètres n'a été faite. Seuls le nombre d'époques (MLP) et le nombre d'arbres (HGB) sont choisis automatiquement, sur les 4 semaines avant la coupure (juin), qui font partie de l'apprentissage.
    - C'est équitable : les deux modèles sont dans le même cas. Mais leurs erreurs ne sont pas les meilleures possibles, ce sera écrit dans les limites.
    - Un réglage éventuel se ferait par validation croisée temporelle **avant le 01/07**, jamais sur juillet-août.
  - **Contrôle de reproductibilité**, fait le 2026-11-24 : le MLP en graine 0 a été réappris avec le code actuel, sans sauvegarde.
    - Code identique au commit d'Esther (`f07599a`, aucune différence dans `neural.py`, `train.py`, `features.py`), mêmes exemples (85 958 / 2 560), même `torch` 2.15.0.
    - **Le résultat n'est pas identique** : meilleure époque 17 contre 20, MAE macro de contrôle (juin) 17,57 contre 17,51.
    - Cause : la machine (4 cœurs et 2 threads torch, contre 8 et 4). L'ordre des additions en virgule flottante change, l'arrêt anticipé choisit une autre époque. Le rapport d'Esther le disait : « même graine, même machine : mêmes poids ».
    - Conséquence : l'écart dû à la machine (0,06) est bien plus petit que l'écart entre graines (17,57 / 17,60 / 17,86 sur la même machine, étendue 0,29). Les graines 1 et 2 servent donc bien à mesurer la variabilité. Le modèle servi reste `e2-mlp-ctx-20260701-s0-9ce9`, déclaré d'avance.
    - À retenir pour la remise : un modèle ne se reproduit à l'identique que sur la même machine, avec le même nombre de threads.

- **Scénario, sites, dates et budget d'information autorisé** :
  - Scénario `known_site` : 97 compteurs `S_train`, 49 groupes de sites.
  - **Validation seulement** : 62 origines quotidiennes à minuit (Paris), du 01/07 au 31/08/2026.
  - **Le test (octobre-novembre) n'est pas lu** : il est réservé à la mesure finale, après le gel du choix.
  - Information autorisée à chaque origine : mesures avec `interval_end <= origin − 24 h`, contexte avec `available_at` vide ou `<= origin`.
  - Les modèles restent figés au 01/07 pendant toute la validation (version admissible, PROTOCOLE §3). Les entrées, elles, avancent avec chaque origine.

- **Facteur modifié et facteurs conservés** :
  - **Facteur modifié** : la méthode de prévision (4 méthodes).
  - **Facteurs conservés** : cas, instantané, coupure, latence, entrées, contexte, masque de score, règle de repli.
  - **Hors de cette fiche**, une fiche par facteur :
    - avec ou sans contexte, et par groupe de contexte (D-12) : [EXP-E2-04](EXP-E2-04.md) ;
    - variabilité entre graines du MLP (mesurée ici, pas choisie ici) ;
    - MLP appris avec ou sans masquage des fenêtres (comparaison d'Idir) ;
    - choix de la loss du HGB (E4).

- **Cas attendus et règle de comparaison** :
  - **Cas attendus**, fixés avant tout calcul : les **6 014** cas `known_site` / `validation` de `proto-v1` (97 compteurs × 62 jours). Aucun cas n'est retiré après coup ; un cas qui échoue reste dans les dénominateurs.
  - **Deux évaluations séparées** (PROTOCOLE §6, « Système après repli ») :
    1. **Modèles bruts** : seulement les horizons servis par la méthode elle-même. On prend l'**intersection commune** des cas complets des 4 méthodes, et on publie sa taille.
    2. **Système** : le modèle plus son repli déclaré, sur **tous** les cas attendus. C'est ce que verra l'application.
  - **Score** :
    - MAE de chaque compteur, sur les heures `is_scoreable` (vraies mesures), avec **le même masque** pour toutes les méthodes ;
    - puis **moyenne non pondérée entre compteurs** (MAE macro) ;
    - un compteur sans heure évaluable reçoit `null`, jamais 0.
  - **Calcul du score** : par E4, avec `evaluate_all(cases, forecasts, observations)` de `src/eval/Metric.py` (branche `Team4`, commit `7a5c3e0`). Les règles ci-dessus y sont déjà, vérifié à la lecture du code :
    - une heure n'est évaluable que si la prévision est valide (`ok` ou `fallback`, finie, ≥ 0), et l'heure observée et `is_scoreable` ;
    - `filter_common_complete_cases` garde les cas complets pour toutes les méthodes, puis les heures évaluables pour toutes ;
    - MAE par compteur, puis moyenne non pondérée (`global_comparable`).

    Comment on l'appelle :
    - `cases` = les 6 014 cas attendus, et non les seuls cas présents dans les prévisions (`evaluation_cases_from_cases` ou `evaluate_all`) ;
    - `forecasts` = les `.pred.csv` des méthodes, concaténés ;
    - `observations` = `counts.csv` de `hist-20261117`. La vérité lue est `count`, identique à `count_raw` sur toutes les heures scorables (vérifié le 2026-11-24 ; les 17 965 heures où elles diffèrent sont des `long_zero_run` remplies par E1, toutes non scorables).
  - **Modèles bruts contre système** : E4 compte une heure `fallback` comme une prévision valide. Son calcul donne donc l'évaluation **système**. Pour les **modèles bruts**, on lui passe une copie des mêmes prévisions où les heures `fallback` sont marquées non servies (`prediction_status = unavailable`, `y_pred` vide). Rien d'autre ne change.
  - **Indicateurs secondaires**, sur la même population :
    - couverture 24 h (cas complets / 6 014) ;
    - taux de repli et causes (`mlp_*`, `hgb_*`) ;
    - biais moyen ;
    - MAE par horizon, par heure locale et par compteur ;
    - gain sur la meilleure référence ;
    - nombre de compteurs où la méthode bat la meilleure référence ;
    - coût : apprentissage, inférence par cas, mémoire et matériel.
  - **Règle de choix pour l'application**, figée :
    1. Un modèle n'est retenu que si, sur les mêmes cas, **les deux conditions** sont vraies :
       - sa MAE macro « système » est **inférieure d'au moins 5 %** à celle de la meilleure référence, soit environ 1 vélo/h, bien au-delà de la variabilité entre graines (environ 1,7 % sur juin) ;
       - il fait mieux que la meilleure référence sur **plus de la moitié des compteurs**, pour ne pas gagner seulement grâce à quelques gros compteurs.

       Sinon, l'application garde la meilleure référence.
    2. Entre MLP et HGB, l'écart doit dépasser **l'étendue entre les 3 graines du MLP**. Sinon, l'écart n'est pas jugé significatif, et on retient le plus simple et le mieux couvert : le HGB, qui n'a pas besoin de torch.
    3. La graine retenue pour le MLP est la graine 0, déclarée à l'avance.
  - Ces règles sont appliquées telles quelles. Les seuils ne seront pas ajustés après avoir vu les scores.

- **Contrôles réalisés** (avant les scores) :
  - Déjà faits :
    - non-fuite du HGB et témoin positif par `predict_24h` (MOD-011) ;
    - non-fuite de `fit_mlp` et `fit_hgb` (E2-TECH-003, E2-TECH-004) ;
    - 25 vrais cas passés par la chaîne complète (MOD-011).
  - À faire au calcul :
    - 6 014 × 24 lignes par méthode, aucune clé en double ;
    - `check_forecasts` d'E4 sur chaque `.pred.csv` ;
    - aucune valeur `y_pred` égale à 0 là où le modèle a refusé ;
    - même `cases_used.csv` pour les 4 méthodes ;
    - SHA-256 de l'instantané.
  - Score manuel sur un compteur et un jour, comparé au calcul d'E4.

- **Résultats mesurés : MAE, cas complets/comparables, échecs et coût** :

  **Scores officiels d'E4** : `data/evaluation/proto-v1/EXP-E2/scores.csv` (sur `dev`, généré le 2026-11-25), lignes `common_complete`, c'est-à-dire l'intersection des cas complets avec le même masque, la MAE par compteur, puis la moyenne. Ils sont **identiques au score provisoire d'E2 du 2026-11-24**, calculé avec les mêmes fonctions d'E4.
  - Livraison à E4 : `data/prediction_results/EXP-E2/EXP-E2-predictions.zip` (12,9 Mo, SHA-256 `1619c83091786456…`), commité normalement, sans LFS. Il contient les `.pred.csv`, `.runs.csv` et `.cases_used.csv` des 6 méthodes (235 Mo une fois décompressé). À décompresser depuis `data/prediction_results/` avec `unzip -o EXP-E2/EXP-E2-predictions.zip`.
  - Prévisions : `data/prediction_results/EXP-E2/`, 6 fichiers, contrôlés par `src/eval/checks/check_forecasts.py` (tout conforme ; `fit_cutoff` vide pour les références, qui n'apprennent rien).
  - Calcul refaisable : `python -m src.models.known.score --experiment EXP-E2` (MOD-018). Il lit le zip et redonne les valeurs d'E4 à la décimale près.
  - Population : les 6 014 cas sont complets pour les 6 méthodes. **5 613 cas comparés** (ceux qui ont au moins une heure de vérité évaluable), 133 624 heures, 95 compteurs.

  | Méthode | MAE macro brute | MAE macro système (E4) | Couverture brute | Taux de repli (système) | Biais (E4, prévu − vrai) | Coût du calcul |
  | --- | --- | --- | --- | --- | --- | --- |
  | `reference` | 29,78 | 29,75 | 100 % | 10,4 % (son repli D-03) | +2,39 | cas par cas, 3 min 11 |
  | `reference_profile` | 27,00 | 27,01 | 100 % | 3,4 % (son repli D-03) | +8,47 | cas par cas, 3 min 19 |
  | `mlp` (graine 0) | 22,20 | 22,23 | 94,7 % | 5,3 % (`mlp_window_too_sparse`) | −0,81 | en bloc, 2 min 41 |
  | `mlp` (graines 0-2 : moyenne, étendue) | 22,36 ; 0,36 | 22,39 ; 0,36 | 94,7 % | 5,3 % | −0,13 (de −0,81 à +0,69) | en bloc, environ 2 min 36 chacune |
  | `hgb` | 22,24 | 22,25 | 100 % | 0 % | −1,13 | en bloc, 2 min 07 |

  En brut, les heures en repli des modèles sont marquées non prévues ; les références gardent leur propre repli (il fait partie de leur méthode). Le calcul cas par cas coûte environ 0,4 s par cas, celui de l'application.

- **Analyse, limites et décision** (définitive, confirmée par les scores d'E4) :

  - **Règle 1, appliquée telle quelle.** Face à la meilleure référence (`reference_profile`, 27,01) :
    - HGB : +17,6 %, meilleur sur 97 % des compteurs ;
    - MLP graine 0 : +17,7 %, sur 93 % ;
    - MLP graine 1 : +17,3 %, sur 94 % ;
    - MLP graine 2 : +16,4 %, sur 94 %.

    Les deux modèles passent largement le seuil de 5 % et la majorité des compteurs.
  - **Règle 2.** MLP graine 0 − HGB = −0,02 vélo/h, alors que l'étendue entre les graines du MLP est de 0,36 : l'écart n'est pas significatif. **Le HGB est retenu pour l'application** : plus simple, il sert 100 % des cas et n'a pas besoin de torch. Conclusion identique en brut.
  - **Biais** : les modèles sont presque sans biais (entre −1,1 et +0,7 vélo/h). La médiane des 4 semaines surestime de +8,5 vélos/h : elle ne voit pas la baisse de l'été, qu'elle copie des semaines précédentes plus chargées. Le gain des modèles vient en partie de là.
  - L'erreur de validation (environ 22 vélos/h) est plus élevée que le contrôle sur juin (environ 17,5) : l'été est plus difficile (vacances, 14 juillet, 15 août). Mais le gain sur les références est plus grand (environ 17 % contre 12 à 14 %).

  Limites connues dès maintenant :
  - protocole non validé ;
  - été seulement ;
  - modèles figés au 01/07, sans réapprentissage au 01/08 ;
  - décalages en UTC (I3) ;
  - règle d'admissibilité provisoire (C3/M2) ;
  - 4 sites en panne pendant l'été (MLP refusé, E2-TECH-003).

- **Lien vers données de résultats et figures** : `data/prediction_results/EXP-E2/` (le zip livré à E4), avec `<method_run_id>.pred.csv`, `.runs.csv`, `.cases_used.csv` et `.selection.json`. Ils sont produits par :

  ```sh
  python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv \
    --snapshot hist-20261117 --experiment EXP-E2 --variant <reference|reference_profile>
  python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv \
    --snapshot hist-20261117 --experiment EXP-E2 --variant <mlp|hgb> --model-run-id <id> --batch
  python -m src.models.known.score --experiment EXP-E2
  ```

  Le notebook [E2_EXP-03_choix_methode.ipynb](../../notebooks/E2_EXP-03_choix_methode.ipynb) refait le score et montre des cas.

- **Retour d'un partenaire et preuve d'utilisation** :
  - E4 : les prévisions ont été notées avec leur `backtest.py` (`scores.csv`, `scores_by_counter.csv`, `coverage.csv` sur `dev`, 2026-11-25), et les scores sont identiques aux nôtres ;
  - E5 : HGB `e2-hgb-ctx-20260701-s0-b357` annoncé comme modèle de l'application (`predict.DEFAULT_MODEL_RUN_IDS`).

## Décisions du gel (2026-11-24, validées par l'équipe)

1. Règle de choix : 5 % de mieux que la meilleure référence **et** meilleur sur plus de la moitié des compteurs ; entre MLP et HGB, écart plus grand que l'étendue entre les 3 graines, sinon le HGB ; MLP en graine 0.
2. HGB : `loss="absolute_error"`, `categorical=False`, `refit_on_holdout=False`, `max_iter=2000` (`b357` conservé, prévisions identiques à la version à 2 000). La loss est présentée à E4 comme proposition, sans changer cette fiche.
3. Graines 1 et 2 du MLP : apprises (`s1-9318`, `s2-6278`), voir le contrôle de reproductibilité.
4. Score : par E4 avec `evaluate_all` de `Metric.py`, sur les 6 014 cas, avec la version « brute » des prévisions pour les modèles seuls. Questions ouvertes à E4 (version de référence, biais global) : elles ne changent pas la règle.
5. Pas de réapprentissage au 01/08 : une seule version par méthode, figée au 01/07, notée dans les limites.

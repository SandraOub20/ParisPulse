# E2-TECH-004 - Premier apprentissage du HGB sur données réelles (essai technique)

- **Date, équipe, responsables et partenaires** : 2026-11-24, E2 ; Ania Garoui (assistée par Claude Code). Socle d'apprentissage commun : Idir (MOD-007) ; règles d'arrêt anticipé et de latence reprises du MLP d'Esther (MOD-008). Données E1 (`hist-20261117`).
- **Question et hypothèse** : l'apprentissage du HGB (`fit_hgb`, [MOD-010](../teams/E2_SUIVI.md#4-journal-des-modifications)) fonctionne-t-il sur tout le réseau des sites connus, sans fuite, et à quel coût ? Le modèle obtenu est-il plausible (contrôle sur l'arrêt anticipé) ? Essai technique : **aucune comparaison de méthodes ni choix de modèle** (protocole non validé par le professeur) et **aucune erreur calculée sur juillet–août**.
- **Références bibliographiques** :
  - Zeng et al. : se mesurer à des références simples ;
  - Hyndman & Athanasopoulos, §5.10 : découpage temporel plutôt qu'aléatoire, d'où l'arrêt anticipé sur les dernières semaines.
  
  Voir [BIBLIOGRAPHIE.md](../../doc/BIBLIOGRAPHIE.md). **Elle ne contient encore aucune référence sur le gradient boosting.** Avant la fiche EXP-E2-03, il faut ajouter et lire les références qui justifient le choix du modèle. Propositions, non encore lues :
  - Friedman (2001), *Greedy Function Approximation: A Gradient Boosting Machine* ;
  - Ke et al. (2017), *LightGBM*, dont s'inspire l'algorithme par histogrammes de scikit-learn ;
  - Makridakis et al. (2022), compétition M5 : modèles globaux de gradient boosting sur de nombreuses séries.
- **Instantané, protocole validé, code et paramètres** :
  - Instantané `hist-20261117`, dossier `data/processed/hist-20261117/`. Les empreintes SHA-256 n'ont pas été revérifiées pour cet essai ; elles l'ont été le 2026-11-23 (E2-TECH-003).
  - Protocole : aucun protocole validé. Coupure `fit_cutoff = 2026-06-30T22:00Z` (01/07/2026 minuit à Paris) et apprentissage depuis le début des données, comme proposé par D-17, identiques au MLP. Aucun `protocol_id` passé.
  - Code : [tabular.py](../../src/models/known/tabular.py), [features.py](../../src/models/known/features.py) (`f1.0`) et [train.py](../../src/models/known/train.py), branche `Team2`, **non commité** au moment de l'essai (base `478c810`).
  - Paramètres : réglages par défaut de `hgb_hyperparameters()` :
    - `HistGradientBoostingRegressor` de scikit-learn 1.9.1 ;
    - `loss="absolute_error"`, `learning_rate=0.1`, 500 arbres au plus ;
    - 31 feuilles, 20 lignes par feuille au minimum, sans régularisation L2, 255 classes ;
    - variables traitées comme numériques ;
    - arrêt anticipé sur 4 semaines, patience 20, sans réapprentissage sur le holdout.
    
    Autres réglages : graine 0 ; contexte complet (calendrier, grèves, météo prévue) ; latence 24 h (`config/project.example.yaml`) ; entrées = mesures seules (D-11).
  - Commande (apprentissage et bilan, sans sauvegarde) :

    ```sh
    .venv/Scripts/python -m src.models.known.tabular --snapshot hist-20261117 \
      --fit-cutoff 2026-06-30T22:00:00+00:00 --seed 0 --no-save
    ```

    Sans `--no-save`, la commande écrit `artifacts/models/e2-hgb-ctx-20260701-s0-b357/` : `model.joblib`, `metadata.json` et `training_report.json`.
- **Scénario, sites, dates et budget d'information autorisé** :
  - Scénario `known_site` : 97 compteurs `S_train` (49 groupes de sites). Les 9 groupes réservés à E3 sont exclus ; preuve : `excluded_site_groups` du bilan.
  - Une origine par jour à minuit (Paris), du 15/11/2023 au 29/06/2026 : ce sont les mêmes origines que le MLP, fixées par `train.fit`.
  - Entrées dont `interval_end <= origin − 24 h` ; contexte dont `available_at` est vide ou `<= origin` ; cibles publiées à `fit_cutoff`.
  - Arrêt anticipé : origines du 03/06 au 29/06/2026, **à l'intérieur** de la période d'apprentissage. Juillet–août ne sont jamais lus.
- **Facteur modifié et facteurs conservés** : sans objet (essai technique, une seule configuration).
- **Contrôles réalisés** :
  - 36 tests synthétiques ([tests/test_known_tabular.py](../../tests/test_known_tabular.py)), sans torch. Les principaux :
    - modifier tout ce qui suit `fit_cutoff` laisse les prévisions identiques ;
    - même graine : même modèle et même nombre d'arbres ;
    - une origine dont les cibles sont publiées après la coupure, hors minuit ou en double est refusée avant toute lecture de cible ;
    - le holdout regroupe des journées entières, commence 4 semaines avant la coupure, et ses cibles sont publiées à la coupure ;
    - une latence différente de la configuration est refusée (D-22) ;
    - refus motivés : origine hors minuit, avant la coupure, sans historique, contexte absent ;
    - une fenêtre clairsemée est prévue ;
    - le calcul en bloc égale le calcul cas par cas (écart ≤ 1e-9) ;
    - 24 sorties finies ≥ 0 ;
    - l'aller-retour `train.save_model` / `train.load_model` donne les mêmes prévisions ;
    - un modèle incompatible est refusé (format, version de variables, colonnes, latence, objet étranger).
  - Suite complète hors tests du MLP (torch absent de l'environnement local) : 242 tests passés ; `ruff check` et `ruff format --check` sans problème.
  - Sur données réelles :
    - le nombre d'arbres retenu (342) est bien le minimum de la courbe du holdout (362 arbres parcourus, arrêt après 20 sans progrès) ;
    - le holdout compte 2 560 origines et 61 370 cibles, comme l'arrêt anticipé du MLP (E2-TECH-003) : les deux modèles voient les mêmes journées.
- **Résultats mesurés** :

  *Apprentissage*

  | Mesure | Valeur |
  | --- | --- |
  | Compteurs / groupes de sites appris / groupes E3 exclus | 97 / 49 / 9 |
  | Lignes (compteur × origine × heure) apprentissage / holdout | 2 082 454 / 61 370 |
  | Origines apprentissage / holdout | 87 084 / 2 560 |
  | Part de NaN par variable (maximum) | 0,33 % (`lag_336h`) ; contexte : 0 % |
  | Arbres retenus | 342 sur 500 au plus |
  | MAE du holdout (toutes cellules) après 1 / 50 / 100 / 200 / 342 arbres | 76,8 / 20,3 / 18,9 / 18,3 / 17,9 vélos/h |
  | Temps | lecture 14,6 s ; compteurs et origines (`train.fit`, avant la méthode) ≈ 94 s ; `fit_hgb` 169,8 s, dont variables 43,4 s et deux apprentissages HGB 125,2 s ; total 278 s |
  | Mémoire | non mesurée (Windows : `_peak_memory_mb` indisponible) |

  *Contrôle sur l'arrêt anticipé* (juin 2026, 95 compteurs, 61 314 cellules où les trois prévisions existent)

  | Méthode | MAE moyenne entre compteurs (vélos/h) |
  | --- | --- |
  | HGB | 17,9 |
  | Médiane des 4 semaines précédentes (`profile_median_4w`), sans repli | 20,3 |
  | Référence hebdomadaire `y(t − 168 h)`, sans repli | 24,5 |

  Matériel : PC Windows, Intel x86_64, 22 threads, CPU, un seul processus.
- **Analyse, limites et décision** :
  - L'apprentissage sur tout le réseau tient en moins de 5 minutes sur un CPU de portable, ni GPU ni Snowflake nécessaires. Le temps dominant est celui des deux apprentissages (choix du nombre d'arbres, puis modèle final), suivi du calcul des origines dans `train.fit` (≈ 94 s, commun à toutes les méthodes et optimisable).
  - Sur juin, le HGB fait 27 % d'erreur de moins que la référence hebdomadaire et 12 % de moins que la médiane sur 4 semaines, sur les mêmes cellules. C'est un **contrôle de bon fonctionnement, pas une comparaison** :
    - juin a servi à choisir le nombre d'arbres, donc l'erreur du HGB y est optimiste ;
    - les références sont lues sans leur repli ;
    - un seul mois, en été ;
    - le protocole n'est pas validé.
  - **Ne pas comparer ce 17,9 au 17,5 du MLP** (E2-TECH-003) : les journées sont les mêmes, mais les cellules diffèrent. Le MLP exclut les fenêtres trop vides ; le HGB les garde car il tolère les NaN. Chaque modèle a aussi choisi ses réglages sur ce mois. La comparaison officielle se fera sur la validation, avec les scores d'E4, selon la fiche EXP-E2-03 figée avant les scores.
  - La courbe du holdout est plate après environ 200 arbres (18,3 → 17,9 vélos/h) : le nombre exact d'arbres compte peu, et le plafond de 500 n'est pas atteint.
  - Couverture : le HGB ne refuse un cas que dans quatre situations : origine hors minuit, origine antérieure à la coupure, aucune mesure publiée, contexte absent. Les 4 sites peu mesurés en été, que le MLP refuse (E2-TECH-003), seront donc prévus par le HGB à partir de variables en partie manquantes. La qualité de ces prévisions est à examiner avec E4. **La couverture sur juillet–août n'est pas encore mesurée.**
  - Limites :
    - règle d'admissibilité provisoire (C3/M2) ;
    - décalages en UTC (I3) ;
    - `fit_cutoff` non écrit dans `config/project.yaml` (D-17) ;
    - une seule graine (sans sous-échantillonnage, le HGB est déterministe ; la graine n'influe que si des réglages aléatoires sont ajoutés) ;
    - modèle non réappris sur le holdout (même question que D-20) ;
    - mémoire non mesurée ;
    - code non commité ;
    - aucune référence de gradient boosting dans la bibliographie.
  - **Décisions et suites** :
    - **loss** : `absolute_error` reste le réglage par défaut pour cet essai ; le choix définitif revient à E4 ;
    - **branchement** : Idir branche les variantes `hgb` et `mlp` dans `predict.py`, avec repli sur la référence ;
    - **reste à faire côté E2** : sauvegarder un modèle, mesurer la couverture et le coût par cas sur la validation, compléter la bibliographie, puis comparer selon EXP-E2-03, réglages figés avant les scores.
- **Lien vers données de résultats et figures** : aucun fichier conservé (`--no-save`). Le bilan complet (`training_report`, courbe du holdout comprise) est recalculable par la commande ci-dessus : sans sous-échantillonnage, l'apprentissage est déterministe sur une même machine.
- **Retour d'un partenaire et preuve d'utilisation** : à obtenir.
  - Idir : branchement dans `predict.py` ; mise en commun de `_check_training_origins` et `_holdout_start` avec `neural.py`.
  - E4 : choix de la loss ; codes de refus `hgb_*` ; couverture plus large que le MLP (comparer sur les mêmes cas complets).
  - E5 : codes de refus `hgb_*`, temps d'apprentissage.

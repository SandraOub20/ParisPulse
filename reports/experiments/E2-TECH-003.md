# E2-TECH-003 - Premier apprentissage du MLP sur données réelles (essai technique)

- **Date, équipe, responsables et partenaires** : 2026-11-23, E2 ; Esther (assistée par Claude Code). Préparation des exemples, réseau et socle d'apprentissage : Idir (MOD-007). Données E1 (`hist-20261117`).
- **Question et hypothèse** : l'apprentissage du MLP (`fit_mlp`, [MOD-008](../teams/E2_SUIVI.md#4-journal-des-modifications)) fonctionne-t-il sur tout le réseau des sites connus, sans fuite, et à quel coût ? Le réseau obtenu est-il plausible (contrôle sur l'arrêt anticipé) et quelle part des cas de validation peut-il servir sans repli ? Essai technique : **aucune comparaison de méthodes ni choix de modèle** (protocole non validé par le professeur) et **aucune erreur calculée sur juillet–août**.
- **Références bibliographiques** : Salinas et al., *DeepAR* (normalisation par le niveau de la série, pondération des exemples par leur échelle) ; Zeng et al. (se mesurer à des références simples). Voir [BIBLIOGRAPHIE.md](../../doc/BIBLIOGRAPHIE.md).
- **Instantané, protocole validé, code et paramètres** :
  - Instantané `hist-20261117` ; empreintes SHA-256 de `counts.csv`, `context.csv` et `inventory_quality.csv` conformes à `data/manifests/hist-20261117.json` (vérifiées le 2026-11-23).
  - Protocole : aucun protocole validé. `fit_cutoff = 2026-06-30T22:00Z` (01/07/2026 minuit à Paris) et apprentissage depuis le début des données, comme proposé par D-17 ; étiquette `protocol_id = proto-v1`.
  - Code : [neural.py](../../src/models/known/neural.py) et [train.py](../../src/models/known/train.py) (MOD-008), branche `Team2-Esther`, non commité au moment de l'essai (`code_version = efb7274-dirty` dans `metadata.json`).
  - Paramètres : réglages par défaut de `mlp_hyperparameters()` (2 couches de 128, dropout 0,1, AdamW avec un pas de 0,001 et une régularisation de 0,0001, lots de 256, 100 époques au plus, patience 8, arrêt anticipé sur 4 semaines, perte L1 pondérée par le niveau) ; graine 0 ; contexte complet (calendrier, grèves, météo prévue) ; latence 24 h (`config/project.example.yaml`) ; entrées = mesures seules (D-11).
  - Commande (apprentissage, sauvegarde et bilan) :

    ```sh
    uv run --locked --no-sync --group dl python -m src.models.known.neural \
      --snapshot hist-20261117 --fit-cutoff 2026-06-30T22:00:00+00:00 --seed 0 --protocol-id proto-v1
    ```

- **Scénario, sites, dates et budget d'information autorisé** : `known_site` ; 97 compteurs `S_train` (49 groupes de sites), les 9 groupes réservés à E3 exclus (preuve : `excluded_site_groups` de `metadata.json`) ; une origine par jour à minuit (Paris), du 15/11/2023 au 29/06/2026 ; entrées dont `interval_end <= origin − 24 h` ; contexte dont `available_at` est vide ou `<= origin` ; cibles publiées à `fit_cutoff`. Arrêt anticipé : origines du 03/06 au 29/06/2026, **dans** la période d'apprentissage. Juillet–août : lus uniquement pour compter les cas servis.
- **Facteur modifié et facteurs conservés** : sans objet (essai technique, une seule configuration).
- **Contrôles réalisés** :
  - 44 tests synthétiques ([tests/test_known_neural_fit.py](../../tests/test_known_neural_fit.py)). Les principaux :
    - modifier tout ce qui est publié après `fit_cutoff` laisse les poids identiques ; un témoin positif (retirer une cible publiée) les change ;
    - les cibles non mesurées, les fenêtres trop vides et les sites réservés n'ont aucun effet sur les poids ;
    - même graine, mêmes poids, et l'état aléatoire global de torch n'est pas modifié ;
    - l'époque rendue est la meilleure ;
    - la prévision cas par cas égale le calcul en bloc ;
    - refus motivés (origine hors minuit ou avant la coupure, latence, contexte, fenêtre, niveau) ;
    - l'aller-retour de sauvegarde donne les mêmes prévisions ;
    - un fichier au format 1 reste lisible.
  - Suite complète : 266 tests passés ; `ruff check` et `ruff format --check` sans problème.
  - Sur données réelles :
    - 90 736 exemples, comme le décompte d'Idir (MOD-007) ;
    - aucun exemple au contexte incomplet ;
    - l'époque retenue (20) est bien le minimum de la perte d'arrêt anticipé (historique relu) ;
    - modèle rechargé par `train.load_model` (SHA-256 et empreinte de configuration vérifiés) ;
    - 40 cas de validation tirés au hasard (graine 0) passés par le chemin réel (`build_inputs` puis `predict_mlp`) : tous servis, écart maximal de 0,0003 vélo/h avec le calcul en bloc (arrondi `float32`), aucune prévision négative.
- **Résultats mesurés** :

  *Apprentissage*

  | Mesure | Valeur |
  | --- | --- |
  | Exemples (compteur × origine) | 90 736 |
  | Exclus : fenêtre trop vide / sans cible / contexte incomplet | 2 047 / 171 / 0 |
  | Apprentissage / arrêt anticipé | 85 958 / 2 560 exemples (2 059 949 / 61 370 cibles) |
  | Exemples ayant une cible > 10 fois le niveau de leur fenêtre | 0,74 % (maximum : 471 fois) |
  | Époques | 28 ; meilleure : 20 (arrêt après 8 époques sans progrès) |
  | Perte (L1 pondérée) apprentissage / arrêt anticipé | 0,290 → 0,170 / 0,220 → 0,162 (époque 20) |
  | Paramètres du réseau | 73 368 ; fichier de poids de 300 Ko |
  | Temps | lecture 11,8 s ; `train.fit` (préparation, apprentissage, bilan) 33,3 s ; total 94 s |
  | Mémoire (pic du processus) | 1 251 Mo |

  *Contrôle sur l'arrêt anticipé* (juin 2026, 95 compteurs ayant des cibles, 61 313 cellules communes aux deux méthodes)

  | Méthode | MAE moyenne entre compteurs (vélos/h) |
  | --- | --- |
  | MLP | 17,5 |
  | Référence hebdomadaire `y(t − 168 h)`, mêmes cellules, sans repli | 24,5 |

  *Couverture des origines de validation (juillet–août 2026), sans score*

  | Mesure | Valeur |
  | --- | --- |
  | Cas (97 compteurs × 62 jours) | 6 014 |
  | Servis par le MLP | 5 694 (94,7 %) |
  | Refusés (repli sur la référence) | 320, tous `mlp_window_too_sparse` |
  | Compteurs concernés (4 sites, les deux sens) | `100047545` (0 % servi), `100036718` (14,5 %), `100007049` (58,1 %), `100056336` (69,4 %) |
  | Temps | 3,2 s pour les 6 014 cas en bloc ; 0,39 s par cas (médiane) par `build_inputs` + `predict_mlp` |

  Couverture recalculable avec :

  ```python
  from collections import Counter
  import pandas as pd
  from src.models.known import features as F, neural as N, train

  model = train.load_model("e2-mlp-ctx-20260701-s0-9ce9")
  data = train.load_training_data("hist-20261117")
  days = pd.date_range("2026-07-01", "2026-08-31", freq="D").tz_localize("Europe/Paris").tz_convert("UTC")
  origins = pd.DataFrame(
      [(c, d) for c in F.training_counters(data.inventory) for d in days], columns=["counter_id", "origin"]
  )
  windows = N.build_windows(data.counts, origins, data.context, use_context=True)
  print(Counter(N.refusal_reasons(windows)))  # None = cas servi par le MLP
  ```

  Matériel : PC Linux x86_64, 8 threads (4 utilisés par torch), CPU, un seul processus.
- **Analyse, limites et décision** :
  - L'apprentissage sur tout le réseau tient en 33 s et 1,3 Go sur un CPU de portable : ni GPU ni Snowflake nécessaires.
  - Sur juin, le MLP fait 29 % d'erreur de moins que la référence hebdomadaire, sur les mêmes cellules. C'est un **contrôle de bon fonctionnement, pas une comparaison** :
    - juin a servi à choisir l'époque, donc l'erreur du MLP y est optimiste ;
    - la référence est ici `y(t − 168 h)` sans son repli ;
    - un seul mois, en été ;
    - le protocole n'est pas validé.

    La comparaison officielle se fera sur la validation, scorée par E4, après la fiche EXP-E2-03 figée avant les scores.
  - La perte d'apprentissage baisse jusqu'à la fin, alors que celle de juin stagne dès l'époque 13 (entre 0,163 et 0,167) : l'arrêt anticipé est utile. D'une époque à l'autre, la perte de juin varie d'environ ±0,005, si bien que le choix de l'époque dépend en partie du hasard. La variabilité entre graines n'est pas encore mesurée.
  - Cibles extrêmes : 0,74 % des exemples ont une cible au-delà de 10 fois le niveau de leur fenêtre, jusqu'à 471 fois (fenêtres effondrées par des zéros). La perte L1 borne leur influence : son gradient ne dépend que du signe de l'erreur, ce que démontre un test dédié. Décision : pas de plafond arbitraire (D-19).
  - Couverture : 5,3 % des cas de validation partiraient en repli. Ils se concentrent sur 4 sites peu ou pas mesurés pendant l'été, dont `100047545`, refusé à 100 %. Ce sont des cas difficiles tout trouvés pour l'approfondissement : qualité du repli sur ces sites, à examiner avec E4.
  - Le coût cas par cas (0,39 s) vient surtout de la préparation du contexte complet à chaque cas (`build_inputs`, `_prepare_context`). C'est acceptable pour l'application, qui traite un cas à la fois. Pour les expériences, utiliser `predict_windows`, qui donne les mêmes valeurs.
  - Limites :
    - règle d'admissibilité provisoire (C3/M2) ;
    - décalages en UTC (I3) ;
    - `fit_cutoff` non écrit dans `config/project.yaml` (D-17) ;
    - une seule graine ;
    - réseau non réappris sur les semaines d'arrêt anticipé (D-20) ;
    - modèle entraîné sur du code non commité.
  - Décision : le MLP est prêt à être branché dans `predict.py` (recette dans [E2_PRISE_EN_MAIN.md](../teams/E2_PRISE_EN_MAIN.md)) puis comparé selon EXP-E2-03, réglages figés avant les scores.
- **Lien vers données de résultats et figures** : `artifacts/models/e2-mlp-ctx-20260701-s0-9ce9/` (`weights.pt`, `metadata.json`, `training_report.json`, avec la perte de chaque époque), exclu de Git et recalculable par la commande ci-dessus (même graine, même machine : mêmes poids).
- **Retour d'un partenaire et preuve d'utilisation** : à obtenir.
  - Idir : socle modifié (contrôle de la latence dans `train.fit`, format 2 de `weights.pt`, test « pas encore entraînable » remplacé).
  - Ania : même règle de latence pour le HGB.
  - E4 : contrôle sur l'arrêt anticipé, sites en panne pendant la validation.
  - E5 : codes de refus `mlp_*`, coût par cas.

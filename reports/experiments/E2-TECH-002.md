# E2-TECH-002 - Jeu d'apprentissage des variables f1.0 sur données réelles (essai technique)

- **Date, équipe, responsables et partenaires** : 2026-11-20, E2 ; Ania Garoui (assistée par Claude Code). Données E1 (`hist-20261117`).
- **Question et hypothèse** : les variables `f1.0` ([features.py](../../src/models/known/features.py), MOD-006) se calculent-elles sur tout le réseau des sites connus, sans fuite, avec le même résultat à l'apprentissage et à l'inférence, et à quel coût ? Essai technique : **aucun modèle entraîné, aucune comparaison** (protocole non validé par le professeur).
- **Références bibliographiques** : aucune à ce stade (choix du modèle à venir, B08).
- **Instantané, protocole validé, code et paramètres** :
  - Instantané `hist-20261117` ; empreintes SHA-256 de `counts.csv`, `context.csv` et `inventory_quality.csv` conformes à `data/manifests/hist-20261117.json`.
  - Protocole : aucun protocole validé. `fit_cutoff = 2026-05-31T22:00Z` (minuit local du 01/06/2026), soit la première origine de validation de `proto-v0` d'E4. **Provisoire** : le protocole proposé indique plutôt le 01/07 (écart (3) signalé à E4).
  - Code : `features.py` f1.0, branche `Team2`, non commité au moment de l'essai (base `b23a1b9`).
  - Paramètres : latence 24 h (`config/project.example.yaml`), entrées `measured` (D-11), cibles `count_raw` si `is_scoreable`, tous les groupes de contexte, 4 semaines de préchauffage.
  - Script : `build_training_frame(counts, training_origins(counts, training_counters(inventory), fit_cutoff), context, fit_cutoff)`, lancé depuis un script local hors dépôt. Les chiffres ci-dessous sont recalculables avec ces trois appels.
- **Scénario, sites, dates et budget d'information autorisé** : `known_site` ; 97 compteurs `S_train` d'E1 (67 `retained` + 30 `robustness`), aucun groupe de site partagé avec `S_dev_new` / `S_test_new` (contrôlé par `training_counters`) ; une origine par jour à minuit (Paris), du 15/11/2023 au 30/05/2026 ; entrées dont `interval_end <= origin − 24 h`, contexte dont `available_at` est vide ou `<= origin` ; cibles dont `interval_end + 24 h <= fit_cutoff`.
- **Facteur modifié et facteurs conservés** : sans objet (essai technique).
- **Contrôles réalisés** :
  - 15 tests synthétiques ([tests/test_known_features.py](../../tests/test_known_features.py)) : changement d'heure, zéro contre manque, absence de fuite (futur modifié sans effet), jointures du contexte, ablation, égalité des deux chemins, cibles, origines, exclusion des sites réservés. Suite complète : 181 tests passés ; `ruff check` et `ruff format --check` sans problème.
  - Sur données réelles :
    - toutes les cibles publiées avant `fit_cutoff` et toutes les entrées disponibles avant l'origine (`max_input_available_at <= origin`) ;
    - **égalité exacte** entre le calcul en bloc et le calcul par cas (`build_inputs` + `build_feature_frame`) sur 12 couples compteur/origine tirés au hasard ;
    - 4 lignes vérifiées indépendamment en relisant `counts.csv` et `context.csv` (`lag_168h`, `level_24h`, `temp_prev`, `is_holiday`) : toutes identiques, à l'arrondi `float32` près.
- **Résultats mesurés** :

  | Mesure | Valeur |
  | --- | --- |
  | Couples compteur/origine | 87 826 |
  | Lignes (horizons avec cible mesurée) | 2 075 614 |
  | Couples avec 24 cibles | 99,2 % |
  | Cibles à zéro (mesurées) | 3,0 % |
  | Part de NaN, variables d'historique | ≤ 0,33 % (`lag_336h`) |
  | Part de NaN, contexte | 0 % |
  | Lignes avec férié / vacances / grève | 64 937 / 683 362 / 53 263 |
  | Mémoire de X | 374 Mo |
  | Temps : lecture / origines / construction | 5,6 s / 22,5 s / 204 s |

  Matériel : PC Windows 11, CPU, un seul processus. Le temps de construction est mesuré avec `tracemalloc` actif, qui ralentit le calcul (pic suivi : 819 Mo).
- **Analyse, limites et décision** :
  - Les variables sont prêtes pour un premier modèle. L'apprentissage sur tout le réseau tient en mémoire sur un portable.
  - Fériés : 64 937 lignes en apprentissage, mais la validation proposée (juillet–août) n'a que 2 jours fériés et le test d'octobre aucun (plan §3). L'ablation sur les fériés aura un effectif faible ; les vacances et les grèves varient davantage.
  - Grèves : recensement manuel d'E1, possiblement incomplet (voir `context_sources.json`).
  - Météo prévue : deux modèles successifs (bascule le 20/01/2024) et disponibilité supposée (`valid_time − 42 h`, pas d'heure d'émission réelle).
  - Limites : règle d'admissibilité provisoire (C3/M2), décalages en UTC (I3), `fit_cutoff` provisoire, construction de 204 s optimisable si nécessaire.
- **Lien vers données de résultats et figures** : aucun fichier écrit (jeu construit en mémoire).
- **Retour d'un partenaire et preuve d'utilisation** : à obtenir. Présenter à E3 les variables et la nouvelle signature (`context_groups`), et à E1 la lecture faite de `context.csv` (rôles, jointure météo sur `interval_end`, `available_at` des grèves).

# EXP-E2-03 - Quelle méthode pour les sites connus : MLP, HGB ou référence ?

> **Statut : brouillon, à figer avant tout score.** Les points marqués « à valider » sont des propositions. Une fois la fiche figée, la date et le commit sont reportés ici, et plus rien n'est modifié avant la lecture des scores. Les résultats restent vides jusque-là.

- **Date, équipe, responsables et partenaires** :
  - Brouillon le 2026-11-24, E2 : Idir, Esther, Ania, Emmanuelle.
  - Rôles proposés (à valider) : chaque modèle est porté par son auteur, Esther pour le MLP et Ania pour le HGB. Idir porte le calcul des prévisions (`predict.py`, MOD-011) et le contrôle des populations comparées.
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
    | `mlp`, graines 1 et 2 | à entraîner, mêmes réglages | seulement pour mesurer la variabilité, jamais pour choisir |
    | `hgb` | `e2-hgb-ctx-20260701-s0-b357` | `hgb_hyperparameters()` par défaut ; `loss="absolute_error"` ; `refit_on_holdout=False` ; `categorical=False` (**à valider**, E2-TECH-004) |

  - Communs à toutes les méthodes :
    - `fit_cutoff` au 2026-06-30T22:00Z, apprentissage depuis le début des données (D-17) ;
    - latence de 24 h (D-22) ;
    - entrées : mesures seules (D-11) ;
    - contexte complet `e1-context/0.3.0` pour les deux modèles ;
    - 97 compteurs `S_train`, groupes E3 exclus.

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
    - avec ou sans contexte, et par groupe de contexte (D-12) ;
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
  - **Indicateurs secondaires**, sur la même population :
    - couverture 24 h (cas complets / 6 014) ;
    - taux de repli et causes (`mlp_*`, `hgb_*`) ;
    - biais moyen ;
    - MAE par horizon, par heure locale et par compteur ;
    - gain sur la meilleure référence ;
    - nombre de compteurs où la méthode bat la meilleure référence ;
    - coût : apprentissage, inférence par cas, mémoire et matériel.
  - **Règle de choix pour l'application**, figée maintenant (**à valider**) :
    1. Un modèle n'est retenu que si sa MAE macro « système » est **inférieure d'au moins 5 %** à celle de la meilleure référence, sur les mêmes cas. Sinon, l'application garde la meilleure référence.
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

  _À remplir avec les valeurs de `scores.csv` d'E4, après le gel._

  | Méthode | MAE macro brute (intersection) | MAE macro système (6 014 cas) | Couverture brute | Taux de repli | Biais | Inférence / cas |
  | --- | --- | --- | --- | --- | --- | --- |
  | `reference` | | | | | | |
  | `reference_profile` | | | | | | |
  | `mlp` (graine 0) | | | | | | |
  | `mlp` (graines 0-2 : moyenne, étendue) | | | | | | |
  | `hgb` | | | | | | |

  Taille de l'intersection commune : _à remplir_ cas, _à remplir_ compteurs.

- **Analyse, limites et décision** :

  _À remplir après les scores._

  Limites connues dès maintenant :
  - protocole non validé ;
  - été seulement ;
  - modèles figés au 01/07, sans réapprentissage au 01/08 ;
  - décalages en UTC (I3) ;
  - règle d'admissibilité provisoire (C3/M2) ;
  - 4 sites en panne pendant l'été (MLP refusé, E2-TECH-003).

- **Lien vers données de résultats et figures** : `data/prediction_results/EXP-E2-03/<method_run_id>.pred.csv` et `.runs.csv`, plus `cases_used.csv` et `selection.json`, produits par :

  ```sh
  python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv \
    --snapshot hist-20261117 --experiment EXP-E2-03 --variant <reference|reference_profile>
  python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv \
    --snapshot hist-20261117 --experiment EXP-E2-03 --variant <mlp|hgb> --model-run-id <id>
  ```

- **Retour d'un partenaire et preuve d'utilisation** : à obtenir.
  - E4 : accord sur la population, le masque et l'intersection, puis scores.
  - E5 : `model_run_id` servi par l'application, selon la règle de choix.

## Points à trancher avant le gel

1. Accord de l'équipe sur la règle de choix : le seuil de 5 % et la règle des graines.
2. Réglages du HGB : `categorical`, `refit_on_holdout`, et la loss, à confirmer avec E4.
3. Entraîner les graines 1 et 2 du MLP (environ 1 min 30 chacune).
4. E4 : son code de score sait-il faire l'intersection commune entre plusieurs méthodes et appliquer le même masque ? Sinon, qui la calcule ?
5. Faut-il réapprendre au 01/08 pour la seconde moitié de la validation (exemple du PROTOCOLE §3) ? Proposition : non, pour garder une seule version par méthode, à noter comme limite.

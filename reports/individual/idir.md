# Journal individuel - Idir (équipe 2, sites connus)

Format : [doc/SUIVI_ET_REMISE.md §4](../../doc/SUIVI_ET_REMISE.md). Entrées les plus récentes en haut. Reprise du code par l'équipe : [E2_PRISE_EN_MAIN.md](../teams/E2_PRISE_EN_MAIN.md).

---

## 2026-11-24 - Vérification du MLP, branchement de `mlp` et `hgb` dans `predict.py`

- **Objectif** : rendre le MLP (Esther) et le HGB (Ania) calculables par E4 et appelables par E5, avec repli sur la référence.

### Travail réalisé

- Branche mise à jour depuis `dev` et `Team2` (MLP, HGB sauvegardé, E3, appli E5) : fusion sans conflit.
- **[predict.py](../../src/models/known/predict.py)** (MOD-011) : `load_trained`, `trained_forecast`, `load_context` ; variantes `mlp` / `hgb` dans `predict_24h`, `run_experiment` et la commande.
- **Tests** : 21 tests ([test_known_predict_trained.py](../../tests/test_known_predict_trained.py)), 371 au total, tous passants.

### Contrôles

- **MLP recalculé indépendamment** sur le holdout de juin : MAE 17,49, comme le rapport d'Esther. Sur les mêmes cellules : médiane 4 semaines 20,3 ; `t − 168 h` 24,5. Le gain honnête est donc ≈ 14 % (face à la médiane), pas 29 %. Meilleur que la médiane sur 84 compteurs sur 95 ; biais −1,1 vélo/h. Contrôle seulement : juin a servi à l'arrêt anticipé.
- **Vrai HGB** : modifier les heures publiées après la coupure ne change rien ; témoin positif : modifier la semaine visible change la prévision.
- **25 vrais cas de validation**, cibles non lues : HGB 25 `ok` ; MLP 10 replis sur le site troué `100047545`.

### Analyse et décisions

- **Le contexte est obligatoire** pour nos deux modèles : sans lui, ils se replient sur tous les cas. La commande le charge donc.
- **Méthode lue dans `metadata.json` avant l'import** : un HGB peut tourner sans torch.
- **Pour E3**, simulation sur sites `S_train` en juin, en gardant seulement les L dernières heures : sans le seuil de 84 h, le MLP actuel tient à 72 h (28,4 contre 38,6 pour la référence au même budget) mais se trompe à 24 h (biais +42). L'adaptation reste le travail d'E3 (sujet p. 6) ; nous fournissons les modèles et leurs conditions d'utilisation.

### Pistes gardées pour plus tard

- **Ma comparaison** : MLP appris avec ou sans masquage des fenêtres, sur les historiques incomplets des sites connus (approfondissement E2 « historique incomplet »). À figer dans une fiche avant les scores.
- `min_observed_hours` en paramètre de `build_windows` (84 par défaut).

### Partenaires

- Emmanuelle : `predict.py` modifié.
- E3 : `load_model` attend un identifiant, pas un chemin (`Team3-massinissa`) ; `manager` non importé dans `adapt.py`.
- E4 / E5 : commande, codes `mlp_*` / `hgb_*`, contexte obligatoire.

### Prochaine étape

- Fiche EXP-E2-03 figée, puis calcul complet de la validation (≈ 50 min par modèle).

---

## 2026-11-22 - Contrôle des données E1, socle `train.py`, préparation du MLP

- **Objectif** : prendre en charge l'expérience de deep learning (MLP compact sur CPU). Question : **un réseau compact vaut-il son coût face au HGB et aux références ?**
- **Outils** : VS Code, Python 3.11, pandas, torch 2.15.0 (CPU), pytest, ruff.

### Travail réalisé

- **[train.py](../../src/models/known/train.py)**, socle commun au HGB et au MLP :
  - `fit` choisit une seule fois les compteurs (sites E3 exclus) et les origines, puis appelle la méthode : toutes les méthodes apprennent sur les mêmes données ;
  - `save_model` / `load_model` : SHA-256 des poids, refus d'écraser, `metadata.json` au format du projet ;
  - `load_training_data` : en entrée, vraies mesures seulement ;
  - nommage `e2-<méthode>-<ctx|noctx>-<coupure>-s<graine>-<empreinte>`.
- **[neural.py](../../src/models/known/neural.py)** :
  - `build_windows` : un exemple par compteur × origine, 419 entrées (168 h normalisées, 168 masques, la journée, la météo prévue heure par heure), 24 sorties ;
  - `MLPNet` minimal (73 368 paramètres), `save_mlp` / `load_mlp`.
- **Tests** : 41 tests ajoutés ([test_known_train.py](../../tests/test_known_train.py), [test_known_neural.py](../../tests/test_known_neural.py)), 222 au total, tous passants.

### Contrôles

- **Données E1 (`hist-20261117`)** :
  - SHA-256 conformes au manifeste ;
  - grille complète (3 053 599 lignes), 0 doublon ;
  - aucune valeur remplie par E1 utilisée comme cible ;
  - sites E3 vides avant leur installation fictive.
- **Raccords** :
  - janvier 2024 (canaux recollés par E1) : rapport janvier/décembre 0,85, identique à l'année suivante, donc pas de marche ;
  - archives → flux (16/10/2025) : pas de cassure (256k, 263k, 242k vélos/jour).
- **`proto-v1` d'E4** : 6 014 cas de validation, 97 compteurs ; les 3 écarts de `proto-v0` sont corrigés.
- **`build_windows`** :
  - modifier le futur ne change pas les entrées ;
  - calcul en bloc = calcul cas par cas ;
  - invariance d'échelle (×10) ;
  - vide ≠ zéro mesuré ;
  - cas réel Pont National du 10/03/2026 identique au calcul à la main.
- **Sauvegarde** : aller-retour identique ; refus d'un fichier modifié, d'une fiche retouchée, d'entrées rangées autrement, d'un fichier contenant du code.

### Résultats

- Données saines pour apprendre depuis 2023. Réserve : **29 heures au-dessus de 1 500 vélos/h sur 5 compteurs, gardées comme cibles** (par exemple 8 190 à 5 h, rue Lecourbe, médiane 56).
- 90 736 exemples d'apprentissage (15/11/2023 → 29/06/2026), construits en 5 s ; 97,7 % utilisables.
- Partie commune de `fit` : 70 s, dont l'essentiel dans `training_origins`.

### Analyse et décisions

- **Correction de conception** : la première version avait 696 entrées. 278 étaient inutiles : l'heure était déjà donnée par la position de la sortie, et le jour, les fériés, les vacances et les grèves étaient recopiés 24 fois. Je passe à 419 entrées, sans perte d'information.
- **Normalisation par la moyenne de la fenêtre**, comme dans DeepAR (Salinas et al.), plutôt qu'un Z-score global : compteurs de 5 à 300 vélos/h, niveau qui dérive dans le temps.
- **Limite du MLP** : il doit apprendre par la position le lien entre une heure et son masque. Or 0,8 % seulement des heures manquent. À analyser : l'erreur avec et sans trous.
- **Pour l'entraînement** : environ 0,1 % des cibles normalisées dépassent 59 fois le niveau (fenêtres effondrées par des zéros). À traiter dans la perte, à décider avant les scores.
- **Erreur corrigée** : j'avais d'abord retenu le 11/10/2025 comme début de l'apprentissage, d'après le protocole écrit. La décision réelle est le début des données (2023), mais elle n'est écrite nulle part : à faire corriger par E4.

### Pistes gardées pour plus tard (un seul facteur changé chacune)

- **Année d'avant en entrée** : prévision naïve sur l'été 2025, MAE de 26,2 contre 19,2 pour la semaine d'avant. Elle ne fait mieux qu'à la rentrée. Piège : un rapport de niveaux qui explose si le compteur était en panne l'an dernier.
- **Zéros suspects** : mettre le masque à 0 sur au moins 24 h de zéros, recomptés dans la fenêtre (pas avec le drapeau d'E1, qui utilise le futur).
- **Normalisation** : moyenne de la fenêtre contre Z-score global.

### Partenaires

- **E2** : message préparé sur la date de début non écrite et la coupure d'E2-TECH-002 au 01/06 au lieu du 01/07.
- **E4** : demander `train_start` dans `project.yaml`, signaler les pics gardés comme cibles.
- **E5** : `verifier_valeurs` (`Team5-integration`) refuse les valeurs vides, alors que notre contrat dit « vide = pas de prévision, jamais 0 ». Message préparé pour Giovanni.
- **Esther** : lui proposer `fit_mlp` et `predict_mlp`.
- Retours à consigner.

### Prochaine étape

- Fait : commit `4684e7c` (+ `efb7274`), fusionné dans `Team2` et poussé ; entrée MOD-007 dans [E2_SUIVI.md](../teams/E2_SUIVI.md).
- Squelettes documentés de `fit_mlp` / `predict_mlp` pour Esther.
- Brancher `variant="model"` dans `predict.py` (avec repli sur la référence) ; fiche EXP-E2-03 figée avant les scores.

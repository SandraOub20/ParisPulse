# Journal individuel - Idir (équipe 2, sites connus)

Format : [doc/SUIVI_ET_REMISE.md §4](../../doc/SUIVI_ET_REMISE.md). Entrées les plus récentes en haut. Reprise du code par l'équipe : [E2_PRISE_EN_MAIN.md](../teams/E2_PRISE_EN_MAIN.md).

---

## 2026-11-24 - Vérification du MLP, branchement de `mlp` et `hgb`, fiches EXP-E2-03 / 04 / 05, reconstruction de `Team2`

- **Objectif** : rendre le MLP (Esther) et le HGB (Ania) calculables par E4 et appelables par E5, avec repli sur la référence ; préparer les comparaisons avant les scores.

### Travail réalisé

- Branche mise à jour depuis `dev` et `Team2` (MLP, HGB sauvegardé, E3, appli E5).
- **[predict.py](../../src/models/known/predict.py)** (MOD-011) : `load_trained`, `trained_forecast`, `load_context` ; variantes `mlp` / `hgb` dans `predict_24h`, `run_experiment` et la commande.
- **Fiches** (brouillons, MOD-012 et MOD-013) : [EXP-E2-03](../experiments/EXP-E2-03.md), MLP / HGB / références, règle de choix fixée d'avance ; [EXP-E2-04](../experiments/EXP-E2-04.md), avec ou sans contexte.
- **Modèles appris** (MOD-013) : MLP graines 1 et 2, MLP sans contexte, HGB sans contexte (`max_iter=2000`).
- **Reconstruction de `Team2`** (MOD-014) : le commit d'E5 `fdc06c1` a été retiré de `dev`. Notre fusion l'avait fait entrer dans `Team2` : branche reconstruite à partir de MOD-013, sur le `dev` propre. Les contrôles d'éligibilité (idée de Sandra) et les modèles par défaut (D-24) sont réécrits dans `predict.py`, sans son fichier `mlp_forecast.py`. Ancienne version gardée dans `sauvegarde/Team2-idir-09d9891`.
- **Documents d'équipe** : [E2_PRISE_EN_MAIN.md](../teams/E2_PRISE_EN_MAIN.md) et [E2_SUIVI.md](../teams/E2_SUIVI.md) mis à jour (HGB, branchement, architecture).
- **Tests** : 384 au total ; tous les tests E2 passent. Un seul échec, dans un test d'E3 (`test_new_predict.py`, cas `team2-adapted`), qui échoue aussi sur `dev` seul.

### Contrôles

- **MLP recalculé indépendamment** sur le holdout de juin : MAE 17,49, comme le rapport d'Esther. Sur les mêmes cellules : médiane 4 semaines 20,3 ; `t − 168 h` 24,5. Le gain honnête est ≈ 14 % (face à la médiane), pas 29 %. Contrôle seulement : juin a servi à l'arrêt anticipé.
- **Vrai HGB** : modifier les heures publiées après la coupure ne change rien ; témoin positif : modifier la semaine visible change la prévision.
- **Reproductibilité** : MLP graine 0 réappris avec le même code, résultat différent (MAE 17,57 contre 17,51) à cause de la machine (threads). Écart plus petit que l'écart entre graines (0,29) ; le modèle servi reste celui déclaré (D-23).
- **Plafond du HGB** : sans contexte, il touchait 500 arbres ; avec 2 000 il s'arrête seul à 679. Avec contexte, rien ne change (342 arbres, prévisions identiques).
- **Code de score d'E4** (`Metric.py`) relu : même masque, intersection commune et MAE macro déjà présents ; il ne sait pas noter les modèles bruts (repli compté comme valide).
- **Vrais cas de validation**, cibles non lues : le HGB prévoit le site troué `100047545`, le MLP s'y replie.

### Résultats (contrôle sur juin, pas des scores)

- MLP : 17,51 / 17,60 / 17,86 selon la graine ; sans contexte 19,22.
- HGB : 17,86 ; sans contexte 18,76.
- Le contexte semble aider les deux, à vérifier sur la validation (EXP-E2-04).

### Analyse et décisions

- **Un seul facteur par fiche** : la méthode (03), le contexte (04), le masquage (05, à écrire).
- **Réglages par défaut**, sans validation croisée ni recherche ; un réglage éventuel se ferait par validation croisée temporelle avant le 01/07.
- **Pour E3**, simulation sur sites `S_train` : sans le seuil de 84 h, le MLP tient à 72 h mais se trompe à 24 h (biais +42). L'adaptation reste le travail d'E3 ; nous fournissons les modèles et leurs conditions.
- **Erreur corrigée** : j'avais écrit que les modèles étaient exclus de Git ; la ligne du `.gitignore` est commentée, ils sont commités.

### Pistes gardées pour plus tard

- **Ma comparaison** : [EXP-E2-05](../experiments/EXP-E2-05.md), figée puis codée (MOD-015, MOD-016).
  - `min_observed_hours` et `mask_windows` dans `build_windows` / `neural.py`, masquage dans `fit_mlp` (Esther prévenue).
  - Avec le seuil de 84 h, un bloc de plus de 84 h ne peut pas s'appliquer : B apprend donc avec un seuil de 24 h.
  - Contrôle sur juin : à 0,25, B perd (18,07 contre 17,68) ; à 0,10, il gagne (17,32), probablement par régularisation. B retenu à 0,10. Le bras A′ isole le masquage du changement de seuil. Scores après le gel d'EXP-E2-03.
- Ablation par groupe de contexte pour le MLP (aujourd'hui tout ou rien).

### Partenaires

- E5 (Sandra) : contrôles d'éligibilité repris dans notre `predict.py` ; règle de propriété des dossiers (D-25) ; l'appli doit passer le contexte pour proposer `mlp` / `hgb`.
- E3 : sur `Team3`, `load_model` sans import de `neural` et `manager` non importé ; corrigés sur `dev`, `Team3` à mettre à jour.
- E4 : `Metric.py` (version de référence ? biais global ? version « brute » des prévisions), date de début d'apprentissage dans `project.yaml`.
- Esther et Ania : 5 points à trancher pour EXP-E2-03, plafond `max_iter=2000` à confirmer.

### Soirée : calcul en bloc et premiers résultats

- **Calcul en bloc** ([batch.py](../../src/models/known/batch.py), MOD-017) : les 6 014 cas en 2 à 3 min au lieu d'environ 45, avec des fichiers identiques au cas par cas (tests et 205 vrais cas).
- **Erreur de ma part** : mon premier essai a saturé la mémoire du PC (7 Go), parce que l'historique était recopié pour chaque cas, puis retenu par une vue `iloc[0:0]`. Corrigé, et depuis chaque calcul tourne sous une limite de 3 Go.
- **EXP-E2-03 figée par l'équipe** (D-26), puis les 6 fichiers de prévision, conformes au contrôle d'E4.
- **Score provisoire** (code d'E4) : HGB 22,25, MLP 22,23, `reference_profile` 27,01. Les deux modèles font environ 17 % de mieux que la meilleure référence, sur plus de 90 % des compteurs ; l'écart entre MLP et HGB est plus petit que l'écart entre graines, donc **le HGB est retenu**.

### Prochaine étape

- Livrer les prévisions à E4 et obtenir le score officiel.
- Prévisions d'EXP-E2-04 (sans contexte) et d'EXP-E2-05 (pannes simulées), en bloc.

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

# Journal individuel - Esther (équipe 2, sites connus)

Format : [doc/SUIVI_ET_REMISE.md §4](../../doc/SUIVI_ET_REMISE.md). Entrées les plus récentes en haut. Synthèse d'équipe dans [E2_SUIVI.md](../teams/E2_SUIVI.md) ; mode d'emploi du MLP dans [E2_PRISE_EN_MAIN.md](../teams/E2_PRISE_EN_MAIN.md).

---

## 2026-11-23 - Apprentissage et prévision du MLP (expérience de deep learning)

- **Date et journée** : 2026-11-23.
- **Question / objectif personnel** : rendre entraînable et utilisable le MLP préparé par Idir (MOD-007), avec les mêmes garanties que les références : aucune information future, vide ≠ 0, traçabilité complète. Il porte la question de l'expérience de deep learning de l'équipe : **un réseau compact vaut-il son coût face au HGB et aux références ?** La comparaison viendra après la validation du protocole.
- **Travail réalisé et outils utilisés** (VS Code, Claude Code, Python 3.11, PyTorch 2.15 CPU, pandas, numpy, pytest, ruff) :
  - Prise de connaissance du sujet, des contrats, du protocole et du travail de l'équipe (MOD-001 à MOD-007). Environnement installé (`./run.sh setup --group dl`) ; données `hist-20261117` récupérées et vérifiées (SHA-256 conformes au manifeste).
  - [neural.py](../../src/models/known/neural.py) :
    - `fit_mlp` : apprentissage, contrôles des origines, perte L1 masquée pondérée par le niveau, arrêt anticipé, graine locale, bilan d'apprentissage ;
    - `predict_mlp` : 24 valeurs ou refus motivé ; `predict_windows` et `refusal_reasons` pour le calcul en bloc ;
    - `mlp_hyperparameters` ;
    - commande `python -m src.models.known.neural` ;
    - signalement du contexte manquant dans `build_windows` ;
    - latence et bilan dans `weights.pt` (format 2).
  - [train.py](../../src/models/known/train.py) : `fit` refuse une latence différente de la configuration.
  - Tests : [tests/test_known_neural_fit.py](../../tests/test_known_neural_fit.py) (44 tests). Le test d'Idir qui vérifiait que le MLP ne savait « pas encore » apprendre a été mis à jour.
  - Essai technique [E2-TECH-003](../experiments/E2-TECH-003.md) ; entrée MOD-008 et décisions D-19 à D-22 dans le suivi ; prise en main mise à jour.
- **Comparaison ou contrôle effectué** :
  - Point de référence avant de modifier quoi que ce soit : 222 tests passés. Après : 266, sans en retirer aucun.
  - **Fuite** : je modifie tout ce qui est publié après `fit_cutoff`, et les poids appris restent identiques au bit près. **Témoin positif** : retirer une seule cible publiée change les poids, ce qui montre que le test sait voir un effet.
  - Mon premier témoin a échoué : gonfler une cible de 175 à 5 000 vélos/h ne changeait pas les poids. Avec la perte L1, le gradient ne dépend que du **signe** de l'erreur, et le réseau prévoyait déjà moins que 175. Je l'ai transformé en test dédié (`test_perte_l1_masquee_ponderee_et_robuste`).
  - Sans effet sur les poids : cibles non mesurées, fenêtres trop vides, compteurs des sites réservés à E3.
  - Même graine, mêmes poids. La prévision cas par cas égale le calcul en bloc. L'époque rendue est la meilleure. L'aller-retour de sauvegarde donne les mêmes prévisions.
  - Sur données réelles :
    - l'époque retenue est bien le minimum de la perte d'arrêt anticipé (historique relu) ;
    - modèle rechargé avec contrôle du SHA-256 ;
    - 40 cas de validation passés par le chemin réel (`build_inputs`, `predict_mlp`) : mêmes valeurs qu'en bloc, à 0,0003 vélo/h près.
- **Données, protocole et versions** : `hist-20261117` ; protocole non validé ; `fit_cutoff` au 01/07/2026 et début des données (D-17) ; latence 24 h ; entrées mesurées seulement (D-11) ; branche `Team2-Esther`, non commitée (base `efb7274`).
- **Résultat obtenu, avec lien vers la preuve** :
  - 266 tests passés ; `ruff check` et `ruff format --check` sans problème.
  - Premier apprentissage réel ([E2-TECH-003](../experiments/E2-TECH-003.md)) :
    - 90 736 exemples (85 958 pour apprendre, 2 560 pour l'arrêt anticipé) ;
    - 28 époques, la meilleure étant la 20e ;
    - 33 s et 1,25 Go sur CPU, ni GPU ni Snowflake ;
    - modèle `e2-mlp-ctx-20260701-s0-9ce9` dans `artifacts/models/`.
  - Contrôle sur juin (arrêt anticipé) : MAE de 17,5 vélos/h pour le MLP contre 24,5 pour « même heure, semaine précédente », sur les mêmes cellules.
  - Couverture de la validation, sans score : 94,7 % des 6 014 cas servis par le MLP ; les 320 autres (fenêtre trop vide) se concentrent sur 4 sites en panne pendant l'été.
- **Analyse critique et décision** :
  - **Pondération par le niveau (D-19)** : la métrique du projet est une erreur en vélos/h. Sans pondération, une erreur relative de 10 % sur un compteur à 5 vélos/h compterait autant que sur un compteur à 300. Pondérer revient à minimiser l'erreur absolue, comme la pondération par l'échelle de DeepAR. L'option sans pondération est gardée pour une comparaison de fonctions de perte.
  - **Cibles extrêmes (D-19)** : je ne les plafonne pas. 0,74 % des exemples dépassent 10 fois le niveau de leur fenêtre, jusqu'à 471 fois (fenêtres effondrées par des zéros). La L1 borne déjà leur influence : mon témoin raté en est la preuve concrète.
  - **Le contrôle sur juin n'est pas une comparaison**, pour trois raisons :
    - juin a servi à choisir l'époque, donc il est optimiste pour le MLP ;
    - la référence y est sans repli ;
    - c'est un seul mois, en été.

    Il montre seulement que l'apprentissage fonctionne. La comparaison officielle se fera sur la validation, scorée par E4.
  - **Pièges trouvés en relisant le code existant**, et traités :
    - `build_windows` lit les cibles sans regarder `fit_cutoff` ;
    - la latence passée à `train.fit` n'est pas transmise aux méthodes ;
    - un contexte manquant devenait 0, soit « 0 °C » pour le réseau ;
    - une origine hors minuit décalerait les 24 sorties sans aucune erreur visible.
  - **Surapprentissage** : la perte d'apprentissage baisse jusqu'au bout, celle de juin stagne dès l'époque 13. L'arrêt anticipé est donc nécessaire. Comme elle varie d'environ ±0,005 d'une époque à l'autre, il faudra mesurer la variabilité entre graines avant toute conclusion.
  - **Décision D-20** : pas de réapprentissage sur les 4 semaines d'arrêt anticipé, par simplicité. Ce sont pourtant les données les plus récentes : à rediscuter avec l'équipe.
  - **Coût** : 0,39 s par cas par le chemin individuel contre 3,2 s pour 6 014 cas en bloc. Le chemin individuel suffit pour l'application ; les expériences doivent passer par le calcul en bloc.
- **Partenaire / retour reçu / usage vérifié** : aucun retour pour l'instant. À présenter :
  - à Idir : socle modifié (contrôle de latence, format 2, test mis à jour) ;
  - à Ania : même règle de latence pour le HGB ;
  - à E3 : réseau réutilisable, sites E3 exclus ;
  - à E4 et E5 : codes de refus `mlp_*`, couverture, sites en panne.
- **Prochaine étape** :
  - Présenter MOD-008 à l'équipe et consigner les retours au §8 du suivi.
  - Brancher la variante MLP dans `predict.py` selon la recette de la prise en main, si l'équipe me la confie (Idir l'avait prévue), puis l'annoncer à E5.
  - Mesurer la variabilité entre graines ; rédiger avec l'équipe la fiche EXP-E2-03, figée avant les scores ; préparer l'ablation avec et sans contexte une fois le protocole validé.
  - Étudier les 4 sites en panne pendant la validation comme cas difficile.

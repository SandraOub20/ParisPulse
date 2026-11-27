# Journal individuel — Carl (équipe 3, nouveaux sites)

Auteur : Carl (`carlaboudiwan`)  
Dernière mise à jour : 27/11/2026

## 27/11/2026 — Adaptation locale de TimesFM 2.5

- **Question / objectif personnel :** rendre Google TimesFM 2.5 utilisable en variante `adapted-v2` sur les nouveaux sites et produire ses prévisions de validation aux budgets locaux de 24 h, 72 h et 168 h.
- **Travail réalisé et outils utilisés :**
  - Ajout dans [`adapt.py`](../../src/models/new/adapt.py) d'un adaptateur TimesFM qui conserve le modèle pré-entraîné gelé et mélange ses prévisions avec le profil horaire local.
  - Ajout dans [`fit_timesfm_blend_weights.py`](../../src/models/new/fit_timesfm_blend_weights.py) du choix des poids par budget sur une grille de 0 à 1 par pas de 0,05.
  - Intégration de la variante dans [`predict.py`](../../src/models/new/predict.py) et création du lanceur [`validation.example.google.adapted.py`](../../src/models/new/validation.example.google.adapted.py).
  - Ajout d'un test synthétique de la variante adaptée dans [`test_new_predict.py`](../../tests/test_new_predict.py).
- **Méthode et contrôles :** le profil correspond à la médiane des observations autorisées du même créneau horaire de Paris. La prévision est le mélange `max(0, poids × TimesFM + (1 − poids) × profil)`. Le calcul utilise le support local causal de chaque cas ; les poids du modèle TimesFM ne sont pas réentraînés.
- **Données, protocole et versions :** commit [`ef0a6c3`](https://github.com/SandraOub20/ParisPulse/commit/ef0a6c3706e28cd310fa46a9c0b6a8e62178b478), snapshot `hist-20261117`, protocole `proto-v1`, nouveaux sites `S_dev_new`, split `validation`. Les poids sauvegardés dans [`blend_weights.json`](../../artifacts/models/e3-timesfm2.5-adapted-v2/blend_weights.json) sont **0,50**, **0,95** et **0,90** pour 24 h, 72 h et 168 h. Ils ont été sélectionnés à partir de cinq compteurs de validation.
- **Résultat obtenu :** génération de 930 exécutions et 22 320 lignes de prévision, disponibles dans les fichiers [prédictions](../../data/prediction_results/EXP-E3/e3-google-TimesFM_2.5-adapted-v2-validation-b24-b72-b168.pred.csv) et [runs](../../data/prediction_results/EXP-E3/e3-google-TimesFM_2.5-adapted-v2-validation-b24-b72-b168.runs.csv).
- **Évaluation E4 consultée :** sur les scores agrégés de [`scores.csv`](../../data/evaluation/proto-v1/EXP-E3/scores.csv), les MAE adapted-v2 sont de 27,68, 22,61 et 19,90 pour les budgets 24 h, 72 h et 168 h, contre 27,98, 22,55 et 19,79 en frozen. L'adaptation réduit donc légèrement la MAE à 24 h, mais ne l'améliore pas aux deux autres budgets.
- **Analyse critique et décision :** ces résultats ne montrent pas de gain global de l'adaptation par rapport à TimesFM frozen. De plus, les poids finaux ont été choisis à partir des cas `S_dev_new` de validation, puis évalués sur ce même split : ces scores ne constituent donc pas une mesure indépendante de généralisation. Le script calcule aussi un diagnostic leave-one-site-out, mais le poids finalement sauvegardé est ajusté sur l'ensemble des lignes disponibles pour chaque budget. Il faudrait choisir les poids sur un jeu de développement distinct et réserver le test final.
- **Tests et limites de vérification :** le commit ajoute un test de comportement adapté avec un faux modèle TimesFM. Je n'ai pas pu l'exécuter dans l'environnement courant : `py -m pytest` échoue car le module `pytest` n'est pas installé. Les prédictions sont produites avec le chemin TimesFM du projet ; les tests synthétiques ne remplacent pas une validation complète avec les poids réels.
- **Partenaire / usage vérifié :** les fichiers de prévisions suivent le contrat E3/E4 et ont été évalués par E4 ; aucun retour direct d'E5 n'est consigné dans ce commit.
- **Prochaine étape :** exécuter les tests ciblés dans l'environnement du projet, confirmer la reproductibilité du calcul des poids, puis comparer les variantes sur un split indépendant avant recommandation à E5.
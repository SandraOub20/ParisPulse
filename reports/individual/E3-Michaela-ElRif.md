# Journal individuel - Michaela El Rif
Auteur : Michaela El Rif
Date dernière mise à jour : 27/11/2026

## 10/11/2026 

- **Objectif :** Comprendre l'architecture générale du projet, le rôle de chaque équipe et choisir celle sur laquelle travailler.

- **Travail réalisé et outils utilisés :** Organisation d'une réunion avec mon équipe pour répartir les rôles entre les membres, définir les tâches de chacun et planifier le travail des trois sessions suivantes.

- **Points discutés :** Discussion sur les objectifs des différentes équipes, leurs missions, les méthodes envisagées ainsi que l'organisation et la répartition des responsabilités.

- **Fichiers et résultats :** Préparation d'un document de cadrage définissant les objectifs, les approches envisagées, les expérimentations et l'organisation du travail de l'équipe 3.

- **Analyse et décision :** Choix de l'équipe 3, chargée de la prévision de la fréquentation cyclable sur de nouveaux sites disposant de peu d'historique.

- **Prochaine étape :** Commencer les tâches attribuées à chaque membre et suivre le planning défini pour les trois sessions suivantes.


## 17/11/2026

- **Objectif :** Comprendre les données disponibles et identifier des modèles de prévision adaptés aux nouveaux sites disposant de peu d'historique.

- **Travail réalisé et outils utilisés :** Participation aux discussions avec les équipes 1 et 2 concernant la préparation des données et les modèles de prévision. Contribution à la réflexion sur le choix des modèles. Recherche personnelle sur TimesFM 2.5 de Google, un modèle pré-entraîné de prévision de séries temporelles, en complément de Chronos-2 proposé avec `Massinissa`.

- **Points discutés :** Analyse du snapshot `hist-20261117` fourni par l'équipe 1, notamment la grille horaire, les doublons, les valeurs manquantes, les zéros mesurés et les valeurs imputées. Discussion sur les données `site_new_dev` et `site_new_test`, leur signification et la manière de récupérer les sites réservés à l'équipe 3 à partir des données préparées, ainsi que sur la possibilité de réutiliser le modèle de l'équipe 2.

- **Fichiers et résultats :**  Identification de Chronos-2 (Amazon) et TimesFM 2.5 (Google) comme modèles pré-entraînés à explorer pour notre problématique.

- **Analyse et décision :** Commencer par tester des modèles publics pré-entraînés sur les nouveaux sites de développement, tout en gardant les sites de test réservés à l'évaluation finale, afin d'éviter les fuites de données. Comparer leurs performances en version gelée, puis envisager une adaptation à partir de l'historique local disponible.

- **Prochaine étape :** Étudier et tester Chronos-2 et TimesFM 2.5 sur les cas de validation fournis par l'équipe 4, en commençant par une prévision des 24 prochaines heures.


## 24/11/2026

- **Objectif :** Tester Chronos-2 en version gelée sur les cas de validation E3 fournis par l'équipe 4.

- **Travail réalisé et outils utilisés :**

  1. Création du lanceur [`validation.example.oneCase.Chronos.py`](../../src/models/new/validation.example.oneCase.Chronos.py), sélectionnant un premier cas de validation `S_dev_new` avec un budget d'un jour (24 h d'historique local) et exécutant Chronos-2 gelé pour prédire les 24 heures suivantes.
  2. Exécution de Chronos-2 sur ce premier cas et enregistrement des prévisions et des informations d'exécution dans les fichiers de résultats correspondants.

- **Contrôles effectués :** Vérification du lancement de la chaîne de prédiction sur un premier cas de validation.

- **Fichiers et résultats :** Création du lanceur [`validation.example.oneCase.Chronos.py`](../../src/models/new/validation.example.oneCase.Chronos.py) et génération des premières prévisions de Chronos-2 gelé sur un cas de validation.

- **Analyse et décision :** Le premier cas permet de vérifier le fonctionnement de la chaîne de prédiction, sans encore permettre de conclure sur les performances globales de Chronos-2.

- **Prochaine étape :** Échanger avec l’équipe 4 sur l’évaluation des résultats obtenus et discuter avec Lynda des possibilités d’adaptation de Chronos-2.

## 25/11/2026

- **Objectif :** Explorer et implémenter une adaptation locale de Chronos-2 à partir de l'historique autorisé, puis comparer ses performances à celles de la version gelée.

- **Travail réalisé et outils utilisés :**

  1. Discussion avec Lynda autour d'une approche d'adaptation par reinforcement learning. Cette piste s'est révélée trop coûteuse en temps et en ressources dans le cadre du projet, ce qui a conduit à privilégier une méthode plus légère, conservant Chronos-2 gelé et corrigeant localement ses prévisions à partir des erreurs passées du compteur.
  2. Implémentation de [`adapt.py`](../../src/models/new/adapt.py), ajoutant un calibrateur local propre au compteur. Celui-ci apprend une correction affine à partir des erreurs passées (`max(0, a × prévision_Chronos + b)`), pour les budgets de 24 h, 72 h et 168 h (1, 3 et 7 jours d'historique local). La correction n'est retenue que si elle améliore simultanément la MAE et la RMSE par rapport aux prévisions Chronos-2 non corrigées. L'adaptation utilise uniquement l'historique autorisé, sans jamais exploiter les 24 h à prévoir.
  3. Modification de [`predict.py`](../../src/models/new/predict.py), limitée au nécessaire pour intégrer la variante `adapted`.
  4. Génération des prévisions adaptées avec le lanceur [`validation.example.chronos.adapted.py`](../../src/models/new/validation.example.chronos.adapted.py) pour les budgets de 1, 3 et 7 jours.
  5. Comparaison des prévisions adaptées avec Chronos-2 gelé sur les mêmes cas de validation.

- **Points discutés :** Analyse des résultats de l'adaptation et discussion avec Lynda sur les possibilités d'amélioration de la méthode.

- **Fichiers et résultats :** [`adapt.py`](../../src/models/new/adapt.py), [`predict.py`](../../src/models/new/predict.py), [`validation.example.chronos.adapted.py`](../../src/models/new/validation.example.chronos.adapted.py), ainsi que les fichiers de prévisions et d'évaluation générés dans [`data/prediction_results/EXP-E3/e3-chronos-2-adapted-v1-validation-b24-b72-b168.runs.csv`](../../data/prediction_results/EXP-E3/e3-chronos-2-adapted-v1-validation-b24-b72-b168.runs.csv).

- **Analyse et décision :** Sur la validation, l'adaptation n'améliore pas la MAE par rapport à Chronos-2 gelé : MAE macro de 26,21 contre 26,09 pour le budget de 24 h (1 jour), et de 23,23 contre 22,83 pour le budget de 72 h (3 jours). Chronos-2 gelé reste donc préférable si la MAE est le critère prioritaire. Les légères améliorations de RMSE ne compensent pas la hausse de MAE. Il reste à chercher une meilleure méthode d'adaptation.

- **Prochaine étape :** Revoir avec Lynda les résultats et explorer d'autres pistes pour améliorer l'adaptation locale de Chronos-2.

## Activités transversales

- Échanges avec Lynda sur les approches possibles pour adapter Chronos-2, puis choix d'un calibrateur local plus léger que le reinforcement learning envisagé initialement.
- Coordination avec les équipes 1, 2 et 4 autour des données des nouveaux sites, des modèles à évaluer et des cas de validation E3.
- Utilisation de Git et des pull requests pour suivre et intégrer les changements, du lanceur de première prévision jusqu'à l'adaptation de Chronos-2 et à son évaluation.
- Attention portée à la causalité des prévisions : utiliser seulement l'historique local autorisé, éviter toute fuite des observations futures et comparer les variantes sur les mêmes cas évaluables.

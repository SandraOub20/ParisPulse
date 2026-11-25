# Journal individuel - Lynda Khazem
Auteur : Lynda Khazem
Date dernière mise à jour : 25/11/2026

## 17/11/2026

- **Objectif :** comprendre les données disponibles et choisir un premier modèle de prévision pour les nouveaux sites.
- **Travail réalisé et outils utilisés :** réunion avec les équipes 1 et 2 pour discuter des choix de préparation des données, des champs utiles et des modèles de prévision. Avec Massinissa, Chronos-2 a été retenu comme candidat pour un premier prototype pré-entraîné (`frozen`).
- **Points discutés :** le snapshot `hist-20261117`, la grille horaire, les doublons ainsi que le traitement des valeurs manquantes, des zéros mesurés et des valeurs imputées.
- **Fichiers et résultats :** snapshot `hist-20261117` évoqué en réunion ; Chronos-2 retenu comme candidat à explorer.
- **Analyse et décision :** démarrer par une prévision ponctuelle des 24 prochaines heures avec Chronos-2.
- **Prochaine étape :** mettre en place la validation sur les cas fournis par l’équipe 4.

## 24/11/2026

- **Objectif :** exécuter Chronos-2 sur les cas de validation E3 fournis par l’équipe 4.
- **Travail réalisé et outils utilisés :** développement de la chaîne de prédiction dans [`predict.py`](../../src/models/new/predict.py) et préparation des lanceurs [`validation.example.chronos.py`](../../src/models/new/validation.example.chronos.py). La chaîne filtre l’historique selon les informations disponibles à l’origine de chaque cas. Pour préparer le passage en production, proposition de consigner le budget d’historique de chaque site dans un fichier, que l’équipe 5 pourrait utiliser pour limiter les données fournies au modèle, comme le fichier `cases` le fait en développement.
- **Contrôles effectués :** exécution sur des historiques locaux de 24, 72 ou 168 heures. Chaque cas produit une prévision de 24 heures.
- **Fichiers et résultats :** 22 320 prévisions pour 930 cas. Les résultats de prédiction ont été transmis à E4 pour évaluation.
- **Analyse et décision :** le rapport d’évaluation d’E4 désigne Chronos-2 comme le meilleur modèle évalué sur 24h et 72h. Les durées de 24, 72 et 168 heures correspondent à l’historique d’entrée, et non à l’horizon de prévision.
- **Prochaine étape :** Travailler avec Michaela sur une adaptation de Chronos-2.

## Activités transversales

- Coordination et communication régulières avec les équipes, pour organiser le travail et clarifier la répartition des tâches.
- Utilisation de Git pour coordonner les contributions, avec apprentissage et mise en pratique de la résolution des conflits.
- Contribution aux échanges sur la préparation des données des nouveaux sites et les besoins des différentes équipes.
- Proposition de solutions pour répondre aux besoins du projet et faciliter la continuité entre le développement et la production.

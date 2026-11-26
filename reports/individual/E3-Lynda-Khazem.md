# Journal individuel - Lynda Khazem
Auteur : Lynda Khazem

Date de dernière mise à jour : 26/11/2026

## 17/11/2026

- **Objectif :** comprendre les données disponibles et choisir un premier modèle de prévision pour les nouveaux sites.
- **Travail réalisé et outils utilisés :** réunion avec les équipes 1 et 2 pour discuter de la préparation des données, des champs utiles et des modèles de prévision. Avec Massinissa, Chronos-2 a été retenu comme candidat pour un premier prototype pré-entraîné (`frozen`).
- **Points discutés :** le snapshot `hist-20261117`, la grille horaire, les doublons ainsi que le traitement des valeurs manquantes, des zéros mesurés et des valeurs imputées.
- **Fichiers et résultats :** snapshot `hist-20261117` évoqué en réunion ; Chronos-2 retenu comme candidat à explorer.
- **Analyse et décision :** démarrer par une prévision ponctuelle des 24 prochaines heures avec Chronos-2.
- **Prochaine étape :** mettre en place la validation sur les cas fournis par l’équipe 4.

## 24/11/2026

- **Objectif :** exécuter Chronos-2 sur les cas de validation E3 fournis par l’équipe 4.
- **Travail réalisé et outils utilisés :** développement de la chaîne de prédiction dans [`predict.py`](../../src/models/new/predict.py) et préparation du lanceur [`validation.example.chronos.py`](../../src/models/new/validation.example.chronos.py). La chaîne filtre l’historique selon les informations disponibles à l’origine de chaque cas. Pour préparer le passage en production, proposition de consigner le budget d’historique de chaque site dans un fichier que l’équipe 5 pourrait utiliser pour limiter les données fournies au modèle, comme le fait le fichier `cases` en développement.
- **Contrôles effectués :** exécution avec des historiques locaux de 24, 72 ou 168 heures. Chaque cas produit une prévision de 24 heures.
- **Fichiers et résultats :** 930 cas, soit 22 320 horizons de prévision, transmis à l’équipe 4 pour évaluation.
- **Analyse et décision :** le rapport d’évaluation d’E4 désigne Chronos-2 comme le meilleur modèle évalué à 24 h et à 72 h. Les durées de 24, 72 et 168 heures correspondent à l’historique d’entrée, et non à l’horizon de prévision.
- **Prochaine étape :** travailler avec Michaela sur une adaptation de Chronos-2.

## 26/11/2026

- **Recherche :** revue des principales approches d’adaptation : apprentissage par transfert (fine-tuning), adaptateurs de type LoRA et adaptations statistiques locales.
- **Travail réalisé :** implémentation de `adapted-v2`, qui mélange la prévision médiane de Chronos-2 frozen avec le profil médian par heure locale de Paris, calculé à partir du support causal du cas. Les anciennes prédictions de Chronos-adapted-v1 ont été conservées et les sorties v2 ont des identifiants distincts.
- **Choix des poids :** les poids du mélange (0,80 pour 24 h, 0,80 pour 72 h et 0,85 pour 168 h) ont été choisis à partir d'un échantillon des cas de validation `S_dev_new`. Chronos-2 n’a pas été réentraîné sur ces données.
- **Comparaison E4 :** comparaison de Chronos frozen, adapted-v1 (correction par résidus) et adapted-v2 à l’aide des fonctions d’évaluation de l’équipe 4. Sur les scores agrégés de validation, adapted-v2 obtient les MAE et RMSE les plus faibles aux trois budgets. Les poids sont conservés dans [`blend_weights.json`](../../artifacts/models/e3-chronos2-adapted-v2/blend_weights.json). Les détails sont consignés dans le rapport [adapted-v2](../experiments/E3-chronos-adapted-v2.md).
- **Décision et suite :** Chronos-adapted-v2 a les meilleurs résultats.

## Activités transversales

- Coordination et communication régulières avec les équipes pour organiser le travail et clarifier la répartition des tâches.
- Utilisation de Git pour coordonner les contributions et pratiquer la résolution des conflits.
- Contribution aux échanges sur la préparation des données des nouveaux sites et les besoins des différentes équipes.
- Proposition de solutions pour répondre aux besoins du projet et faciliter la continuité entre le développement et la production.

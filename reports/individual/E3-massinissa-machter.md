
# Journal individuel - Massinissa Machter
Auteur : Massinissa MACHTER
Date dernière mise à jour : 24/11/2026

## 17/11/2026

- Date et journée : 17/11/2025 
- Question ou objectif personnel : Identifier des modèles publics pré-entraînés qui pourraient aider à prévoir le trafic sur de nouveaux sites.
- Travail réalisé et outils utilisés : Recherche documentaire sur l’état de l’art des modèles disponibles sur des plateformes comme Hugging Face, leurs usages et leur potentiel pour la prévision sur des sites non vus. Chronos-2 a notamment été repéré comme candidat.
- Expérience ou contrôle effectué : Comparaison exploratoire des modèles et de leur adéquation au problème. Aucun résultat expérimental n’est consigné pour cette journée.
- Versions et liens vers les fichiers/résultats : [Bibliographie du projet](../../doc/BIBLIOGRAPHIE.md) ; 
- Résultat et analyse critique : Cette recherche a permis d’identifier des pistes de modèles publics à évaluer. Leur disponibilité ne garantit toutefois pas leur adéquation aux données du projet ni l’absence de contamination par celles-ci.
- Décision ou adaptation : Retenir Chronos-2 comme exemple de modèle à étudier pour la prévision sur les nouveaux sites.
- Partenaire, retour reçu et usage vérifié : Recherche individuelle de model (chronos-2) ; j'ai parler avec `lynda & mechaela ` qui vont s'occuper de son implementation (prediction & adaptation).
- Prochaine étape : Integrer le model de team 2 (MLP-team2) dans notre pipeline de predictions pour les site new . 

## 24/11/2026

- Date et journée : 24/11/2026 — mardi
- Question ou objectif personnel : Brancher le MLP de l’équipe 2 en variante `frozen` et préparer son évaluation (new_site ; sur la validation) sur les nouveaux sites avec un historique local de 7 jours.
- Travail réalisé et outils utilisés : Intégration de `neural.predict_mlp` dans la prévision E3, préparation des entrées causales et prise en compte du contexte disponible à l’origine. Préparation d’un script de validation qui sélectionne les cas `new_site` concernés, de validation `S_dev_new`, avec `local_budget_hours = 168`, à partir du fichier de cas (proto-v1/cases.csv) fourni par l’équipe 4.
- Expérience ou contrôle effectué : Le script permet de générer les prévisions du MLP et d’utiliser la référence hebdomadaire lorsque le MLP refuse un cas. La vérification des résultats et leur analyse restent à consigner après exécution.
- Versions et liens vers les fichiers/résultats : [Prédiction E3](../../src/models/new/predict.py) ; [script de validation Team2](../../src/models/new/validation.example.modelTeam2.py) ; [cas proto-v1](/data/evaluation/proto-v1/cases.csv) ; [README E3](../../src/models/new/README.md). Sorties prévues dans `data/prediction_results/EXP-E3/`.
- Résultat et analyse critique : Le chemin de prédiction `frozen` et la sélection des cas à budget 168 h sont préparés. Les performances ne sont pas conclues ici : elles doivent être examinées à partir des fichiers de résultats après validation.
- Décision ou adaptation : Pour l'instant , utiliser le modèle MLP Team2 gelé, sans adaptation aux nouveaux sites, et conserver un repli explicite lorsque le modèle refuse une prévision.
- Partenaire, retour reçu et usage vérifié : Échanges avec l’équipe 2 sur le transfert et la réutilisation de leur modèle pour les nouveaux sites. Parler avec l'équipe 4 pour qu'il evaluent les resultats de mes experiences (data/predictions_results/e3-team3-mlp-frozen-v1-validation-b168.pred.csv) et me donner un retour (erreur MAE observé)
- Prochaine étape : en fonction d'eval de l’équipe 4, on va voir si une adaptation est necessaire.

## Tâches diverses (depuis le début de projet)

- Participation aux réunions avec les membres du projet.
- Discussions sur l’organisation du travail et la répartition des tâches avec les autres membres de l'équipe.
- Échanges sur l’architecture Git et la coordination des contributions avec les autres équipes.
- Communication avec l’équipe 2 sur les modalités de transfert et d’utilisation de leur modèle pour les nouveaux sites.



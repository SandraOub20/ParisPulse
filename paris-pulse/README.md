# ParisPulse

Comprendre et prévoir la fréquentation cyclable à l'échelle d'un réseau.

Plan mis à jour le **10 novembre 2026**, après lecture intégrale de [ParisPulse - Sujet étudiants](ParisPulse_Sujet_etudiants.docx). Ce document détaillé devient la référence de travail et précise le [premier sujet PDF](<Projet 1 - Construire un observatoire prédictif des déplacements à vélo.pdf>).

## Documents pour démarrer

| Document | Contenu |
| --- | --- |
| [Plan du projet](PLAN_PROJET.md) | Exigences, priorités, cinq équipes, trois journées, architecture, backlog et risques |
| [Contrats v2](docs/CONTRATS.md) | Formats communs, contexte, cas de prévision, adaptation, couverture, exports et interfaces |
| [Protocole proposé](docs/PROTOCOLE_EVALUATION.md) | Sites connus/nouveaux, disponibilité de l'information, comparaisons, MAE et tests réservés |
| [Suivi et remise](docs/SUIVI_ET_REMISE.md) | Livrables, barème, journal individuel et preuves d'intégration |
| [Bibliographie initiale](docs/BIBLIOGRAPHIE.md) | Sources de données, lectures méthodologiques et pistes de modèles à examiner |

## Exigences qui structurent la réalisation

- **15 à 20 étudiants**, répartis en **cinq équipes de 3 à 4** ; trois journées complètes et une demi-journée d'évaluation.
- Une première prévision et son score affichés sur une **série réelle avant la fin de la première matinée**, si les accès fonctionnent.
- Deux situations accessibles dans l'application : **sites connus** et **nouveaux sites avec peu de mesures**, avec comparaison avant/après adaptation.
- Une **source complémentaire intégrée**, au moins une **expérience de deep learning**, une étude du réseau puis une extension mesurée.
- Comparaison par MAE moyenne entre compteurs, couverture des cas complets de 24 heures et coût de calcul.
- Export de l'étude, installation depuis une copie neuve et recalcul de la référence sur un autre cas admissible.
- Rapport et présentation par équipe, démonstration collective et journal individuel daté.

Le sujet demande de **faire valider le protocole par le professeur avant les comparaisons servant à retenir les modèles**. Le protocole fourni ici est prêt à discuter ; sa validation n'est pas acquise.

## Première action

Un représentant par équipe fixe les échanges pendant que les autres commencent : E1 extrait une série, E2 code une référence, E3 prépare les sites réservés et une méthode transférable, E4 vérifie un score à la main, E5 raccorde l'écran. Le premier cas technique ne remplace pas l'inventaire qui justifiera l'échantillon scientifique.

**État : planification uniquement.** Les formats, modules et commandes décrits sont à implémenter. Les métadonnées publiques et l'accès au calendrier ont été vérifiés ; l'audit complet, les expériences et l'application restent à réaliser.

# ParisPulse

Comprendre et prévoir la fréquentation cyclable à l'échelle d'un réseau.

Structure de travail fondée sur le [sujet étudiants](ParisPulse_Sujet_etudiants.pdf) et les plans du **10 novembre 2026**. Les fichiers Python contiennent des consignes à compléter par les équipes ; l'application et les algorithmes restent à développer.

## Architecture et démarrage du travail

Lire l'[architecture](doc/ARCHITECTURE.md) puis les consignes du dossier de son équipe :

| Équipe | Dossier | Première livraison |
| --- | --- | --- |
| E1 - Données et contexte | [src/data](src/data/README.md) | Un compteur réel préparé, sa localisation et sa provenance |
| E2 - Prévision sur sites connus | [src/models/known](src/models/known/README.md) | Une référence de 24 heures, son repli et un calcul réutilisable |
| E3 - Prévision sur nouveaux sites | [src/models/new](src/models/new/README.md) | Sites réservés et méthode sur un historique local limité |
| E4 - Évaluation et fiabilité | [src/eval](src/eval/README.md) | Cas attendus, protocole proposé et score vérifié à la main |
| E5 - Application | [src/app](src/app/README.md) | Parcours appelant réellement les composants des partenaires |

Les objets et paramètres communs sont à définir dans [src/common](src/common/README.md). Les échanges suivent les [gabarits](doc/templates/README.md) : vérité terrain dans `data/processed/`, prévisions dans `data/prediction_results/`, résultats d'évaluation dans `data/evaluation/`.

Un représentant de chaque équipe fixe les échanges pendant que les autres commencent leurs premiers travaux. Le `Dockerfile`, `requirements.txt` et `run.sh.example` décrivent le packaging à réaliser par E5 ; aucune commande de lancement de l'application n'est encore implémentée.

## Documents pour démarrer

| Document | Contenu |
| --- | --- |
| [Index de la documentation](doc/README.md) | Ordre de lecture et références du dépôt |
| [Architecture à compléter](doc/ARCHITECTURE.md) | Fichiers, responsabilités, flux et premières tâches |
| [Gabarits d'échange et de suivi](doc/templates/README.md) | CSV vides, provenance, fiche d'expérience et journal individuel |
| [Plan du projet](PLAN_PROJET.md) | Exigences, priorités, cinq équipes, trois journées, architecture, backlog et risques |
| [Contrats v2](doc/CONTRATS.md) | Formats communs, contexte, cas de prévision, adaptation, couverture, exports et interfaces |
| [Protocole proposé](doc/PROTOCOLE_EVALUATION.md) | Sites connus/nouveaux, disponibilité de l'information, comparaisons, MAE et tests réservés |
| [Suivi et remise](doc/SUIVI_ET_REMISE.md) | Livrables, barème, journal individuel et preuves d'intégration |
| [Bibliographie initiale](doc/BIBLIOGRAPHIE.md) | Sources de données, lectures méthodologiques et pistes de modèles à examiner |

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

**État : squelette documenté.** Les modules sont des fichiers d'instructions, les CSV sont des en-têtes vides et les configurations sont des exemples à renseigner. Les données, modèles, calculs, tests et lancement restent à réaliser. Aucun résultat scientifique n'est fourni par cette structure.

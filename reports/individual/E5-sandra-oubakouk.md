# Journal individuel - ParisPulse

**Étudiante :** Sandra Oubakouk  
**Équipe :** E5 - Application  
**Période :** du 10 au 28 novembre 2026  
**Outils :** Python, Streamlit, Pandas, Plotly, Folium, Git, GitHub, Pytest, Ruff et uv.

## 10 novembre 2026 - Organisation et coordination du projet

**Question et objectif personnel**

Comment organiser le développement de l'application alors que les données, les modèles et les résultats d'évaluation sont produits simultanément par quatre autres équipes ?

**Travail réalisé**

- Participation à la définition de l'architecture collaborative du projet.
- Organisation du dépôt GitHub et des branches de développement.
- Mise en place d'une démarche d'intégration progressive des contributions.
- Identification des dépendances entre l'application et les équipes E1, E2, E3 et E4.
- Participation à la répartition des tâches au sein de l'équipe E5.

**Analyse et décision**

Le développement ne pouvait pas dépendre de la disponibilité immédiate de tous les résultats des autres équipes. Nous avons donc choisi de travailler progressivement sur les composants de l'application, puis de les intégrer à mesure que les interfaces et les ressources devenaient disponibles.

J'ai retenu une organisation avec une branche commune `dev`, des branches dédiées aux contributions et des Pull Requests pour contrôler les intégrations.

**Transmission**

Les conventions de travail ont été partagées avec les membres du projet afin de faciliter le développement parallèle et de limiter les conflits Git.

**Prochaine étape**

Développer une première application permettant de consulter les compteurs et d'intégrer les résultats des équipes partenaires.

---

## 24 novembre 2026 - Intégration de la carte et unification de l'application

**Question et objectif personnel**

Comment permettre à l'utilisateur de sélectionner facilement un compteur, de comprendre son périmètre et d'accéder aux prévisions associées ?

**Travail réalisé**

- Développement et intégration de la carte interactive des compteurs.
- Utilisation de Folium et Streamlit pour la navigation géographique.
- Exploitation des identifiants, coordonnées et sens de circulation fournis par E1.
- Participation à l'unification des composants de l'application E5.
- Participation à la définition des formats d'échange et du routage vers les moteurs de prévision.

**Contrôles effectués**

Vérification de la cohérence entre les compteurs affichés, les informations disponibles et les paramètres transmis aux composants de prévision.

La distinction entre les différentes directions d'un même site est importante, car deux compteurs proches géographiquement peuvent correspondre à des séries temporelles différentes.

**Résultat et analyse critique**

La carte facilite la navigation, mais elle ne doit pas constituer le seul moyen de sélection. Le menu de sélection reste nécessaire, notamment pour distinguer les directions et accéder aux compteurs qui ne peuvent pas être représentés correctement sur la carte.

**Transmission et retour reçu**

Lors du point d'avancement, le professeur a notamment demandé de mieux représenter les données manquantes et de rendre visibles les situations où une prévision échoue.

Ces remarques ont orienté la suite de mon travail sur les visualisations et les diagnostics.

**Preuves**

- [PR nº 15 - Routage et visualisations](https://github.com/SandraOub20/ParisPulse/pull/15)
- [PR nº 16 - Prévisions CSV](https://github.com/SandraOub20/ParisPulse/pull/16)

---

## 27 novembre 2026 - Intégration des nouveaux sites E3

**Question et objectif personnel**

Comment permettre la prévision sur de nouveaux sites disposant d'un historique limité, tout en respectant les conditions de comparaison entre les modèles gelés et adaptés ?

**Travail réalisé**

J'ai intégré la gestion des budgets fixes d'historique local de 24, 72 et 168 heures dans l'application.

J'ai développé un mécanisme d'attribution déterministe des budgets aux compteurs E3, ainsi qu'un fichier de cas dédié à l'application, sans modifier les cas officiels d'évaluation.

J'ai également raccordé la sélection des cas et des dates à ces budgets, y compris dans les parcours utilisant les archives et les dates libres.

**Protocole et contrôles**

Les comparaisons entre Chronos-2 gelé et Chronos-2 adapté v2 sont réalisées sur un même compteur, une même date et un même budget local.

J'ai vérifié plusieurs compteurs correspondant aux trois budgets.

| Compteur | Budget | Date | MAE gelé | MAE adapté |
|---|---:|---|---:|---:|
| Voie Georges Pompidou, SO-NE | 24 h | 01/07/2026 | 57,2613 | 46,7686 |
| Voie Georges Pompidou, NE-SO | 72 h | 01/07/2026 | 13,4966 | 12,1555 |
| 27 boulevard Davout, N-S | 168 h | 01/07/2026 | 5,9802 | 6,5712 |

MAE exprimées en vélos par heure.

Les vérifications automatiques réalisées avant l'intégration ont donné 24 tests réussis.

**Résultat et analyse critique**

L'adaptation améliore les résultats sur certains cas, mais pas systématiquement. Sur le compteur du boulevard Davout, la version gelée obtient une erreur plus faible que la version adaptée.

Il n'est donc pas possible de conclure à une supériorité générale de l'adaptation à partir de ces quelques cas.

De plus, les paramètres d'adaptation ont été déterminés à partir de données de validation. Les résultats obtenus sur ces données doivent être interprétés avec prudence et ne constituent pas une confirmation indépendante des performances finales.

**Décision**

Conserver les deux méthodes dans l'application et permettre leur comparaison, sans sélectionner automatiquement le modèle adapté comme étant systématiquement meilleur.

L'attribution fixe du budget garantit également que le changement de date ou de méthode ne modifie pas arbitrairement la quantité d'historique local accordée au compteur.

**Transmission**

Le travail s'appuie sur les modèles et les interfaces fournis par E3. Les modifications ont été intégrées dans la branche commune sans modifier leur moteur de prévision.

**Preuves**

- [PR nº 52 - Intégration E3](https://github.com/SandraOub20/ParisPulse/pull/52)
- `src/app/generate_app_cases.py`
- `src/app/cases-app.csv`
- `src/app/service.py`
- `src/app/streamlit_app.py`

---

## 27-28 novembre 2026 - Visualisation des erreurs et des prévisions indisponibles

**Question et objectif personnel**

Comment représenter correctement une prévision lorsque le modèle principal échoue, utilise une méthode de secours ou ne fournit aucune valeur ?

**Travail réalisé**

À la suite des retours du professeur, j'ai amélioré les graphiques de prévision pour distinguer trois situations :

- Prévision disponible.
- Prévision obtenue par repli.
- Prévision indisponible.

J'ai également développé une visualisation des erreurs horaires permettant de comparer les prévisions aux observations réelles.

Les erreurs ne sont calculées et représentées que lorsque les données nécessaires à la comparaison sont disponibles.

**Expériences et contrôles**

Les trois premiers contrôles ont été réalisés sur le compteur 10 avenue de la Grande Armée, direction SE-NO.

| Date | Prévisions disponibles | Replis | Indisponibles | MAE |
|---|---:|---:|---:|---:|
| 31/08/2026 | 24 | 0 | 0 | 14,2 |
| 15/06/2026 | 24 | 24 | 0 | 9,1 |
| 09/01/2025 | 13 | 13 | 11 | 13,2 |

Pour le cas du 9 janvier 2025, j'ai également vérifié que les heures sans prévision ne génèrent pas artificiellement des erreurs égales à zéro.

J'ai contrôlé l'affichage des informations de statut et des raisons de refus dans les infobulles.

**Résultat et analyse critique**

Le cas incomplet montre qu'une application de prévision ne doit pas masquer les échecs du modèle.

Une valeur indisponible ne signifie pas une fréquentation nulle. De même, une prévision de secours ne doit pas être présentée comme une réussite du modèle principal.

La MAE doit être interprétée conjointement avec le nombre d'heures comparables et la couverture.

**Décision**

Utiliser des symboles et des couleurs spécifiques pour les replis et les indisponibilités. Conserver les heures manquantes sans leur attribuer de valeur fictive.

Afficher les erreurs horaires automatiquement après le calcul afin de rendre le diagnostic directement accessible à l'utilisateur.

**Transmission**

Cette amélioration répond aux remarques du professeur et permet aux équipes partenaires d'examiner les résultats de leurs méthodes depuis une interface commune.

**Preuves**

- [PR nº 58 - Diagnostics et erreurs horaires](https://github.com/SandraOub20/ParisPulse/pull/58)
- `src/app/dashboard/forecast_case.py`
- `src/app/dashboard/case_errors.py`

---

## 28 novembre 2026 - Intégration de l'évaluation officielle E4

**Question et objectif personnel**

Comment intégrer le tableau de bord des évaluations officielles sans perdre les fonctionnalités déjà développées dans la branche commune ?

**Travail réalisé**

Giovanni a développé le service de lecture des résultats officiels E4 et le tableau de bord associé.

Ma contribution a consisté à intégrer ses trois commits à partir de la version récente de `dev`, puis à vérifier leur compatibilité avec les contributions déjà fusionnées.

J'ai utilisé Git et la commande `cherry-pick` afin de récupérer précisément les commits nécessaires, sans reprendre l'intégralité d'une ancienne branche de développement.

**Contrôles effectués**

- Vérification du périmètre des fichiers modifiés.
- Vérification de l'absence de retard sur `dev`.
- Contrôle de la conservation des fichiers liés aux budgets E3 et aux visualisations.
- Exécution de 135 tests ciblés, tous réussis.
- Correction des imports et formatage des fichiers E5 avec Ruff.
- Nouvelle exécution de 169 tests et 2 sous-tests, tous réussis.
- Vérification manuelle des filtres E2, E3 et Tout le réseau.

**Analyse critique**

Il est nécessaire de distinguer l'évaluation locale d'un compteur et l'évaluation globale des modèles.

Une méthode peut obtenir une meilleure MAE sur un compteur particulier sans être globalement supérieure sur les populations officielles.

La comparaison `common_complete` permet d'étudier les méthodes sur les mêmes cas complets, tandis que `self` utilise les cas évaluables propres à chaque méthode. La couverture reste indispensable pour interpréter ces résultats.

**Décision**

Conserver deux onglets distincts : prévision par compteur et évaluation officielle E4.

Limiter les corrections de formatage aux fichiers de notre équipe afin de ne pas modifier inutilement les contributions des autres équipes.

**Transmission**

L'intégration du travail de Giovanni a été fusionnée dans `dev`. Les résultats officiels E4 sont désormais consultables depuis l'application commune.

**Preuves**

- [PR nº 59 - Intégration E4](https://github.com/SandraOub20/ParisPulse/pull/59)
- `src/app/evaluation_service.py`
- `src/app/dashboard/comparison.py`

---

## 28 novembre 2026 - Intégration des deux modèles MLP d'E2

**Question et objectif personnel**

Comment rendre accessibles les deux variantes MLP fournies par E2 tout en conservant le HGB comme méthode par défaut et en préservant les mécanismes de repli ?

**Travail réalisé**

À la demande d'E2, j'ai intégré les deux variantes de modèles déjà présentes dans le dépôt :

- MLP A : `e2-mlp-ctx-20260701-s0-9ce9`.
- MLP B : `e2-mlp-ctx-20260701-s0-37f5`.

J'ai adapté le routage du service E5, les libellés, les messages d'avertissement et les raisons de refus affichées dans les graphiques.

Je n'ai pas réentraîné les modèles ni modifié le moteur E2.

**Protocole expérimental**

Pour comparer les méthodes, j'ai conservé le même compteur, la même direction et la même date : 10 avenue de la Grande Armée, SE-NO, le 31 août 2026.

| Méthode | Prévisions | Replis | MAE |
|---|---:|---:|---:|
| HGB | 24/24 | 0 | 14,2 |
| MLP A | 24/24 | 0 | 19,8 |
| MLP B | 24/24 | 0 | 19,9 |

MAE exprimées en vélos par heure.

J'ai ensuite sélectionné le 15 juin 2026 afin de contrôler le comportement des deux MLP sur une date antérieure à la fin de leur apprentissage.

Dans les deux cas, le modèle a refusé la prévision directe et la référence hebdomadaire a fourni les 24 prévisions de secours.

**Contrôles complémentaires**

- 29 tests automatiques réussis.
- Contrôles Ruff réussis.
- Vérification de la conservation du résultat HGB.
- Vérification du parcours E3 avec un budget fixe de 72 heures.
- Contrôle de l'affichage de l'évaluation E4.

**Analyse critique et décision**

Le HGB obtient la meilleure MAE sur le cas étudié. Cette observation ne suffit cependant pas à établir un classement général des méthodes.

J'ai conservé le HGB comme modèle par défaut et identifié explicitement le MLP B comme expérimental.

Les résultats obtenus par la référence de secours ne doivent pas être attribués au MLP lorsqu'il refuse une prévision.

**Transmission**

L'équipe E2 a fourni les modèles et demandé leur intégration. J'ai rendu ces méthodes disponibles dans l'application commune sans modifier leurs poids ou leur code de prédiction.

**Preuves**

- [PR nº 60 - Intégration MLP A et MLP B](https://github.com/SandraOub20/ParisPulse/pull/60)
- `src/app/service.py`
- `src/app/streamlit_app.py`
- `src/app/dashboard/forecast_case.py`

---

## 28 novembre 2026 - Finalisation visuelle et stabilisation

**Question et objectif personnel**

Comment améliorer la lisibilité et l'ergonomie de l'application sans introduire de régression à l'approche du rendu ?

**Travail réalisé**

- Refonte de la bannière de présentation.
- Ajout d'une illustration locale.
- Création de cartes dynamiques dans la barre latérale.
- Personnalisation du panneau de configuration.
- Harmonisation des couleurs et simplification des libellés.
- Amélioration de la lisibilité des graphiques E4.
- Actualisation des libellés attendus dans les tests de navigation.

**Contrôles effectués**

J'ai isolé les modifications dans une branche dédiée, sans intervenir sur les modèles, les données ou les calculs des scores.

Les contrôles Ruff et les 56 tests de navigation et de comparaison E4 ont réussi.

Les modifications ont ensuite été fusionnées dans `dev`.

**Analyse critique**

À proximité du rendu, la stabilité de l'application est plus importante que l'ajout de nouvelles fonctionnalités.

La présentation doit faciliter l'interprétation des résultats, sans modifier leur signification scientifique. Les couleurs spécifiques aux erreurs et aux replis ont donc été conservées.

**Décision**

Geler les développements fonctionnels après cette intégration. Consacrer le travail restant à la documentation, aux commentaires, à la validation collective et à la préparation de la soutenance.

**Preuve**

- [PR nº 61 - Finalisation du design](https://github.com/SandraOub20/ParisPulse/pull/61)
- Version intégrée dans `dev` : `4c5dbde`.

---

## Bilan personnel

Ma contribution au projet ParisPulse a principalement porté sur l'intégration des composants, la coordination technique, la gestion des nouveaux sites, la visualisation des résultats, l'intégration des modèles et la stabilisation de l'application.

Ce projet m'a permis de mettre en pratique plusieurs compétences :

- Intégration de modèles de machine learning et de deep learning dans une application.
- Manipulation et visualisation de séries temporelles.
- Gestion des données manquantes et des mécanismes de repli.
- Interprétation des erreurs et des limites d'une évaluation.
- Développement collaboratif avec Git et GitHub.
- Tests de non-régression et contrôle de la qualité du code.
- Coordination entre plusieurs équipes interdépendantes.

La principale difficulté a été de maintenir une application cohérente alors que les composants des autres équipes évoluaient parallèlement.

J'ai progressivement privilégié une démarche fondée sur des intégrations ciblées, des branches dédiées et des contrôles avant fusion.

Sur le plan scientifique, je retiens notamment qu'une erreur faible ne suffit pas à caractériser une bonne méthode de prévision. Il faut également examiner la couverture, les refus, les replis, les conditions d'évaluation et la comparabilité des résultats.

## Limites et prochaines étapes

Les essais manuels réalisés sont des contrôles d'intégration sur des cas ciblés. Ils ne constituent pas une évaluation exhaustive des modèles.

L'installation sur une copie neuve par une autre équipe reste à confirmer et à consigner. La provenance de l'illustration doit également être documentée.

La dernière étape consiste à finaliser les guides utilisateurs, le rapport E5 et la préparation de la démonstration collective.

Les résultats scientifiques globaux restent ceux produits dans le cadre du protocole d'évaluation E4.
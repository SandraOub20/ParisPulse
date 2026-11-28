# ParisPulse - Plan des slides de restitution (E5)

Une slide par section ; chiffres repris du [rapport E5](E5_RAPPORT.md) et de la
[démonstration](E5_DEMONSTRATION.md). Durée cible à confirmer avec l'enseignant.

## 1. ParisPulse : prévoir les 24 prochaines heures d'un compteur vélo

- Titre, équipes, date.
- Une phrase : choisir un compteur et une date, prévoir 24 heures, comparer aux mesures.

## 2. Deux situations

- **Site connu** : des années d'historique → HGB d'E2 et références.
- **Nouveau site** : 1, 3 ou 7 jours d'historique local → Chronos-2 d'E3, gelé ou adapté.
- 113 compteurs, 58 sites : 97 connus, 5 nouveaux de développement, 10 réservés au test.

## 3. Qui fait quoi

Schéma de la [section 8 de l'architecture](../../doc/ARCHITECTURE.md#8-architecture-réalisée-de-lapplication-e5) :
E1 données → E4 cas → E5 routage → E2 ou E3 → E5 affichage et export.

Note : l'application n'a recopié aucun calcul ; elle appelle les fonctions des équipes.

## 4. Règles qui rendent la comparaison honnête

- Seul le passé publié à l'origine est transmis (délai de 24 h simulé).
- Prévision affichée avant les mesures ; jamais recalculée après.
- Une heure sans mesure n'est pas une erreur de zéro.
- Test final (octobre–novembre 2026) réservé : aucune démonstration n'y touche.

## 5. Démo 1 - Site connu (en direct)

89 boulevard de Magenta NO-SE, lundi 31/08/2026, HGB.
MAE du cas : HGB 45,5 · semaine précédente 47,2 · médiane 4 semaines 67,3 vélos/h.

## 6. Démo 2 - Nouveau site (en direct)

56 boulevard Kellermann E-O, 12/08/2026, gelé contre adapté v2.

| Budget | Gelé | Adapté v2 |
| --- | ---: | ---: |
| 24 h | 16,3 | 14,4 |
| 168 h | 6,8 | 6,5 |

Message : l'historique local compte plus que l'adaptation.

## 7. Démo 3 - Cas difficile (en direct)

- Porte de Bagnolet, 20/06 : le HGB refuse, la référence répond, l'écran l'explique.
- Quai de la Tournelle, 12/08 : 12 heures mesurées sur 24, trous visibles dans l'onglet
  *Données manquantes*.

## 8. Résultats officiels (validation, scores E4)

| Sites connus (95 compteurs) | MAE |
| --- | ---: |
| HGB | 22,25 |
| Médiane des 4 semaines | 27,01 |
| Semaine précédente | 29,75 |

| Nouveaux sites (5 compteurs) | 24 h | 72 h | 168 h |
| --- | ---: | ---: | ---: |
| Chronos-2 gelé | 26,09 | 22,83 | 19,67 |
| Chronos-2 adapté v2 | 25,89 | 22,06 | 19,27 |

Note : adaptation v2 évaluée sur les cas ayant servi à choisir ses poids → gain optimiste.

## 9. Ce qui ne marche pas encore

- Scores E4 officiels absents de l'application (MAE d'un seul cas).
- HGB sans contrôle de fraîcheur : il prévoit un compteur muet depuis le 5 juillet.
- Validation du protocole par le professeur non enregistrée.
- Lint/format non conformes ; modules de visualisation non branchés.

## 10. Recommandations

- Afficher scores E4 et couverture dans l'application.
- Fusionner le travail de fiabilité (`Team5-fiabilité`).
- Évaluer l'adaptation sur les sites réservés après le gel des choix.
- Questions.

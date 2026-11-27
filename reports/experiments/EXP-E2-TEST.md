# EXP-E2-TEST - Test final sur les sites connus (octobre-novembre 2026)

> **Statut : terminé le 2026-11-27, lu une seule fois.** Les méthodes et la lecture ont été déclarées au gel D-07 ([E2_SUIVI.md](../teams/E2_SUIVI.md), §6, commits `349a8b4` et `d08fe84`), et la lecture a été commitée dans [final_test.py](../../src/models/known/final_test.py) (`718404c`), avant le calcul. **Aucun choix n'est changé d'après ce résultat.**

- **Date, équipe, responsables et partenaires** : 2026-11-27, E2 (calcul Idir). Partenaire : E4, qui confirmera le score officiel.

- **Question** : les choix faits sur la validation (juillet-août) tiennent-ils hors période, sur des données jamais vues ?

- **Instantané, protocole, code et paramètres** :
  - `hist-20261117` et `proto-v1` ;
  - modèles figés au 01/07/2026, sans réapprentissage ;
  - mêmes réglages et même calcul du score qu'[EXP-E2-03](EXP-E2-03.md).

  Méthodes déclarées au gel :
  - `reference` et `reference_profile` ;
  - HGB `e2-hgb-ctx-20260701-s0-b357`, servi par l'application ;
  - MLP A `e2-mlp-ctx-20260701-s0-9ce9`, avec son seuil de 84 h et son repli ;
  - pour information seulement, le MLP B `e2-mlp-ctx-20260701-s0-37f5`, masqué, au seuil de 24 h et non servi.

- **Cas** : les 4 365 cas `known_site` / `test` (origines du 01/10 au 14/11/2026, 97 compteurs). 3 966 cas sont comparés, sur 93 compteurs et 43 jours avec une vérité évaluable. La période contient :
  - les vacances de la Toussaint (17/10 → 01/11) ;
  - les jours fériés du 01/11 et du 11/11 ;
  - 3 jours de grève ;
  - le changement d'heure du 25/10 (I3).

- **Commandes** :
  ```sh
  python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv --snapshot hist-20261117 \
    --experiment EXP-E2-TEST --split test --allow-test --variant <variante> [--model-run-id <id> --batch]
  python -m src.models.known.score --experiment EXP-E2-TEST --split test
  python -m src.models.known.final_test
  ```

- **Résultats** (score d'E4 refait par `score.py`, lecture système) :

  | Méthode | MAE macro | Biais | Repli |
  | --- | --- | --- | --- |
  | MLP B (information) | 16,86 | +2,4 | 202 cas |
  | **MLP A** | **17,41** | +2,6 | 207 cas |
  | **HGB (servi)** | 19,86 | +2,6 | 0 |
  | Même heure J−7 | 25,16 | +5,2 | 492 cas |
  | Médiane 4 semaines | 27,64 | +11,9 | 181 cas |

  La lecture brute donne les mêmes conclusions (MLP A 17,35, HGB 19,82).

  **Gain face aux références, par période** (bootstrap sur les jours, IC à 95 %) :

  | Période (jours) | HGB / médiane | HGB / J−7 | MLP A / médiane | MLP A / J−7 |
  | --- | --- | --- | --- | --- |
  | Ensemble (43) | +28 % [+19 ; +35] | +21 % [+12 ; +29] | +37 % [+25 ; +47] | +31 % [+19 ; +40] |
  | Normale (18) | +8 % [−14 ; +25] | +14 % [−4 ; +29] | +0 % [−24 ; +23] | +7 % [−16 ; +29] |
  | Transition (14) | +35 % [+24 ; +43] | +10 % [−5 ; +24] | +49 % [+37 ; +59] | +31 % [+19 ; +41] |
  | Vacances (11) | +39 % [+28 ; +48] | +35 % [+24 ; +46] | +57 % [+48 ; +62] | +54 % [+47 ; +59] |

  Les périodes ont été fixées avant la lecture :
  - normale : du 01/10 au 13/10 et du 09/11 au 14/11 ;
  - transition : du 14/10 au 20/10 et du 02/11 au 08/11 ;
  - vacances : du 21/10 au 01/11.

  **Tranches horaires** (MAE ; WAPE entre parenthèses) :

  | Tranche | HGB | MLP A | Médiane | J−7 |
  | --- | --- | --- | --- | --- |
  | Toutes les heures | 19,8 (20 %) | 17,3 (18 %) | 27,6 (28 %) | 25,1 (25 %) |
  | Pointe du matin 7-9 h | 25,4 | 21,2 | 54,5 | 37,1 |
  | Pointe du soir 17-19 h | 39,6 | 33,1 | 53,1 | 48,3 |
  | Nuit 0-6 h | 5,6 | 5,4 | 6,7 | 6,8 |

  **Jours particuliers** (MAE macro) :

  | Jours | HGB | MLP A | MLP B | Médiane | J−7 |
  | --- | --- | --- | --- | --- | --- |
  | Fériés (2) | 22,7 | 16,4 | 14,8 | 33,1 | 35,0 |
  | Grèves (3) | 21,6 | 15,0 | 15,4 | 35,6 | 23,8 |
  | Pluie prévue d'au moins 1 mm (14) | **19,4** | 21,1 | 19,5 | 32,5 | 29,9 |

- **Analyse** :
  - **Les modèles battent les références hors période**, aux pointes comme au total : de +21 à +37 %, avec des intervalles loin de 0.
  - **La nuance de la validation se confirme.** En semaines normales, le gain face à la médiane n'est pas significatif (+8 % [−14 ; +25] pour le HGB). Pendant les transitions et les vacances, il est très fort (+35 à +57 %). Le modèle vaut une médiane en régime stable et apporte lors des changements de régime. La nuance est donc gardée.
  - **Le MLP bat le HGB sur le test** (17,41 contre 19,86), surtout pendant les ruptures : 14,4 contre 18,6 aux transitions, et 17,1 contre 23,9 en vacances, fériés et grèves. En semaines normales, le HGB fait mieux (18,2 contre 19,7). Sur la validation, les deux étaient à égalité (22,23 contre 22,25), et la règle d'EXP-E2-03 a choisi le HGB, plus simple.
  - **Le contexte du MLP semble mieux servir les ruptures d'automne**, mais **il dégrade toujours les jours de pluie** (21,1 contre 19,4 pour le HGB). C'est l'effet vu dans EXP-E2-04, et il se confirme sur 14 jours.
  - **Le MLP B** (information) fait légèrement mieux que A (16,86 contre 17,41). Sur des semaines réelles d'automne, le masquage ne coûte rien ici, contrairement aux semaines complètes de la validation (+0,39).
  - **La médiane surestime beaucoup** (+11,9) : elle ne suit pas la baisse d'automne et des vacances.

- **Décision et recommandation** :
  - Aucun changement : le test n'est pas un jeu de réglage (D-07). Le HGB reste le modèle déclaré de l'application.
  - **Recommandation pour une suite** : revoir le choix entre MLP et HGB sur une validation qui contienne des ruptures (rentrée, vacances d'automne). Avec une seule période d'été, l'égalité de la validation masquait un avantage du MLP pendant les ruptures. Ce choix demande une nouvelle fiche et une nouvelle validation, jamais ce test.

- **Limites** :
  - 43 jours seulement, dont 2 fériés et 3 jours de grève ;
  - le changement d'heure du 25/10 décale les références d'une heure (I3) ;
  - une graine pour A et B sur le test ;
  - protocole non validé ;
  - score à confirmer par E4.

- **Lien vers données de résultats** : `data/prediction_results/EXP-E2-TEST/` (`scores_known_site_test.json`, `*_by_counter.csv`, et les prévisions dans le zip livré à E4).

# EXP-E1-04 - Longues suites de zéros : les garder ou les écarter de l'apprentissage ?

- **Date, équipe, responsables et partenaires :** 15/11/2026, E1, Sabrina (approfondissement : traitement d'un problème de qualité). Partenaires : E2 (modèle sites connus, exécution des deux variantes), E4 (cas d'évaluation, validation du protocole). Données d'entrée : comptages (`prepare.py`, Tasnim ; instantané créé par Nihed), inventaire et statuts de Zeineb (`quality.py`).
- **Question et hypothèse :** faut-il garder (A) ou écarter (B) de l'apprentissage les heures situées dans une suite d'au moins 24 h consécutives de zéros ? Hypothèse : ces suites ressemblent à des pannes ou des fermetures et non à la fréquentation habituelle ; les écarter devrait réduire l'erreur sur les compteurs concernés, sans dégrader les autres, au prix d'un historique plus court. Le sujet le rappelle : les fichiers permettent de constater ces zéros, **sans en établir la cause**.
- **Références :** sujet, fiche E1, « Approfondissement » ; `PLAN_PROJET.md` §5 (question autonome E1) et §3 (« comparer deux préparations de l'entraînement en gardant les mêmes observations d'évaluation ; mesurer aussi le changement de couverture ») ; `doc/CONTRATS.md` §3 (un zéro observé reste un zéro, évaluable) ; `doc/PROTOCOLE_EVALUATION.md` §2, §3 et §6.
- **Instantané, protocole, code et paramètres :** instantané `flux-20261115` (113 compteurs ; 1 073 839 lignes dans la version à grille commune, 1 049 499 dans la première version ; empreintes SHA-256 vérifiées le 15/11/2026). Protocole d'évaluation **proposé, non validé**. Ce protocole d'expérience est écrit **avant tout résultat** ; il est lui aussi **proposé, à valider par E4**. Code (`e1-zeros/0.1.0`) : `src/data/zeros.py` (traitement B, détection sans fuite) et `src/data/zeros_experiment.py` (comparaison A/B, règle de décision), testés par `tests/test_data_zeros.py` sur données synthétiques seulement. Le modèle d'E2 se branchera sur l'interface `Model` (`fit`, `predict`), **provisoire, à convenir avec E2** ; `ProfileModel` ne sert que de test technique du script et ne décide rien. Délai de publication : 24 h, lu dans `protocol.publication_lag_hours`.

## Les deux traitements

Un seul facteur change : **les exemples utilisés pour apprendre**. Le modèle, ses variables, ses hyperparamètres, la coupure d'apprentissage, les cas évalués et le masque d'évaluation sont identiques.

| Variante | Apprentissage | Évaluation |
| --- | --- | --- |
| **A - garder** | Toutes les heures évaluables (`is_scoreable = true`), zéros compris | Mêmes cas et mêmes heures pour A et B |
| **B - écarter** | Mêmes heures, **sauf** celles qui appartiennent à une suite d'au moins 24 h de zéros, détectée sans regarder après la coupure | Mêmes cas et mêmes heures pour A et B |

Précisions :

- **Seules les cibles d'apprentissage sont retirées.** Les entrées du modèle au moment de prévoir (valeurs passées, décalages) ne sont pas modifiées : un zéro observé reste une entrée telle quelle. Sinon, on changerait deux facteurs à la fois. Dans le code, le modèle reçoit le même historique pour A et B ; seul le drapeau `is_target` change (vérifié par test).
- **Entrées mises à jour à chaque origine.** Comme le prévoit `PROTOCOLE_EVALUATION.md` §3 (« les observations d'entrée peuvent s'actualiser à chaque origine même si le modèle reste gelé »), le modèle appris au 01/07 peut lire, pour une origine au 15/08, tous les comptages publiés avant le 15/08 (délai de 24 h compris). Cet historique est identique pour A et B (vérifié par test). Ce qui doit être confirmé avec E2 : que son modèle accepte ces entrées (`predict(cibles, historique)`) et de quel historique il a besoin.
- **Évaluation inchangée.** Un zéro observé reste une cible évaluable dans les deux variantes (contrat). Rien n'est retiré de la validation.
- **Une heure absente interrompt une suite**, comme dans `prepare.py` : une absence n'est pas un zéro.

### Détection sans fuite

Le drapeau `long_zero_run` de `counts.csv` est **rétrospectif** : il est calculé sur tout l'instantané, donc avec des heures postérieures à la coupure. Il ne sert **pas** directement.

Pour une coupure d'apprentissage `F`, la variante B recalcule les suites **uniquement avec les heures disponibles à `F`**, c'est-à-dire celles dont `interval_end + 24 h <= F` (délai de publication `protocol.publication_lag_hours` de `config/project.yaml`, et règle « toutes les cibles disponibles à `F` » de `PROTOCOLE_EVALUATION.md` §2). Une heure est écartée si elle appartient à au moins 24 h consécutives de zéros parmi ces heures. Une suite qui se prolonge au-delà n'est comptée que par sa partie disponible. Ce marquage ne sert jamais de variable de prévision.

## Données concernées

Compteurs de `S_train` (`retained` et `robustness`). Les sites réservés à E3 (`reserved_dev_new`, `reserved_test_new`) et le compteur exclu sont hors de l'étude, comme dans le reste du projet.

**Mesure descriptive des entrées** (pas un résultat de modèle) : suites de zéros ≥ 24 h parmi les heures disponibles à la coupure du 01/07/2026 00:00, heure de Paris (délai de 24 h compris). Obtenue avec `uv run python -m src.data.zeros --snapshot flux-20261115 --coupure 2026-07-01`, qui liste aussi le compteur exclu (106 av. Denfert-Rochereau NE-SO, 6 165 h), hors de l'étude. La part est calculée sur les heures évaluables publiées à la coupure.

| Compteur | Statut | Suites | Heures écartées par B | Dates (heure de Paris) | Part des heures observées |
| --- | --- | --- | --- | --- | --- |
| 24 boulevard Jourdan E-O | robustness | 2 | 3 853 | 16/10/2025 → 25/03/2026 | 62,5 % |
| 51 boulevard Masséna SO-NE | robustness | 2 | 827 | 16/10 → 19/11/2025 | 13,4 % |
| 12 avenue de la Porte de Bagnolet O-E | robustness | 1 | 357 | 30/03 → 14/04/2026 | 5,8 % |
| 12 avenue de la Porte de Bagnolet E-O | robustness | 1 | 356 | 30/03 → 14/04/2026 | 5,8 % |
| 29 boulevard des Batignolles E-O | robustness | 1 | 120 | 22 → 27/11/2025 | 2,0 % |
| 29 boulevard des Batignolles O-E | robustness | 1 | 117 | 22 → 27/11/2025 | 1,9 % |
| 35 boulevard de Ménilmontant NO-SE | robustness | 1 | 88 | 22 → 26/05/2026 | 1,4 % |
| Totem Cours la Reine O-E | robustness | 1 | 79 | 26 → 29/06/2026 | 1,3 % |
| 18 quai de l'Hôtel de Ville SE-NO | robustness | 1 | 25 | 01 → 02/05/2026 | 0,4 % |

Soit **9 compteurs concernés** (5 822 heures), **tous en `robustness`**. Zeineb les a classés ainsi précisément à cause de ces suites, et ils sont évalués à part du score principal (fiche EXP-E1-02).

Groupes de comparaison :

- **groupe témoin : les 74 compteurs `retained`**, sans aucune suite longue. C'est la population du score principal. Il sert à voir si un modèle global appris sur tout le réseau change aussi pour eux ;
- **les 8 autres compteurs `robustness`** (faible volume, série interrompue, ou suite de zéros après la coupure) sont rapportés à part, comme le prévoit leur statut. Deux d'entre eux (rue d'Aubervilliers, les deux sens, arrêtés en février 2026) n'ont aucune heure mesurée en juillet-août : ils n'auront pas de MAE (valeur absente, jamais zéro) et sont comptés comme tels.

Remarques :

- La suite de Cours la Reine se prolonge jusqu'au 30/06 : avec le délai de 24 h, seules 79 de ses 88 heures sont disponibles à la coupure.
- Jourdan E-O et Masséna ont chacune deux suites parce que l'heure absente du 26/10/2025 à 2 h (heure répétée, manquante sur tout le réseau) coupe une même période de zéros en deux. Les deux morceaux dépassent 24 h : ils sont écartés tous les deux.
- 243 boulevard Saint Germain NO-SE a une suite de 49 h du 26 au 28/09/2026 : elle n'est concernée par aucune coupure de la validation (01/07, 01/08), ni par un réentraînement au 01/09.
- Jourdan E-O a 46 % de ses heures dans des suites de zéros sur la période de sélection (seuil d'exclusion 50 %), mais 62,5 % sur la seule période d'apprentissage. Avec B, il perd près des deux tiers de son historique : il lui reste 96 jours d'heures d'apprentissage, contre 222 à 256 jours pour les huit autres. Aucun compteur ne passe donc sous le seuil de 28 jours à cette coupure.
- Les zéros isolés ne sont **pas** concernés : seules les suites ≥ 24 h le sont.

## Cas d'évaluation et règle de comparaison

À confirmer avec E4 avant toute exécution.

- **Période :** bloc de validation du protocole, juillet-août 2026. Modèle appris jusqu'à la coupure du 01/07/2026 (puis version du 01/08 si E2 la produit, comme le prévoit le protocole). **Aucune origine de septembre (diagnostic) ni d'octobre (test final)** : le test final n'est pas utilisé.
- **Cas :** un compteur de `S_train` × une origine quotidienne à 00:00 heure de Paris, 24 heures cibles. La liste des cas attendus est fixée avant l'exécution, identique pour A et B : 91 compteurs × 62 origines (01/07 au 31/08/2026) = **5 642 cas**, dont 381 sans aucune heure mesurée (les 91 cas du 22/08, les compteurs arrêtés et quelques journées isolées). Ces cas restent comptés.
- **Comparaison :** sur l'intersection des cas complets de A et de B, avec le même masque d'heures réellement mesurées (`PROTOCOLE_EVALUATION.md` §6). Les heures sans mesure sur tout le réseau (02/07 et 06/07 de 0 h à 2 h, journée du 22/08) restent dans les cas attendus : elles sont hors du masque d'évaluation (aucune observation), jamais supprimées. Le cas du 22/08 n'a donc aucune heure évaluable et est compté comme tel.

## Ce qui sera mesuré

| Mesure | Groupes | Rôle |
| --- | --- | --- |
| MAE macro (MAE par compteur, puis moyenne non pondérée) | 9 concernés ; 74 témoins `retained` ; 8 autres `robustness` | Critère principal |
| MAE par compteur, et nombre de compteurs améliorés / dégradés | 9 concernés | Voir si l'effet tient à un seul compteur (Jourdan) |
| Compteurs utilisables : au moins 28 jours d'heures d'apprentissage après traitement (heures / 24, même définition et même seuil que `observed_days` dans `quality.py`) **et** au moins un cas complet en validation | tous | Mesure de couverture demandée par le sujet |
| Cas complets / attendus (couverture 24 h) | tous | Couverture |
| MAE sur les heures cibles où l'observation vaut 0 | 9 concernés | Diagnostic : B prévoit-il moins bien un vrai zéro ? |
| Heures d'apprentissage retirées par B | par compteur | Coût en données |

## Règle de décision, fixée avant les résultats

Seuils proposés, à valider par E4 :

1. **B est retenu** si les trois conditions sont réunies :
   - la MAE macro des 9 compteurs concernés baisse d'au moins **5 %** par rapport à A ;
   - la MAE macro du groupe témoin (74 `retained`) n'augmente pas de plus de **1 %** ;
   - aucun compteur ne devient inutilisable à cause de B.
2. **Sinon, A est retenu.** C'est le traitement le plus simple et il ne retire aucune donnée.
3. Si l'amélioration ne vient que d'un ou deux compteurs, la décision le dit, et B peut être proposé seulement pour ces compteurs, comme une piste à confirmer.

Une absence de différence est une conclusion valable.

### Pourquoi ces seuils

Ce sont des **conventions fixées avant les résultats**, pas des valeurs tirées d'un document du projet ni d'un test statistique.

- **Gain d'au moins 5 % sur les compteurs concernés.** Avec 9 compteurs seulement, une petite différence de moyenne peut venir du hasard ou d'un seul compteur. Et B a un coût : il retire des données (jusqu'à 62,5 % des heures pour Jourdan E-O) et ajoute une règle à expliquer et à maintenir. On demande donc un gain net pour l'adopter.
- **Perte d'au plus 1 % sur les témoins.** Ces 74 compteurs n'ont aucune suite longue : leurs heures d'apprentissage sont identiques dans A et B. Ils ne peuvent changer que si le modèle apprend sur tout le réseau à la fois. On tolère un petit bruit, mais B ne doit pas dégrader le score principal du projet.
- **Aucun compteur perdu.** Le sujet demande de comparer l'erreur **et** le nombre de compteurs utilisables : un gain d'erreur obtenu en perdant un compteur n'est pas un gain.
- **A par défaut.** En cas de doute, on garde le traitement le plus simple, celui qui ne retire rien.

Limites de cette règle :

- la moyenne sur 9 compteurs est fragile : Jourdan E-O peut à lui seul faire passer ou échouer le seuil de 5 %. C'est pourquoi la MAE par compteur et le nombre de compteurs améliorés ou dégradés sont rapportés, et que le point 3 de la règle prévoit ce cas ;
- d'autres valeurs seraient défendables (3 % ou 10 % de gain, par exemple). Elles sont soumises à E4 et peuvent être ajustées **tant qu'aucun résultat n'existe** ; après, elles ne changent plus.

## Analyses complémentaires (fixées avant les résultats, elles ne décident rien)

Ajoutées le 15/11/2026 au soir, avant toute comparaison. Elles servent à **comprendre** le résultat principal, jamais à changer la décision prise à 24 h.

1. **Sans Jourdan E-O.** Jourdan représente 3 853 des 5 822 heures retirées (66 %). La MAE macro des concernés sera aussi calculée sur les **8 autres compteurs**. Si l'effet de B disparaît sans Jourdan, la conclusion le dira : B aide un compteur très atypique, pas les suites de zéros en général.
2. **Compteur par compteur.** MAE de A et de B pour chacun des 9 concernés, et nombre de compteurs améliorés / dégradés (déjà dans la sortie du script).
3. **Effet sur les témoins.** Variation de la MAE des 74 `retained`, pour voir si retirer des zéros chez quelques compteurs change le modèle pour tout le réseau (cas d'un modèle global).
4. **Seuil de longueur des suites : 48 h et 72 h** (option `--seuil` du script). Mesure descriptive faite avant les résultats : à 48 h comme à 72 h, B retire 5 797 heures sur 8 compteurs ; seul le quai de l'Hôtel de Ville (suite de 25 h) sort. Sur cet instantané, le seuil change donc très peu de chose : cette analyse sera rapportée brièvement, l'analyse « sans Jourdan » est la plus informative. Les groupes de comparaison restent ceux de la règle à 24 h.

## Contrôles réalisés

Tests automatiques sur un petit jeu synthétique (`tests/test_data_zeros.py`, 16 tests, verts le 16/11/2026 ; 69 tests au total après la fusion de `team1-nihed`) :

- une suite de 24 h de zéros est écartée, une suite de 23 h ne l'est pas ;
- une heure absente au milieu de zéros coupe la suite (case vide ou ligne manquante) ;
- **modifier les heures postérieures à la coupure ne change pas les heures écartées** (absence de fuite) ;
- une heure dont `interval_end + 24 h` dépasse la coupure n'est pas prise en compte ;
- B ne retire que des cibles d'apprentissage : l'historique transmis au modèle est identique pour A et B ;
- les valeurs de `count` ne sont jamais modifiées ;
- un cas compte 24 heures consécutives, y compris au passage à l'heure d'hiver ;
- comparaison sur l'intersection des cas complets, avec le même masque pour A et B ;
- un zéro observé reste une cible évaluable ;
- un cas sans aucune mesure reste compté, et un compteur sans heure évaluable n'a pas de MAE (jamais zéro) ;
- la règle de décision applique les trois conditions ; les sites réservés à E3 n'entrent pas dans l'expérience.
- à une origine, le modèle ne voit que les comptages publiés à cette date, identiques pour A et B.
- à 48 h et 72 h, B retire moins d'heures mais les groupes restent ceux de la règle à 24 h.

Sur données réelles, **sans modèle ni calcul d'erreur** (15/11/2026) : 91 compteurs répartis en 9 concernés, 74 témoins et 8 autres ; B retire 5 822 cibles d'apprentissage, toutes des zéros, sur ces 9 compteurs seulement ; historique identique pour A et B ; 5 642 cas attendus, dont 381 sans aucune mesure. **Relancé le 16/11/2026 sur la grille commune** (113 × 9 503 heures, reconstruite à partir de l'instantané) : chiffres strictement identiques, comme attendu, puisqu'une heure absente coupait déjà les suites. **Reconfirmé le 16/11/2026 sur la nouvelle version de `flux-20261115`** (les 8 fichiers reçus ont l'empreinte SHA-256 du manifeste ; 1 073 839 lignes, 9 503 par compteur, `direction` remplie, drapeau `network_gap` présent) : 5 822 heures sur 9 compteurs, 5 642 cas dont 381 sans mesure, 5 797 heures à 48 h et 72 h.

## Résultats mesurés

*À remplir après l'exécution par E2. Laissé vide volontairement : le protocole est fixé avant les résultats.*

## Analyse, limites et décision

*À remplir après les résultats.* Limites connues dès maintenant :

- Les effectifs sont petits (9 compteurs concernés) : la MAE par compteur sera rapportée en plus de la moyenne.
- La cause des zéros reste inconnue : B suppose qu'ils ne décrivent pas la fréquentation habituelle, ce qui n'est pas prouvé.
- La grille commune (étape 2, faite par Nihed le 15/11) ne change aucun chiffre de cette fiche (relancé le 16/11).
- Le résultat dépend du modèle d'E2 : un modèle global et un modèle par compteur peuvent réagir différemment.

## Lien vers les données et retours des partenaires

- Données : `data/processed/flux-20261115/counts.csv`, `inventory_quality.csv`.
- Validation du protocole par E4 : *à renseigner*.
- Exécution par E2 et preuve d'usage : *à renseigner*.

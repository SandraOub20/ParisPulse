# EXP-E1-04 - Longues suites de zéros : les garder ou les remplacer par l'année d'avant ?

- **Date, équipe, responsables et partenaires :** 15/11/2026, E1, Sabrina (approfondissement : traitement d'un problème de qualité). Partenaires : E2 (modèle sites connus, exécution des deux variantes), E4 (cas d'évaluation, validation du protocole). Données d'entrée : comptages (`prepare.py`, Tasnim ; instantané créé par Nihed), inventaire et statuts de Zeineb (`quality.py`).
- **Question et hypothèse :** pour apprendre, faut-il garder (A) les heures situées dans une suite d'au moins 24 h consécutives de zéros, ou les remplacer par les valeurs du même compteur un an avant (C) ? Hypothèse : ces suites ressemblent à des pannes ou des fermetures et non à la fréquentation habituelle ; les remplacer devrait réduire l'erreur sur les compteurs concernés, sans dégrader les autres. Le sujet le rappelle : les fichiers permettent de constater ces zéros, **sans en établir la cause**.
- **Références :** sujet, fiche E1, « Approfondissement » (« mesurez avec les équipes 2 et 4 l'effet de deux traitements sur l'erreur et sur le nombre de compteurs utilisables ») ; `PLAN_PROJET.md` §5 (question autonome E1) et §3 (« comparer deux préparations de l'entraînement en gardant les mêmes observations d'évaluation ; mesurer aussi le changement de couverture ») ; `doc/CONTRATS.md` §3 (un zéro observé reste un zéro, évaluable ; les cibles ne sont jamais imputées) ; `doc/PROTOCOLE_EVALUATION.md` §2, §3 et §6.
- **Instantané, protocole, code et paramètres :** mesure descriptive sur `flux-20261115`, version régénérée par Nihed le 17/11/2026 (`e1-prepare/0.3.0`, grille commune du 16/10/2025 00:00 UTC au 14/11/2026 22:00 UTC : 113 compteurs × 9 479 heures = 1 071 127 lignes ; empreintes SHA-256 des 8 fichiers de `data/processed/` vérifiées le 17/11/2026). Comparaison A/C sur l'historique `hist-20261117`, seul instantané qui contient l'année d'avant (voir « Données concernées »). Protocole d'évaluation **proposé, non validé**. Ce protocole d'expérience est écrit **avant tout résultat** ; il est lui aussi **proposé, à valider par E4**. Code (`e1-zeros/0.2.0`) : `src/data/zeros.py` (détection sans fuite, traitement C) et `src/data/zeros_experiment.py` (comparaison A/C, règle de décision), testés par `tests/test_data_zeros.py` sur données synthétiques seulement. Le modèle d'E2 se branchera sur l'interface `Model` (`fit`, `predict`), **provisoire, à convenir avec E2** ; `ProfileModel` ne sert que de test technique du script et ne décide rien. Délai de publication : 24 h, lu dans `protocol.publication_lag_hours`.

## Évolution du protocole (18/11/2026, avant tout résultat)

Le 15/11, le second traitement était B : **écarter** ces heures des cibles d'apprentissage. Le 18/11, Sabrina a décidé que les données livrées aux autres équipes remplacent ces suites par l'année d'avant (`src/data/fill_counts.py`, qui remplit directement `counts.csv` depuis le 19/11, sur les heures marquées `long_zero_run`). Le sujet demande de mesurer l'effet des traitements avec E2 et E4 : l'étude compare donc A au traitement réellement appliqué, **C**, à la place de B. Aucun résultat n'existait : la règle de décision et les analyses complémentaires sont reprises telles quelles, pour C.

## Les deux traitements

Un seul facteur change : **le traitement des longues suites de zéros dans les données d'apprentissage**. Le modèle, ses variables, ses hyperparamètres, la coupure d'apprentissage, les cas évalués et le masque d'évaluation sont identiques.

| Variante | Apprentissage | Évaluation |
| --- | --- | --- |
| **A - garder** | Toutes les heures publiées à la coupure, telles quelles ; les heures évaluables (`is_scoreable = true`), zéros compris, sont les cibles | Mêmes cas et mêmes heures pour A et C |
| **C - année d'avant** | Mêmes heures ; chaque heure d'une suite d'au moins 24 h de zéros, détectée sans regarder après la coupure, reçoit la valeur du même compteur aux mêmes date et heure de Paris un an avant, **si elle est > 0** ; cette heure n'est alors plus une cible | Mêmes cas et mêmes heures pour A et C |

Précisions :

- **Une valeur remplacée est une entrée, jamais une cible.** Le contrat le demande (`doc/CONTRATS.md` §3 : « Les cibles ne sont jamais imputées ») : le modèle peut lire la valeur d'un an avant dans son historique, mais n'apprend pas à la prévoir (`is_target` faux). C'est la même règle que dans les données livrées (`is_scoreable` faux).
- **Le zéro est gardé quand l'année d'avant ne donne pas de valeur.** Si la même heure un an avant vaut 0, est vide, ou est inconnue (avant le début de l'instantané, ou avant la première mesure du compteur), rien ne change : le zéro reste une entrée et une cible. Le sujet le demande : « ne remplacez pas automatiquement les zéros par des valeurs manquantes ».
- **Entrées mises à jour à chaque origine.** Comme le prévoit `PROTOCOLE_EVALUATION.md` §3 (« les observations d'entrée peuvent s'actualiser à chaque origine même si le modèle reste gelé »), le modèle appris au 01/07 peut lire, pour une origine au 15/08, tous les comptages publiés avant le 15/08 (délai de 24 h compris). Pour C, cet historique contient les valeurs remplacées à la coupure. Le traitement est appliqué une fois, à la coupure, comme l'apprentissage : une suite apparue après la coupure n'est pas remplacée (la détecter demanderait de lire au-delà). Ce qui doit être confirmé avec E2 : que son modèle accepte ces entrées (`predict(cibles, historique)`) et de quel historique il a besoin.
- **Évaluation inchangée.** Les cibles d'évaluation sont les comptages d'origine. Un zéro observé reste une cible évaluable dans les deux variantes (contrat). Rien n'est retiré de la validation.
- **Une heure absente interrompt une suite**, comme dans `prepare.py` : une absence n'est pas un zéro.

### Détection sans fuite

Le drapeau `long_zero_run` de `counts.csv` est **rétrospectif** : il est calculé sur tout l'instantané, donc avec des heures postérieures à la coupure. Il ne sert **pas** directement. Pour la même raison, l'étude ne reprend pas les remplacements de `fill_counts.py`, dont les suites sont aussi détectées sur toute la série : elle relit `counts.csv` avec ses valeurs d'origine (`src/data/original.py`, grâce à `count_raw`) et applique C à la coupure.

Pour une coupure d'apprentissage `F`, la variante C recalcule les suites **uniquement avec les heures disponibles à `F`**, c'est-à-dire celles dont `interval_end + 24 h <= F` (délai de publication `protocol.publication_lag_hours` de `config/project.yaml`, ou du gabarit `config/project.example.yaml` si ce fichier n'existe pas, et règle « toutes les cibles disponibles à `F` » de `PROTOCOLE_EVALUATION.md` §2). Une heure est traitée si elle appartient à au moins 24 h consécutives de zéros parmi ces heures. Une suite qui se prolonge au-delà n'est comptée que par sa partie disponible. La valeur d'un an avant est publiée bien avant `F`. Ce marquage ne sert jamais de variable de prévision.

## Données concernées

Compteurs de `S_train` (`retained` et `robustness`). Les sites réservés à E3 (`reserved_dev_new`, `reserved_test_new`) et le compteur exclu sont hors de l'étude, comme dans le reste du projet.

**Mesure descriptive des entrées** (pas un résultat de modèle) : suites de zéros ≥ 24 h parmi les heures disponibles à la coupure du 01/07/2026 00:00, heure de Paris (délai de 24 h compris). Obtenue avec `uv run python -m src.data.zeros --snapshot flux-20261115 --coupure 2026-07-01`, qui liste aussi le compteur exclu (106 av. Denfert-Rochereau NE-SO, 6 165 h), hors de l'étude. La part est calculée sur les heures évaluables publiées à la coupure.

| Compteur | Statut | Suites | Heures en suite longue | Dates (heure de Paris) | Part des heures observées |
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

**Sur `flux-20261115`, C ne remplace aucune de ces heures** (0 sur 5 822, vérifié le 18/11/2026 avec la même commande) : l'instantané commence le 16/10/2025, et toutes ces suites sont antérieures au 16/10/2026, donc leur année d'avant est hors de l'instantané. Sur le flux, A et C seraient identiques. La comparaison se fera donc sur l'historique `hist-20261117`, qui contient les archives 2023 à 2025. **Mesuré sur `hist-20261117` le 19/11/2026** (`uv run python -m src.data.zeros --snapshot hist-20261117 --coupure 2026-07-01`, valeurs d'origine) : 26 compteurs ont au moins une suite longue à la coupure, soit 50 552 heures, dont **17 770 remplacées par C** (année d'avant > 0) ; les autres gardent leur zéro (0, vide ou inconnu un an avant). Exemples : Jourdan E-O 8 408 h remplacées sur 12 900, Masséna SO-NE 5 456 sur 5 692, Denfert-Rochereau (exclu, hors étude) 1 883 sur 21 583. Ces chiffres comptent tous les compteurs, réservés et exclu compris ; les groupes de comparaison se calculent avec l'inventaire de l'historique (67 `retained`, 30 `robustness`, 10 + 5 réservés, 1 exclu), qui n'a pas les mêmes statuts que celui du flux (question Q6 de la fiche `E1-historique.md`). Le tableau ci-dessus reste celui du flux.

Groupes de comparaison (sur le flux) :

- **groupe témoin : les 74 compteurs `retained`**, sans aucune suite longue. C'est la population du score principal. Il sert à voir si un modèle global appris sur tout le réseau change aussi pour eux ;
- **les 8 autres compteurs `robustness`** (faible volume, série interrompue, ou suite de zéros après la coupure) sont rapportés à part, comme le prévoit leur statut. Deux d'entre eux (rue d'Aubervilliers, les deux sens, arrêtés en février 2026) n'ont aucune heure mesurée en juillet-août : ils n'auront pas de MAE (valeur absente, jamais zéro) et sont comptés comme tels.

Les compteurs concernés sont ceux qui ont au moins une suite longue à la coupure, que C y remplace des heures ou non. Le nombre d'heures remplacées par compteur est affiché par `zeros.py` (colonne `n_hours_replaced_c`).

Remarques :

- La suite de Cours la Reine se prolonge jusqu'au 30/06 : avec le délai de 24 h, seules 79 de ses 88 heures sont disponibles à la coupure.
- Jourdan E-O et Masséna ont chacune deux suites parce que l'heure absente du 26/10/2025 à 2 h (heure répétée, manquante sur tout le réseau) coupe une même période de zéros en deux. Les deux morceaux dépassent 24 h : ils sont traités tous les deux.
- 243 boulevard Saint Germain NO-SE a une suite de 49 h du 26 au 28/09/2026 : elle n'est concernée par aucune coupure de la validation (01/07, 01/08), ni par un réentraînement au 01/09.
- Jourdan E-O a 46 % de ses heures dans des suites de zéros sur la période de sélection (seuil d'exclusion 50 %), mais 62,5 % sur la seule période d'apprentissage. Avec C, il perd au plus ces 3 853 cibles (si l'année d'avant est > 0 partout) : il lui reste au moins 96 jours d'heures d'apprentissage, contre 222 à 256 jours pour les huit autres dans le même cas. Aucun compteur ne passe donc sous le seuil de 28 jours à cette coupure.
- D'après l'examen des archives (fiche `E1-historique.md`, ligne « Zéros : année d'avant »), Jourdan E-O et Denfert-Rochereau étaient déjà à zéro un an avant : aux heures où l'année d'avant vaut 0, C garde le zéro. Le nombre de ces heures est à mesurer sur l'historique.
- Les zéros isolés ne sont **pas** concernés : seules les suites ≥ 24 h le sont.

## Cas d'évaluation et règle de comparaison

À confirmer avec E4 avant toute exécution.

- **Période :** bloc de validation du protocole, juillet-août 2026. Modèle appris jusqu'à la coupure du 01/07/2026 (puis version du 01/08 si E2 la produit, comme le prévoit le protocole). **Aucune origine de septembre (diagnostic) ni d'octobre (test final)** : le test final n'est pas utilisé. **À confirmer avec E4** : le début de l'apprentissage sur l'historique (le protocole proposé, écrit pour le flux seul, le fait commencer au 11/10/2025 ; sur `hist-20261117`, A et C apprennent sur les mêmes heures publiées à la coupure, quelle que soit cette date).
- **Cas :** un compteur de `S_train` × une origine quotidienne à 00:00 heure de Paris, 24 heures cibles. La liste des cas attendus est fixée avant l'exécution, identique pour A et C. Sur le flux : 91 compteurs × 62 origines (01/07 au 31/08/2026) = **5 642 cas**, dont 381 sans aucune heure mesurée (les 91 cas du 22/08, les compteurs arrêtés et quelques journées isolées). Ces cas restent comptés. À recompter sur l'historique.
- **Comparaison :** sur l'intersection des cas complets de A et de C, avec le même masque d'heures réellement mesurées (`PROTOCOLE_EVALUATION.md` §6). Les heures sans mesure sur tout le réseau (02/07 et 06/07 de 0 h à 2 h, journée du 22/08) restent dans les cas attendus : elles sont hors du masque d'évaluation (aucune observation), jamais supprimées. Le cas du 22/08 n'a donc aucune heure évaluable et est compté comme tel.

## Ce qui sera mesuré

| Mesure | Groupes | Rôle |
| --- | --- | --- |
| MAE macro (MAE par compteur, puis moyenne non pondérée) | concernés ; témoins `retained` ; autres `robustness` | Critère principal |
| MAE par compteur, et nombre de compteurs améliorés / dégradés | concernés | Voir si l'effet tient à un seul compteur (Jourdan) |
| Compteurs utilisables : au moins 28 jours d'heures d'apprentissage (cibles) après traitement (heures / 24, même définition et même seuil que `observed_days` dans `quality.py`) **et** au moins un cas complet en validation | tous | Mesure de couverture demandée par le sujet |
| Cas complets / attendus (couverture 24 h) | tous | Couverture |
| MAE sur les heures cibles où l'observation vaut 0 | concernés | Diagnostic : C prévoit-il moins bien un vrai zéro ? |
| Heures remplacées par C (`n_hours_replaced_c`) | total et par compteur | Coût en cibles d'apprentissage |

## Règle de décision, fixée avant les résultats

Seuils proposés, à valider par E4 :

1. **C est retenu** si les trois conditions sont réunies :
   - la MAE macro des compteurs concernés baisse d'au moins **5 %** par rapport à A ;
   - la MAE macro du groupe témoin (`retained`) n'augmente pas de plus de **1 %** ;
   - aucun compteur ne devient inutilisable à cause de C.
2. **Sinon, A est retenu.** C'est le traitement le plus simple et il ne modifie aucune donnée. Les données remplies livrées aux autres équipes seraient alors à revoir avec elles.
3. Si l'amélioration ne vient que d'un ou deux compteurs, la décision le dit, et C peut être proposé seulement pour ces compteurs, comme une piste à confirmer.

Une absence de différence est une conclusion valable.

### Pourquoi ces seuils

Ce sont des **conventions fixées avant les résultats**, pas des valeurs tirées d'un document du projet ni d'un test statistique.

- **Gain d'au moins 5 % sur les compteurs concernés.** Avec 9 compteurs seulement sur le flux, une petite différence de moyenne peut venir du hasard ou d'un seul compteur. Et C a un coût : les heures remplacées ne sont plus des cibles (jusqu'à 62,5 % des heures pour Jourdan E-O), et il ajoute une règle à expliquer et à maintenir. On demande donc un gain net pour l'adopter.
- **Perte d'au plus 1 % sur les témoins.** Ces compteurs n'ont aucune suite longue : leurs heures d'apprentissage sont identiques dans A et C. Ils ne peuvent changer que si le modèle apprend sur tout le réseau à la fois. On tolère un petit bruit, mais C ne doit pas dégrader le score principal du projet.
- **Aucun compteur perdu.** Le sujet demande de comparer l'erreur **et** le nombre de compteurs utilisables : un gain d'erreur obtenu en perdant un compteur n'est pas un gain.
- **A par défaut.** En cas de doute, on garde le traitement le plus simple, celui qui ne modifie rien.

Limites de cette règle :

- la moyenne sur 9 compteurs est fragile : Jourdan E-O peut à lui seul faire passer ou échouer le seuil de 5 %. C'est pourquoi la MAE par compteur et le nombre de compteurs améliorés ou dégradés sont rapportés, et que le point 3 de la règle prévoit ce cas ;
- d'autres valeurs seraient défendables (3 % ou 10 % de gain, par exemple). Elles sont soumises à E4 et peuvent être ajustées **tant qu'aucun résultat n'existe** ; après, elles ne changent plus.

## Analyses complémentaires (fixées avant les résultats, elles ne décident rien)

Ajoutées le 15/11/2026 au soir, avant toute comparaison, et reprises pour C le 18/11/2026. Elles servent à **comprendre** le résultat principal, jamais à changer la décision prise à 24 h.

1. **Sans Jourdan E-O.** Jourdan représente 3 853 des 5 822 heures en suite longue (66 %). La MAE macro des concernés sera aussi calculée sans lui (fonction `concerned_without` de `zeros_experiment.py`, affichée à la fin de la sortie du script). Si l'effet de C disparaît sans Jourdan, la conclusion le dira : C aide un compteur très atypique, pas les suites de zéros en général.
2. **Compteur par compteur.** MAE de A et de C pour chacun des concernés, et nombre de compteurs améliorés / dégradés (tableau « MAE par compteur concerné » et colonnes `n_improved` / `n_degraded` de la sortie du script).
3. **Effet sur les témoins.** Variation de la MAE des `retained`, pour voir si remplacer des zéros chez quelques compteurs change le modèle pour tout le réseau (cas d'un modèle global).
4. **Seuil de longueur des suites : 48 h et 72 h** (option `--seuil` du script). Mesure descriptive sur le flux, faite avant les résultats : à 48 h comme à 72 h, les suites comptent 5 797 heures sur 8 compteurs ; seul le quai de l'Hôtel de Ville (suite de 25 h) sort. Les groupes de comparaison restent ceux de la règle à 24 h.

## Contrôles réalisés

Tests automatiques sur un petit jeu synthétique (`tests/test_data_zeros.py`, 20 tests, verts le 18/11/2026 ; 134 tests au total dans le dépôt à cette date) :

- une suite de 24 h de zéros est détectée, une suite de 23 h ne l'est pas ;
- une heure absente au milieu de zéros coupe la suite (case vide ou ligne manquante) ;
- **modifier les heures postérieures à la coupure ne change ni les suites détectées ni les valeurs de C** (absence de fuite) ;
- une heure dont `interval_end + 24 h` dépasse la coupure n'est pas prise en compte ;
- A ne change rien ; C remplace par l'année d'avant quand elle est > 0, et ces heures ne sont plus des cibles ; quand l'année d'avant vaut 0 ou est vide, le zéro reste, et reste une cible ; sans année d'avant dans l'instantané, C est identique à A ;
- les comptages d'origine ne sont jamais modifiés (C travaille sur une copie) ;
- l'historique transmis au modèle a les mêmes heures et la même publication pour A et C : A y garde les zéros, C les valeurs d'un an avant ;
- un cas compte 24 heures consécutives, y compris au passage à l'heure d'hiver ;
- comparaison sur l'intersection des cas complets, avec le même masque pour A et C ;
- un zéro observé reste une cible évaluable ;
- un cas sans aucune mesure reste compté, et un compteur sans heure évaluable n'a pas de MAE (jamais zéro) ;
- la règle de décision applique les trois conditions ; les sites réservés à E3 n'entrent pas dans l'expérience ;
- à une origine, le modèle ne voit que les comptages publiés à cette date ;
- à 48 h et 72 h, C remplace moins d'heures, mais les groupes restent ceux de la règle à 24 h ;
- l'analyse « sans Jourdan E-O » recalcule la MAE macro des seuls concernés restants ; sans aucun compteur, elle ne donne pas de valeur (jamais zéro) ;
- une heure sans mesure remplacée par J-7 (`src/data/fill_j7.py` : `count` remplacé, `count_raw` vide, `is_observed` et `is_scoreable` faux) ne compte jamais comme un zéro observé et ne rallonge pas une suite (`tests/test_data_fill_j7.py`).

Sur données réelles, **sans modèle ni calcul d'erreur** (15/11/2026) : 91 compteurs répartis en 9 concernés, 74 témoins et 8 autres ; 5 822 heures en suite longue, toutes des zéros, sur ces 9 compteurs seulement ; 5 642 cas attendus, dont 381 sans aucune mesure. **Relancé le 16/11/2026 sur la grille commune** (113 × 9 503 heures, reconstruite à partir de l'instantané) : chiffres strictement identiques, comme attendu, puisqu'une heure absente coupait déjà les suites. **Reconfirmé le 16/11/2026 sur la nouvelle version de `flux-20261115`** (les 8 fichiers reçus ont l'empreinte SHA-256 du manifeste ; 1 073 839 lignes, 9 503 par compteur, `direction` remplie, drapeau `network_gap` présent) : 5 822 heures sur 9 compteurs, 5 642 cas dont 381 sans mesure, 5 797 heures à 48 h et 72 h. **Relancé le 17/11/2026 sur la version régénérée (`e1-prepare/0.3.0`)** : la grille commence maintenant au premier jour UTC complet (16/10/2025 00:00 UTC), soit 9 479 heures par compteur et 1 071 127 lignes. Tous les chiffres de cette fiche sont inchangés : 9 compteurs concernés et 5 822 heures (même tableau, mêmes parts), 74 témoins et 8 autres, 5 642 cas dont 381 sans mesure, 5 797 heures sur 8 compteurs à 48 h et 72 h, 96 jours d'apprentissage restants pour Jourdan E-O si toutes ses heures de suite sont retirées des cibles. **18/11/2026, passage à C** : mêmes 5 822 heures sur les 9 compteurs ; C n'en remplace aucune sur le flux (année d'avant hors de l'instantané).

## Résultats mesurés

*À remplir après l'exécution par E2, sur l'historique. Laissé vide volontairement : le protocole est fixé avant les résultats.*

## Analyse, limites et décision

*À remplir après les résultats.* Limites connues dès maintenant :

- Les effectifs sont petits (9 compteurs concernés sur le flux) : la MAE par compteur sera rapportée en plus de la moyenne.
- La cause des zéros reste inconnue : C suppose que l'année d'avant décrit mieux la fréquentation que la suite de zéros, ce qui n'est pas prouvé.
- C ne se mesure que sur l'historique : sur le flux, l'année d'avant manque pour toutes les suites d'avant la coupure.
- Dans les données livrées (`counts.csv` rempli), les suites sont détectées sur toute la série ; dans l'étude, à la coupure. Les heures remplacées peuvent donc différer près de la coupure (Cours la Reine : 79 h sur 88 dans l'étude).
- La grille commune (étape 2, faite par Nihed le 15/11) et la fenêtre au premier jour complet (`e1-prepare/0.3.0`, 17/11) ne changent aucun chiffre de cette fiche (relancé le 16/11 et le 17/11).
- Le résultat dépend du modèle d'E2 : un modèle global et un modèle par compteur peuvent réagir différemment.

## Lien vers les données et retours des partenaires

- Données : mesure descriptive sur `data/processed/flux-20261115/counts.csv` et `inventory_quality.csv` ; comparaison A/C sur `data/processed/hist-20261117/` (à recevoir).
- Validation du protocole par E4 : *à renseigner*.
- Exécution par E2 et preuve d'usage : *à renseigner*.

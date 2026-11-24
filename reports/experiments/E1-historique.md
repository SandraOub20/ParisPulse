# E1 - Historique : archives 2023-2025 et instantané `hist-20261117`

- **Date, équipe, responsables :** 18/11/2026, E1. Assemblage et préparation : Nihed (17/11/2026, `src/data/archives.py`, `e1-archives/0.3.0`). Fiche (tâche A5 de la passation) : Sabrina.
- **Question :** peut-on ajouter deux années d'archives avant le flux courant, sur une seule grille, sans rupture entre archives et flux ?
- **Décision de départ :** réunion E1 du 17/11/2026 : ajouter l'historique, d'abord **2 cycles d'un an alignés sur le début du flux** (16/10), et non au 1er janvier.
- **Sources :** jeu Open Data Paris `comptage-velo-historique-donnees-compteurs` (un fichier par année, pièces jointes « par compteur et par heure »), et flux courant `flux-20261115`.
- **Statut des chiffres :** sauf mention contraire, les chiffres de cette fiche viennent de la passation de Nihed du 17/11/2026. Les chiffres de base (lignes, heures, part observée, statuts) ont été revérifiés le 19/11/2026 sur `hist-20261117`, reçu en zip : identiques (section « Outils lancés sur l'historique »).

## Les deux instantanés

| Instantané | Période (UTC) | Usage |
| --- | --- | --- |
| `flux-20261115` | 16/10/2025 → 14/11/2026 (13 mois) | Utilisé par les autres équipes, **inchangé** |
| `hist-20261117` | 16/10/2023 → 14/11/2026 (3 ans) | **Livré le 19/11/2026** (branche `Team1`, Git LFS), remplace `flux-20261115` ; vérifié côté consommateur le 24/11 ([EXP-E1-05](E1-verification-livraison.md)) |

## Les archives

| | 2023 | 2024 | 2025 |
| --- | --- | --- | --- |
| Format | zip, UTF-8, `;` | zip, UTF-8, `;` | zip, latin-1, `,` |
| Lignes / identifiants | 860 190 / 101 | 1 505 640 / 179 | 1 502 954 / 172 |
| Dates avec fuseau | oui | oui | oui |
| Doublons / conflits | 0 | 0 | 0 |
| Particularités | colonnes en plus (photos) | une ligne par heure sans identifiant (agrégat, voir A4 ci-dessous) | idem, et nombres écrits « 1 007 » |

**Vérifié le 18/11/2026 (Sabrina)** sur les archives retéléchargées dans `archive-20261117` : lignes, identifiants, formats et doublons identiques au tableau ; 49 canaux jumeaux, 7 renommages et 17 542 lignes sans identifiant retrouvés avec `archives.find_twins` et `archives.archive_long`.

Les archives brutes restent intactes (`data/history/archive-20261117/archives/`) ; un fichier déjà présent n'est jamais retéléchargé sans `--force` (`archives.py`).

## Découverte : la réorganisation des compteurs au 1er janvier 2024

Comparaison heure par heure archive / flux sur la période commune (16/10 → 31/12/2025, 1 846 h) :

- **57 compteurs** identiques tels quels ;
- **49 compteurs** découpés en deux canaux dans l'archive depuis janvier 2024 (ex. `…-103…` = 101 + 103, `…-104…` = 102 + 104 ; pour les sites `300030…`, un canal voisin). Le flux publie la somme ; une fois additionnés, 100 % d'heures identiques ;
- **7 compteurs renommés** dans l'archive en 2024-2025 (ex. Voie Georges Pompidou : `100042374-109042374` dans le flux = `100042374-101042374` dans l'archive).

Selon la passation, le raccord en janvier 2024 est continu (même baisse saisonnière que l'année suivante) ; sans la somme, ces sens chutaient de 90 à 97 %.

## Règles d'assemblage (validées par Nihed)

| Règle | Contenu |
| --- | --- |
| R1 | Compteur = canal + canal jumeau, depuis l'apparition du jumeau. Jumeau trouvé automatiquement sur la période commune : au moins 99 % d'heures identiques au flux. Avant l'apparition du jumeau, le canal seul. |
| R1 bis | Compteur renommé : ses heures manquantes sont prises sous son autre identifiant (même seuil de 99 %). |
| R2 | Lignes sans identifiant (17 542 lignes, une par heure en 2024 et 2025) écartées et comptées. Ce n'est **pas** le total des compteurs (A4 ci-dessous). |
| R3 (option A) | Seuls les 113 compteurs du flux sont gardés ; les 26 anciens compteurs présents seulement dans les archives sont listés dans le manifeste, hors grille. |
| Priorité | Archives avant le 16/10/2025, flux ensuite. |

Pour `hist-…`, `prepare.py` lit le brut et la fenêtre dans le bloc `history` du manifeste, sans écarter de premier jour ; rien ne change pour `flux-…`.

### A4 - Les lignes sans identifiant ne sont pas le total (Sabrina, 18/11/2026)

La passation les décrivait comme « le total horaire ». Vérification sur les archives : pour chaque heure, valeur de la ligne sans identifiant comparée à la somme des compteurs identifiés à la même heure.

| Archive | Lignes sans identifiant | Heures égales à la somme | Rapport médian « sans identifiant / somme » |
| --- | --- | --- | --- |
| 2023 | 0 | - | - |
| 2024 | 8 783 (une par heure) | 0 sur 8 783 | 0,32 |
| 2025 | 8 759 (une par heure) | 0 sur 8 759 | 0,33 |

- Ces lignes n'ont ni nom, ni site, ni coordonnées (`null, null`), seulement une date et un comptage. Exemple : 01/01/2024 00:00 UTC, 953 contre 3 361 pour les 162 compteurs mesurés.
- Aucun compteur seul, aucune famille d'identifiants (`1000…`, `3000…`) et aucun type de canal (`101` à `104`) ne donne cette valeur. Elle suit pourtant l'activité du réseau (corrélation de 0,98 avec certains compteurs).
- **Conclusion :** agrégat horaire de nature inconnue. R2 reste juste (sans identifiant, impossible de rattacher ces lignes à un compteur) ; aucun chiffre de l'historique ne change. Le mot « total » est à retirer du contrat (A8).

## Résultat : `hist-20261117`

- Grille commune du 16/10/2023 00:00 au 14/11/2026 22:00 UTC : **27 023 h**, 113 compteurs, **3 053 599 lignes**.
- 96,6 % d'heures observées ; 104 heures `network_gap`, dont une heure perdue à chaque passage à l'heure d'hiver (2023, 2024, 2025).
- 431 alertes à examiner (tâche A3) ; 58 groupes de sites ; 113 directions opposées.
- Contexte 2023-2025 (Nihed, 17/11) : calendrier et observations Météo-France complets ; prévision J-2 du modèle JMA GSM jusqu'au 20/01/2024 12:00 UTC (exclu), puis du modèle par défaut (une seule bascule, `location_id` différent, détail dans `context_sources.json`). Jointure : 3 053 599 lignes avant et après, 0 prévision manquante ; observation manquante : pluie 0,45 %, vent 4 h, température 1 h.

**Sélection (`quality.py`) :**

| Statut | `flux-20261115` | `hist-20261117` |
| --- | --- | --- |
| `retained` | 74 | 67 |
| `robustness` | 17 | 30 |
| `reserved_test_new` | 15 | 10 (5 groupes) |
| `reserved_dev_new` | 6 | 5 (4 groupes) |
| `excluded` | 1 | 1 (Denfert-Rochereau) |

Selon la passation, la hausse des `robustness` vient surtout du critère « au moins une suite de zéros ≥ 24 h » appliqué sur 3 ans au lieu d'un an (décision A2, ci-dessous).

## Refaire l'instantané

Depuis la racine du dépôt, avec le brut de `flux-20261115` en place (commandes de `archives.py` et de la passation) :

```
uv run python -m src.data.archives --snapshot archive-20261117 --cycles 2 --comparer flux-20261115
uv run python -m src.data.archives --assembler hist-20261117 --snapshot archive-20261117 --comparer flux-20261115 --cycles 2
uv run python -m src.data.quality --snapshot hist-20261117
```

Sorties attendues selon la passation : 49 jumeaux, 7 renommages, 0 compteur sous 99 %, 17 542 lignes sans identifiant, 26 anciens compteurs, 27 023 h, 96,6 % observées, puis 67 / 30 / 10 / 5 / 1.

## Outils lancés sur l'historique (Sabrina, 19/11/2026)

`hist-20261117` reçu de Nihed en zip le 19/11/2026 : les 8 fichiers de `data/processed/hist-20261117/` ont l'empreinte SHA-256 de son manifeste, et les trois archives qu'il cite ont la même empreinte que celles téléchargées le 18/11. Vérifié : 3 053 599 lignes, 113 compteurs, 27 023 heures (16/10/2023 00:00 → 14/11/2026 22:00 UTC), 96,6 % observées, statuts 67 / 30 / 10 / 5 / 1 : identique à la passation. Contexte converti au format `label` (166 532 → 164 278 lignes), puis grèves ajoutées (B4, ci-dessous).

| Tâche | Commande | Sur `flux-20261115` | Sur `hist-20261117` |
| --- | --- | --- | --- |
| A3 - alertes du manifeste | `uv run python -m src.data.alerts_review --snapshot hist-20261117` | 229 alertes = 113 heures perdues au passage à l'heure d'hiver + 108 journées non publiées + 8 pics | 431 alertes = 314 heures perdues au passage à l'heure d'hiver (sur tout le réseau) + 108 journées non publiées + 4 pics du soir (sens des trajets) + **5 manques propres au compteur**, examinés ci-dessous |
| A2 - critère des zéros | `uv run python -m src.data.zeros_criteria --snapshot hist-20261117` | option 1 = inventaire (95 / 17 / 1 avant réservation) ; seuils 1 %, 5 %, 10 % : 15, 9, 8 `robustness` | option 1 = inventaire (82 / 30 / 1 avant réservation) ; seuils 1 %, 5 %, 10 % : 18, 9, 7 `robustness` |
| B1 - mêmes dates un an avant | `uv run python -m src.data.zeros_years --snapshot hist-20261117 --annees 1 2` | 17 suites ; 1 seule comparable un an avant | 153 suites. Un an avant : 40 comparables, dont 14 avec des zéros aux mêmes dates ; 113 non comparables (compteur pas encore installé ou avant le 16/10/2023). Deux ans avant : 13 comparables, dont 4 |
| B7 - étude des zéros, A / C | `uv run python -m src.data.zeros --snapshot hist-20261117 --coupure 2026-07-01` (description), puis `zeros_experiment` avec le modèle d'E2 | C ne remplace aucune heure à la coupure du 01/07/2026 | 26 compteurs avec une suite longue à la coupure, 50 552 h, dont 17 770 remplacées par C. Modèle d'E2 à brancher |
| Remplissage (B2, zéros, sites nouveaux) | `uv run python -m src.data.fill_counts --snapshot hist-20261117` | non rempli (instantané déjà partagé) | `counts.csv` rempli directement le 19/11/2026 : voir ci-dessous |

### A3 - les 5 manques propres au compteur (examinés le 19/11/2026)

Toutes les autres alertes s'expliquent automatiquement. Ces 5 cas ont été regardés heure par heure dans `counts.csv` (heures de Paris) :

| Compteur | Jour | Ce que montrent les données |
| --- | --- | --- |
| 106 av. Denfert-Rochereau NE-SO (exclu) | 29/10/2023 | aucune mesure du 27/10/2023 00:00 au 31/10/2023 07:00 (105 h) : panne de plusieurs jours |
| 72 bd Voltaire NO-SE | 27/10/2024 | heure répétée de 2 h perdue sur tout le réseau, puis aucune mesure de 4 h à 14 h (11 h) |
| 44 av. des Champs-Élysées SE-NO | 31/03/2024 | aucune mesure du 28/11/2023 au 05/04/2024 08:00 (3 104 h) : arrêt de plusieurs mois |
| Pont des Invalides (couloir bus) N-S | 27/10/2024 | aucune mesure du 26/10/2024 19:00 au 27/10/2024 00:00, puis des zéros mesurés de 1 h à 9 h (sauf 8 h), et aucune mesure de 10 h à 21 h |
| 124 bd MacDonald E-O | 31/03/2024 | aucune mesure du 30/03/2024 au 17/05/2024 09:00 (1 161 h) : arrêt de plusieurs semaines |

**Conclusion :** ce sont des pannes du compteur qui tombent un jour de changement d'heure, pas une erreur de traitement du changement d'heure. Les heures sont déjà marquées `missing` ; rien à corriger. Les cinq alertes de l'historique sont donc toutes expliquées, et l'historique peut être partagé (A1 à A3 faits).

### Remplissage de `counts.csv` (décision de Sabrina, 19/11/2026)

`count` est remplacé directement dans `counts.csv` ; `count_raw` et les drapeaux gardent la trace, et `src/data/original.py` retrouve les valeurs d'origine (vérifié le 19/11/2026 : hors sites réservés, `count`, `is_observed` et `is_scoreable` identiques au fichier de Nihed sur les 3 053 599 lignes). Le manifeste porte un bloc `fill`, et un second remplissage est refusé. L'inventaire (`inventory_quality.csv`) décrit les données d'origine : ne pas relancer `quality.py` sur ce fichier.

- **Sites réservés à E3** (B5, sans cahier des charges, modifiable à la demande d'E3) : 15 compteurs sur 9 sites, tous avec 7 jours d'historique local (cas principal du protocole ; E3 raccourcit lui-même à 3 ou 1 jour, sur les mêmes sites) ; installation au début du support de la première origine d'évaluation (01/07/2026 pour dev, 01/10/2026 pour test, moins 24 h de délai et 7 jours) ; 371 917 heures mesurées cachées avant.
- **J-7** (heures marquées `missing` ou `empty_value`) : 25 500 heures sans mesure en période active ; 18 385 remplies, 7 115 laissées vides (J-7 sans mesure).
- **Année d'avant** (heures marquées `long_zero_run`) : 153 suites, 51 789 h ; 17 965 remplacées (valeur > 0) ; le 0 reste pour 19 170 h (0 un an avant), 139 h (vide) et 14 515 h (inconnu).
- Une valeur remplacée n'est jamais une cible (`is_scoreable` faux).

### B4 - Grèves

Référentiel de Zeineb (`data/reference/greves_transport_idf.csv`, branche `team1-zeineb`, fusionnée le 19/11/2026) joint au contexte (`context.py --greves`, `e1-context/0.3.0`) : une ligne par jour, `is_strike` vrai si les transports en commun d'Île-de-France sont annoncés perturbés, la portée, l'intensité et les réseaux dans `label`. Connu au plus tard 24 h avant (notice du référentiel) : `available_at` = minuit (Paris) du jour - 24 h. Historique : 1 127 jours, dont 33 de grève ; flux : 396 jours, dont 11. Jointure : aucune ligne créée ni perdue, aucune heure sans valeur. Limite (notice) : recensement manuel, peut-être incomplet.

### A6 - Dates de découpage

Rien n'a été convenu pour 3 ans dans le dépôt : `config/project.example.yaml` laisse `train_until`, `validation_until` et `test_start` vides. Les outils suivent le protocole proposé (`doc/PROTOCOLE_EVALUATION.md` §3) : coupure d'apprentissage au 01/07/2026, validation juillet-août, diagnostic septembre, test sur les origines d'octobre 2026. L'historique ajoute seulement de l'apprentissage avant le 16/10/2025. À confirmer avec E4.

Les seuils 1 %, 5 % et 10 % ne sont que des exemples pour la discussion.

**Décision A2 (Sabrina, 18/11/2026) :** pour `hist-20261117`, la règle actuelle est gardée (« au moins une suite de zéros ≥ 24 h » → `robustness`). Raisons : aucune modification de `quality.py` ni nouveau tirage des sites réservés à E3 (consigne B5) ; aucun seuil sur la part de zéros n'est justifié à ce jour ; `robustness` ne retire aucun compteur de l'apprentissage. Limite : avec un historique plus long, un compteur a plus de chances d'avoir une suite, d'où 30 `robustness` au lieu de 17. Une fois l'historique reçu, `zeros_criteria.py` montrera l'effet d'un seuil sur la part de zéros. Décision présentée aux autres équipes après la livraison, et modifiable selon leurs retours.

## Limites et points à confirmer

- R2 : fait (A4, ci-dessus) ; les lignes sans identifiant ne sont pas le total des compteurs, leur nature reste inconnue.
- Sites réservés à E3 (Q6) : l'historique en a moins que le flux (10 / 5 contre 15 / 6). Des sites réservés sur le flux ont des suites de zéros en 2023-2024 et passent en `robustness` sur l'historique, donc ne sont plus éligibles (ex. Porte des Ternes O-E, quai de la Tournelle NO-SE). À présenter à E3 et E4 ; `quality.py` non modifié (B5).
- Dates de découpage sur 3 ans : protocole proposé appliqué, à confirmer avec E4 (A6).
- Contrat de données à mettre à jour (A8) : R1 à R3 remplacent A8 ; Q3, Q8, Q14.
- Livraison (décision de Sabrina, 19/11/2026) : **un seul instantané, `hist-20261117`**. Il contient, à la suite, les deux années d'archives puis exactement la grille de `flux-20261115` (16/10/2025 → 14/11/2026) : il remplace le flux pour les autres équipes. `flux-20261115` n'est pas rempli et n'est plus livré.
- `counts.csv` rempli ne suit plus `doc/CONTRATS.md` §3 sur un point : une heure remplie par J-7 a `is_observed=false` mais un `count` rempli (le contrat dit `count=null`). À signaler dans le message de livraison, et à reprendre dans le contrat version 2 (A8).

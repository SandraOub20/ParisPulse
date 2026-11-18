# E1 - Historique : archives 2023-2025 et instantané `hist-20261117`

- **Date, équipe, responsables :** 18/11/2026, E1. Assemblage et préparation : Nihed (17/11/2026, `src/data/archives.py`, `e1-archives/0.3.0`). Fiche (tâche A5 de la passation) : Sabrina.
- **Question :** peut-on ajouter deux années d'archives avant le flux courant, sur une seule grille, sans rupture entre archives et flux ?
- **Décision de départ :** réunion E1 du 17/11/2026 : ajouter l'historique, d'abord **2 cycles d'un an alignés sur le début du flux** (16/10), et non au 1er janvier.
- **Sources :** jeu Open Data Paris `comptage-velo-historique-donnees-compteurs` (un fichier par année, pièces jointes « par compteur et par heure »), et flux courant `flux-20261115`.
- **Statut des chiffres :** sauf mention contraire, les chiffres de cette fiche viennent de la passation de Nihed du 17/11/2026. **Ils sont à revérifier sur les données** : à la date de cette fiche, `hist-20261117` et les archives brutes n'ont pas encore été reçus par Sabrina (zip à partager par Nihed, tâche A7).

## Les deux instantanés

| Instantané | Période (UTC) | Usage |
| --- | --- | --- |
| `flux-20261115` | 16/10/2025 → 14/11/2026 (13 mois) | Utilisé par les autres équipes, **inchangé** |
| `hist-20261117` | 16/10/2023 → 14/11/2026 (3 ans) | Nouveau, **pas encore partagé** |

## Les archives

| | 2023 | 2024 | 2025 |
| --- | --- | --- | --- |
| Format | zip, UTF-8, `;` | zip, UTF-8, `;` | zip, latin-1, `,` |
| Lignes / identifiants | 860 190 / 101 | 1 505 640 / 179 | 1 502 954 / 172 |
| Dates avec fuseau | oui | oui | oui |
| Doublons / conflits | 0 | 0 | 0 |
| Particularités | colonnes en plus (photos) | une ligne « total » par heure, sans identifiant | idem, et nombres écrits « 1 007 » |

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
| R2 | Lignes sans identifiant (le « total » horaire, 17 542 lignes) écartées et comptées. |
| R3 (option A) | Seuls les 113 compteurs du flux sont gardés ; les 26 anciens compteurs présents seulement dans les archives sont listés dans le manifeste, hors grille. |
| Priorité | Archives avant le 16/10/2025, flux ensuite. |

Pour `hist-…`, `prepare.py` lit le brut et la fenêtre dans le bloc `history` du manifeste, sans écarter de premier jour ; rien ne change pour `flux-…`.

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

## Outils préparés pour l'historique (Sabrina, testés sur `flux-20261115`)

Ces scripts prennent l'instantané en paramètre ; ils sont prêts à être lancés sur `hist-20261117` dès sa réception.

| Tâche | Commande | Sur `flux-20261115` |
| --- | --- | --- |
| A3 - les 431 alertes | `uv run python -m src.data.alerts_review --snapshot hist-20261117` | Retrouve la fiche de Tasnim : 229 alertes = 113 heures perdues au passage à l'heure d'hiver + 108 journées non publiées + 8 pics (4 sens du soir, 2 faibles volumes, 1 panne, 1 à examiner : Pont des Invalides). |
| A2 - critère des zéros | `uv run python -m src.data.zeros_criteria --snapshot hist-20261117` | L'option 1 retrouve exactement l'inventaire (95 / 17 / 1 avant réservation). Avec une part de zéros > 1 %, 5 % ou 10 % au lieu d'« au moins une suite » : 15, 9 ou 8 `robustness`. |
| B1 - mêmes dates un an avant | `uv run python -m src.data.zeros_years --snapshot hist-20261117 --annees 1 2` | 17 suites ; 1 seule comparable un an avant (13 mois de données), sans zéros aux mêmes dates. |
| B2 - remplacement J-7 | `uv run python -m src.data.fill_j7 --snapshot hist-20261117` | 13 589 heures remplacées directement dans `count` (`count_raw` reste vide), 2 116 laissées vides. |
| B7 - étude A/B des zéros | `uv run python -m src.data.zeros_experiment --snapshot hist-20261117 --coupure … --debut … --fin …` | Dates de découpage sur 3 ans à fixer (A6) ; modèle d'E2 à brancher. |

Les seuils 1 %, 5 % et 10 % ne sont que des exemples pour la discussion.

**Décision A2 (Sabrina, 18/11/2026) :** pour `hist-20261117`, la règle actuelle est gardée (« au moins une suite de zéros ≥ 24 h » → `robustness`). Raisons : aucune modification de `quality.py` ni nouveau tirage des sites réservés à E3 (consigne B5) ; aucun seuil sur la part de zéros n'est justifié à ce jour ; `robustness` ne retire aucun compteur de l'apprentissage. Limite : avec un historique plus long, un compteur a plus de chances d'avoir une suite, d'où 30 `robustness` au lieu de 17. Une fois l'historique reçu, `zeros_criteria.py` montrera l'effet d'un seuil sur la part de zéros. Décision présentée aux autres équipes après la livraison, et modifiable selon leurs retours.

## Limites et points à confirmer

- Tous les chiffres de l'historique sont à revérifier sur les données, dès réception du zip.
- R2 : vérifier que les lignes sans identifiant sont bien le total des compteurs à la même heure (tâche A4, archives brutes nécessaires).
- Les 431 alertes ne sont pas encore examinées (A3) : l'historique ne doit pas être partagé avant A1 à A3.
- Le tirage des sites réservés à E3 change entre les deux instantanés (10 / 5 contre 15 / 6) : à voir avec E3 (Q6), sans modifier `quality.py` d'ici là (B5).
- Dates de découpage sur 3 ans (`train_until`, `validation_until`, `test_start`) : à fixer par Nihed avec E4 (A6).
- Contrat de données à mettre à jour (A8, Nihed) : R1 à R3 remplacent A8 ; Q3, Q8, Q14.

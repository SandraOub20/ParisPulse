# EXP-E1-02 - Inventaire du réseau et choix de l'échantillon

- **Date, équipe, responsables et partenaires :** 13/11/2026, E1, Zeineb (inventaire et sélection) ; partenaire principal E4 (protocole, sites réservés), E3 (sites nouveaux), E2 (sites connus), E5 (carte et couverture). Données d'entrée : extraction de Tasnim (`acquire.py`, `prepare.py`).
- **Question et hypothèse :** quel réseau observe-t-on dans le flux courant, et quels compteurs peut-on utiliser, avec quel rôle ? Hypothèse de travail : une partie des compteurs a un historique court, des manques ou de longues suites de zéros. On les garde visibles, on les écarte de l'apprentissage seulement quand la série ne permet pas de construire un cas, et on met de côté des sites entiers pour E3.
- **Références :** `doc/CONTRATS.md` §2 (inventaire), `doc/PROTOCOLE_EVALUATION.md` §3-4 (séparations temporelles et spatiales), sujet p. 3 (« Étudier le réseau avant de choisir les compteurs »).
- **Instantané, protocole, code et paramètres :** `src/data/quality.py` (`e1-quality/0.1.0`), instantané `flux-AAAAMMJJ` (à renseigner au premier calcul), protocole **proposé, non validé**.

## Ce que produit le module

`uv run python -m src.data.quality --snapshot <snapshot_id> --figures` lit `counts.csv` et `counters.csv` de `data/processed/<snapshot_id>/` et écrit :

| Fichier | Contenu | Consommateurs |
| --- | --- | --- |
| `inventory_quality.csv` | Une ligne par compteur et par période (`period_role`). Les 12 colonnes du gabarit viennent en premier, puis : site et groupe, coordonnées, zone, bornes observées, taux de manque, suites de zéros, jours de changement d'heure incomplets, volumes, profil, alias possibles, incertitudes | E2, E3, E4, E5 |
| `selection_summary.json` | Critères, effectifs par statut, listes `site_groups.train / dev_new / test_new` à recopier dans `config/project.yaml`, diversité des profils par statut | E3, E4 |
| `figures/inventory_*.png` | Histogrammes (volume, historique, manques, zéros) et carte des statuts | rapport, présentation |

Les sorties sont aussi ajoutées au manifeste de l'instantané, avec leurs SHA-256.

## Période utilisée pour décider : avant le test seulement

Le protocole réserve les origines d'octobre 2026 au test final. Les statuts sont donc calculés **uniquement sur la période allant du début de l'instantané au 01/10/2026 00:00 heure de Paris** (`--fin-selection`, ou `protocol.test_start` s'il est renseigné). La période complète (`full_snapshot`) est mesurée elle aussi, mais seulement pour **décrire** le réseau : le statut y est recopié depuis la période de sélection, jamais recalculé. Un test automatique le vérifie : si on modifie toutes les heures postérieures à la fin de sélection, aucun statut ne change.

## Mesures par compteur

Toutes les mesures portent sur une **grille horaire UTC commune** à tous les compteurs. Une heure de la grille absente de `counts.csv` compte comme manquante. Ainsi, un compteur installé tard a un historique court, ce qui se voit.

| Mesure | Définition | Remarque |
| --- | --- | --- |
| `n_expected`, `n_observed`, `n_missing` | heures de la grille, heures avec mesure, différence | `missing_rate` = `n_missing / n_expected` |
| `missing_rate_in_span` | manques entre la première et la dernière mesure | distingue « installé tard » et « en panne par moments » |
| `n_scoreable`, `n_invalid` | règle structurelle de `prepare` (conflit, négatif, valeur illisible) | |
| `n_zeros`, `longest_zero_run`, `n_long_zero_runs`, `long_zero_share` | zéros observés, plus longue suite, suites ≥ 24 h, part des heures observées dans ces suites | **les zéros restent des zéros** ; une heure absente interrompt la suite |
| `n_dst_days_incomplete` | jours de 23 ou 25 h locales avec moins d'heures observées qu'attendu | signalés, jamais supprimés (même choix que `prepare`) |
| `mean/median/p95/max_count` | sur les heures évaluables | `volume_class` = tertiles faible / moyen / fort |
| `weekday_weekend_ratio`, `commute_peak_ratio` | moyenne semaine / week-end ; pointe 7-9 h et 17-19 h locales / moyenne semaine | `profile_type` pendulaire / mixte / loisirs, **descriptif seulement** |
| `dist_center_km`, `zone` | distance à l'Hôtel de Ville : centre < 2,5 km ≤ intermédiaire < 5 km ≤ périphérie | `inconnue` sans coordonnées |

## Critères de sélection (fixés avant le test)

Les seuils sont regroupés dans `SelectionCriteria`. Ils peuvent être remplacés par une section `quality:` de `config/project.yaml`, ce qui laisse une trace versionnée.

| Statut | Règle | Justification |
| --- | --- | --- |
| `excluded` | aucune heure évaluable, **ou** < 28 jours observés, **ou** > 50 % de manques en fonctionnement, **ou** > 50 % des heures observées dans des suites de zéros ≥ 24 h | Moins de 4 semaines : pas de référence hebdomadaire stable, et pas de support de 7 jours suivi d'une cible avec un historique d'apprentissage. Au-delà de 50 % de manques ou de zéros prolongés, la série ne décrit plus la fréquentation. Le compteur reste dans l'inventaire et sur la carte, avec sa raison |
| `robustness` | < 180 jours observés, **ou** > 10 % de manques, **ou** au moins une suite de zéros ≥ 24 h, **ou** moyenne < 5 passages/h, **ou** série arrêtée plus de 7 jours avant la fin de la période | Ce sont les situations « moins favorables » que demande le sujet. Le compteur est un site connu, évalué **à part** par E2/E4. Il ne contamine pas le score principal et ne disparaît pas |
| `retained` | tous les critères satisfaits | site connu `S_train` pour E2 |
| `reserved_dev_new` / `reserved_test_new` | tiré parmi les groupes dont **tous** les compteurs sont `retained` | sites nouveaux `S_dev_new` / `S_test_new` pour E3, hors de l'apprentissage initial |

Plusieurs raisons peuvent être cumulées dans `status_reason`. Les zéros prolongés **ne sont pas transformés en manques** : ils sont comptés, signalés et motivent un statut. Les fichiers ne permettent pas d'en établir la cause.

## Sites réservés pour E3

1. **Groupes candidats.** On part de `site_group_id` (égal à `site_id` par défaut, à vérifier). On réunit ensuite les groupes situés à moins de 50 m l'un de l'autre. Le contrat demande de ne pas répartir entre donneurs et réservés des séries qui pourraient être identiques. Un nom identique ne suffit pas à raccorder deux séries ; la proximité ne le prouve pas non plus. Ces regroupements sont donc signalés comme incertitude (`alias_candidates`) et tranchés avec E3/E4.
2. **Éligibilité.** Seuls les groupes dont toutes les directions sont `retained` peuvent être réservés. Cela évite de confondre la question « généraliser à un nouveau site » avec un problème de qualité.
3. **Effectifs.** 15 % des groupes éligibles en `test_new` et 10 % en `dev_new`, au moins 2 chacun. Au moins la moitié des groupes éligibles reste en apprentissage.
4. **Diversité.** Les groupes sont classés par strate (volume × zone). On les tire tour à tour dans chaque strate, dans un ordre fixé par un hachage SHA-256 et une graine (`parispulse-e1`). Le tirage est **reproductible** et ne dépend d'aucun score de modèle.
5. **Toutes les directions d'un site** reçoivent le même rôle (vérifié par test).

## Contrôles réalisés

Ils sont dans `tests/test_data_quality.py`, sur un réseau synthétique :

- colonnes du gabarit en tête, deux périodes par compteur ;
- comptes attendus / observés / manquants sur la grille, y compris pour un compteur installé tard ;
- une suite de 72 h de zéros est mesurée (72 h, 1 suite) **sans** créer de manques ;
- statuts et raisons : série morte et historique de 20 jours exclus, 30 % de manques et suite de zéros en robustesse, compteur sans coordonnées conservé ;
- directions d'un même site et alias possibles gardés ensemble ; aucun groupe à la fois en apprentissage et réservé ;
- tirage identique d'une exécution à l'autre ;
- **aucun statut ne change quand on modifie le futur** après la fin de sélection ;
- clé `(counter_id, timestamp)` dupliquée refusée ;
- jour de passage à l'heure d'hiver (25 h) avec une heure absente signalé comme incomplet.

## Résultats mesurés

*À renseigner après la première exécution sur l'extraction complète de Tasnim.* À compléter : nombre de compteurs et de sites inventoriés ; nombre de compteurs `retained`, `robustness`, `excluded` (et principales raisons) et réservés ; diversité par volume, zone et profil ; groupes à alias possible ; figures.

## Analyse, limites et décision

- Les critères sont des choix raisonnés. Ils ne sont pas optimisés : ils ont été fixés avant tout score de modèle. Une analyse de sensibilité (par exemple le seuil de 180 jours) peut se faire avec E4 **sur la période de sélection uniquement**.
- `site_group_id = site_id` par défaut : le regroupement physique n'est pas vérifié. Les alias sont seulement candidats.
- La direction n'est pas validée (`prepare` la laisse vide). Elle ne sert donc pas encore à la sélection.
- Les jours fériés et les vacances scolaires ne sont pas pris en compte dans le profil. `context.py` (membre 3) pourra raffiner `profile_type`.
- Le flux couvre 13 mois glissants. Le seuil de 180 jours suppose que l'instantané commence vers octobre 2025, comme prévu au protocole.
- Le protocole n'est **pas encore validé** par le professeur. Les listes de sites deviennent définitives seulement après cette validation, et avant toute comparaison de modèles.

## Lien vers les données et retours des partenaires

- Données : `data/processed/<snapshot_id>/inventory_quality.csv`, `selection_summary.json`, `figures/`.
- Retour d'E4 sur les critères et les sites réservés : *à renseigner*.
- Preuve d'usage par E3 (sites réservés repris dans `config/project.yaml`) et par E5 (statuts affichés sur la carte) : *à renseigner*.

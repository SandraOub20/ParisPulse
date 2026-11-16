# EXP-E1-02 - Inventaire du réseau et choix de l'échantillon

- **Date, équipe, responsables et partenaires :** 13/11/2026, E1, Zeineb (inventaire et sélection) ; partenaire principal E4 (protocole, sites réservés), E3 (sites nouveaux), E2 (sites connus), E5 (carte et couverture). Données d'entrée : extraction de Tasnim (`acquire.py`, `prepare.py`).
- **Question et hypothèse :** quel réseau observe-t-on dans le flux courant, et quels compteurs peut-on utiliser, avec quel rôle ? Hypothèse de travail : une partie des compteurs a un historique court, des manques ou de longues suites de zéros. On les garde visibles, on les écarte de l'apprentissage seulement quand la série ne permet pas de construire un cas, et on met de côté des sites entiers pour E3.
- **Références :** `doc/CONTRATS.md` §2 (inventaire), `doc/PROTOCOLE_EVALUATION.md` §3-4 (séparations temporelles et spatiales), sujet p. 3 (« Étudier le réseau avant de choisir les compteurs »).
- **Instantané, protocole, code et paramètres :** `src/data/quality.py` (`e1-quality/0.1.0`), protocole **proposé, non validé**. Instantané de référence de l'équipe : **`flux-20261115`** :
  - export CSV complet du flux courant, préparé avec la boucle `uv run python -m src.data.acquire --tout` (grille commune, `e1-prepare/0.2.0`, branche `team1-nihed`) ;
  - colonnes `id_compteur, nom_compteur, id, name, sum_counts, date, installation_date, coordinates`, `timezone=UTC` ;
  - nombre de lignes et SHA-256 du brut : dans `data/manifests/flux-20261115.json` (`files[role=raw]`).

  Il remplace l'instantané provisoire `flux-20261114`, qui avait été normalisé compteur par compteur avant la livraison de la boucle. **Les effectifs par statut sont identiques** : 74 `retained` / 17 `robustness` / 15 `reserved_test_new` / 6 `reserved_dev_new` / 1 `excluded`. Les listes de sites réservés sont elles aussi identiques.

  **Contrôle de reproductibilité (16/11/2026, Zeineb)** : la chaîne complète a été relancée sur une copie neuve, en partant de zéro : `acquire --tout`, puis `quality --figures`. L'instantané obtenu, `flux-20261116`, a été récupéré le 16/11/2026 à 13:59 UTC : 1 034 677 lignes, SHA-256 `5194759a…fb3260`, grille du 16/10/2025 au 15/11/2026 (9 503 h). Il redonne les mêmes effectifs, les mêmes 58 groupes et les mêmes listes `train / dev_new / test_new`. La fenêtre a pourtant glissé de deux jours.

## Ce que produit le module

`uv run python -m src.data.quality --snapshot <snapshot_id> --figures` lit `counts.csv` et `counters.csv` de `data/processed/<snapshot_id>/` et écrit :

| Fichier | Contenu | Consommateurs |
| --- | --- | --- |
| `inventory_quality.csv` | Une ligne par compteur et par période (`period_role`). Les 12 colonnes du gabarit viennent en premier, puis : site et groupe, coordonnées, zone, bornes observées, taux de manque, suites de zéros, jours de changement d'heure incomplets, volumes, profil, alias possibles, incertitudes | E2, E3, E4, E5 |
| `selection_summary.json` | Critères, effectifs par statut, listes `site_groups.train / dev_new / test_new` à recopier dans `config/project.yaml`, diversité des profils par statut, trous communs au réseau (`network_gaps`) | E3, E4, E5 |
| `counters.csv` (colonne `site_group_id`) | **58 groupes de sites candidats** désormais écrits pour les 113 compteurs. `prepare.py --tout` les écrit dès la préparation (même règle, `quality.candidate_site_groups`). `quality.py` les recalcule et ne réécrit le fichier que s'ils diffèrent (« déjà à jour » sur `flux-20261116`). Aucune autre colonne ne change. Ajouté le 15/11/2026 (étape 3 des décisions E1, fait par Nihed pour Zeineb) | Toutes |
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

1. **Groupes candidats.** On part de `site_id`, jamais d'un `site_group_id` déjà réécrit : relancer le script donne donc exactement le même résultat. On réunit ensuite les sites situés à moins de **100 m** l'un de l'autre ; l'identifiant du groupe est le plus petit `site_id` qu'il contient. Ce groupe est écrit dans `site_group_id` de `counters.csv`, d'`inventory_quality.csv` et dans les listes de `selection_summary.json` : toutes les équipes lisent ainsi le même regroupement. Le contrat demande de ne pas répartir entre donneurs et réservés des séries qui pourraient être identiques. Un nom identique ne suffit pas à raccorder deux séries ; la proximité ne le prouve pas non plus. Ces regroupements sont donc signalés comme incertitude (`alias_candidates`) et tranchés avec E3/E4. Le seuil était d'abord de 50 m ; il a été corrigé après contrôle, voir « Évolution de la décision ».
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
- `site_group_id` de `counters.csv` = groupe candidat (alias et deux sens réunis), aucune autre colonne modifiée ;
- relancer après la réécriture de `counters.csv` ne change plus aucun fichier (mêmes octets).
- **aucun statut ne change quand on modifie le futur** après la fin de sélection ;
- clé `(counter_id, timestamp)` dupliquée refusée ;
- jour de passage à l'heure d'hiver (25 h) avec une heure absente signalé comme incomplet.

Après passage sur données réelles, deux tests ont été ajoutés (13), puis deux autres le 15/11 pour l'écriture des groupes (15 au total) : deux sens à 80 m restent ensemble, et un trou commun au réseau est détecté. Sur l'instantané réel, on a aussi vérifié qu'aucun groupe utilisé n'a deux rôles et qu'aucun site réservé n'a de site d'apprentissage à moins de **164 m**.

## Résultats mesurés (`flux-20261115`, période de sélection jusqu'au 30/09/2026)

Les chiffres ci-dessous ont été mesurés d'abord sur `flux-20261114` (fenêtre ouverte le 14/10/2025), puis contrôlés sur `flux-20261116` (fenêtre ouverte le 16/10/2025). Ils sont stables à l'unité près. Seuls changent les nombres qui dépendent du bord de la fenêtre : compteurs à plus de 340 jours d'historique (102, puis 108) et historique de la rue d'Aubervilliers (128 j, puis 126 j). Les statuts, les groupes et les rôles ne changent pas.

### Le réseau

- **113 compteurs** répartis sur **82 `site_id`**. Tous ont des coordonnées.
- **Historique** : médiane de 349 jours observés ; 102 compteurs ont plus de 340 jours.
- **Manques en fonctionnement** : médiane 0,6 %, maximum 8,7 %. Environ 53 heures sont absentes pour presque tous les compteurs à la fois (voir les trous communs ci-dessous).
- **Volumes** : médiane de 62 passages/h, de 0 à 393. Tertiles à 50 et 75 passages/h.
- **Profils** : 87 compteurs pendulaires, 23 mixtes, 2 loisirs, 1 indéterminé. Ratio semaine / week-end médian 1,52, pointe / journée médian 2,01.
- **Jours de changement d'heure** : les 113 compteurs ont un jour incomplet sur la période de sélection, le 26/10/2025. Il y manque une des deux heures 02:00 (l'heure répétée). C'est un manque **à la source**, signalé et non corrigé, comme dans `prepare`.

### Statuts

| Statut | Compteurs | Groupes candidats (`site_id`) |
| --- | --- | --- |
| `retained` (S_train) | 74 | 47 groupes `S_train` (68 `site_id`), robustesse comprise |
| `robustness` (S_train, évalué à part) | 17 | |
| `reserved_test_new` (S_test_new) | 15 | 7 (9) |
| `reserved_dev_new` (S_dev_new) | 6 | 4 (4) |
| `excluded` | 1 | 1 (le groupe de Denfert-Rochereau, dont l'autre sens est en `S_train`) |

Au total, **58 groupes** : 47 + 7 + 4 = 58, puisque le groupe de l'exclu est aussi un groupe `S_train`. Les versions précédentes de cette fiche donnaient « 68 » et « 9 » : ce sont des nombres de `site_id`, comptés avant que les groupes candidats soient écrits partout.

- **Exclu** : 106 avenue Denfert-Rochereau NE-SO. 100 % des heures sont dans une suite de zéros (5 973 h). L'autre sens du même lieu est gardé.
- **Robustesse, 17 compteurs** :
  - 10 avec au moins une suite de zéros ≥ 24 h. Les plus longues : boulevard Jourdan E-O (3 613 h), boulevard Masséna SO-NE (587 h), Porte de Bagnolet (356-357 h, **les deux sens en même temps**), Batignolles (117-120 h, les deux sens), Ménilmontant et Cours la Reine (88 h) ;
  - 4 séries interrompues : rue d'Aubervilliers, arrêtée en février 2026 avec 128 jours d'historique, et quai François Mauriac, arrêté 87 jours avant la fin ;
  - 3 à faible volume (< 5 passages/h) : boulevard Diderot E-O et porte de Charenton, dans les deux sens.

  Que des zéros apparaissent dans les deux sens au même moment fait penser à une panne de capteur, mais les fichiers ne permettent pas de l'établir.
- **Sites réservés à E3** :
  - test : Porte des Ternes, boulevard du Montparnasse, Pont Charles-de-Gaulle + Totem quai d'Austerlitz (regroupés car à 64 m), quai de Grenelle, quai de la Tournelle, boulevard Kellermann, boulevard Poniatowski ;
  - dev : quai des Tuileries, quai d'Issy, boulevard Davout, boulevard Victor.

  Les trois classes de volume et les trois zones sont représentées. Les sites réservés sont tous pendulaires ou mixtes, comme 97 % du réseau.

### Un `site_id` n'est pas un lieu

21 groupes candidats réunissent plusieurs `site_id`. Dans presque tous les cas, ce sont **les deux sens d'un même lieu publiés sous deux `site_id`**, par exemple « 89 bd de Magenta NO-SE » et « 102 bd de Magenta SE-NO », ou « Pont National SO-NE » et « Pont National NE-SO ». Séparer les sites par `site_id`, comme le ferait le réglage par défaut `site_group_id = site_id`, aurait mis un sens en apprentissage et l'autre en test E3.

### Contrôle à la main : Pont National (critère « Fini quand »)

Critère : les deux sens ont le même `site_group_id` et des directions opposées. Commande :

```bash
uv run python -c "import pandas as pd;k=pd.read_csv('data/processed/flux-20261116/counters.csv',dtype=str);print(k[k.counter_name.str.contains('National')][['counter_id','counter_name','site_id','site_group_id','direction']])"
```

| `counter_id` | Nom | `site_id` | `site_group_id` | `direction` | Statut |
| --- | --- | --- | --- | --- | --- |
| 100047541-353326452 | Pont National SO-NE | 100047541 | **100047541** | SO-NE | `retained` |
| 100047549-101047549 | Pont National NE-SO | 100047549 | **100047541** | NE-SO | `retained` |

**Validé** : il y a deux `site_id` distants d'environ 57 m, un seul groupe, des sens opposés et le même rôle (`S_train`). Avec l'ancien seuil de 50 m, ces deux sens étaient séparés (voir « Évolution de la décision »). Le contrôle automatique de `prepare` le confirme sur tout le réseau : `direction_checks.sites_not_opposite = []` (31 sites à plusieurs compteurs). Sur `flux-20261116`, on a aussi revérifié qu'aucun groupe n'a deux rôles et qu'aucun site réservé n'a de site d'apprentissage à moins de 164 m.

### Trous communs au réseau (≥ 90 % des compteurs actifs sans mesure)

**Changement de définition (15/11/2026)** : dans `network_gaps`, un compteur est désormais « actif » à une heure seulement si cette heure est **entre sa première et sa dernière mesure**. Avant, il suffisait qu'il ait une ligne dans `counts.csv`. Ce changement est nécessaire avec la grille commune de `prepare --tout`, où tout compteur a une ligne à toutes les heures, même avant son installation ou après son arrêt. Sans lui, ces heures auraient été comptées comme des manques du réseau. **Les trous trouvés restent les mêmes** (`flux-20261115` et `flux-20261116`), à l'exception du bord de la fenêtre glissante, qui suit la date de l'instantané.

| Début (heure de Paris) | Durée | Période |
| --- | --- | --- |
| premier jour de la fenêtre glissante (14/10/2025 sur `-20261114`, 16/10/2025 sur `-20261116`), plusieurs heures | 8 à 12 h au total | début de la fenêtre glissante |
| 26/10/2025 02:00 | 1 h | heure répétée du passage à l'heure d'hiver |
| 02/07/2026 et 06/07/2026 00:00 | 2 h + 2 h | validation |
| 22/08/2026 | 24 h | validation |
| 23/09/2026 | 24 h | diagnostic |
| 04/10/2026 | 24 h | **test** |
| 25/10/2026 (jour de 25 h) | 25 h | **test** |

Ces journées n'ont aucune cible évaluable. Pour E4, les cas qui partent de ces dates sont sans observation : il faut les compter, pas les supprimer en silence. Pour E5, il faut un message du type « donnée absente pour tout le réseau ». Ces journées sont listées dans `selection_summary.json` (`network_gaps`).

## Évolution de la décision : seuil d'alias de 50 m à 100 m

Le premier calcul utilisait 50 m. Le contrôle des distances entre sites (au plus proche voisin) a montré que **Pont National SO-NE** (tiré en test E3) et **Pont National NE-SO** (en apprentissage) étaient à 57 m. De même, les deux sens du boulevard Richard-Lenoir étaient à 65 m, l'un en dev E3 et l'autre en apprentissage. C'était précisément la fuite que le regroupement devait empêcher.

Dans la distribution des distances, les paires « même lieu, deux sens » vont de 0 à 93 m. La paire suivante est à 113 m (Pont des Invalides / quai d'Orsay), déjà regroupée par chaînage. Le seuil de 100 m tombe dans ce creux. Il réunit aussi quelques lieux voisins mais distincts : Pont Charles-de-Gaulle et Totem d'Austerlitz, quai de la Marne et quai de l'Oise, boulevard Voltaire et boulevard Richard-Lenoir. C'est l'erreur la moins grave : deux lieux voisins ont des flux corrélés, et les garder ensemble évite aussi d'évaluer E3 sur un voisin immédiat d'un site d'apprentissage.

Cette correction s'appuie **uniquement sur les coordonnées et les noms**, jamais sur les données du test ni sur un score de modèle. Le tirage des sites réservés a été refait avec le nouveau seuil, avant toute expérience de prévision.

## Analyse, limites et décision

- Les critères sont des choix raisonnés. Ils ne sont pas optimisés : ils ont été fixés avant tout score de modèle. Une analyse de sensibilité (par exemple le seuil de 180 jours) peut se faire avec E4 **sur la période de sélection uniquement**.
- `site_group_id` est un groupe **candidat** : déduit de la distance (100 m), non vérifié sur place. La règle est notée dans le manifeste (`quality.site_group_rule`, `site_groups.rule`). `prepare.py --tout` écrit déjà les groupes. Seule la préparation compteur par compteur remet `site_group_id = site_id` : dans ce cas, il faut relancer `quality.py`.
- La direction est tirée de la fin du nom (par exemple « SO-NE »), sans vérification sur place. Elle est renseignée pour 113 compteurs sur 113, et les sens d'un même site sont tous opposés. Elle ne sert pas aux critères de sélection.
- Les jours fériés et les vacances scolaires ne sont pas pris en compte dans le profil. `context.py` (membre 3) pourra raffiner `profile_type`.
- Le flux couvre 13 mois glissants. Le seuil de 180 jours suppose que l'instantané commence vers octobre 2025, comme prévu au protocole.
- Le protocole n'est **pas encore validé** par le professeur. Les listes de sites deviennent définitives seulement après cette validation, et avant toute comparaison de modèles. Elles ne sont pas encore recopiées dans `config/project.yaml`, qui relève d'E4.
- Le boulevard Jourdan E-O a 46 % de ses heures dans des suites de zéros, juste sous le seuil d'exclusion de 50 % : il est classé en robustesse. Ce cas limite est à examiner avec E2 (garder ou écarter la période de zéros en apprentissage, travail du membre 4).
- La fenêtre glissante commence vers mi-octobre 2025 (le 14/10 pour `-20261114`, le 16/10 pour `-20261116`). Le seuil de 180 jours ne concerne en pratique que les séries arrêtées tôt.
- Le premier jour de l'instantané est incomplet pour tout le réseau : c'est un effet du bord de la fenêtre glissante, pas une panne.

### Décision à défendre : des critères fixés avant le test

1. **Période** : tous les statuts sont calculés sur la seule période de sélection, du début de l'instantané au 01/10/2026 00:00, heure de Paris. Les origines d'octobre 2026, réservées au test final, ne sont pas lues pour décider.
2. **Preuve** : le test `tests/test_data_quality.py` modifie toutes les heures postérieures à la fin de sélection et vérifie qu'aucun statut ne change. La période complète sert seulement à décrire, et le statut y est recopié.
3. **Aucun score de modèle** : les seuils (28 j, 180 j, 10 %, 50 %, 5 passages/h, 24 h de zéros, 100 m) et le tirage (SHA-256, graine `parispulse-e1`) ont été fixés avant toute prévision. La seule révision, de 50 m à 100 m, repose sur les coordonnées et les noms. Elle a été faite avant toute expérience de prévision.
4. **Stabilité** : deux instantanés différents (`-20261115` et `-20261116`) donnent les mêmes statuts et les mêmes listes. Le choix ne dépend donc pas du jour d'extraction.
5. **Rien ne disparaît** : l'exclu et les 17 compteurs de robustesse restent dans l'inventaire et sur la carte, avec leur raison.

## Lien vers les données et retours des partenaires

- Données : `data/processed/<snapshot_id>/inventory_quality.csv`, `selection_summary.json`, `figures/`.
- Retour d'E4 sur les critères, la date de test (01/10/2026) et les sites réservés : **demandé (point 1 du message à E4), en attente**. Dès qu'E4 valide, Zeineb lui transmet `site_groups.train / dev_new / test_new` de `selection_summary.json` pour `config/project.yaml` (`protocol.site_groups`), fichier qui relève d'E4. Listes actuelles :
  - `dev_new` : `100056035, 100056331, 300030163, 300030922` ;
  - `test_new` : `100047534, 100049407, 100056329, 100056330, 100056336, 300030139, 300030250` ;
  - `train` : les 47 autres groupes (liste complète dans `selection_summary.json`).
- Preuve d'usage par E3 (sites réservés repris dans `config/project.yaml`) et par E5 (statuts affichés sur la carte) : *à renseigner*.

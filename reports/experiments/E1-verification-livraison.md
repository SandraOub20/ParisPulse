# EXP-E1-05 - Vérification de la livraison `hist-20261117`, côté consommateur

- **Date, équipe, responsables et partenaires :** 24/11/2026, E1, Tasnim. Données livrées le 19/11/2026 par Sabrina (remplissage, sites nouveaux, grèves, livraison) à partir de l'assemblage de Nihed (archives, contexte) et de l'inventaire de Zeineb. Destinataires : E2, E3, E4, E5.
- **Question :** chaque affirmation du message de livraison (`livraison/README.md`) se vérifie-t-elle sur les fichiers du zip seuls, sans relire le code qui les a produits ?
- **Références :** `doc/CONTRATS.md` §3 (comptages) et §10 (acceptation d'une livraison : « le consommateur contrôle clés, heures et un cas difficile ») ; `doc/PROTOCOLE_EVALUATION.md` §3 ; [E1-historique.md](E1-historique.md).
- **Instantané, code et paramètres :** `hist-20261117` récupéré avec la procédure du message (branche `Team1`, commit `61ff322`, `git lfs pull`, `unzip`). Script indépendant `src/data/verify_delivery.py` : il ne réutilise pas les fonctions de remplissage et recalcule J-7 et l'année d'avant à partir des données livrées. 140 tests du dépôt verts.
- **Commande :** `uv run python -m src.data.verify_delivery` (à la racine, après l'`unzip`), environ 2 min.

## Résultat : 47 contrôles conformes, 5 écarts, dont un seul à traiter

### Ce qui est conforme au message

| Affirmation | Vérifié sur les données |
| --- | --- |
| 113 compteurs, 16/10/2023 00:00 → 14/11/2026 22:00 UTC, 27 023 h, 3 053 599 lignes | oui : grille complète (113 × 27 023), sans doublon, pas horaire régulier, `interval_end` = début + 1 h |
| Heures en UTC | oui : toutes les heures sont en `+00:00` |
| Archives puis flux, sans coupure | oui : au moins 98 compteurs mesurés à chaque heure du 14 au 19/10/2025. Sur la partie flux, `count_raw` est identique à `flux-20261115` (voir l'écart 5) |
| 18 385 h remplies par J-7 | oui : toutes marquées `missing` ou `empty_value`, avec `count_raw` vide et `is_observed = is_scoreable = false`. Chaque valeur égale la mesure d'origine de la même heure de Paris 7 jours avant |
| 17 965 h remplacées par l'année d'avant | oui : toutes marquées `long_zero_run`, avec `count_raw = 0`. Chaque valeur égale le `count` du même compteur aux mêmes date et heure de Paris un an avant |
| « Sinon, le 0 reste » | oui : 33 824 h de suites longues gardent 0 et restent des cibles |
| 36 350 valeurs remplacées, jamais `is_scoreable` | oui |
| `is_scoreable = true` = vraies mesures seulement, zéros compris | oui : équivalent exact à « observée et `count = count_raw` » ; 92 931 zéros mesurés évaluables |
| 104 heures `network_gap` | oui, jamais posé sur une heure mesurée |
| Statuts 67 / 30 / 5 (4 sites) / 10 (5 sites) / 1 | oui ; le compteur exclu est 106 av. Denfert-Rochereau NE-SO |
| Sites réservés : historique vidé, installation au 23/06 et au 23/09 | oui : avant l'installation, `count` et `count_raw` sont vides et `is_observed` faux. `installation_date` est renseignée dans `counters.csv` |
| Contexte : une ligne par jour, nom dans `label` | oui : 35 jours fériés, 395 jours de vacances (zone C) et 33 jours de grève, tous avec un `label` |
| `available_at` | oui : vide pour les fériés et les vacances ; minuit (Paris) − 24 h pour les grèves ; `valid_time` + 24 h pour la météo observée. Météo prévue : `available_at` = `valid_time` − 42 h (J-2) |
| Contrat §3 | oui : le contrat actuel dit bien `count = null` pour une heure insérée ; l'écart est annoncé |
| Dates du protocole | oui : identiques à `doc/PROTOCOLE_EVALUATION.md` §3 (proposé, non validé) |
| Empreintes SHA-256 | oui pour les 10 fichiers du zip (dont `counts.csv`, `context.csv`, `fill_report.json`) |

### Les 5 écarts

| # | Écart | Gravité | Explication |
| --- | --- | --- | --- |
| 1 | **Sites de test : 6 jours de mesures à la première origine (01/10/2026), pas 7** | **à traiter** | Le 23/09/2026, jour de l'installation fictive, est un trou réseau de 24 h : rien n'est publié sur tout le réseau. Les 10 compteurs `reserved_test_new` ont leur première mesure le 24/09 00:00 (Paris), soit 144 h mesurées dans le support de 168 h. J-7 ne comble pas ce jour, qui est avant leur première mesure. Les 5 compteurs dev ont bien 168 h |
| 2 | Empreinte de `data/reference/greves_transport_idf.csv` et de `…_sources.csv` différente du manifeste | mineure | Le contenu est identique. Le manifeste a été calculé sur une copie aux fins de ligne Windows (CRLF), alors que Git fournit des fins LF : avec CRLF, on retrouve exactement l'empreinte. Sur macOS ou Linux, le contrôle d'empreinte échoue donc à tort |
| 3 | Calendrier : 1 127 jours pour 1 126 dates de Paris dans la grille | aucune | Le jour en plus est le 15/11/2026, date de fin de la dernière heure. La jointure se fait sur la date de début de l'heure : ce jour n'est jamais joint |
| 4 | Contrôle J-7 de mon premier passage | aucune (erreur de ma part) | J-7 lit les valeurs d'origine. Dans 201 heures, la J-7 était un zéro remplacé ensuite par l'année d'avant : l'heure remplie garde ce 0, conformément à la règle. Contrôle corrigé dans le script |
| 5 | 2 328 différences avec `flux-20261115`, toutes le 15/10/2025 | aucune | Ma copie locale de `flux-20261115` est l'ancienne version (`e1-prepare/0.2.0`), qui commence le 15/10/2025, jour rogné par la source. `hist-20261117` prend ce jour dans les archives. Hors de ce jour, aucune différence (931 294 lignes communes en tout) |

## Ce que les équipes doivent savoir en plus du message

- **`count` peut encore être vide.**
  - 7 115 h en période active n'ont pas de valeur, parce que la J-7 n'était pas mesurée ;
  - 450 365 h tombent hors de la période active (avant l'installation ou après l'arrêt du compteur) ;
  - un modèle doit donc accepter des entrées vides.
- **Journées entières sans aucune cible**, sur tout le réseau : 22/08 (validation), 23/09 (diagnostic), 04/10 et 25/10/2026 (test). S'y ajoute une heure perdue à chaque passage à l'heure d'hiver. 10 603 des 10 909 lignes `network_gap` ont un `count` rempli par J-7, mais ce sont des entrées, jamais des cibles.
- **Le remplacement par l'année d'avant utilise un drapeau rétrospectif.** `long_zero_run` demande d'avoir vu les 24 h de la suite. À une origine située au début d'une suite, les heures déjà remplacées n'étaient donc pas connues comme telles. L'effet sur les blocs évalués est faible :

  | Bloc | Suites | Heures remplacées | Heures J-7 | Cibles |
  | --- | --- | --- | --- | --- |
  | Apprentissage (avant le 01/07/2026) | 149 | 17 779 | 6 534 | 2 237 845 |
  | Validation (juillet-août) | 3 | 0 | 3 753 | 141 942 |
  | Diagnostic (septembre) | 1 | 49 | 2 506 | 69 521 |
  | Test (octobre) | 1 | 137 | 5 566 | 74 535 |

  L'étude A/C (EXP-E1-04) applique la détection sans fuite. Pour un usage strict, on retrouve les valeurs d'origine avec `src/data/original.py`.
- **La J-7 peut recopier un zéro suspect** : 750 des 18 385 valeurs J-7 sont un 0 venant d'une longue suite de zéros.

## Décision et suite

- **Écart 1 :** à décider avec E3 et E4. Deux options :
  - installer les sites de test le 22/09/2026, pour avoir 7 jours mesurés ;
  - garder le 23/09 et annoncer « 6 jours mesurés à la première origine de test ».

  Le cas de 7 jours étant le cas principal du protocole, je propose la première option, ce qui demande de régénérer les données (`new_sites.py`, `fill_counts.py`).
- **Écart 2 :** recalculer les deux empreintes sur la version LF, ou les retirer du manifeste.
- Le message de livraison est exact sur tous ses chiffres. Les points ci-dessus sont à ajouter au descriptif (`livraison/README.md`) ou au contrat version 2.
- **Retour d'un partenaire et preuve d'utilisation :** à compléter quand E2, E3 ou E4 auront relancé le script sur leur copie.

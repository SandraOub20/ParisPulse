# ParisPulse – Données E1 : `hist-20261117`

Livrées le 19/11/2026 sur la branche `Team1` (fichier `livraison/hist-20261117.zip`, Git LFS).

## 1. Ce que c'est

- Comptages vélo **horaires** de **113 compteurs** de Paris, du **16/10/2023 00:00 au 14/11/2026 22:00 UTC** : 27 023 heures, 3 053 599 lignes.
- Deux ans d'archives de la Ville (16/10/2023 → 15/10/2025), puis, sans coupure, les 13 mois de `flux-20261115` (16/10/2025 → 14/11/2026).
- **Remplace `flux-20261115`** : un seul instantané à utiliser.

## 2. Récupérer les données

Depuis votre branche, à la racine du dépôt :

```bash
git fetch origin
git merge origin/Team1
git lfs install
git lfs pull --include="livraison/hist-20261117.zip"
unzip -o livraison/hist-20261117.zip
```

Sous Windows sans `unzip` : `Expand-Archive livraison\hist-20261117.zip -DestinationPath . -Force`

Les fichiers arrivent dans `data/processed/hist-20261117/` et `data/manifests/hist-20261117.json`.

## 3. Les fichiers

| Fichier                             | Contenu                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| `counts.csv`                        | une ligne par compteur et par heure (les comptages)                                   |
| `counters.csv`                      | compteurs : site, nom, coordonnées, direction, `installation_date`                    |
| `inventory_quality.csv`             | qualité, statut et rôle de chaque compteur ; **filtrer `period_role == "selection"`** |
| `selection_summary.json`            | listes de sites `train` / `dev_new` / `test_new`, trous du réseau                     |
| `context.csv`                       | jours fériés, vacances zone C, grèves, météo prévue (J-2) et observée                 |
| `fill_report.json`                  | bilan des valeurs remplacées                                                          |
| `data/manifests/hist-20261117.json` | empreintes SHA-256 et règles de construction                                          |

## 4. `counts.csv` : les règles à connaître

| Colonne         | Sens                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------ |
| `timestamp`     | début de l'heure, **en UTC** (minuit à Paris = 22:00 UTC la veille en été, 23:00 en hiver) |
| `count_raw`     | valeur publiée par la Ville, jamais modifiée (sauf sites réservés à E3 : vidée avant leur installation fictive) |
| `count`         | valeur à utiliser                                                                          |
| `is_observed`   | la Ville a publié une mesure pour cette heure                                              |
| `is_scoreable`  | **vraie mesure, utilisable comme cible** : c'est le seul masque d'évaluation               |
| `quality_flags` | `missing`, `empty_value`, `long_zero_run`, `network_gap`                                   |

Valeurs remplacées dans `count` (jamais des cibles : `is_scoreable = false`) :

| Cas                                              | Remplacement                                                                | Trace                                   |
| ------------------------------------------------ | --------------------------------------------------------------------------- | --------------------------------------- |
| heure sans mesure (`missing`, `empty_value`)     | même heure de Paris 7 jours avant (J-7), si elle a été mesurée              | `is_observed = false`, `count_raw` vide |
| suite d'au moins 24 h de zéros (`long_zero_run`) | même date et heure de Paris un an avant, si elle est > 0 ; sinon le 0 reste | `count_raw = 0`                         |

- 18 385 heures remplies par J-7, 17 965 par l'année d'avant.
- **Repérer une valeur estimée** (J-7 ou année d'avant) : `count` rempli **et** `is_scoreable == false` (36 350 heures en tout).
- Un **zéro mesuré reste un zéro** et reste une cible.
- `network_gap` : heure absente pour presque tout le réseau (104 heures) : aucune cible ces heures-là.

**Ajustement du contrat (`doc/CONTRATS.md` §3)** : une heure remplie par J-7 a `is_observed = false` mais un `count` rempli (le contrat actuel dit `count = null`). Ce changement sera intégré à la version 2 du contrat ; si cela vous pose problème, dites-le-nous.

## 5. Statuts et sites

`inventory_quality.csv`, colonnes `selection_status` et `site_role` :

| Statut              | Compteurs    | Rôle                                           |
| ------------------- | ------------ | ---------------------------------------------- |
| `retained`          | 67           | sites connus (`S_train`), score principal      |
| `robustness`        | 30           | sites connus (`S_train`), évalués à part       |
| `reserved_dev_new`  | 5 (4 sites)  | nouveaux sites E3, développement (`S_dev_new`) |
| `reserved_test_new` | 10 (5 sites) | nouveaux sites E3, test final (`S_test_new`)   |
| `excluded`          | 1            | Denfert-Rochereau NE-SO, que des zéros         |

Sites réservés à E3 : historique vidé avant une installation fictive, placée **8 jours avant la première origine** d'évaluation = **7 jours de mesures + 24 h de délai de publication** (une mesure n'est connue que 24 h après). À l'origine, E3 dispose donc de 7 jours de mesures publiées ; avec un délai de 0, il en verrait 8 :

| Groupe       | Installé le (Paris) | Première origine |
| ------------ | ------------------- | ---------------- |
| `S_dev_new`  | 23/06/2026 00:00    | 01/07/2026 00:00 |
| `S_test_new` | 23/09/2026 00:00    | 01/10/2026 00:00 |

La date fictive est dans `installation_date` de `counters.csv`. Pour 3 ou 1 jour, garder seulement les derniers jours de ce support.

## 6. Contexte

- **Calendrier** (`is_holiday`, `is_school_holiday`, `is_strike`) : une ligne par jour, le nom dans `label` ; jointure sur la **date de Paris** du début de l'heure.
- **Grèves** (`is_strike`) : transports en commun d'Île-de-France annoncés perturbés ; connues **24 h avant** seulement.
- **Météo** : prévue (J-2) et observée ; jointure sur `interval_end`. Une observation n'est disponible que 24 h après.
- Avant de prévoir depuis une origine, ne garder que ce qui était connu : les lignes de `context.csv` dont `available_at` est vide (connu à l'avance) ou antérieur ou égal à l'origine.

## 7. Découpage temporel

Protocole proposé (`doc/PROTOCOLE_EVALUATION.md` §3), **à confirmer par E4** :

| Bloc          | Période                 |
| ------------- | ----------------------- |
| Apprentissage | jusqu'au 01/07/2026 ; début à choisir : 11/10/2025 (protocole, écrit pour le flux seul) ou 16/10/2023 (les 3 ans) |
| Validation    | juillet – août 2026     |
| Diagnostic    | septembre 2026          |
| Test final    | origines d'octobre 2026 |

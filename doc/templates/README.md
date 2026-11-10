# Gabarits d'échange et de suivi

Les CSV sont **vides, avec en-têtes uniquement**. Copier un gabarit vers le dossier de travail indiqué dans l'[architecture](../ARCHITECTURE.md), puis remplir les valeurs réelles. Aucun fichier de ce dossier ne constitue une prévision ni un résultat scientifique.

| Fichier | À remplir par | Usage |
| --- | --- | --- |
| `counts.csv` | E1 | Vérité terrain horaire et qualité |
| `counters.csv` | E1 | Catalogue, groupes physiques, sens et localisation |
| `inventory_quality.csv` | E1 | Périodes, manques, zéros et décisions de périmètre |
| `context.csv` | E1 | Contexte, lieu/zone, validité et disponibilité |
| `cases.csv` | E4 | Cas attendus avant l'exécution des méthodes |
| `forecasts.csv` | E2/E3 | 24 horizons par cas, sans observations cibles |
| `case_runs.csv` | E2/E3 | Temps et statut par exécution, sans compter 24 fois le coût |
| `scores.csv` | E4 | MAE, populations comparées et couverture |
| `errors.csv` | E4 | Erreurs sur les heures réellement mesurées |
| `coverage.csv` | E4/E5 | Inventaire, prise en charge, refus et replis |
| `manifest.example.json` | E1 | Provenance, licence et empreintes |
| `model_metadata.example.json` | E2/E3 | Modèle, coupure, donneurs, paramètres et conditions |
| `experiment.md` | Chaque équipe | Hypothèse, comparaison, contrôles, résultats et transmission |
| `journal.md` | Chaque étudiant | Travail daté, vérifications et usage par un partenaire |

Conventions : UTF-8, virgule, point décimal, booléens `true`/`false`, cellule vide pour une valeur absente. Dates UTC ISO 8601 avec fuseau. Les listes dans une cellule sont du JSON. Les identifiants sont des chaînes de caractères.

`scores.csv` comporte une ligne par méthode/scénario/population comparée ; les MAE par compteur peuvent être stockées dans une table détaillée associée. `is_complete_24h` concerne les 24 prévisions, pas la présence de 24 observations cibles. Une absence de score reste vide, jamais zéro par défaut.

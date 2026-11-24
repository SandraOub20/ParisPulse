# E2-TECH-001 - Premier calcul des références E2 sur données réelles (essai technique)

- **Date, équipe, responsables et partenaires** : 2026-11-19, E2 ; kid-emmanuelle. Données E1 (`hist-20261117`), cas E4 (`proto-v0`, branche `Team4-sher`, commit `2ac02dd`).
- **Question et hypothèse** : la chaîne `cases.csv` → `counts.csv` → `predict_24h` → `.pred.csv` / `.runs.csv` fonctionne-t-elle sur les données réelles, avec quelle couverture et quel coût ? Essai technique : **aucune comparaison de méthodes ni choix de modèle** (protocole non validé par le professeur).
- **Références bibliographiques** : aucune (référence saisonnière naïve, voir [E2_SUIVI §9](../teams/E2_SUIVI.md#9-matière-pour-le-rapport-final)).
- **Instantané, protocole validé, code et paramètres** :
  - Instantané `hist-20261117` ; empreintes SHA-256 de `counts.csv`, `counters.csv`, `inventory_quality.csv`, `selection_summary.json`, `context.csv` vérifiées contre `data/manifests/hist-20261117.json`.
  - Protocole : `proto-v0` d'E4, **non validé**.
  - Code : [predict.py](../../src/models/known/predict.py), [baseline.py](../../src/models/known/baseline.py) (MOD-005, non commité au moment de l'essai).
  - Paramètres : latence 24 h (`config/project.example.yaml`), repli N = 4, profil 4 semaines, `values = measured`.
  - Commande, pour chaque variante (`reference`, `reference_profile`) :

    ```sh
    python -m src.models.known.predict --cases <proto-v0/cases.csv> \
      --snapshot hist-20261117 --experiment E2-TECH-001 --variant reference
    ```

- **Scénario, sites, dates et budget d'information autorisé** : `known_site`, bloc `validation` de `proto-v0` (origines à minuit local du 01/06 au 31/08/2026), compteurs classés `S_train` par E1 ; information disponible : mesures dont `interval_end <= origin − 24 h`.
- **Facteur modifié et facteurs conservés** : sans objet (essai technique). Les deux variantes reçoivent les mêmes cas et les mêmes entrées.
- **Cas attendus et règle de comparaison** :

  | Étape | Cas |
  | --- | --- |
  | Lignes de `proto-v0` | 19 418 |
  | Écartées : `new_site` | 4 221 |
  | Écartées : bloc `test` (jamais calculé) | 4 095 |
  | Écartées : compteur non `S_train` chez E1 | 244 (2 compteurs que E1 réserve à `S_dev_new`) |
  | **Retenues** | **10 858** |

  `snapshot_id` remplacé par `hist-20261117` sur les 10 858 cas (les cas `proto-v0` portaient `flux-20261115`). Liste exacte : `<method_run_id>.cases_used.csv` ; décompte : `<method_run_id>.selection.json`.
- **Contrôles réalisés** :
  - 24 lignes par cas ;
  - aucune clé en double ;
  - aucune prévision négative ou non finie ;
  - aucun cas en erreur ;
  - 11 valeurs recalculées indépendamment depuis `counts.csv`, toutes identiques : 5 `weekly_naive`, 3 replis (médiane des 4 dernières mesures de même jour et heure locale avant la coupure), 3 `weekly_profile_median`.
- **Résultats mesurés** (couverture et coût ; **MAE non calculée ici**, à calculer par E4) :

  | `method_run_id` | Cas complets / attendus | Cas `ok` / `fallback` | Horizons en repli | Inférence médiane / cas | Durée totale |
  | --- | --- | --- | --- | --- | --- |
  | `e2-reference-measured` | 10 858 / 10 858 | 10 013 / 845 | 16 124 / 260 592 (6,2 %) | 2,9 ms (+ 3,8 ms préparation) | 123 s |
  | `e2-reference_profile-measured` | 10 858 / 10 858 | 10 475 / 383 | 8 996 / 260 592 (3,5 %) | 4,3 ms (+ 3,8 ms préparation) | 129 s |

  Matériel : ordinateur portable Apple M5 Pro, 24 Go, CPU, un seul processus ; lecture de `counts.csv` en 2,8 s.
- **Analyse, limites et décision** :
  - Sur les 16 124 horizons en repli de `weekly_naive`, 5 234 avaient une valeur estimée par E1 (J-7) dans `count` à t − 168 h. Lue telle quelle, cette valeur aurait produit un statut `ok` pour ce qui est en réalité y(t − 336 h). D'où la règle `values = measured` (D-11).
  - Les zéros des longues suites restent des entrées valides (mesures publiées).
  - Limites : protocole et cas provisoires ; règle d'admissibilité provisoire (C3/M2) ; écart I3 (UTC contre heure locale) non tranché.
- **Lien vers données de résultats et figures** : `data/prediction_results/E2-TECH-001/` (exclu de Git, recalculable par la commande ci-dessus).
- **Retour d'un partenaire et preuve d'utilisation** : à obtenir. Transmettre à E4 pour un premier score et à E5 pour l'affichage. Signaler à E4 les 3 écarts de `proto-v0` (voir [E2_SUIVI §8](../teams/E2_SUIVI.md#8-échanges-avec-les-partenaires)).

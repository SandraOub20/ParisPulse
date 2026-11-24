# Journal individuel - Zeineb (E1, inventaire et sélection : `src/data/quality.py`)

## 13-14/11/2026 - Journée 1 : inventaire du réseau et premier choix d'échantillon

- Date et journée : 13/11 et 14/11/2026, journée 1.
- Question ou objectif personnel : quel réseau observe-t-on dans le flux courant ? Quels compteurs utiliser, et avec quel rôle (S_train, robustesse, sites réservés E3, exclus) ?
- Travail réalisé et outils utilisés : `src/data/quality.py` (Python, pandas), avec les mesures par compteur sur une grille UTC commune, les critères `SelectionCriteria`, le tirage reproductible des sites réservés (SHA-256 et graine) et les trous communs au réseau. Tests dans `tests/test_data_quality.py`. Commits `fd12d94`, `bc0acae`, `3c0dd3d`.
- Expérience ou contrôle effectué : tests sur un réseau synthétique (zéros non transformés en manques, rien ne change quand on modifie le futur, directions d'un même site gardées ensemble). Contrôle des distances au plus proche voisin entre sites.
- Versions et liens vers les fichiers/résultats : instantané provisoire `flux-20261114` ; [fiche EXP-E1-02](../experiments/E1-inventaire-selection.md).
- Résultat et analyse critique : 74 / 17 / 15 / 6 / 1 compteurs (retenus, robustesse, test E3, dev E3, exclu). Avec un seuil d'alias de 50 m, les deux sens du Pont National (57 m) et du boulevard Richard-Lenoir (65 m) étaient répartis entre apprentissage et E3 : c'est une fuite.
- Décision ou adaptation : seuil d'alias porté à 100 m, placé dans le creux de la distribution des distances (0-93 m, puis 113 m). La décision repose uniquement sur les coordonnées et les noms, avant tout score.
- Partenaire, retour reçu et usage vérifié : critères envoyés à E4.
- Prochaine étape : passer à l'instantané produit par la boucle `--tout`.

## 16/11/2026 - Journée 2 : reprise sur `team1-nihed`, mise à jour de la fiche, contrôles

- Date et journée : 16/11/2026.
- Question ou objectif personnel : le passage de `flux-20261114` à `flux-20261115` (boucle `--tout`, grille commune, groupes écrits, nouvelle définition d'un compteur actif) change-t-il la sélection ? Les deux sens du Pont National sont-ils bien réunis ?
- Travail réalisé et outils utilisés : relecture du contrat (`doc/CONTRATS.md` §2 inventaire, §4 contexte). Branche `team1-zeineb` repartie de `team1-nihed` (fast-forward). Installation sur une copie neuve (`uv sync`), puis `uv run python -m src.data.acquire --tout` et `uv run python -m src.data.quality --snapshot flux-20261116 --figures`.
- Expérience ou contrôle effectué :
  - tests : `uv run pytest tests`, 68 réussis ;
  - reproductibilité : un nouvel instantané (`flux-20261116`, 1 034 677 lignes, SHA-256 `5194759a…fb3260`) redonne 74 / 17 / 15 / 6 / 1, 58 groupes et les mêmes listes `train / dev_new / test_new` ;
  - **Pont National, à la main** : `100047541-353326452` (SO-NE) et `100047549-101047549` (NE-SO) ont le même `site_group_id` `100047541` et des directions opposées, tous deux `retained`. Critère validé ;
  - aucun groupe n'a deux rôles ; distance minimale entre un site réservé et un site d'apprentissage : 164 m ;
  - `network_gaps` avec la nouvelle définition d'un compteur actif : mêmes trous, sauf le bord de la fenêtre glissante.
- Versions et liens vers les fichiers/résultats : [fiche EXP-E1-02](../experiments/E1-inventaire-selection.md) mise à jour ; `data/processed/flux-20261116/selection_summary.json`, `inventory_quality.csv`, `figures/` ; `data/manifests/flux-20261116.json`.
- Résultat et analyse critique : la sélection ne dépend pas du jour d'extraction. Seules les mesures liées au bord de la fenêtre changent un peu (compteurs à plus de 340 jours : 102, puis 108). Les anciens effectifs « 68 / 9 » de la fiche étaient des nombres de `site_id`, pas de groupes : correction faite (47 / 7 / 4 groupes, 58 au total). La direction est maintenant tirée du nom et non plus laissée vide : limite mise à jour.
- Décision ou adaptation : `flux-20261115` reste la référence de l'équipe ; `flux-20261116` sert de contrôle de reproductibilité. Argumentaire « critères fixés avant le test » ajouté à la fiche.
- Partenaire, retour reçu et usage vérifié : Nihed a écrit `site_group_id` (groupes candidats) dans `counters.csv` le 15/11 ; usage vérifié sur `flux-20261116` (58 groupes, deux sens du Pont National réunis). E4 : en attente de sa réponse sur les critères, la date de test (01/10/2026) et les sites réservés.
- Prochaine étape : dès qu'E4 valide, lui transmettre les listes `site_groups` de `selection_summary.json` pour `config/project.yaml`, puis noter son retour dans la fiche. Vérifier ensuite l'usage par E3 (sites réservés) et par E5 (statuts sur la carte).

## 17/11/2026 - Voisins à moins de 300 m, référentiel des grèves

> Entrée reconstituée par Tasnim le 24/11/2026, à partir des commits `8a4f3d0`, `4bf5c9b` et `05a90f3`, de `data/reference/README.md` et des fiches des autres équipes. **Zeineb : à relire et à compléter**, en particulier les outils utilisés et les retours reçus.

- Date et journée : 17/11/2026.
- Question ou objectif personnel :
  - quand un compteur n'a pas de mesure, quel compteur proche peut-on proposer ?
  - y a-t-il grève des transports d'Île-de-France tel jour, et à partir de quand le sait-on ?
- Travail réalisé et outils utilisés :
  - `quality.py` : distances aux sites voisins. Deux colonnes dans `inventory_quality.csv`, `alias_candidates` (moins de 100 m, ceux qui forment les groupes) et `nearby_sites_300m` (moins de 300 m, à titre descriptif) ; 2 tests ajoutés, 78 au total (`8a4f3d0`, 13:46) ;
  - `data/reference/greves_transport_idf.csv` : une ligne par jour, du 01/01/2023 au 17/11/2026 (1 417 jours, dont 73 de grève) ;
  - `greves_transport_idf_sources.csv` : une source datée par jour de grève (`4bf5c9b`, 16:56) ;
  - notice avec un exemple, la règle de jointure et les trois moments de l'annonce (`05a90f3`, 17:03) ;
  - outils : *à compléter*.
- Expérience ou contrôle effectué :
  - jointure expliquée sur le passage UTC / Paris (23:00 UTC = minuit le lendemain) ;
  - disponibilité fixée à 24 h avant : c'est la prévision de trafic obligatoire (Code des transports, art. L1222-8), alors qu'un préavis n'entraîne pas toujours de perturbation.
- Versions et liens vers les fichiers/résultats : [data/reference/README.md](../../data/reference/README.md) ; [EXP-E1-02](../experiments/E1-inventaire-selection.md).
- Résultat et analyse critique :
  - aucune API ne donne l'historique des grèves : la liste est manuelle (RATP, Transilien, Citymapper, presse) ;
  - couverture faible pour les grèves de bus 2023-2025, de janvier à avril 2025 et de février à mai 2026 ;
  - l'effet sur le vélo n'est pas mesuré.
- Décision ou adaptation : `greve = true` veut dire « trafic annoncé comme perturbé », information connue 24 h avant.
- Partenaire, retour reçu et usage vérifié :
  - Sabrina a joint le référentiel au contexte le 19/11 (`context.py --greves`, `e1-context/0.3.0`) : 33 jours de grève sur l'historique, 11 sur le flux, sans ligne créée ni perdue ;
  - E2 utilise les grèves dans le contexte complet de son premier réseau (E2-TECH-003, 23/11) ;
  - E2 entraîne sur les 97 compteurs `S_train` (49 groupes) et exclut les 9 groupes réservés à E3 (preuve : `excluded_site_groups` de leur `metadata.json`). C'est un usage vérifié de la sélection ;
  - E4 : `proto-v0` mettait 2 compteurs `S_dev_new` en sites connus. Selon le suivi d'E2, `proto-v1` corrige ce point ;
  - réponse d'E4 sur les critères : toujours *à renseigner*.
  - Une remarque de Tasnim (24/11) : les empreintes des deux fichiers de grèves dans le manifeste ont été calculées sur une copie aux fins de ligne Windows (CRLF). Le contenu est identique, mais le contrôle échoue sous macOS et Linux ([EXP-E1-05](../experiments/E1-verification-livraison.md)).
- Prochaine étape : *à compléter*.

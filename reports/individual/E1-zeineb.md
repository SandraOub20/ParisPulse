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

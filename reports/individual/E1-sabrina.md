# Journal individuel - Sabrina (E1)

Entrées reliées aux commits de la branche `Team1-sabrina` et aux fiches de `reports/experiments/`.

## 15/11/2026 - Protocole de l'étude des zéros (EXP-E1-04)

- **Question ou objectif personnel :** faut-il garder (A) ou écarter (B) de l'apprentissage les heures d'une suite d'au moins 24 h de zéros ?
- **Travail réalisé et outils utilisés :** `src/data/zeros.py` (détection sans fuite à la coupure, délai de publication de 24 h), `src/data/zeros_experiment.py` (comparaison A/B, règle de décision), `tests/test_data_zeros.py`. Outils : *à compléter*.
- **Expérience ou contrôle effectué :** mesure descriptive sur `flux-20261115` à la coupure du 01/07/2026 : 9 compteurs concernés, tous `robustness`, 5 822 heures retirées par B, dont 3 853 pour 24 boulevard Jourdan E-O.
- **Versions et liens :** commits `50df487`, `20bb850` ; fiche `reports/experiments/E1-zeros-apprentissage.md`.
- **Résultat et analyse critique :** pas de résultat de modèle ; la règle de décision (−5 % sur les concernés, +1 % au plus sur les témoins, aucun compteur perdu) est fixée avant tout résultat. Jourdan pèse 66 % des heures retirées : analyse « sans Jourdan » prévue.
- **Décision ou adaptation :** A par défaut ; seuils proposés, à valider par E4.
- **Partenaire, retour reçu et usage vérifié :** E2 (modèle), E4 (protocole) : *à renseigner*.
- **Prochaine étape :** recalculer sur la grille commune.

## 16/11/2026 - Grille commune, relecture et analyse « sans Jourdan E-O »

- **Question ou objectif personnel :** vérifier que les chiffres tiennent sur la nouvelle version de `flux-20261115`, et retirer de la fiche ce qui n'est pas vérifiable.
- **Travail réalisé et outils utilisés :** fusion de `team1-nihed` ; entrées du modèle mises à jour à chaque origine ; fonction `concerned_without` (MAE des concernés sans Jourdan E-O) et tableau de MAE par compteur. Outils : *à compléter*.
- **Expérience ou contrôle effectué :** chiffres relancés sur la grille commune (113 × 9 503 h) : identiques ; empreintes SHA-256 des fichiers vérifiées.
- **Versions et liens :** commits `0743ce7`, `cb990df`, `31deea8`, `54b98ed`, `6e4b40c`.
- **Résultat et analyse critique :** 17 tests de l'étude verts ; script vérifié de bout en bout avec un modèle de test technique, dont les chiffres ne décident rien.
- **Décision ou adaptation :** affirmations non vérifiables retirées de la fiche.
- **Partenaire, retour reçu et usage vérifié :** *à renseigner*.
- **Prochaine étape :** relancer sur la version régénérée de l'instantané.

## 17/11/2026 - Version `e1-prepare/0.3.0` et remplacement J-7

- **Question ou objectif personnel :** adapter l'étude à l'instantané régénéré ; remplacer les heures sans mesure par J-7 (demande de Nihed).
- **Travail réalisé et outils utilisés :** fiche relancée sur `e1-prepare/0.3.0` (1 071 127 lignes, 9 479 h par compteur) ; nouveau `src/data/fill_j7.py` et ses tests. Outils : *à compléter*.
- **Expérience ou contrôle effectué :** tous les chiffres de l'étude inchangés ; J-7 sur `flux-20261115` : 15 705 heures sans mesure en période active, 13 589 remplacées, 2 116 laissées vides (J-7 sans mesure), 21 945 hors période active non touchées.
- **Versions et liens :** commit `b49816f` ; sortie `data/processed/flux-20261115/filled_j7.csv` (hors Git).
- **Résultat et analyse critique :** une valeur remplacée n'est jamais une cible évaluable (contrat §3) et ne compte pas comme un zéro observé dans l'étude des zéros (vérifié : mêmes 5 822 heures).
- **Décision ou adaptation :** même heure de Paris J-7 ; période active seulement ; pas de J-14 ; J-7 sans mesure = vide.
- **Partenaire, retour reçu et usage vérifié :** Nihed (demande) : *à renseigner*.
- **Prochaine étape :** passation de l'historique.

## 18/11/2026 - Passation de l'historique : préparation sans les données

- **Question ou objectif personnel :** préparer les tâches A2, A5, B1, B2 et B7 de la passation de Nihed avant de recevoir `hist-20261117`.
- **Travail réalisé et outils utilisés :** J-7 remplacé directement dans `count`, `count_raw` restant vide comme trace (B2) ; `src/data/zeros_criteria.py` (A2) ; `src/data/zeros_years.py` (B1) ; fiche `reports/experiments/E1-historique.md` (A5). Outils : *à compléter*.
- **Expérience ou contrôle effectué :** sur `flux-20261115`, A2 retrouve exactement les statuts de l'inventaire avec la règle actuelle (95 / 17 / 1 avant réservation) ; avec une part de zéros > 1 %, 5 % ou 10 % : 15, 9 ou 8 `robustness`. B1 : 17 suites, 1 seule comparable un an avant (13 mois de données).
- **Versions et liens :** fiches `E1-historique.md`, `E1-zeros-apprentissage.md`.
- **Résultat et analyse critique :** outils prêts mais non lancés sur l'historique ; chiffres de l'historique repris de la passation, à revérifier.
- **Décision ou adaptation :** critère A2 non choisi (Zeineb puis E4) ; interprétation de « year − 1 » à confirmer avec Nihed.
- **Partenaire, retour reçu et usage vérifié :** *à renseigner*.
- **Prochaine étape :** recevoir `hist-20261117` (zip et manifeste), puis A3, A2, A4, B1, J-7 et B7 sur l'historique.

## 18/11/2026 (soir) - Relecture complète, données remplies conformes au sujet et au contrat

- **Question ou objectif personnel :** vérifier que le code et les fiches d'E1 n'ont ni erreur ni contradiction avec le sujet et le contrat, et corriger.
- **Travail réalisé et outils utilisés :** relecture du sujet, de la documentation et du code d'E1 ; `fill_zeros_year.py` (`e1-fill-zeros-year/0.2.0`) : l'année d'avant ne remplace un zéro que si elle est > 0, et la valeur remplacée n'est plus une cible ; `zeros.py` et `zeros_experiment.py` (`e1-zeros/0.2.0`) : étude A (garder) / C (année d'avant) à la place de A / B ; `new_sites.py` (`e1-new-sites/0.2.0`) et `fill_counts.py` : une version des données par budget (1, 3, 7 jours), sites installés au début du support de la première origine d'évaluation ; fiche d'inventaire revérifiée en `e1-prepare/0.3.0` (tâche C2) ; fiches contexte, historique et README corrigées. Outils : *à compléter*.
- **Expérience ou contrôle effectué :** 134 tests verts. Sur `flux-20261115` : C ne remplace aucune heure à la coupure du 01/07/2026 (année d'avant hors de l'instantané) ; données livrées : 137 heures remplacées par l'année d'avant, 13 087 gardées à 0 (année d'avant inconnue) ; 21 compteurs réservés sur 11 sites, installés pour 7 jours le 23/06/2026 (dev) et le 23/09/2026 (test), heure de Paris.
- **Versions et liens :** fiches `E1-zeros-apprentissage.md`, `E1-historique.md`, `E1-inventaire-selection.md` ; sorties `data/processed/flux-20261115/counts_filled_<budget>j.csv` (hors Git).
- **Résultat et analyse critique :** quatre points contraires au sujet ou au contrat corrigés : un zéro n'est jamais remplacé par une case vide ; une valeur remplacée n'est jamais une cible ; le traitement appliqué aux données (année d'avant) est celui que l'étude mesure avec E2 et E4 ; les sites nouveaux ont des jours à prévoir après leur historique local, et seul le budget change d'une version à l'autre. Limite : l'étude A/C ne peut se faire que sur l'historique.
- **Décision ou adaptation :** décisions de Sabrina du 18/11/2026 (points ci-dessus), à présenter aux autres équipes après la livraison.
- **Partenaire, retour reçu et usage vérifié :** *à renseigner*.
- **Prochaine étape :** recevoir le brut du flux, assembler `hist-20261117`, puis lancer les outils sur l'historique.

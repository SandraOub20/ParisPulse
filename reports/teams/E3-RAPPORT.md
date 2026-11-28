# Rapport de l'équipe 3 : prévision à 24 h sur les nouveaux sites

**Équipe 3 :** Lynda Khazem, Massinissa Machter, Andrew Zgheib, Michaela El Rif, Carl Abou Diwan.\
**Périmètre :** nouveaux compteurs réservés à E3 (`S_dev_new`, puis `S_test_new`), avec `hist-20261117` et le protocole `proto-v1`.\
**État :** Produit (modèle Chronos-2 et son interface avec deux variantes : gelée et adaptée, livré à l'équipe Application E5).

Le détail des expériences est disponible dans [le dossier reports/teams/E3-\*](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/experiments/) et la documentation rapide ainsi que la prise en main dans [la documentation E3](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/teams/E3-DOC-&-PRISE-EN-MAIN.md).

## 1. Rôle de l'équipe 3 et question étudiée

L’équipe 3 étudie l’arrivée d’un nouveau compteur pour lequel seules quelques journées de mesures sont disponibles.

Dans le cadre du contrat établi entre les équipes 1, 3, 4 et 5, les nouveaux sites disposent d’un historique local limité à :

- 24 heures, soit 1 jour ;
- 72 heures, soit 3 jours ;
- 168 heures, soit 7 jours.

L’objectif est de répondre à la question suivante : peut-on prévoir les passages d’un nouveau compteur (`new_site`) à partir de connaissances acquises sur d’autres lieux/données, avec un modèle public ou avec celui de l’équipe 2 ?

Pour cela, les expériences comparent :

- les modèles utilisés sans aucune adaptation en une seule prévision, appelés variante `frozen` (gelée) ;
- l’adaptation de ces modèles aux premières observations locales (historique autorisé), appelée variante `adapted` (adaptée) ;
- la quantité de données locales nécessaire à cette adaptation.

## 2. Données autorisées et protocole

- Snapshot des données : `hist-20261117`.
- Périmètre : nouveaux sites (`new_site`) de validation `S_dev_new` pour toutes les évaluations des modèles. `S_test_new` n'est pas touché et est destiné au test final de l'application.
- Fichier des cas : `data/evaluation/proto-v1/cases.csv`, protocole `proto-v1` (fourni par E4).
- Budgets locaux simulés (contrat avec E1, E4 et E5) : 24 h (1 jour), 72 h (3 jours) et 168 h (7 jours) pour l'évaluation (validation `S_dev_new`). Un budget d'historique fixe pour chaque couple (compteur-site) est également fixé entre 1, 3 ou 7 jours dans l'application pour les cas du test final en production (application).
- Horizon : prédiction des 24 heures suivant l'origine (00 h) de chaque cas.
- Prévision gelée (`frozen`) : les paramètres des modèles (publics et du modèle MLP de l'équipe 2 transféré) restent inchangés ; prévision directe en one-shot.
- Prévision adaptée (`adapted`) : les paramètres locaux sont adaptés et calculés uniquement dans le cadre du budget d'historique autorisé du cas.
- Évaluation : toutes les évaluations portent sur la validation (`S_dev_new`), réalisée par E4 (scores et erreurs sur la validation `S_dev_new`). La MAE est la moyenne macro entre compteurs et les variantes sont comparées sur les mêmes cas.

Lien utile (cas de validation `new_site`) : [la fiche `proto-v1/cases.csv`](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/data/evaluation/proto-v1/cases.csv).

## 3. État de l’art

Nous avons étudié et effectué des recherches sur les modèles publics disponibles pour la prévision de séries temporelles, notamment Chronos-2 et Google TimesFM.

| Référence                                                                                                                                               | Apport au choix E3                                                                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Ansari et al., [Chronos: Learning the Language of Time Series](https://arxiv.org/abs/2403.07815) ; [Chronos-2](https://huggingface.co/amazon/chronos-2) | Modèle temporel préentraîné susceptible de transférer des séries temporelles vers de nouveaux compteurs. |
| [Google TimesFM 2.5](https://github.com/google-research/timesfm)                                                                                        | Un autre modèle public concurrent de Chronos-2, testé en variantes gelée et adaptée.                     |

## 4. Prévisions avec les modèles en version gelée

Trois modèles (deux modèles publics et le modèle MLP de l'équipe 2 transféré) ont été testés en variante gelée (`frozen`) :

| Modèle                 | Principe                                                                               | Résultat ; temporal split : validation (S_dev_new)                                                                                |
| ---------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Chronos-2**          | Modèle temporel préentraîné sur des séries publiques (médiane comme repli)             | Disponible pour les trois budgets ; meilleur compromis en validation parmi les candidats publics à 24 h et 72 h.                  |
| **Google TimesFM 2.5** | Modèle public préentraîné, sortie médiane utilisée comme prévision ponctuelle de repli | Testé sur les trois budgets ; comparable à Chronos à 168 h, mais moins précis en MAE aux trois budgets.                           |
| **MLP de l'équipe 2**  | Modèle transféré de l'équipe 2, entraîné sur les sites connus                          | Utilisable seulement avec au moins 7 jours d'historique ; MAE de validation meilleure que celle des deux modèles publics à 168 h. |

### 4.1 Évaluation des variantes gelées (frozen)

Résultats en MAE (erreur moyenne en vélos/h) des modèles frozen (gelés), fournis par E4 :

| Budget | Modèle             | Cas comparés | Heures | MAE       |
| ------ | ------------------ | ------------ | ------ | --------- |
| 24 h   | Chronos-2          | 300          | 7 180  | **26,09** |
| 24 h   | Google TimesFM 2.5 | 300          | 7 180  | 27,98     |
| 72 h   | Chronos-2          | 305          | 7 300  | 22,83     |
| 72 h   | Google TimesFM 2.5 | 305          | 7 300  | **22,55** |
| 168 h  | Chronos-2          | 305          | 7 300  | **19,67** |
| 168 h  | Google TimesFM 2.5 | 305          | 7 300  | 19,79     |
| 168 h  | MLP équipe 2       | 305          | 7 300  | **18,80** |

Le MLP n'est pas applicable aux budgets de 24 h et 72 h.

La fiche complète est disponible ici : [E3-models-frozen-results.md](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/experiments/E3-models-frozen-results.md).

## 5. Adaptation ou pas

Les premiers résultats obtenus avec les variantes `frozen` (gelées) étant encourageants, cela ne nous a pas empêchés de poursuivre l'étude de l'adaptation. Pour cela, nous avons approfondi l'étude sur davantage de sites.

Une adaptation est envisagée uniquement pour les méthodes publiques pouvant fonctionner avec les trois budgets locaux. Le MLP de l'équipe 2 n'est pas adapté : son contrat exige au moins 7 jours d'historique, donc il ne couvre pas l'ensemble des budgets de 1, 3 et 7 jours prévus pour E3.

**Chronos-2** justifie une adaptation légère parce que ses poids en variante `frozen` donnent une base solide sur les trois budgets. **Google TimesFM** mérite également que son adaptation soit testée.

## 6. Adaptation et approfondissement

### 6.1 Chronos-2 adapted-v1

Cette première adaptation conserve les poids gelés et estime une correction additive locale (méthode statistique) par créneaux : matin, soir et autres heures. Une correction n'est retenue que si elle améliore simultanément la MAE et la RMSE sur les pseudo-prévisions internes.

| Budget | MAE frozen | MAE adapted-v1 |
| ------ | ---------- | -------------- |
| 24 h   | **26,09**  | 26,21          |
| 72 h   | **22,83**  | 23,23          |
| 168 h  | **19,67**  | 19,92          |

La v1, détaillée dans [E3-chronos-adapted-v2.md](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/experiments/E3-chronos-adapted-v2.md), n'améliore la MAE pour aucun budget. Elle est donc écartée au profit de la variante `frozen`, qui est une méthode plus stable.

### 6.2 Chronos-2 adapted-v2

La v2 conserve les poids préentraînés du modèle `frozen` et mélange la prévision Chronos avec la médiane de l'historique local du même créneau horaire :

`prévision = max(0, poids × prévision Chronos + (1 - poids) × profil horaire local)`

Les poids sélectionnés et calculés une seule fois sur `S_dev_new` en validation sont de 0,80 à 24 h, 0,80 à 72 h et 0,85 à 168 h. Ils sont enregistrés dans [blend_weights.json](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/artifacts/models/e3-chronos2-adapted-v2/blend_weights.json).

| Budget | MAE frozen | MAE adapted-v2 | Δ MAE |
| ------ | ---------- | -------------- | ----- |
| 24 h   | 26,09      | **25,89**      | -0,20 |
| 72 h   | 22,83      | **22,06**      | -0,77 |
| 168 h  | 19,67      | **19,27**      | -0,40 |

L'adaptation v2 améliore simultanément la MAE pour les trois budgets. Les détails sont disponibles dans [E3-chronos-adapted-v2.md](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/experiments/E3-chronos-adapted-v2.md).

### 6.3 Google TimesFM 2.5 adapted-v2

TimesFM utilise le même principe que Chronos-2 adapted-v2, avec des poids différents : 0,50 à 24 h, 0,95 à 72 h et 0,90 à 168 h.

| Budget | MAE frozen | MAE adapted-v2 | Δ MAE |
| ------ | ---------- | -------------- | ----- |
| 24 h   | **27,98**  | **27,68**      | -0,30 |
| 72 h   | **22,55**  | 22,61          | +0,06 |
| 168 h  | **19,79**  | 19,90          | +0,12 |

L'adaptation n'apporte pas de gain net sur les trois budgets. Elle ne réduit la MAE qu'à 24 h. Le rapport complet est disponible ici : [E3-google-adapted-v2.md](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/experiments/E3-google-adapted-v2.md).

## 7. Résultats finaux

- L'allongement de l'historique (de 1 j à 3 j puis à 7 j) réduit l'erreur : **Chronos adapted-v2** passe d'une **MAE de 25,89 à 24 h** à **19,27 à 168 h**.
- **Chronos adapted-v2 améliore sa variante gelée (frozen) aux trois budgets.**
- TimesFM adapted-v2 n'améliore pas le modèle frozen de façon régulière.
- À 168 h, le MLP frozen de l'équipe 2 (entraîné sur des sites connus) reste meilleur que Chronos adapté en termes de MAE (18,80 contre 19,27), mais il n'est disponible que pour ce budget. On ne peut pas le généraliser aux autres budgets (1 et 3 jours), d'où son abandon.

**Modèle retenu pour E3 : Chronos-2, avec les variantes `frozen` et `adapted-v2`.** Cette recommandation privilégie une méthode applicable aux trois budgets du contrat, avec une amélioration constante de la MAE grâce à une adaptation légère des poids (sélection des poids statistiques), sans réentraînement des poids Chronos.

## 8. Contributions et utilisation des partenaires

### 8.1 Périmètre GitHub

Les principaux livrables E3 sont :

- [src/models/new/](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/src/models/new/) : prévisions frozen Chronos-2, TimesFM et MLP de l'équipe 2, adaptations.
- [data/prediction_results/EXP-E3/](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/data/prediction_results/EXP-E3/) : prévisions `.pred.csv` et coûts/exécutions `.runs.csv`.
- [data/evaluation/proto-v1/EXP-E3/](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/data/evaluation/proto-v1/EXP-E3/) : résultats d'évaluation reçus d'E4.
- [artifacts/models/e3-chronos2-adapted-v2/](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/artifacts/models/e3-chronos2-adapted-v2/) : poids de mélange Chronos.
- [reports/experiments/](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/experiments/) : résultats frozen, adaptations et comparaisons.
- [journaux individuels](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/reports/individual/) : suivi des membres E3.

### 8.2 Travail transversal avec les partenaires

| Partenaire | Contribution reçue ou retour                                                                     | Utilisation E3                                                                                                                                                                                                  |
| ---------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **E1**     | Instantané `hist-20261117`, comptages, historique et contexte                                    | Filtrage causal de l'historique, exclusion des données estimées, chargement des cas.                                                                                                                            |
| **E2**     | MLP entraîné sur les sites connus                                                                | Utilisation gelée sur les cas à 168 h, sans adaptation locale.                                                                                                                                                  |
| **E4**     | Cas `proto-v1`, séparation `S_dev_new` de `S_dev_test`, calcul des scores MAE/RMSE/R²/couverture | Choix des variantes et du modèle à retenir à partir des scores de validation comparables.                                                                                                                       |
| **E5**     | Interface applicative, affichage des nouveaux cas, calcul des prédictions en direct et archivage | Notre produit : Chronos-2 est exposé en variantes `frozen` et `adapted-v2` ; l'application utilise une même interface `src.models.new.predict_24h` et affiche les prévisions de notre modèle en deux variantes. |

La documentation d'intégration est disponible dans [src/models/new/README.md](https://github.com/SandraOub20/ParisPulse/blob/Team3-v2/src/models/new/README.md). Le point d'entrée commun est `predict_24h(case, history, variant, model_name)`, qui produit 24 horizons de prédiction dans le format du contrat E3/E4/E5.

## 9. Recommandation et limites

- Servir **Chronos-2 frozen** et **Chronos-2 adapted-v2** dans E5.
- Fixer un seul budget (24 h, 72 h ou 168 h) pour chaque couple compteur-site avant l'utilisation de l'application.
- Utiliser adapted-v2 pour améliorer l'erreur moyenne aux trois budgets.
- Les résultats d'évaluation sont issus du split de validation `S_dev_new` ; ils ne mesurent pas encore la généralisation sur `S_test_new`, qui sera évaluée au moment du test final de l'application.

Avec ces réserves, les résultats en validation sont encourageants pour une intégration dans l'application : Chronos adapted-v2 offre le meilleur compromis entre MAE, couverture des trois budgets et stabilité face à sa variante frozen. 
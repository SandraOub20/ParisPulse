# Rapport de l'équipe 2 : prévision à 24 h sur les sites connus

Équipe : Idir, Esther, Ania, Emmanuelle. Version du 2026-11-27. Le détail est dans le [suivi](E2_SUIVI.md), les fiches d'expérience dans [reports/experiments/](../experiments/), et la prise en main dans [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md).

## 1. Question étudiée

Pour un compteur vélo déjà suivi (site connu), prévoir les 24 heures du lendemain à minuit, heure de Paris, avec seulement l'information publiée à ce moment :
- mesures publiées 24 h après coup ;
- calendrier ;
- grèves annoncées ;
- météo prévue à J−2.

Il faut savoir :
1. si une méthode apprise bat clairement des références simples ;
2. laquelle servir dans l'application (E5) ;
3. si l'information ajoutée (le contexte) aide ;
4. si le modèle de deep learning résiste aux pannes de capteur.

## 2. Choix bibliographiques

| Référence | Ce qu'on en retient |
| --- | --- |
| Zeng et al. (2022), *Are Transformers Effective for Time Series Forecasting?* | Toujours comparer à des solutions simples : d'où deux références recalculables à la main |
| Salinas et al., *DeepAR* (2017-2019) | Un seul modèle appris sur toutes les séries, chaque fenêtre normalisée par son niveau, et des covariables connues à l'avance : d'où notre MLP partagé |
| Gradient boosting par histogrammes (scikit-learn `HistGradientBoostingRegressor`), perte `absolute_error` | Une méthode tabulaire solide sur des variables de décalage et de calendrier ; la perte L1 vise directement la MAE du projet |
| Che et al. (2018), *GRU-D* ; masquage aléatoire des entrées (proche du *dropout* d'entrée) | Le masque comme information, et l'apprentissage sur entrées trouées : la base d'EXP-E2-05 |

Prophet a été envisagé comme référence, puis abandonné : il n'est pas déclaré dans les dépendances, il demande un ajustement par cas et il ne se vérifie pas à la main (D-04, D-10).

## 3. Données autorisées et protocole

- Instantané `hist-20261117` d'E1. Les cas viennent d'E4 (`proto-v1`) : **6 014 cas de validation**, soit 97 compteurs `S_train` sur les 62 jours de juillet-août 2026, et **4 365 cas de test** (octobre-novembre), lus une seule fois après le gel.
- **Sans fuite** :
  - une mesure n'est lisible que si elle est publiée à l'origine (24 h de délai) ;
  - les modèles apprennent du 16/10/2023 au **01/07/2026**, avant la validation ;
  - la météo est celle prévue à J−2, jamais celle observée ;
  - les sites réservés à E3 sont exclus de l'apprentissage, et la preuve est écrite dans `metadata.json`.
- **Vide ≠ 0** : seules les vraies mesures servent d'entrées (`count_raw` si `is_observed`), sans les valeurs remplies par E1. Une prévision absente reste vide.
- **Score** : celui d'E4 (`src/eval/metrics.py`) :
  - la MAE est calculée par compteur, puis moyennée sans pondération ;
  - toutes les méthodes sont comparées sur les mêmes cas complets ;
  - le score est donné en deux lectures, « système » (repli compris) et « brut » (modèle seul).

  Notre `score.py` refait exactement ce calcul (mêmes valeurs qu'E4 à la décimale près) pour que tout soit recalculable.
- Chaque fiche est **figée avant la lecture des scores** : règle de décision, seuils et modèles déclarés d'avance.

## 4. Méthodes comparées

| Méthode | Principe | Coût |
| --- | --- | --- |
| `reference` | Même heure 7 jours avant ; repli sur la médiane des semaines précédentes (D-03) | Sans apprentissage |
| `reference_profile` | Médiane des 4 mêmes heures des semaines précédentes | Sans apprentissage |
| **MLP** (deep learning) | 73 368 paramètres. Entrées : la semaine visible normalisée par son niveau, avec le masque des heures manquantes, le calendrier et la météo prévue. Les 24 heures sont prévues d'un coup. Perte L1 pondérée par le niveau, arrêt anticipé sur juin. Refus (puis repli) si moins de 84 h mesurées | 30 à 45 s d'apprentissage sur CPU par graine ; 3 graines |
| **HGB** | Gradient boosting par histogrammes, perte L1. Variables : décalages, niveaux récents, calendrier, contexte. Pas d'identifiant de compteur : le modèle est partagé | Environ 2 min d'apprentissage ; 342 arbres |

Les deux modèles passent par `predict_24h`, le même point d'entrée que l'application et E3. Ses contrôles d'éligibilité portent sur l'instantané, la coupure, le site présent à l'apprentissage et la version du contexte. En cas de refus, le repli sur la référence se fait avec un code exact.

## 5. Vérifications

- Chaque fonction est testée sur de petits exemples calculés à la main. La suite `pytest` passe (environ 440 tests).
- Le calcul en bloc d'une expérience donne **les mêmes fichiers** que le calcul cas par cas, à 1e-3 près (MLP, arrondi `float32`), et 300 fois plus vite.
- Les fichiers de prévision sont conformes au contrat d'E4 (`check_forecasts.py`) : 24 lignes par cas, aucun doublon, vide plutôt que 0.
- Le score d'EXP-E2-03 recalculé par E2 est identique au `scores.csv` officiel d'E4.
- Les contrôles sur juin (dans la période d'apprentissage) ne servent qu'à l'arrêt anticipé et aux règles écrites d'avance, jamais comme score.

## 6. Résultats

**EXP-E2-03, choix de la méthode** (validation, 5 613 cas comparés, 95 compteurs ; [fiche](../experiments/EXP-E2-03.md)) :

| Méthode | MAE macro (système) | Biais | Repli |
| --- | --- | --- | --- |
| HGB | **22,25** | −1,13 | 0 % |
| MLP, graine 0 (graines 0-2 : étendue 0,36) | **22,23** | −0,81 | 5,3 % |
| `reference_profile` | 27,01 | +8,47 | 3,4 % |
| `reference` | 29,75 | +2,39 | 10,4 % |

- Les deux modèles font environ **18 % de mieux** que la meilleure référence et gagnent sur plus de 93 % des compteurs.
- L'écart MLP − HGB (−0,02) est bien plus petit que l'étendue entre les graines du MLP (0,36). La règle fixée d'avance choisit alors le plus simple : **le HGB est retenu pour l'application.** Il sert tous les cas et n'a pas besoin de `torch`.
- Coût : 0,4 s par cas dans l'application, 2 à 3 min pour les 6 014 cas en bloc.
- **Solidité du gain** (intervalles à 95 %, bootstrap sur les jours ; `robustness.py`) :

  | Gain du HGB | Ensemble | Juillet | Août |
  | --- | --- | --- | --- |
  | face à « même heure J−7 » | +25 % [+20 ; +31] | +27 % | +22 % |
  | face à la médiane des 4 semaines | +18 % [+10 ; +25] | +6 % [−3 ; +14] | +36 % [+26 ; +44] |

  - Le gain tient aux heures de pointe : +20 à +24 % face à la médiane, contre +7 % la nuit.
  - Face à la médiane, il vient surtout d'août : la médiane y est en retard sur la baisse des vacances (biais de +10,5).
  - **En régime stable, le modèle vaut une médiane ; il apporte surtout lors des changements de régime.** Semaine par semaine, le gain sur la médiane va de +32 à +54 % pendant la baisse des vacances (27/07 → 17/08), et reste proche de 0 les semaines stables. À la reprise de fin août, aucune méthode n'anticipe la remontée.
  - La semaine du 20/07, le HGB perd face à la médiane (−28 %) : ses entrées lisent la semaine du 13/07, décalée de 2 h dans les données d'E1.

**EXP-E2-04, intérêt du contexte** ([fiche](../experiments/EXP-E2-04.md)) : _résultats à compléter._

**EXP-E2-05, robustesse du MLP aux pannes** ([fiche](../experiments/EXP-E2-05.md)) : _résultats à compléter._

**Test final** (octobre-novembre, lu une seule fois) : _à compléter._

## 7. Cas d'échec

- **Sites en panne pendant l'été.** C'est le cas de la face 104 rue d'Aubervilliers et de 3 autres sites : leur semaine visible a moins de 84 h mesurées. Le MLP refuse alors ces cas (`mlp_window_too_sparse`, 320 cas) et la référence prend le relais. Le refus est visible dans `status_reason`, jamais caché.
- **La médiane sur 4 semaines surestime l'été (+8,5 vélos/h).** Elle copie des semaines plus chargées que le mois d'août : une méthode simple « stable » n'est pas forcément sans biais.
- **Les mesures d'E1 sont décalées de 2 h** les 9, 10, 13, 15 et 16 juillet sur la plupart des compteurs : le pic du matin tombe à 7 h au lieu de 9 h. Toutes les méthodes se trompent ces jours-là, et sans eux, la MAE du HGB passe de 22,25 à 19,25. C'est signalé à E1.
- **L'été est plus difficile que juin.** L'erreur passe d'environ 17,5 vélos/h sur juin à environ 22 en validation (vacances, 14 juillet, 15 août).

## 8. Contribution et utilisation des partenaires

| Partenaire | Ce qu'on a reçu | Ce qu'ils utilisent de nous |
| --- | --- | --- |
| E1 | L'instantané, les mesures publiées, le contexte (`e1-context/0.3.0`) et la date de début des données | Retours sur les zéros et les valeurs remplies (D-11) |
| E4 | Les cas `proto-v1` et le code de score | Nos prévisions (zips livrés), notées par leur `backtest.py` ; scores identiques aux nôtres |
| E3 | La liste des sites réservés | Le MLP E2 transféré aux nouveaux sites (« MLP E2 transféré »), et `predict_24h`, `write_predictions` et `train.load_model` |
| E5 | La signature `predict_24h(case, history, variant)` | `predict_24h` avec `reference`, `reference_profile`, `hgb` (par défaut) et `mlp` ; codes de refus et repli |

## 9. Recommandation et limites

**Recommandation** : servir le **HGB avec contexte** (`e2-hgb-ctx-20260701-s0-b357`) dans l'application, avec repli sur la référence. Le MLP reste disponible : il est aussi bon en moyenne, mais il dépend du nombre d'heures mesurées. _Compléter avec les conclusions de 04 et 05._

**Limites** :
- protocole `proto-v1` non validé par le professeur ;
- validation sur l'été seulement : 2 jours fériés et aucune grève dans la période ;
- modèles figés au 01/07, sans réapprentissage ;
- reproductibilité exacte seulement sur la même machine (D-23).

Incohérences laissées ouvertes, documentées dans le suivi (§10) :
- `available_at` est absent des mesures d'E1, si bien que le délai de 24 h est supposé fixe (C3, M2) ;
- les semaines de changement d'heure décalent la référence d'une heure (I3) ;
- le contrat commun reste dans `src/models/schemas.py` (I1).

## 10. Refaire les expériences

Voir le [README du dossier](../../src/models/known/README.md#refaire-les-expériences) et les notebooks `notebooks/E2_*.ipynb`. On peut :
- rescorer une expérience, en environ 5 min ;
- recalculer une méthode, en 2 à 3 min ;
- prévoir un cas au choix, en quelques secondes ;
- réapprendre un modèle, en environ 5 min.

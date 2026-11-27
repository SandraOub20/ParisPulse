# Rapport de l'équipe 2 : prévision à 24 h sur les sites connus

Équipe : Idir, Esther, Ania, Emmanuelle. Version du 2026-11-28. Le détail est dans le [suivi](E2_SUIVI.md), les fiches d'expérience dans [reports/experiments/](../experiments/), et la prise en main dans [E2_PRISE_EN_MAIN.md](E2_PRISE_EN_MAIN.md).

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
| **HGB** | Gradient boosting par histogrammes, perte L1. Variables : décalages, niveaux récents, calendrier, contexte. Pas d'identifiant de compteur : le modèle est partagé | Quelques minutes d'apprentissage sur CPU ; 342 arbres |

Les deux modèles passent par `predict_24h`, le même point d'entrée que l'application et E3. Ses contrôles d'éligibilité portent sur l'instantané, la coupure, le site présent à l'apprentissage et la version du contexte. En cas de refus, le repli sur la référence se fait avec un code exact.

## 5. Vérifications

- Chaque fonction est testée sur de petits exemples calculés à la main. La suite `pytest` complète passe (460 tests).
- Le calcul en bloc d'une expérience donne **les mêmes fichiers** que le calcul cas par cas, à 1e-3 près (MLP, arrondi `float32`), en 2 à 3 min au lieu d'environ 45.
- Les fichiers de prévision ont le format du contrat d'E4 : 24 lignes par cas, aucun doublon, vide plutôt que 0. C'est vérifié avec `check_forecasts.py` d'E4 sur toutes les livraisons (03, 04, les 5 niveaux de 05 et le test). La seule alerte est le `fit_cutoff` vide des références, qui n'apprennent rien.
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

**EXP-E2-04, intérêt du contexte** ([fiche](../experiments/EXP-E2-04.md)) : chaque modèle est comparé avec et sans contexte, à méthode, graine et réglages égaux. Le seuil de bruit est de 0,357, fixé au gel.

| | Avec contexte | Sans contexte | Gain | Compteurs améliorés |
| --- | --- | --- | --- | --- |
| HGB | 22,25 | 22,90 | **+0,64** | 86 / 95 |
| MLP | 22,23 | 23,38 | **+1,15** | 88 / 95 |

- **Le gain vient surtout du calendrier.** Les jours fériés, le contexte évite une erreur de 6 à 10 vélos/h. Retirer le calendrier coûte 0,48 au HGB, retirer la météo 0,17 (sous le seuil), et retirer les grèves rien du tout (il n'y en a aucune en été).
- **Les jours de pluie prévue, le contexte dégrade**, de −0,6 pour le HGB et −3,2 pour le MLP, sur 5 jours seulement. Le test le confirme pour le MLP : 21,1 contre 19,4 pour le HGB sur 14 jours de pluie prévue.
- Décision : le HGB avec contexte reste servi.

**EXP-E2-05, robustesse du MLP aux pannes** ([fiche](../experiments/EXP-E2-05.md), comparaison individuelle d'Idir). On compare 4 bras :
- A, le MLP actuel, qui refuse sous 84 h mesurées puis se replie ;
- A′, les mêmes poids, forcés à prévoir dès 24 h ;
- B, un MLP appris en masquant au hasard des blocs de 24 à 144 h sur 10 % des exemples, avec un seuil de 24 h ;
- R, la médiane.

On efface ensuite une partie de la semaine visible des 6 014 cas. MAE en lecture système, moyenne des 3 graines :

| Niveau | A | A′ | B | R |
| --- | --- | --- | --- | --- |
| rien effacé | 22,39 | 22,37 | 22,73 | 27,01 |
| 48 dernières heures | 27,93 | 27,91 | **25,17** | 27,01 |
| 96 dernières heures | 29,75 (repli) | 36,45 | **26,15** | 27,01 |
| 144 dernières heures | 28,49 (repli) | 46,00 | **28,20** | 30,26 |
| la moitié au hasard | 27,36 | 27,74 | **25,69** | 28,64 |

- **Le masquage aide nettement dès que la semaine est trouée.** Sur les vraies semaines de 83 à 24 h mesurées, B fait 15,7 contre 24,1 pour le repli de A. B est aussi beaucoup plus stable entre graines.
- Sans masquage, le MLP forcé à prévoir s'effondre (46,0).
- **Mais B perd 0,39 sur les semaines complètes**, juste au-delà du bruit entre graines (0,36). La règle figée demandait que B ne perde pas plus que ce bruit : **A reste le MLP servi.**
- Piste chiffrée, à mesurer dans une nouvelle fiche : servir A sur les semaines complètes et B entre 24 et 83 h, au lieu du repli.

**Test final** ([fiche](../experiments/EXP-E2-TEST.md)) : octobre-novembre 2026, lu une seule fois après le gel D-07. 3 966 cas comparés sur 43 jours, période qui contient la Toussaint, 2 jours fériés et 3 jours de grève.

| Méthode | MAE macro | Gain / médiane | Gain / J−7 |
| --- | --- | --- | --- |
| MLP A | **17,41** | +37 % [+25 ; +47] | +31 % [+19 ; +40] |
| HGB (servi) | 19,86 | +28 % [+19 ; +35] | +21 % [+12 ; +29] |
| Même heure J−7 | 25,16 | | |
| Médiane 4 semaines | 27,64 | | |

- **Les choix tiennent hors période** : les deux modèles battent nettement les références, aux heures de pointe comme au total.
- **La nuance de la validation se confirme.** En semaines normales, le gain sur la médiane n'est pas significatif : +8 % [−14 ; +25] pour le HGB. Pendant les transitions et les vacances, il va de +35 à +57 %.
- **Hors période, le MLP bat le HGB** (−2,45 vélos/h), surtout pendant les ruptures et les jours fériés ou de grève. Le HGB reste meilleur en semaines normales et les jours de pluie.
- Le MLP B, masqué et calculé pour information, fait 16,86 : sur des semaines réelles d'automne, le masquage ne coûte rien.
- Aucun choix n'est changé d'après le test (D-07).

## 7. Cas d'échec

- **Sites en panne pendant l'été.** C'est le cas de la face 104 rue d'Aubervilliers et de 3 autres sites : leur semaine visible a moins de 84 h mesurées. Le MLP refuse alors ces cas (`mlp_window_too_sparse`, 320 cas) et la référence prend le relais. Le refus est visible dans `status_reason`, jamais caché. Sur ces 320 cas, aucune méthode ne fait bien : HGB 29,3, J−7 29,6, médiane 30,3. Toutes surestiment de +23 à +31 vélos/h, parce qu'au retour d'une panne, le compteur repart plus bas que son niveau d'avant.
- **La médiane sur 4 semaines surestime l'été (+8,5 vélos/h).** Elle copie des semaines plus chargées que le mois d'août : une méthode simple « stable » n'est pas forcément sans biais.
- **Les mesures d'E1 sont décalées de 2 h** les 9, 10, 13, 15 et 16 juillet sur la plupart des compteurs : le pic du matin tombe à 7 h au lieu de 9 h. Toutes les méthodes se trompent ces jours-là, et sans eux, la MAE du HGB passe de 22,25 à 19,25. Le défaut est consigné dans le suivi (§8) pour E1.
- **L'été est la période la plus difficile** : environ 22 vélos/h en validation, contre 17 à 20 sur le test d'automne. Les vacances, le 14 juillet, le 15 août et les jours décalés y pèsent. Le contrôle de juin (environ 17,5) est dans la période d'apprentissage et ne se compare pas directement.

## 8. Contribution et utilisation des partenaires

| Partenaire | Ce qu'on a reçu | Ce qu'ils utilisent de nous |
| --- | --- | --- |
| E1 | L'instantané, les mesures publiées, le contexte (`e1-context/0.3.0`) et la date de début des données | Nos retours : zéros et valeurs remplies (D-11), décalage de 2 h de juillet |
| E4 | Les cas `proto-v1` et le code de score | Les prévisions d'EXP-E2-03, notées par leur `backtest.py`, avec des scores identiques aux nôtres ; celles d'EXP-E2-04, 05 et du test sont livrées en zip, et leur score officiel reste à confirmer |
| E3 | La liste des sites réservés | Notre MLP, transféré aux nouveaux sites, ainsi que `predict_24h`, `write_predictions` et `train.load_model` |
| E5 | La signature `predict_24h(case, history, variant)` | `predict_24h` avec `reference`, `reference_profile`, `hgb` (par défaut) et `mlp` ; codes de refus et repli |

## 9. Recommandation et limites

**Recommandation** : servir le **HGB avec contexte** (`e2-hgb-ctx-20260701-s0-b357`) dans l'application, avec repli sur la référence. Le MLP reste disponible : à égalité en validation, meilleur sur le test, mais il dépend du nombre d'heures mesurées et se replie sur les semaines trouées.
- **Garder le contexte**, surtout pour le calendrier : il apporte beaucoup les jours fériés.
- **Garder le MLP A et son repli** (EXP-E2-05). Pour une suite, mesurer la combinaison A / B, avec B en remplacement du repli sur les semaines trouées.
- Le modèle bat nettement la référence simple « même heure J−7 » (+25 % en validation, +21 à +31 % sur le test). Face à la médiane des 4 semaines, il apporte surtout lors des changements de régime ; en régime stable, il fait à peu près comme elle. Ce constat est confirmé sur le test.
- **À revoir dans une suite : le choix entre MLP et HGB**, sur une validation qui contienne des ruptures. L'été les donnait à égalité, alors que l'automne favorise le MLP. Ce choix ne peut pas se faire sur le test.

**Un MLP plus complexe ferait-il mieux ?** Ce n'est pas testé : on a gardé les réglages par défaut, sans recherche d'architecture. Plusieurs indices montrent cependant que la limite vient de l'**information disponible** plutôt que de la capacité du réseau :
- deux familles très différentes finissent au même niveau (MLP 22,23, HGB 22,25) ;
- l'arrêt anticipé arrive tôt : meilleure époque 20 à 24, sur 100 possibles, puis 8 époques sans progrès. Après ce point, l'erreur d'apprentissage continue de baisser (de 0,175 à 0,170 pour la graine 0), alors que celle de juin **plafonne** (de 0,162 à 0,165). Le réseau n'exploite déjà plus sa capacité actuelle ;
- ce qui a aidé, c'est de **régulariser**, pas de grossir : le masquage à 10 % fait baisser l'erreur de contrôle sur juin, de 17,68 à 17,32 (EXP-E2-05) ;
- l'écart entre graines (0,36) dépasse déjà l'écart entre le MLP et le HGB (0,02) ;
- comme le notent Zeng et al., des modèles simples égalent souvent des réseaux plus complexes.

Les erreurs restantes viennent surtout de ce que les entrées ne contiennent pas : la reprise de fin août, que personne n'anticipe, et les jours décalés dans les données. Des informations nouvelles (l'année précédente à la même période, un calendrier plus fin) sont donc une meilleure piste qu'un réseau plus gros. Une vérification simple serait un MLP 2 à 3 fois plus large, sur 3 graines, comparé sur la validation.

**Limites** :
- protocole `proto-v1` non validé par le professeur ;
- une seule période de validation, l'été : 2 jours fériés et aucune grève. Le choix entre MLP et HGB s'est fait sans rupture d'automne ;
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

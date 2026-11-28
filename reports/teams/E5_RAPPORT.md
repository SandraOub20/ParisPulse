# ParisPulse - Rapport de l'équipe 5 (application et intégration)

Version du 28/11/2026, établie sur la branche `Team5-VF-docs` issue de `dev` (commit `8268d23`).
Tous les chiffres viennent des fichiers du dépôt ou de calculs refaits sur l'instantané
`hist-20261117` ; la source est indiquée à chaque fois.

## 1. Objectif

L'équipe 5 livre l'application qui rend le travail des autres équipes utilisable : choisir un
compteur parisien et une date, prévoir les 24 heures suivantes avec la méthode désignée par le
protocole, puis comparer la prévision aux mesures réelles, avec la provenance et un export.

Contraintes tenues :

- ne pas recopier les calculs : l'application appelle les fonctions d'E2 et d'E3 ;
- ne transmettre aux modèles que l'information disponible à l'origine ;
- montrer la prévision **avant** les mesures cibles ;
- distinguer sites connus et nouveaux sites, et rendre visibles les replis et les échecs.

Répartition dans l'équipe : intégration E3 (Chronos-2), évaluation E4, visualisations, tests et
recette, documentation et démonstration.

## 2. Architecture

Interface **Streamlit** (`src/app/streamlit_app.py`) au-dessus d'une couche de service
(`src/app/service.py`) qui choisit le moteur et contrôle les entrées et sorties. Schéma complet
et tableau des échanges : [ARCHITECTURE.md, section 8](../../doc/ARCHITECTURE.md#8-architecture-réalisée-de-lapplication-e5).

| Fichier | Rôle |
| --- | --- |
| `streamlit_app.py` | Carte, sélection, onglets, graphiques, téléchargements |
| `service.py` | Routage E2/E3, historique autorisé, contrôle des 24 lignes, révélation |
| `v1_service.py` | Lecture de l'instantané E1 et des cas E4, MAE d'un cas |
| `export.py` | ZIP de l'étude : cas, prévisions, coûts, manifeste, observations après comparaison |
| `dashboard/coverage.py`, `dashboard/forecast_case.py` | Graphiques des données manquantes et de la prévision |

Choix techniques :

- **Routage par le cas E4.** `eval.cases.forecasting_team` désigne le moteur à partir du rôle
  spatial : `S_train` → E2, `S_dev_new` / `S_test_new` → E3. L'interface ne décide pas seule.
- **Historique filtré par E5.** `published_history` coupe à `origine − 24 h` (délai de
  publication simulé, `config/project.yaml`) et, pour un nouveau site, au budget local.
- **Lecture d'un seul compteur.** `counts.csv` fait 414 Mo ; il est lu par blocs pour ne garder
  qu'un compteur, puis mis en cache par Streamlit.
- **Contrat vérifié à chaque calcul** (`validate_forecast`) : 24 horizons, même origine, même
  scénario, aucune valeur pour une heure en échec.

## 3. Intégration E1

- **Inventaire** : 113 compteurs directionnels sur 58 sites, tous localisés ; rôles 97 `S_train`,
  5 `S_dev_new`, 10 `S_test_new`, 1 exclu (source : `counters.csv`, `inventory_quality.csv`).
- **Carte** : couleur par moteur (turquoise E2, bleu E3, gris inventaire seul) ; sélection par
  clic ou par menu, sens distingués.
- **Historique** : onglet *Historique disponible* limité au passé publié ; onglet *Données
  manquantes* séparant mesures, heures estimées par E1 et heures sans valeur.
- **Contexte** : calendrier, grèves et météo prévue (`context.csv`, version `e1-context/0.3.0`),
  affichés et transmis au HGB.

## 4. Intégration E2

- **HGB par défaut** sur les sites connus : gradient boosting avec contexte, appris sur les
  cibles du 14/11/2023 au 29/06/2026, coupure au 1er juillet 2026 (metadata
  `artifacts/models/e2-hgb-ctx-20260701-s0-b357/`).
- **Références** : même heure la semaine précédente, médiane des quatre semaines ; et leur
  comparaison sur la même date.
- **Replis** : si le HGB refuse un cas (date avant sa coupure, contexte absent, site hors
  apprentissage…), la référence répond ; l'écran l'annonce et chaque heure porte sa raison.
  Vérifié : Porte de Bagnolet E-O, 20/06/2026 → 24 heures en repli, MAE 9,0.
- Le choix du HGB suit la règle d'E2 ([EXP-E2-03](../experiments/EXP-E2-03.md)) : MAE 22,25 contre
  22,23 pour le MLP, écart inférieur à la dispersion entre graines (0,36).

## 5. Intégration E3

- **Chronos-2 gelé** en direct, sur l'historique local autorisé (24, 72 ou 168 h).
- **Chronos-2 adapté v2** : Chronos-2 n'est pas réentraîné ; sa prévision est mélangée avec la
  médiane locale de la même heure, `max(0, poids × Chronos + (1 − poids) × profil)`. Les poids
  0,80 / 0,80 / 0,85 ont été **choisis** par E3 sur une grille (0 à 1, pas 0,05) à partir des cas
  de validation `S_dev_new` ([fiche E3](../experiments/E3-chronos-adapted-v2.md)). Le code
  (`src/models/new/adapt.py`) applique bien cette formule. La documentation de l'application
  disait que les poids avaient été « appris » : corrigé dans `src/app/README.md` et dans le
  message à l'écran.
- **Comparaison avant/après adaptation** sur le même support, vérifié par `verify_same_support`.
- **Archives E3** (TimesFM, MLP, Chronos v1) consultables sur leurs cas enregistrés.
- Coût mesuré : premier calcul 109 s (téléchargement et chargement du modèle), puis 0,1 à 0,4 s.

## 6. Intégration E4

- **Cas** : `data/evaluation/proto-v1/cases.csv` fournit les dates et bornes de support ; le bouton
  **Télécharger cases.csv** exporte la ligne au format E4. Une date libre crée un cas
  `technique-e5` sans modifier les fichiers d'E4.
- **Score par cas** : MAE sur les seules heures réellement mesurées ; une heure absente n'est pas
  une erreur de zéro ; deux méthodes comparées utilisent les mêmes heures.
- **Scores officiels** (MAE moyenne entre compteurs, couverture, cas complets communs) : présents
  dans `data/evaluation/proto-v1/EXP-E2|EXP-E3/scores.csv` et repris dans le README ; **pas
  affichés dans l'application**.

## 7. Interface finale

Fonctionnalités disponibles (détail : [guide de l'application](../../src/app/README.md)) :

| Écran | Fonctionnalité |
| --- | --- |
| Barre latérale | Instantané, périmètre (tout le réseau, sites connus, nouveaux sites) |
| Carte et menu | Choix du compteur et du sens |
| Réglages | Date ou cas E4, budget local, méthode, archives E3, date libre |
| Prévision | Courbe, mesures réelles, indicateurs (heures prédites, replis, MAE, temps), 24 lignes |
| Onglets | Historique disponible, Données manquantes, Contexte E1 |
| Export | `cases.csv` et ZIP de l'étude |

Captures à ajouter avant la remise : carte du réseau ; démo 1 (courbe HGB et mesures) ;
démo 2 (gelé contre adapté) ; message de repli de la démo 3a ; onglet Données manquantes de la
démo 3b.

## 8. Expérimentation

Cas rejoués dans l'interface le 28/11/2026, toutes dates en validation
([parcours détaillés](E5_DEMONSTRATION.md)) :

| Cas | Méthode | Résultat |
| --- | --- | --- |
| Magenta NO-SE, 31/08 | HGB / semaine précédente / médiane 4 sem. | MAE 45,5 / 47,2 / 67,3 ; 24 h comparées |
| Kellermann E-O, 12/08, budget 24 h | Chronos-2 gelé / adapté v2 | 16,3 / 14,4 |
| Kellermann E-O, 12/08, budget 168 h | Chronos-2 gelé / adapté v2 | 6,8 / 6,5 |
| Porte de Bagnolet E-O, 20/06 | HGB → repli | refus annoncé, 24 h en repli, MAE 9,0 |
| Quai de la Tournelle SE-NO, 12/08 | HGB | 12 heures mesurées sur 24, MAE 73,4 |

Balayages faits pour choisir ces cas :

- **HGB** sur les 97 compteurs `S_train` × 3 dates (15/07, 12/08, 31/08), soit 291 cas :
  285 prévisions complètes. Les 6 autres concernent « Face 104 rue d'Aubervilliers » (deux
  sens), sans mesure depuis le 19/02/2026 ; dans l'application, ce compteur ne propose que des
  dates antérieures, où le HGB refuse et la référence répond. Le 31/08, la MAE du cas médiane
  est de 21,7 vélos/h sur 92 cas entièrement mesurés.
- **Chronos-2** sur les 5 sites `S_dev_new` × 3 budgets, le 12/08 : l'adaptée fait mieux dans
  10 cas sur 15. L'historique compte davantage : sur Kellermann, l'erreur passe de 16,3 à 6,8
  entre 24 h et 168 h.

Interprétation : ces cas illustrent le fonctionnement ; ils ne remplacent pas les scores E4.
Les sites `S_dev_new` ont servi à choisir les poids de l'adaptation : leurs gains sont optimistes.

Échec relevé : le HGB prévoit « 39 quai François Mauriac » le 31/08/2026 alors que le compteur
ne mesure plus depuis le 5 juillet ; 24 heures sont affichées comme disponibles, sans
avertissement, et aucune ne peut être évaluée. À signaler à E2.

## 9. Tests

- `./run.sh test` : **428 tests passent** sur `dev` (28/11/2026), dont `test_v1_service.py` et
  `test_v2_service.py` (parcours de l'application : prévision, export masqué puis révélé),
  `test_dashboard_coverage.py`, et les tests de validation CSV des prévisions.
- **Lancement vérifié** avec la commande Windows du README : le serveur répond
  (`/_stcore/health` → `ok`).
- **Parcours interface** : les 5 cas du §8 rejoués avec `streamlit.testing`, sans exception.
- `./run.sh check` signale 4 erreurs de lint et 22 fichiers à reformater.
- Travail de fiabilité disponible sur la branche `Team5-fiabilité`, **pas encore fusionné dans
  `dev`** : contrôle de l'historique avant le calcul, messages d'erreur lisibles, `scores.csv` et
  empreintes SHA-256 dans l'export, parcours sur 6 cas réels. Copie neuve testée sur cette
  branche (installation 17 s avec cache, tests passés, application lancée).

## 10. Conclusion

L'application couvre les deux situations du sujet : sites connus avec le HGB et ses replis,
nouveaux sites avec Chronos-2 gelé et adapté sur un budget local. Elle montre la prévision avant
les mesures, garde la provenance et s'exporte.

Limites et problèmes non résolus :

- La validation du protocole par le professeur n'est pas enregistrée (`validated_at: null`).
- Les scores officiels E4 ne sont pas affichés dans l'application ; la MAE affichée concerne un
  seul cas.
- Le MLP d'E2 n'est pas proposé dans l'application.
- Le HGB ne signale pas un compteur sans mesure récente (§8).
- L'adaptation v2 est évaluée sur les cas qui ont servi à choisir ses poids.
- Une partie des dates proposées pour les sites `S_test_new` tombe dans le test final.
- `python -m src.eval.protocol` échoue (`KeyError: 'status'`).
- Lint et format non conformes ; plusieurs modules de `dashboard/` et `counter_map.py` ne sont
  pas utilisés.

Perspectives : afficher les scores E4 et la couverture dans l'application ; fusionner le travail
de fiabilité ; ajouter un contrôle de fraîcheur des mesures avant le HGB ; évaluer l'adaptation
sur `S_test_new` après le gel des choix.

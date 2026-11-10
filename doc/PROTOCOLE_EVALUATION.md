# ParisPulse - Protocole d'évaluation proposé

Version du **10 novembre 2026**. Responsable proposé : E4 avec E1, E2, E3 et E5. **Statut : proposé, à faire valider par le professeur avant les comparaisons utilisées pour choisir les modèles.** Le sujet l'exige dans « Les règles communes pour comparer les méthodes ». Ce dossier ne constitue pas cette validation.

## 1. Questions et unités

1. **Sites connus :** comment prévoir un compteur dont les données passées participent à l'apprentissage ? Quel est l'effet d'une méthode ou d'une information supplémentaire ?
2. **Nouveaux sites :** une méthode apprise ailleurs prévoit-elle avec peu de mesures locales ? Son adaptation sur ces seules mesures aide-t-elle ?
3. **Système livré :** quels cas reçoivent une prévision complète, à quel coût et avec quels replis ?

Un **cas** est un compteur et une origine de prévision, avec scénario et budget d'information fixés. Il comporte 24 intervalles horaires cibles. Pour nouveaux sites, la variante gelée, l'adaptée et la référence partagent le même cas et le même support local. Les scénarios sont rapportés séparément.

Une cible est un nombre de passages, pas de personnes distinctes. Un compteur/direction et un site physique sont deux unités différentes ; les séparations spatiales portent sur des groupes de sites vérifiés.

## 2. Temps et information autorisée

Pour une origine `t0` et `h = 1…24` :

```text
target_start(h) = t0 + (h - 1) heures
target_end(h)   = t0 + h heures
entrée admissible seulement si available_at <= t0
```

Les calculs sont en UTC ; calendrier et affichage en `Europe/Paris`. Une origine quotidienne à minuit local est une première proposition. L'horizon reste 24 heures écoulées : près d'un changement d'heure, les origines quotidiennes peuvent laisser une heure non couverte ou répéter une cible. Rapporter la couverture exacte et ne pas confondre les cibles répétées avec des observations indépendantes.

### Délai de publication

Le portail courant annonce J−1 sans donner la disponibilité historique exacte de chaque ligne. Proposition : `available_at = interval_end + 24 h`, simulation clairement étiquetée, avec sensibilité à 48 h si possible. Un protocole idéal à disponibilité immédiate est distinct, si l'enseignant le préfère ; ne pas mélanger les scores.

Une latence constante de 24 h ne prouve pas un rejeu exact de publications quotidiennes. Les données téléchargées aujourd'hui peuvent inclure des corrections futures par rapport à l'origine simulée. Ces limites sont indiquées dans les résultats. L'heure de téléchargement n'est pas l'heure de publication historique.

### Règles d'absence de fuite

- Chaque entrée, profil local, remplissage et normalisation respecte les données autorisées. Pas d'interpolation vers le futur ni moyenne centrée.
- Les paramètres du modèle et transformations globales sont entraînés avant leur `fit_cutoff <= origin` ; le futur de validation/test n'entre pas dans cet apprentissage.
- Pour entraîner une fenêtre à la coupure `F`, toutes ses cibles nécessaires doivent être disponibles à `F`. Purger les fenêtres chevauchant les blocs et la fin d'apprentissage selon horizon + latence.
- Le calendrier futur connu est admissible ; une observation météo future est réservée à l'analyse après révélation. Un bulletin doit avoir été émis et disponible avant l'origine pour être une entrée.
- La sélection de méthode, la calibration, la sélection de donneurs et le routage ne consomment pas des scores dont les observations seraient encore indisponibles à leur date de décision.
- La révélation ne recalcule pas les prévisions et ne met pas à jour un modèle avant de montrer ses erreurs.

## 3. Séparations temporelles proposées

Après audit, la plage actuellement visible permet la proposition suivante. Les frontières sont à minuit local puis converties en UTC ; les règles d'admissibilité peuvent enlever les dernières fenêtres d'un bloc.

| Bloc | Proposition | Usage |
| --- | --- | --- |
| Apprentissage initial | À partir du 11/10/2025, jusqu'à la coupure 01/07/2026 | Sources, variables, modèles initiaux et profils donneurs |
| Validation | Juillet–août 2026 | Choix de méthodes et de paramètres, sur versions entraînées au plus tard à chaque coupure |
| Diagnostic/calibration | Septembre 2026 | Diagnostic supplémentaire ou calibration d'intervalles sans retoucher le test |
| Test final | Origines d'octobre 2026 | Bilan de la version et du routage figés |

Exemple exécutable : versions au 01/07 et 01/08 pour validation, sélection au 01/09 sur les seules cibles alors disponibles, puis réentraînement admissible au 01/09 et gel de ce modèle pendant septembre et octobre. Si intervalles, calibration au 01/10 avec les seuls résidus disponibles à cette date. La fin de septembre n'est donc pas intégralement utilisable pour cette calibration.

Les observations d'entrée peuvent s'actualiser à chaque origine même si le modèle reste gelé. Un modèle final entraîné au 01/09 ne sert pas à rejouer juillet. Les archives 2016–2025 permettent un autre découpage si leur qualité ou la question scientifique le justifie ; changer avant sélection et conserver la décision de validation.

Les critères de sélection d'échantillon sont fondés sur les métadonnées et la période autorisée avant le test. Un audit rétrospectif de la qualité du test peut être publié, mais ne doit pas servir à choisir les sites les plus faciles après coup.

## 4. Séparation des sites

Former trois groupes disjoints avant les expériences :

| Groupe | Rôle | Usage permis |
| --- | --- | --- |
| `S_train` | Sites connus / donneurs | Apprentissage global sur le passé, validation et test temporels pour E2 |
| `S_dev_new` | Nouveaux sites de développement | Choix de méthode d'adaptation et de budget sur le bloc de validation ; jamais dans l'apprentissage initial global |
| `S_test_new` | Nouveaux sites finaux | Aucun entraînement global ni réglage ; seul support local autorisé pour l'inférence et l'adaptation finale |

Les proportions et effectifs sont décidés après inventaire, sans taille arbitraire imposée ici. Réserver plusieurs sites si les données le permettent, avec des profils différents. Publier les listes ou empreintes, ainsi que la distribution de leurs profils.

Garder toutes les directions et alias confirmés d'un même lieu dans le même groupe. Si le rattachement est incertain, le documenter et éviter de répartir des séries potentiellement identiques entre donneurs et réservés. Un modèle réutilisé d'E2 est acceptable pour E3 seulement si son apprentissage a exclu `S_dev_new` et `S_test_new`.

Un modèle public peut avoir vu des séries similaires ou ces données en préentraînement. Déclarer ce qui est connu et inconnu ; l'exclusion du projet est vérifiable, une indépendance mondiale du préentraînement ne l'est pas toujours.

## 5. Expérience nouveaux sites

### Support local

Budget principal proposé : **7 × 24 heures écoulées** ; approfondissement : 1 et 3 jours. Un budget est un intervalle fixe avec ses manques, pas une sélection des journées complètes les plus favorables.

Sous une latence constante `delta`, définir :

```text
support_end   = origin - delta
support_start = support_end - local_budget_hours
support = observations locales d'intervalles inclus dans cette fenêtre,
          avec interval_end <= support_end et available_at <= origin
```

Ne pas consulter les autres valeurs du site pour normaliser, sélectionner des donneurs, imputer, régler ou adapter. Les paramètres appris chez les donneurs restent autorisés s'ils respectent les coupures. Les contextes externes sont identiques entre variantes et leur rôle est déclaré.

Avec `delta=0`, le cas de sept jours suivi du huitième jour reproduit l'exemple pédagogique du sujet. Avec `delta=24 h`, une lacune d'information sépare le support de la cible : l'afficher et comparer toutes les méthodes dans ce même cadre.

### Comparaison contrôlée

Pour chaque cas :

1. Charger un modèle de base entraîné ailleurs et figé avant l'origine.
2. Construire une fois le support autorisé et conserver son empreinte.
3. Produire la prévision **sans adaptation**, avec ce support en entrée et les paramètres globaux inchangés.
4. Produire la prévision **avec adaptation** à partir du même support. Décrire exactement les paramètres ajustés et leur estimation.
5. Produire une référence recevant le même budget local. Si la référence hebdomadaire manque d'historique, utiliser le repli annoncé ; elle ne reçoit pas sept jours supplémentaires.
6. Enregistrer les sorties avant de lire les observations cibles, puis calculer les scores communs.

Pour un correcteur appris sur des sous-fenêtres du support, leurs entrées et cibles restent dans ce support, avec disponibilité cohérente. Choisir pénalisation et nombre d'étapes sur `S_dev_new`, sans regard sur les cibles de `S_test_new`. Avec un historique trop court pour adapter, déclarer un statut, le temps et le repli ; ne pas utiliser le lendemain caché pour obtenir plus d'exemples.

Répéter sur plusieurs sites et origines. Réinitialiser l'adaptation à chaque cas si le protocole promet toujours L jours locaux ; accumuler des observations entre cas changerait le budget d'information. Faire varier un seul facteur à la fois pour l'étude 1/3/7 jours.

## 6. MAE, couverture et comparabilité

Un cas est **prévu complètement** si les 24 horizons distincts ont chacun une prévision finie, non négative et alignée. Un cas partiel n'entre pas dans la comparaison principale des cas complets ; il reste dans les dénominateurs et causes d'échec.

Pour deux méthodes A et B :

1. Fixer l'ensemble attendu des cas avant de connaître leur réussite.
2. Compter séparément les cas complets de A et B.
3. Prendre l'intersection de ces cas complets, à scénario/budget identiques.
4. Sur cette intersection, noter uniquement les observations réellement mesurées et structurellement valides, avec le même masque pour A et B.
5. Calculer la MAE de chaque compteur sur ses paires évaluables, puis la moyenne non pondérée entre compteurs.

```text
MAE_c = somme des |prévision - observation| évaluables du compteur c
        / nombre de paires évaluables du compteur c
MAE_macro = moyenne des MAE_c pour les compteurs évaluables
couverture_24h = nombre de cas complets / nombre de cas attendus
```

Un compteur sans observation évaluable n'obtient pas une MAE de zéro : afficher `null`, raison et effectif. Rapporter les heures mesurées, compteurs évaluables et cas comparables. Une heure réelle absente n'empêche pas de dire que 24 prévisions ont été produites ; elle limite les erreurs calculables.

Présenter couverture sur tous les cas attendus et, en complément, sur les cas déclarés admissibles par la méthode, sans cacher le premier dénominateur. Si plus de deux méthodes sont comparées, privilégier une intersection commune et publier sa taille ; des comparaisons par paires ne constituent pas automatiquement un classement global sur la même population.

### Résultats requis et secondaires

- Principal : MAE macro, sites connus et nouveaux séparés, variante gelée/adaptée/référence séparées.
- Couverture : cas complets, partiels, sans résultat, causes et taux de repli.
- Coût : entraînement, inférence, adaptation, temps d'attente, mémoire si mesurée, matériel et taille des lots.
- Diagnostics : MAE par compteur/horizon/profil, faibles volumes, manques, zéros prolongés et période inhabituelle.
- Secondaires utiles : biais, RMSE, moyenne globale par observation et gain sur référence sur la même population.

Éviter MAPE comme indicateur principal, à cause des zéros. Ne pas retirer du test les valeurs élevées valides simplement parce qu'elles augmentent l'erreur.

### Système après repli

Évaluer séparément les modèles bruts et le système effectivement proposé dans l'application. Le système peut combiner méthode principale, adaptation et référence selon une règle figée sur validation. Rapporter méthode effective par cas/horizon et effets du repli sur erreur, couverture et coût. Tester cette règle sur des cas non utilisés pour la choisir.

## 7. Fiabilité et approfondissement

Minimum proposé : masquer une fraction annoncée des entrées, puis simuler une panne contiguë, en conservant les mêmes vérités terrain. Comparer erreur, couverture et repli. Choisir niveaux et règles sur validation.

Alternative ou complément : intervalles calibrés sur une période séparée, effectif suffisant, couverture **effective**, largeur et limites par profil. Aucune garantie universelle sous dépendance temporelle ou changement de régime. Une calibration ne peut servir aux origines qui la précèdent.

Pour l'extension, comparer les distributions du premier échantillon et des nouveaux lots. Un gain qui disparaît après élargissement doit être analysé, sans effacer les sites défavorables.

## 8. Validation, gel et contrôles

Le document soumis au professeur fixe : instantané/période, listes de sites, dates et coupures, disponibilité, support local, comparaisons prévues, MAE/couverture/coût, règles de refus/repli, budget et test réservé. Conserver décision, date et version ; ne pas remplir une approbation à la place du professeur.

Après validation, consigner les changements et leur raison. Les modifications influençant les conclusions sont discutées avant les comparaisons de sélection. En fin de J2 ou début de J3, geler modèles, adaptation et routage avant le test final ; aucune décision ultérieure ne s'appuie sur ce test.

Contrôles critiques : score manuel, heure décalée, doublon, prédiction absente, 24 horizons, absence de fuite temporelle, exclusion de toutes les directions d'un site réservé et invariance aux mesures locales masquées. Vérifier aussi la provenance de l'entraînement : figer un modèle entraîné sur le futur ne corrige pas une fuite.

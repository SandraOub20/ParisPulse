# Évaluation des modèles E3 (Chronos-2, Google TimesFM 2.5 et MLP de l'équipe 2) en variante `frozen`

L'équipe 4 a évalué nos prédictions. Les résultats sont disponibles dans le
fichier [scores.csv](https://github.com/SandraOub20/ParisPulse/blob/Team4-sher/data/evaluation/proto-v1/EXP-E3/scores.csv).

**Expérience :** `EXP-E3` · **Scénario :** nouveaux sites (`S_dev_new`) · **Période :** validation  
**Prédictions :** [`data/prediction_results/EXP-E3/`](../../data/prediction_results/EXP-E3/)  
**Protocole des cas :** `proto-v1/cases.csv` · **Snapshot :** `hist-20261117`

## Analyse globale des résultats en version `frozen`

La MAE mesure l'erreur absolue moyenne, en nombre de passages de vélos par heure
(plus elle est basse, mieux c'est). La RMSE pénalise davantage les grandes erreurs
(plus elle est basse, mieux c'est). Le R² est d'autant meilleur qu'il se rapproche
de 1. Un R² égal à 0 signifie que le modèle ne fait pas mieux que la moyenne; un
R² inférieur à 0 signifie qu'il fait moins bien.

Voici les résultats globaux :

| Budget local | Modèle | Cas comparés / 310 | Heures comparées | MAE | RMSE | R² | Biais |
|---:|---|---:|---:|---:|---:|---:|---:|
| 24 h | Chronos-2 | 300 | 7 180 | **26,09** | 57,41 | 0,294 | -10,38 |
| 24 h | Google TimesFM 2.5 | 300 | 7 180 | 27,98 | 60,05 | 0,228 | -4,02 |
| 72 h | Chronos-2 | 305 | 7 300 | 22,83 | 52,27 | 0,418 | -8,98 |
| 72 h | Google TimesFM 2.5 | 305 | 7 300 | **22,55** | **49,92** | **0,469** | -0,87 |
| 168 h | Chronos-2 | 305 | 7 300 | 19,67 | 47,62 | 0,517 | -2,76 |
| 168 h | Google TimesFM 2.5 | 305 | 7 300 | 19,79 | 45,01 | 0,568 | -1,06 |
| 168 h | MLP de l'équipe 2 | 305 | 7 300 | **18,80** | **42,43** | **0,617** | +1,74 |

**Remarque :** le MLP de l'équipe 2 nécessite au moins 7 jours d'historique local.
Il n'a donc pas de résultats pour les budgets de 24 h et 72 h (voir la
documentation de l'équipe 2 pour plus de détails).

## Lecture et conclusion

- À **24 h d'historique**, Chronos-2 obtient la meilleure MAE et le meilleur R²
  des deux modèles disponibles; Google a un biais plus proche de zéro.
- À **72 h**, Google TimesFM 2.5 est légèrement meilleur que Chronos-2 sur la MAE,
  la RMSE et le R².
- À **168 h**, le MLP a les meilleurs scores sur les trois métriques d'erreur et
  d'ajustement. Google reste légèrement meilleur que Chronos sur la RMSE et le R²,
  tandis que Chronos a une MAE très légèrement inférieure.
- Les erreurs diminuent globalement lorsque le budget local passe de 24 h (1 jour)
  à 168 h (7 jours). Cela suggère que les modèles bénéficient d'un historique local
  plus long.
- Le biais négatif de Chronos indique une tendance à sous-prédire si le biais est
  calculé comme `prédit - observé`; le MLP à 168 h présente un léger biais positif.

Le **MLP de l'équipe 2** est donc le candidat le plus prometteur pour les cas
disposant d'au moins 168 h (7 jours) d'historique local. Il n'a pas été évalué ici
avec des budgets de 24 h ou 72 h, donc aucune comparaison n'est possible pour ces
budgets. **Chronos-2** donne également de très bons résultats avec 24 h et 72 h
d'historique.

Selon cette analyse, pour l'application finale, il serait préférable de proposer à l'équipe 5 le **MLP** en
version `frozen` pour les prévisions disposant d'au moins 7 jours d'historique, et
d'étudier l'**adaptation de Chronos-2** pour les budgets de 1 et 3 jours. Cette analyse
est initial : la décision sera validée après discussion avec tous les membres de
l'équipe.

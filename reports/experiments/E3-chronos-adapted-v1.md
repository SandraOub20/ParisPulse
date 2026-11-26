## Méthode d'adaptation de Chronos-v1

Les poids pré-entraînés de Chronos-2 restent gelés. Pour chaque cas, des
pseudo-prévisions à origines glissantes sont produites à l'intérieur de
l'historique local autorisé. Les résidus observés servent à estimer des
corrections additives pour trois plages horaires locales : pointe du matin
(7–10 h), pointe du soir (17–20 h) et autres heures. Les corrections sont
réduites lorsque le nombre de fenêtres est faible et appliquées aux prévisions
seulement si elles améliorent à la fois MAE et RMSE sur ces pseudo-prévisions.
Les prévisions corrigées sont bornées à zéro. L'évaluation E4 mesure ensuite
leur performance sur les cibles E3.

# Comparaison Chronos frozen vs adapted

**Expérience :** EXP-E3 · nouveaux sites · validation · snapshot `hist-20261117`

Les variantes sont évaluées sur les mêmes populations : 300 cas et 7 180 heures
comparées à 24 h d'historique, puis 305 cas et 7 300 heures à 72 h et 168 h.
La couverture est identique entre les variantes pour chaque budget.

| Historique local | MAE frozen | MAE adapted | Écart MAE | RMSE frozen | RMSE adapted | Écart RMSE | R² frozen | R² adapted |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 h | 26,09 | 26,21 | +0,12 | 57,41 | 57,77 | +0,37 | 0,294 | 0,285 |
| 72 h | 22,83 | 23,23 | +0,40 | 52,27 | 52,07 | −0,20 | 0,418 | 0,423 |
| 168 h | 19,67 | 19,92 | +0,26 | 47,62 | 47,56 | −0,06 | 0,517 | 0,518 |



## Conclusion

Chronos adapted n'améliore pas la MAE, quel que soit le budget. À 72 h et 168 h,
la RMSE et le R² progressent très légèrement, mais ces gains restent faibles. À
24 h, adapted est moins bon sur la MAE, la RMSE et le R². Si la MAE est le
critère prioritaire, Chronos frozen reste préférable.

Sources : [scores E4](../../data/evaluation/proto-v1/EXP-E3/scores.csv) et
[scores par compteur](../../data/evaluation/proto-v1/EXP-E3/scores_by_counter.csv).

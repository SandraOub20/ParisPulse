# Google TimesFM 2.5 adapted-v2

**Protocole :** `proto-v1` · `S_dev_new` · Données : validation · snapshot `hist-20261117`

Ce rapport compare Google TimesFM 2.5 en variante gelée (`frozen`) et avec
l'adaptation v2 (`adapted-v2`), puis situe les résultats par rapport à
Chronos-2 adapted-v2. Les scores E4 proviennent du même [scores.csv](../../data/evaluation/proto-v1/EXP-E3/scores.csv).
Les variantes Google ont la même population évaluée pour chaque budget : 300 cas
et 7 180 heures à 24 h, puis 305 cas et 7 300 heures à 72 h et 168 h.

## Méthode d'adaptation

Les poids du modèle TimesFM restent gelés. Pour chaque heure cible, sa prévision
est mélangée avec la médiane historique du même créneau horaire local :

`prévision = max(0, poids × TimesFM + (1 − poids) × profil local)`

Les poids utilisés sont **0,50**, **0,95** et **0,90** pour les budgets de 24 h,
72 h et 168 h. Le profil est calculé à partir du support local causal du cas.
Les poids ont été choisis selon la MAE sur les prévisions évaluables de cinq
compteurs `S_dev_new` du split `validation`.

## Résultats : frozen vs adapted-v2

Les écarts sont calculés comme `adapted-v2 − frozen` ; une baisse de MAE ou de
RMSE est une amélioration, tandis qu'une hausse du R² est préférable.

| Budget local | Cas / heures comparés | MAE frozen | MAE adapted-v2 | Δ MAE | RMSE frozen | RMSE adapted-v2 | Δ RMSE | R² frozen | R² adapted-v2 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 h (1 j) | 300 / 7 180 | 27,98 | **27,68** | **−0,30** | **60,05** | 62,14 | +2,09 | **0,228** | 0,173 |
| 72 h (3 j) | 305 / 7 300 | **22,55** | 22,61 | +0,06 | **49,92** | 50,13 | +0,22 | **0,469** | 0,465 |
| 168 h (7 j) | 305 / 7 300 | **19,79** | 19,90 | +0,12 | **45,01** | 45,04 | +0,03 | **0,568** | 0,568 |

À 24 h, adapted-v2 réduit légèrement la MAE, mais augmente la RMSE et dégrade
le R². À 72 h et 168 h, frozen reste légèrement meilleur sur les trois métriques,
avec des écarts faibles à 168 h. L'adaptation rapproche le biais de zéro à
24 h et 168 h ; à 72 h, le biais reste pratiquement inchangé.

## Comparaison avec Chronos-2 adapted-v2

| Budget local | MAE Google adapted-v2 | MAE Chronos-2 adapted-v2 | RMSE Google adapted-v2 | RMSE Chronos-2 adapted-v2 | R² Google adapted-v2 | R² Chronos-2 adapted-v2 |
|---:|---:|---:|---:|---:|---:|---:|
| 24 h (1 j) | 27,68 | **25,89** | 62,14 | **56,70** | 0,173 | **0,311** |
| 72 h (3 j) | 22,61 | **22,06** | 50,13 | **51,38** | **0,465** | 0,438 |
| 168 h (7 j) | 19,90 | **19,27** | **45,04** | 46,25 | **0,568** | 0,545 |

Chronos-2 adapted-v2 obtient une meilleure MAE aux trois budgets. À 24 h, il est
aussi meilleur en RMSE et en R². À 72 h, Google adapted-v2 a une RMSE légèrement
plus basse et un R² plus élevé ; à 168 h, Google a également une RMSE et un R²
légèrement meilleurs. Le biais de Google adapté est plus proche de zéro à chacun
des budgets, mais cela ne compense pas sa MAE supérieure.

## Conclusion

L'adaptation v2 de Google TimesFM 2.5 n'apporte pas de gain global net par
rapport à sa variante frozen : le bénéfice de MAE à 24 h se fait au prix d'une
RMSE et d'un R² moins bons, tandis que frozen est légèrement supérieur à 72 h
et 168 h. Par rapport à Chronos-2 adapted-v2, Google est moins précis en MAE
pour tous les budgets. Chronos-2 adapted-v2 est donc à privilégier si la MAE
est le critère principal ; Google adapté reste compétitif à 72 h et 168 h sur
RMSE et R², et présente un biais plus proche de zéro.

Ces conclusions portent sur `S_dev_new` en validation. Les poids d'adaptation
ont été choisis sur des cas de cette validation ; une évaluation indépendante
sur le split de test est nécessaire avant d'en faire une conclusion de
généralisation.

## Références

Sources : [scores E4](../../data/evaluation/proto-v1/EXP-E3/scores.csv),
[prédictions Google TimesFM 2.5 adapted-v2](../../data/prediction_results/EXP-E3/e3-google-TimesFM_2.5-adapted-v2-validation-b24-b72-b168.pred.csv),
[prédictions Google TimesFM 2.5 frozen](../../data/prediction_results/EXP-E3/e3-google-TimesFM_2.5-frozen-v1-validation-all.pred.csv),
[poids de mélange TimesFM](../../artifacts/models/e3-timesfm2.5-adapted-v2/blend_weights.json) et
[rapport Chronos-2 adapted-v2](E3-chronos-adapted-v2.md).

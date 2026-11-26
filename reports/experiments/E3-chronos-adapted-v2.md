## Méthode d'adaptation de Chronos-v2 
Chronos-2 reste en frozen au départ : seuls les poids du mélange sont ajustés. Pour chaque heure cible, la prévision est mélangée avec la
médiane historique du même créneau horaire local :
`prévision = max(0, poids × Chronos + (1 − poids) × profil local)`
Les poids appris (avec l'adaptation v2) sont **0,80**, **0,80** et **0,85** pour les budgets 24 h, 72 h
et 168 h. Le profil provient du support local causal du cas. L'apprentissage des poids,
effectué sur une partie des sites réservés à `S_dev_new` (**temporal split = validation**), montre également une amélioration
agrégée par rapport au modèle chronos frozen et au modèle chronos adapted-v1.

### Réserves de l'adaptation v2
- Le profil seul (comme chronos adapted-v1) est moins performant que Chronos frozen ; les gains viennent du
  mélange qui conserve 80–85 % de la prévision Chronos + 20-15 % du profil locale.
- Les poids finaux ont été réajustés pour le modèle adapté, calculé seulement une fois par notre équipe (E3) et sauvegardé dans [Artifact/models](../../artifacts/models/e3-chronos2-adapted-v2/) .

---
# Comparaison de Chronos frozen, adapted-v1 et adapted-v2 (adaptation actuellement retenue)
**Protocole :** `proto-v1` · `S_dev_new` · Données : validation · snapshot `hist-20261117`
Ce rapport compare Chronos frozen, l'ancienne adaptation v1 par la méthode locale par résidus
(`adapted-v1`) et la nouvelle adaptation (`adapted-v2`) par la méthode de mélange avec un profil horaire local et la prévision Chronos-2 frozen.
Les résultats de l'ancienne v1 proviennent du [rapport E3-chronos-adapted-v1](../experiments/E3-chronos-adapted-v1.md) ;
les nouveaux scores (pour les versions frozen, adapted-v1 et adapted-v2) proviennent du dernier [scores.csv](../../data/evaluation/proto-v1/EXP-E3/scores.csv) d'E4.

### Résultats

| Budget local | MAE avec frozen | MAE avec adapted-v1 | MAE adapted-v2 | Δ MAE: adapted-v2 vs frozen | RMSE frozen | RMSE adapted-v1 | RMSE adapted-v2 | Δ RMSE: adapted-v2 vs frozen |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 h (1j) | 26,09 | 26,21 | **25,89** | **−0,20** | 57,41 | 57,77 | **56,70** | **−0,71** |
| 72 h (3j) | 22,83 | 23,23 | **22,06** | **−0,77** | 52,27 | 52,07 | **51,38** | **−0,89** |
| 168 h (7j) | 19,67 | 19,92 | **19,27** | **−0,40** | 47,62 | 47,56 | **46,25** | **−1,37** |
La nouvelle adaptation (v2) améliore les scores agrégés par rapport au modèle gelé pour les trois
budgets et fait mieux que l'ancienne adaptation v1 en MAE et en RMSE. L'ancienne v1 n'améliorait pas la MAE.

## Conclusion
`adapted-v2` est la meilleure version de Chronos-2 parmi celles comparées. Les scores agrégés
observés constituent un résultat prometteur sur `S_dev_new`. Nous proposons de transmettre
à l'équipe 5 la fonction `predict_24` en version `adapted-v2`.


## Références
Sources : [scores E4](../../data/evaluation/proto-v1/EXP-E3/scores.csv),
[rapport de l'adaptation v1 de Chronos (méthode par résidus)](E3-chronos-adapted-v1.md),
[prédictions E3 de Chronos-2 adapted-v2 sur la validation S_dev_new](../../data/prediction_results/EXP-E3/e3-chronos-2-adapted-v2-validation-b24-b72-b168.pred.csv).


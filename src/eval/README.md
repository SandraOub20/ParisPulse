# Évaluation et fiabilité - équipe 4

| Fichier | Travail attendu |
| --- | --- |
| `protocol.py` | Dates, groupes de sites, information autorisée et cas attendus |
| `metrics.py` | Alignement, MAE par compteur puis moyenne, couverture et refus |
| `backtest.py` | Calculs communs, perturbations, diagnostics, extension et test final |

Commencer par un petit score à la main avec heure décalée, doublon ou prévision absente, puis évaluer le premier cas réel. Faire valider le protocole par le professeur avant les comparaisons servant à choisir les modèles.

Vérité terrain : `data/processed/<snapshot_id>/counts.csv`. Prévisions : `data/prediction_results/<experiment_id>/`. Cas : `data/evaluation/<protocol_id>/cases.csv`. Résultats : `data/evaluation/<protocol_id>/<experiment_id>/`.

Comparer sur les mêmes cas complets de 24 heures et le même masque de mesures réelles. Rapporter également les cas attendus, échecs, causes et coûts ; séparer sites connus/nouveaux et modèle brut/système après repli. Une cible absente n'est pas une erreur de zéro.

Transmettre un diagnostic à un partenaire puis vérifier sa réponse. Les fichiers présents sont des instructions, pas un évaluateur implémenté.

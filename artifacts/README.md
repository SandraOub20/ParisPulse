# Artefacts

Sauvegarder ici les artefacts générés par le projet, notamment les modèles
finaux entraînés.

- `models/<model_run_id>/` : poids, paramètres et métadonnées E2/E3.
- `cache/` : résultats réutilisables avec règles d'invalidation E5.
- `exports/` : études et provenance exportées par l'application.

Prévisions CSV dans `data/prediction_results/` ; scores dans `data/evaluation/`. Éviter plusieurs emplacements concurrents pour les mêmes résultats. Les artefacts générés sont exclus de Git, mais leur récupération doit être prévue pour une installation neuve.

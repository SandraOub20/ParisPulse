# Prévisions - équipes 2 et 3

Pour chaque expérience, créer `<experiment_id>/<method_run_id>.pred.csv`, par exemple `EXP-001/equipe-2.reference.pred.csv`, et le fichier de coût associé `<method_run_id>.runs.csv`.

Le CSV de prévision suit `doc/templates/forecasts.csv` : 24 lignes par cas, avec compteur, origine, horizon, prévision, méthode effective, statut et provenance. Les cibles observées en sont absentes. Une prévision impossible reste une ligne vide avec une raison.

E4 compare avec `data/processed/<snapshot_id>/counts.csv` et les cas attendus, puis écrit dans `data/evaluation/`. E5 utilise les mêmes calculs et résultats, avec possibilité de recalcul. Les fichiers d'expérience sont exclus de Git ; conserver leur traçabilité pour la remise.

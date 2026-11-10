# Données traitées

Déposer ici les données historiques traitées au format CSV.

E1 produit un sous-dossier `<snapshot_id>/` avec `counts.csv`, `counters.csv`, `inventory_quality.csv` et `context.csv`, selon les gabarits de `doc/templates/`.

Ce dossier contient la vérité terrain partagée ; les observations futures ne doivent pas être transmises aux calculs de prévision. Conserver UTC, les zéros observés, les valeurs absentes et les alertes distinctement. Parquet peut être utilisé en interne si le CSV commun est maintenu.

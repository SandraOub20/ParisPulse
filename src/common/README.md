# Échanges communs - E1 à E5

- `contracts.py` : définir cas, entrées autorisées, sortie de 24 heures et validations des CSV.
- `config.py` : définir le chargement de la configuration et les chemins relatifs.

Un représentant par équipe adopte les conventions avant l'intégration. Les [contrats](../../doc/CONTRATS.md) et les [gabarits](../../doc/templates/README.md) servent de référence. Les fichiers Python ne contiennent aucune implémentation.

Décisions à figer : identifiants, UTC/heure locale, délai simulé, statut des valeurs manquantes, schémas CSV, versions, signature de calcul et raisons des échecs. Le cas et son `case_id` sont indépendants du modèle pour permettre une comparaison équitable.

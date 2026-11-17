# Nouveaux sites - équipe 3

## Ordre de réalisation

1. Avec E1/E4, réserver des sites entiers et garder les directions d'un même site ensemble.
2. Utiliser une méthode apprise ailleurs, en vérifiant explicitement sa provenance si elle vient d'E2 ou d'un modèle public (load des models dans _core.py).
3. Dans `predict.py`, limiter toutes les entrées locales au support autorisé et produire une version gelée.
4. Dans `adapt.py`, ajuster une partie déclarée de la méthode sur le même support, puis enregistrer une seconde prévision avant la révélation des cibles.
5. Comparer les variantes gelée, adaptée et de référence avec E4 sur plusieurs sites et origines ; étudier aussi les budgets de 1, 3 et 7 jours d'historique local.
6. Fournir à E5 les calculs, les budgets minimaux, les limites, les coûts et les solutions de remplacement.

## Règles de comparabilité

- Même historique et même contexte entre variantes.
- Aucune normalisation sur les mesures masquées.
- Aucun cumul silencieux de données entre cas.
- Les réglages se choisissent sur des sites de développement distincts du test final.

## Livraisons

- Prévisions et coûts dans `data/prediction_results/`
- Paramètres dans `artifacts/models/`
- `support_id` et `adaptation_id` traçables selon les [contrats](../../../doc/CONTRATS.md)

Les modules présents sont des consignes à compléter ; ils ne remplacent pas le protocole officiel du projet.

# Nouveaux sites - équipe 3

1. Avec E1/E4, réserver des sites entiers et garder leurs directions ensemble.
2. Utiliser une méthode apprise ailleurs, en vérifiant la provenance si elle vient d'E2 ou d'un modèle public.
3. Dans `predict.py`, limiter toutes les entrées locales au support autorisé et produire une version gelée.
4. Dans `adapt.py`, ajuster une partie déclarée de la méthode sur le même support, puis enregistrer une seconde prévision avant révélation des cibles.
5. Comparer gelée/adaptée/référence avec E4 sur plusieurs sites, puis étudier éventuellement 1, 3 et 7 jours d'historique.
6. Fournir à E5 les calculs, budgets minimaux, limites, coûts et solutions de remplacement.

Même historique et contexte entre variantes, aucune normalisation sur les mesures masquées, aucun cumul silencieux de données entre cas. Les réglages se choisissent sur des sites de développement distincts du test final.

Sorties : prévisions et coûts dans `data/prediction_results/`, paramètres dans `artifacts/models/`, `support_id` et `adaptation_id` traçables selon les [contrats](../../../doc/CONTRATS.md). Les modules présents sont uniquement des consignes à compléter.

# Sites connus - équipe 2

## Ordre de réalisation

1. Obtenir d'E1 une série réelle et d'E4 une origine avec les données autorisées.
2. Dans `baseline.py`, construire la référence décalée de 168 heures UTC et son repli causal. Joindre par timestamp ; conserver zéro et manque distincts.
3. Vérifier quelques valeurs à la main, produire les 24 horizons et raccorder la fonction/CSV à E4 et E5 avant la fin de la première matinée si les accès fonctionnent.
4. Dans `features.py`, préparer les variables communes, sans information future. Convenir des signatures avec `src/common/`.
5. Dans `train.py`, comparer une méthode justifiée et une variante explicative, par exemple avec/sans contexte, selon le protocole validé. Coordonner l'expérience DL avec E3.
6. Dans `predict.py`, fournir les calculs, les conditions et les exports ; recalculer une autre origine avec E5.
7. Étudier un cas difficile, étendre les compteurs, puis mesurer le test final après gel des choix.

## Livraisons

- À E4 : `.pred.csv`, `.runs.csv`, versions, paramètres, hypothèses et limites.
- À E5 : calcul exécutable, historique minimal, méthodes effectives, refus et repli.
- À E3 si modèle partagé : provenance prouvant l'exclusion des sites réservés.

Mesurer MAE moyenne entre compteurs, couverture en cas complets et coût avec E4. Ne pas régler sur le test final. Conserver les expériences et journaux dans `reports/`.

Ces fichiers sont des gabarits de travail ; les algorithmes restent à écrire.

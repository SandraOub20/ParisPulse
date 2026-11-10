# Prévision - équipes 2 et 3

- [known/](known/README.md) : E2, compteurs déjà présents dans l'apprentissage.
- [new/](new/README.md) : E3, sites entiers exclus de l'apprentissage initial, avec support local limité.
- `registry.py` : interface commune, versions, historique nécessaire, coupure et méthodes de remplacement.

Entrées : données E1 de `data/processed/` et cas E4 de `data/evaluation/<protocol_id>/cases.csv`. Sorties : fonction de calcul réutilisable par E5 et CSV dans `data/prediction_results/<experiment_id>/`.

Un fichier `<method_run_id>.pred.csv` contient 24 lignes par cas, sans observations cibles. Un fichier `.runs.csv` associé conserve le coût et les erreurs de calcul. Poids et paramètres vont dans `artifacts/models/<model_run_id>/`.

Partager les [contrats](../../doc/CONTRATS.md) et les [gabarits](../../doc/templates/README.md). Attribuer explicitement la responsabilité de l'expérience de deep learning obligatoire au collectif. Les fichiers présents sont des instructions, sans implémentation de modèle.

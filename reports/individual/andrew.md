# Journal individuel - Andrew (équipe 3, nouveaux sites)

Format : [doc/SUIVI_ET_REMISE.md §4](../../doc/SUIVI_ET_REMISE.md). Entrées les plus récentes en haut.

---

## 2026-11-24 - Implémentation de la variante gelée Google TimesFM 2.5

- **Date et journée** : 2026-11-24.
- **Question / objectif personnel** : rendre utilisable la variante `frozen` de `google_TimesFM_2.5` pour les nouveaux sites, avec les mêmes règles de support, de causalité, de format de sortie et de coûts que la variante gelée Chronos-2.
- **Travail réalisé et outils utilisés** (VS Code, Python 3.14 pour les tests disponibles dans l'environnement, pandas, numpy, pytest, uv) :
  - Ajout du chargement local Google TimesFM 2.5 dans [_core.py](../../src/models/new/_core.py), avec la configuration officielle `forecast`, `max_context=1024`, `max_horizon=256` et tête continue des quantiles.
  - Implémentation de la branche `variant="frozen"` dans [predict.py](../../src/models/new/predict.py).
  - Utilisation de l'horizon médian lorsque TimesFM retourne son tableau de quantiles ; repli sur la prévision ponctuelle si la sortie du quantile est indisponible.
  - Réindexation des sorties sur les 24 timestamps de `origin`, comme pour Chronos-2, avec écrêtage à zéro des valeurs négatives et motif `negative_quantile_clipped_to_zero`.
  - Ajout de `timesfm[torch]` au groupe `dl` de [pyproject.toml](../../pyproject.toml) et mise à jour de [uv.lock](../../uv.lock).
  - Mise à jour de la documentation E3 dans [README.md](../../src/models/new/README.md).
  - Ajout de deux tests Google TimesFM et adaptation des tests des variantes non implémentées dans [test_new_predict.py](../../tests/test_new_predict.py).
- **Comparaison ou contrôle effectué** :
  - Un faux TimesFM vérifie que l'horizon demandé vaut `forecast_offset + 24`, que le contexte ne contient que les mesures autorisées du support local et que les sorties ont le format commun.
  - Le chemin Google TimesFM réutilise le même filtrage causal, le même support, les mêmes timestamps cibles et les mêmes champs `ForecastResult` que Chronos-2.
  - Un témoin négatif vérifie l'écrêtage à zéro et `status_reason`.
  - Les cas adaptés, ainsi que les variantes Team2, restent explicitement non implémentées au lieu d'être remplacés silencieusement par une sortie partielle.
- **Données, protocole et versions** :
  - Code vérifié sur les cas synthétiques de `test_new_predict.py`, sans données réelles ni score de validation.
  - TimesFM 2.5 chargé depuis `google/timesfm-2.5-200m-pytorch`.
  - La variante reste gelée : aucun entraînement ou adaptation n'est effectué sur les données locales.
  - L'environnement principal du dépôt ne contenait pas encore pytest dans son `.venv` ; les tests ciblés ont été exécutés avec Python 3.14 disponible sur la machine. Cette exécution ne constitue pas un test d'installation complète du groupe `dl`.
- **Résultat obtenu, avec lien vers la preuve** :
  - **11 tests passés** sur [test_new_predict.py](../../tests/test_new_predict.py).
  - Google TimesFM produit maintenant un `ForecastResult` complet avec 24 lignes pour une variante gelée.
  - Les dépendances TimesFM sont déclarées et le verrouillage uv a résolu `timesfm==1.3.0`.
- **Analyse critique et décision** :
  - La variante n'a pas été exécutée avec les vrais poids TimesFM dans cette session : les tests utilisent des sorties simulées et ne mesurent donc ni le chargement réel du modèle, ni sa qualité predictive.
  - La médiane est utilisée comme prévision ponctuelle pour rester cohérente avec la médiane Chronos-2 ; ce choix doit être confirmé par la fiche d'expérience avant tout score comparatif.
  - Une sortie TimesFM avec un nombre d'horizons incorrect ou des valeurs non finies est refusée explicitement.
  - Les valeurs négatives sont corrigées et expliquées dans `status_reason`, comme sur Chronos-2.
- **Partenaire / retour reçu / usage vérifié** :
  - Aucun retour extérieur reçu à ce stade.
  - L'intégration est destinée à E3/E4 : E4 pourra comparer les deux modèles avec le même support et les mêmes cas ; E5 pourra relire le résultat grâce au contrat CSV commun.
  - L'exécution réelle des poids devra être vérifiée sur une machine préparée avec le groupe `dl` avant transmission.
- **Prochaine étape** :
  - Synchroniser l'environnement avec `uv sync --locked --group dl` et exécuter un cas réel avec les poids Google TimesFM.
  - Vérifier la forme exacte des sorties quantiles avec le modèle réel et enregistrer la preuve d'exécution.
  - Faire une fiche d'expérience gelée avec Chronos-2 et TimesFM sur les mêmes cas, sans mélanger validation et test.

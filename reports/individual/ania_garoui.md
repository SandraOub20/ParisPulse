# Journal individuel - Ania Garoui (équipe 2, sites connus)

Format : [doc/SUIVI_ET_REMISE.md §4](../../doc/SUIVI_ET_REMISE.md). Entrées les plus récentes en haut. Synthèse d'équipe dans [E2_SUIVI.md](../teams/E2_SUIVI.md).

---

## 2026-11-19 - Squelette `src/models`, revue de cohérence et premières corrections

- **Date et journée** : 2026-11-19
- **Question / objectif personnel** : poser des interfaces E2 stables avant de coder, et vérifier qu'elles respectent le sujet, le plan et les contrats communs. Le but est de pouvoir raccorder rapidement la référence hebdomadaire à E4 et E5.
- **Travail réalisé et outils utilisés** (VS Code, Claude Code, Python) :
  - Écriture du squelette de `src/models` : création de [schemas.py](../../src/models/schemas.py), qui contient `Case`, `ForecastInputs`, `ForecastResult`, `RunCost`, les colonnes des CSV et `target_timestamps()` (implémentée). Squelettes de [registry.py](../../src/models/registry.py), [baseline.py](../../src/models/known/baseline.py), [features.py](../../src/models/known/features.py), [train.py](../../src/models/known/train.py) et [predict.py](../../src/models/known/predict.py). Entrée MOD-001.
  - Création du document de suivi d'équipe [E2_SUIVI.md](../teams/E2_SUIVI.md) : règles de mise à jour, état d'avancement, journal des modifications, décisions.
  - Revue de cohérence des squelettes face au [sujet](../../ParisPulse_Sujet_etudiants.pdf) (12 p.), au [plan](../../PLAN_PROJET.md), à [CONTRATS](../../doc/CONTRATS.md), au [PROTOCOLE](../../doc/PROTOCOLE_EVALUATION.md), à l'[ARCHITECTURE](../../doc/ARCHITECTURE.md) et aux gabarits CSV.
  - Application de deux corrections et ajout de la rubrique Incohérences (§10) au suivi. Entrée MOD-002.
- **Comparaison ou contrôle effectué** :
  - Colonnes `FORECAST_COLUMNS` et `CASE_RUNS_COLUMNS` comparées aux gabarits `forecasts.csv` et `case_runs.csv` : identiques. Champs de `Case` comparés à `cases.csv` : identiques.
  - `target_timestamps(2025-03-29T23:00Z)` : 24 heures UTC consécutives à travers le passage à l'heure d'été.
  - Calcul de la latence : avec `publication_lag_hours = 24`, la valeur t − 168 h reste disponible pour les 24 horizons (la donnée utile pour h = 24 est disponible à origin − 120 h).
  - Import des modules `src/models` après modification : OK.
- **Données, protocole et versions** : aucune donnée réelle utilisée (en attente d'E1 et E4). Protocole au statut « proposé, non validé ». Branche `Team2-squelette`, non commitée. Vérifications faites avec Python 3.13.1 système, alors que le projet cible 3.11 ; ruff non exécuté (`uv` local trop ancien).
- **Résultat obtenu, avec lien vers la preuve** :
  - Ma première revue (MOD-001) concluait « aucune incohérence critique ». La seconde revue a montré que c'était faux : 5 incohérences critiques, 5 importantes et 3 mineures, listées dans [E2_SUIVI.md §10](../teams/E2_SUIVI.md#10-incohérences-relevées-et-suivi).
  - C1 corrigée : le mot « nul » laissait confondre zéro et valeur manquante. Un `y_pred = 0` aurait compté un cas comme complet et faussé la MAE, et exclure les zéros des cibles contredisait le sujet (p. 3).
  - C2 corrigée : les fériés étaient dans les variables calendaires toujours présentes, donc l'ablation « avec / sans calendrier » ne les retirait pas. Ils sont maintenant dans `context_features`, seule partie retirée par `use_context=False`.
- **Analyse critique et décision** :
  - Une première relecture rapide ne suffit pas : il faut confronter chaque docstring aux gabarits CSV et au sujet, mot par mot. L'ambiguïté « nul » aurait pu fausser les scores sans erreur visible.
  - Décisions prises :
    - C3 (`available_at` et `site_group_id` absents de `counts.csv`) : reportée jusqu'à la version finale des données (D-08).
    - C4 : la signature `predict_24h` est exigée par E5 ; sa coexistence avec l'interface du registre sera traitée plus tard (D-09).
    - C5 : Prophet sera d'abord testé pour juger de sa viabilité, avant toute discussion d'intégration (D-10).
- **Partenaire / retour reçu / usage vérifié** :
  - E5 a exigé la signature `predict_24h(case, history, variant)`.
  - Pas encore de retour d'E3 ni d'E1 sur le changement d'interface de `calendar_features` (paramètre `calendar` retiré) : à leur communiquer.
  - Aucun usage vérifié par un partenaire à ce stade.
- **Prochaine étape** :
  - Prévenir E1 et E3 du changement de `calendar_features`, et présenter `schemas.py` aux autres équipes (D-01).
  - Mettre `uv` à jour, puis vérifier avec Python 3.11 et ruff.
  - Obtenir un premier `counts.csv` réel (E1) et un `cases.csv` (E4), puis coder `lookup_lagged`, `fallback_value` et `weekly_reference`, avec un calcul à la main sur un petit cas (zéro observé, heure absente, changement d'heure).
  - Tester Prophet hors intégration.

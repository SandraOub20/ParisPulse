# Équipe 2 - Prévision sur sites connus : document de suivi

> ## ⚠️ À lire avant toute modification de ce fichier
>
> Ce document est la **source de vérité du travail de l'équipe 2** et la matière première du rapport final. Toute personne qui modifie du code, des données, des paramètres ou une décision de l'équipe 2 **doit le mettre à jour dans le même commit**. Pour qu'il reste cohérent :
>
> 1. **Une entrée par modification** dans le [§4 Journal des modifications](#4-journal-des-modifications), ajoutée **en haut** de la liste (la plus récente d'abord). Ne jamais réécrire ni supprimer une entrée passée : pour corriger, ajouter une nouvelle entrée qui renvoie à l'ancienne (`Corrige MOD-xxx`).
> 2. **Identifiant séquentiel** `MOD-NNN` (le suivant du plus grand existant), **date au format ISO** `AAAA-MM-JJ`, **auteur nommé**, branche et commit (hash court, ou `non commité` à remplacer ensuite).
> 3. **Remplir tous les champs du gabarit d'entrée** (§4) : quoi, pourquoi, fichiers (liens relatifs), impact sur les contrats/partenaires, vérifications réellement effectuées, points ouverts. Écrire `aucun` plutôt que laisser vide.
> 4. **Mettre à jour en même temps** les sections d'état concernées : [§2 État](#2-état-davancement), [§5 Reste à faire](#5-reste-à-faire), [§6 Décisions](#6-décisions-et-points-ouverts), [§7 Expériences](#7-expériences-et-résultats). Cocher une tâche uniquement si elle est **faite et vérifiée**, avec le renvoi `MOD-NNN`.
> 5. **Ne noter que des faits vérifiés.** Un résultat chiffré cite sa source (fichier `.pred.csv`, `scores.csv`, fiche d'expérience). Ne jamais reporter un score mesuré sur le **test final** avant le gel des choix (§6).
> 6. **Français, dates UTC ISO 8601**, noms de fichiers/fonctions entre backticks, liens relatifs depuis ce fichier (`../../src/...`). Pas de chemin personnel (`C:\Users\...`).
> 7. Toute **modification d'interface** (signature, colonnes CSV, statut, nom de méthode) doit être signalée dans le champ *Impact partenaires* et dans le §6, et communiquée à E3/E4/E5 **avant** d'être fusionnée.
> 8. Les journaux individuels restent dans `reports/individual/` ; ce fichier n'en contient qu'une synthèse et un lien.
> 9. **Périmètre E2 uniquement** : ne pas modifier `src/models/new/` (équipe 3) et ne pas y documenter de travail E3. Toute modification d'un fichier partagé (`registry.py`, `schemas.py`) est signalée à E3.

---

## 1. Mission et périmètre

**Question de recherche** (sujet, p. 4 et 6) : comment mieux prévoir les 24 prochaines heures d'un compteur dont on possède déjà un historique ? Quelles données utiliser, quelle méthode retenir, à quel coût ?

| Livrable | Destinataire | Référence |
| --- | --- | --- |
| Référence hebdomadaire recalculable + repli | E4, E5 | [baseline.py](../../src/models/known/baseline.py) |
| Variables causales partagées | E1, E3 | [features.py](../../src/models/known/features.py) |
| Modèle(s) entraîné(s) et comparaison de variantes (dont ablation d'information) | E4 | [train.py](../../src/models/known/train.py) |
| Calcul exécutable `predict_24h` + exports `.pred.csv` / `.runs.csv` | E4, E5 | [predict.py](../../src/models/known/predict.py) |
| Fiches méthode (historique minimal, repli, conditions) | E5 | [registry.py](../../src/models/registry.py) |
| Provenance prouvant l'exclusion des sites réservés (si modèle partagé) | E3 | `artifacts/models/<model_run_id>/metadata.json` |
| Contribution à l'expérience deep learning collective | Collectif | responsabilité à attribuer (§6) |

Documents de référence : [sujet](../../ParisPulse_Sujet_etudiants.pdf), [architecture](../../doc/ARCHITECTURE.md), [contrats](../../doc/CONTRATS.md), [protocole](../../doc/PROTOCOLE_EVALUATION.md), [README E2](../../src/models/known/README.md), [gabarits](../../doc/templates/README.md).

**Hors périmètre** : `src/models/new/` appartient à l'équipe 3 et n'est ni modifié ni suivi ici. Les fichiers partagés (`src/models/registry.py`, `src/models/schemas.py`) sont modifiés en concertation avec E3.

**Membres** : _tout le monde_.

---

## 2. État d'avancement

_Dernière mise à jour : 2026-11-19 - MOD-002._

| Étape (README E2) | État | Renvoi |
| --- | --- | --- |
| 0. Revue de cohérence sujet / architecture / contrats / `src/models` | 🟡 Revue faite, incohérences en partie traitées (§10) | MOD-001, MOD-002 |
| 0. Squelette de code `src/models` (signatures, types, docstrings) | ✅ Fait | MOD-001 |
| 1. Série réelle E1 + origine et données autorisées E4 | ⏳ En attente partenaires | - |
| 2. Référence 168 h + repli causal (`baseline.py`) | 🔲 À coder | - |
| 3. Vérification manuelle + raccord E4/E5 | 🔲 | - |
| 4. Variables communes (`features.py`) | 🔲 | - |
| 5. Méthode justifiée + variante explicative (`train.py`) | 🔲 | - |
| 6. Calcul exécutable et exports, recalcul autre origine (`predict.py`) | 🔲 | - |
| 7. Cas difficile, extension, test final après gel | 🔲 | - |

Légende : ✅ fait et vérifié · 🟡 en cours · ⏳ bloqué/en attente · 🔲 non commencé.

---

## 3. Architecture du code E2 (état actuel)

```text
src/models/
  schemas.py        Case, ForecastInputs, ForecastResult, RunCost, colonnes CSV,
                    target_timestamps() [implémenté], assert_causal()
                    -> PROPOSITION à migrer vers src/common/contracts.py
  registry.py       ForecastMethod (Protocol), MethodSpec, register/get_method/
                    list_methods/check_eligibility/select_method
  known/
    baseline.py     weekly_reference, lookup_lagged, fallback_value, prophet_reference (optionnel)
    features.py     calendar_features (heure/jour, toujours présentes), history_features,
                    context_features (fériés, vacances, météo : seule partie retirée par
                    l'ablation), build_feature_frame, build_training_frame
    train.py        TrainConfig, TrainedModel, exclude_reserved_sites, fit, compare_variants,
                    save_model/load_model
    predict.py      build_inputs, predict_24h (signature imposée), run_experiment,
                    write_predictions, write_runs
```

Flux prévu d'un cas :

```text
cases.csv (E4) --Case.from_row--> Case
counts.csv (E1) --build_inputs (available_at <= origin)--> ForecastInputs --assert_causal
  --> predict_24h(case, history, variant, context=...)
        variant="reference" -> baseline.weekly_reference (+ fallback_value)
        autre variante      -> train.load_model -> modèle ; repli référence si inéligible
  --> ForecastResult --to_forecast_frame / to_run_row--> <method_run_id>.pred.csv / .runs.csv
```

Fonctions réellement implémentées à ce jour : `target_timestamps()` uniquement. Toutes les autres lèvent `NotImplementedError("E2 : ...")`.

---

## 4. Journal des modifications

### Gabarit d'entrée (copier en haut de la liste)

```markdown
### MOD-NNN - AAAA-MM-JJ - Titre court
- **Auteur** :
- **Branche / commit** :
- **Quoi** : description précise de la modification.
- **Pourquoi** : motivation, lien avec le sujet, les contrats ou un retour partenaire.
- **Fichiers** : liens relatifs.
- **Impact partenaires / contrats** : signatures, colonnes, statuts modifiés ; équipes prévenues.
- **Vérifications effectuées** : commandes lancées, résultats observés (ou "aucune").
- **Points ouverts** : ce qui reste incertain ou à valider.
```

### MOD-002 - 2026-11-19 - Revue des incohérences critiques ; corrections C1 et C2 (Corrige MOD-001)

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2-squelette` / non commité.
- **Quoi** :
  - Nouvelle revue des squelettes E2 face au sujet, au plan, à CONTRATS, PROTOCOLE, ARCHITECTURE et aux gabarits. **Corrige MOD-001** : la conclusion « aucune incohérence critique » était fausse ; cinq incohérences critiques (C1–C5), cinq importantes (I1–I5) et trois mineures (M1–M3) sont listées au [§10](#10-incohérences-relevées-et-suivi).
  - C1 appliquée : suppression de l'ambiguïté « nul » (zéro ou manquant). Dans [baseline.py](../../src/models/known/baseline.py), un horizon sans repli a `y_pred` manquant (NaN, jamais 0) ; un zéro observé à t−168 h est une prévision valide. Dans [features.py](../../src/models/known/features.py), `build_training_frame` exclut les cibles manquantes et conserve les zéros observés.
  - C2 appliquée : `calendar_features` ne contient plus que heure locale, jour de semaine et week-end (paramètre `calendar` retiré) ; fériés et vacances passent dans `context_features` avec la météo admissible. `use_context=False` retire désormais toute la source complémentaire, et elle seule.
  - [predict.py](../../src/models/known/predict.py) : docstring précisant que la signature `predict_24h` est exigée par E5 et renvoyant à C4.
- **Pourquoi** : C1, un `y_pred = 0` comptait un cas comme complet et faussait la MAE (CONTRATS §7) ; exclure les zéros des cibles contredisait le sujet (p. 3). C2, l'ablation « même modèle avec et sans calendrier » (sujet p. 6, plan §5) gardait les fériés dans les deux variantes.
- **Fichiers** : [baseline.py](../../src/models/known/baseline.py), [features.py](../../src/models/known/features.py), [predict.py](../../src/models/known/predict.py), ce fichier.
- **Impact partenaires / contrats** : signature `calendar_features(targets)` modifiée (paramètre `calendar` retiré) ; à signaler à E3, qui partage la bibliothèque de variables, et à E1 pour le rôle `known_calendar` de `context.csv`. Aucune colonne CSV ni aucun statut modifié.
- **Vérifications effectuées** : import de `src/models/known/{baseline,features,predict,train}` et `src/models/registry` OK après modification, avec Python 3.13.1 système (le projet cible 3.11 : I5). Ruff non exécuté. Aucune logique exécutée : les fonctions restent non implémentées.
- **Points ouverts** : C3, C4 et C5 en suspens selon les décisions D-08 à D-10 ; I1–I5 et M1–M3 non traités (§10).

### MOD-001 - 2026-11-19 - Revue de cohérence et squelette du dossier `src/models`

- **Auteur** : Ania Garoui (assistée par Claude Code).
- **Branche / commit** : `Team2-squelette` / non commité.
- **Quoi** :
  - Revue croisée du sujet (PDF, 12 p.), de [ARCHITECTURE.md](../../doc/ARCHITECTURE.md), de [CONTRATS.md](../../doc/CONTRATS.md), des gabarits CSV et des consignes de `src/models/`. Conclusion : **aucune incohérence critique** ; rôles E2/E3, scénarios `known_site`/`new_site`, format 24 lignes, `.runs.csv`, `support_id`/`adaptation_id` et comparaison gelée/adaptée/référence sont alignés.
  - Création de [schemas.py](../../src/models/schemas.py) : dataclasses `Case` (= une ligne de `cases.csv`), `ForecastInputs` (historique et contexte filtrés à la coupure d'information, `support_id` pour E3), `RunCost` (une ligne `.runs.csv`), `ForecastResult` (24 horizons, statut, provenance, coût) ; constantes `FORECAST_COLUMNS` et `CASE_RUNS_COLUMNS` recopiées des gabarits ; types `Scenario`, `Variant`, `PredictionStatus` ; `target_timestamps(origin)` implémentée (24 heures écoulées UTC, refus d'une origine sans fuseau).
  - Remplacement des consignes de [registry.py](../../src/models/registry.py) par un squelette : protocole `ForecastMethod(inputs, variant) -> ForecastResult`, fiche `MethodSpec` (scénarios, `min_history_hours`, `fit_cutoff`, dépendances, GPU, repli), fonctions de registre et de routage `select_method` avec chaîne de repli déclarée.
  - Squelettes de [baseline.py](../../src/models/known/baseline.py), [features.py](../../src/models/known/features.py), [train.py](../../src/models/known/train.py) et [predict.py](../../src/models/known/predict.py). Les consignes d'origine sont conservées dans les docstrings de module.
- **Pourquoi** : disposer d'interfaces stables avant de coder, conformément à ARCHITECTURE §5 (« interface à convenir avant de coder ») et permettre l'intégration d'une première prévision dès la première matinée.
- **Fichiers** : `src/models/schemas.py` (nouveau), `src/models/registry.py`, `src/models/known/{baseline,features,train,predict}.py`.
- **Impact partenaires / contrats** :
  - `schemas.py` est une **proposition** qui devra migrer dans `src/common/contracts.py` (fichier partagé E1-E5, actuellement vide). À présenter aux autres équipes.
  - `predict_24h(case, history, variant="reference")` conservée telle qu'imposée, avec ajout d'arguments nommés optionnels `context=` et `model_run_id=` (compatibles avec la signature imposée).
  - `src/models/new/` (périmètre E3) n'est pas modifié. `schemas.py` et `registry.py` prévoient `support_id` / `adaptation_id` et le scénario `new_site` pour qu'E3 puisse s'y brancher : à lui présenter.
- **Vérifications effectuées** : import de tous les modules `src/models` OK ; `target_timestamps(2025-03-29T23:00Z)` produit 24 heures UTC consécutives (h1 = 23:00, h24 = 2025-03-30 22:00) à travers le passage à l'heure d'été. Exécuté avec Python 3.13 système (le projet cible 3.11). **ruff non exécuté** : `uv` local en 0.10.9 alors que le projet exige ≥ 0.13.1 (`uv self update`).
- **Points ouverts** : voir §6 (D-01 à D-04).

---

## 5. Reste à faire

Prioriser dans l'ordre. Cocher avec le renvoi `MOD-NNN` uniquement une fois vérifié.

### Immédiat (première matinée)

- [ ] Mettre `uv` à jour, lancer `./run.sh check` et `ruff` sur `src/models`.
- [ ] Faire adopter (ou amender) `schemas.py` par E1/E3/E4/E5 puis le migrer dans `src/common/contracts.py`.
- [ ] Obtenir d'E1 un premier `counts.csv` réel et d'E4 un premier `cases.csv`.
- [ ] Implémenter `lookup_lagged` (jointure par timestamp, pas par position).
- [ ] Implémenter `fallback_value` (règle à figer, cf. D-03) et `weekly_reference`.
- [ ] Implémenter `ForecastResult.is_complete`, `to_forecast_frame`, `to_run_row`.
- [ ] Implémenter `build_inputs`, `assert_causal`, `predict_24h` (variante `reference`).
- [ ] Vérifier 3 à 5 valeurs à la main sur un petit cas construit (zéro observé, heure absente, changement d'heure).
- [ ] Produire un premier `.pred.csv` / `.runs.csv` et le faire consommer par E4 et E5 (preuve d'usage).

### Étude principale

- [ ] `features.py` : calendrier de base (heure locale, jour), contexte (fériés, vacances, météo admissible), lags, profils, masques de manque ; `FEATURE_VERSION` incrémentée à chaque changement.
- [ ] Tester Prophet hors intégration (viabilité, coût par cas) avant toute discussion d'ajout au projet (D-10).
- [ ] Traiter les incohérences restantes du §10 (C3 après version finale des données, C4 avec E5, I1–I5, M1–M3).
- [ ] Choisir une méthode justifiée par la bibliographie (statistique, tabulaire, réseau compact, modèle partagé...).
- [ ] Ablation : même modèle avec / sans calendrier ou météo, réglages figés avant le test.
- [ ] `train.py` : `exclude_reserved_sites` (par `site_group_id`), `fit`, `save_model` avec `metadata.json` + SHA-256.
- [ ] Enregistrer la référence et les modèles dans le registre (`register_defaults`).
- [ ] Recalcul de la référence sur une autre origine avec E5 (`use_cache=False`).

### Approfondissement et extension

- [ ] Étudier un cas difficile (faibles volumes, météo manquante, rupture, historique incomplet) et une modification ciblée avec son coût.
- [ ] Étendre aux compteurs admissibles ; reporter prévisions non produites et coûts.
- [ ] Mesurer le test final **après gel** des choix.
- [ ] Fiches d'expérience dans `reports/experiments/`, rapport d'équipe final.

---

## 6. Décisions et points ouverts

| ID | Date | Sujet | Statut | Décision / question | Qui |
| --- | --- | --- | --- | --- | --- |
| D-01 | 2026-11-19 | Contrats communs | Ouvert | `src/common/contracts.py` est vide ; `schemas.py` proposé comme base. À valider avec les 5 équipes. | E2 → toutes |
| D-02 | 2026-11-19 | Signature `predict_24h` | Proposé | Signature imposée conservée ; ajout de `context=` (le contrat §5-6 prévoit un contexte admissible absent de la signature). | E2, E5 |
| D-03 | 2026-11-19 | Repli de la référence | Ouvert | Proposition : médiane même heure locale / même jour sur N semaines admissibles, puis moyenne même heure locale, sinon `unavailable`. Valeur de N à fixer. | E2, E4, E5 |
| D-04 | 2026-11-19 | Prophet | Proposé | Variante optionnelle seulement (`prophet_reference`), non déclarée dans `pyproject.toml`, jamais obligatoire. Ajout de la dépendance à décider. | E2 |
| D-05 | 2026-11-19 | Expérience deep learning | Ouvert | Responsabilité E2 ou E3 à attribuer explicitement (ARCHITECTURE §6). `torch` disponible dans le groupe `dl` (CPU). | E2, E3 |
| D-06 | 2026-11-19 | Latence et décalage 168 h | Vérifié | Avec `publication_lag_hours = 24`, y(t−168 h) reste disponible pour les 24 horizons (dernière source disponible à origin − 120 h). | E2 |
| D-07 | - | Gel des choix avant test final | Ouvert | Date de gel à fixer avec E4 ; aucun réglage sur les dates réservées. | E2, E4 |
| D-08 | 2026-11-19 | C3 : `available_at`, latence et `site_group_id` | Reporté | Attendre la version finale des données d'E1 avant de choisir où calculer `available_at` et comment joindre `site_group_id`. | E2, E1 |
| D-09 | 2026-11-19 | C4 : origine de `predict_24h` | Décidé (origine) / Ouvert (cohérence) | La signature `predict_24h(case, history, variant)` est exigée par E5. Sa coexistence avec `ForecastMethod(inputs, variant)` et le double routage seront traités plus tard. | E2, E5 |
| D-10 | 2026-11-19 | C5 : Prophet | Décidé | Tester d'abord Prophet pour juger de sa viabilité ; son intégration au projet (dépendance, module, bibliographie) ne sera discutée qu'ensuite. Précise D-04. | E2 |

---

## 7. Expériences et résultats

Chaque expérience a sa fiche dans `reports/experiments/` (gabarit [experiment.md](../../doc/templates/experiment.md)). Ne remplir les colonnes de résultats qu'avec des valeurs issues de `scores.csv` d'E4.

| ID | Date | Question | Variantes comparées | Protocole / snapshot | MAE macro | Cas complets / attendus | Coût | Conclusion | Fiche |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _aucune pour l'instant_ | | | | | | | | | |

---

## 8. Échanges avec les partenaires

| Date | Équipe | Objet | Résultat / preuve d'usage |
| --- | --- | --- | --- |
| _à compléter_ | | | |

---

## 9. Matière pour le rapport final

Notes à enrichir au fil du projet ; elles serviront directement à la rédaction.

- **Question et périmètre** : sites connus, prévision 24 h, information disponible à l'origine uniquement (latence simulée J−1).
- **Choix d'architecture** : interface unique `ForecastInputs → ForecastResult` partagée E2/E3, registre de méthodes avec repli déclaré, séparation sortie brute / résultat système après repli (CONTRATS §7).
- **Garanties de causalité** : jointure par timestamp, `available_at <= origin`, `fit_cutoff < origin`, labels joints séparément, sites réservés exclus par `site_group_id`.
- **Référence** : naïf hebdomadaire 168 h ; justification : saisonnalité hebdomadaire des passages vélo, recalculable sans apprentissage.
- **Méthodes et ablations** : _à compléter_.
- **Résultats, limites, coûts** : _à compléter (citer `scores.csv`)_.
- **Ce qui n'a pas marché et pourquoi** : _à compléter - une absence de gain est une conclusion valable_.

---

## 10. Incohérences relevées et suivi

Revue du 2026-11-19 (MOD-002) des squelettes E2 face au [sujet](../../ParisPulse_Sujet_etudiants.pdf), au [plan](../../PLAN_PROJET.md), aux [contrats](../../doc/CONTRATS.md), au [protocole](../../doc/PROTOCOLE_EVALUATION.md), à l'[architecture](../../doc/ARCHITECTURE.md) et aux gabarits. Mettre à jour le statut et le renvoi `MOD-NNN` à chaque traitement ; ne pas supprimer une ligne traitée.

Statuts : ✅ corrigé · ⏸️ reporté (décision prise) · 🔲 à traiter.

### Critiques

| ID | Incohérence | Référence | Décision | Statut |
| --- | --- | --- | --- | --- |
| C1 | « y_pred nul » et « cibles nulles » : confusion possible entre zéro et manquant. Un 0 rendrait le cas complet et fausserait la MAE ; exclure les zéros contredit le sujet. | Sujet p. 3 ; CONTRATS §7 | Appliquer la correction : manquant = NaN, zéro observé conservé. | ✅ MOD-002 |
| C2 | L'ablation calendrier n'est pas isolée : fériés et vacances dans `calendar_features`, alors que `use_context` ne coupe que `context_features`. | Sujet p. 6 ; plan §5 | Appliquer la correction : fériés et vacances déplacés dans `context_features`. | ✅ MOD-002 |
| C3 | `counts.csv` n'a ni `available_at` ni `site_group_id` : `build_inputs` et `exclude_reserved_sites` ne peuvent pas être codées telles quelles ; latence fixée à 24 h en dur au lieu de `config/project.yaml`. | CONTRATS §3, §5 ; gabarit `counts.csv` | Attendre la version finale des données avant de choisir (D-08). | ⏸️ |
| C4 | Deux points d'entrée (`predict_24h(case, history, …)` et `ForecastMethod(inputs, variant)`), ambiguïté sur qui filtre l'historique, routage en double (`predict_24h` et `select_method`), alors que le sujet confie l'implémentation du routage à E5. | Sujet p. 9 ; CONTRATS §9 | Signature exigée par E5 ; la cohérence sera traitée plus tard (D-09). | ⏸️ |
| C5 | Prophet non déclaré dans `pyproject.toml` (calcul non reproductible par l'enseignant), absent de la bibliographie, placé dans `baseline.py`, et ne compte pas comme expérience DL. | Sujet p. 2, 4, 10 | Tester d'abord sa viabilité ; intégration discutée ensuite (D-10). | ⏸️ |

### Importantes

| ID | Incohérence | Référence | Statut |
| --- | --- | --- | --- |
| I1 | `schemas.py` est dans `src/models/` alors que le contrat commun relève de `src/common/contracts.py` ; risque de divergence si E4 ou E5 définissent leur propre `Case`. | ARCHITECTURE §5 ; D-01 | 🔲 |
| I2 | `TrainedModel` ne suit pas `model_metadata.example.json` : noms différents (`donor_site_groups`, `label_interval`, `train_seconds`) ; il manque `excluded_site_groups` (preuve attendue par E3), `weights_sha256`, `minimum_history_hours`, `supported_scenarios`, `fallback`. | CONTRATS §6 ; gabarit métadonnées | 🔲 |
| I3 | Référence décalée de 168 h UTC, mais repli en heure locale, et le plan dit « même heure une semaine avant » : décalage d'une heure en semaine de changement d'heure. Règle à choisir, documenter et tester. | Plan §7 ; PROTOCOLE §2 | 🔲 |
| I4 | `MIN_HISTORY_HOURS = 168` est ambigu : avec 24 h de latence, il faut la fenêtre [origin − 168 h, origin − 145 h], pas « 168 h d'historique ». Utilisée par `check_eligibility`, elle refuserait la référence alors que son repli peut répondre. | Sujet p. 2 (méthode simple toujours utilisable) | 🔲 |
| I5 | MOD-001 concluait « aucune incohérence critique » et a été vérifiée avec Python 3.13 au lieu de 3.11 ; ruff non exécuté. | Règles de ce fichier | 🟡 Conclusion corrigée par MOD-002 ; vérification 3.11 + ruff à faire |

### Mineures

| ID | Incohérence | Statut |
| --- | --- | --- |
| M1 | `check_eligibility` exige `fit_cutoff < origin`, le protocole admet `<=` (un modèle gelé au 01/09 00:00 serait refusé pour l'origine du 01/09 00:00) ; `MethodSpec.fit_cutoff` est une chaîne au lieu d'un `Timestamp`. Le §9 de ce fichier reprend aussi `<`. | 🔲 |
| M2 | `ForecastInputs.information_cutoff` mal défini : comparé à `available_at` (= `origin`) ou à `interval_end` (= `origin − latence`) selon les docstrings. Lié à C3. | 🔲 |
| M3 | Expérience deep learning non planifiée concrètement dans le squelette (D-05 ouvert), alors qu'elle est obligatoire. | 🔲 |

### Points vérifiés cohérents

`FORECAST_COLUMNS` et `CASE_RUNS_COLUMNS` identiques aux gabarits ; champs de `Case` identiques à `cases.csv` ; `target_timestamps` conforme (24 h écoulées UTC) ; note de latence de `baseline.py` exacte (donnée de h = 24 disponible à origin − 120 h) ; jointure par timestamp, exclusion par `site_group_id` et préservation du test final prévues.

# EXP-E1-01 - Extraction du flux : retrouver les mêmes données, et la source change-t-elle d'un jour à l'autre ?

- **Date, équipe, responsables et partenaires :** 12/11/2026 (extraction d'un compteur) et 16/11/2026 (contrôles ci-dessous), E1, Tasnim. Code `--tout`, grille commune et instantané `flux-20261115` : Nihed. Consommateurs : E2 et E3 (`counts.csv`, `counters.csv`), E4 (heures évaluables, cas sans cible), E5 (provenance, messages), et dans E1 Zeineb (`quality.py`) et Sabrina (`zeros.py`).
- **Question et hypothèse :**
  1. L'extraction permet-elle de **retrouver exactement** les données utilisées par une expérience ?
  2. La source **modifie-t-elle** les heures déjà publiées d'un jour à l'autre : valeurs corrigées, heures manquantes comblées plus tard ?

  Hypothèse : non. Seul le début de la fenêtre glissante de 13 mois change, parce qu'il avance chaque jour. Si l'hypothèse est fausse, un instantané figé ne suffirait pas à rejouer une expérience. Il faudrait aussi tenir compte de la date à laquelle chaque valeur a été publiée.
- **Références :** page du jeu « Comptage vélo - Données compteurs » (opendata.paris.fr, Ville de Paris, ODbL) ; `doc/CONTRATS.md` §1 à §3 ; `doc/PROTOCOLE_EVALUATION.md` (délai de publication).
- **Instantané, protocole, code et paramètres :**
  - `flux-20261112` : un compteur (`100057445-104057445`, Totem 73 bd de Sébastopol S-N), extrait le 12/11/2026 à 13:10 UTC, préparé avec `e1-prepare/0.1.0` (commit `e301f54`).
  - `flux-20261115` : tout le flux (113 compteurs), extrait le 15/11/2026 (brut complet à 16:08 UTC), préparé avec `e1-prepare/0.2.0`, reçu en zip de l'équipe 1.
  - Code : `src/data/acquire.py` ; `src/data/prepare.py` jusqu'à `e1-prepare/0.2.2` (commits `159f12d`, `b325294`). Export CSV de l'API v2.1 avec `timezone=UTC` et séparateur `;`. Pour `--tout`, `select` est limité aux colonnes utiles : environ 150 Mo au lieu de plus de 1 Go.
  - Protocole d'évaluation : **proposé, non validé** par E4.
- **Scénario, sites, dates et budget d'information autorisé :** sans objet. Contrôle des données d'entrée, pas de prévision.
- **Facteur modifié et facteurs conservés :**
  - facteur modifié : la date d'extraction (12/11 et 15/11, 3 jours d'écart) ;
  - facteurs conservés : même compteur, même API, même conversion en UTC, même règle de doublons.

  Les versions de préparation diffèrent (0.1.0 et 0.2.0). C'est pourquoi la comparaison porte seulement sur `count_raw` et `is_observed` : leur règle n'a pas changé entre ces deux versions. Les changements portent sur la grille commune, `direction` et les drapeaux `network_gap`.
- **Cas attendus et règle de comparaison :**
  - on compare les heures UTC communes aux deux instantanés pour `100057445-104057445` ;
  - une heure est « modifiée » si `count_raw` ou `is_observed` diffère ;
  - une heure est « comblée » si elle était absente le 12/11 et observée le 15/11.

## Contrôles réalisés

1. **Chaîne de l'extraction** (`acquire.py`, relue) :
   - le brut est déposé tel quel dans `data/history/<snapshot_id>/`, via un fichier temporaire puis un renommage, et n'est jamais retéléchargé sans `--force` ;
   - un instantané `flux-AAAAMMJJ` qui n'est pas daté du jour (UTC) est refusé, sauf avec `--autre-date`. Ses fichiers se récupèrent dans le zip de l'équipe, pour ne jamais ranger d'autres données sous le même nom ;
   - le manifeste enregistre l'URL exacte et ses filtres, `retrieved_at`, la date de mise à jour du jeu, la licence et l'attribution, ainsi que la SHA-256, le nombre de lignes et les bornes de chaque fichier.
2. **Intégrité du zip `flux-20261115`** : SHA-256 recalculée pour chaque fichier listé dans le manifeste.
3. **Lecture des dates** (manifeste de `flux-20261115`) :
   - sur 1 034 819 lignes source : 0 ligne à date illisible ou hors de l'heure pile, 0 heure ambiguë ou inexistante ;
   - aucune alerte « dates sans fuseau ».
4. **Stabilité de la source** : comparaison heure par heure du même compteur dans les deux instantanés.

## Résultats mesurés

Pas de MAE : ce n'est pas une comparaison de modèles.

**Intégrité :**

- les 8 fichiers traités du zip (`counts.csv`, `counters.csv`, `audit_duplicates.csv`, `context.csv`, `context_sources.json`, `context_join_audit.json`, `inventory_quality.csv`, `selection_summary.json`) ont **la même SHA-256 que dans le manifeste** ;
- les 6 bruts de `data/history/flux-20261115/` (flux complet, compteur seul, 4 sources de contexte) **ne sont pas dans le zip**. La préparation ne peut donc pas encore être relancée avec `e1-prepare/0.2.2`.

**Volume de `flux-20261115`** (manifeste) :

- 1 034 819 lignes source, 113 compteurs ;
- grille commune de 9 503 heures, du 15/10/2025 00:00 au 14/11/2026 22:00 UTC, soit 1 073 839 lignes (`e1-prepare/0.2.0`). Depuis la régénération du 17/11/2026 (`e1-prepare/0.3.0`) : 9 479 heures à partir du 16/10/2025 00:00, soit 1 071 127 lignes et 1 033 477 heures observées ; 27 mesures du 15/10/2025 écartées, gardées dans le brut ;
- 1 033 504 heures observées, 39 020 heures absentes, 1 315 valeurs vides ;
- 0 doublon, 0 conflit, 0 valeur négative ou invalide.

**Stabilité entre le 12/11 et le 15/11** (compteur `100057445-104057445`) :

| | Heures |
| --- | ---: |
| Heures communes aux deux instantanés | 9 431 |
| Identiques (`count_raw` et `is_observed`) | 9 408 |
| Modifiées | 23 |
| … dont hors du 15/10/2025 | **0** |
| Absentes le 12/11 | 102 |
| … dont comblées le 15/11 | **0** |
| Heures nouvelles (12/11 23:00 à 14/11 22:00 UTC), observées | 72 / 72 |

- **Les 23 heures modifiées** tombent toutes le **15/10/2025**. Elles sont observées le 12/11, mais absentes le 15/11. Sur tout le réseau, le 15/10/2025 n'a que de 0 à 5 compteurs observés par heure dans `flux-20261115`, contre 113 dès le 16/10 à 00:00 UTC.
- **Les 102 heures absentes le 12/11** tombent toutes sur des pannes de tout le réseau :
  - 22 à 23 h les 22/08, 23/09, 04/10 et 25/10/2026, plus 2 h la veille au soir ;
  - 2 h les 01/07 et 05/07/2026 ;
  - 1 h le 26/10/2025, au passage à l'heure d'hiver.

  Aucune n'a été publiée après coup.

## Analyse, limites et décision

- **La source ne corrige pas et ne complète pas les heures déjà publiées**, du moins sur 3 jours et pour ce compteur. Un instantané figé, identifié par sa date et par les empreintes de ses fichiers, suffit donc à rejouer une expérience. Les heures manquantes d'une panne restent manquantes : ce sont des cas sans cible pour E4, pas des valeurs à attendre.
- **Le début de la fenêtre glissante est rogné.** La source retire les données au-delà de 13 mois, si bien que le premier jour d'un instantané est partiel et varie selon l'heure d'extraction.
  - **Effet de bord constaté :** dans `flux-20261115`, ces heures rognées du 15/10/2025 sont marquées `network_gap` (1 574 lignes), alors que ce n'est pas une panne.
  - **Proposition à valider avec E1 et E4 :** faire commencer la grille commune au premier jour complet (16/10/2025 00:00 UTC pour `flux-20261115`), ou marquer ces heures d'un drapeau distinct (« hors fenêtre »). Dans les deux cas, ne pas les compter comme panne.
  - **Appliqué le 17/11/2026 (`e1-prepare/0.3.0`, Nihed) :** le premier jour UTC du brut est toujours écarté, et le manifeste note la règle (`grid.window_rule`), la première heure du brut et le nombre de mesures écartées (27). Les heures `network_gap` passent de 116 à 102. Question Q13 du contrat, en attente de l'accord d'E4.
- **Limites :**
  - un seul compteur ;
  - 3 jours d'écart : une révision plus tardive n'est pas exclue. À refaire sur tout le flux avec le prochain instantané ;
  - comparaison faite sur les fichiers préparés, faute de brut dans le zip.
- **Décisions :**
  1. garder les instantanés figés et ne jamais retélécharger sous un ancien nom (règle déjà dans le code) ;
  2. demander que le zip d'un instantané contienne aussi `data/history/` (fait le 17/11 : zip séparé des bruts, partagé par Drive) ;
  3. décider avec l'équipe du traitement du premier jour de la fenêtre (proposé et appliqué le 17/11, voir ci-dessus).

## Reproduire

```bash
# Données : zip de l'équipe 1 décompressé dans data/ (processed/ et manifests/)
uv run python - <<'EOF'
import pandas as pd
cid = "100057445-104057445"
a = pd.read_csv("data/processed/flux-20261112/counts.csv", dtype=str, keep_default_na=False)
b = pd.read_csv("data/processed/flux-20261115/counts.csv", dtype=str, keep_default_na=False)
m = a.merge(b[b.counter_id == cid], on="timestamp", suffixes=("_12", "_15"))
diff = m[(m.count_raw_12 != m.count_raw_15) | (m.is_observed_12 != m.is_observed_15)]
print(len(m), "heures communes ;", len(diff), "modifiées ; jours :", sorted(set(diff.timestamp.str[:10])))
gone = m[m.is_observed_12 == "false"]
print(len(gone), "absentes le 12/11 ;", (gone.is_observed_15 == "true").sum(), "comblées le 15/11")
EOF
```

## Liens

- Données : `data/manifests/flux-20261112.json`, `data/manifests/flux-20261115.json`, `data/processed/flux-20261112/counts.csv`, `data/processed/flux-20261115/counts.csv` (non versionnés).
- Alertes du manifeste : [E1-alertes-manifeste.md](E1-alertes-manifeste.md).
- Code : `src/data/acquire.py`, `src/data/prepare.py` ; tests : `tests/test_data_prepare.py`.

## Retour d'un partenaire et preuve d'utilisation

À renseigner : retours de Nihed et de Sabrina sur les corrections `159f12d` et `b325294`, et d'E4 sur le traitement du premier jour de la fenêtre et des journées de panne.

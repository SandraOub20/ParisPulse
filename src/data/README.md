# Données et contexte - équipe 1

Les modules contiennent des instructions à implémenter :

| Fichier | Travail attendu |
| --- | --- |
| `acquire.py` | Sources, extraction, archives/flux et provenance ; `--tout` télécharge tout le flux en un seul export (`data/history/<snapshot_id>/comptage-velo-donnees-compteurs__complet.csv`) puis lance la préparation |
| `prepare.py` | UTC, identifiants, grille horaire et résolution des doublons ; avec `--tout`, grille commune à tous les compteurs, `direction` tirée du nom, drapeau `network_gap` (contrôles dans le manifeste : `grid`, `network_gap`, `direction_checks`) |
| `archives.py` | Archives annuelles 2023-2025 : téléchargement, inventaire, canaux jumeaux (R1) et renommages (R1 bis), assemblage de `hist-…` avec le flux. [Fiche](../../reports/experiments/E1-historique.md) |
| `context.py` | Source complémentaire, disponibilité et cardinalité des jointures ; écrit `context.csv` (jours fériés, vacances zone C, grèves des transports d'Île-de-France connues 24 h avant, météo prévue J-2 et observée ; une ligne par jour pour le calendrier, nom dans `label`) ; `--greves` ajoute les grèves (référentiel `data/reference/`) à un `context.csv` existant, `context_sources.json` et `context_join_audit.json` ; `--migrer` convertit un ancien `context.csv` sans retélécharger. Hypothèses de disponibilité dans la section `context` de `config/project.yaml`. Choix et contrôles : [fiche](../../reports/experiments/E1-contexte-source-complementaire.md) |
| `alerts_review.py` | Classe les alertes du manifeste (changement d'heure, pics de semaine, métadonnées) avec la méthode de la [fiche de Tasnim](../../reports/experiments/E1-alertes-manifeste.md) ; ne corrige rien |
| `fill_counts.py` | Remplit **directement** `counts.csv` et `counters.csv` (une seule fois par instantané, après `quality.py`, `context.py` et l'examen des alertes) : sites réservés à E3 rendus nouveaux, 7 jours d'historique local pour tous (E3 raccourcit à 3 ou 1 jour), installés au début du support de la première origine d'évaluation (`new_sites.py`) ; heures `missing`/`empty_value` remplacées par J-7 (`fill_j7.py`) ; heures `long_zero_run` remplacées par l'année d'avant quand elle est > 0, sinon le 0 reste (`fill_zeros_year.py`). Une valeur remplacée n'est jamais une cible (`is_scoreable` faux). `count_raw` et les drapeaux gardent la trace ; bloc `fill` dans le manifeste et `fill_report.json`. Ne pas relancer `quality.py` sur un `counts.csv` rempli |
| `original.py` | Relit un `counts.csv` rempli avec les valeurs d'origine (J-7 et année d'avant annulés grâce à `count_raw`) ; utilisé par les analyses des zéros et l'examen des alertes |
| `zeros_criteria.py`, `zeros_years.py` | Critère des zéros pour `robustness` (A2) ; suites de zéros aux mêmes dates d'une année à l'autre (B1) |
| `quality.py` | Inventaire, distribution, manques, zéros et choix d'échantillon ; écrit `inventory_quality.csv` et `selection_summary.json` (sites réservés E3), et réécrit `site_group_id` dans `counters.csv` (groupes candidats à moins de 100 m ; à relancer après `prepare.py`). Critères : [fiche](../../reports/experiments/E1-inventaire-selection.md) |
| `zeros.py` | Approfondissement : heures d'une suite d'au moins 24 h de zéros, détectées avec les seules heures publiées à la coupure, remplacées par l'année d'avant (traitement C, sur une copie : aucun fichier modifié). Protocole : [fiche](../../reports/experiments/E1-zeros-apprentissage.md) |
| `zeros_experiment.py` | Comparaison A (garder) / C (année d'avant) avec E2/E4 : mêmes cas, même masque, MAE par compteur, compteurs utilisables, règle de décision. À lancer sur l'historique, après validation du protocole |

**Commencer :** transmettre rapidement une série réelle avec sa localisation et ses problèmes à E2/E4/E5, sans attendre l'inventaire complet.

**Ordre pour un instantané complet :**

```bash
uv run python -m src.data.acquire --tout --snapshot flux-20261115
uv run python -m src.data.quality --snapshot flux-20261115 --figures
uv run python -m src.data.context --snapshot flux-20261115
uv run python -m src.data.fill_counts --snapshot flux-20261115
```

`quality.py` vient après `prepare.py`. Avec `--tout`, `prepare` écrit déjà les groupes candidats et `quality.py` confirme qu'ils sont à jour. En préparation compteur par compteur, `prepare` remet `site_group_id = site_id` : `quality.py` réécrit alors les groupes.

Entrées : `data/history/`. Sorties : `data/processed/<snapshot_id>/counts.csv`, `counters.csv`, `inventory_quality.csv`, `context.csv`, puis `data/manifests/<snapshot_id>.json` ; avec `fill_counts`, `counts.csv` et `counters.csv` remplis sur place et `fill_report.json`.

Utiliser les [gabarits](../../doc/templates/README.md), conserver les bruts et distinguer les zéros des absences. Vérifier avec E3/E4 les groupes de sites physiques et les directions réservées. Les critères de sélection et traitements se décident avant le test final.

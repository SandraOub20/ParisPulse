# Données et contexte - équipe 1

Les modules contiennent des instructions à implémenter :

| Fichier | Travail attendu |
| --- | --- |
| `acquire.py` | Sources, extraction, archives/flux et provenance ; `--tout` télécharge tout le flux en un seul export (`data/history/<snapshot_id>/comptage-velo-donnees-compteurs__complet.csv`) puis lance la préparation |
| `prepare.py` | UTC, identifiants, grille horaire et résolution des doublons ; `--tout` prépare tous les compteurs du brut complet |
| `context.py` | Source complémentaire, disponibilité et cardinalité des jointures ; écrit `context.csv` (jours fériés, vacances zone C, météo prévue J-2 et observée), `context_sources.json` et `context_join_audit.json`. Hypothèses de disponibilité dans la section `context` de `config/project.yaml`. Choix et contrôles : [fiche](../../reports/experiments/E1-contexte-source-complementaire.md) |
| `quality.py` | Inventaire, distribution, manques, zéros et choix d'échantillon ; écrit `inventory_quality.csv` et `selection_summary.json` (sites réservés E3), et réécrit `site_group_id` dans `counters.csv` (groupes candidats à moins de 100 m ; à relancer après `prepare.py`). Critères : [fiche](../../reports/experiments/E1-inventaire-selection.md) |
| `zeros.py` | Approfondissement : heures d'une suite d'au moins 24 h de zéros à écarter de l'apprentissage (traitement B), détectées avec les seules heures publiées à la coupure ; ne modifie ni `count` ni les fichiers. Protocole : [fiche](../../reports/experiments/E1-zeros-apprentissage.md) |
| `zeros_experiment.py` | Comparaison A (garder) / B (écarter) avec E2/E4 : mêmes cas, même masque, MAE par compteur, compteurs utilisables, règle de décision. À lancer après validation du protocole |

**Commencer :** transmettre rapidement une série réelle avec sa localisation et ses problèmes à E2/E4/E5, sans attendre l'inventaire complet.

**Ordre pour un instantané complet :**

```bash
uv run python -m src.data.acquire --tout --snapshot flux-20261115
uv run python -m src.data.quality --snapshot flux-20261115 --figures
uv run python -m src.data.context --snapshot flux-20261115
```

`quality.py` doit venir après `prepare.py` (qui remet `site_group_id = site_id`).

Entrées : `data/history/`. Sorties : `data/processed/<snapshot_id>/counts.csv`, `counters.csv`, `inventory_quality.csv`, `context.csv`, puis `data/manifests/<snapshot_id>.json`.

Utiliser les [gabarits](../../doc/templates/README.md), conserver les bruts et distinguer les zéros des absences. Vérifier avec E3/E4 les groupes de sites physiques et les directions réservées. Les critères de sélection et traitements se décident avant le test final.

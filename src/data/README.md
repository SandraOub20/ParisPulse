# Données et contexte - équipe 1

Les modules contiennent des instructions à implémenter :

| Fichier | Travail attendu |
| --- | --- |
| `acquire.py` | Sources, extraction, archives/flux et provenance |
| `prepare.py` | UTC, identifiants, grille horaire et résolution des doublons |
| `context.py` | Source complémentaire, disponibilité et cardinalité des jointures |
| `quality.py` | Inventaire, distribution, manques, zéros et choix d'échantillon |

**Commencer :** transmettre rapidement une série réelle avec sa localisation et ses problèmes à E2/E4/E5, sans attendre l'inventaire complet.

Entrées : `data/history/`. Sorties : `data/processed/<snapshot_id>/counts.csv`, `counters.csv`, `inventory_quality.csv`, `context.csv`, puis `data/manifests/<snapshot_id>.json`.

Utiliser les [gabarits](../../doc/templates/README.md), conserver les bruts et distinguer les zéros des absences. Vérifier avec E3/E4 les groupes de sites physiques et les directions réservées. Les critères de sélection et traitements se décident avant le test final.

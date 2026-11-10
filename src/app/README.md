# Application et intégration - équipe 5

- `service.py` : charger les entrées autorisées, appeler E2/E3/E4, définir cache et routage.
- `streamlit_app.py` : carte, sélection, passé, 24 prévisions, révélation, erreurs et contexte.
- `export.py` : exporter étude, scores révélés, provenance, périmètre et refus.

Commencer par un cas d'essai construit par l'équipe, puis utiliser rapidement la série E1, la référence E2 et le score E4. Les calculs scientifiques restent dans les modules des partenaires.

L'analyste distingue inventaire, données chargées et méthodes disponibles. Le mode nouveau site expose son budget local. Toute sélection nouvelle remet les observations cibles à l'état masqué ; la révélation ne recalcule pas la prévision.

Prévoir le recalcul d'une autre date, des erreurs explicites et des caches versionnés. L'[environnement de développement](../../doc/ENVIRONNEMENT.md) est configuré ; compléter le packaging et ajouter le lancement applicatif suivant `run.sh.example`. Déclarer toute dépendance supplémentaire dans `pyproject.toml`, actualiser le verrou et l'export. Faire vérifier une copie neuve par une autre équipe.

Les fichiers Python sont des gabarits d'instructions ; l'application et sa commande de lancement restent à développer.

# Application et intégration - équipe 5

- `service.py` : charger les entrées autorisées, appeler E2/E3/E4, définir cache et routage.
- `streamlit_app.py` : carte, sélection, passé, 24 prévisions, révélation, erreurs et contexte.
- `export.py` : exporter étude, scores révélés, provenance, périmètre et refus.

Commencer par un cas d'essai construit par l'équipe, puis utiliser rapidement la série E1, la référence E2 et le score E4. Les calculs scientifiques restent dans les modules des partenaires.

L'analyste distingue inventaire, données chargées et méthodes disponibles. Le mode nouveau site expose son budget local. Toute sélection nouvelle remet les observations cibles à l'état masqué ; la révélation ne recalcule pas la prévision.

Prévoir le recalcul d'une autre date, des erreurs explicites et des caches versionnés. Définir les dépendances puis compléter `Dockerfile` et le futur lanceur à partir de `run.sh.example`. Faire vérifier une copie neuve par une autre équipe.

Les fichiers sont des gabarits d'instructions ; aucune application ni commande de lancement n'est fournie à ce stade.

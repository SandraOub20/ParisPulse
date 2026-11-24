# Journal individuel - Nihed (E1, préparation de tout le flux, contexte, historique)

> **Entrées reconstituées par Tasnim le 24/11/2026**, à partir des commits de Nihed (branche `team1-nihed`, puis `Team1`) et des fiches [EXP-E1-03](../experiments/E1-contexte-source-complementaire.md) et [historique](../experiments/E1-historique.md). Les heures sont celles des commits. **Nihed : à relire et à compléter**, en particulier les outils utilisés, les retours reçus et ce qui t'a fait changer d'avis. Rien n'a été ajouté qui ne soit pas dans une trace.

## 15/11/2026 (après-midi) - Source complémentaire : calendrier et météo sans information du futur

- **Question ou objectif personnel :** quelles informations externes, connues au moment de prévoir, peut-on joindre aux comptages sans créer ni perdre de ligne et sans utiliser le futur ?
- **Travail réalisé et outils utilisés :**
  - `src/data/context.py` (`e1-context/0.1.0`) : jours fériés, vacances de la zone C, météo prévue J-2 (Open-Meteo) et observée (Météo-France, station Montsouris), audit de jointure (commit `9621e36`, 15:17) ;
  - délais de disponibilité de la météo (6 h pour un run, 24 h pour une observation) lus dans `config/project.yaml`, pour être validés par E4 sans modifier le code (`f6ef4d8`, 16:18) ;
  - outils : *à compléter*.
- **Expérience ou contrôle effectué :**
  - tests sur des sources synthétiques au format réel. Le principal : modifier les observations postérieures à l'origine ne change pas le contexte admissible ;
  - premier essai sur un compteur (Totem 73 bd de Sébastopol S-N) ;
  - alignement horaire prévue / observée : la corrélation des températures est maximale sans décalage (0,987).
- **Versions et liens :** [EXP-E1-03](../experiments/E1-contexte-source-complementaire.md).
- **Résultat et analyse critique :**
  - jointure sans ligne créée ni perdue ;
  - l'alignement horaire est confirmé, mais l'écart entre 0 h et +1 h est faible (0,987 contre 0,985) ;
  - les délais de publication sont des hypothèses.
- **Décision ou adaptation :** livrer le calendrier et la prévision J-2 comme entrées admissibles, et la météo observée comme passé seulement.
- **Partenaire, retour reçu et usage vérifié :** *à compléter*.
- **Prochaine étape :** étendre le contexte aux 113 compteurs.

## 15/11/2026 (soir) - Tout le flux, grille commune, `network_gap` (tâches reprises de Tasnim)

- **Question ou objectif personnel :** passer d'un compteur à tout le réseau, sur une grille horaire commune.
- **Travail réalisé et outils utilisés :**
  - boucle `acquire --tout`, qui produit `flux-20261115` ; groupes de sites ; contexte sur les 113 compteurs (`6cc7544`, 17:16) ;
  - grille commune à tous les compteurs, direction tirée de la fin du nom, drapeau `network_gap` (`ae48cc0`, 21:14). Ces trois tâches étaient au départ celles de Tasnim ;
  - chiffres du contexte mis à jour après la grille commune (`293208c`, 21:28) ;
  - instantané mal daté refusé, `site_group_id` écrit dès `prepare`, brut réellement utilisé noté dans le manifeste, seuils définis à un seul endroit (`1e6d8cf`, 21:44).
- **Expérience ou contrôle effectué :** *à compléter* (tests ajoutés avec les commits).
- **Versions et liens :** `flux-20261115` (`e1-prepare/0.2.0`), `data/manifests/flux-20261115.json`.
- **Résultat et analyse critique :** 113 compteurs sur une grille de 9 503 h.
- **Décision ou adaptation :** *à compléter*.
- **Partenaire, retour reçu et usage vérifié :**
  - Tasnim a relu ce code le 16/11 (`159f12d`, `b325294`) : `network_gap` est maintenant limité aux compteurs actifs, les sites dont un sens manque sont signalés, et les dates sans fuseau sont lues en heure de Paris (voir [son journal](tasnim.md)) ;
  - Zeineb a vérifié l'usage des groupes sur `flux-20261116` : 58 groupes, et les deux sens du Pont National sont réunis ([son journal](E1-zeineb.md)).
- **Prochaine étape :** régénérer l'instantané après la relecture.

## 17/11/2026 - `e1-prepare/0.3.0`, assemblage de l'historique `hist-20261117`

- **Question ou objectif personnel :**
  - appliquer la décision de faire commencer la grille au premier jour complet (le premier jour de la fenêtre est rogné par la source) ;
  - suivre la décision de la réunion E1 du 17/11 : ajouter deux cycles d'un an d'archives avant le flux, sans rupture.
- **Travail réalisé et outils utilisés :**
  - fenêtre au premier jour complet, `e1-prepare/0.3.0` : grille du 16/10/2025 au 14/11/2026, 9 479 h (`c342dd1`, 08:10) ; fiches mises à jour (`7b294f6`) ;
  - `src/data/archives.py` (`e1-archives/0.3.0`), qui assemble les archives Open Data 2023-2025 et le flux, avec les règles suivantes (`12ee747`, 16:50) :
    - R1 : canaux jumeaux additionnés ;
    - R1 bis : compteurs renommés ;
    - R2 : lignes sans identifiant écartées ;
    - R3 : seuls les 113 compteurs du flux sont gardés ;
  - contexte de l'historique : prévision J-2 du modèle JMA GSM jusqu'au 20/01/2024 12:00 UTC, puis du modèle par défaut (`a386912`, 17:10).
- **Expérience ou contrôle effectué :**
  - comparaison heure par heure archive / flux sur la période commune : après la somme des canaux jumeaux, 100 % d'heures identiques ;
  - 49 canaux jumeaux et 7 renommages trouvés ;
  - jointure du contexte : 3 053 599 lignes avant et après.
- **Versions et liens :** `hist-20261117` ; [fiche historique](../experiments/E1-historique.md) ; passation à Sabrina (tâches A1 à A8, B1 à B7).
- **Résultat et analyse critique :**
  - 27 023 h × 113 compteurs, dont 96,6 % d'heures observées ;
  - sans la somme des canaux, certains sens chutaient de 90 à 97 % en janvier 2024 ;
  - la passation décrivait les lignes sans identifiant comme « le total » : Sabrina a montré le 18/11 que ce n'est pas le cas (A4).
- **Décision ou adaptation :** règles R1 à R3 ; priorité aux archives avant le 16/10/2025, au flux ensuite.
- **Partenaire, retour reçu et usage vérifié :**
  - Sabrina a revérifié l'assemblage le 18 et le 19/11 (même nombre de lignes, mêmes empreintes, mêmes statuts), puis a fait le remplissage et la livraison le 19/11 ;
  - E2 utilise `hist-20261117` depuis le 19/11 (E2-TECH-001 à 003, empreintes vérifiées). Son contrôle indépendant du 22/11 conclut « données saines depuis 2023 » ;
  - Tasnim l'a vérifié côté consommateur le 24/11 ([EXP-E1-05](../experiments/E1-verification-livraison.md)).
- **Prochaine étape :** *à compléter*.

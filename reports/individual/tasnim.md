# Journal individuel - Tasnim (équipe 1, E1 données)

## 12/11/2026 - Extraction et préparation d'un compteur réel

- **Question ou objectif personnel :** extraire un premier compteur réel du flux Open Data Paris et le préparer au format du contrat (`counts.csv`, `counters.csv`), sans perdre ni inventer de mesure.
- **Travail réalisé et outils utilisés :**
  - `src/data/acquire.py` : export CSV de l'API v2.1 en `timezone=UTC`, brut déposé intact dans `data/history/`, manifeste avec URL, licence, `retrieved_at` et SHA-256 ;
  - `src/data/prepare.py` : conversion en UTC, grille horaire complète, doublons, drapeaux de qualité ;
  - logique reprise de l'ancien script de l'équipe (`src/phase0.py`, commit `5488590`) ;
  - outils : Python, pandas, httpx, pytest.
- **Expérience ou contrôle effectué :**
  - compteur `100057445-104057445` (Totem 73 bd de Sébastopol S-N) ;
  - 13 tests sur un petit jeu synthétique : zéro conservé, heure absente insérée, doublon en conflit signalé, valeur négative non évaluable, heures ambiguës ou inexistantes du changement d'heure, jour de 25 h, pics horaires, colonnes conformes aux gabarits, BOM de l'export.
- **Versions et liens :** commit `e301f54` ; instantané `flux-20261112` ; `e1-prepare/0.1.0` ; `data/manifests/flux-20261112.json`.
- **Résultat et analyse critique :**
  - 9 377 lignes source placées sur une grille de 9 479 heures, du 13/10/2025 au 11/11/2026, soit une couverture de 98,9 % ;
  - 102 heures absentes, en 7 trous ;
  - 0 doublon, 0 conflit, 0 valeur négative ou invalide, 1 seule heure à zéro ;
  - pics de semaine à 9 h et 18 h (heure de Paris), ce qui est cohérent avec la lecture « la date marque le début de l'intervalle », sans le prouver à l'heure près ;
  - 2 alertes de changement d'heure : 24 heures sur 25 le 26/10/2025, et 0 sur 25 le 25/10/2026. Je les ai comprises le 16/11 (voir ci-dessous).
- **Décision ou adaptation :** trois corrections par rapport à l'ancien script :
  - les heures ambiguës du changement d'heure sont signalées au lieu d'être supprimées ;
  - les doublons en conflit sont signalés au lieu d'un `keep="first"` silencieux ;
  - les longues suites de zéros reçoivent un drapeau rétrospectif `long_zero_run`, qui ne sert pas de variable de prévision.

  `direction` est laissée vide tant que le suffixe du nom n'est pas validé, et `site_group_id` vaut `site_id` par défaut.
- **Partenaire, retour reçu et usage vérifié :** à compléter.
- **Prochaine étape :** passer à tout le flux. C'est Nihed qui l'a fait ensuite (`--tout`, grille commune, direction, `network_gap`).

## 16/11/2026 - Relecture du code écrit à ma place, alertes du manifeste, stabilité de la source

- **Question ou objectif personnel :**
  - comprendre et vérifier le code écrit par Nihed sur mes tâches (boucle `--tout`, grille commune, direction, `network_gap`, refus d'un instantané mal daté) ;
  - expliquer les 236 alertes du manifeste `flux-20261115` ;
  - vérifier si la source modifie les données d'un jour à l'autre.
- **Travail réalisé et outils utilisés :**
  - branche `Team1-tasnim` avancée sur `team1-nihed` (`1e6d8cf`) ;
  - zip `flux-20261115` installé, empreintes SHA-256 vérifiées ;
  - relecture de `prepare.py` et `acquire.py` ;
  - scripts de vérification sur données synthétiques puis réelles ;
  - pytest et ruff.
- **Expérience ou contrôle effectué :**
  1. **`network_gap`** était aussi posé sur des compteurs pas encore installés ou déjà arrêtés. Je l'ai montré avec un compteur synthétique installé après une panne : il recevait `["missing", "network_gap"]`.
  2. **La définition du drapeau** disait « toujours avec 'missing' », mais une valeur vide pendant une panne donnait `["empty_value", "network_gap"]`.
  3. **`direction_checks`** ne signalait pas un site dont un compteur n'a pas de sens, et regroupait les compteurs sans `site_id` en un faux site.
  4. **`snapshot_range`** lisait les dates sans fuseau en UTC, alors que `normalize` les lit en heure de Paris.
  5. **Alertes du manifeste :** 349, dont 113 alertes obsolètes (`site_group_id`, supprimée par `1e6d8cf`), soit 236. Je les ai classées en 4 types, chacun vérifié dans `counts.csv`.
  6. **Pics inattendus :** j'ai comparé les profils horaires des deux sens d'un même site, pour distinguer une erreur de fuseau d'un usage réel.
  7. **Stabilité de la source :** j'ai comparé le même compteur dans `flux-20261112` et `flux-20261115`.
- **Versions et liens :**
  - corrections poussées sur `Team1-tasnim` : `159f12d` (`e1-prepare/0.2.1`) et `b325294` (`e1-prepare/0.2.2`) ; 72 tests passent ;
  - [E1-alertes-manifeste.md](../experiments/E1-alertes-manifeste.md) ;
  - [E1-extraction.md](../experiments/E1-extraction.md) (EXP-E1-01).
- **Résultat et analyse critique :**
  - **Aucune alerte ne remet en cause la convention horaire.**
    - 221 alertes viennent de la source : une heure perdue au passage à l'heure d'hiver 2025, et une journée non publiée le 25/10/2026 ;
    - 7 alertes venaient de compteurs déjà arrêtés : c'est un effet de bord de la grille commune, que j'ai corrigé ;
    - 8 alertes de pics s'expliquent par l'usage. Le sens opposé du même site a bien son pic à 8–9 h, ce qui exclut une erreur de fuseau. Ce sont des sens surtout utilisés le soir, deux compteurs presque vides (porte de Charenton) et un compteur en panne (Denfert-Rochereau).
  - **La source ne corrige ni ne complète les heures déjà publiées :**
    - 9 408 heures identiques sur 9 431 heures communes ;
    - 0 heure comblée sur les 102 qui manquaient le 12/11 ;
    - les 23 différences tombent toutes le 15/10/2025, le début de la fenêtre de 13 mois, que la source rogne.
  - **Un nouveau problème mis au jour :** ces heures rognées sont marquées à tort `network_gap` (1 574 lignes).
  - **Limite :** un seul compteur et 3 jours d'écart.
- **Décision ou adaptation :**
  - `network_gap` et le contrôle des jours de changement d'heure ne s'appliquent plus qu'aux compteurs actifs ;
  - les sites dont un sens manque sont maintenant signalés ;
  - proposition à valider avec l'équipe : faire commencer la grille au premier jour complet de la fenêtre.
- **Partenaire, retour reçu et usage vérifié :**
  - Nihed : j'ai adapté son test sur le compteur `stop` (plus de `network_gap` après l'arrêt). Je lui demande de confirmer que l'ancien comportement n'était pas voulu ;
  - Sabrina : ses chiffres de la fiche zéros reposent sur `e1-prepare/0.2.0`. Ceux qui utilisent `network_gap` sont à revérifier ; `count` et `long_zero_run` ne changent pas ;
  - retours à compléter.
- **Prochaine étape :**
  - récupérer les bruts (`data/history/flux-20261115/`), absents du zip, relancer `prepare --tout` et vérifier qu'il reste 229 alertes ;
  - décider avec l'équipe du traitement du premier jour de la fenêtre ;
  - ouvrir une PR de `Team1-tasnim` vers `Team1`.

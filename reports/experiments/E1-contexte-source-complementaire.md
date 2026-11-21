# EXP-E1-03 - Source complémentaire : calendrier et météo sans information du futur

- **Date, équipe, responsables et partenaires :** 15/11/2026, E1, Nihed (source complémentaire) ; partenaires E2 (sites connus, ablation du contexte), E3 (nouveaux sites, même contexte pour les variantes), E4 (règle de disponibilité). Données d'entrée : comptages de Tasnim (`acquire.py`, `prepare.py`).
- **Question et hypothèse :** quelles informations externes, connues au moment de prévoir, peut-on joindre aux comptages sans créer ni perdre de lignes et sans utiliser le futur ? Hypothèse : le calendrier (jours fériés, vacances) et la météo expliquent une partie des écarts au profil hebdomadaire ; leur intérêt réel sera mesuré par E2.
- **Références :** sujet, « Ajouter une source complémentaire » et « Les règles communes pour comparer les méthodes » ; `doc/CONTRATS.md` §4 (contexte) ; `doc/PROTOCOLE_EVALUATION.md` §2 (information autorisée).
- **Instantané, protocole, code et paramètres :** `src/data/context.py` (`e1-context/0.3.0` depuis le 19/11/2026 : grèves ajoutées ; `e1-context/0.2.0` depuis le 18/11/2026 : calendrier sur une seule ligne par jour, nom dans la colonne `label` ; `e1-context/0.1.0` avant), protocole **proposé, non validé**. Instantané `flux-20261115` (export complet du 15/11/2026) : 113 compteurs, 1 071 127 lignes de comptage (grille commune, `e1-prepare/0.3.0`, régénérée le 17/11/2026), du 16/10/2025 00:00 au 14/11/2026 22:00 UTC. Le premier jour du brut (15/10/2025), rogné par la source, est écarté. Premier essai sur un seul compteur (Totem 73 bd de Sébastopol S-N, 9 500 heures). Paramètres : prévision de J-2, délai de publication d'un run 6 h, latence des observations 24 h, lus dans la section `context` de `config/project.yaml` (commit `f6ef4d8`) pour être validés par E4 sans modifier le code.

## Ce que produit le module

`uv run python -m src.data.context --snapshot <snapshot_id>` (option `--sans-meteo` pour le calendrier seul) écrit dans `data/processed/<snapshot_id>/` :

| Fichier | Contenu | Consommateurs |
| --- | --- | --- |
| `context.csv` | Colonnes exactes du gabarit, format long : une ligne par source, lieu, validité et variable ; pour le calendrier, le nom du jour férié ou des vacances est dans la colonne `label` de la même ligne (vide sinon et pour la météo) | E2, E3, E4, E5 |
| `context_sources.json` | Une fiche par source : URL, licence, géographie, fuseau, unités, règle de jointure, rôle, disponibilité | Toutes |
| `context_join_audit.json` | Lignes avant / après jointure, clés en double, heures sans contexte par variable | E2, E4 |

Les bruts sont conservés intacts dans `data/history/<snapshot_id>/context/` et ajoutés au manifeste avec leur SHA-256. La fonction `admissible_context(contexte, origine)` ne garde que les lignes connues à l'origine.

## Sources retenues

| Source | Variables | Rôle | Licence |
| --- | --- | --- | --- |
| Jours fériés métropole, calendrier.api.gouv.fr | `is_holiday` (nom dans `label`) | `known_calendar` | Licence Ouverte 2.0, à confirmer |
| Calendrier scolaire, data.education.gouv.fr, zone C, académie de Paris | `is_school_holiday` (nom dans `label`) | `known_calendar` | Licence Ouverte 2.0, à confirmer |
| Grèves des transports d'Île-de-France, référentiel E1 (Zeineb, `data/reference/`, liste manuelle datée) | `is_strike` (portée, intensité et réseaux dans `label`) | `known_calendar`, mais connu seulement 24 h avant : `available_at` = minuit (Paris) du jour - 24 h | sources citées jour par jour |
| Open-Meteo, Previous Runs API, prévision de J-2, point Hôtel de Ville | `temp_prev` (°C), `rain_prev` (mm), `wind_prev` (m/s) | `forecast_bulletin` | CC BY 4.0 |
| Météo-France, données horaires, Paris-Montsouris (75114001) | `temp_obs` (°C), `rain_obs` (mm), `wind_obs` (m/s) | `past_observation` | Licence Ouverte 2.0 |

Le calendrier est proposé en premier, comme le suggère le plan du projet : il est connu à l'avance, simple et sans risque de fuite. La météo vient ensuite.

## Décision 1 : ne pas utiliser la météo du futur

Le sujet autorise une prévision météo **publiée avant** le moment où l'on prévoit, et réserve les observations futures à l'analyse.

- **Observation (Météo-France).** Une mesure de l'heure H n'est utilisable que pour une origine postérieure à `available_at = H + 24 h` (publication quotidienne, hypothèse). Elle ne sert jamais pour les heures à prévoir.
- **Prévision (Open-Meteo).** L'API ne donne pas l'heure d'émission du bulletin. La série « previous_day N » garantit seulement que la valeur de l'heure H vient d'un run lancé au plus tard à `H - N×24 h`. Un run est publié quelques heures après son lancement ; on suppose 6 h au plus. D'où `available_at = H - N×24 h + 6 h`.
- **Choix de J-2 plutôt que J-1.** Pour une origine à minuit et 24 heures à prévoir, la dernière heure est H = origine + 24 h.
  - J-2 : `available_at = H - 42 h`, toujours avant l'origine ;
  - J-1 : `available_at = H - 18 h`, donc les heures 19 à 24 utiliseraient un bulletin pas encore publié.

  Un test automatique le vérifie : avec J-2, les 24 horizons sont admissibles ; avec J-1, ils ne le sont pas tous. Une première analyse (vérifications du 11/11) supposait J-1 suffisante ; elle ignorait le délai de publication d'un run et a été corrigée.
- **Coût du choix :** nul en couverture. La prévision de J-2 est renseignée sur 100 % des heures de l'instantané, comme celle de J-1 vérifiée le 11/11. Une prévision plus ancienne est en principe un peu moins précise ; c'est le prix de l'absence de fuite.

## Décision 2 : aligner les heures

- **Calendrier :** jointure sur la date locale (Europe/Paris) du **début** de l'heure comptée. Les deux heures « 2 h » du jour de 25 heures appartiennent bien au 25 octobre.
- **Météo :** jointure sur la **fin** de l'heure comptée (`interval_end`). Chez Météo-France, la pluie de l'heure H est le cumul de l'heure qui se termine à H ; Open-Meteo suit la même convention. Comptage et météo décrivent ainsi la même heure.
- **Vacances :** un jour est en vacances si `début <= jour < reprise`, le jour de reprise étant exclu.

## Contrôles réalisés

Automatiques, dans `tests/test_data_context.py` (23 tests au 19/11/2026, sources synthétiques au format réel) :

- colonnes identiques au gabarit `doc/templates/context.csv`, booléens `true`/`false`, clé unique (un doublon est refusé) ;
- jours fériés : une seule ligne par jour, valeurs explicites `false` hors jours fériés, nom dans `label` (vide hors jours fériés) ; le nom est aussi présent après jointure (`is_holiday_label`) ;
- conversion d'un `context.csv` de l'ancien format (`--migrer`) : lignes de nom retirées, nom passé dans `label`, valeurs inchangées ;
- vacances : zone C seulement, enseignants exclus, académie de Paris prioritaire, doublons fusionnés, jour de reprise exclu, jour de 25 heures compris ;
- météo observée : station filtrée, virgule décimale lue, heures en UTC, disponibilité à +24 h ;
- prévision : unité du vent contrôlée (m/s), règle J-2 / J-1 vérifiée sur 24 horizons ;
- **modifier les observations postérieures à l'origine ne change pas le contexte admissible** ;
- jointure sur un jour de 25 heures : aucune ligne créée ni perdue ; heures sans contexte comptées.
- hypothèses de disponibilité lues dans `config/project.yaml`, valeurs par défaut sinon, délai bien appliqué.
- grèves : une ligne par jour recensé (aucune hors du référentiel), `label` rempli les jours de grève, `available_at` 24 h avant minuit ; une grève n'est admissible que 24 h avant, alors qu'un jour férié l'est toujours ; jointure sur la date de Paris (23 h UTC = minuit le lendemain).

Sur données réelles (`flux-20261115`, 113 compteurs ; chiffres vérifiés le 18/11/2026 sur le `context.csv` converti en `e1-context/0.2.0`, grèves ajoutées le 19/11/2026) :

| Contrôle | Résultat |
| --- | --- |
| Lignes de comptage avant / après jointure | 1 071 127 / 1 071 127 ; 0 clé en double ; statut `ok` |
| Lignes de `context.csv` | 57 556 (format long ; 58 348 avant la conversion du 18/11, qui retire les 2 × 396 lignes de nom sans changer aucune valeur) |
| Calendrier | 396 jours (16/10/2025 au 15/11/2026), 0 ligne de comptage sans valeur ; 13 jours fériés, tous corrects |
| Grèves (19/11/2026) | 396 jours, dont 11 de grève ; `context.csv` 57 556 → 57 952 lignes ; 0 ligne de comptage sans valeur. Sur `hist-20261117` : 1 127 jours, dont 33 de grève, 0 ligne sans valeur |
| Vacances zone C 2025-2026 | Toussaint 18/10–02/11, Noël 20/12–04/01, hiver 21/02–08/03, printemps 18/04–03/05, pont de l'Ascension 14–17/05, été à partir du 04/07 : conformes au calendrier officiel |
| Météo prévue (J-2) | 9 481 heures par variable, 0 ligne de comptage sans valeur |
| Météo observée | 9 480 heures pour la température et le vent, 9 361 pour la pluie. Lignes de comptage sans valeur : 113 (0,01 %, une seule heure, le 31/10/2025) pour la température et le vent, 13 560 (1,3 %) pour la pluie. Avant le 17/11, la grille commençait le 15/10/2025 et ces nombres étaient de 2 260 et 15 707. Manques de la station, signalés, non remplacés |
| Unités plausibles (premier essai) | température −4,2 à 40,5 °C (observée), vent moyen 3,0 m/s (observé) et 2,4 m/s (prévu), pluie max 25,9 mm/h (observée) et 8,8 mm/h (prévue) |
| Alignement horaire prévue / observée (premier essai) | corrélation des températures 0,960 (−2 h), 0,978 (−1 h), **0,987 (0 h)**, 0,985 (+1 h), 0,972 (+2 h) : maximum sans décalage |

## Analyse, limites et décision

- **Décision :** livrer le calendrier et la météo prévue de J-2 comme entrées admissibles ; la météo observée comme passé admissible ou comme analyse après coup.
- L'alignement horaire est confirmé, mais l'écart entre 0 h et +1 h est faible (0,987 contre 0,985) : la température varie lentement. Un contrôle plus discriminant pourra utiliser la pluie et la chute des comptages.
- Les délais de publication (6 h pour un run, 24 h pour les observations) sont des **hypothèses versionnées**, à valider avec E4 et le professeur. Elles ne reconstituent pas exactement l'historique des publications.
- La prévision archivée n'existe qu'à partir de 2024 (avant : température seule). Pour les archives 2016–2023, seule la météo observée serait disponible.
- La prévision est un point (Hôtel de Ville) et l'observation une station (Montsouris), pour tout le réseau : l'écart local de météo entre compteurs n'est pas représenté.
- Les licences des deux sources de calendrier sont à confirmer sur leurs pages officielles.
- **L'intérêt de la source n'est pas encore mesuré.** Il le sera avec E2 et E4 : même modèle, mêmes cas, avec et sans calendrier, puis avec et sans météo prévue. Une absence de gain sera une conclusion valable.

## Lien vers les données et retours des partenaires

- Données : `data/processed/<snapshot_id>/context.csv`, `context_sources.json`, `context_join_audit.json`.
- Retour d'E4 sur la règle de disponibilité : *à renseigner*.
- Preuve d'usage par E2 (ablation du contexte) et par E3 (même contexte pour les variantes gelée et adaptée) : *à renseigner*.

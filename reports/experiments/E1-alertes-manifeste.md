# E1 - Les 236 alertes du manifeste `flux-20261115`

- **Auteure :** Tasnim (tâche 4 de la répartition E1).
- **Entrée :** `data/manifests/flux-20261115.json` (zip de l'équipe 1, préparé avec `e1-prepare/0.2.0`), et `data/processed/flux-20261115/counts.csv` pour vérifier.
- **But :** expliquer chaque type d'alerte par compteur (`counters.<id>.alerts`) et dire s'il demande une action.

## Décompte

Le manifeste contient **349** alertes sur 113 compteurs. **113** viennent de l'ancienne alerte « `site_group_id = site_id ici : relancer quality.py` », une par compteur. Elle a été supprimée par le commit `1e6d8cf`, parce que `prepare --tout` écrit maintenant les groupes lui-même. Il reste **236 alertes réelles** :

| Type | Nombre | Compteurs | Origine | Action |
| --- | ---: | ---: | --- | --- |
| A. Passage à l'heure d'hiver du 26/10/2025 : 24/25 heures | 113 | 113 (tous) | Source | Aucune ; à documenter |
| B. Passage à l'heure d'hiver du 25/10/2026 : 0/25 heures | 108 | 108 | Source (journée non publiée) | Aucune ; déjà `network_gap` |
| C. Jour de changement d'heure après l'arrêt du compteur | 7 | 5 | Effet de bord de la grille commune | Corrigé (`e1-prepare/0.2.2`) |
| D. Pics de semaine hors de ~8 h / ~18 h | 8 | 8 | Usage réel ou compteur en panne | Aucune sur le fuseau ; voir détail |
| **Total** | **236** | | | |

Le jour de passage à l'heure d'été du 29/03/2026 est complet (23/23) pour les 111 autres compteurs.

## A. 26/10/2025 : une heure perdue à la source sur tout le réseau (113 alertes)

Le 26/10/2025, la journée locale compte 25 heures. Pour chaque compteur, une seule manque : **2025-10-26T00:00Z**, c'est-à-dire **2 h du matin heure d'été (CEST)**, la première des deux « 2 h ». Elle manque pour les 113 compteurs à la fois et elle est marquée `missing` + `network_gap`. L'heure d'avant (22:00Z) et les deux suivantes (01:00Z, 02:00Z) sont observées partout.

**Explication probable (non vérifiée auprès de la source) :** la source agrège en heure locale. Les deux « 2 h » de cette nuit-là se confondent, et une seule est publiée. Ce n'est ni un défaut du compteur ni un défaut de notre préparation : notre code garde les heures ambiguës et les signale (`dst_ambiguous`). Ici, l'heure n'est jamais arrivée.

**Recoupement :** le même trou apparaît déjà dans `flux-20261112` (compteur `100057445-104057445`, extrait trois jours plus tôt). Il ne dépend donc pas de la date d'extraction, et la source ne l'a pas comblé depuis (voir [EXP-E1-01](E1-extraction.md)).

**Conséquence :** 1 heure non évaluable par compteur. Il n'y a rien à corriger, mais il faut le signaler à E4 : une heure manquante au changement d'heure n'est pas un trou du compteur.

## B. 25/10/2026 : journée entière non publiée (113 alertes)

Le 25/10/2026, aucun compteur n'a d'heure observée sur la journée locale (0/25). Le manifeste lève cette alerte pour les 113 compteurs, mais 5 d'entre eux étaient déjà arrêtés : leurs alertes sont classées en C. Il en reste 108. Toutes les heures sont `missing` et presque toutes `network_gap` (2 599 lignes ce jour-là, plus 226 le 24/10 au soir).

**Explication :** c'est une panne de publication de tout le réseau, pas un problème de changement d'heure. Elle tombe un jour de changement d'heure par hasard. Le même motif d'environ 22 h sans données sur tout le réseau revient le 22/08, le 23/09 et le 04/10/2026 (2 486 lignes `network_gap` chacun).

Cette journée manquait déjà le 12/11 dans `flux-20261112`, et elle n'a pas été publiée depuis : ce n'est pas un simple retard de publication.

**Conséquence :** déjà traitée par `network_gap`. Pour E4, cette journée ne peut pas servir de cas d'évaluation (pas de cible) ; pour E5, prévoir un message « données non publiées ».

## C. Jour de changement d'heure après l'arrêt du compteur (7 alertes, 5 compteurs)

| Compteur | Dernière mesure | Alertes concernées |
| --- | --- | --- |
| `100047545-103047545` | 19/02/2026 | 29/03/2026 (0/23) et 25/10/2026 (0/25) |
| `100047545-104047545` | 19/02/2026 | 29/03/2026 (0/23) et 25/10/2026 (0/25) |
| `100036718-103036718` (quai de l'Hôtel de Ville) | 05/07/2026 | 25/10/2026 (0/25) |
| `100036718-104036718` (quai de l'Hôtel de Ville) | 05/07/2026 | 25/10/2026 (0/25) |
| `100003098-101003098` (106 av. Denfert-Rochereau) | 12/08/2026 | 25/10/2026 (0/25) |

**Explication :** ces alertes sont un effet de bord de la grille commune. Depuis `e1-prepare/0.2.0`, chaque compteur a toutes les heures de l'instantané, et le contrôle des jours de changement d'heure (`dst_days`) s'appliquait aussi après l'arrêt. L'absence de mesure y vient de l'arrêt du compteur, pas du changement d'heure. Avec l'ancienne grille propre au compteur, ces alertes n'existaient pas.

**Correction (`e1-prepare/0.2.2`) :** `dst_days` ne contrôle plus que les jours où le compteur est actif, entre sa première et sa dernière mesure. C'est la même règle que pour `network_gap` (`e1-prepare/0.2.1`). Test : `test_changement_d_heure_pas_controle_apres_l_arret`. Vérifié sur `counts.csv` de `flux-20261115` : il reste 221 alertes de changement d'heure (113 + 108), et les 2 compteurs `100047545` n'ont plus que l'alerte A.

## D. Pics de semaine inattendus (8 alertes)

Le contrôle cherche le maximum de la moyenne de semaine entre 5 h et 12 h (matin), puis entre 14 h et 21 h (soir). Il attend environ 8 h et 18 h, heure de Paris. Un écart pourrait signaler une erreur de fuseau.

**Ce n'est pas une erreur de fuseau.** Une erreur de fuseau décalerait les 113 compteurs de la même façon. Or ici, le **sens opposé du même site** a bien son pic vers 8 h–9 h :

| Compteur alerté | Pics | Sens opposé du même site | Lecture |
| --- | --- | --- | --- |
| 18 quai de l'Hôtel de Ville NO-SE | 12 h / 18 h | 103036719 : pic à 8–9 h | Sens « retour » : matin faible (36/h à 8 h), midi légèrement plus fort (38/h) |
| Totem 64 rue de Rivoli O-E | 12 h / 18 h | 103050876 : 677/h à 9 h | 307/h à 12 h contre 270/h à 9 h dans ce sens ; soir très fort (811/h) |
| 38 rue Turbigo SO-NE | 12 h / 18 h | 103056334 : 387/h à 9 h | Même profil : sens surtout utilisé le soir |
| 29 boulevard des Batignolles O-E | 12 h / 18 h | 353406823 : 325/h à 9 h | Même profil |
| Pont des Invalides (couloir bus) N-S | 12 h / 18 h | — | 105/h à 12 h contre 102/h à 9 h : matin et midi presque à égalité |
| Face au 8 av. de la porte de Charenton SE-NO | 11 h / 18 h | — | Comptages de 1 à 3 vélos par heure : profil trop faible pour situer un pic |
| Face au 8 av. de la porte de Charenton NO-SE | 12 h / 18 h | — | 3 à 10 vélos par heure, même remarque |
| 106 avenue Denfert-Rochereau NE-SO | 5 h / 14 h | — | Compteur en panne : 7 207 heures de zéros longs, couverture 76 % ; déjà exclu de l'étude (fiche zéros) |

**Explication :** dans 5 cas, le sens alerté est le sens des trajets du soir. Le matin y est faible, et l'activité de midi dépasse de peu le creux de 8 h–9 h. Le pic du soir est, lui, toujours à 18 h. Les 2 compteurs de la porte de Charenton comptent trop peu de vélos pour que le profil veuille dire quelque chose. Denfert-Rochereau est en panne.

**Action proposée :** aucune sur l'heure. On pourrait rendre le contrôle plus fiable en le faisant au niveau du site (somme des deux sens) plutôt que par sens. Les compteurs Charenton (volumes très faibles) sont à signaler à la sélection (`quality.py`).

## Résumé

- Aucune des 236 alertes ne remet en cause la convention horaire (UTC, début d'intervalle, heure de Paris pour les profils).
- 221 alertes (A et B) viennent de la source : une heure perdue au passage à l'heure d'hiver 2025, et une journée non publiée le 25/10/2026.
- 7 alertes (C) étaient un effet de bord de la grille commune ; corrigé dans `e1-prepare/0.2.2` (commit `b325294`).
- 8 alertes (D) décrivent des usages réels (sens du soir, très faibles volumes) ou une panne déjà connue.
- Quand `flux-20261115` sera relancé avec `e1-prepare/0.2.2`, le manifeste devrait compter **229** alertes (113 A + 108 B + 8 D). À vérifier dès que le brut sera disponible : il manque dans le zip.

## Reproduire

```bash
# Données : zip de l'équipe 1 décompressé dans data/ (processed/ et manifests/)
uv run python - <<'PY'
import json, re, collections
m = json.load(open("data/manifests/flux-20261115.json"))
alerts = [a for c in m["counters"].values() for a in c["alerts"] if not a.startswith("site_group_id")]
types = collections.Counter(re.sub(r"\d+ h et \d+ h", "X h et Y h", a.split(" :")[0]) for a in alerts)
print(len(alerts), "alertes")
for t, n in types.most_common():
    print(n, t)
PY
```

Pour recompter après correction (`e1-prepare/0.2.2`) sans le brut, appliquer `src.data.prepare.dst_days` à chaque compteur de `counts.csv` : 221 alertes de changement d'heure au lieu de 228.

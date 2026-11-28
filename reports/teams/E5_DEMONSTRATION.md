# ParisPulse - Démonstration de l'application (E5)

Trois parcours pour la restitution finale. Les compteurs, dates et méthodes ont été choisis
**après des calculs réels** sur l'instantané `hist-20261117`, et non inventés. Ils ont été
rejoués dans l'interface (`streamlit.testing`) le 28/11/2026, sur la branche `Team5-VF-docs`
issue de `dev` (commit `8268d23`). Les chiffres ci-dessous sont ceux affichés par l'application.

Toutes les dates sont dans la **validation** (juin–août 2026) : aucune démonstration ne touche au
test final réservé (1er octobre au 14 novembre 2026).

## Préparer la machine (avant la séance)

1. Installer et extraire les données (voir le [README](../../README.md#lancer-lapplication)).
2. Lancer l'application et **faire une fois la démo 2** : le premier calcul Chronos-2 télécharge
   les poids depuis Hugging Face (environ 2 minutes mesurées). Ensuite, ils sont en cache et
   chaque calcul prend moins d'une seconde.
3. Garder une copie locale des ressources : la démonstration ne doit pas dépendre du réseau. Sans
   Internet, le fond de carte ne s'affiche pas, mais le menu **Compteur et sens**, les
   prévisions et l'export fonctionnent.

## Démo 1 - Site connu

**Message** : sur un site avec historique, le HGB d'E2 prévoit les 24 heures avec le contexte E1,
et on compare honnêtement aux références.

| Réglage | Valeur |
| --- | --- |
| Périmètre | Sites connus |
| Compteur et sens | **89 boulevard de Magenta · NO-SE** (`100047533-101047533`) |
| Date de départ | **31/08/2026** (lundi, date proposée par défaut) |
| Méthode | HGB (modèle entraîné) |

Étapes :

1. Cliquer sur le point de Magenta sur la carte, puis choisir le sens NO-SE.
2. Onglet **Historique disponible** : montrer que seul le passé publié est utilisé.
3. **Calculer la prévision**, puis commenter le graphique et le tableau des 24 heures.
4. Montrer les mesures réelles et l'erreur.
5. **Télécharger l'étude (.zip)** et ouvrir le manifeste.
6. Facultatif : passer la méthode à **Comparer les deux références**.

Résultats affichés :

| Méthode | MAE du cas (vélos/h) | Heures prédites |
| --- | ---: | ---: |
| HGB | **45,5** | 24 / 24 |
| Même heure la semaine précédente | 47,2 | 24 / 24 |
| Médiane des quatre semaines précédentes | 67,3 | 24 / 24 |

Autres valeurs à l'écran : 0 heure en repli, 24 heures comparées sur 24, 696 heures mesurées
sur 720 dans les 30 jours précédents, calcul en 0,4 s. Le trafic culmine à 639 vélos/h à 9 h.

À dire : la MAE représente environ 19 % du trafic moyen (245 vélos/h) ; c'est un seul cas, pas le
score officiel E4 (22,25 en moyenne sur 95 compteurs). La médiane des quatre semaines est
nettement moins bonne ici ; hypothèse non vérifiée : ces semaines tombent en août, mois de
faible trafic.

## Démo 2 - Nouveau site

**Message** : avec peu d'historique local, Chronos-2 prévoit quand même ; la quantité
d'historique compte plus que l'adaptation.

| Réglage | Valeur |
| --- | --- |
| Périmètre | Nouveaux sites |
| Compteur et sens | **56 boulevard Kellermann · E-O** (`300030139-353355137`, `S_dev_new`) |
| Budget d'historique local | 24 heures, puis 168 heures |
| Départ des 24 heures à prévoir | **12/08/2026 à 00:00 · proto-v1** (mercredi) |
| Méthode | Comparer Chronos-2 avant et après adaptation |

Étapes :

1. Choisir le compteur, le budget **24 heures**, le départ du 12/08/2026.
2. **Calculer la prévision** : les deux courbes (gelé et adapté v2) s'affichent sur le même
   historique local. Lire le message sur l'adaptation v2.
3. Recommencer avec le budget **168 heures**.
4. Onglet **Données manquantes** : montrer que la courbe suit seulement la fenêtre locale.

Résultats mesurés (MAE du cas, vélos/h, 24 heures comparées sur 24) :

| Budget local | Chronos-2 gelé | Chronos-2 adapté v2 |
| --- | ---: | ---: |
| 24 h | 16,3 | **14,4** |
| 72 h | **9,2** | 9,8 |
| 168 h | 6,8 | **6,5** |

À dire :

- Passer de 24 h à 168 h d'historique divise l'erreur par plus de deux ; l'adaptation change
  l'erreur de moins de 2 vélos/h.
- L'adaptation n'aide pas toujours : à 72 h, elle est moins bonne ici. Sur les 5 sites
  `S_dev_new` le 12/08/2026, l'adaptée fait mieux dans 10 cas sur 15.
- Chronos-2 n'est pas réentraîné ; les poids du mélange ont été choisis par E3 sur ces mêmes
  cas de validation : le gain est probablement optimiste.

## Démo 3 - Cas difficile

**Message** : quand le modèle refuse ou que les données manquent, l'application le dit et le
montre, au lieu de cacher le problème.

### 3a - Refus du modèle et repli

| Réglage | Valeur |
| --- | --- |
| Périmètre | Sites connus |
| Compteur et sens | **12 avenue de la Porte de Bagnolet · E-O** (`300030838-353360366`) |
| Date de départ | **20/06/2026** (samedi) |
| Méthode | HGB (modèle entraîné) |

Affichage : « Le HGB n'a pas prévu ce cas : Date antérieure à la fin de l'apprentissage du HGB.
Les valeurs affichées viennent de la référence hebdomadaire. » 24 heures prédites, **24 heures
avec repli**, MAE 9,0 vélos/h. Dans le tableau, chaque heure porte le statut *Avec repli* et sa
raison.

À dire : le HGB a appris jusqu'au 1er juillet 2026 ; il refuse une date antérieure, pour ne
pas prévoir une période qu'il a vue pendant son apprentissage. Le système reste complet grâce
au repli.

### 3b - Données manquantes

| Réglage | Valeur |
| --- | --- |
| Compteur et sens | **27 quai de la Tournelle · SE-NO** (`100056336-103056336`) |
| Date de départ | **12/08/2026** (mercredi) |
| Méthode | HGB (modèle entraîné) |

Affichage : 24 heures prédites, mais **12 heures comparées sur 24** (les 12 premières heures de
la journée n'ont pas de mesure), MAE 73,4 vélos/h. **376 heures mesurées sur 720** dans les 30
jours précédents. Onglet **Données manquantes** : montrer les trous sous la courbe.

À dire : une heure sans mesure n'est jamais comptée comme une erreur de zéro ; le score ne porte
que sur les 12 heures mesurées, qui incluent le pic du soir (471 vélos/h). Le score de ce cas
est donc élevé et peu représentatif.

## Ce qu'il ne faut pas montrer comme un succès

- La MAE d'un seul cas n'est pas le résultat du projet : renvoyer aux scores E4 du
  [README](../../README.md#résultats-de-validation).
- Ne pas choisir de date d'octobre ou de novembre 2026 : c'est le test final réservé.
- Les sites `S_test_new` ne doivent pas servir à régler une méthode.

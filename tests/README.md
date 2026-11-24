# Vérifications à implémenter

Ces scénarios sont un plan de tests ; aucun test applicatif n'est encore écrit.

L'environnement fournit pytest et Ruff : lancer `./run.sh setup`, puis `./run.sh check` pour les vérifications de code, et `./run.sh test` pour les futurs tests. Tant qu'il n'existe aucun test, pytest retourne le code 5 ; cela ne constitue pas une validation applicative. Voir le [guide de développement](../doc/ENVIRONNEMENT.md).

| Contrôle | Responsable / partenaire | Attendu |
| --- | --- | --- |
| Schémas CSV, clé compteur/heure et jointure du contexte | E1 / E2–E4 | Clés uniques, nombre de lignes expliqué et colonnes conformes |
| Zéro, heure absente et conflit de doublon | E1 / E4 | Trois situations distinctes ; cibles invalides non imputées |
| Référence calculée à la main | E2 / E4 | Même résultat, dont un zéro et un repli |
| 24 horizons et changement d'heure | E2/E3 / E4 | 24 intervalles UTC consécutifs et bon affichage local |
| Modification du futur ou d'une donnée non publiée | E2/E3 / E4 | Prévision et variables inchangées ; audit aussi de l'entraînement |
| Groupes de sites réservés | E1/E3 / E4 | Toutes les directions d'un même site hors apprentissage initial |
| Budget local et adaptation | E3 / E4 | Mêmes observations autorisées ; normalisation sans mesures masquées |
| MAE, cas incomplet et observation absente | E4 / E2/E3 | Moyenne entre compteurs, cas communs et échecs comptés |
| Révélation, changement de sélection et export | E5 / E4 | Aucun dévoilement prématuré ; prévision inchangée après révélation |
| Cache, copie neuve et recalcul d'un autre cas | E5 / autre équipe | Versions cohérentes, ressources complètes et procédure reproductible |

Commencer par de petits exemples créés par les étudiants, puis un cas réel partagé. Les données synthétiques servent à vérifier le code, pas à annoncer des performances sur Paris. Ajouter les tests automatisés utiles au fur et à mesure de l'implémentation.

## Fiabilité, export et parcours complet - E5

Lancer : `uv run --locked --group dl pytest tests/test_reliability.py tests/test_parcours_complet.py tests/test_parcours_reel.py tests/test_export.py`.

| Fichier | Données | Ce qui est vérifié |
| --- | --- | --- |
| `test_reliability.py` | synthétiques | Mesures exactement lues par la méthode (24 pour « semaine précédente », 96 pour le profil 4 semaines, le budget local pour un nouveau site) ; l'annonce « N mesures manquent » est égale au nombre d'heures ensuite en repli ; heure estimée par E1 non comptée ; zéro observé compté ; futur et période non publiée jamais lus ; blocage seulement si aucune mesure sur 4 semaines ; horizons absents/en double, valeurs vides ou négatives ; messages lisibles pour codes `status_reason` et exceptions |
| `test_parcours_complet.py` | synthétiques | Contrôle → prévision → export masqué → révélation → export, sur un cas normal, un cas difficile (panne de 6 h : 6 replis, cible manquante : 23 heures comparées), un compteur sans historique et un nouveau site ; aucune cible ni score dans le zip avant révélation ; empreinte SHA-256 de chaque fichier vérifiée ; `scores.csv` (MAE, RMSE, biais, couverture) ; prévision inchangée après révélation |
| `test_parcours_reel.py` | instantané E1 `hist-20261117`, ignoré s'il est absent | Six cas réels décrits en tête du fichier : normal, une mesure manquante, semaine précédente vide, cibles absentes le 25/10/2026 (score nul et expliqué, jamais zéro), compteur sans historique, nouveau site |
| `test_export.py` | synthétiques | `export_study` : colonnes du contrat, format `true`/`false`/vide/JSON, observations et scores absents avant révélation, identifiant de dossier sûr, manifeste non falsifiable |

Validation du contrôle d'historique sur 3 783 cas réels (97 sites connus × 39 origines, octobre–novembre 2026) : le nombre de mesures manquantes annoncé avant le calcul est égal au nombre d'heures en repli dans 100 % des cas, et le blocage correspond exactement aux 156 cas où la référence ne produit aucune heure.

Module testé : `src/app/reliability.py`, appelé par `streamlit_app.py` avant le calcul (historique, bouton désactivé si aucune mesure) et après (détail des heures sans prévision, message clair si une méthode échoue). L'export `study_zip` ajoute après révélation `scores.csv` et inscrit dans `manifest.json` l'empreinte SHA-256 de chaque fichier.

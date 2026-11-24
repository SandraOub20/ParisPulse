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

Lancer : `uv run --locked --group dl pytest tests/test_reliability.py tests/test_parcours_complet.py tests/test_export.py`. Données synthétiques uniquement.

| Fichier | Ce qui est vérifié |
| --- | --- |
| `test_reliability.py` | Historique requis selon la méthode (168 h, 4 semaines, budget local E3) ; historique complet, partiel ou absent ; zéro observé compté comme mesure ; heures cibles et non publiées jamais comptées ; horizons absents ou en double, valeurs vides ou négatives ; traduction des codes `status_reason` et des exceptions en messages lisibles |
| `test_parcours_complet.py` | Parcours de l'interface (contrôle → prévision → export masqué → révélation → export) sur un **cas normal**, un **cas difficile** (panne de 6 h avant l'origine et heure cible manquante : 6 replis, 23 heures comparées), un compteur sans historique (24 heures `unavailable`, expliquées) et un **nouveau site** (support local de 168 h puis de 24 h) ; aucune cible dans le zip avant révélation ; prévision inchangée après révélation |
| `test_export.py` | `export_study` : colonnes du contrat, format `true`/`false`/vide/JSON, observations et scores absents avant révélation et supprimés d'un export révélé précédent, identifiant de dossier sûr, manifeste non falsifiable |

Module testé : `src/app/reliability.py`, appelé par `streamlit_app.py` avant le calcul (historique, bouton désactivé si aucune mesure) et après (détail des heures sans prévision).

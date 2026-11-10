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

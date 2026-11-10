# ParisPulse - Suivi, contributions et remise

Version du **10 novembre 2026**. Les exigences et barèmes viennent de « Déroulement et livrables » et « Évaluation du projet » du [sujet étudiants](../ParisPulse_Sujet_etudiants.docx). Les formats de suivi ci-dessous sont des propositions pratiques.

## 1. Ce qui est évalué

Trois notes sur 20 : **C** pour la classe, **G** pour l'équipe, **I** pour l'étudiant.

**Note finale = 0,30 × C + 0,40 × G + 0,30 × I.**

C apprécie globalement l'avancement, l'ambition effectivement explorée, l'utilisabilité et l'implication collective, sans sous-points fixes. Qualité des comparaisons, périmètre, intégration et explication des limites comptent davantage qu'un nombre de compteurs ou un meilleur score isolé.

| Note de groupe G | Points |
| --- | ---: |
| Qualité technique de la mission | 6 |
| Expérimentation et interprétation | 5 |
| Intégration reproductible et échanges vérifiés | 4 |
| Collaboration et transmission | 3 |
| Rapport et présentation clairs et étayés | 2 |
| Total | 20 |

| Note individuelle I | Points |
| --- | ---: |
| Question et protocole | 4 |
| Expérience et contrôles | 6 |
| Analyse critique et adaptation | 6 |
| Transmission et usage vérifié | 4 |
| Total | 20 |

G et I peuvent atteindre 20 indépendamment de C. Le volume de code ou de texte ne prouve pas à lui seul une contribution ; chaque étudiant doit pouvoir expliquer une expérience, ses vérifications, une décision et son usage par d'autres.

## 2. Checklist collective avant l'évaluation

- [ ] Application packagée, README avec prérequis et une commande d'installation/préparation/lancement.
- [ ] Données, code, paramètres et poids nécessaires fournis ou récupérés par la procédure, sans chemin personnel.
- [ ] Manifestes, sources, licences, dates d'extraction et conventions temporelles conservés.
- [ ] Inventaire du réseau, échantillon justifié, sites réservés et profils difficiles documentés.
- [ ] Source complémentaire intégrée, cardinalité de jointure contrôlée et intérêt mesuré.
- [ ] Au moins une expérience de deep learning exécutée et analysée.
- [ ] Sites connus et nouveaux sites accessibles ; méthode gelée/adaptée comparée à information locale équivalente.
- [ ] Protocole validé par le professeur avant sélection ; dates finales restées réservées.
- [ ] MAE par compteur puis moyenne, mêmes cas complets, couverture, coût et causes de refus publiés.
- [ ] Référence et replis exécutables ; système complet évalué en distinguant méthode principale et repli.
- [ ] Carte distinguant inventaire, données chargées et prévisions réellement prises en charge.
- [ ] Export comprenant prévisions, scores, provenance, périmètre et conditions de cache.
- [ ] Test intégré sur un cas ordinaire, un cas avec manque et un nouveau site.
- [ ] Extension mesurée, dont un compteur plus difficile ; périmètre partiel expliqué si nécessaire.
- [ ] Copie neuve testée par une autre équipe ; autre cas admissible réellement recalculé.
- [ ] Redémarrage puis traitement d'un nouveau cas vérifiés ; cache valide et invalidation testée.
- [ ] Présentation collective avec démonstration, présentations et rapports par équipe préparés.
- [ ] Journaux individuels datés et reliés aux expériences et retours des partenaires.

Les durées de présentation, nombre de pages, format et lieu de dépôt ne sont pas fixés dans le sujet ; les demander au démarrage sans retarder le travail technique.

## 3. Fiche d'expérience commune

Créer une fiche par comparaison dans un emplacement cible tel que `reports/experiments/EXP-xxx.md` :

| Champ | À renseigner |
| --- | --- |
| Question et hypothèse | Effet attendu et raison, avec référence bibliographique si utile |
| Propriétaire et partenaires | Qui réalise, consomme et contrôle le résultat |
| Versions | Instantané, protocole validé, code, modèle, contexte, support local et graines |
| Population | Scénario, sites, dates, budgets d'information et nombre de cas attendus |
| Comparaison | Facteur modifié, facteurs conservés, budget de calcul et règle de choix |
| Vérifications | Alignement, fuite, masques, manuel ou perturbation selon l'expérience |
| Résultats | MAE, cas complets/comparables, échecs, coût et figures ou tables liées |
| Interprétation | Conclusion, limites, résultat nul ou défavorable, causes établies ou hypothèses |
| Décision et transmission | Changement retenu ou non, composant intégré, retour du consommateur |

Ne pas remplir des résultats estimés comme s'ils avaient été mesurés. Séparer validation et test ; une expérience postérieure au test est exploratoire et ne remplace pas le résultat de la version figée.

## 4. Journal individuel à tenir au fil du projet

Emplacement cible : `reports/individual/<identifiant>.md`. Une entrée après chaque travail significatif ; conserver les retours reçus et les liens vers fichiers, expériences, revues ou résultats.

```text
Date et journée :
Question / objectif personnel :
Travail réalisé et outils utilisés :
Comparaison ou contrôle effectué :
Données, protocole et versions :
Résultat obtenu, avec lien vers la preuve :
Analyse critique et décision :
Partenaire / retour reçu / usage vérifié :
Prochaine étape :
```

Une entrée utile décrit par exemple une jointure qui multipliait les lignes, le contrôle qui l'a révélé, la correction comparée et la confirmation d'un consommateur. « J'ai travaillé sur les données » ne permet pas d'évaluer la démarche.

## 5. Rapport et présentation par équipe

Trame proposée : question étudiée ; choix bibliographiques ; données autorisées et protocole ; méthodes comparées ; vérifications ; résultats avec erreur/couverture/coût ; cas d'échec ; contribution et utilisation des partenaires ; recommandation et limites.

Relier les affirmations aux fiches d'expérience et artefacts. Une absence de gain peut être une bonne conclusion si elle résulte d'une comparaison contrôlée. Chaque membre doit pouvoir expliquer au moins une décision et un contrôle sans dépendre uniquement du référent de l'équipe.

## 6. Installation croisée et répétition

Consigner : version remise, système et prérequis du testeur, copie neuve utilisée, commande exécutée, ressources préparées, durée, problème éventuel et correction vérifiée.

Parcours de contrôle : ouvrir l'inventaire ; cas ordinaire ; prévision et révélation ; export ; cas avec manque ; nouveau site sans/avec adaptation ; arrêter et relancer ; choisir un autre cas admissible ; forcer le recalcul de la référence. Pour l'extension, ajouter un compteur difficile et vérifier que son échec éventuel reste visible.

La démonstration collective présente le besoin, le périmètre réel, les deux situations, un succès, un échec et les recommandations. Préparer une copie locale des ressources essentielles pour ne pas dépendre d'un téléchargement pendant la restitution.

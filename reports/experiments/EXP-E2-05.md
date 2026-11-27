# EXP-E2-05 - Apprendre avec des fenêtres masquées rend-il le MLP plus robuste aux historiques incomplets ?

> **Statut : terminée le 2026-11-27.** Figée le 2026-11-24 pour le code et l'apprentissage, précisée au point 8 avant les scores. **Décision, selon la règle : on garde A** ; le masquage aide nettement sur les semaines trouées, mais B perd un peu sur les semaines complètes. Même population et même calcul du score que [EXP-E2-03](EXP-E2-03.md).

- **Date, équipe, responsables et partenaires** :
  - Brouillon le 2026-11-24, E2.
  - Responsable : **Idir** (comparaison individuelle ; préparation des données du MLP, `build_windows`, MOD-007).
  - Avec Esther pour l'apprentissage (`fit_mlp`, MOD-008).
  - Partenaires : E4 (scores) ; E5 (règle de repli de l'application) ; E3 pour information (fenêtres courtes des nouveaux sites, hors périmètre de cette fiche).

- **Question et hypothèse** :
  - Le sujet le propose (E2, « Approfondissement ») : « Examinez une situation où la méthode fonctionne moins bien : […] historique incomplet. Étudiez une modification ciblée et son coût. »
  - Le protocole le demande (PROTOCOLE §7, fiabilité) : « masquer une fraction annoncée des entrées, puis simuler une panne contiguë, en conservant les mêmes vérités terrain. Comparer erreur, couverture et repli. »
  - Constat de départ :
    - le MLP actuel refuse une fenêtre où moins de 84 h sont mesurées sur 168 (D-18). Ces fenêtres ont été écartées de l'apprentissage (2 047 exemples sur 90 736) ;
    - en validation, 320 cas sur 6 014 partent en repli (`mlp_window_too_sparse`), sur 4 sites en panne l'été (E2-TECH-003) ;
    - sur les sites connus de juin, sans le seuil et avec seulement les 24 dernières heures visibles, le MLP actuel surestime fortement : biais de +42 vélos/h, pire que la simple copie de J−2. Ce contrôle est fait sur des fenêtres raccourcies artificiellement.
  - Question : un MLP **appris en voyant des fenêtres trouées** prévoit-il mieux les cas à historique incomplet, sans perdre en précision sur les semaines complètes ?
  - Hypothèse : gain net quand la fenêtre est très incomplète, perte faible ou nulle sur les semaines complètes. « Le masquage n'aide pas » est une conclusion valable.

- **Références bibliographiques** :
  - Salinas et al., *DeepAR* : masque des valeurs manquantes en entrée.
  - Che et al. (2018), *Recurrent Neural Networks for Multivariate Time Series with Missing Values* (GRU-D) : le masque comme information, à lire avant le gel (à valider).
  - Masquage aléatoire des entrées pendant l'apprentissage, proche du *dropout* d'entrée et de l'apprentissage par masquage : référence à choisir et à lire avant le gel.

- **Instantané, protocole validé, code et paramètres** :
  - Identiques à EXP-E2-03 : `hist-20261117`, `proto-v1` (non validé par le professeur), `fit_cutoff` au 2026-06-30T22:00Z, apprentissage depuis le début des données, latence de 24 h, mesures seules, contexte complet, réglages par défaut du MLP.
  - **Code à écrire, une fonction à la fois, après le gel de cette fiche** :
    1. `min_observed_hours` en paramètre de `build_windows`, `refusal_reasons` et `predict_mlp`, enregistré dans le modèle. Par défaut 84 : rien ne change pour les modèles existants.
    2. `mask_windows(windows, rng, ...)` dans `neural.py` : applique le masquage ci-dessous à des fenêtres déjà construites, puis recalcule le niveau sur les seules heures restantes.
    3. Dans `fit_mlp` (avec Esther) : masquage tiré à chaque époque, uniquement sur les exemples d'apprentissage, jamais sur le holdout d'arrêt anticipé. Réglages ajoutés à `mlp_hyperparameters` : ils entrent dans l'empreinte et dans `metadata.json`.
  - **Masquage à l'apprentissage**, fixé avant tout essai :
    - chaque exemple d'apprentissage est masqué avec une probabilité de **0,25**. Ce n'est pas 0,5, parce que les trous sont rares dans les vraies données (environ 0,8 % des heures) : trop masquer ferait perdre B sur les semaines complètes ;
    - un nouveau masque est tiré à chaque époque, avec un générateur séparé (graine du modèle) : désactivé, l'apprentissage est identique à celui d'aujourd'hui ;
    - un masque efface **un bloc contigu** de la fenêtre, d'une longueur tirée uniformément entre 24 h et 144 h, à une position tirée uniformément. Une panne récente, un début de série et une coupure au milieu sont ainsi couverts ;
    - les heures effacées passent au statut « non mesurée » (masque à 0). Elles ne sont jamais remplacées par 0 ;
    - le niveau de normalisation est recalculé sur les heures restantes, comme en prévision.
  - **Bras comparés** (même architecture, mêmes réglages, mêmes origines d'apprentissage) :

    | Bras | Modèle | Masquage à l'apprentissage | Seuil en prévision |
    | --- | --- | --- | --- |
    | A | MLP actuel (`9ce9`, `s1-9318`, `s2-6278`) | non | 84 h (actuel) |
    | A′ | les mêmes poids que A | non | **24 h** (à valider) |
    | B | MLP masqué, graines 0, 1, 2 (`mask_prob=0.10` après le contrôle sur juin, `min_observed_hours=24`) : `e2-mlp-ctx-20260701-s0-37f5`, `s1-bd12`, `s2-f26e` | **oui** | **24 h** |
    | R | référence `reference_profile` (médiane sur 4 semaines), même entrée | sans objet | sans objet |

    - **A′ contre B isole le masquage** : même seuil, seul l'apprentissage change. C'est la comparaison principale.
    - A contre B mesure l'effet pour l'application : le masquage et le seuil changent ensemble, comme dans la pratique.

- **Scénario, sites, dates et budget d'information autorisé** :
  - `known_site`, 97 compteurs `S_train`, validation de juillet-août 2026 ; le test n'est pas lu.
  - Même information autorisée qu'EXP-E2-03. Les dégradations simulées ne font qu'**effacer** des entrées déjà autorisées : rien de nouveau n'est lu, et les vraies valeurs cibles ne changent pas.

- **Facteur modifié et facteurs conservés** :
  - **Facteur modifié** : le masquage des fenêtres pendant l'apprentissage (A′ contre B).
  - **Facteurs conservés** : architecture, réglages, graines, origines d'apprentissage, coupure, contexte, seuil en prévision (entre A′ et B), cas, masque de score, règle de repli.

- **Cas attendus et règle de comparaison** :
  - **Population 1, naturelle** : les 6 014 cas de validation, découpés par heures mesurées dans la fenêtre visible : 168 à 140, 139 à 84, 83 à 24, moins de 24 (seuils à valider, fixés avant les scores).
  - **Population 2, dégradée artificiellement** (PROTOCOLE §7) : les mêmes 6 014 cas, avec les mêmes cibles et une entrée effacée selon un niveau annoncé :

    | Niveau | Ce qui est effacé de la semaine visible |
    | --- | --- |
    | `d0` | rien (contrôle) |
    | `panne-48` | les 48 dernières heures disponibles (panne récente) |
    | `panne-96` | les 96 dernières heures disponibles |
    | `panne-144` | les 144 dernières heures disponibles (il en reste 24) |
    | `trous-50` | 50 % des heures, tirées au hasard (graine fixée 0) |

    Les mêmes effacements s'appliquent à tous les bras, y compris R : on efface l'historique avant de l'envoyer. Chaque niveau donne des `.pred.csv` à part (`method_run_id` suffixé par le niveau).
  - **Score** : par E4, avec `evaluate_all` de `Metric.py`, comme EXP-E2-03. MAE macro sur l'intersection des cas complets et le même masque, par niveau et par tranche. Résultats « modèle brut » et « système ».
  - **Variabilité** : les écarts entre B et A′ sont lus avec l'étendue entre les 3 graines de chaque bras.
  - **Règle de décision**, figée maintenant (à valider) :
    1. B remplace A comme MLP de l'application **seulement si** les deux conditions suivantes sont vraies :
       - sur `d0` et la tranche 168-140 h (semaines complètes), la MAE de B ne dépasse pas celle de A de plus que l'étendue entre graines de A ;
       - sur `panne-96` et `panne-144`, B fait mieux qu'A′ d'au moins l'étendue entre graines.
    2. Sinon, on garde A et le repli actuel, et on rapporte dans quels cas le masquage aide.
    3. On rapporte aussi B face à R sur chaque niveau : si R reste meilleure quand la fenêtre est très incomplète, le seuil de B doit monter. Ce seuil se choisit sur la validation, jamais sur le test.

- **Contrôles réalisés** :
  - À faire avant les scores :
    - `mask_windows` n'efface que des heures, ne remplace jamais par 0, ne touche pas aux cibles. Test : une fenêtre complète masquée garde ses cibles et voit son niveau recalculé ;
    - le holdout d'arrêt anticipé n'est jamais masqué. Test sur les indices ;
    - le masquage dépend de la graine : même graine, mêmes masques et mêmes poids (sur la même machine, D-23) ;
    - `min_observed_hours = 84` redonne exactement les prévisions actuelles ;
    - dégradations simulées : les fichiers d'entrée ne contiennent aucune heure après `origin − 24 h`, et les cibles sont identiques à `d0`.

- **Résultats mesurés : MAE, cas complets/comparables, échecs et coût** :

  Score calculé le 2026-11-27 par E2 avec les fonctions d'E4 (`score.py`, identique aux scores officiels d'EXP-E2-03). Valeurs : moyenne des 3 graines (étendue entre crochets), en lecture **système**. 5 613 cas comparés à chaque niveau. Notebook : [E2_EXP-05_masquage.ipynb](../../notebooks/E2_EXP-05_masquage.ipynb).

  | Niveau ou tranche | MAE A | MAE A′ | MAE B | MAE R | Couverture brute A / B |
  | --- | --- | --- | --- | --- | --- |
  | `d0` | 22,39 [0,36] | 22,37 [0,36] | 22,73 [0,53] | 27,01 | 94,7 % / 95,4 % |
  | `panne-48` | 27,93 [4,40] | 27,91 [4,43] | **25,17** [0,60] | 27,01 | 94,4 % / 95,3 % |
  | `panne-96` | 29,75 (repli partout) | 36,45 [7,97] | **26,15** [1,11] | 27,01 | 0 % / 95,0 % |
  | `panne-144` | 28,49 (repli partout) | 46,00 [5,06] | **28,20** [1,44] | 30,26 | 0 % / 89,5 % |
  | `trous-50` | 27,36 [0,91] | 27,74 [0,99] | **25,69** [0,29] | 28,64 | 68,1 % / 95,2 % |
  | naturel 168-140 h (5 659 cas) | 22,38 [0,36] | 22,38 [0,36] | 22,77 [0,54] | 26,98 | |
  | naturel 139-84 h (35 cas) | 18,31 [2,19] | 18,31 [2,19] | **17,07** [0,40] | 29,56 | |
  | naturel 83-24 h (46 cas) | 24,14 (repli) | 18,36 [0,34] | **15,68** [0,43] | 24,59 | |
  | naturel < 24 h (274 cas) | 39,01 (repli) | 39,01 (repli) | 39,01 (repli) | 40,39 | |

  En lecture brute, les conclusions sont les mêmes (voir le notebook).

  Coût :
  - apprentissage de B : environ 45 s par graine, comme A ;
  - prévision en bloc : environ 3 min par calcul, soit 50 calculs pour l'expérience ;
  - en prévision, B coûte la même chose que A.

- **Analyse, limites et décision** :

  **Règle appliquée telle quelle** (moyennes des 3 graines, lecture système) :

  | Condition | Mesure | Seuil | Verdict |
  | --- | --- | --- | --- |
  | 1a, `d0` : B − A | +0,340 | ≤ 0,357 (étendue de A) | ✅ |
  | 1a, semaines complètes (168-140 h) : B − A | **+0,387** | ≤ 0,36 (étendue de A) | ❌ de justesse |
  | 1b, `panne-96` : A′ − B | +10,30 | ≥ 7,97 | ✅ |
  | 1b, `panne-144` : A′ − B | +17,80 | ≥ 5,06 | ✅ |

  **Décision : on garde A et son repli** comme MLP de l'application. B ne remplace pas A, parce qu'il perd un peu sur les semaines complètes (+0,39), juste au-delà du bruit entre graines. La règle a été écrite avant les scores et elle est appliquée sans la retoucher.

  **Où le masquage aide** (point 2 de la règle) :
  - **Les semaines trouées, simulées ou réelles.** Sous `panne-48` et `trous-50`, B fait 2 à 2,7 vélos/h de mieux que A et A′. Sur les vraies semaines de 83 à 24 h mesurées, B fait 15,68 contre 24,14 pour le repli de A et 18,36 pour A′.
  - **Prévoir avec peu d'heures, ce qu'A′ ne sait pas faire.** Forcé à prévoir sur une semaine trouée, le MLP sans masquage s'effondre : 46,00 sous `panne-144`, plus mauvais que la médiane. B tient.
  - **La stabilité.** Entre graines, l'étendue de B reste entre 0,3 et 1,4 quand il y a des trous, contre 4 à 8 pour A et A′. Le masquage régularise le réseau.
  - **Face à la référence** : B bat la médiane à tous les niveaux, de −0,9 à −4,3 vélos/h.

  **Le prix du masquage** : un peu de précision sur les semaines complètes (+0,39), qui sont 95 % des cas. C'est le compromis attendu : à 10 % de masquage, le réseau apprend moins finement les semaines parfaites.

  **Recommandation, pour une suite** (non décidée ici) : garder A quand la semaine a au moins 84 h mesurées, et servir B entre 24 et 83 h au lieu du repli. Sur la validation, ce serait au mieux 22,38 sur les semaines complètes et 15,68 sur les semaines trouées. Cette combinaison est une **nouvelle méthode** : il faudrait la figer dans une fiche et la mesurer, pas la déduire de ce tableau.

  **Limites** :
  - les pannes simulées effacent la fin de la semaine visible ou des heures au hasard ; une panne réelle peut avoir une autre forme ;
  - les semaines naturellement trouées sont peu nombreuses (35 et 46 cas), et elles viennent surtout de 4 sites ;
  - été seulement ;
  - protocole non validé ;
  - les 3 graines de B sont apprises sur la même machine, et A en partie sur une autre (D-23) ;
  - les jours décalés de 2 h dans les données d'E1 touchent tous les bras de la même façon.

- **Lien vers données de résultats et figures** : `data/prediction_results/EXP-E2-05/`, un dossier par niveau de dégradation.

- **Retour d'un partenaire et preuve d'utilisation** : prévisions à livrer à E4 pour leur score officiel ; E5 : rien ne change (A et son repli restent servis). La combinaison A / B serait à proposer à E5 et E3 après une fiche dédiée.

## Décisions du gel (2026-11-24)

1. Masquage : probabilité de 0,25 ; un bloc continu de 24 à 144 h, à une position tirée au hasard ; un seul bloc par exemple ; holdout jamais masqué.
2. Seuil en prévision pour A′ et B : 24 h. B apprend aussi avec `min_observed_hours=24` : il garde les exemples naturellement troués (écartés aujourd'hui), ce qui fait partie de « apprendre avec des fenêtres incomplètes ».
3. Niveaux de dégradation et tranches d'heures mesurées : ceux du tableau ci-dessus.
4. Règle de décision : celle ci-dessus, inchangée.
5. **Résultat du contrôle sur juin** (2026-11-24, même mois, mêmes 61 313 cellules et 2 560 exemples pour A et B, validation non lue) :

   | Modèle | Graine 0 | Graine 1 | Graine 2 | Moyenne |
   | --- | --- | --- | --- | --- |
   | A (même machine) | 17,57 | 17,60 | 17,86 | 17,68 |
   | B, `mask_prob=0.25` (`s0-a3b2`, `s1-02bb`, `s2-5238`) | 17,56 | 18,00 | 18,64 | 18,07 |
   | B, `mask_prob=0.10` (`s0-37f5`, `s1-bd12`, `s2-f26e`) | 17,12 | 17,44 | 17,39 | 17,32 |

   - À 0,25, B dépasse A de 0,39, plus que l'étendue entre graines de A (0,29). La règle s'applique : passage à 0,10, réappris.
   - À 0,10, B fait 0,36 de moins que A sur juin, et l'arrêt anticipé arrive plus tard (époques 37, 18, 41 contre 17 à 24). Le masquage léger semble agir comme une régularisation.
   - Juin a servi à l'arrêt anticipé de tous les modèles : ce n'est pas un score, la validation décidera.
   - **B retenu : `mask_prob=0.10`.** Les modèles à 0,25 sont gardés pour la transparence, et ne sont pas évalués.
   - Effet du seuil de 24 h à l'apprentissage : 1 879 exemples écartés au lieu de 2 047 ; 86 085 exemples d'apprentissage au lieu de 85 958. Environ 10 % des exemples d'apprentissage sont masqués à chaque époque.

   Règle écrite au gel, appliquée telle quelle :  Juin est le holdout d'arrêt anticipé, dans la période d'apprentissage : la validation n'est pas lue.
   - Si la MAE de contrôle moyenne de B (semaines complètes, sans masque) dépasse celle de A de plus de l'étendue entre graines de A (même machine : 17,57 / 17,60 / 17,86, soit 0,29), on passe à `mask_prob=0.10`, on réapprend, et on le note ici.
   - C'est la seule adaptation permise après le gel.
6. Code : `min_observed_hours` et `mask_windows` (Idir), branchement dans `fit_mlp` (Esther prévenue). Option désactivée par défaut : les modèles existants ne changent pas.
7. Ordre : les scores d'EXP-E2-05 attendent le gel d'EXP-E2-03.
8. **Mise en œuvre de la dégradation** (2026-11-27, avant tout score d'EXP-E2-05 ; c'est une précision, pas un changement de choix) :
   - La « semaine visible » est la grille des 168 heures qui finit à `origin − 24 h`, la même que la fenêtre du MLP. `panne-N` efface les N dernières heures de cette grille. Une heure déjà manquante reste manquante, si bien que « les N dernières heures disponibles » se lit « les N dernières heures de la semaine visible ».
   - `trous-50` efface 84 heures sur 168, tirées avec la graine 0 et l'identifiant du cas : chaque cas a ses propres trous, identiques pour tous les bras.
   - Code dans [batch.py](../../src/models/known/batch.py) :
     - `erased_positions` donne les positions effacées, `degrade_history` efface un historique, et la fenêtre de chaque cas est effacée en bloc ;
     - le repli du MLP et la référence R voient la même semaine effacée que le modèle ;
     - chaque fonction est testée : aucun 0 inventé, cibles intactes, le bloc donne le même résultat que le cas par cas sur l'historique effacé, `d0` est identique au calcul sans dégradation.
   - Commande, pour un niveau et un modèle :
     ```
     python -m src.models.known.predict --cases data/evaluation/proto-v1/cases.csv --snapshot hist-20261117 --experiment EXP-E2-05/<niveau> --variant mlp --model-run-id <id> --batch --degrade <niveau>
     ```
     A′ ajoute `--min-observed-hours 24 --method-run-id <id>-seuil24`, et R utilise `--variant reference_profile`.
   - Score : `python -m src.models.known.score --experiment EXP-E2-05 --level <niveau>`.
   - Lecture de la règle, fixée avant les scores :
     - on compare les **moyennes des 3 graines** de chaque bras, en lecture **système** (ce que voit l'application). La lecture brute est rapportée à côté ;
     - « l'étendue entre graines » de la condition 1a est celle de A sur le même niveau ou la même tranche ;
     - en 1b, c'est **la plus grande** des étendues de A′ et de B (lecture prudente).

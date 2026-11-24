# EXP-E2-05 - Apprendre avec des fenêtres masquées rend-il le MLP plus robuste aux historiques incomplets ?

> **Statut : brouillon, à figer avant tout code d'apprentissage et tout score.** Les points marqués « à valider » sont des propositions. Les résultats restent vides jusqu'au gel. Même population et même calcul du score que [EXP-E2-03](EXP-E2-03.md).

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
  - **Masquage à l'apprentissage**, fixé avant tout essai (à valider) :
    - chaque exemple d'apprentissage est masqué avec une probabilité de 0,5 ;
    - un masque efface **un bloc contigu** de la fenêtre, d'une longueur tirée uniformément entre 24 h et 144 h, à une position tirée uniformément. Une panne récente, un début de série et une coupure au milieu sont ainsi couverts ;
    - les heures effacées passent au statut « non mesurée » (masque à 0). Elles ne sont jamais remplacées par 0 ;
    - le niveau de normalisation est recalculé sur les heures restantes, comme en prévision.
  - **Bras comparés** (même architecture, mêmes réglages, mêmes origines d'apprentissage) :

    | Bras | Modèle | Masquage à l'apprentissage | Seuil en prévision |
    | --- | --- | --- | --- |
    | A | MLP actuel (`9ce9`, `s1-9318`, `s2-6278`) | non | 84 h (actuel) |
    | A′ | les mêmes poids que A | non | **24 h** (à valider) |
    | B | MLP masqué, graines 0, 1, 2 (à apprendre) | **oui** | **24 h** (à valider) |
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

  _À remplir avec les valeurs d'E4, après le gel._

  | Niveau ou tranche | MAE A | MAE A′ | MAE B (graines 0-2) | MAE R | Cas comparés | Repli A / B |
  | --- | --- | --- | --- | --- | --- | --- |
  | `d0` | | | | | | |
  | `panne-48` | | | | | | |
  | `panne-96` | | | | | | |
  | `panne-144` | | | | | | |
  | `trous-50` | | | | | | |
  | naturel 168-140 h | | | | | | |
  | naturel 139-84 h | | | | | | |
  | naturel 83-24 h | | | | | | |

  Coût : temps d'apprentissage de B contre A ; temps de prévision par cas.

- **Analyse, limites et décision** :

  _À remplir après les scores._

  Limites connues dès maintenant :
  - les pannes simulées effacent toujours la fin de la semaine visible, ou des heures au hasard ; une panne réelle peut avoir une autre forme ;
  - les cas naturels de moins de 84 h viennent surtout de 4 sites ;
  - été seulement ;
  - protocole non validé ;
  - les 3 graines de B sont apprises sur la même machine, A en partie sur une autre (D-23).

- **Lien vers données de résultats et figures** : `data/prediction_results/EXP-E2-05/`, un dossier par niveau de dégradation.

- **Retour d'un partenaire et preuve d'utilisation** : à obtenir (E4 : scores ; E5 : seuil et repli de l'application).

## Points à trancher avant le gel

1. Masquage à l'apprentissage : probabilité de 0,5 ; bloc contigu de 24 à 144 h ; un seul bloc par exemple.
2. Seuil en prévision de A′ et B : 24 h.
3. Niveaux de dégradation et tranches d'heures mesurées.
4. Règle de décision, en particulier « au moins l'étendue entre graines ».
5. Avec Esther : masquage dans `fit_mlp`, tiré à chaque époque.
6. Ordre : figer EXP-E2-03 et EXP-E2-04 d'abord. A est le MLP déclaré dans EXP-E2-03.

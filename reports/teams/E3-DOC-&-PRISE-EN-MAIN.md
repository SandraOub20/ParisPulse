# Équipe 3 — Documentation, rôle et prise en main

**Date de dernière mise à jour : 25 novembre 2026**

**Auteurs :** membres de l’équipe 3

- Lynda Khazem
- Massinissa Machter
- Andrew Zgheib
- Michaela El Rif
- Carl Abou Diwan

---

# DOC 

## 1. Comprendre le rôle de l’équipe 3 dans le projet 

L’équipe 3 étudie l’arrivée d’un nouveau compteur pour lequel seules quelques jours de mesures sont disponibles.

Dans le cadre du contrat entre les équipes 1, 3, 4 et 5, les nouveaux sites disposent d’un historique local limité à soit :

- 24 heures, soit 1 jour ;
- 72 heures, soit 3 jours ;
- 168 heures, soit 7 jours.

L’objectif est de répondre à la question suivante : peut-on prévoir les passages d’un nouveau compteur (new_site) à partir de connaissances acquises sur d’autres lieux/data, avec un modèle public ou avec celui de l’équipe 2 ?

Pour cela, les expériences comparent :

- les modèles (pris sans aucun adaptation) en une seule prévision, appelés variante `frozen` (gelé) ;
- l’adaptation de ces modèles aux premières observations (historique autorisé) locales, appelée variante `adapted` (adapté) ;
- la quantité de données locales nécessaire à cette adaptation.

## 2. Tâche réalisés par E3 

Les détails des expériences sont disponibles dans [reports/experiments/E3-*](/reports/experiments/).

- **Tâche 1 - Définition des données**

  Avec les équipes 1 et 4, nous avons réservé des sites entiers pour constituer de nouveaux sites. Ces sites sont exclus de l’apprentissage initial de l'équipe2, puis associés à des budgets d’historique de 1, 3 ou 7 jours.

- **Tâche 2 - État de l’art**

  Nous avons étudié et fais des recherches sur les modèles publics disponibles pour la prévision de séries temporelles, notament chronos-2 & Google TimesFM.

- **Tâche 3 - Premières prévisions avec les variantes gelées (frozen)**

  Nous avons intégré les méthodes entraînées sur d’autres données que celles des nouveaux sites :
  Chronos-2, Google TimesFM 2.5 et le modèle MLP de l’équipe 2 (`team2`). Nous avons produit trois prévisions en variante `frozen` (gelé) sur `S_dev_new`, à partir des données de **validation** définies dans `data/evaluation/proto-v1/cases.csv`. Le code est dans [src/models/new/predict.py](/src/models/new/predict.py).

- **Tâche 4 - Évaluation des variantes gelées (frozen)**

  Nous avons transmis les résultats de predictions des 3 modèles à l’équipe 4 sous forme de fichiers `.pred.csv`, ainsi que les fichiers `.runs.csv` contenant les informations de calcul.

- **Tâche 5 - Adaptation ou pas d’adaptation ?**

  Après évaluation des prévisions de validation sur `S_dev_new`, nous avons comparé les performances des modèles en variante `frozen` (gelé). Cette étude & analyse, disponible dans [E3-models-frozen-results.md](/reports/experiments/E3-models-frozen-results.md), vise à déterminer si une adaptation est nécessaire.

- **Tâche 6 - Adaptation et approfondissement**

  Les premiers résultats obtenus avec les variantes `frozen` (gelé) étant encourageantes, mais cela nous a pas empéché a faire l'étude de l'adaptation, pour cela nous avons poursuivi l'étude sur davantage de sites.

  Chronos-2 a été testé dans deux versions adaptées : [E3-chronos-adapted-v1.md](/reports/experiments/E3-chronos-adapted-v1.md) et [E3-chronos-adapted-v2.md](/reports/experiments/E3-chronos-adapted-v2.md). Google TimesFM est en cours d'étude avec une première version adaptée.

  Le MLP de l’équipe 2 n’est applicable que lorsque l’historique du site est d'au moins 7 jours. Il ne peut donc pas être considéré comme généralisable aux trois budgets d’historique retenus (1,3,7j) ; nous ne l’avons pas adapté.

- **Tâche 7 - Comparaison des variantes adaptées**

  Nous avons produit une seconde série de prévisions avec les modèles adaptés. Les résultats et analyses de l’équipe 4 montrent que Chronos-2 dans sa variante `adapted` (adapté), en particulier **la version v2**, est actuellement le candidat le plus prometteur.

- **Travaux transverses**
  Nous avons participé aux discussions entre équipes, aux choix collectifs, à la définition des données et à la construction de l’architecture du dépôt.

## 3. Périmètre GitHub de l’équipe

Les principaux éléments produits ou modifiés par l’équipe 3 sont :

- [src/models/new/](/src/models/new/) : implémentation des modèles et des prévisions de l’équipe 3 ;
- [data/prediction_results/EXP-E3/](/data/prediction_results/EXP-E3/) : résultats des prévisions en variantes `frozen` (gelé) et `adapted` (adapté), avec les fichiers `.pred.csv` et `.runs.csv` ;
- [data/evaluation/proto-v1/EXP-E3/](/data/evaluation/proto-v1/EXP-E3/) : évaluations reçues de l’équipe 4, incluant les scores, erreurs et taux de couverture ;
- [artifacts/models/](/artifacts/models/) : poids retenus pour Chronos-2 en variante `adapted` (adapté) v2 ;
- [reports/experiments/](/reports/experiments/) : résultats des prévisions gelées, adaptations, approfondissements et comparaisons ;
- [reports/teams/E3-DOC-&-PRISE-EN-MAIN.md](/reports/teams/E3-DOC-&-PRISE-EN-MAIN.md) : présente le rapport global de l'équipe 3, avec le rôle de l’équipe, les tâches réalisées et les éléments nécessaires à l’intégration dans l'application E5 ;
- [reports/individual/](/reports/individual/) : suivi individuel des membres de l’équipe.

---

# Prise en main rapide pour l’équipe 5 (notre produit & son intégration)

Le sujet proposé dans [ParisPulse — sujet étudiant](/ParisPulse_Sujet_etudiants.pdf) demande a l'équipe 3 de transmettre à l’équipe 5 une méthode/modèle (produit) retenue sur la base des évaluations de validation (S_dev_new) de l’équipe 4.

À ce stade, **Chronos-2 est notre meilleur modèle** sur la validation `S_dev_new`. Il doit être intégré dans l'application avec ses deux variantes :

- `variant="frozen"` : variante `frozen` (gelé) ;
- `variant="adapted"` : variante `adapted` (adapté).

Pour un nouveau site, l’application doit charger son cas, appeler `predict_24h(...)` avec chacune des deux variantes, puis afficher les prévisions ainsi que les scores utiles de chaque variante calculé au moment de la prédiction avec les fonctions d'éval de l'équipe 4.

### Budget d’historique

Dans [data/evaluation/proto-v1/cases.csv](/data/evaluation/proto-v1/cases.csv), chaque couple compteur–site possède trois budgets (pour l'évaluation) :

- `b_24` : 24 heures, soit 1 jour ;
- `b_72` : 72 heures, soit 3 jours ;
- `b_168` : 168 heures, soit 7 jours.

**L’équipe 5 doit retenir un budget fixe pour chaque couple compteur–site (et non pas 3) dans l’application ou dans son fichier de cas. Le choix présenté à l’utilisateur doit correspondre au budget réellement chargé pour le cas.**

### Passage d’un cas à  `src.models.new.predict.predict_24h`

L’exemple suivant utilise Chronos-2 en variante `frozen` (gelé). Seule la valeur de `variant` doit être remplacée par `"adapted"` pour utiliser la variante adaptée.

```python
import pandas as pd

from src.models.known.predict import counts_history_loader
from src.models.new.predict import predict_24h
from src.models.schemas import Case

snapshot_id = "hist-20261117"

# Le fichier cases.csv (de data/evaluation/proto-v1/ ) contient les 3 budgets pour un meme cas .
# Attention : Dans l’application, fixer ici un budget fix (entre 1, 3 ou 7jr) d’historique pour chaque cas.
cases = pd.read_csv(
    "data/evaluation/proto-v1/cases.csv",
    dtype=str,
    keep_default_na=False,
)
selection = cases[cases["scenario"] == "new_site"]

if selection.empty:
    raise ValueError("Aucun cas correspondant au scénario new_site.")

# Exemple : sélection du premier cas disponible 
case = Case.from_row(selection.iloc[0])
history = counts_history_loader(snapshot_id)(case.counter_id)

result = predict_24h(
    case,
    history,
    variant="frozen", # pour avoir la version adapté changer : "frozen" en "adapted"
    model_name="chronos-2",
)

print(f"Cas : {case.case_id}")
print(f"Prévision complète : {result.is_complete()}") # data frame de 24 ligne 
```

La structure retournée respecte le contrat de prédiction : une prévision couvre les 24 heures suivantes et contient les colonnes attendues par l’application.



---

## resources 


- [Documentation Chronos-2 sur Hugging Face](https://huggingface.co/amazon/chronos-2)
- [Google TimesFM — dépôt officiel](https://github.com/google-research/timesfm)

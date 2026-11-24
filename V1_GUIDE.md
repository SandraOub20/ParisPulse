# ParisPulse — V1 rapide (E5)

Cette V1 ajoute **de nouveaux fichiers**. Elle n'écrase pas `streamlit_app.py`,
`counter_map.py` ni le travail existant des autres membres.

## Fichiers livrés

- `src/app/v1_app.py` : carte, sélection compteur/sens, historique, cas, courbe des prévisions et observations, score et export ZIP.
- `src/app/v1_service.py` : lecture du snapshot E1, appel réel de la référence E2, prévisions E3 archivées si présentes, vérification des 24 heures et MAE locale provisoire.
- `tests/test_v1_service.py` : tests unitaires sans données réelles.

## 1. Mettre à jour les fichiers Git

Depuis **la racine du dépôt** sur ton ordinateur :

```bash
git status
git fetch origin
```

Si ton travail local n'est pas commité, **commite-le sur ta branche** avant de changer de branche. Pour créer une branche V1 basée sur le `dev` actuel :

```bash
git switch -c Team5-v1-20261123 origin/dev
```

S'il existe déjà une branche portant ce nom, choisis un autre nom. Décompresse ensuite le ZIP fourni **à la racine de ParisPulse** (et non dans `src/app/`). Il ne doit ajouter que les trois fichiers Python ci-dessus et ce guide.

## 2. Télécharger les vraies données E1 (nécessaire)

Le dépôt livre le snapshot **`hist-20261117`**, pas `flux-20261115`.

```bash
git lfs install
git lfs pull --include="livraison/hist-20261117.zip"
unzip -o livraison/hist-20261117.zip
```

Les fichiers doivent se trouver dans :

```
data/processed/hist-20261117/counters.csv
data/processed/hist-20261117/counts.csv
data/processed/hist-20261117/inventory_quality.csv
```

Si `git lfs` n'existe pas, installe Git LFS sur ta machine. Vérifie l'espace disque avant de décompresser le snapshot.

## 3. Ajouter les cas E4 (fortement recommandé, pas obligatoire pour un compteur connu)

Les cas E4 sont actuellement sur la branche `Team4` et non dans `dev`.

```bash
mkdir -p data/evaluation/proto-v1
git show origin/Team4:data/evaluation/proto-v1/cases.csv > data/evaluation/proto-v1/cases.csv
```

Cela copie **uniquement le CSV**, sans fusionner le code d'évaluation E4 qui nécessite encore des corrections. Le fichier n'est pas nécessaire pour un **cas technique de compteur connu**, car la V1 propose alors une date manuelle. En revanche, pour afficher les prévisions pré-calculées d'E3, le `case_id` doit correspondre à un cas E4.

## 4. Tester et lancer

Sans dépendances de développement :

```bash
uv run --locked --no-dev python -m unittest discover -s tests -p 'test_v1_service.py' -v
uv run --locked --no-dev python -m streamlit run src/app/v1_app.py
```

Ouvre `http://localhost:8501` si le navigateur ne s'ouvre pas.

**Parcours à vérifier :**

1. Choisir `hist-20261117` puis un compteur `retained` ou `robustness` de site connu.
2. Vérifier sa direction et l'historique (vrai zéro / valeur remplacée / manque).
3. Choisir un cas E4 ou la date technique proposée.
4. Choisir `reference`, puis cliquer sur **Calculer et afficher**.
5. Voir 24 heures prédites, la courbe de vraies observations mesurées, MAE provisoire et effectif.
6. Exporter un ZIP comprenant `forecasts.csv`, `errors.csv`, `manifest.json`.
7. Changer de compteur ou de date et recommencer.

## 5. Limites à expliquer au professeur

- **E2 modèle entraîné** : le MLP existe sur `Team2`, mais sa variante n'est pas encore branchée à `src/models/known/predict.py`. Cette V1 exécute la référence hebdomadaire E2 sur un cas réel, pas encore le MLP.
- **E3** : cette V1 peut afficher une prévision **déjà enregistrée** sur un `case_id` présent dans le fichier `.pred.csv` d'E3. Elle ne télécharge pas Chronos-2 et ne calcule pas de nouvelle prévision E3.
- **E4** : `evaluate_local` calcule une **MAE de contrôle V1** sur les heures dont `is_scoreable=true`. Cela ne remplace pas les agrégations, comparaisons et scores officiels validés par E4. Le protocole `proto-v1` est encore proposé, pas nécessairement approuvé.
- **Démonstration** : seuls les résultats effectivement calculés sur des données réelles peuvent être présentés comme tels. Aucun score n'a été calculé ici sur le snapshot E1 complet.
- **Affichage direct** des observations : conforme au retour oral rapporté par E5. Leur présence dans l'affichage ne les transmet pas à E2 : les entrées sont coupées à la date de disponibilité.

## 6. Partage Git (après test)

```bash
git add src/app/v1_app.py src/app/v1_service.py tests/test_v1_service.py V1_GUIDE.md
git commit -m "feat(team5): ajouter une V1 carte-prevision-score-export"
git push -u origin Team5-v1-20261123
```

Vous pourrez ensuite intégrer ces modules au code commun de l'équipe 5. Ne poussez jamais directement dans `main`.

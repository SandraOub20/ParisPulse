# ParisPulse V2

Lancer `./run.sh demo` depuis la racine du dépôt pour préparer les ressources et démarrer.
Pour les lancements suivants, utiliser `./run.sh app`. Sous Windows, après avoir extrait
`livraison/hist-20261117.zip` à la racine, utiliser
`uv run --locked python -m streamlit run src/app/streamlit_app.py`.

1. Choisir **Sites connus**, **Nouveaux sites** ou **Tout le réseau**. Le menu **Compteur et sens**
   permet aussi de sélectionner les compteurs sans coordonnées et de distinguer les sens
   superposés sur la carte.
2. Choisir la date et la méthode. Pour un nouveau site, choisir aussi le budget d’historique
   local. Le passé publié et les dates de la fenêtre cible sont disponibles avant le calcul.
   **Télécharger cases.csv** fournit une ligne avec le compteur, la date, le scénario, le
   protocole et, pour E3, le budget et les bornes d’historique.
   **Calculer la prévision** transmet ce même cas au moteur et affiche son graphique et les
   24 lignes horaires.
   Pour consulter une archive Chronos-2, choisir explicitement l’archive et **Ouvrir la prévision**.
3. Consulter les 24 horizons, les replis et les raisons d’indisponibilité. L’option
   **Comparer les deux références** calcule les deux références E2 pour la même date et affiche
   leur couverture, leurs replis et leur durée de calcul. Les onglets donnent
   accès à l’historique admissible au départ et au contexte E1 connu à cette date.
   L’onglet **Données manquantes** affiche la courbe des comptages, les estimations E1 et les
   heures sans valeur sous la courbe. Pour un site connu, choisir une fenêtre de 7, 30 ou 90 jours
   avant la coupure.
   Pour un cas de nouveau site, le graphique suit la fenêtre d’historique local.
4. Les mesures réelles et l’erreur moyenne absolue du cas s’affichent avec le résultat.
   La comparaison aux mesures cibles intervient une fois les prévisions calculées.
5. **Télécharger l’étude (.zip)** fournit le cas, les prévisions, le manifeste et les coûts
   disponibles. Le ZIP inclut les observations et les erreurs lorsque la comparaison est disponible.

Le routage suit le rôle spatial E1 et le scénario du cas. **E4 → E2** pour un site connu
(`S_train`). **E4 → E3** pour un nouveau site réservé (`S_dev_new` ou `S_test_new`).
Les deux moteurs sont appelés dans l’application sur l’historique publié autorisé.
Sur un site réservé E3, la référence locale et Chronos-2 utilisent la même règle de support.
L’option Chronos-2 en direct apparaît avec `./run.sh setup --group dl` et charge les poids publics
lors du premier calcul. Sans ces dépendances, la référence locale E3 reste calculable.
Les archives Chronos-2 gelé restent accessibles sur leurs cas enregistrés. La comparaison E3
vérifie l’empreinte du support avant d’afficher deux méthodes ensemble. Le fichier
`data/evaluation/<protocole>/cases.csv`, s’il est présent, fournit les dates et bornes exactes du
support. Pour E2, la date exacte sélectionne le cas E4 correspondant lorsqu’il existe. Pour E3,
le budget et la date identifient le cas. Les dates libres génèrent un cas `technique-e5`, à usage
interactif, sans modifier les fichiers d’évaluation E4.

La MAE est un contrôle par cas après calcul. La comparaison E2 affiche les deux scores sur
les mêmes heures mesurées lorsque les deux prévisions couvrent 24 heures. Les agrégations E4
officielles et la variante Chronos-2 adaptée restent à intégrer.

Le fond de carte OpenStreetMap demande un accès Internet. La sélection par menu, les
prévisions et l’export fonctionnent avec les fichiers locaux.

Le lancement historique reste accessible avec
`uv run --locked python -m streamlit run src/app/v1_app.py`.

# Nouveaux sites — équipe 3

Depuis la racine du dépôt, installer les dépendances verrouillées avec
`./run.sh setup --group dl`. Sous Windows, utiliser `py -m uv sync --locked --group dl`.
Chronos-2 et TimesFM 2.5 téléchargent leurs poids publics au premier chargement. Le MLP
utilise les poids livrés par E2 et le contexte E1 disponible à l’origine.

## Prévoir sur un site réservé

`predict_24h(case, history, variant="frozen", model_name="chronos-2", context=None)`
renvoie 24 horizons pour un cas `new_site` réservé à E3 (`S_dev_new` ou `S_test_new`).
Les noms des modèles sont `chronos-2`, `google_TimesFM_2.5` et `team2` (MLP E2 transféré).

L’entrée est filtrée sur le compteur, la coupure de publication et les bornes du support.
Les modèles utilisent les comptages publiés. Le MLP a été entraîné avec une fenêtre de
168 heures et exige au moins 84 mesures dans cette fenêtre. Quand il refuse un cas,
la référence hebdomadaire utilise le même support et le motif du repli est tracé.

## Comparaison gelé et adapté

La variante `adapted` garde les poids du modèle gelé et ajuste un biais additif. Elle
rejoue au plus deux origines à minuit (heure de Paris) dans le support local. À chaque
rejeu, les mesures d’entrée et le contexte respectent la disponibilité simulée de cette
origine. Les 24 heures cibles du rejeu se terminent au plus tard à la fin du support.
La correction est la médiane des écarts « mesure − prévision », réduite par le facteur
`n / (n + 24)`, où `n` est le nombre d’heures appariées. Les prévisions ajustées sont
ramenées à zéro si elles deviennent négatives.

Avec moins de 12 heures appariées, un support trop court ou un refus du modèle gelé, le
résultat indique le repli et conserve les valeurs du modèle gelé ou son propre repli.
La correction est estimée de nouveau pour chaque cas. Les poids et les mesures cibles
des 24 heures à prévoir restent hors de l’ajustement. Cette règle technique et ses
seuils doivent être validés par E4 avant la mesure finale.

## Produire les fichiers pour E4

```sh
uv run --locked --group dl python -m src.models.new.batch \
  --cases data/evaluation/proto-v1/cases.csv --snapshot hist-20261117 \
  --experiment E3-comparaison --model team2 --variant both --budget 168
```

La commande utilise le bloc de validation par défaut et écrit `.pred.csv`, `.runs.csv` et
les détails d’adaptation en JSON dans `data/prediction_results/E3-comparaison/`.
Le bloc test requiert `--split test --allow-test` après le gel du protocole et des modèles.
La comparaison des scores agrégés relève d’E4.

Les scripts d’origine reproduisent les archives gelées dans `data/prediction_results/EXP-E3/`.
Chronos-2 et TimesFM couvrent les trois budgets. Le MLP transféré couvre le budget de 168 h.
[Chronos-2](validation.example.chronos.py) · [TimesFM](validation.example.google.py) · [MLP](validation.example.modelTeam2.py)

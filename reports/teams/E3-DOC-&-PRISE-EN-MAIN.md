# Équipe 3 — Prise en main

**Date de dernière mise à jour : 24 novembre 2026**

## Tâches faites

- Prévisions en variante `frozen` réalisées avec 2 modèles publiques : Chronos-2 et Google TimesFM 2.5 et le modèle MLP de l'équipe 2 (`team2`).

## Passer un cas à `predict_24h` : exemple avec Chronos-2

Depuis la racine du dépôt, l'exemple ci-dessous sélectionne le premier cas de
validation `new_site` réservé à E3 (`S_dev_new`), charge son historique mesuré,
puis passe le cas et l'historique à `predict_24h`.

```bash
import pandas as pd

from src.models.known.predict import counts_history_loader
from src.models.new.predict import predict_24h
from src.models.schemas import Case

snapshot_id = "hist-20261117"
cases = pd.read_csv("data/evaluation/proto-v1/cases.csv", dtype=str, keep_default_na=False)
selection = cases[
    (cases["scenario"] == "new_site")
    & (cases["spatial_role"] == "S_dev_new")
    & (cases["temporal_split"] == "validation")
]
if selection.empty:
    raise ValueError("Aucun cas de validation S_dev_new.")

case = Case.from_row(selection.iloc[0])
history = counts_history_loader(snapshot_id)(case.counter_id)
result = predict_24h(
    case,
    history,
    variant="frozen",
    model_name="chronos-2",
)

print(f"Cas : {case.case_id}")
print(f"Prévision complète : {result.is_complete()}") # 24 ligne = 24h de pred 
PY
```

Le script [validation.example.oneCase.Chronos.py](../../src/models/new/validation.example.oneCase.Chronos.py)
montre également comment enregistrer les prévisions et le journal d'exécution
pour ce cas.

## Tâches en attente — partenaire E4

- Évaluer les prédictions réalisées sur la période de validation de `S_dev_new` et nous transmettre l'analyse des résultats.

## Tâches prochaines

- À partir de l'évaluation d'E4, adapter le modèle le plus pertinent si les résultats le justifient.

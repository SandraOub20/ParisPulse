"""GABARIT À COMPLÉTER - E4

Calculer des scores comparables sans masquer les refus.

Entrées et sorties : voir doc/CONTRATS.md et doc/templates/.

À faire :
1. Vérifier alignement, doublons et présence des 24 prévisions par cas.
2. Comparer sur les mêmes cas complets et les mêmes heures réellement mesurées.
3. Calculer MAE par compteur puis moyenne non pondérée ; rapporter les dénominateurs.
4. Séparer sites connus/nouveaux et modèle brut/système après repli ; conserver les échecs.

Aucune implémentation fournie ; ce fichier contient uniquement des consignes.
"""


#MAE
#MAPE
#RSME
#R²
#MAE, MAPE, RSME, R² global


import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


def calculate_metrics(y_true, y_pred):
    """
    Calcule MAE, MAPE, RMSE et R².

    y_true : valeurs réellement observées
    y_pred : valeurs prédites
    """

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    #Vérification taille des y_pred et y_true
    if len(y_true) != len(y_pred):
        raise ValueError("y_true et y_pred doivent avoir la même taille.")

    #Seules les paires valides retenue
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[valid]
    y_pred = y_pred[valid]

    n = len(y_true)

    if n == 0:
        return {
            "n_predictions": 0,
            "n_mape_predictions": 0,
            "MAE": np.nan,
            "MAPE": np.nan,
            "RMSE": np.nan,
            "R2": np.nan
        }

    #MAE
    mae = mean_absolute_error(y_true, y_pred)

    #MAPE (exclure les valeurs réelles égales à zéro)
    nonzero = y_true != 0

    if nonzero.any():
        mape = np.mean(
            np.abs(
                (y_true[nonzero] - y_pred[nonzero])
                / y_true[nonzero]
            )
        ) * 100
    else:
        mape = np.nan

    #RMSE
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    #R²
    if n >= 2 and np.var(y_true) > 0:
        r2 = r2_score(y_true, y_pred)
    else:
        r2 = np.nan

    return {
        "n_predictions": n,
        "n_mape_predictions": int(nonzero.sum()),
        "MAE": mae,
        "MAPE": mape,
        "RMSE": rmse,
        "R2": r2
    }


def calculate_by_counter(df):
    """
    Calcule les métriques pour chaque compteur et chaque modèle.
    """

    results = []

    for (model, counter_id), group in df.groupby(
        ["model", "counter_id"]
    ):

        metrics = calculate_metrics(
            group["y_true"],
            group["y_pred"]
        )

        results.append({
            "model": model,
            "counter_id": counter_id,
            **metrics
        })

    return pd.DataFrame(results)


def calculate_global_metrics(results_df):
    """
    Calcule la moyenne des métriques entre les compteurs,
    séparément pour chaque modèle.
    """

    metric_columns = ["MAE", "MAPE", "RMSE", "R2"]

    global_results = (
        results_df
        .groupby("model")[metric_columns]
        .mean()
        .reset_index()
    )

    #Nombre de compteurs ayant contribué à chaque métrique
    for metric in metric_columns:
        counts = (
            results_df.groupby("model")[metric]
            .count()
            .rename(f"n_counters_{metric}")
        )

        global_results = global_results.merge(
            counts,
            on="model"
        )

    return global_results

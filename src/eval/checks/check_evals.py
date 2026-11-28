import re
import sys

import numpy as np
import pandas as pd

from src.common.config import ROOT, load_config

# CONFIGURATION
cfg = load_config()

PROTOCOLE_ID = cfg["protocol"]["id"]
EXP_ID = ["EXP-E2", "EXP-E3"]
EVAL = ROOT / cfg["paths"]["evaluation"] / PROTOCOLE_ID
OUTPUT_SCRIPT = ROOT / "src" / "eval" / "backtest.py"

EXPECTED_COLUMNS = {
    "coverage.csv": [
        "case_id",
        "counter_id",
        "origin",
        "scenario",
        "method_run_id",
        "variant",
        "local_budget_hours",
        "coverage_status",
        "n_predicted_hours",
        "is_complete_24h",
        "status_reason",
        "protocol_id",
        "snapshot_id",
    ],
    "errors.csv": [
        "case_id",
        "counter_id",
        "horizon",
        "target_timestamp",
        "method_run_id",
        "variant",
        "y_true",
        "y_pred",
        "is_scoreable",
        "signed_error",
        "absolute_error",
        "squared_error",
        "MAE",
        "MAPE",
        "R2",
        "RMSE",
        "protocol_id",
        "snapshot_id",
    ],
    "scores.csv": [
        "experiment_id",
        "scenario",
        "temporal_split",
        "method_run_id",
        "variant",
        "local_budget_hours",
        "comparison_population_id",
        "n_expected_cases",
        "n_complete_cases",
        "n_compared_cases",
        "n_compared_hours",
        "n_evaluable_counters",
        "mae_macro",
        "rmse",
        "r2",
        "bias",
        "coverage_24h",
        "n_fallback_cases",
        "protocol_id",
        "snapshot_id",
    ],
    "scores_by_counter.csv": [
        "counter_id",
        "method_run_id",
        "variant",
        "MAE",
        "MAPE",
        "R2",
        "RMSE",
        "bias",
        "n_predictions",
        "n_mape_predictions",
        "experiment_id",
        "scenario",
        "temporal_split",
        "local_budget_hours",
        "comparison_population_id",
        "protocol_id",
        "snapshot_id",
    ],
}

issues = {
    "ERROR": [],
    "WARNING": [],
    "OK": [],
}


def report(level, message):
    """Ajoute et affiche un résultat d'audit."""
    issues[level].append(message)

    prefix = {
        "ERROR": "[ERROR]",
        "WARNING": "[WARNING]",
        "OK": "[OK]",
    }[level]

    print(f"{prefix} {message}")


def _parse_bool(series):
    """Convertit proprement une colonne booléenne lue depuis CSV."""
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "1": True,
                "yes": True,
                "false": False,
                "0": False,
                "no": False,
            }
        )
    )


# Vérification des fichiers CSV
def check_file_exists(path):
    """Vérifie la présence d'un fichier."""
    if not path.is_file():
        report("ERROR", f"Fichier absent : {path}")
        return False

    report("OK", f"Fichier présent : {path}")
    return True


def check_csv_structure(path, expected_columns):
    """Vérifie les colonnes et charge le CSV."""
    filename = path.name

    if not check_file_exists(path):
        return None

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        report("ERROR", f"Lecture impossible de {filename} : {exc}")
        return None

    # Détection d'un index exporté par erreur
    unnamed = [
        col for col in df.columns if str(col).startswith("Unnamed:") or str(col).strip() == ""
    ]

    if unnamed:
        report("WARNING", f"{filename} contient une colonne d'index parasite : {unnamed}")

    missing = [col for col in expected_columns if col not in df.columns]
    unexpected = [col for col in df.columns if col not in expected_columns and col not in unnamed]

    if missing:
        report("ERROR", f"{filename} : colonnes manquantes : {missing}")
    else:
        report("OK", f"{filename} : toutes les colonnes attendues sont présentes")

    if unexpected:
        report("WARNING", f"{filename} : colonnes supplémentaires : {unexpected}")

    if len(df) == 0:
        report("WARNING", f"{filename} est vide")
    else:
        report("OK", f"{filename} contient {len(df)} lignes")

    return df


# Vérification de coverage.csv
def check_coverage(df, label="coverage.csv"):
    """Contrôle les informations de couverture."""
    if df is None:
        return

    required = [
        "case_id",
        "method_run_id",
        "variant",
        "n_predicted_hours",
        "is_complete_24h",
        "coverage_status",
    ]

    if not all(col in df.columns for col in required):
        return

    key = ["case_id", "method_run_id", "variant"]
    if df.duplicated(key).any():
        report("ERROR", f"{label} contient des doublons sur {key}")
    else:
        report("OK", f"{label} : clé {key} sans doublons")

    hours = pd.to_numeric(df["n_predicted_hours"], errors="coerce")

    if hours.isna().any():
        report("ERROR", f"{label} : n_predicted_hours contient des valeurs non numériques")
    elif ((hours < 0) | (hours > 24)).any():
        report("ERROR", f"{label} : n_predicted_hours doit être compris entre 0 et 24")
    else:
        report("OK", f"{label} : nombre d'heures prédites dans l'intervalle [0, 24]")

    # Vérification de cohérence entre nombre d'heures et complétude
    complete = _parse_bool(df["is_complete_24h"])

    if complete.isna().any():
        report("WARNING", f"{label} : valeurs de is_complete_24h non reconnues")
    else:
        mismatch = complete != (hours == 24)

        if mismatch.any():
            report(
                "WARNING",
                f"{label} : {mismatch.sum()} incohérence(s) entre "
                "is_complete_24h et n_predicted_hours",
            )
        else:
            report("OK", f"{label} : cohérence entre heures prédites et complétude")

    if df["coverage_status"].isna().any():
        report("WARNING", f"{label} : coverage_status contient des valeurs manquantes")


# Vérification de errors.csv
def check_error(df, label="errors.csv"):
    """Contrôle les erreurs horaires."""
    if df is None:
        return

    required = [
        "case_id",
        "counter_id",
        "horizon",
        "method_run_id",
        "variant",
        "y_true",
        "y_pred",
        "is_scoreable",
        "signed_error",
        "absolute_error",
        "squared_error",
    ]

    if not all(col in df.columns for col in required):
        return

    key = ["case_id", "counter_id", "horizon", "method_run_id", "variant"]

    if df.duplicated(key).any():
        report("ERROR", f"{label} contient des doublons sur {key}")
    else:
        report("OK", f"{label} : pas de doublons sur {key}")

    horizon = pd.to_numeric(df["horizon"], errors="coerce")

    if horizon.isna().any():
        report("ERROR", f"{label} : horizon contient des valeurs manquantes ou non numériques")
    elif ((horizon < 1) | (horizon > 24)).any():
        report("ERROR", f"{label} : des horizons sont en dehors de [1, 24]")
    else:
        report("OK", f"{label} : horizons dans l'intervalle [1, 24]")

    y_true = pd.to_numeric(df["y_true"], errors="coerce")
    y_pred = pd.to_numeric(df["y_pred"], errors="coerce")
    signed_err = pd.to_numeric(df["signed_error"], errors="coerce")
    abs_err = pd.to_numeric(df["absolute_error"], errors="coerce")
    sq_err = pd.to_numeric(df["squared_error"], errors="coerce")

    # Vérifie l'absence de valeurs négatives (comptages cyclables >= 0)
    if (y_true.dropna() < 0).any():
        report("ERROR", f"{label} : y_true contient des valeurs négatives")
    if (y_pred.dropna() < 0).any():
        report("WARNING", f"{label} : y_pred contient des prévisions négatives")

    # Vérifie signed_error, absolute_error et squared_error sur les paires valides
    scoreable = _parse_bool(df["is_scoreable"])
    valid = y_true.notna() & y_pred.notna() & scoreable.fillna(False)

    if not valid.any():
        report("WARNING", f"{label} : aucune ligne ne permet de vérifier les erreurs")
    else:
        expected_signed = y_pred[valid] - y_true[valid]
        expected_abs = expected_signed.abs()
        expected_sq = expected_signed ** 2

        if signed_err[valid].isna().any() or not np.allclose(
            signed_err[valid], expected_signed, rtol=1e-5, atol=1e-8
        ):
            report("ERROR", f"{label} : signed_error incohérente avec (y_pred - y_true)")
        else:
            report("OK", f"{label} : signed_error cohérente")

        if abs_err[valid].isna().any() or not np.allclose(
            abs_err[valid], expected_abs, rtol=1e-5, atol=1e-8
        ):
            report("ERROR", f"{label} : absolute_error incohérente avec |y_pred - y_true|")
        else:
            report("OK", f"{label} : absolute_error cohérente")

        if sq_err[valid].isna().any() or not np.allclose(
            sq_err[valid], expected_sq, rtol=1e-5, atol=1e-8
        ):
            report("ERROR", f"{label} : squared_error incohérente avec (y_pred - y_true)^2")
        else:
            report("OK", f"{label} : squared_error cohérente")

    for col in ["MAE", "RMSE"]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce")
            if values.isna().all():
                report("WARNING", f"{label} : {col} est entièrement vide")

    # is_scoreable porte sur la vérité terrain (y_true), pas sur y_pred
    scoreable = _parse_bool(df["is_scoreable"])

    if scoreable.isna().any():
        report("WARNING", f"{label} : valeurs is_scoreable non reconnues")
    else:
        anomaly = scoreable & y_true.isna()

        if anomaly.any():
            report(
                "ERROR",
                f"{label} : {anomaly.sum()} ligne(s) marquées is_scoreable=True "
                "mais avec y_true manquant",
            )
        else:
            report("OK", f"{label} : cohérence entre is_scoreable et y_true")


# Vérification de scores.csv
def check_scores(df, label="scores.csv"):
    """Contrôle les scores globaux."""
    if df is None:
        return

    key = [
        "scenario",
        "temporal_split",
        "method_run_id",
        "variant",
        "local_budget_hours",
        "comparison_population_id",
    ]
    if all(col in df.columns for col in key):
        if df.duplicated(key).any():
            report("ERROR", f"{label} contient des doublons sur {key}")
        else:
            report("OK", f"{label} : pas de doublons sur {key}")

    if "comparison_population_id" in df.columns:
        if df["comparison_population_id"].isna().any():
            report("ERROR", f"{label} : comparison_population_id contient des valeurs manquantes")
        else:
            report("OK", f"{label} : comparison_population_id renseigné sur toutes les lignes")

    # Alerte si le bloc test est déjà évalué avant le gel officiel
    if "temporal_split" in df.columns:
        if df["temporal_split"].astype(str).str.lower().eq("test").any():
            report(
                "WARNING",
                f"{label} : contient le split 'test' — vérifier que les modèles sont figés.",
            )

    count_columns = [
        "n_expected_cases",
        "n_complete_cases",
        "n_compared_cases",
        "n_compared_hours",
        "n_evaluable_counters",
        "n_fallback_cases",
    ]

    for col in count_columns:
        if col not in df.columns:
            continue

        values = pd.to_numeric(df[col], errors="coerce")

        # n_fallback_cases est NaN sur les lignes _common_complete
        if col != "n_fallback_cases" and values.isna().any():
            report("WARNING", f"{label} : {col} contient des valeurs non numériques")
        elif (values.dropna() < 0).any():
            report("ERROR", f"{label} : {col} contient des valeurs négatives")

    if all(
        col in df.columns
        for col in ["n_expected_cases", "n_complete_cases", "n_compared_cases", "coverage_24h"]
    ):
        expected = pd.to_numeric(df["n_expected_cases"], errors="coerce")
        complete = pd.to_numeric(df["n_complete_cases"], errors="coerce")
        compared = pd.to_numeric(df["n_compared_cases"], errors="coerce")
        cov_24 = pd.to_numeric(df["coverage_24h"], errors="coerce")

        if ((complete > expected) | (compared > expected)).any():
            report(
                "ERROR",
                f"{label} : nombre de cas complets ou comparés supérieur "
                "au nombre de cas attendus",
            )

        valid_cov = expected > 0
        if valid_cov.any():
            expected_cov = complete[valid_cov] / expected[valid_cov]
            if not np.allclose(cov_24[valid_cov], expected_cov, rtol=1e-5, atol=1e-8):
                report(
                    "ERROR",
                    f"{label} : coverage_24h incohérent avec n_complete_cases / n_expected_cases",
                )
            else:
                report("OK", f"{label} : coverage_24h cohérent")

    for col in ["mae_macro", "rmse"]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if (values < 0).any():
                report("ERROR", f"{label} : {col} contient des valeurs négatives")

    for col in ["mae_macro", "rmse", "r2", "bias", "coverage_24h"]:
        if col not in df.columns:
            continue

        values = pd.to_numeric(df[col], errors="coerce")

        if values.isna().all():
            report("WARNING", f"{label} : {col} est entièrement vide")


# Vérification de scores_by_counter.csv
def check_scores_by_counter(df, label="scores_by_counter.csv"):
    """Contrôle les scores et le biais par compteur."""
    if df is None:
        return

    for col in ["MAE", "RMSE"]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if (values < 0).any():
                report("ERROR", f"{label} : {col} contient des valeurs négatives")

    if "bias" in df.columns:
        bias_vals = pd.to_numeric(df["bias"], errors="coerce")
        if bias_vals.isna().all():
            report("WARNING", f"{label} : bias est entièrement vide")
        else:
            report(
                "OK",
                f"{label} : bias par compteur présent ({bias_vals.notna().sum()} lignes valides)",
            )


# Vérification statique de backtest.py
def check_eval_outputs():
    """Recherche des constructions potentiellement problématiques."""
    if not check_file_exists(OUTPUT_SCRIPT):
        return

    source = OUTPUT_SCRIPT.read_text(encoding="utf-8")
    script_name = OUTPUT_SCRIPT.name

    # Vérification de l'import du module consolidé src.eval.metrics
    if "src.eval.metrics" in source:
        report("OK", f"{script_name} : utilise bien src.eval.metrics")
    else:
        report("WARNING", f"{script_name} : import de src.eval.metrics non détecté")

    # Export de error.csv commenté
    if re.search(r"^\s*#\s*error\.to_csv", source, flags=re.MULTILINE):
        report("ERROR", f"{script_name} : export de errors.csv commenté")

    # Recherche des to_csv sans index=False
    for match in re.finditer(r"\.to_csv\s*\((.*?)\)", source, flags=re.DOTALL):
        call = match.group(0)
        line_number = source[: match.start()].count("\n") + 1

        if not re.search(r"\bindex\s*=\s*False\b", call):
            report("WARNING", f"{script_name} ligne {line_number} : to_csv() sans index=False")

    # Répétition artificielle des observations
    if ".repeat(" in source:
        report(
            "ERROR",
            f"{script_name} : utilisation de repeat() pour les observations. "
            "Risque d'associer incorrectement les y_true aux y_pred.",
        )

    # Vérification des fonctions principales de la nouvelle architecture
    expected_functions = [
        "_check_forecast_file",
        "_prepare_observations",
        "_get_case_groups",
        "get_time_interval",
        "make_error",
        "make_scores",
        "make_common_scores",
        "make_coverage",
    ]

    for function in expected_functions:
        if re.search(rf"^\s*def\s+{function}\s*\(", source, re.MULTILINE):
            report("OK", f"{script_name} : fonction {function} présente")
        else:
            report("ERROR", f"{script_name} : fonction {function} absente")

    # Vérification des métriques attendues
    for metric in ["MAE", "MAPE", "RMSE", "R2", "bias"]:
        if metric in source:
            report("OK", f"{script_name} : référence à {metric} trouvée")
        else:
            report("WARNING", f"{script_name} : référence à {metric} absente")


# Exécution de l'audit
def main():
    print("=" * 65)
    print(f"AUDIT EVALUATIONS ({PROTOCOLE_ID})")
    print("=" * 65)
    print(f"Racine projet    : {ROOT}")
    print(f"Dossier évalué   : {EVAL}")
    print(f"Script contrôlé  : {OUTPUT_SCRIPT}")
    print()

    for exp in EXP_ID:
        exp_dir = EVAL / exp
        print(f"\n{'=' * 65}")
        print(f"EXPÉRIENCE : {exp}")
        print("=" * 65)

        if not exp_dir.is_dir() or not any(exp_dir.glob("*.csv")):
            report("WARNING", f"Aucune sortie CSV trouvée pour {exp} dans {exp_dir} (en attente de prévisions)")
            continue

        cov_path = exp_dir / "coverage.csv"
        err_path = exp_dir / "errors.csv"
        scr_path = exp_dir / "scores.csv"
        cnt_path = exp_dir / "scores_by_counter.csv"

        coverage = check_csv_structure(cov_path, EXPECTED_COLUMNS["coverage.csv"])
        error = check_csv_structure(err_path, EXPECTED_COLUMNS["errors.csv"])
        scores = check_csv_structure(scr_path, EXPECTED_COLUMNS["scores.csv"])
        counters = check_csv_structure(cnt_path, EXPECTED_COLUMNS["scores_by_counter.csv"])

        print(f"\n--- Contrôle {exp}/{cov_path.name} ---")
        check_coverage(coverage, f"{exp}/{cov_path.name}")

        print(f"\n--- Contrôle {exp}/{err_path.name} ---")
        check_error(error, f"{exp}/{err_path.name}")

        print(f"\n--- Contrôle {exp}/{scr_path.name} ---")
        check_scores(scores, f"{exp}/{scr_path.name}")

        print(f"\n--- Contrôle {exp}/{cnt_path.name} ---")
        check_scores_by_counter(counters, f"{exp}/{cnt_path.name}")

    print(f"\n--- Contrôle {OUTPUT_SCRIPT.name} ---")
    check_eval_outputs()

    print("\n" + "=" * 65)
    print("BILAN")
    print("=" * 65)

    for level in ["ERROR", "WARNING", "OK"]:
        print(f"{level}: {len(issues[level])}")

    if issues["ERROR"]:
        print("\nDes erreurs ont été détectées. Vérification nécessaire.")
        return 1

    if issues["WARNING"]:
        print("\nAucune erreur bloquante détectée, mais des points restent à vérifier.")
        return 0

    print("\nTous les contrôles effectués sont OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
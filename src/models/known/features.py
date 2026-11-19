"""Variables causales identiques à l'apprentissage et à l'inférence - E2 avec E1.

À faire :
1. Utiliser heure/jour cible et contexte autorisé, historique admissible et masques de manque.
   Fériés et vacances appartiennent au contexte (context_features), pas au calendrier de
   base, pour que l'ablation avec/sans calendrier n'agisse que sur la source complémentaire.
2. Vérifier available_at <= origin pour chaque observation utilisée.
3. Calculer profils, imputations et statistiques sans futur ; versionner les transformations.
4. Partager les variables avec E3 si elles respectent son budget local.
"""

from __future__ import annotations

import pandas as pd

from src.models.schemas import ForecastInputs

FEATURE_VERSION = "f0.1"
LOCAL_TZ = "Europe/Paris"


def calendar_features(targets: pd.Series) -> pd.DataFrame:
    """Variables temporelles de base, dérivées du seul timestamp, toujours présentes.

    Heure locale, jour de semaine, week-end, calculés en Europe/Paris pour la cible.
    Aucune source externe ici : fériés et vacances relèvent de context_features, afin
    que l'ablation avec/sans calendrier officiel ne touche que la source complémentaire.
    """
    raise NotImplementedError("E2 : heure et jour en Europe/Paris")


def history_features(inputs: ForecastInputs, targets: pd.Series) -> pd.DataFrame:
    """Variables issues du passé admissible (available_at <= information_cutoff).

    Ex. : lags 168/336 h, profils hebdomadaires, niveau récent, part de manques,
    indicateur de zéro prolongé calculé causalement.
    """
    raise NotImplementedError("E2 : lags et profils sans futur")


def context_features(inputs: ForecastInputs, targets: pd.Series) -> pd.DataFrame:
    """Source complémentaire autorisée (context.csv d'E1), seule partie retirée par l'ablation.

    - calendrier officiel (rôle known_calendar) : jour férié, vacances scolaires, joints sur
      la date locale de la cible ; contrôler unicité et nombre de lignes ;
    - météo : bulletin émis et disponible avant l'origine uniquement (forecast_bulletin).
    Les observations météo ultérieures (posthoc_only) sont réservées à l'analyse après coup.
    """
    raise NotImplementedError("E2 avec E1 : jointure du contexte autorisé")


def build_feature_frame(inputs: ForecastInputs, use_context: bool = True) -> pd.DataFrame:
    """Assembler les 24 lignes de variables d'un cas (sans label).

    calendar_features et history_features sont toujours présentes ; use_context=False
    retire uniquement context_features (fériés, vacances, météo) pour l'ablation.

    Colonnes de traçabilité : feature_version, case_id, target_timestamp, horizon,
    max_input_available_at (<= origin).
    """
    raise NotImplementedError("E2 : assemblage et contrôle de causalité")


def build_training_frame(
    counts: pd.DataFrame,
    origins: pd.DataFrame,
    context: pd.DataFrame | None,
    fit_cutoff: pd.Timestamp,
    use_context: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Construire X, y sur des origines d'apprentissage ; labels joints séparément.

    Chaque fenêtre n'utilise que des entrées disponibles à son origine et des labels
    disponibles à fit_cutoff. Les cibles manquantes (NaN / cellule vide) ou non évaluables
    sont exclues de y ; les zéros observés sont conservés comme cibles valides.
    """
    raise NotImplementedError("E2 : fenêtres d'apprentissage causales")

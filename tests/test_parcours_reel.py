"""Parcours complet E5 sur les vraies données E1 (instantané hist-20261117).

Les tests sont ignorés si l'instantané n'est pas installé (voir V1_GUIDE.md, §2).
Les cas ont été choisis d'après les métadonnées et un balayage de fiabilité des
origines d'octobre–novembre 2026 ; ils servent à vérifier le code, pas à annoncer
une performance : le score indiqué est celui d'un seul cas.

| Cas | Compteur | Date | Ce qu'il vérifie |
| --- | --- | --- | --- |
| Normal | 100044494-353504987 | 13/10/2026 | 24 mesures lues, 24 heures ok, 24 comparées |
| Repli partiel | idem | 31/10/2026 | 1 mesure lue manque → exactement 1 heure en repli |
| Semaine vide | idem | 11/10/2026 | 0 mesure directe, repli sur les 24 heures, pas de blocage |
| Cibles absentes | idem | 25/10/2026 | 24 prévisions, 0 mesure cible : score nul, pas zéro |
| Sans historique | 100036718-104036718 | 13/10/2026 | aucune mesure sur 4 semaines : calcul bloqué |
| Nouveau site | 300030163-353355237 | 13/10/2026 | support local de 168 h, référence locale complète |
"""

import io
import json
from zipfile import ZipFile

import pandas as pd
import pytest

from src.app import reliability, service, v1_service
from src.app.export import study_zip
from src.common.config import ROOT

SNAPSHOT_ID = "hist-20261117"
SNAPSHOT = ROOT / "data" / "processed" / SNAPSHOT_ID
LAG = 24
NORMAL = "100044494-353504987"
EMPTY = "100036718-104036718"
NEW_SITE = "300030163-353355237"

pytestmark = pytest.mark.skipif(
    not (SNAPSHOT / "counts.csv").is_file(),
    reason=f"Instantané E1 {SNAPSHOT_ID} absent : décompresser livraison/{SNAPSHOT_ID}.zip",
)


@pytest.fixture(scope="module")
def inventory():
    return v1_service.load_inventory(SNAPSHOT).set_index("counter_id", drop=False)


@pytest.fixture(scope="module")
def histories():
    """Lire une seule fois counts.csv pour les trois compteurs, depuis septembre 2026."""
    wanted = {NORMAL, EMPTY, NEW_SITE}
    parts = []
    for chunk in pd.read_csv(
        SNAPSHOT / "counts.csv",
        usecols=v1_service.COUNT_INPUT_COLUMNS,
        dtype={"counter_id": "string"},
        chunksize=500_000,
    ):
        chunk = chunk.loc[chunk["counter_id"].isin(wanted) & chunk["timestamp"].ge("2026-09")]
        if not chunk.empty:
            parts.append(chunk)
    rows = pd.concat(parts, ignore_index=True)
    for name in ("timestamp", "interval_end"):
        rows[name] = pd.to_datetime(rows[name], utc=True, format="ISO8601")
    for name in ("count_raw", "count"):
        rows[name] = pd.to_numeric(rows[name], errors="coerce")
    for name in ("is_observed", "is_scoreable"):
        rows[name] = v1_service.bool_series(rows[name])
    return {cid: rows.loc[rows["counter_id"].eq(cid)].reset_index(drop=True) for cid in wanted}


def known(inventory, counter_id, day):
    return service.technical_case(inventory.loc[counter_id], pd.Timestamp(day).date(), SNAPSHOT_ID)


def journey(case, history, method="reference"):
    check = reliability.check_history(case, history, LAG, method)
    (study,) = service.run_studies(case, method, None, history, None, LAG)
    with ZipFile(io.BytesIO(study_zip(study))) as archive:
        hidden = set(archive.namelist())
    evaluation = service.reveal(study, history)
    with ZipFile(io.BytesIO(study_zip(study, evaluation))) as archive:
        revealed = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    assert not {"observations.csv", "errors.csv", "scores.csv"} & hidden
    assert {"observations.csv", "errors.csv", "scores.csv"} <= revealed
    assert manifest["case"]["snapshot_id"] == SNAPSHOT_ID
    status = study.forecast["prediction_status"]
    return check, reliability.check_forecast(study.forecast), status, evaluation


def test_reel_cas_normal(inventory, histories):
    case = known(inventory, NORMAL, "2026-10-13")
    check, forecast, status, evaluation = journey(case, histories[NORMAL])

    assert check.level == reliability.LEVEL_OK
    assert forecast.is_complete
    assert status.eq("ok").all()
    assert evaluation["n_compared_hours"] == 24
    assert evaluation["mae"] == pytest.approx(169 / 24)


def test_reel_une_mesure_manquante_un_repli(inventory, histories):
    case = known(inventory, NORMAL, "2026-10-31")
    check, forecast, status, _ = journey(case, histories[NORMAL])

    assert check.level == reliability.LEVEL_PARTIAL
    assert "1 des 24 mesures" in check.message
    assert forecast.is_complete
    assert status.eq("fallback").sum() == 1


def test_reel_semaine_precedente_vide_repli_complet(inventory, histories):
    case = known(inventory, NORMAL, "2026-10-11")
    check, forecast, status, _ = journey(case, histories[NORMAL])

    assert check.level == reliability.LEVEL_PARTIAL
    assert check.observed_hours == 0
    assert check.can_forecast  # le repli sur les semaines plus anciennes reste possible
    assert forecast.is_complete
    assert status.eq("fallback").all()


def test_reel_cibles_absentes_score_nul_et_explique(inventory, histories):
    case = known(inventory, NORMAL, "2026-10-25")
    _, forecast, _, evaluation = journey(case, histories[NORMAL])

    assert forecast.is_complete  # la prévision existe
    assert evaluation["n_compared_hours"] == 0
    assert evaluation["mae"] is None  # jamais une erreur de zéro
    assert evaluation["reason"]


def test_reel_compteur_sans_historique(inventory, histories):
    case = known(inventory, EMPTY, "2026-10-13")
    check = reliability.check_history(case, histories[EMPTY], LAG, "reference")

    assert check.level == reliability.LEVEL_NONE
    assert not check.can_forecast
    (study,) = service.run_studies(case, "reference", None, histories[EMPTY], None, LAG)
    assert study.forecast["prediction_status"].eq("unavailable").all()
    assert reliability.check_forecast(study.forecast).problems


def test_reel_nouveau_site_support_local(inventory, histories):
    case = service.technical_new_case(
        inventory.loc[NEW_SITE], pd.Timestamp("2026-10-13").date(), SNAPSHOT_ID, 168, LAG
    )
    check, forecast, _, evaluation = journey(case, histories[NEW_SITE], service.LOCAL_REFERENCE)

    assert check.level == reliability.LEVEL_OK
    assert check.observed_hours == 168
    assert forecast.is_complete
    assert evaluation["n_compared_hours"] == 24

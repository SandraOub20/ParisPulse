"""Score des expériences E2 (score.py) : petit exemple calculé à la main.

Deux compteurs, un cas chacun, 24 heures mesurées : A vaut 10 vélos/h, B 20 vélos/h.
- référence : 12 sur A (erreur 2), 20 sur B (erreur 0) -> MAE macro (2 + 0) / 2 = 1 ;
- hgb : 10 sur A sauf l'heure 1 en repli à 14 (erreur 4 sur 1 heure / 24), 23 sur B
  (erreur 3) -> MAE macro (4/24 + 3) / 2.
En lecture brute, l'heure de repli du hgb disparaît : le cas A n'est plus complet pour
toutes les méthodes, il sort de la comparaison, et seul B est comparé.
"""

from __future__ import annotations

import zipfile

import numpy as np
import pandas as pd
import pytest

from src.models.known import score as S

ORIGIN = pd.Timestamp("2026-07-01T22:00:00Z")


def _cases() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "case_id": ["A_case", "B_case"],
            "counter_id": ["A", "B"],
            "origin": [ORIGIN.isoformat()] * 2,
            "scenario": ["known_site"] * 2,
            "temporal_split": ["validation"] * 2,
            "snapshot_id": ["snap"] * 2,
        }
    )


def _observations() -> pd.DataFrame:
    stamps = [ORIGIN + pd.Timedelta(hours=h) for h in range(24)]
    rows = [
        (c, t.isoformat(), v, True, True) for c, v in (("A", 10.0), ("B", 20.0)) for t in stamps
    ]
    return pd.DataFrame(rows, columns=S.OBSERVATION_USECOLS)


def _forecast(
    method: str, variant: str, values: dict[str, float], fallback_a1: float | None = None
):
    rows = []
    for counter, value in values.items():
        for h in range(1, 25):
            y, status = value, "ok"
            if counter == "A" and h == 1 and fallback_a1 is not None:
                y, status = fallback_a1, "fallback"
            rows.append(
                {
                    "case_id": f"{counter}_case",
                    "method_run_id": method,
                    "counter_id": counter,
                    "horizon": h,
                    "target_timestamp": (ORIGIN + pd.Timedelta(hours=h - 1)).isoformat(),
                    "y_pred": y,
                    "variant": variant,
                    "prediction_status": status,
                }
            )
    return pd.DataFrame(rows)


def _forecasts() -> pd.DataFrame:
    ref = _forecast("ref", "reference", {"A": 12.0, "B": 20.0})
    hgb = _forecast("hgb", "hgb", {"A": 10.0, "B": 23.0}, fallback_a1=14.0)
    return pd.concat([ref, hgb], ignore_index=True)


def test_score_systeme_calcul_a_la_main():
    table = S.score(_cases(), _forecasts(), _observations())
    assert table.loc["ref", "mae_macro"] == pytest.approx(1.0)
    assert table.loc["hgb", "mae_macro"] == pytest.approx((4 / 24 + 3) / 2)
    # biais sur toutes les heures ensemble : ref +2 sur 24 h de A, 0 sur B
    assert table.loc["ref", "bias"] == pytest.approx(2 * 24 / 48)
    assert table.loc["hgb", "n_fallback_cases"] == 1
    assert table.loc["ref", "n_compared_cases"] == 2
    assert list(table.index) == ["ref", "hgb"]  # trié par MAE


def test_score_brut_retire_le_repli_du_modele_pas_de_la_reference():
    raw = S.as_raw(_forecasts())
    hgb_a1 = raw[(raw.method_run_id == "hgb") & (raw.counter_id == "A") & (raw.horizon == 1)]
    assert hgb_a1["y_pred"].isna().all() and (hgb_a1["prediction_status"] == "unavailable").all()
    assert raw.loc[raw.method_run_id == "ref", "y_pred"].notna().all()

    table = S.score(_cases(), raw, _observations())
    # le cas A n'est plus complet pour hgb : seule B reste comparée, pour les deux méthodes
    assert table.loc["ref", "n_compared_cases"] == 1
    assert table.loc["hgb", "mae_macro"] == pytest.approx(3.0)
    assert table.loc["ref", "mae_macro"] == pytest.approx(0.0)
    assert table.loc["hgb", "coverage_24h"] == pytest.approx(0.5)


def test_score_experiment_lit_le_zip_et_ecrit_les_deux_lectures(tmp_path):
    exp = tmp_path / "pred" / "EXP-X"
    exp.mkdir(parents=True)
    with zipfile.ZipFile(exp / "EXP-X-predictions.zip", "w") as zf:
        for method, frame in _forecasts().groupby("method_run_id"):
            zf.writestr(f"EXP-X/{method}.pred.csv", frame.to_csv(index=False))
    (tmp_path / "eval" / "proto").mkdir(parents=True)
    _cases().to_csv(tmp_path / "eval" / "proto" / "cases.csv", index=False)
    (tmp_path / "processed" / "snap").mkdir(parents=True)
    _observations().to_csv(tmp_path / "processed" / "snap" / "counts.csv", index=False)

    tables = S.score_experiment(
        exp,
        protocol_id="proto",
        cases_root=tmp_path / "eval",
        processed_root=tmp_path / "processed",
    )
    assert set(tables) == {"système", "brut"}
    assert tables["système"].loc["ref", "mae_macro"] == pytest.approx(1.0)
    payload = S.to_json(tables)
    assert payload["brut"]["hgb"]["mae_macro"] == pytest.approx(3.0)


def test_vide_reste_vide_jamais_zero(tmp_path):
    """Un y_pred vide dans le fichier est lu comme absent (NaN), jamais comme 0."""
    frame = _forecast("ref", "reference", {"A": 12.0})
    frame.loc[0, "y_pred"] = np.nan
    path = tmp_path / "ref.pred.csv"
    frame.to_csv(path, index=False)
    loaded = S.load_forecasts(tmp_path)
    assert pd.isna(loaded.loc[0, "y_pred"]) and loaded.loc[1, "y_pred"] == 12.0


def test_erreurs_claires(tmp_path):
    with pytest.raises(FileNotFoundError, match="pred.csv"):
        S.load_forecasts(tmp_path)
    _forecasts().to_csv(tmp_path / "all.pred.csv", index=False)
    with pytest.raises(ValueError, match="absentes"):
        S.load_forecasts(tmp_path, methods=["inconnue"])


def test_score_experiment_plusieurs_dossiers(tmp_path):
    """EXP-E2-04 : les prévisions sans contexte d'un dossier, avec contexte d'un autre."""
    one, two = tmp_path / "pred" / "EXP-A", tmp_path / "pred" / "EXP-B"
    one.mkdir(parents=True)
    two.mkdir(parents=True)
    forecasts = _forecasts()
    forecasts[forecasts.method_run_id == "ref"].to_csv(one / "ref.pred.csv", index=False)
    forecasts[forecasts.method_run_id == "hgb"].to_csv(two / "hgb.pred.csv", index=False)
    (tmp_path / "eval" / "proto").mkdir(parents=True)
    _cases().to_csv(tmp_path / "eval" / "proto" / "cases.csv", index=False)
    (tmp_path / "processed" / "snap").mkdir(parents=True)
    _observations().to_csv(tmp_path / "processed" / "snap" / "counts.csv", index=False)
    kw = {"protocol_id": "proto", "cases_root": tmp_path / "eval"}
    tables = S.score_experiment([one, two], processed_root=tmp_path / "processed", **kw)
    assert set(tables["système"].index) == {"ref", "hgb"}
    with pytest.raises(ValueError, match="absentes"):
        S.score_experiment([one], methods=["hgb"], processed_root=tmp_path / "processed", **kw)


def test_score_detail_par_compteur():
    table, per_counter = S.score_detail(_cases(), _forecasts(), _observations())
    mae = per_counter.set_index(["method_run_id", "counter_id"])["MAE"]
    assert mae[("ref", "A")] == pytest.approx(2.0) and mae[("ref", "B")] == pytest.approx(0.0)
    assert mae[("hgb", "B")] == pytest.approx(3.0)
    # la MAE macro est la moyenne simple des MAE par compteur
    assert table.loc["hgb", "mae_macro"] == pytest.approx(mae["hgb"].mean())


def test_score_par_groupe():
    groups = pd.Series({"A_case": "a", "B_case": "b"})
    table = S.score_by_group(_cases(), _forecasts(), _observations(), groups)
    assert table.loc[("a", "ref"), "mae_macro"] == pytest.approx(2.0)
    assert table.loc[("b", "hgb"), "mae_macro"] == pytest.approx(3.0)
    assert table.loc[("a", "hgb"), "n_compared_cases"] == 1
    with pytest.raises(ValueError, match="aucun cas"):
        S.score_by_group(_cases(), _forecasts(), _observations(), pd.Series(dtype=str))

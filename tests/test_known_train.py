"""Socle commun de train.py : nommage, sauvegarde et rechargement des modèles E2.

Un faux modèle (un dictionnaire écrit en JSON) remplace le HGB et le MLP : on teste
ici la mécanique commune, pas un apprentissage. Tout est écrit dans tmp_path, jamais
dans artifacts/models.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from src.models.known import train
from src.models.known.train import (
    MethodBackend,
    TrainConfig,
    TrainedModel,
    config_fingerprint,
    get_backend,
    load_model,
    make_model_run_id,
    register_backend,
    save_model,
)

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = pd.Timestamp("2026-06-30 22:00", tz="UTC")  # 01/07/2026 minuit à Paris


def _save_json(estimator, path: Path) -> None:
    path.write_text(json.dumps(estimator), encoding="utf-8")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


FAKE = MethodBackend("weights.json", save=_save_json, load=_load_json)
register_backend("fake", FAKE)


def _config(**changes) -> TrainConfig:
    base = dict(
        method="fake",
        fit_cutoff=CUTOFF,
        hyperparameters={"hidden": 128, "lr": 0.001},
        snapshot_id="hist-20261117",
        protocol_id="proto-v1",
        feature_version="f1.0",
    )
    base.update(changes)
    return TrainConfig(**base)


def _model(config: TrainConfig | None = None) -> TrainedModel:
    config = config or _config()
    return TrainedModel(
        model_run_id=make_model_run_id(config),
        config=config,
        estimator={"weights": [1.5, -2.0, 3.25]},
        donor_site_groups=["100047541", "100003096"],
        label_interval=(pd.Timestamp("2023-10-16 00:00", tz="UTC"), CUTOFF),
        train_seconds=12.345,
        hardware="test-cpu",
        excluded_site_groups=["100049407"],
        minimum_history_hours=192,
        limitations=["essai"],
    )


# --- Nommage ---------------------------------------------------------------------------


def test_run_id_lisible_et_stable():
    run_id = make_model_run_id(_config())
    assert re.fullmatch(r"e2-fake-ctx-20260701-s0-[0-9a-f]{4}", run_id)
    assert make_model_run_id(_config()) == run_id  # même config -> même nom


def test_run_id_change_avec_un_seul_reglage():
    a = make_model_run_id(_config())
    b = make_model_run_id(_config(hyperparameters={"hidden": 256, "lr": 0.001}))
    assert a[:-4] == b[:-4]  # partie lisible identique
    assert a != b  # mais pas d'écrasement possible


def test_run_id_noctx_graine_et_methode_nettoyee():
    run_id = make_model_run_id(_config(method="MLP_torch", use_context=False, seed=2))
    assert run_id.startswith("e2-mlp-torch-noctx-20260701-s2-")


def test_run_id_refuse_une_coupure_sans_fuseau():
    with pytest.raises(ValueError, match="fuseau"):
        make_model_run_id(_config(fit_cutoff=pd.Timestamp("2026-07-01 00:00")))


def test_empreinte_independante_de_l_ordre_et_du_fuseau_d_ecriture():
    a = _config(hyperparameters={"hidden": 128, "lr": 0.001})
    b = _config(
        hyperparameters={"lr": 0.001, "hidden": 128},
        fit_cutoff=pd.Timestamp("2026-07-01 00:00", tz="Europe/Paris"),
    )
    assert config_fingerprint(a) == config_fingerprint(b)


# --- Registre des méthodes ---------------------------------------------------------------


def test_registre():
    assert get_backend("fake") is FAKE
    register_backend("fake", FAKE)  # redéclarer le même backend est sans effet
    with pytest.raises(ValueError, match="déjà déclarée"):
        register_backend("fake", MethodBackend("autre.json", _save_json, _load_json))
    with pytest.raises(KeyError, match="inconnue"):
        get_backend("absente")


# --- Sauvegarde --------------------------------------------------------------------------


def test_sauvegarde_puis_rechargement_identiques(tmp_path):
    model = _model()
    out = save_model(model, tmp_path)
    assert out == tmp_path / model.model_run_id
    assert sorted(p.name for p in out.iterdir()) == ["metadata.json", "weights.json"]

    back = load_model(model.model_run_id, tmp_path, expected_feature_version="f1.0")
    assert back.estimator == model.estimator
    assert back.config == model.config
    assert back.label_interval == model.label_interval
    assert back.excluded_site_groups == model.excluded_site_groups
    assert back.minimum_history_hours == 192
    assert back.train_seconds == pytest.approx(12.345)


def test_metadata_suit_le_gabarit_du_projet(tmp_path):
    model = _model()
    meta = json.loads((save_model(model, tmp_path) / "metadata.json").read_text("utf-8"))
    template = json.loads((ROOT / "doc/templates/model_metadata.example.json").read_text("utf-8"))
    missing = set(template) - {"template"} - set(meta)
    assert not missing, f"champs du gabarit absents : {missing}"
    assert meta["fit_cutoff"] == "2026-06-30T22:00:00+00:00"
    assert meta["excluded_site_groups"] == ["100049407"]
    assert len(meta["weights_sha256"]) == 64


def test_sauvegarde_refuse_d_ecraser(tmp_path):
    model = _model()
    save_model(model, tmp_path)
    with pytest.raises(FileExistsError):
        save_model(model, tmp_path)


def test_echec_d_ecriture_ne_laisse_aucun_dossier(tmp_path):
    def broken_save(estimator, path):
        path.write_text("à moitié", encoding="utf-8")
        raise OSError("disque plein (simulé)")

    register_backend("broken", MethodBackend("weights.json", broken_save, _load_json))
    model = _model(_config(method="broken"))
    with pytest.raises(OSError, match="disque plein"):
        save_model(model, tmp_path)
    assert list(tmp_path.iterdir()) == []  # ni modèle, ni dossier temporaire


# --- Rechargement : les refus -------------------------------------------------------------


@pytest.fixture
def saved(tmp_path):
    model = _model()
    return model, save_model(model, tmp_path)


def _edit_metadata(model_dir: Path, **changes) -> None:
    path = model_dir / "metadata.json"
    meta = json.loads(path.read_text("utf-8"))
    meta.update(changes)
    path.write_text(json.dumps(meta), encoding="utf-8")


def test_refus_modele_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_model("e2-fake-ctx-20260701-s0-0000", tmp_path)


def test_refus_poids_modifies(saved, tmp_path):
    model, model_dir = saved
    (model_dir / "weights.json").write_text(json.dumps({"weights": [9.9]}), encoding="utf-8")
    with pytest.raises(ValueError, match="modifiés depuis la sauvegarde"):
        load_model(model.model_run_id, tmp_path)


def test_refus_fiche_retouchee(saved, tmp_path):
    model, model_dir = saved
    _edit_metadata(model_dir, parameters={"hidden": 999, "lr": 0.001})
    with pytest.raises(ValueError, match="réglages ont été modifiés"):
        load_model(model.model_run_id, tmp_path)


def test_refus_dossier_renomme(saved, tmp_path):
    model, model_dir = saved
    model_dir.rename(tmp_path / "e2-fake-ctx-20260701-s0-ffff")
    with pytest.raises(ValueError, match="annonce"):
        load_model("e2-fake-ctx-20260701-s0-ffff", tmp_path)


def test_refus_chemin_de_poids_hors_du_dossier(saved, tmp_path):
    model, model_dir = saved
    _edit_metadata(model_dir, weights_path="../autre/weights.json")
    with pytest.raises(ValueError, match="nom de fichier"):
        load_model(model.model_run_id, tmp_path)


def test_refus_variables_differentes(saved, tmp_path):
    model, _ = saved
    with pytest.raises(ValueError, match="réentraîner"):
        load_model(model.model_run_id, tmp_path, expected_feature_version="f1.1")


def test_code_version_renseignee():
    version = train._code_version()
    assert version is None or re.fullmatch(r"[0-9a-f]{4,40}(-dirty)?", version)


# --- fit : la partie commune --------------------------------------------------------------

LAG = 24


def _synthetic_counts() -> pd.DataFrame:
    """3 compteurs horaires du 01/04 au 05/07/2026 : 2 sites connus, 1 site réservé E3."""
    hours = pd.date_range("2026-04-01 00:00", "2026-07-05 00:00", freq="h", tz="UTC")
    frames = []
    for cid in ("A-1", "A-2", "R-1"):
        frames.append(
            pd.DataFrame(
                {
                    "counter_id": cid,
                    "timestamp": hours,
                    "count_raw": 10.0,
                    "is_observed": True,
                    "is_scoreable": True,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


INVENTORY = pd.DataFrame(
    {
        "counter_id": ["A-1", "A-2", "R-1"],
        "site_group_id": ["G-A", "G-A", "G-R"],
        "site_role": ["S_train", "S_train", "S_test_new"],
        "selection_status": ["retained", "robustness", "reserved_test_new"],
        "period_role": ["selection"] * 3,
    }
)

SEEN: dict = {}


def _spy_fit(config, counts, context, origins):
    """Méthode espion : note ce que train.fit lui transmet et renvoie un petit modèle."""
    SEEN.update(counters=set(counts["counter_id"]), origins=origins.copy())
    return {"n_origins": len(origins)}


register_backend(
    "spy",
    MethodBackend("weights.json", _save_json, _load_json, fit=_spy_fit, minimum_history_hours=192),
)


def test_exclude_reserved_sites_retire_e3():
    kept = train.exclude_reserved_sites(_synthetic_counts(), INVENTORY)
    assert set(kept["counter_id"]) == {"A-1", "A-2"}
    assert set(
        train.exclude_reserved_sites(_synthetic_counts(), INVENTORY, False)["counter_id"]
    ) == {"A-1"}


def test_fit_commun_compteurs_origines_et_preuve():
    model = train.fit(
        _config(method="spy"), _synthetic_counts(), None, INVENTORY, publication_lag_hours=LAG
    )
    assert SEEN["counters"] == {"A-1", "A-2"}  # le site E3 n'arrive jamais à la méthode
    assert set(SEEN["origins"]["counter_id"]) == {"A-1", "A-2"}
    # dernière origine : ses 24 cibles publiées (24 h de délai) au plus tard à la coupure
    last = SEEN["origins"]["origin"].max()
    assert last + pd.Timedelta(hours=24 + LAG) <= CUTOFF
    assert last == pd.Timestamp("2026-06-28 22:00", tz="UTC")  # minuit à Paris le 29/06
    assert model.donor_site_groups == ["G-A"]
    assert model.excluded_site_groups == ["G-R"]
    assert model.label_interval[1] <= CUTOFF
    assert model.minimum_history_hours == 192
    assert model.estimator == {"n_origins": len(SEEN["origins"])}
    assert model.model_run_id == make_model_run_id(model.config)


def test_fit_respecte_train_start():
    start = pd.Timestamp("2026-06-01 00:00", tz="Europe/Paris").tz_convert("UTC")
    train.fit(
        _config(method="spy", train_start=start),
        _synthetic_counts(),
        None,
        INVENTORY,
        publication_lag_hours=LAG,
    )
    assert SEEN["origins"]["origin"].min() == start


def test_train_start_change_le_nom_et_survit_au_rechargement(tmp_path):
    start = pd.Timestamp("2023-10-16 00:00", tz="UTC")
    assert make_model_run_id(_config(train_start=start)) != make_model_run_id(_config())
    model = _model(_config(train_start=start))
    save_model(model, tmp_path)
    assert load_model(model.model_run_id, tmp_path).config.train_start == start


def test_fit_refuse_une_methode_qui_ne_sait_pas_apprendre():
    with pytest.raises(NotImplementedError, match="ne sait pas encore apprendre"):
        train.fit(_config(), _synthetic_counts(), None, INVENTORY, publication_lag_hours=LAG)


def test_fit_refuse_une_fenetre_vide():
    late = pd.Timestamp("2026-08-01 00:00", tz="UTC")
    with pytest.raises(ValueError, match="aucune origine"):
        train.fit(
            _config(method="spy", train_start=late),
            _synthetic_counts(),
            None,
            INVENTORY,
            publication_lag_hours=LAG,
        )


# --- load_training_data ---------------------------------------------------------------------


def _write_snapshot(folder: Path) -> None:
    folder.mkdir(parents=True)
    (folder / "counts.csv").write_text(
        "counter_id,timestamp,interval_end,count_raw,count,is_observed,is_scoreable\n"
        "A-1,2026-03-01T00:00:00+00:00,2026-03-01T01:00:00+00:00,12.0,12.0,true,true\n"
        "A-1,2026-03-01T01:00:00+00:00,2026-03-01T02:00:00+00:00,,12.0,false,false\n"
        "A-1,2026-03-01T02:00:00+00:00,2026-03-01T03:00:00+00:00,0.0,0.0,true,true\n",
        encoding="utf-8",
    )
    (folder / "context.csv").write_text(
        "variable,local_date,valid_time,value,available_at,role,context_version\n"
        "is_holiday,2026-03-01,,false,,known_calendar,e1-context/0.3.0\n"
        "temp_prev,,2026-03-01T01:00:00+00:00,10.6,2026-02-27T07:00:00+00:00,"
        "forecast_bulletin,e1-context/0.3.0\n",
        encoding="utf-8",
    )
    INVENTORY.to_csv(folder / "inventory_quality.csv", index=False)


def test_load_training_data_garde_les_seules_mesures(tmp_path):
    _write_snapshot(tmp_path / "snap")
    data = train.load_training_data("snap", root=tmp_path / "snap")
    counts = data.counts
    assert counts["timestamp"].dt.tz is not None  # dates en UTC
    assert counts["is_observed"].tolist() == [True, False, True]
    # heure non mesurée : valeur J-7 d'E1 mise de côté, pas utilisée en entrée
    assert pd.isna(counts["count"].iloc[1]) and counts["count_e1"].iloc[1] == 12.0
    assert counts["count"].iloc[2] == 0.0  # un zéro mesuré reste un zéro
    assert data.context_version == "e1-context/0.3.0"
    assert set(data.inventory["counter_id"]) == {"A-1", "A-2", "R-1"}

    filled = train.load_training_data("snap", root=tmp_path / "snap", values="e1_filled")
    assert filled.counts["count"].iloc[1] == 12.0


def test_load_training_data_erreurs_claires(tmp_path):
    with pytest.raises(FileNotFoundError, match="counts.csv"):
        train.load_training_data("absent", root=tmp_path / "absent")
    with pytest.raises(ValueError, match="values"):
        train.load_training_data("snap", root=tmp_path, values="autre")


def test_repo_relative_sans_chemin_personnel(tmp_path):
    """Le bilan commité garde un chemin relatif au dépôt, jamais /home/<personne>/..."""
    from src.common.config import ROOT

    inside = ROOT / "artifacts" / "models" / "e2-mlp-ctx-20260701-s0-ffff"
    assert train.repo_relative(inside) == "artifacts/models/e2-mlp-ctx-20260701-s0-ffff"
    outside = tmp_path / "e2-mlp-ctx-20260701-s0-ffff"  # hors du dépôt : le nom seul
    assert train.repo_relative(outside) == "e2-mlp-ctx-20260701-s0-ffff"

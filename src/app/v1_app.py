"""ParisPulse V1 exécutable sans écraser les fichiers des autres membres E5.

Lancer depuis la racine : uv run --no-dev streamlit run src/app/v1_app.py
V1 technique : référence E2 et MAE locale provisoire ; E4 officiel à raccorder.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src.app import v1_service as svc

st.set_page_config(page_title="ParisPulse · V1", layout="wide")
st.title("ParisPulse - V1 - première version intégrée")
st.caption("Un compteur = un seul sens. Les deux directions ne sont jamais additionnées.")


@st.cache_data(show_spinner="Chargement de l'inventaire...")
def inventory_cached(path: str, mtime: tuple[int, int]) -> pd.DataFrame:
    return svc.load_inventory(Path(path))


@st.cache_data(show_spinner="Lecture des mesures du compteur...")
def history_cached(path: str, counter_id: str, mtime: int) -> pd.DataFrame:
    return svc.load_counter_history(Path(path), counter_id)


@st.cache_data(show_spinner=False)
def cases_cached(snapshot_id: str, path_signature: tuple) -> pd.DataFrame:
    return svc.load_cases(snapshot_id)


def make_map(located: pd.DataFrame) -> folium.Map:
    positions = located[["latitude", "longitude"]].drop_duplicates()
    center = positions.mean().tolist() if not positions.empty else [48.8566, 2.3522]
    m = folium.Map(location=center, zoom_start=12, tiles="OpenStreetMap")
    if len(positions) > 1:
        m.fit_bounds(
            [positions.min().tolist(), positions.max().tolist()], padding=(20, 20), max_zoom=14
        )
    for row in located.itertuples(index=False):
        folium.CircleMarker(
            [row.latitude, row.longitude],
            radius=6,
            weight=1,
            color="#087f79",
            fill=True,
            fill_opacity=0.8,
            tooltip=str(row.counter_id),  # identifiant unique, même si deux points se superposent
            popup=folium.Popup(str(row.label), max_width=280),
        ).add_to(m)
    return m


def chart_history(history: pd.DataFrame) -> None:
    st.subheader("Historique du compteur")
    if history.empty:
        st.warning("Aucune mesure disponible pour ce compteur.")
        return
    last = history["timestamp"].max().tz_convert(svc.LOCAL_TZ).date()
    day = st.date_input("Dernier jour de l'historique", value=last, key="v1_history_end")
    end_local = pd.Timestamp(day).tz_localize(svc.LOCAL_TZ) + pd.DateOffset(days=1)
    start_local = end_local - pd.DateOffset(days=7)
    dates = history["timestamp"].dt.tz_convert(svc.LOCAL_TZ)
    window = history.loc[(dates >= start_local) & (dates < end_local)].copy()
    if window.empty:
        st.info("Pas de mesures sur ces dates.")
        return
    wdate = window["timestamp"].dt.tz_convert(svc.LOCAL_TZ)
    observed = window["is_scoreable"] & window["count_raw"].notna()
    estimated = ~window["is_scoreable"] & window["count"].notna()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=wdate,
            y=window["count_raw"].where(observed),
            mode="lines+markers",
            name="Observation exploitable",
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=wdate,
            y=window["count"].where(estimated),
            mode="markers",
            name="Valeur remplacée (E1)",
            marker={"symbol": "diamond", "size": 8},
        )
    )
    fig.update_layout(xaxis_title="Heure de Paris", yaxis_title="Vélos / heure", height=310)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"{int(observed.sum())} heures mesurées exploitables · "
        f"{int(estimated.sum())} valeurs remplacées · "
        f"{int(window['count'].isna().sum())} heures sans valeur"
    )


def chart_prediction(forecast: pd.DataFrame, errors: pd.DataFrame) -> None:
    st.subheader("Prévisions et observations sur les 24 heures")
    combined = forecast[["horizon", "target_timestamp", "y_pred", "prediction_status"]].copy()
    combined = combined.merge(
        errors[["horizon", "y_true", "is_scoreable"]], on="horizon", validate="one_to_one"
    )
    x = combined["target_timestamp"].dt.tz_convert(svc.LOCAL_TZ)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x, y=combined["y_pred"], name="Prévision", mode="lines+markers", connectgaps=False
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=combined["y_true"].where(combined["is_scoreable"]),
            name="Observation réelle (évaluable)",
            mode="lines+markers",
            connectgaps=False,
        )
    )
    fig.update_layout(height=420, xaxis_title="Heure de Paris", yaxis_title="Vélos / heure")
    st.plotly_chart(fig, use_container_width=True)


def bundle_export(forecast: pd.DataFrame, evaluation: dict, case) -> bytes:
    buf = io.BytesIO()
    metadata = {
        "case_id": case.case_id,
        "counter_id": case.counter_id,
        "snapshot_id": case.snapshot_id,
        "protocol_id": case.protocol_id,
        "origin_utc": case.origin.isoformat(),
        "note": "MAE de contrôle V1 non validée par E4 ; pas un score scientifique officiel",
        "mae_v1": evaluation["mae"],
        "n_compared_hours": evaluation["n_compared_hours"],
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("forecasts.csv", forecast.to_csv(index=False))
        z.writestr("errors.csv", evaluation["errors"].to_csv(index=False))
        z.writestr("manifest.json", json.dumps(metadata, indent=2, ensure_ascii=False))
    return buf.getvalue()


def main() -> None:
    snapshots = svc.snapshot_dirs()
    if not snapshots:
        st.error(
            "Données E1 absentes : décompresse d'abord livraison/hist-20261117.zip à la racine."
        )
        st.code(
            "git lfs install\ngit lfs pull --include='livraison/hist-20261117.zip'\nunzip -o livraison/hist-20261117.zip",
            language="bash",
        )
        st.stop()
    names = {p.name: p for p in snapshots}
    snapshot_name = st.selectbox("Version des données E1", list(names))
    snap = names[snapshot_name]
    q = snap / "inventory_quality.csv"
    inv = inventory_cached(
        str(snap),
        ((snap / "counters.csv").stat().st_mtime_ns, q.stat().st_mtime_ns if q.exists() else 0),
    )
    st.caption(f"{len(inv)} compteurs répertoriés · données : {snapshot_name}")
    inventory, panel = st.columns([3, 2], gap="large")
    status_values = sorted(inv["selection_status"].fillna("non précisé").astype(str).unique())
    status = panel.selectbox("Statut E1", ["Tous"] + status_values)
    visible = (
        inv if status == "Tous" else inv[inv["selection_status"].fillna("non précisé").eq(status)]
    )
    if visible.empty:
        st.warning("Aucun compteur avec ce statut")
        st.stop()
    available_ids = visible["counter_id"].astype(str).tolist()
    if st.session_state.get("v1_selected_counter") not in available_ids:
        st.session_state["v1_selected_counter"] = available_ids[0]
    points = visible.loc[visible["located"]]
    with inventory:
        st.subheader("Carte des compteurs")
        if points.empty:
            st.warning("Aucune coordonnée valide pour cette sélection")
        else:
            event = st_folium(
                make_map(points),
                key=f"v1_map:{snapshot_name}:{status}",
                height=440,
                use_container_width=True,
                returned_objects=["last_object_clicked_tooltip", "last_object_clicked_count"],
            )
            if isinstance(event, dict):
                cid = str(event.get("last_object_clicked_tooltip") or "")
                click_count = event.get("last_object_clicked_count")
                signature = (cid, str(click_count))
                if cid in available_ids and signature != st.session_state.get("v1_last_map_click"):
                    st.session_state["v1_selected_counter"] = cid
                    st.session_state["v1_last_map_click"] = signature
    label_by_id = dict(zip(visible["counter_id"].astype(str), visible["label"].astype(str)))
    with panel:
        selected = st.selectbox(
            "Compteur / sens",
            available_ids,
            format_func=lambda cid: label_by_id[cid],
            key="v1_selected_counter",
        )
        row = visible.loc[visible["counter_id"].eq(selected)].iloc[0]
        st.write("**Site :**", row["site_name"] if pd.notna(row["site_name"]) else "Non renseigné")
        st.write("**Sens :**", row["direction"] if pd.notna(row["direction"]) else "Non renseigné")
        st.write(
            "**Statut E1 :**",
            row["selection_status"] if pd.notna(row["selection_status"]) else "Non renseigné",
        )
        st.caption(
            "La sélection porte toujours sur un compteur, jamais sur la somme des deux sens."
        )
    counts_path = snap / "counts.csv"
    if not counts_path.exists():
        st.error("counts.csv introuvable pour le snapshot choisi")
        st.stop()
    try:
        history = history_cached(str(snap), selected, counts_path.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError) as error:
        st.error(f"Impossible de lire l'historique : {error}")
        st.stop()
    chart_history(history)
    if history.empty:
        st.stop()

    st.divider()
    st.subheader("Prévoir 24 heures")
    case_files = sorted((svc.ROOT / "data" / "evaluation").glob("*/cases.csv"))
    sig = tuple((str(p), p.stat().st_mtime_ns) for p in case_files)
    try:
        cases = cases_cached(snapshot_name, sig)
    except (OSError, ValueError) as error:
        st.warning(f"Cas E4 non chargés : {error}")
        cases = pd.DataFrame()
    available = cases.loc[cases["counter_id"].eq(selected)] if not cases.empty else pd.DataFrame()
    if not available.empty:
        available = available.sort_values("origin")
        opts = available["case_id"].astype(str).tolist()
        index = {str(v): i for i, v in enumerate(available["case_id"])}
        chosen_id = st.selectbox(
            "Cas E4 (date, scénario et budget)",
            opts,
            format_func=lambda cid: (
                f"{available.iloc[index[cid]]['origin']} · "
                f"{available.iloc[index[cid]]['scenario']} · "
                f"budget {available.iloc[index[cid]].get('local_budget_hours', '')} h"
            ),
        )
        case = svc.make_case(available.iloc[index[chosen_id]])
        st.caption(
            f"Cas issu du protocole E4 : {case.protocol_id}. Statut scientifique à confirmer."
        )
    else:
        if str(row["site_role"]) not in ("S_train", "<NA>", "nan") and str(
            row["selection_status"]
        ).startswith("reserved"):
            st.warning("Nouveau site : récupère cases.csv d'E4 pour sélectionner un cas E3 valide.")
            st.stop()
        st.info(
            "cases.csv E4 non disponible pour ce compteur : cas technique de V1, hors évaluation officielle."
        )
        local_dates = history["timestamp"].dt.tz_convert(svc.LOCAL_TZ)
        min_day = (local_dates.min() + pd.Timedelta(days=9)).date()
        max_day = local_dates.max().date()
        if min_day > max_day:
            st.warning("Historique trop court pour préparer une origine technique.")
            st.stop()
        default_day = pd.Timestamp("2026-08-10").date()
        if not min_day <= default_day <= max_day:
            default_day = max_day
        chosen_day = st.date_input(
            "Date de prévision (heure de Paris : 00 h)",
            value=default_day,
            min_value=min_day,
            max_value=max_day,
        )
        group = row["site_group_id"] if pd.notna(row["site_group_id"]) else None
        case = svc.pilot_case(selected, chosen_day, snapshot_name, site_group_id=group)

    if case.scenario == "known_site":
        variant = st.selectbox("Méthode E2 disponible", ["reference", "reference_profile"])
        st.caption("La variante modèle entraîné n'est pas encore connectée à predict_24h sur dev.")
    else:
        variant = "frozen (CSV E3)"
        st.caption(
            "Nouveau site : prévisions Chronos-2 déjà enregistrées, sans installer le modèle localement."
        )

    run_key = (case.case_id, case.snapshot_id, variant)
    if st.button("Calculer et afficher", type="primary"):
        with st.spinner("Calcul et alignement des 24 heures..."):
            try:
                if case.scenario == "known_site":
                    raw = svc.predict_known_reference(case, history, variant)
                else:
                    raw = svc.precomputed_new_forecast(case)
                forecast = svc.validate_forecast(raw, case)
                result = svc.evaluate_local(case, forecast, history)
                st.session_state["v1_result"] = (run_key, forecast, result, case)
            except (
                ValueError,
                KeyError,
                OSError,
                RuntimeError,
                ImportError,
                NotImplementedError,
            ) as error:
                st.session_state.pop("v1_result", None)
                st.error(f"Prévision impossible : {error}")
    stored = st.session_state.get("v1_result")
    if stored and stored[0] == run_key:
        _, forecasts, result, run_case = stored
        chart_prediction(forecasts, result["errors"])
        col_a, col_b, col_c = st.columns(3)
        col_a.metric(
            "MAE V1 indicative",
            f"{result['mae']:.2f} vélos" if result["mae"] is not None else "Indisponible",
        )
        col_b.metric("Heures comparables", f"{result['n_compared_hours']}/24")
        col_c.metric("Heures prédites", f"{result['n_forecast_hours']}/24")
        if result["reason"]:
            st.warning(result["reason"])
        st.caption("Score MAE calculé localement pour vérifier la V1, et non score officiel E4.")
        st.subheader("État des prévisions")

        status_counts = forecasts["prediction_status"].value_counts()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Réussies", int(status_counts.get("ok", 0)))
        col2.metric("Replis", int(status_counts.get("fallback", 0)))
        col3.metric("Indisponibles", int(status_counts.get("unavailable", 0)))
        col4.metric("Erreurs", int(status_counts.get("error", 0)))

        if status_counts.get("error", 0) or status_counts.get("unavailable", 0):
            st.warning("Certaines prévisions sont indisponibles.")
        elif status_counts.get("fallback", 0):
            st.info("Certaines prévisions utilisent une méthode de repli.")
        else:
            st.success("24 prévisions réussies sans repli.")

        st.caption(f"Modèle utilisé : {forecasts['method_run_id'].iloc[0]}")

        with st.expander("Voir les statuts heure par heure"):
            st.dataframe(
                forecasts[["horizon", "prediction_status", "method_used", "status_reason"]],
                use_container_width=True,
                hide_index=True,
            )
        st.dataframe(result["errors"], use_container_width=True, hide_index=True)
        st.download_button(
            "Exporter cette étude (prévisions + erreurs + manifeste)",
            bundle_export(forecasts, result, run_case),
            file_name=f"parispulse-v1-{case.case_id}.zip",
            mime="application/zip",
        )
    else:
        st.info("Choisis un cas, puis clique sur « Calculer et afficher ».")


if __name__ == "__main__":
    main()

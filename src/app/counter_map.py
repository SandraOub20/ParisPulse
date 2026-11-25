"""
Carte et historique des compteurs à partir des CSV préparés par E1 
"""

from html import escape # Protège le texte d’une infobulle. Par exemple, un < dans un nom de compteur s’affiche comme du texte
from pathlib import Path

import folium # pour construire la carte et ses marqueurs
import pandas as pd
import plotly.graph_objects as go # pour les graphiques 
import streamlit as st # Afficher les éléments de l'interface 
from streamlit_folium import st_folium # Insère la carte Folium dans Streamlit et récupère les interactions avec la carte

LOCAL_TZ = "Europe/Paris" # Fuseau horraire utilisé pour afficher les heures
DEMO_SOURCE = "Démo - données fictives" # Le texte de l’option

# __file__ désigne le fichier counter_map.py
# Path(__file__).resolve() obtient son chemin absolu
# .parents[0] correspond à app, .parents[1] à src et .parents[2] à ParisPulse
# / "data" / "processed" ajoute les deux dossiers au chemin. Avec un objet Path, / sert à assembler les morceaux du chemin.
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

# liste les colonnes utiles pour identifier et situer chaque compteur
COUNTER_COLUMNS = [
    "counter_id",
    "counter_name",
    "site_name",
    "latitude",
    "longitude",
    "direction",
] 

# liste celles utiles pour connaître ses mesures
COUNT_COLUMNS = ["counter_id", "timestamp", "count", "is_observed"]
# Dict pour traduire les codes - à modifier - voir avec l'E1 
STATUS_LABELS = {
    "retained": "Retenu",
    "robustness": "Robustesse",
    "reserved_dev_new": "Réservé · nouveau site (validation)",
    "reserved_test_new": "Réservé · nouveau site (test)",
    "excluded": "Exclu",
}


# _read_csv est une fonction utilisée à l’intérieur du module. Le _ en début de nom indique cette intention par convention.
# - path est le chemin du CSV. columns contient la liste des colonnes à lire.
# - usecols=columns limite la lecture à ces colonnes.
# - dtype="string" lit leurs valeurs comme du texte. Un identifiant comme 001 garde ainsi ses zéros initiaux. Le code convertira ensuite les coordonnées et les comptages en nombres.
# - keep_default_na=False préserve notamment les cellules vides sous forme de texte vide. Les fonctions suivantes décident comment traiter chacune de ces valeurs.
# - -> pd.DataFrame indique que la fonction renvoie un tableau pandas.
# @st.cache_data est un décorateur. Il demande à Streamlit de conserver le résultat pour pouvoir le réutiliser lors d’un appel avec les mêmes arguments. show_spinner=False masque l’indicateur de chargement du cache. modified_at_ns est utile même s’il n’apparaît pas dans le return. Il fait partie des arguments du cache. Si la date de modification du CSV change, l’appel utilise une nouvelle clé et Streamlit relit le fichier
@st.cache_data(show_spinner=False)
def _read_csv(path: Path, columns: list[str], modified_at_ns: int) -> pd.DataFrame:
    # La date de modification fait partie de la clé de cache.
    return pd.read_csv(path, usecols=columns, dtype="string", keep_default_na=False)

# La fonction _load_snapshot(snapshot) reçoit un dossier d’instantané, par exemple data/processed/flux-20261115/
# Elle construit trois chemins et renvoie trois tableaux, toujours dans cet ordre
# counters	=> counters.csv	Obligatoire => Il fournit la liste des compteurs
# counts => counts.csv	=> Facultatif =>  En son absence, le code garde un tableau vide avec les colonnes attendues
# quality => inventory_quality.csv	=> Facultatif => Il fournit le statut E1 et sa raison
def _load_snapshot(snapshot: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    counters_path = snapshot / "counters.csv"
    counts_path = snapshot / "counts.csv"
    quality_path = snapshot / "inventory_quality.csv"
    
    counters = _read_csv(counters_path, COUNTER_COLUMNS, counters_path.stat().st_mtime_ns)
    counts = pd.DataFrame(columns=COUNT_COLUMNS)
    quality = pd.DataFrame(columns=["counter_id", "selection_status", "status_reason"])
    
    # Vérifient que les fichiers existent avant de les lire
    # path.stat().st_mtime_ns récupère la date de modification transmise au cache
    if counts_path.is_file():
        counts = _read_csv(counts_path, COUNT_COLUMNS, counts_path.stat().st_mtime_ns)
    if quality_path.is_file():
        quality = _read_csv(quality_path, list(quality.columns), quality_path.stat().st_mtime_ns)
    
    # Grâce aux tableaux vides, la carte peut déjà s’afficher avec le seul inventaire des compteurs
    return counters, counts, quality



# Fabriquer les données de démo
# fabrique les mêmes trois tableaux pour que toute la suite fonctionne aussi en mode fictif
def _demo_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    counters = pd.DataFrame(
        [
            ("DEMO-01", "Rivoli (exemple)", "Rivoli", 48.8571, 2.3538, "Est => Ouest"),
            ("DEMO-02", "Canal (exemple)", "Canal", 48.8730, 2.3640, "Sud => Nord"),
            ("DEMO-03", "Site sans position (exemple)", "Site démo", None, None, ""),
        ],
        columns=COUNTER_COLUMNS,
    )
    
    # crée 168 heures, soit sept fois 24 heures, à partir du 1er novembre 2026
    hours = pd.date_range("2026-11-01", periods=168, freq="h", tz="UTC")
    # cree le tableau de comptage les empile et nimérote les lignes 
    counts = pd.concat(
        [
            pd.DataFrame(
                {
                    "counter_id": counter_id,
                    "timestamp": hours,
                    # hour est ici le numéro de la ligne dans la série, 
                    # à partir de zéro. % 9 calcule le reste de la division par 9. 
                    # Pour Rivoli, base vaut 40. Les premières valeurs sont donc 40, 48, 56, puis le motif recommence à 40 quand hour atteint 9. 
                    # Ce calcul sert uniquement à fabriquer une courbe fictive
                    "count": [base + 8 * (hour % 9) for hour in range(len(hours))],
                    "is_observed": "true",
                }
            )
            for counter_id, base in [("DEMO-01", 40), ("DEMO-03", 20)]
        ],
        ignore_index=True,
    )
    
    # Ensuite, le code force la ligne 140 à zéro et les lignes 146 à 149 
    # à valeur absente avec is_observed = "false". Ces cas permettent de 
    # voir qu’un zéro est tracé dans la courbe, tandis qu’une mesure absente 
    # laisse un trou
    counts.loc[140, "count"] = 0
    counts.loc[146:149, "count"] = None
    counts.loc[146:149, "is_observed"] = "false"
    quality = pd.DataFrame(
        [("DEMO-01", "retained", ""), ("DEMO-03", "robustness", "Coordonnées indisponibles")],
        columns=["counter_id", "selection_status", "status_reason"],
    )
    return counters, counts, quality


# réunit les informations utiles dans un tableau que l’écran peut exploiter
def _counter_index(
    counters: pd.DataFrame,
    counts: pd.DataFrame,
    quality: pd.DataFrame,
) -> pd.DataFrame:
    # utilise l’identifiant comme clé de ligne et déclenche une erreur s’il est dupliqué.
    # On peut ensuite retrouver Rivoli avec counters.loc["DEMO-01"]
    counters = counters.set_index("counter_id", verify_integrity=True)
    
    # Convertit la latitude et la longitude en nombres. 
    # errors="coerce" transforme une valeur illisible en valeur manquante. 
    # located vaut True lorsque latitude et longitude sont dans leurs plages valides
    for coord in ["latitude", "longitude"]:
        counters[coord] = pd.to_numeric(counters[coord], errors="coerce")
        
    counters["located"] = (
        counters.latitude.between(-90, 90) & counters.longitude.between(-180, 180)
    ).fillna(False)
    
    # Fabrique le libellé visible. Il prend le nom du compteur, puis le nom du site si nécessaire, puis "Compteur". Il ajoute l’identifiant
    names = counters.counter_name.replace("", pd.NA).fillna(counters.site_name.replace("", pd.NA))
    counters["label"] = names.fillna("Compteur") + " - " + counters.index
    
    # isin(...) vérifie si l’identifiant apparaît dans counts
    # Avec historique chargé signifie qu’il existe au moins une ligne de comptage
    # même si les valeurs de ces lignes sont manquantes.
    counters["has_history"] = counters.index.isin(counts.counter_id)
    
    # Garde une ligne de qualité par compteur, 
    # puis ajoute les informations de qualité en faisant correspondre les identifiants
    # L’inventaire conserve ses compteurs même s’il manque leur statut    
    quality = quality.drop_duplicates("counter_id").set_index("counter_id")
    counters = counters.join(quality)
    
    # Traduit le code de statut, utilise "Non renseigné" si nécessaire et trie les compteurs par libellé
    counters["status"] = counters.selection_status.map(STATUS_LABELS).fillna("Non renseigné")
   
    return counters.sort_values("label")


# reçoit les compteurs déjà filtrés qui ont des coordonnées valides
# envoie l’objet carte. Plus bas, c’est st_folium(...) qui l’affiche dans la page Streamlit
def _build_map(counters: pd.DataFrame) -> folium.Map:
    
    # drop_duplicates() garde les positions distinctes pour calculer le cadrage
    positions = counters[["latitude", "longitude"]].drop_duplicates()
    
    # calcule le centre initial, sous la forme [latitude, longitude]
    center = positions.mean().tolist()
    
    # crée la carte avec un fond OpenStreetMap et un zoom initial de 13
    view = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap")
    
    # S’il y a plusieurs positions distinctes, fit_bounds(...) 
    # ajuste la vue pour les faire tenir à l’écran, avec une marge. 
    # Il utilise le minimum et le maximum de chaque coordonnée pour former le rectangle
    if len(positions) > 1:
        view.fit_bounds(
            [positions.min().tolist(), positions.max().tolist()], padding=(28, 28), max_zoom=14
        )
        
    # parcourt les compteurs. La couleur est turquoise si has_history vaut True, grise sinon
    for counter in counters.itertuples():
        color = "#087f79" if counter.has_history else "#667587"
        # Folium insère les infobulles dans un littéral JavaScript et dans le HTML
        # escape(...) et les trois .replace(...) protègent le texte dans l’infobulle
        tooltip = (
            escape(counter.label).replace("`", "&#96;").replace("$", "&#36;").replace("\\", "&#92;")
        )
        
        # définit le marqueur.
        folium.CircleMarker(
            [counter.latitude, counter.longitude],
            radius=7, # fixe sa taille
            color=color, # couleur
            weight=2, # l’épaisseur du contour
            fill=True, # active le remplissage
            fill_opacity=0.75, # règle son opacité
            tooltip=tooltip,
        ).add_to(view) # ajoute le cercle à la carte
    return view

# transforme le CSV en série horaire
def _history_for(counts: pd.DataFrame, counter_id: str) -> pd.Series:
    
    # crée un masque qui vaut True pour les lignes du compteur demandé
    rows = counts.loc[counts.counter_id.eq(counter_id)]
    
    # convertit les horodatages en dates utilisables en UTC. Le code signale les formats invalides ou les dates manquantes
    hours = pd.to_datetime(rows.timestamp, format="ISO8601", utc=True, errors="raise")
    if hours.isna().any():
        raise ValueError("Un horodatage est manquant")
    
    # convertit les comptages en nombres. 
    values = pd.to_numeric(rows["count"], errors="coerce")
    
    # where(rows.is_observed.eq("true")) conserve la valeur seulement quand la ligne est déclarée observée. 
    # Une valeur observée de 0 reste 0
    values = values.where(rows.is_observed.eq("true")).astype(float)
    
    # associe chaque valeur à son horodatage. Le code refuse deux lignes qui correspondent au même instant
    history = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(hours), name="Passages")
    if history.index.has_duplicates:
        raise ValueError("Plusieurs lignes existent pour la même heure de ce compteur")
    
    # sort_index() trie les heures
    # asfreq("h") ajoute les heures absentes entre la première et la dernière avec NaN
    # puis tz_convert(LOCAL_TZ) convertit les heures pour l’affichage à Paris
    # Par exemple, avec 12 passages à 08 h et 0 passage à 10 h, 
    # la série contient 08 h => 12, 09 h => NaN, 10 h => 0. Le zéro correspond à une mesure. 
    # NaN indique que l’application n’a pas de valeur exploitable à cette heure
    return history.sort_index().asfreq("h").tz_convert(LOCAL_TZ)



# Affiche la série
def _render_history(counts: pd.DataFrame, counter_id: str) -> None:
    # affiche le titre
    st.subheader("Historique horaire")
    
    # appelle _history_for() et gère deux cas
    try:
        history = _history_for(counts, counter_id)
    # Une erreur déclenche un message avec st.error(...)
    except ValueError as error:
        st.error(f"Historique indisponible · {error}")
        return
    # Une série vide déclenche le message « Aucun historique chargé pour ce compteur »
    # Dans les deux cas, return arrête cette fonction avant de construire le graphique
    if history.empty:
        st.info("Aucun historique chargé pour ce compteur.")
        return

    first_day, last_day = history.index[0].date(), history.index[-1].date()
    # affiche le calendrier. 
    # Sa valeur initiale est le dernier jour de l’historique. 
    # min_value et max_value limitent les choix aux dates disponibles. 
    # La clé contient notamment l’identifiant du compteur pour donner au widget une identité liée à cette sélection
    end_day = st.date_input(
        "Dernier jour affiché",
        value=last_day,
        min_value=first_day,
        max_value=last_day,
        format="DD/MM/YYYY",
        key=f"counter_history_date:{counter_id}:{first_day}:{last_day}",
    )
    # On rajoute un jour car si on veut aller jusqu'au 10 nov inclut on doit mentionner le 11 nov exclut (minuit)
    end = pd.Timestamp(end_day) + pd.DateOffset(days=1)
    start = end - pd.DateOffset(days=7)
    window = history.loc[
        (history.index >= start.tz_localize(LOCAL_TZ)) & (history.index < end.tz_localize(LOCAL_TZ))
    ]
    
    # window.isna().sum() compte les heures sans valeur valide et window.eq(0).sum() compte les zéros
    st.caption(
        f"Jusqu’à 7 jours - heure de Paris -  {window.isna().sum()} h sans valeur valide -  "
        f"{window.eq(0).sum()} h à zéro"
    )
    
    # window.count() compte les valeurs valides
    # Si ce nombre vaut zéro, la fonction affiche un message à la place d’une courbe
    if window.count() == 0:
        st.info("Aucune valeur valide sur cette période")
        return

    # go.Scatter(...) crée la courbe avec les heures sur l’axe x et les passages sur l’axe y
    # connectgaps=False laisse les trous visibles
    # L’axe utilise des instants en UTC pour garder chaque heure distincte
    # y compris lors du passage à l’heure d’hiver
    # Les dates affichées sous la courbe et l’heure affichée au survol sont celles de Paris
    # Au survol, %z précise aussi le décalage horaire
    figure = go.Figure(
        go.Scatter(
            x=window.index.tz_convert("UTC"),
            y=window.to_numpy(),
            text=window.index.strftime("%d/%m/%Y %H:%M %Z (%z)"),
            mode="lines",
            connectgaps=False,
            line={"color": "#087f79", "width": 2},
            hovertemplate="%{text}<br>%{y} passages<extra></extra>",
        )
    )
    ticks = window.index[window.index.hour == 0]
    
    # figure.update_layout(...) règle la présentation 
    # st.plotly_chart(...) affiche le graphique
    figure.update_layout(
        height=310,
        margin={"l": 12, "r": 12, "t": 8, "b": 12},
        yaxis_title="Passages / h",
        xaxis={"tickvals": ticks.tz_convert("UTC"), "ticktext": ticks.strftime("%d/%m")},
    )
    st.plotly_chart(figure, width="stretch")


# Relier la source, la carte, la liste et le graphique
# Quand streamlit_app.py appelle la fonction sans argument, elle cherche dans ParisPulse/data/processed/
# elle renvoie l’identifiant du compteur sélectionné, ou None si l’inventaire ne peut pas être chargé ou s’il est vide
def render_counter_explorer(processed_dir: Path = PROCESSED_DIR) -> str | None:
    """Affiche le réseau et renvoie l'identifiant du compteur sélectionné"""
    
    # glob("*/counters.csv") cherche les fichiers counters.csv dans les sous-dossiers immédiats de data/processed/
    # Le code les trie par nom de dossier en ordre décroissant
    # puis construit la liste des sources et y ajoute la démo sources.get(source) donne le dossier choisi, ou None pour la démo
    snapshots = sorted(
        (path for path in processed_dir.glob("*/counters.csv") if path.is_file()),
        key=lambda path: path.parent.name,
        reverse=True,
    )
    
    # Associe un texte a son chemin sur le disque
    sources = {f"Instantané - {path.parent.name}": path.parent for path in snapshots}
    
    # Ouvre la liste des sources. *sources y ajoute les clés du dictionnaire, donc les noms visibles, puis le code ajoute la démo
    source = st.selectbox("Source des données", [*sources, DEMO_SOURCE])
    
    # Récupère le chemin associé au choix
    snapshot = sources.get(source)
    if snapshot is None:
        st.info("Mode démo - Les compteurs et les mesures affichés sont fictifs")

    # data contient les trois tableaux
    # Le * les passe séparément à _counter_index, 
    # comme si on avait  _counter_index(data[0], data[1], data[2])
    try:
        # Lit les vrais CSV si on a choisi un dossier. Sinon, fabrique les tableaux de démo
        data = _load_snapshot(snapshot) if snapshot else _demo_snapshot()
        
        # data contient les fiches, les mesures et les diagnostics
        # *data donne les trois tableaux à la fonction
        # qui prépare une ligne par compteur avec les colonnes located, has_history, label et status
        counters = _counter_index(*data)
    except (OSError, ValueError) as error:
        st.error(f"Chargement de l’inventaire impossible · {error}")
        return None
    
    if counters.empty:
        st.info("L’inventaire est vide.")
        return None

# Afficher les compteurs et appliquer le filtre

    # Crée trois emplacements pour les chiffres en haut de la page
    inventory, located, loaded = st.columns(3)
    
    # len(counters) compte toutes les fiches
    # La somme de located compte les True pour les coordonnées
    # La somme de has_history compte les True pour l’historique
    inventory.metric("Compteurs inventoriés", len(counters))
    located.metric("Avec coordonnées", int(counters.located.sum()))
    loaded.metric("Avec historique chargé", int(counters.has_history.sum()))

	# Donne trois parts de largeur à la carte et deux au panneau de sélection
    map_panel, selection_panel = st.columns([3, 2], gap="large")
    
    # Affiche le titre et le filtre dans le panneau
    with selection_panel:
        st.subheader("Sélection")
        status = st.selectbox(
            "Statut dans l’inventaire E1",
            ["Tous les statuts", *sorted(counters.status.unique())],
            key=f"map_status:{source}",
        )
        
    # Garde tous les compteurs ou seulement ceux du statut choisi
    # visible sert à remplir la liste
    visible = counters if status == "Tous les statuts" else counters[counters.status.eq(status)]
    
    # Garde, parmi les compteurs visibles, ceux qui ont une position
    # points sert à dessiner la carte.
    points = visible[visible.located]
    
    # Donnent une clé distincte à la liste et à la carte
    # en incluant la source et le filtre choisis
    selection_key = f"counter_selection:{source}:{status}"
    map_key = f"counter_map:{source}:{status}"
    
    # Fabrique la correspondance texte de l’infobulle => identifiant Exemple Rivoli (exemple) - DEMO-01 →=>DEMO-01
    ids_by_label = dict(zip(points.label, points.index))

    # réagit au clic sur un point
    def select_marker() -> None:
        clicked = st.session_state.get(map_key, {}).get("last_object_clicked_tooltip")
        if clicked in ids_by_label:
            st.session_state[selection_key] = ids_by_label[clicked]


    # affiche la carte à gauche
    with map_panel:
        if points.empty:
            st.info("Aucune coordonnée valide pour cette sélection.")
        else:
            st_folium(
                _build_map(points), # 	Construit la carte avec un point pour chaque compteur ayant des coordonnées valides dans la sélection
                key=map_key, #	Identifie cette carte dans Streamlit. C’est cette clé que select_marker() utilise pour lire les informations du clic
                height=460, # Donne à la carte une hauteur de 460 pixels.
                use_container_width=True, # Utilise la largeur disponible dans la colonne.
                returned_objects=["last_object_clicked_tooltip", "last_object_clicked_count"], # Demande au composant de transmettre le texte du point cliqué et le compteur de clics. Ce nombre change même si tu recliques sur le même point
                on_change=select_marker, # ker	Confie à st_folium la fonction à appeler lorsque ces informations changent. On écrit select_marker sans parenthèses pour lui passer la fonction à exécuter plus tard
            )
            # sous la carte affiche la légende des points turquoise et gris
            st.caption("Turquoise : historique chargé | Gris : aucun historique chargé")
    
    with selection_panel:
        selected = st.selectbox(
            "Compteur", # "Compteur" est le titre de la liste
            visible.index.tolist(), # fournit les options. Comme counter_id est l’index du tableau, ces options sont les identifiants comme "DEMO-01"
            format_func=visible.label.__getitem__, # dit à Streamlit quoi afficher pour chaque identifiant
            key=selection_key, # relie la liste à la valeur enregistrée par select_marker()
        )
        counter = visible.loc[selected]
        st.write(f"**Site** · {counter.site_name or 'Non renseigné'}")
        st.write(f"**Sens** · {counter.direction or 'Non renseigné'}")
        # st.write(f"**Statut E1** · {counter.status}")
        
        if pd.notna(counter.status_reason) and counter.status_reason:
            st.caption(counter.status_reason)
        if not counter.located:
            st.caption("Coordonnées indisponibles pour ce compteur.")
        st.caption("Tu peux aussi sélectionner un compteur en cliquant sur son point.")

    _render_history(data[1], selected)
    return selected


# Charge les données depuis les CSV de l’équipe 1 ou depuis la démo.
# Applique le filtre et affiche la liste des compteurs. Ceux qui ont des coordonnées apparaissent aussi sur la carte.
# Récupère l’identifiant du compteur choisi, que tu cliques sur la carte ou que tu le sélectionnes dans la liste.
# Affiche sa fiche et son historique, puis renvoie son identifiant pour que le reste de l’application puisse demander les prévisions.
"""
Point d'entrée de l'application ParisPulse
"""

import streamlit as st

from src.app.counter_map import render_counter_explorer


def main() -> None:
    # Configuration de la page (ParisPulse comme nom de l'onglet et wide => mise en page large donc plus de place à la carte au panneau de selection)
    st.set_page_config(page_title="ParisPulse", layout="wide")
    # le titre de la page 
    st.title("ParisPulse")
    # affiche la phrase d’introduction sous le titre en markdown
    st.markdown("Explore les compteurs et les passages cyclables à Paris")
    # afficher la carte et construit l'interface des compteurs en gérant la sélection et en affichant l'historique
    # Elle renvoit l'id du compteur selectionné mais ici on le stock pas 
    # on le stockera quand on fera les prévisions  pour savoir à quelle compteur on affichera les prévisions
    render_counter_explorer()


if __name__ == "__main__":
    main()
# uv run --locked --no-dev python -m streamlit run src/app/streamlit_app.py
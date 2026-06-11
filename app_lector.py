import streamlit as st
from pymongo import MongoClient
import re

# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────
def extraer_contexto(texto, palabra, window=60):
    pattern = re.compile(rf"(.{{0,{window}}}{re.escape(palabra)}.{{0,{window}}})", re.IGNORECASE)
    match = pattern.search(texto)
    return match.group(1) if match else texto[:2 * window]

def highlight_extra(text, word):
    pattern = re.compile(rf"({re.escape(word)})", re.IGNORECASE)
    style = (
        "background: linear-gradient(90deg, #fff3a3 0%, #ffe680 100%); "
        "padding: 2px 4px; "
        "border-radius: 4px; "
        "font-weight: 600;"
    )
    return pattern.sub(rf'<span style="{style}">\1</span>', text)

# ─────────────────────────────────────────
# MONGODB CONNECTION
# ─────────────────────────────────────────

uri = st.secrets["mongo"]["connection_string"]
client = MongoClient(uri)
db = client["ley_fintech_db"]
collection = db["pages"]

# ─────────────────────────────────────────
# UI
# ─────────────────────────────────────────
st.title("Lector-buscador de leyes en español")

# Book selector
book_options = {
    "Ley Fintech MX": "fintech_MX",
    "Disposiciones Generales de Crédito MX": "DispoGenCred_MX",
    "Ambos documentos": None
}

selected_label = st.selectbox("Selecciona el documento", options=list(book_options.keys()))
selected_book_id = book_options[selected_label]

query = st.text_input("Palabra o frase a buscar")

if query:
    # Build filter
    text_filter = {"$text": {"$search": query}}

    if selected_book_id is not None:
        text_filter["book_id"] = selected_book_id

    results = list(collection.find(text_filter))

    if not results:
        st.warning("No se encontraron resultados para tu búsqueda.")
    else:
        st.success(f"{len(results)} resultado(s) encontrado(s)")

        for r in results:
            contexto = extraer_contexto(r["text"], query)
            highlighted = highlight_extra(contexto, query)

            st.markdown(
                f"<h4>📄 {r['book_id']} — Página {r['page']}</h4>",
                unsafe_allow_html=True
            )
            st.markdown(highlighted, unsafe_allow_html=True)
            st.markdown("<hr>", unsafe_allow_html=True)

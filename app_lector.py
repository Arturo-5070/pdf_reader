%%writefile app_lector.py
import streamlit as st
from pymongo import MongoClient
import re
import unicodedata

# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

def remove_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def extraer_contexto(texto, palabra, window=60):
    texto_norm = remove_accents(texto)
    palabra_norm = remove_accents(palabra)
    pattern = re.compile(rf"(.{{0,{window}}}{re.escape(palabra_norm)}.{{0,{window}}})", re.IGNORECASE)
    match = pattern.search(texto_norm)
    if match:
        start, end = match.start(1), match.end(1)
        return texto[start:end]  # Return original text slice (with accents)
    return texto[:2 * window]

def highlight_extra(text, word):
    word_norm = remove_accents(word)

    # Build a pattern that matches both accented and unaccented versions
    pattern = re.compile(rf"({re.escape(word_norm)})", re.IGNORECASE)
    text_norm = remove_accents(text)

    style = (
        "background: linear-gradient(90deg, #fff3a3 0%, #ffe680 100%); "
        "padding: 2px 4px; "
        "border-radius: 4px; "
        "font-weight: 600;"
    )

    # Find matches in normalized text, apply highlights to original text
    result = []
    last = 0
    for match in pattern.finditer(text_norm):
        start, end = match.start(), match.end()
        result.append(text[last:start])  # Original text before match
        result.append(f'<span style="{style}">{text[start:end]}</span>')  # Original text of match
        last = end
    result.append(text[last:])  # Remaining original text

    return "".join(result)

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

book_options = {
    "Ley Fintech MX": "fintech_MX",
    "Disposiciones Generales de Crédito MX": "DispoGenCred_MX",
    "Ambos documentos": None
}

selected_label = st.selectbox("Selecciona el documento", options=list(book_options.keys()))
selected_book_id = book_options[selected_label]

query = st.text_input("Palabra o frase a buscar")

if query:
    text_filter = {"$text": {"$search": query}}

    if selected_book_id is not None:
        text_filter["book_id"] = selected_book_id

    # ── FIX: sort by page ascending ──
    results = list(collection.find(text_filter).sort("page", 1))

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


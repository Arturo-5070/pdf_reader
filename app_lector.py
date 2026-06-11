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

def extraer_contexto(texto, palabra, window=100):
    texto_norm = remove_accents(texto)
    palabra_norm = remove_accents(palabra)
    pattern = re.compile(rf"(.{{0,{window}}}{re.escape(palabra_norm)}.{{0,{window}}})", re.IGNORECASE)
    match = pattern.search(texto_norm)
    if match:
        start, end = match.start(1), match.end(1)
        return texto[start:end]
    return texto[:2 * window]

def highlight_extra(text, word):
    word_norm = remove_accents(word)
    pattern = re.compile(rf"({re.escape(word_norm)})", re.IGNORECASE)
    text_norm = remove_accents(text)

    style = (
        "background: linear-gradient(90deg, #807c6b 0%, #5e5011 100%); "
        "padding: 2px 4px; "
        "border-radius: 4px; "
        "font-weight: 600;"
    )

    result = []
    last = 0
    for match in pattern.finditer(text_norm):
        start, end = match.start(), match.end()
        result.append(text[last:start])
        result.append(f'<span style="{style}">{text[start:end]}</span>')
        last = end
    result.append(text[last:])

    return "".join(result)

# ─────────────────────────────────────────
# MONGODB CONNECTION
# ─────────────────────────────────────────
uri = st.secrets["mongo"]["connection_string"]
client = MongoClient(uri)
db = client["ley_fintech_db"]
collection = db["pages"]

# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
if "selected_page" not in st.session_state:
    st.session_state.selected_page = None
if "selected_book_id" not in st.session_state:
    st.session_state.selected_book_id = None

# ─────────────────────────────────────────
# FULL PAGE VIEW
# ─────────────────────────────────────────
if st.session_state.selected_page is not None:
    book = st.session_state.selected_book_id
    page = st.session_state.selected_page

    doc = collection.find_one({"book_id": book, "page": page}, {"text": 1, "_id": 0})

    st.markdown(f"### 📄 {book} — Página {page}")

    if doc:
        full_text = highlight_extra(doc["text"], st.session_state.get("last_query", ""))
        st.markdown(
            f"""
            <div style="
                background-color: #1e1e1e;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 20px;
                font-size: 15px;
                line-height: 1.8;
                text-align: justify;
            ">{full_text}</div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error("No se pudo cargar el texto de esta página.")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Volver a los resultados"):
        st.session_state.selected_page = None
        st.session_state.selected_book_id = None
        st.rerun()

# ─────────────────────────────────────────
# SEARCH VIEW
# ─────────────────────────────────────────
else:
    st.title("Buscador de palabras en disposiciones de la Comision Nacional Bancaria y de Valores")

    book_options = {
        "Disposiciones de carácter general aplicables a las instituciones de crédito (2026)": "DispoGenCred_MX",
        "Ley para Regular las Instituciones de Tecnología Financiera (2018)": "fintech_MX",
        "Ambos documentos": None
    }

    selected_label = st.selectbox("Selecciona el documento", options=list(book_options.keys()))
    selected_book_id = book_options[selected_label]

    query = st.text_input("Palabra o frase a buscar")

    if query:
        st.session_state.last_query = query

        text_filter = {"$text": {"$search": query}}
        if selected_book_id is not None:
            text_filter["book_id"] = selected_book_id

        results = list(collection.find(text_filter).sort("page", 1))

        if not results:
            st.warning("No se encontraron resultados para tu búsqueda.")
        else:
            st.success(f"{len(results)} resultado(s) encontrado(s)")

            for r in results:
                contexto = extraer_contexto(r["text"], query)
                highlighted = highlight_extra(contexto, query)

                col1, col2 = st.columns([5, 1])

                with col1:
                    st.markdown(
                        f"<b>📄 {r['book_id']} — Página {r['page']}</b>",
                        unsafe_allow_html=True
                    )
                    st.markdown(highlighted, unsafe_allow_html=True)

                with col2:
                    if st.button("Ver página", key=f"{r['book_id']}_{r['page']}"):
                        st.session_state.selected_page = r["page"]
                        st.session_state.selected_book_id = r["book_id"]
                        st.rerun()

                st.markdown("<hr>", unsafe_allow_html=True)

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
# CACHED MONGODB CONNECTION
# ─────────────────────────────────────────
@st.cache_resource
def get_collection():
    uri = st.secrets["mongo"]["connection_string"]
    client = MongoClient(uri)
    db = client["ley_fintech_db"]
    return db["pages"]

# ─────────────────────────────────────────
# CACHED QUERIES
# ─────────────────────────────────────────
@st.cache_data(ttl=300)
def search_pages(query, selected_book_id):
    collection = get_collection()
    text_filter = {"$text": {"$search": query}}
    if selected_book_id is not None:
        text_filter["book_id"] = selected_book_id
    return list(collection.find(text_filter, {"text": 1, "page": 1, "book_id": 1, "_id": 0}).sort("page", 1))

@st.cache_data(ttl=600)
def get_full_page(book_id, page):
    collection = get_collection()
    doc = collection.find_one({"book_id": book_id, "page": page}, {"text": 1, "_id": 0})
    return doc["text"] if doc else None

# ─────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────
if "selected_page" not in st.session_state:
    st.session_state.selected_page = None
if "selected_book_id" not in st.session_state:
    st.session_state.selected_book_id = None
if "last_query" not in st.session_state:
    st.session_state.last_query = ""

# ─────────────────────────────────────────
# FULL PAGE VIEW
# ─────────────────────────────────────────
if st.session_state.selected_page is not None:
    book = st.session_state.selected_book_id
    page = st.session_state.selected_page

    st.markdown(f"### 📄 {book} — Página {page}")

    full_text = get_full_page(book, page)

    if full_text:
        highlighted = highlight_extra(full_text, st.session_state.last_query)
        st.markdown(
            f"""
            <div style="
                border: 1px solid #444;
                border-radius: 8px;
                padding: 20px;
                font-size: 15px;
                line-height: 1.8;
                text-align: justify;
            ">{highlighted}</div>
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
    st.title("Buscador de palabras en publicaciones de la Comision Nacional Bancaria y de Valores")

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

        results = search_pages(query, selected_book_id)

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

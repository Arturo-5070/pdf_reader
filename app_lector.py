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
    if not word:
        return text

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

def format_breadcrumb(bc):
    """
    Build a single human-readable breadcrumb string from a structure dict,
    e.g. 'TÍTULO QUINTO > Capítulo XIV Bis > Sección Tercera'.
    Skips empty levels (Apartado/Subapartado are often blank).
    """
    if not bc:
        return ""

    parts = []
    if bc.get("titulo"):
        label = bc["titulo"]
        if bc.get("nombre_titulo"):
            label += f" ({bc['nombre_titulo']})"
        parts.append(label)
    if bc.get("capitulo"):
        label = bc["capitulo"]
        if bc.get("nombre_capitulo"):
            label += f" ({bc['nombre_capitulo']})"
        parts.append(label)
    if bc.get("seccion"):
        label = bc["seccion"]
        if bc.get("nombre_seccion"):
            label += f" ({bc['nombre_seccion']})"
        parts.append(label)
    if bc.get("apartado"):
        label = bc["apartado"]
        if bc.get("nombre_apartado"):
            label += f" ({bc['nombre_apartado']})"
        parts.append(label)
    if bc.get("subapartado"):
        label = bc["subapartado"]
        if bc.get("nombre_subapartado"):
            label += f" ({bc['nombre_subapartado']})"
        parts.append(label)

    return " &gt; ".join(parts)

def render_breadcrumbs(structure_list):
    """
    Render one or more breadcrumb trails for a page. A page can have
    multiple entries if more than one Seccion/Capitulo starts on it.
    """
    if not structure_list:
        return ""

    html_parts = []
    for bc in structure_list:
        crumb = format_breadcrumb(bc)
        if crumb:
            html_parts.append(
                f'<div style="font-size: 13px; opacity: 0.75; margin-bottom: 2px;">📍 {crumb}</div>'
            )
    return "".join(html_parts)

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
    return list(collection.find(
        text_filter,
        {"text": 1, "page": 1, "book_id": 1, "structure": 1, "_id": 0}
    ).sort("page", 1))

@st.cache_data(ttl=600)
def get_full_page(book_id, page):
    collection = get_collection()
    doc = collection.find_one(
        {"book_id": book_id, "page": page},
        {"text": 1, "structure": 1, "_id": 0}
    )
    return doc

@st.cache_data(ttl=600)
def get_page_bounds(book_id):
    """Return (min_page, max_page) for a given book_id, used for nav button limits."""
    collection = get_collection()
    first_doc = collection.find_one({"book_id": book_id}, {"page": 1}, sort=[("page", 1)])
    last_doc = collection.find_one({"book_id": book_id}, {"page": 1}, sort=[("page", -1)])
    min_page = first_doc["page"] if first_doc else None
    max_page = last_doc["page"] if last_doc else None
    return (min_page, max_page)

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

    doc = get_full_page(book, page)
    min_page, max_page = get_page_bounds(book)

    st.markdown(f"### 📄 {book} — Página {page}")

    if doc:
        breadcrumb_html = render_breadcrumbs(doc.get("structure"))
        if breadcrumb_html:
            st.markdown(breadcrumb_html, unsafe_allow_html=True)

        full_text = doc.get("text", "")
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

    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 2])

    with nav_col1:
        prev_disabled = (min_page is not None and page <= min_page)
        if st.button("← Página anterior", disabled=prev_disabled, use_container_width=True):
            st.session_state.selected_page = page - 1
            st.rerun()

    with nav_col2:
        next_disabled = (max_page is not None and page >= max_page)
        if st.button("Página siguiente →", disabled=next_disabled, use_container_width=True):
            st.session_state.selected_page = page + 1
            st.rerun()

    with nav_col3:
        if st.button("← Volver a los resultados"):
            st.session_state.selected_page = None
            st.session_state.selected_book_id = None
            st.rerun()

# ─────────────────────────────────────────
# SEARCH VIEW
# ─────────────────────────────────────────
else:
    st.title("Lector-buscador de leyes en español")

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
                    breadcrumb_html = render_breadcrumbs(r.get("structure"))
                    if breadcrumb_html:
                        st.markdown(breadcrumb_html, unsafe_allow_html=True)
                    st.markdown(highlighted, unsafe_allow_html=True)

                with col2:
                    if st.button("Ver página", key=f"{r['book_id']}_{r['page']}"):
                        st.session_state.selected_page = r["page"]
                        st.session_state.selected_book_id = r["book_id"]
                        st.rerun()

                st.markdown("<hr>", unsafe_allow_html=True)

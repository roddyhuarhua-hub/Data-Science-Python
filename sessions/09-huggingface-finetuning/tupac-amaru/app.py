"""Vista previa local (Streamlit) de la práctica sobre Túpac Amaru II.

Uso, desde esta carpeta:
    pip install streamlit pandas
    streamlit run app.py
Solo lee los CSV de data/; no publica nada.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import discurso  # noqa: E402

DATA = Path(__file__).parent / "data"
LA = DATA / "linea_a"

st.set_page_config(page_title="Túpac Amaru II · fuentes primarias", layout="wide")


@st.cache_data
def corpus() -> pd.DataFrame:
    return pd.read_csv(DATA / "tupac_amaru_corpus.csv")


@st.cache_data
def muestra() -> pd.DataFrame:
    return pd.read_csv(DATA / "clasificacion_muestra.csv")


def tabla(nombre: str, **kw) -> pd.DataFrame:
    return pd.read_csv(LA / nombre, **kw)


st.title("La rebelión de Túpac Amaru II")
st.caption("Corpus de fuentes primarias y análisis léxico · vista previa local")

tab_corpus, tab_lex, tab_clf, tab_dis = st.tabs(["Corpus", "Análisis léxico", "Clasificación", "Discurso"])

# ---------------------------------------------------------------- corpus
with tab_corpus:
    df = corpus()
    c1, c2, c3 = st.columns(3)
    c1.metric("Páginas", f"{len(df):,}")
    c2.metric("Documentos", df["documento"].nunique())
    c3.metric("Caracteres", f"{df['caracteres'].sum():,}")

    f1, f2 = st.columns(2)
    roles = f1.multiselect("Rol", sorted(df["rol"].unique()), default=["fuente_primaria"])
    docs = f2.multiselect("Documento", sorted(df["documento"].unique()))
    q = st.text_input("Buscar palabra o frase en el texto", placeholder="p. ej. cacique, visitador, Tinta")

    sel = df[df["rol"].isin(roles)] if roles else df
    if docs:
        sel = sel[sel["documento"].isin(docs)]
    if q:
        sel = sel[sel["texto_fuente"].fillna(sel["texto"]).str.contains(q, case=False, regex=False)]

    st.write(f"{len(sel):,} páginas")
    st.dataframe(
        sel[["documento", "pagina", "rol", "caracteres", "url"]],
        use_container_width=True,
        height=260,
        column_config={"url": st.column_config.LinkColumn("fuente original")},
    )
    if len(sel):
        i = st.number_input("Ver página (fila de la tabla)", 0, len(sel) - 1, 0)
        fila = sel.iloc[int(i)]
        st.markdown(f"**{fila['documento']}**, p. {fila['pagina']}  ·  [{fila['url']}]({fila['url']})")
        st.text_area("Texto", fila["texto_fuente"] if pd.notna(fila["texto_fuente"]) else fila["texto"], height=320)
        if pd.notna(fila["notas"]) and fila["notas"]:
            with st.expander("Notas al pie del editor"):
                st.text(fila["notas"])

# ---------------------------------------------------------------- léxico
with tab_lex:
    st.subheader("Cómo se nombra el hecho (por 10 000 palabras, según volumen)")
    des = tabla("designaciones_por_volumen.csv").set_index("término")
    st.line_chart(des.T)
    st.dataframe(des, use_container_width=True)

    a, b = st.columns(2)
    with a:
        st.subheader("Lugares más mencionados")
        lug = tabla("lugares_por_volumen.csv", index_col=0).sort_values("total", ascending=False)
        st.bar_chart(lug["total"].head(15))
    with b:
        st.subheader("Personas más mencionadas")
        per = tabla("personas_por_volumen.csv", index_col=0).sort_values("total", ascending=False)
        st.bar_chart(per["total"].head(15))

    a, b = st.columns(2)
    with a:
        st.subheader("Fechas citadas por mes")
        st.bar_chart(tabla("fechas_por_mes.csv", index_col=0)["fechas"])
    with b:
        st.subheader("Años citados por volumen")
        st.area_chart(tabla("anios_por_volumen.csv", index_col=0))

    with st.expander("Figuras originales del notebook"):
        for png in sorted(LA.glob("*.png")):
            st.image(str(png), caption=png.stem)

# ---------------------------------------------------------- clasificación
with tab_clf:
    m = muestra()
    st.write(f"Muestra de {len(m)} páginas clasificadas por tema y encuadre.")
    a, b = st.columns(2)
    a.subheader("Tema")
    a.bar_chart(m["tema_modelo"].value_counts())
    b.subheader("Encuadre")
    b.bar_chart(m["encuadre_modelo"].value_counts())

    t = st.multiselect("Filtrar por tema", sorted(m["tema_modelo"].dropna().unique()))
    e = st.multiselect("Filtrar por encuadre", sorted(m["encuadre_modelo"].dropna().unique()))
    v = m
    if t:
        v = v[v["tema_modelo"].isin(t)]
    if e:
        v = v[v["encuadre_modelo"].isin(e)]
    st.dataframe(
        v[["documento", "pagina", "tema_modelo", "tema_conf", "encuadre_modelo", "encuadre_conf",
           "n_rebelion", "n_revolucion", "url"]],
        use_container_width=True,
        column_config={"url": st.column_config.LinkColumn("fuente original")},
    )

# --------------------------------------------------------------- discurso
with tab_dis:
    st.subheader("Eje 1 · Designaciones y calificativos")
    st.caption(
        "Solo fuentes primarias (texto sin notas del editor ni encabezados corridos). "
        "Búsqueda sin tildes; 'ynga/inga' se agrupan en 'inca'."
    )

    @st.cache_data(show_spinner="Preparando corpus de fuentes primarias…")
    def primarias() -> pd.DataFrame:
        return discurso.cargar()

    @st.cache_data
    def frecuencias() -> pd.DataFrame:
        return discurso.frecuencia_por_volumen(primarias())

    @st.cache_data
    def rotulos() -> pd.DataFrame:
        return discurso.rotulos_actor(primarias())

    prim = primarias()
    plano = {n: p for ts in discurso.LEXICO.values() for n, p in ts.items()}
    termino = st.selectbox("Término", list(plano), index=list(plano).index("rebelde"))
    patron = plano[termino]

    freq = frecuencias()
    serie = freq[freq["termino"] == termino].set_index("volumen")["por_10k"]
    a, b = st.columns(2)
    a.markdown("**Frecuencia por 10 000 palabras, según volumen**")
    a.bar_chart(serie)
    rot = rotulos()
    r_t = rot[rot["termino"] == termino].set_index("volumen")["por_100_menciones"]
    b.markdown("**Junto al nombre de Túpac Amaru (por 100 menciones)**")
    b.bar_chart(r_t if len(r_t) else pd.Series(dtype=float))

    col = discurso.colocaciones(prim, patron, ventana=5, min_n=5, top=25)
    c1, c2 = st.columns([1, 2])
    c1.markdown("**Colocaciones (±5 palabras)**")
    c1.dataframe(col, use_container_width=True, height=420, hide_index=True)

    c2.markdown("**Concordancias**")
    vol = c2.selectbox("Volumen", ["todos"] + sorted(prim["volumen"].unique().tolist()))
    k = discurso.kwic(prim, patron, ancho=80, volumen=None if vol == "todos" else int(vol))
    c2.write(f"{len(k):,} ocurrencias")
    if len(k):
        n = c2.slider("Mostrar", 5, min(200, len(k)), min(25, len(k)))
        k = k.sample(n, random_state=0).sort_values(["volumen", "pagina"]) if len(k) > n else k
        k["contexto"] = k["izquierda"].str.rjust(80) + "  【" + k["termino"] + "】  " + k["derecha"]
        c2.dataframe(
            k[["volumen", "pagina", "contexto", "url"]],
            use_container_width=True,
            height=420,
            hide_index=True,
            column_config={"url": st.column_config.LinkColumn("fuente")},
        )

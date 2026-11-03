"""Dashboard: titulares de La República y El Comercio + clasificador BETO.

Correr desde la carpeta tarea_1:   streamlit run app.py

Pestaña 1 · Explorar: filtros en la barra lateral, métricas, gráficos, tabla y descarga.
Pestaña 2 · Clasificar: escribe un titular y pulsa el botón para ver la predicción.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Clasificador de titulares", page_icon="📰", layout="wide")

CARPETA = Path(__file__).parent
NOMBRES = {
    "politica": "Política",
    "economia": "Economía",
    "deportes": "Deportes",
    "ciencia_tecnologia": "Ciencia y tecnología",
    "otra": "Otra",
}


# ---------- Datos ----------
@st.cache_data
def cargar_datos():
    noticias = pd.read_csv(CARPETA / "datos" / "noticias.csv")
    etiquetas = pd.read_csv(CARPETA / "datos" / "etiquetas_llm.csv")
    # Del CSV del LLM solo traemos lo que no está en noticias.csv
    columnas_llm = [c for c in ["url", "etiqueta_llm", "confianza", "modelo_llm"] if c in etiquetas.columns]
    datos = noticias.merge(etiquetas[columnas_llm], on="url", how="left")
    if "confianza" not in datos.columns:
        datos["confianza"] = None
    datos["confianza"] = pd.to_numeric(datos["confianza"], errors="coerce")
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    datos["categoria"] = datos["etiqueta_llm"].map(NOMBRES).fillna("Sin etiqueta")
    datos["coincide_seccion"] = datos["etiqueta"] == datos["etiqueta_llm"]
    return datos


@st.cache_data
def cargar_metricas():
    ruta = CARPETA / "datos" / "metricas.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {}


@st.cache_resource
def cargar_modelo():
    # Se importa aquí para que la pestaña de datos abra rápido aunque no haya modelo
    from transformers import pipeline
    return pipeline("text-classification", model=str(CARPETA / "modelo"), top_k=None)


def hay_pesos_del_modelo():
    carpeta = CARPETA / "modelo"
    return any(carpeta.glob("*.safetensors")) or any(carpeta.glob("*.bin"))


datos = cargar_datos()
metricas = cargar_metricas()

# ---------- Barra lateral: filtros ----------
st.sidebar.title("📰 Filtros")

medios = sorted(datos["medio"].unique())
medios_elegidos = st.sidebar.multiselect("Medio", medios, default=medios)

categorias = [NOMBRES[c] for c in NOMBRES if NOMBRES[c] in set(datos["categoria"])]
categorias_elegidas = st.sidebar.multiselect("Categoría (etiqueta del LLM)", categorias, default=categorias)

fecha_min, fecha_max = datos["fecha"].min().date(), datos["fecha"].max().date()
rango = st.sidebar.date_input("Fecha de publicación", value=(fecha_min, fecha_max),
                              min_value=fecha_min, max_value=fecha_max)

hay_confianza = datos["confianza"].notna().any()
confianza_minima = 0.0
if hay_confianza:
    confianza_minima = st.sidebar.slider("Confianza mínima del LLM", 0.0, 1.0, 0.0, 0.05)

texto_buscado = st.sidebar.text_input("Buscar en el titular", placeholder="p. ej. Congreso")

st.sidebar.divider()
st.sidebar.caption(
    "Datos: feeds RSS de La República y El Comercio (13 y 14 de octubre de 2026). "
    "Etiquetas: Claude Haiku 5.5. Modelo: BETO ajustado."
)

# Aplicar filtros
filtro = datos["medio"].isin(medios_elegidos) & datos["categoria"].isin(categorias_elegidas)
if isinstance(rango, (list, tuple)) and len(rango) == 2:
    filtro &= datos["fecha"].dt.date.between(rango[0], rango[1])
if hay_confianza and confianza_minima > 0:
    filtro &= datos["confianza"] >= confianza_minima
if texto_buscado:
    filtro &= datos["titular"].str.contains(texto_buscado, case=False, na=False, regex=False)
filtrados = datos[filtro]

# ---------- Página ----------
st.title("Clasificador de titulares peruanos")
st.caption("¿Puede un modelo pequeño clasificar un titular en política, economía, deportes "
           "o ciencia/tecnología? Explora los datos y prueba el modelo.")

pestaña_datos, pestaña_modelo = st.tabs(["📊 Explorar titulares", "🤖 Clasificar un titular"])

with pestaña_datos:
    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Titulares filtrados", f"{len(filtrados):,}", f"de {len(datos):,} en total", delta_color="off")
    if len(filtrados) > 0:
        c2.metric("Coincidencia sección vs. LLM", f"{filtrados['coincide_seccion'].mean():.0%}")
    else:
        c2.metric("Coincidencia sección vs. LLM", "—")
    if hay_confianza and filtrados["confianza"].notna().any():
        c3.metric("Confianza media del LLM", f"{filtrados['confianza'].mean():.2f}")
    else:
        c3.metric("Confianza media del LLM", "—")
    if "f1_macro_finetuning" in metricas:
        c4.metric("F1 macro del modelo (prueba)", f"{metricas['f1_macro_finetuning']:.2f}",
                  f"{metricas['f1_macro_finetuning'] - metricas['f1_macro_zero_shot']:+.2f} vs. zero-shot")

    if len(filtrados) == 0:
        st.warning("Ningún titular cumple los filtros. Amplía la selección en la barra lateral.")
    else:
        # Gráficos
        g1, g2 = st.columns(2)
        conteo = filtrados.groupby(["categoria", "medio"]).size().reset_index(name="titulares")
        fig1 = px.bar(conteo, x="categoria", y="titulares", color="medio", barmode="group",
                      title="¿Qué cubre cada medio?",
                      labels={"categoria": "Categoría", "titulares": "Titulares", "medio": "Medio"})
        g1.plotly_chart(fig1, use_container_width=True)

        # "Otra" no existe como sección del diario, así que no entra en esta comparación
        acuerdo = (filtrados[filtrados["etiqueta_llm"] != "otra"].groupby(["categoria", "medio"])["coincide_seccion"].mean()
                   .mul(100).round(1).reset_index(name="coincidencia"))
        fig2 = px.bar(acuerdo, x="categoria", y="coincidencia", color="medio", barmode="group",
                      range_y=[0, 100], title="¿La sección del diario coincide con el LLM? (%)",
                      labels={"categoria": "Categoría", "coincidencia": "Coincidencia (%)", "medio": "Medio"})
        g2.plotly_chart(fig2, use_container_width=True)

        if hay_confianza and filtrados["confianza"].notna().any():
            fig3 = px.histogram(filtrados, x="confianza", color="medio", nbins=20, barmode="overlay",
                                title="¿Qué tan seguro estuvo el LLM de cada etiqueta?",
                                labels={"confianza": "Confianza del LLM (0 a 1)", "medio": "Medio"})
            fig3.update_yaxes(title="Titulares")
            st.plotly_chart(fig3, use_container_width=True)

        # Tabla y descarga
        st.subheader("Titulares")
        tabla = filtrados[["fecha", "medio", "titular", "categoria", "seccion_original", "confianza", "url"]]
        tabla = tabla.sort_values("fecha", ascending=False)
        st.dataframe(
            tabla, hide_index=True, use_container_width=True,
            column_config={
                "fecha": st.column_config.DateColumn("Fecha", format="YYYY-MM-DD"),
                "medio": "Medio",
                "titular": st.column_config.TextColumn("Titular", width="large"),
                "categoria": "Categoría (LLM)",
                "seccion_original": "Sección del diario",
                "confianza": st.column_config.NumberColumn("Confianza", format="%.2f"),
                "url": st.column_config.LinkColumn("Enlace", display_text="abrir"),
            },
        )
        st.download_button(
            "⬇️ Descargar estos titulares (CSV)",
            data=tabla.to_csv(index=False).encode("utf-8"),
            file_name="titulares_filtrados.csv",
            mime="text/csv",
        )

with pestaña_modelo:
    st.subheader("Prueba el clasificador")
    st.write("Escribe un titular y pulsa **Clasificar**. El modelo es BETO ajustado con los "
             f"{metricas.get('n_entrenamiento', 382)} titulares de entrenamiento.")

    with st.form("prediccion"):
        titular = st.text_area("Titular", placeholder="Ej.: BCR mantiene la tasa de referencia en 4.25 %",
                               height=80)
        boton = st.form_submit_button("Clasificar", type="primary")

    if boton:
        if not titular.strip():
            st.warning("Escribe un titular primero.")
        elif not hay_pesos_del_modelo():
            st.error("No están los pesos del modelo en `modelo/` (no se suben a GitHub por su tamaño). "
                     "Corre el notebook 02 para entrenarlo y vuelve a intentar.")
        else:
            with st.spinner("Clasificando..."):
                resultados = cargar_modelo()(titular.strip())[0]
            probabilidades = pd.DataFrame(resultados)
            probabilidades["categoria"] = probabilidades["label"].map(NOMBRES)
            probabilidades = probabilidades.sort_values("score", ascending=False)
            ganadora = probabilidades.iloc[0]

            st.success(f"**{ganadora['categoria']}** · probabilidad {ganadora['score']:.0%}")
            fig = px.bar(probabilidades, x="score", y="categoria", orientation="h",
                         range_x=[0, 1], title="Probabilidad por categoría",
                         labels={"score": "Probabilidad", "categoria": ""})
            fig.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig, use_container_width=True)

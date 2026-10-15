"""Dashboard: clasifica un titular peruano en cuatro categorías.

Correr con:  streamlit run app.py

El modelo se carga de la carpeta local `modelo/`. En Streamlit Cloud los pesos
no están en el repositorio (superan los 100 MB de GitHub), así que se leen de
Hugging Face Hub: basta definir el secreto MODELO_ID = "usuario/nombre-del-modelo".
"""
import streamlit as st
from transformers import pipeline

st.title("Clasificador de titulares peruanos")
st.write("Escribe un titular y el modelo dirá a qué sección pertenece.")


def ruta_del_modelo():
    # Con secreto definido se usa el repositorio de Hugging Face; si no, la carpeta local
    try:
        return st.secrets["MODELO_ID"]
    except Exception:
        return "modelo"


# Cargar el modelo toma segundos; con cache solo se hace una vez
@st.cache_resource
def cargar_modelo():
    return pipeline("text-classification", model=ruta_del_modelo(), top_k=None)


clasificador = cargar_modelo()

titular = st.text_input("Titular")

if titular:
    resultados = clasificador(titular)[0]
    st.subheader("Probabilidad por categoría")
    for resultado in sorted(resultados, key=lambda r: r["score"], reverse=True):
        st.write(resultado["label"], round(resultado["score"], 3))
        st.progress(resultado["score"])

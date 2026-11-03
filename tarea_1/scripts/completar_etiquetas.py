"""Completa datos/etiquetas_llm.csv con las columnas que pide la rúbrica.

Columnas finales: url, titular, etiqueta_llm, confianza, modelo_llm, fecha

- titular:     se copia de datos/noticias.csv (misma URL).
- modelo_llm:  el modelo que puso la etiqueta (claude-haiku-5-5, ver BITACORA D6).
- fecha:       día en que se etiquetó la nota. Para las 562 notas originales sale del
               historial de git (commit en el que la URL entró al CSV), ver BITACORA D13.
- confianza:   número de 0 a 1. Se le muestra al LLM la noticia y la etiqueta que YA
               tiene, y se le pregunta qué tan seguro está de que es la correcta.
               La etiqueta NO se cambia: así el split y el F1 (0.93) quedan iguales.

Correr desde la carpeta tarea_1:   python scripts/completar_etiquetas.py
Necesita ANTHROPIC_API_KEY en tarea_1/.env. Si se corta, se vuelve a correr y
solo pide la confianza de las filas que aún no la tienen.
"""
import re
import time
from pathlib import Path

import pandas as pd

RUTA_ETIQUETAS = Path("datos/etiquetas_llm.csv")
RUTA_NOTICIAS = Path("datos/noticias.csv")
MODELO_LLM = "claude-haiku-5-5"
COLUMNAS = ["url", "titular", "etiqueta_llm", "confianza", "modelo_llm", "fecha"]

# Fecha de etiquetado según el historial de git: cuántas filas tenía el CSV
# después de cada commit que lo modificó (las filas nuevas se agregan al final).
#   1e1cc78 (13 oct): filas 1-240  | f3f2790 (13 oct): 241-274
#   621a108 (14 oct): 275-399      | 506d9a9 (14 oct): 400-562
CORTES_DE_FECHA = [(240, "2026-10-13"), (274, "2026-10-13"), (399, "2026-10-14"), (562, "2026-10-14")]

INSTRUCCIONES = (
    "Eres un editor de un diario peruano. Las categorias posibles son:\n"
    "- politica: gobierno, Congreso, partidos, elecciones, justicia y autoridades\n"
    "- economia: precios, empleo, empresas, finanzas, comercio, dolar, inflacion\n"
    "- deportes: futbol y cualquier otro deporte, torneos, deportistas\n"
    "- ciencia_tecnologia: ciencia, tecnologia, salud, medio ambiente, innovacion\n"
    "- otra: si no encaja con claridad en ninguna de las cuatro\n"
    "Te doy una noticia y la categoria que se le asigno. Responde SOLO con un numero "
    "entre 0 y 1 que diga que tan seguro estas de que esa categoria es la correcta "
    "(1 = totalmente seguro, 0 = seguro de que es incorrecta). Sin explicacion."
)


def fecha_por_posicion(posicion):
    """posicion empieza en 1 (primera fila de datos)."""
    for limite, fecha in CORTES_DE_FECHA:
        if posicion <= limite:
            return fecha
    return pd.Timestamp.today().strftime("%Y-%m-%d")   # filas nuevas: hoy


def leer_numero(texto):
    """Saca el primer número de la respuesta; '0,85' también vale."""
    encontrado = re.search(r"\d+(?:[.,]\d+)?", texto)
    if encontrado is None:
        return None
    numero = float(encontrado.group().replace(",", "."))
    if numero > 1 and numero <= 100:      # por si responde en porcentaje
        numero = numero / 100
    if 0 <= numero <= 1:
        return round(numero, 2)
    return None


def pedir_confianza(cliente, titular, bajada, etiqueta):
    texto = f"Titular: {titular}\nBajada: {bajada}\nCategoria asignada: {etiqueta}"
    for intento in range(2):               # un solo reintento, como en el notebook 02
        try:
            respuesta = cliente.messages.create(
                model=MODELO_LLM,
                max_tokens=300,
                system=INSTRUCCIONES,
                messages=[{"role": "user", "content": texto}],
            )
            texto_respuesta = ""
            for bloque in respuesta.content:
                if bloque.type == "text":
                    texto_respuesta = bloque.text
            return leer_numero(texto_respuesta)
        except Exception as error:         # errores de red o de la API
            print("  reintento por:", type(error).__name__)
            time.sleep(2)
    return None


def main():
    etiquetas = pd.read_csv(RUTA_ETIQUETAS)
    noticias = pd.read_csv(RUTA_NOTICIAS)
    noticias["bajada"] = noticias["bajada"].fillna("")

    # 1. Columnas que no necesitan al LLM
    titulares = noticias.set_index("url")["titular"]
    bajadas = noticias.set_index("url")["bajada"]
    etiquetas["titular"] = etiquetas["url"].map(titulares)
    if "modelo_llm" not in etiquetas.columns:
        etiquetas["modelo_llm"] = MODELO_LLM
    etiquetas["modelo_llm"] = etiquetas["modelo_llm"].fillna(MODELO_LLM)
    if "fecha" not in etiquetas.columns:
        etiquetas["fecha"] = None
    for posicion, indice in enumerate(etiquetas.index, start=1):
        if pd.isna(etiquetas.at[indice, "fecha"]):
            etiquetas.at[indice, "fecha"] = fecha_por_posicion(posicion)
    if "confianza" not in etiquetas.columns:
        etiquetas["confianza"] = None

    # 2. Confianza: solo las filas que aún no la tienen
    pendientes = etiquetas[etiquetas["confianza"].isna()].index
    print("Filas:", len(etiquetas), "| sin confianza:", len(pendientes))

    if len(pendientes) > 0:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
        cliente = anthropic.Anthropic()

        for numero, indice in enumerate(pendientes, start=1):
            fila = etiquetas.loc[indice]
            etiquetas.at[indice, "confianza"] = pedir_confianza(
                cliente, fila["titular"], bajadas.get(fila["url"], ""), fila["etiqueta_llm"])
            if numero % 25 == 0:           # guardar avance cada 25 filas
                etiquetas[COLUMNAS].to_csv(RUTA_ETIQUETAS, index=False, encoding="utf-8")
                print(f"  {numero} de {len(pendientes)}")

    etiquetas[COLUMNAS].to_csv(RUTA_ETIQUETAS, index=False, encoding="utf-8")
    print("Listo. Confianza media:", round(etiquetas["confianza"].astype(float).mean(), 3),
          "| filas sin confianza:", int(etiquetas["confianza"].isna().sum()))


if __name__ == "__main__":
    main()

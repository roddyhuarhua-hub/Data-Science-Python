"""Limpieza y transformación de la base de casos de la Defensoría del Pueblo.

Entrada:  datos/originales/defensoria_casos_por_mes_2015_2026.csv  (N.° 131 a 247)
          datos/procesados/casos_2024_10_a_2026_09.csv            (N.° 248 a 271)
Salidas:  datos/procesados/casos_limpios.csv   (una fila por caso y por mes)
          datos/procesados/panel_mensual.csv   (conteos por mes, departamento,
                                                tipo, actividad y estado)

Uso (desde la carpeta tarea_3):  python scripts/procesar_datos.py
"""
from pathlib import Path
import re

import pandas as pd

from actividad import clasificar

BASE = Path(__file__).resolve().parents[1]
ORIGEN = BASE / "datos" / "originales" / "defensoria_casos_por_mes_2015_2026.csv"
# Reextracción de oct 2024 (N.° 248) a set 2026 (N.° 271) con scripts/completar_2024_2026.py:
# en la base original la tabla de activos "sin hechos" de esos meses repetía textos de otros casos.
COMPLEMENTO = BASE / "datos" / "procesados" / "casos_2024_10_a_2026_09.csv"
DESDE_COMPLEMENTO = 248
DESTINO = BASE / "datos" / "procesados"

# Código INEI de departamento (2 dígitos) -> nombre con tildes
DEPARTAMENTOS = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
    "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
    "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
    "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali",
}

# Frase que la lectura automática del PDF a veces mete en medio de la descripción
FRASE_SIN_HECHOS = re.compile(r"\s*No se registraron (nuevos hechos durante el mes\.?)?", re.I)


def limpiar_texto(texto):
    if pd.isna(texto):
        return ""
    texto = FRASE_SIN_HECHOS.sub(" ", str(texto))
    return re.sub(r"\s+", " ", texto).strip()


def main():
    original = pd.read_csv(ORIGEN, dtype=str)
    complemento = pd.read_csv(COMPLEMENTO, dtype=str)
    original = original[original["reporte_n"].astype(int) < DESDE_COMPLEMENTO]
    df = pd.concat([original, complemento], ignore_index=True)
    n_inicial = len(df)

    # 1. Tipos de dato
    for col in ["reporte_n", "anio", "mes"]:
        df[col] = df[col].astype(int)
    df["periodo"] = df["anio"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2)

    # 2. Texto del caso limpio
    df["caso"] = df["caso"].map(limpiar_texto)

    # 3. Duplicados exactos dentro del mismo reporte (la extracción a veces repite la ficha).
    #    Solo cuentan como duplicado las filas con una descripción real del caso: desde 2024
    #    muchos activos "sin hechos" traen solo el tipo ("Socioambiental") como texto, y
    #    esas filas son casos distintos aunque el texto coincida.
    clave = ["reporte_n", "estado", "caso", "ubicacion", "departamento", "ubigeo"]
    repetida = df.duplicated(clave) & (df["caso"].str.len() >= 40)
    duplicados = int(repetida.sum())
    df = df[~repetida]

    # 4. Departamento normalizado a partir del ubigeo (el texto original viene en
    #    mayúsculas/minúsculas mezcladas y a veces pegado con otras palabras)
    df["cod_dep"] = df["ubigeo"].str[:2]
    df["dep"] = df["cod_dep"].map(DEPARTAMENTOS)
    multi = df["departamento"].fillna("").str.contains("nacional|multirregional|multiregional", case=False)
    df.loc[df["dep"].isna() & multi, "dep"] = "Nacional / multirregional"
    df["dep"] = df["dep"].fillna("Sin ubicación")
    df.loc[df["dep"].isin(["Nacional / multirregional", "Sin ubicación"]), "cod_dep"] = ""

    # 5. Tipo de conflicto
    df["tipo"] = df["tipo_conflicto"].fillna("Sin tipo")
    df["socioambiental"] = df["tipo"].eq("Socioambiental")

    # 6. Actividad (solo para socioambientales), por palabras clave en la descripción
    df["actividad"] = ""
    df.loc[df["socioambiental"], "actividad"] = df.loc[df["socioambiental"], "caso"].map(clasificar)

    # 7. Diálogo: la Defensoría solo informa si hay diálogo en los casos activos.
    #    Desde mediados de 2024 los casos "sin hechos nuevos" ya no traen el dato,
    #    así que el indicador se calcula sobre casos activos con hechos en el mes.
    df["con_hechos"] = df["estado"].eq("activo") & df["sin_hechos_en_mes"].eq("False")
    df["dialogo"] = df["hay_dialogo"].fillna("sd")
    df.loc[df["estado"].eq("latente"), "dialogo"] = "na"

    columnas = ["reporte_n", "anio", "mes", "periodo", "estado", "caso", "cod_dep", "dep",
                "provincia", "distrito", "ubigeo", "nivel_ubicacion", "tipo", "socioambiental",
                "actividad", "con_hechos", "dialogo", "url_reporte"]
    df = df[columnas].sort_values(["periodo", "estado", "dep"])

    DESTINO.mkdir(parents=True, exist_ok=True)
    df.to_csv(DESTINO / "casos_limpios.csv", index=False, encoding="utf-8")

    panel = (df.groupby(["periodo", "anio", "mes", "cod_dep", "dep", "tipo", "actividad",
                         "estado", "con_hechos", "dialogo"], dropna=False)
               .size().rename("casos").reset_index())
    panel.to_csv(DESTINO / "panel_mensual.csv", index=False, encoding="utf-8")

    print(f"Filas originales: {n_inicial:,}")
    print(f"Duplicados eliminados: {duplicados:,}")
    print(f"Filas limpias: {len(df):,}  |  meses: {df['periodo'].nunique()}  "
          f"({df['periodo'].min()} a {df['periodo'].max()})")
    print("Actividad de los socioambientales:")
    print(df.loc[df["socioambiental"], "actividad"].value_counts(normalize=True).round(3).to_string())


if __name__ == "__main__":
    main()

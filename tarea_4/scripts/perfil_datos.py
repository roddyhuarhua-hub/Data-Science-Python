"""Convierte los xlsx originales del OEFA a CSV UTF-8 y escribe datos/perfil_datos.md.

Uso (desde tarea_4/): uv run --no-project --with pandas --with openpyxl python scripts/perfil_datos.py
"""

import csv
from pathlib import Path

import pandas as pd

DATOS = Path(__file__).resolve().parent.parent / "datos"
NO_PERFILAR = {"catalogo_oefa_crudo.csv"}


def convertir_originales() -> None:
    for xlsx in sorted((DATOS / "originales").glob("*.xlsx")):
        hojas = pd.read_excel(xlsx, sheet_name=None, dtype=str)
        hojas = {n: h.dropna(how="all") for n, h in hojas.items() if not h.dropna(how="all").empty}
        for nombre, hoja in hojas.items():
            sufijo = "" if len(hojas) == 1 else f"__{nombre.strip().replace(' ', '_')}"
            destino = DATOS / f"{xlsx.stem}{sufijo}.csv"
            hoja.to_csv(destino, index=False, encoding="utf-8")
            print(f"{xlsx.name} [{nombre}] -> {destino.name}: {len(hoja)} filas")


def codificacion(ruta: Path) -> str:
    crudo = ruta.read_bytes()
    for cod in ("utf-8-sig", "utf-8"):
        try:
            crudo.decode(cod)
            return "UTF-8 con BOM" if crudo.startswith(b"\xef\xbb\xbf") else "UTF-8"
        except UnicodeDecodeError:
            pass
    return "cp1252 / latin-1"


def rango_fechas(df: pd.DataFrame) -> list[str]:
    salida = []
    for col in df.columns:
        if "FECHA" not in col.upper() and "DATE" not in col.upper():
            continue
        valores = df[col].dropna().astype(str).str.strip()
        if valores.empty:
            continue
        # el xlsx trae fechas ISO; la API de Junar usa m/d/aa o m/d/aaaa
        fechas = pd.to_datetime(valores, errors="coerce", format="ISO8601")
        if fechas.notna().mean() < 0.5:
            fechas = pd.to_datetime(valores, errors="coerce", format="mixed", dayfirst=False)
        validas = fechas.dropna()
        if validas.empty:
            continue
        salida.append(f"`{col}`: {validas.min().date()} a {validas.max().date()} "
                      f"({len(validas):,} válidas de {len(valores):,})")
    return salida


def perfilar(ruta: Path) -> str:
    cod = codificacion(ruta)
    texto = ruta.read_text(encoding="utf-8-sig" if cod.startswith("UTF") else "cp1252")
    sep = csv.Sniffer().sniff(texto[:20000], delimiters=",;\t|").delimiter
    df = pd.read_csv(ruta, sep=sep, dtype=str, encoding="utf-8-sig" if cod.startswith("UTF") else "cp1252")
    nombre_sep = {",": "coma (,)", ";": "punto y coma (;)", "\t": "tabulador", "|": "barra (|)"}[sep]
    muestra = df.head(3).fillna("").to_markdown(index=False) if hasattr(df, "to_markdown") else ""
    lineas = [
        f"### `{ruta.relative_to(DATOS).as_posix()}`",
        "",
        f"- Tamaño: {ruta.stat().st_size / 1024:,.0f} KB",
        f"- Codificación: {cod} · Separador: {nombre_sep}",
        f"- Filas: {len(df):,} · Columnas: {df.shape[1]}",
        f"- Columnas: {', '.join(f'`{c}`' for c in df.columns)}",
    ]
    fechas = rango_fechas(df)
    lineas.append("- Rango de fechas: " + ("; ".join(fechas) if fechas else "sin columna de fecha"))
    lineas += ["", "Tres filas de ejemplo:", "", muestra, ""]
    return "\n".join(lineas)


def main() -> None:
    convertir_originales()
    rutas = sorted(p for p in DATOS.glob("*.csv") if p.name not in NO_PERFILAR)
    partes = [
        "# Perfil de los datos del OEFA",
        "",
        "Generado con `scripts/perfil_datos.py`. Cada CSV lleva la clave que usa `server.py` y sale del xlsx "
        "original de su dataset (`datos/originales/`), porque `data.csv` de la API devuelve solo 999 filas "
        "sin parámetros y 10,000 como máximo. Las fechas del xlsx vienen en ISO; las de la API, como m/d/aa. "
        "El xlsx de «Informes de la Dirección de Supervisión 2018» trae en realidad informes de 2019 a 2024, "
        "así que el servidor no lo usa.",
        "",
    ]
    partes += [perfilar(r) for r in rutas]
    (DATOS / "perfil_datos.md").write_text("\n".join(partes), encoding="utf-8")
    print(f"perfil -> {DATOS / 'perfil_datos.md'}")


if __name__ == "__main__":
    main()

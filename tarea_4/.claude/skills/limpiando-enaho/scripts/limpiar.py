"""Limpia la ENAHO del INEI y arma una base de personas con pobreza.

Uso (desde la raíz del repositorio):
    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024

Entra:  datos/966-Modulo34.zip (sumaria) y datos/966-Modulo02.zip (miembros)
Sale:   salidas/personas_2024.parquet, salidas/validacion.txt y salidas/indicadores.csv

El pipeline siempre sigue los mismos siete pasos:
    1 Leer · 2 Normalizar · 3 Filtrar · 4 Unir · 5 Construir · 6 Validar · 7 Guardar
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

# Código de cada año en el portal de microdatos del INEI.
CODIGOS_INEI = {2024: 966}

# Cifras oficiales para validar. Fuente: INEI, ENAHO 2024 (README de la sesión 16).
OFICIAL = {
    2024: {
        "hogares": 33_691,
        "filas_modulo_02": 117_721,
        "residentes": 108_664,
        "pobreza": 27.6,
        "pobreza_extrema": 5.5,
        "urbano": 24.8,
        "rural": 39.3,
    }
}
TOLERANCIA = 0.1  # puntos porcentuales

LLAVES_HOGAR = ["conglome", "vivienda", "hogar"]
LLAVES_PERSONA = LLAVES_HOGAR + ["codperso"]
# Largo de cada código: así se recuperan los ceros a la izquierda.
ANCHO = {"conglome": 6, "vivienda": 3, "hogar": 2, "codperso": 2, "ubigeo": 6}

VARS_SUMARIA = LLAVES_HOGAR + [
    "anio", "ubigeo", "dominio", "estrato", "pobreza", "mieperho", "factor07",
]
VARS_PERSONAS = LLAVES_PERSONA + [
    "p203", "p204", "p205", "p206", "p207", "p208a", "facpob07",
]

RAIZ = Path.cwd()


# ---------------------------------------------------------------- 1 · Leer
def buscar_dta(zip_o_carpeta: Path, patron: str) -> tuple[Path, str | None]:
    """Devuelve (zip, nombre interno) o (archivo .dta, None)."""
    if zip_o_carpeta.suffix == ".zip" and zip_o_carpeta.exists():
        with zipfile.ZipFile(zip_o_carpeta) as z:
            nombres = [n for n in z.namelist()
                       if n.lower().endswith(".dta") and patron in Path(n).name.lower()]
        if not nombres:
            sys.exit(f"ERROR: {zip_o_carpeta} no tiene un .dta con '{patron}'")
        # Si hay varios, el de nombre más corto es el principal (sumaria-2024.dta, no sumaria-2024-12g.dta).
        return zip_o_carpeta, min(nombres, key=lambda n: len(Path(n).name))
    sueltos = sorted(p for p in (RAIZ / "datos").rglob("*.dta") if patron in p.name.lower())
    if sueltos:
        return min(sueltos, key=lambda p: len(p.name)), None
    sys.exit(
        f"ERROR: falta {zip_o_carpeta.name}. Bájalo del INEI y ponlo en datos/:\n"
        f"  https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/{zip_o_carpeta.name}"
    )


def leer_stata(origen: Path, interno: str | None) -> pd.DataFrame:
    if interno is None:
        return pd.read_stata(origen, convert_categoricals=False)
    with zipfile.ZipFile(origen) as z, z.open(interno) as f:
        return pd.read_stata(f, convert_categoricals=False)


# ---------------------------------------------------------- 2 · Normalizar
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Minúsculas y sin tildes: «aÑo» pasa a «anio»."""
    def limpio(c: str) -> str:
        c = str(c).strip().lower()
        c = c.replace("ñ", "ni")
        c = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode()
        return c
    df = df.rename(columns=limpio)
    return df


def llaves_como_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Llaves y ubigeo como texto, con sus ceros a la izquierda."""
    for col, ancho in ANCHO.items():
        if col not in df.columns:
            continue
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            s = s.astype("Int64").astype(str)
        df[col] = s.astype(str).str.strip().str.zfill(ancho)
    return df


def numerico(df: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    for c in columnas:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def ponderado(valor: pd.Series, peso: pd.Series) -> float:
    m = valor.notna() & peso.notna()
    return float((valor[m] * peso[m]).sum() / peso[m].sum() * 100)


NOMBRES_DEP = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
    "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
    "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
    "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali",
}


def indicadores(base: pd.DataFrame, anio: int) -> pd.DataFrame:
    """Pobreza monetaria y extrema ponderadas con facpob07: nacional, área, sexo y departamento."""
    filas = []
    grupos = [("nacional", None), ("area", "area"), ("sexo", "sexo"), ("departamento", "departamento")]
    for nivel, col in grupos:
        partes = [("Perú", base)] if col is None else list(base.groupby(col, observed=True))
        for valor, g in partes:
            filas.append({
                "anio": anio, "nivel": nivel,
                "codigo": valor if nivel == "departamento" else "",
                "grupo": NOMBRES_DEP.get(valor, valor) if nivel == "departamento" else valor,
                "pobreza_pct": ponderado(g["pobre"].astype(float), g["facpob07"]),
                "pobreza_extrema_pct": ponderado(g["pobre_extremo"].astype(float), g["facpob07"]),
                "poblacion_expandida": round(float(g["facpob07"].sum())),
                "encuestados": len(g),
            })
    return pd.DataFrame(filas)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anio", type=int, default=2024)
    args = ap.parse_args()
    anio = args.anio
    if anio not in CODIGOS_INEI:
        sys.exit(f"ERROR: año {anio} sin código INEI conocido. Agrega su código en CODIGOS_INEI.")
    codigo = CODIGOS_INEI[anio]
    datos = RAIZ / "datos"

    print(f"1 · Leer ENAHO {anio} (código INEI {codigo})")
    sumaria = leer_stata(*buscar_dta(datos / f"{codigo}-Modulo34.zip", f"sumaria-{anio}"))
    miembros = leer_stata(*buscar_dta(datos / f"{codigo}-Modulo02.zip", f"enaho01-{anio}-200"))
    filas_02 = len(miembros)
    print(f"  sumaria: {len(sumaria):,} filas · miembros: {filas_02:,} filas")

    print("2 · Normalizar nombres y llaves")
    sumaria = llaves_como_texto(normalizar_columnas(sumaria))
    miembros = llaves_como_texto(normalizar_columnas(miembros))
    faltan = [c for c in VARS_SUMARIA if c not in sumaria.columns] + \
             [c for c in VARS_PERSONAS if c not in miembros.columns]
    if faltan:
        sys.exit(f"ERROR: faltan columnas {faltan}. Revisa el diccionario del INEI.")
    sumaria = numerico(sumaria[VARS_SUMARIA].copy(),
                       ["dominio", "estrato", "pobreza", "mieperho", "factor07"])
    miembros = numerico(miembros[VARS_PERSONAS].copy(),
                        ["p203", "p204", "p205", "p206", "p207", "p208a", "facpob07"])

    print("3 · Filtrar residentes habituales")
    residente = ((miembros.p204 == 1) & (miembros.p205 == 2)) | \
                ((miembros.p204 == 2) & (miembros.p206 == 1))
    personas = miembros[residente].copy()
    print(f"  {len(personas):,} residentes de {filas_02:,} filas")

    print("4 · Unir personas y hogares (validate='m:1')")
    llaves_hogar_unicas = not sumaria.duplicated(LLAVES_HOGAR).any()
    llaves_persona_unicas = not personas.duplicated(LLAVES_PERSONA).any()
    base = personas.merge(sumaria, on=LLAVES_HOGAR, how="left",
                          validate="m:1", indicator=True)
    sin_hogar = int((base["_merge"] != "both").sum())
    base = base.drop(columns="_merge")

    print("5 · Construir variables")
    base["departamento"] = base["ubigeo"].str[:2]
    base["urbano"] = base["estrato"] <= 5
    base["area"] = base["urbano"].map({True: "Urbana", False: "Rural"})
    base["pobre"] = base["pobreza"] <= 2              # 1 extremo + 2 no extremo
    base["pobre_extremo"] = base["pobreza"] == 1
    base["sexo"] = base["p207"].map({1: "Hombre", 2: "Mujer"})
    base["edad"] = base["p208a"]
    base["grupo_edad"] = pd.cut(
        base["edad"], bins=[-1, 13, 29, 44, 59, 200],
        labels=["0-13", "14-29", "30-44", "45-59", "60 y más"],
    ).astype(str)
    base["lima_metropolitana"] = base["dominio"] == 8

    print("6 · Validar")
    ref = OFICIAL.get(anio, {})
    peso_hogar = sumaria["factor07"] * sumaria["mieperho"]
    pob_sumaria = ponderado((sumaria["pobreza"] <= 2).astype(float), peso_hogar)
    ext_sumaria = ponderado((sumaria["pobreza"] == 1).astype(float), peso_hogar)
    pob_personas = ponderado(base["pobre"].astype(float), base["facpob07"])
    ext_personas = ponderado(base["pobre_extremo"].astype(float), base["facpob07"])
    urb = sumaria["estrato"] <= 5
    pob_urbano = ponderado((sumaria.loc[urb, "pobreza"] <= 2).astype(float), peso_hogar[urb])
    pob_rural = ponderado((sumaria.loc[~urb, "pobreza"] <= 2).astype(float), peso_hogar[~urb])
    poblacion = float(peso_hogar.sum())

    chequeos: list[tuple[str, bool, str]] = []

    def chequear(nombre: str, ok: bool, detalle: str) -> None:
        chequeos.append((nombre, bool(ok), detalle))

    chequear("Llaves de hogar únicas en la sumaria", llaves_hogar_unicas, ", ".join(LLAVES_HOGAR))
    chequear("Llaves de persona únicas", llaves_persona_unicas, ", ".join(LLAVES_PERSONA))
    chequear("La unión no perdió ni duplicó filas", len(base) == len(personas),
             f"{len(base):,} filas en la base = {len(personas):,} residentes")
    chequear("Todas las personas tienen hogar en la sumaria", sin_hogar == 0,
             f"{sin_hogar} personas sin hogar")
    chequear("Ubigeo con 6 dígitos", base["ubigeo"].str.len().eq(6).all(),
             f"{base['departamento'].nunique()} departamentos")
    chequear("25 códigos territoriales (Lima 15 y Callao 07 separados)",
             base["departamento"].nunique() == 25 and {"07", "15"} <= set(base["departamento"]),
             f"{base['departamento'].nunique()} códigos: {', '.join(sorted(base['departamento'].unique()))}")
    chequear("Factores de expansión completos y positivos",
             base["facpob07"].notna().all() and (base["facpob07"] > 0).all(),
             f"{int(base['facpob07'].isna().sum())} personas sin facpob07")
    if ref:
        chequear("Hogares en la sumaria", len(sumaria) == ref["hogares"],
                 f"{len(sumaria):,} (INEI: {ref['hogares']:,})")
        chequear("Filas del módulo 02", filas_02 == ref["filas_modulo_02"],
                 f"{filas_02:,} (INEI: {ref['filas_modulo_02']:,})")
        chequear("Residentes habituales", len(personas) == ref["residentes"],
                 f"{len(personas):,} (esperado: {ref['residentes']:,})")
        for nombre, valor, clave in [
            ("Pobreza monetaria, sumaria (factor07 × mieperho)", pob_sumaria, "pobreza"),
            ("Pobreza monetaria, personas (facpob07)", pob_personas, "pobreza"),
            ("Pobreza extrema, sumaria", ext_sumaria, "pobreza_extrema"),
            ("Pobreza urbana, sumaria", pob_urbano, "urbano"),
            ("Pobreza rural, sumaria", pob_rural, "rural"),
        ]:
            dif = valor - ref[clave]
            chequear(nombre, abs(dif) < TOLERANCIA,
                     f"{valor:.2f} % (INEI: {ref[clave]:.1f} %, diferencia {dif:+.2f})")

    todo_ok = all(ok for _, ok, _ in chequeos)
    lineas = [
        f"Validación ENAHO {anio} · limpiando-enaho",
        f"Archivos: {codigo}-Modulo34.zip (sumaria) y {codigo}-Modulo02.zip (miembros)",
        "",
        f"Hogares en la sumaria:       {len(sumaria):,}",
        f"Filas del módulo 02:         {filas_02:,}",
        f"Residentes habituales:       {len(personas):,}",
        f"Población expandida:         {poblacion:,.0f} personas",
        f"Pobreza monetaria (sumaria): {pob_sumaria:.2f} %",
        f"Pobreza monetaria (personas):{pob_personas:6.2f} %",
        f"Pobreza extrema (sumaria):   {ext_sumaria:.2f} %",
        f"Pobreza extrema (personas):  {ext_personas:.2f} %",
        f"Urbano / rural (sumaria):    {pob_urbano:.2f} % / {pob_rural:.2f} %",
        "",
        "Chequeos",
    ]
    for nombre, ok, detalle in chequeos:
        lineas.append(f"  [{'OK' if ok else 'FALLA'}] {nombre}: {detalle}")
    lineas += ["", "RESULTADO: " + ("TODO OK, la base replica al INEI" if todo_ok
                                     else "HAY FALLAS, no uses la base")]
    texto = "\n".join(lineas) + "\n"

    print("7 · Guardar")
    salidas = RAIZ / "salidas"
    salidas.mkdir(exist_ok=True)
    (salidas / "validacion.txt").write_text(texto, encoding="utf-8")
    if todo_ok:
        columnas = LLAVES_PERSONA + [
            "anio", "ubigeo", "departamento", "dominio", "lima_metropolitana", "estrato",
            "urbano", "area", "p203", "p207", "sexo", "p208a", "edad", "grupo_edad",
            "pobreza", "pobre", "pobre_extremo", "mieperho", "factor07", "facpob07",
        ]
        base[columnas].to_parquet(salidas / f"personas_{anio}.parquet", index=False)
        print(f"  salidas/personas_{anio}.parquet ({len(base):,} filas)")
        indicadores(base, anio).to_csv(salidas / "indicadores.csv", index=False, float_format="%.4f")
        print("  salidas/indicadores.csv")
    print("  salidas/validacion.txt\n")
    print(texto)
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())

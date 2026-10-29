"""Servidor MCP con los datos abiertos de fiscalización ambiental del OEFA.

    uv run pytest                                           # el contrato: las 8 pruebas deben pasar
    uv run server.py                                        # el servidor, por stdio
    claude mcp add --scope project oefa -- uv run server.py # conectarlo a Claude Code

Las cuentas las hace pandas, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import re
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

AQUI = Path(__file__).parent
DATOS = AQUI / "datos"
CATALOGO = DATOS / "catalogo_oefa_crudo.csv"   # lo arma scripts/catalogo_oefa.py y sí se sube a git
PORTAL = "https://datosabiertos.oefa.gob.pe"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

# Cada dataset: su vista en el portal, el xlsx original (la API solo entrega 1,000 filas) y qué columna
# del original es cada columna normalizada. "fecha" puede ser una pareja (año, mes en letras).
DATASETS = {
    "sinada": {
        "titulo": "Denuncias SINADA 2019-2025", "id": "262247",
        "vista": f"{PORTAL}/dataviews/262247/denuncias-sinada-2019-2025/",
        "original": f"{PORTAL}/datasets/197779-denuncias-sinada-2019-2025.download/",
        "columnas": {"fecha": "FECHA DE REGISTRO", "departamento": "DEPARTAMENTO", "provincia": "PROVINCIA",
                     "distrito": "DISTRITO", "subsector": "ACTIVIDAD ECONOMICA", "tipo": "ESTADO"}},
    "supervision": {
        "titulo": "Informes de la Dirección de Supervisión 2019-2025", "id": "262236",
        "vista": f"{PORTAL}/dataviews/262236/informes-de-la-direccion-de-supervision-2019-2025/",
        "original": f"{PORTAL}/datasets/197769-informes-de-la-direccion-de-supervision-2019-2025.download/",
        "columnas": {"fecha": "FECHA_INFORME", "subsector": "COORDINACION", "tipo": "TIPO_DE_SUPERVISION",
                     "administrado": "ADMINISTRADO", "unidad": "UNIDAD_FISCALIZABLE"},
        "nota": "El original no trae ubicación: el departamento sale de la misma unidad fiscalizable en las "
                "resoluciones, medidas y multas del OEFA. Cerca de 1 de cada 4 informes queda sin departamento."},
    "medidas": {
        "titulo": "Medidas administrativas de las direcciones de supervisión 2016-2025", "id": "262688",
        "vista": f"{PORTAL}/dataviews/262688/medidas-administrativas-de-las-direcciones-de-supervision-2016-2025/",
        "original": f"{PORTAL}/datasets/197768-medidas-administrativas-de-las-direcciones-de-supervision-2016-2025.download/",
        "columnas": {"fecha": "FECHA_RESOLUCION", "departamento": "REGION", "provincia": "PROVINCIA",
                     "distrito": "DISTRITO", "subsector": "SECTOR", "tipo": "TIPO_MEDIDA",
                     "administrado": "ADMIN", "unidad": "UF"}},
    "multas_firmes": {
        "titulo": "Resoluciones con multa firme 2019-2025", "id": "262240",
        "vista": f"{PORTAL}/dataviews/262240/resolucion-con-multa-firmes-2019-2025/",
        "original": f"{PORTAL}/datasets/197772-resolucion-con-multa-firmes-2019-2025.download/",
        "columnas": {"fecha": ("AÑO", "MES"), "departamento": "DEPARTAMENTO", "provincia": "PROVINCIA",
                     "distrito": "DISTRITO", "subsector": "SECTOR", "tipo": "TIPO DE INFRACCION",
                     "administrado": "ADMINISTRADO", "unidad": "UNIDAD AMBIENTAL", "monto": "MULTA (SOLES)"},
        "unidad_monto": "soles",
        "nota": "monto en soles. Se usa MULTA (SOLES) porque MULTA (UIT) a veces trae soles por error."},
    "actos_administrativos": {
        "titulo": "Registro de actos administrativos 2021-2025", "id": "262241",
        "vista": f"{PORTAL}/dataviews/262241/registros-actos-administrativos-2021-2025/",
        "original": f"{PORTAL}/datasets/197773-registros-actos-administrativos-2021-2025.download/",
        "columnas": {"fecha": "Fecha de la Resolución 4", "departamento": "Departamento ",
                     "provincia": "Provincia ", "distrito": "Distrito", "subsector": "Sector económico ",
                     "tipo": "MASK SANCION",
                     "administrado": "Nombre, razón o denominación social del administrado",
                     "unidad": "Unidad Ambiental "},
        "nota": "fecha = fecha de la resolución de apelación del Tribunal de Fiscalización Ambiental."},
    "resoluciones_directorales": {
        "titulo": "Resoluciones directorales 2018-2025", "id": "262238",
        "vista": f"{PORTAL}/dataviews/262238/resoluciones-directorales-2018-2025/",
        "original": f"{PORTAL}/datasets/197771-resoluciones-directorales-2018-2025.download/",
        "columnas": {"fecha": "FECHA RD", "departamento": "DEPARTAMENTO", "provincia": "PROVINCIA",
                     "distrito": "DISTRITO", "subsector": "SECTOR", "tipo": "TIPO DE RD",
                     "administrado": "RAZON SOCIAL", "unidad": "UNIDAD AMBIENTAL"}},
    "resoluciones_subdirectorales": {
        "titulo": "Resoluciones subdirectorales 2018-2025", "id": "262237",
        "vista": f"{PORTAL}/dataviews/262237/resoluciones-subdirectorales-2018-2025/",
        "original": f"{PORTAL}/datasets/197770-resoluciones-subdirectorales-2018-2025.download/",
        "columnas": {"fecha": "FECHA RSD", "departamento": "DEPARTAMENTO", "provincia": "PROVINCIA",
                     "distrito": "DISTRITO", "subsector": "SECTOR", "tipo": "TIPO DE RSD",
                     "administrado": "RAZON SOCIAL", "unidad": "UNIDAD AMBIENTAL"}},
    "expedientes_tfa": {
        "titulo": "Expedientes resueltos por el Tribunal de Fiscalización Ambiental 2021-2025", "id": "262242",
        "vista": f"{PORTAL}/dataviews/262242/expedientes-resueltos-2021-2025/",
        "original": f"{PORTAL}/datasets/197774-expedientes-resueltos-2021-2025.download/",
        "columnas": {"fecha": "FECHA DE RESOLUCIÓN", "departamento": "DEPARTAMENTO", "provincia": "PROVINCIA",
                     "distrito": "DISTRITO", "subsector": "SECTOR", "tipo": "SENTIDO DE LA RESOLUCIÓN",
                     "administrado": "ADMINISTRADO", "unidad": "UNIDAD FISCALIZABLE", "monto": "MULTA TFA"},
        "unidad_monto": "UIT",
        "nota": "monto en UIT; -999 en el original significa «sin multa» y se deja vacío."},
}
NORMALIZADAS = ["fecha", "departamento", "provincia", "distrito", "subsector", "tipo", "administrado", "unidad", "monto"]
MESES = {m: i for i, m in enumerate(["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
                                      "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"], start=1)}

mcp = FastMCP("oefa", instructions=(
    "Datos abiertos del OEFA (Organismo de Evaluación y Fiscalización Ambiental del Perú): denuncias SINADA, "
    "supervisiones, medidas administrativas, resoluciones y multas. Usa buscar_datos para ubicar un dataset, "
    "resumen para conteos y sumas por grupo, datos para ver registros y ficha_territorio para un departamento. "
    "No calcules a mano: cita siempre el dataset, el periodo y la fuente que devuelve cada herramienta."))


def _norm(s):
    """Mayúsculas, sin tildes y sin espacios de sobra: así «Cajamarca» y «CAJAMARCA » son lo mismo."""
    if pd.isna(s):
        return None
    s = unicodedata.normalize("NFD", str(s).upper()).encode("ascii", "ignore").decode()
    return " ".join(s.split()) or None


def _numero(s):
    """'S/.24.866,80', 'S/.23,000,000.00' o '15110.1' -> float. El xlsx mezcla los dos formatos."""
    if pd.isna(s):
        return None
    s = re.sub(r"S/\.?|\s", "", str(s))
    if re.search(r",\d{1,2}$", s):   # coma decimal, como en 24.866,80
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _dataset(clave):
    if clave not in DATASETS:
        raise ToolError(f"No existe el dataset {clave!r}. Los disponibles son: {', '.join(DATASETS)}.")
    return DATASETS[clave]


def _original(clave):
    """El CSV de datos/ o, si no está, el xlsx original del portal convertido a CSV (se baja una vez)."""
    csv = DATOS / f"{clave}.csv"
    if not csv.exists():
        (DATOS / "originales").mkdir(parents=True, exist_ok=True)
        r = httpx.get(_dataset(clave)["original"], follow_redirects=True, timeout=300)
        r.raise_for_status()
        xlsx = DATOS / "originales" / f"{clave}.xlsx"
        xlsx.write_bytes(r.content)
        pd.read_excel(xlsx, dtype=str).dropna(how="all").to_csv(csv, index=False)
    return pd.read_csv(csv, dtype=str)


@cache
def tabla(clave):
    """El dataset con las columnas normalizadas de NORMALIZADAS (las que no tiene quedan vacías)."""
    d = _dataset(clave)
    crudo = _original(clave)
    df = pd.DataFrame(index=crudo.index, columns=NORMALIZADAS)
    for nueva, col in d["columnas"].items():
        if nueva == "fecha" and isinstance(col, tuple):   # año y mes en letras, como en multas_firmes
            mes = crudo[col[1]].map(_norm).map(MESES)
            df["fecha"] = pd.to_datetime(crudo[col[0]] + "-" + mes.astype("Int64").astype(str), errors="coerce")
        elif nueva == "fecha":
            df["fecha"] = pd.to_datetime(crudo[col], errors="coerce", format="ISO8601")
        elif nueva == "monto":
            monto = crudo[col].map(_numero)
            df["monto"] = monto.where(monto >= 0)   # -999 = sin multa
        else:
            df[nueva] = crudo[col].map(_norm)
    df["departamento"] = df.departamento.str.replace("CUZCO", "CUSCO")
    df["subsector"] = df.subsector.str.removeprefix("COORDINACION DE SUPERVISION AMBIENTAL EN ")
    if clave == "supervision":
        df["departamento"] = df.unidad.map(_departamento_por_unidad())
    return df


@cache
def _departamento_por_unidad():
    """Unidad fiscalizable -> departamento más frecuente en los otros datasets que sí traen ubicación."""
    claves = ["medidas", "multas_firmes", "resoluciones_directorales", "resoluciones_subdirectorales"]
    pares = pd.concat([tabla(c)[["unidad", "departamento"]] for c in claves]).dropna()
    return pares.groupby("unidad").departamento.agg(lambda s: s.value_counts().index[0])


def _periodo(texto, final=False):
    """'2024' -> 2024-01-01 (o 2024-12-31 si final); también acepta '2024-03' y '2024-03-15'."""
    try:
        p = pd.Period(texto)
    except ValueError:
        raise ToolError(f"No entiendo la fecha {texto!r}: usen 2024, 2024-03 o 2024-03-15.")
    return p.end_time if final else p.start_time


def _filtrar(clave, departamento=None, provincia=None, subsector=None, desde=None, hasta=None):
    """Filas del dataset que cumplen los filtros. Un registro con varios departamentos («JUNIN; LIMA»)
    cuenta para cada uno de ellos."""
    df = tabla(clave)
    for col, valor in [("departamento", departamento), ("provincia", provincia), ("subsector", subsector)]:
        if valor:
            df = df[df[col].str.contains(rf"\b{re.escape(_norm(valor))}\b", na=False)]
    if desde:
        df = df[df.fecha >= _periodo(desde)]
    if hasta:
        df = df[df.fecha <= _periodo(hasta, final=True)]
    return df


def _cubre(df):
    fechas = df.fecha.dropna()
    if fechas.empty:
        return None
    return {"desde": fechas.min().strftime("%Y-%m-%d"), "hasta": fechas.max().strftime("%Y-%m-%d")}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_datos(texto: str, categoria: str | None = None, limite: int = 10) -> list[dict]:
    """Busca entre los 98 recursos del portal de datos abiertos del OEFA: todas las palabras deben aparecer
    en el título o la descripción.

    Ejemplos: "denuncias", "multas", "supervision", "medidas administrativas", "agua". categoria:
    "Fiscalización Ambiental", "Supervisión Ambiental", "Evaluación Ambiental", "Políticas y estrategias"...
    Devuelve el título, la categoría y la vista en el portal. Si «clave» no es null, el dataset se puede
    consultar con datos, resumen y ficha_territorio usando esa clave.
    """
    cat = pd.read_csv(CATALOGO, dtype=str).fillna("")
    texto_cat = (cat.titulo + " " + cat.descripcion_corta).map(_norm)
    m = pd.Series(True, index=cat.index)
    for palabra in _norm(texto).split():
        m &= texto_cat.str.contains(re.escape(palabra))
    if categoria:
        m &= cat.categoria.map(_norm).str.contains(re.escape(_norm(categoria)))
    claves = {d["id"]: c for c, d in DATASETS.items()}
    return [{"clave": claves.get(f.datastream_id), "titulo": f.titulo, "categoria": f.categoria,
             "descripcion": f.descripcion_corta, "vista": f.url_vista}
            for f in cat[m].head(limite).itertuples()]


@mcp.tool(annotations=SOLO_LECTURA)
def datos(dataset: str, departamento: str | None = None, provincia: str | None = None,
          subsector: str | None = None, desde: str | None = None, hasta: str | None = None,
          limite: int = 50) -> dict:
    """Registros de un dataset del OEFA con filtros, del más reciente al más antiguo.

    dataset: sinada, supervision, medidas, multas_firmes, actos_administrativos, resoluciones_directorales,
    resoluciones_subdirectorales o expedientes_tfa. desde y hasta: "2024", "2024-03" o "2024-03-15".
    Ejemplo: dataset="sinada", departamento="Cajamarca", desde="2024", hasta="2024".
    «total» es el número de registros que cumplen los filtros; «filas» trae solo los primeros «limite».
    """
    d = _dataset(dataset)
    df = _filtrar(dataset, departamento, provincia, subsector, desde, hasta).sort_values("fecha", ascending=False)
    filas = df.head(limite).assign(fecha=df.fecha.dt.strftime("%Y-%m-%d"))
    filas = filas.dropna(axis=1, how="all").astype(object).where(filas.notna(), None)
    return {"dataset": dataset, "titulo": d["titulo"], "total": len(df), "periodo": _cubre(df),
            "filas": filas.to_dict("records"), "fuente": d["vista"]}


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(dataset: str, agrupar_por: str, departamento: str | None = None, provincia: str | None = None,
            subsector: str | None = None, desde: str | None = None, hasta: str | None = None,
            suma: str | None = None) -> dict:
    """Cuenta registros (o suma montos) por grupo. Úsenla para cualquier conteo, total, ranking o comparación.

    agrupar_por: "anio", "mes", "departamento", "provincia", "distrito", "subsector", "tipo" o "administrado".
    suma="monto" suma las multas en vez de contar: en soles en multas_firmes, en UIT en expedientes_tfa.
    Filtros iguales a los de datos. Ejemplo: dataset="multas_firmes", agrupar_por="subsector", desde="2024",
    hasta="2024", suma="monto". Devuelve el total, los 10 grupos más grandes (o todos si se agrupa por tiempo),
    el máximo y el mínimo con su grupo, el periodo cubierto y la fuente.
    """
    d = _dataset(dataset)
    df = _filtrar(dataset, departamento, provincia, subsector, desde, hasta)
    if suma and suma != "monto":
        raise ToolError("suma solo acepta 'monto'.")
    if suma and df.monto.isna().all():
        raise ToolError(f"El dataset {dataset!r} no tiene montos para sumar.")
    if agrupar_por in ("anio", "mes"):
        grupo = df.fecha.dt.strftime("%Y" if agrupar_por == "anio" else "%Y-%m")
    elif agrupar_por in NORMALIZADAS[1:-1]:
        grupo = df[agrupar_por]
    else:
        raise ToolError(f"No se puede agrupar por {agrupar_por!r}: usen anio, mes, departamento, provincia, "
                        "distrito, subsector, tipo o administrado.")
    valores = (df.monto.groupby(grupo).sum() if suma else grupo.value_counts()).round(2)
    if valores.empty:
        raise ToolError("Ningún registro cumple esos filtros.")
    tiempo = agrupar_por in ("anio", "mes")
    tabla_grupos = valores.sort_index() if tiempo else valores.sort_values(ascending=False).head(10)
    return {"dataset": dataset, "titulo": d["titulo"], "agrupado_por": agrupar_por,
            "medida": f"suma de multas en {d['unidad_monto']}" if suma else "número de registros",
            "registros": len(df), "total": round(float(df.monto.sum()), 2) if suma else len(df),
            "sin_grupo": int(grupo.isna().sum()), "numero_de_grupos": len(valores),
            "grupos": [{"grupo": g, "valor": float(v)} for g, v in tabla_grupos.items()],
            "maximo": {"grupo": valores.idxmax(), "valor": float(valores.max())},
            "minimo": {"grupo": valores.idxmin(), "valor": float(valores.min())},
            "periodo": _cubre(df), "fuente": d["vista"], "nota": d.get("nota")}


@mcp.tool(annotations=SOLO_LECTURA)
def ficha_territorio(departamento: str, provincia: str | None = None, desde: str | None = None,
                     hasta: str | None = None) -> dict:
    """Ficha ambiental de un departamento (o provincia) para preparar una entrada a campo de relaciones
    comunitarias: qué denuncian los vecinos, cuánto supervisa el OEFA, qué medidas y multas firmes hubo y
    qué empresas aparecen más.

    Ejemplo: departamento="Cajamarca", desde="2023", hasta="2024". Junta denuncias SINADA por actividad,
    informes de supervisión por subsector, medidas administrativas por tipo, multas firmes (número y soles) y
    los 5 administrados con más registros en supervisión, medidas, multas y resoluciones directorales.
    Cada bloque trae su periodo y su fuente.
    """
    filtros = {"departamento": departamento, "provincia": provincia, "desde": desde, "hasta": hasta}

    def bloque(clave, por):
        df = _filtrar(clave, **filtros)
        return {"total": len(df), f"por_{por}": df[por].value_counts().head(5).to_dict(),
                "periodo": _cubre(df), "fuente": DATASETS[clave]["vista"]}

    multas = _filtrar("multas_firmes", **filtros)
    claves = ["supervision", "medidas", "multas_firmes", "resoluciones_directorales"]
    administrados = pd.concat([_filtrar(c, **filtros).administrado for c in claves]).value_counts().head(5)
    return {
        "territorio": " / ".join(_norm(x) for x in (departamento, provincia) if x),
        "denuncias_sinada": bloque("sinada", "subsector"),
        "supervisiones": {**bloque("supervision", "subsector"), "nota": DATASETS["supervision"]["nota"]},
        "medidas_administrativas": bloque("medidas", "tipo"),
        "multas_firmes": {**bloque("multas_firmes", "subsector"), "suma_soles": round(float(multas.monto.sum()), 2)},
        "administrados_con_mas_registros": administrados.to_dict(),
        "fuentes": [DATASETS[c]["vista"] for c in ["sinada", *claves]],
    }


@mcp.resource("oefa://dataset/{clave}")
def ficha_dataset(clave: str) -> dict:
    """La ficha de un dataset: título, vista en el portal, xlsx original, columnas, filas y periodo."""
    d = _dataset(clave)
    df = tabla(clave)
    return {"clave": clave, "titulo": d["titulo"], "vista": d["vista"], "original": d["original"],
            "columnas_originales": {k: v if isinstance(v, str) else list(v) for k, v in d["columnas"].items()},
            "filas": len(df), "periodo": _cubre(df), "nota": d.get("nota")}


@mcp.prompt
def informe_territorio(departamento: str) -> str:
    """Pide un informe corto de un departamento con cifras del OEFA citadas."""
    return (f"Prepara un informe sobre la situación de fiscalización ambiental en {departamento} para un equipo de "
            "relaciones comunitarias que va a campo. Usa ficha_territorio y, si hace falta, resumen. Escribe 5 "
            "viñetas; en cada cifra cita el dataset, el periodo y la fuente. No hagas cuentas a mano.")


if __name__ == "__main__":
    mcp.run()

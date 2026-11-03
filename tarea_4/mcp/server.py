"""Servidor MCP del BCRP para la Tarea 4: series oficiales del Banco Central de Reserva del Perú.

    uv run pytest -q                                          # las 10 pruebas (8 del curso + 2 propias)
    uv run mcp/server.py                                      # el servidor, por stdio
    claude mcp add --scope project bcrp -- uv run mcp/server.py

Herramientas: buscar_series, serie, resumen, produccion_minera_departamental (propia) y graficar_serie.
Recurso: bcrp://serie/{codigo}. Prompt: informe(tema).

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

AQUI = Path(__file__).parent
RAIZ = AQUI.parent                                   # la carpeta tarea_4/
CATALOGO = RAIZ / "datos" / "catalogo_bcrp.csv"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}

mcp = FastMCP("bcrp", instructions=(
    "Series oficiales del Banco Central de Reserva del Perú (BCRP). Primero busca el código con buscar_series; "
    "luego usa resumen para variaciones, promedios y extremos, serie para los datos y "
    "produccion_minera_departamental para saber cuánto cobre, oro u otro metal produjo cada departamento en un año. "
    "No calcules a mano: cita siempre el código de la serie, el periodo y la fuente."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    """El catálogo oficial: 17 mil series en unos 7 MB. Se baja una vez y queda en datos/."""
    if not CATALOGO.exists():
        CATALOGO.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_CATALOGO, timeout=120)
        r.raise_for_status()
        CATALOGO.write_text(r.content.decode("latin-1"), encoding="utf-8")
    df = pd.read_csv(CATALOGO, sep=";", dtype=str).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria", "Grupo de serie": "grupo",
                            "Nombre de serie": "nombre", "Frecuencia": "frecuencia",
                            "Fecha de actualización": "actualizada", "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def _ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ToolError(f"No existe el código de serie {codigo!r}. Búsquenlo con buscar_series.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}", "categoria": f.categoria,
            "frecuencia": f.frecuencia, "inicio": f.inicio, "actualizada": f.actualizada}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_series(texto: str, frecuencia: str | None = None, limite: int = 10) -> list[dict]:
    """Busca series del BCRP por palabras: todas deben aparecer en la categoría, el grupo o el nombre.

    Ejemplos: "ipc 12 meses", "tipo de cambio interbancario venta", "reservas internacionales netas",
    "tasa de referencia", "cobre precio". frecuencia: "Diaria", "Mensual", "Trimestral" o "Anual".
    Devuelve el código, el nombre completo, la frecuencia y desde cuándo hay datos. Si no hay resultados,
    prueben con menos palabras.
    """
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    # primero las series vigentes y, entre ellas, las de nombre más corto (las más generales)
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025", largo=(sel.grupo + sel.nombre).str.len())
    return [_ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


# ------------------------------------------------------------------ fechas
def _tipo(frecuencia):
    f = _sin_tildes(frecuencia)
    for clave in ("diaria", "mensual", "trimestral", "anual"):
        if clave in f:
            return clave
    raise ToolError(f"Frecuencia {frecuencia!r} no soportada (solo diaria, mensual, trimestral o anual).")


def _fecha_api(fecha, tipo):
    """De lo que escribe el usuario ("2025-01", "2025-1", "2026-10-01", "2025", "2025-T1") a lo que pide la API."""
    fecha = str(fecha).strip()
    partes = re.findall(r"\d+", fecha)
    if not partes:
        raise ToolError(f"No entiendo la fecha {fecha!r}. Usen 2025-01, 2026-10-01 o 2025.")
    anio = int(partes[0])
    if tipo == "anual":
        return f"{anio}"
    if tipo == "diaria":
        if len(partes) < 3:
            raise ToolError(f"La serie es diaria: pidan la fecha completa, por ejemplo 2026-10-01 (llegó {fecha!r}).")
        return f"{anio}-{int(partes[1]):02d}-{int(partes[2]):02d}"
    if len(partes) < 2:
        raise ToolError(f"La serie es {tipo}: pidan año y {'mes' if tipo == 'mensual' else 'trimestre'} "
                        f"(por ejemplo 2025-01 o 2025-T1), llegó {fecha!r}.")
    return f"{anio}-{int(partes[1])}"


def _periodo(nombre, tipo):
    """De lo que devuelve la API ("Ene.2025", "01.Oct.26", "T1.25", "2025") a "2025-01", "2026-10-01", "2025-T1"."""
    n = nombre.strip()
    if tipo == "anual":
        return n
    if tipo == "mensual":
        mes, anio = n.split(".")
        return f"{int(anio)}-{MESES[_sin_tildes(mes)[:3]]:02d}"
    if tipo == "diaria":
        dia, mes, anio = n.split(".")
        anio = int(anio)
        anio = anio + 2000 if anio < 100 else anio
        return f"{anio}-{MESES[_sin_tildes(mes)[:3]]:02d}-{int(dia):02d}"
    trimestre, anio = n.split(".")
    anio = int(anio)
    anio = anio + 2000 if anio < 100 else anio
    numero = int(re.sub(r"\D", "", trimestre))
    return f"{anio}-T{numero}"


@cache
def _bajar(codigo, desde_api, hasta_api):
    """Pide la serie a la API con reintentos: si hay muchos pedidos seguidos responde HTML en vez de JSON."""
    url = f"{API}/{codigo}/json/{desde_api}/{hasta_api}"
    ultimo = ""
    for intento in range(4):
        try:
            r = httpx.get(url, timeout=60, follow_redirects=True)
            texto = r.content.decode("utf-8", errors="replace").strip()
            if texto.startswith("{"):
                return url, r.json()
            ultimo = f"respuesta no JSON (HTTP {r.status_code})"
        except (httpx.HTTPError, ValueError) as e:
            ultimo = str(e)
        time.sleep(2 * (intento + 1))
    raise ToolError(f"El BCRP no respondió con datos para {codigo} ({ultimo}). Reintenten en unos segundos.")


def _datos(codigo, desde, hasta):
    """La serie como (ficha, url, lista de {"periodo", "valor"}), sin los "n.d."."""
    ficha = _ficha(codigo)
    tipo = _tipo(ficha["frecuencia"])
    url, js = _bajar(codigo, _fecha_api(desde, tipo), _fecha_api(hasta, tipo))
    datos = []
    for p in js.get("periods", []):
        valor = (p.get("values") or [None])[0]
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            continue                                 # "n.d." y vacíos
        datos.append({"periodo": _periodo(p["name"], tipo), "valor": valor})
    if not datos:
        raise ToolError(f"La serie {codigo} no tiene datos entre {desde} y {hasta}.")
    return ficha, url, datos


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Descarga los datos de una serie del BCRP entre dos fechas, con la URL de la fuente.

    Úsenla cuando necesiten los valores periodo por periodo. Fechas: "2025-01" (mensual), "2025-T1" o "2025-1"
    (trimestral), "2026-10-01" (diaria) o "2025" (anual). Ejemplo: serie("PN01273PM", "2025-01", "2025-12").
    Devuelve codigo, nombre, frecuencia, datos [{periodo, valor}] y fuente.
    """
    ficha, url, datos = _datos(codigo, desde, hasta)
    return {"codigo": ficha["codigo"], "nombre": ficha["nombre"], "frecuencia": ficha["frecuencia"],
            "datos": datos, "fuente": url}


def _resumen(datos):
    df = pd.DataFrame(datos)
    primero, ultimo = df.iloc[0], df.iloc[-1]
    imax, imin = df.valor.idxmax(), df.valor.idxmin()
    cambio = ultimo.valor - primero.valor
    return {
        "primero": {"periodo": primero.periodo, "valor": float(primero.valor)},
        "ultimo": {"periodo": ultimo.periodo, "valor": float(ultimo.valor)},
        "cambio": round(float(cambio), 6),
        "variacion_pct": round(float(cambio / primero.valor * 100), 4) if primero.valor else None,
        "promedio": round(float(df.valor.mean()), 6),
        "maximo": {"periodo": df.periodo[imax], "valor": float(df.valor[imax])},
        "minimo": {"periodo": df.periodo[imin], "valor": float(df.valor[imin])},
        "n": len(df),
    }


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Resume una serie del BCRP en un periodo: primero, último, cambio, variación %, promedio, máximo y mínimo.

    Úsenla para cualquier pregunta de variación, promedio o extremos, en vez de calcular a mano.
    Ejemplo: resumen("PN01273PM", "2025-12", "2026-09"). Las fechas siguen el formato de serie.
    """
    ficha, url, datos = _datos(codigo, desde, hasta)
    return {"codigo": ficha["codigo"], "nombre": ficha["nombre"], "frecuencia": ficha["frecuencia"],
            "desde": datos[0]["periodo"], "hasta": datos[-1]["periodo"], **_resumen(datos), "fuente": url}


# ----------------------------------------------------------- herramienta propia
GRUPO_MINERO = "produccion de productos mineros segun departamentos"
# Código INEI de departamento (los dos primeros dígitos del ubigeo): sirve para unir con la ENAHO por código.
DEPARTAMENTOS = {
    "amazonas": "01", "ancash": "02", "apurimac": "03", "arequipa": "04", "ayacucho": "05", "cajamarca": "06",
    "callao": "07", "cusco": "08", "huancavelica": "09", "huanuco": "10", "ica": "11", "junin": "12",
    "la libertad": "13", "lambayeque": "14", "lima": "15", "loreto": "16", "madre de dios": "17",
    "moquegua": "18", "pasco": "19", "piura": "20", "puno": "21", "san martin": "22", "tacna": "23",
    "tumbes": "24", "ucayali": "25",
}
METALES = ["cobre", "oro", "plata", "zinc", "plomo", "molibdeno", "hierro", "estano", "tungsteno"]


def _partes_nombre(nombre):
    """"Cobre - Apurimac (tm.f)" -> ("cobre", "apurimac", "tm.f")."""
    m = re.match(r"\s*(.+?)\s+-\s+(.+?)\s*\((.+)\)\s*$", nombre)
    if not m:
        return None
    return _sin_tildes(m.group(1)).strip(), _sin_tildes(m.group(2)).strip(), m.group(3).strip()


@mcp.tool(annotations=SOLO_LECTURA)
def produccion_minera_departamental(metal: str, anio: int) -> dict:
    """Ranking de departamentos por producción de un metal en un año, con su participación en el total nacional.

    Úsenla cuando pregunten qué departamentos producen más cobre, oro, plata, zinc, plomo o molibdeno, cuánto
    produjo un departamento, o para saber cuáles son los «departamentos mineros» y cruzarlos con otra base
    (por ejemplo la pobreza de la ENAHO). Cada fila trae el código de departamento del INEI (ccdd = ubigeo[:2]),
    así que la unión se hace por código y no por nombre.

    Fuente: BCRP, «Producción de productos mineros según departamentos» (series anuales RD155..DA, datos del
    MINEM). Unidades: cobre, zinc, plomo, molibdeno en tm.f (toneladas métricas finas); oro en grs.f (gramos
    finos); plata en kg.f. Ejemplo: produccion_minera_departamental("cobre", 2024).
    """
    metal_n = _sin_tildes(metal).strip()
    if metal_n not in METALES:
        raise ToolError(f"Metal {metal!r} no reconocido. Usen uno de: {', '.join(METALES)}.")
    df = catalogo()
    sel = df[df.grupo.map(_sin_tildes).str.contains(GRUPO_MINERO) & (df.frecuencia.str.lower() == "anual")]
    filas = []
    for f in sel.itertuples():
        partes = _partes_nombre(f.nombre)
        if partes and partes[0] == metal_n:
            filas.append({"codigo": f.codigo, "lugar": partes[1], "unidad": partes[2]})
    if not filas:
        raise ToolError(f"El BCRP no tiene series anuales de producción de {metal} por departamento.")

    # Una sola llamada con todos los códigos unidos por «-»: la API los devuelve en SU orden, así que cada valor
    # se asigna por el nombre de la serie (config.series[].name), nunca por la posición.
    codigos = sorted(x["codigo"] for x in filas)
    url, js = _bajar("-".join(codigos), str(anio), str(anio))
    nombres = [s.get("name", "") for s in js.get("config", {}).get("series", [])]
    valores = (js.get("periods") or [{}])[0].get("values", []) if js.get("periods") else []
    por_lugar = {}
    for nombre, valor in zip(nombres, valores):
        partes = _partes_nombre(nombre.split(" - ", 1)[1] if " - " in nombre else nombre)
        try:
            por_lugar[partes[1]] = float(valor)
        except (TypeError, ValueError, IndexError):
            continue                                          # "n.d."
    if not por_lugar:
        raise ToolError(f"La API del BCRP no trae datos de producción de {metal} para {anio}.")

    unidad = filas[0]["unidad"]
    total = por_lugar.pop("total", None)
    suma = sum(por_lugar.values())
    base = total or suma
    ranking = []
    for x in filas:
        if x["lugar"] == "total" or x["lugar"] not in por_lugar:
            continue
        v = por_lugar[x["lugar"]]
        ranking.append({"departamento": x["lugar"].title(), "ccdd": DEPARTAMENTOS.get(x["lugar"], ""),
                        "produccion": round(v, 2), "participacion_pct": round(v / base * 100, 2) if base else None,
                        "codigo": x["codigo"]})
    ranking.sort(key=lambda r: r["produccion"], reverse=True)
    for i, r in enumerate(ranking, 1):
        r["puesto"] = i
    return {"metal": metal_n, "anio": anio, "unidad": unidad, "total_nacional": round(total, 2) if total else None,
            "suma_departamentos": round(suma, 2), "departamentos": ranking, "fuente": url,
            "nota": "Departamentos sin producción registrada no aparecen. Fuente original: MINEM, vía BCRP."}


@mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
def graficar_serie(codigo: str, desde: str, hasta: str, titulo: str | None = None) -> dict:
    """Guarda un gráfico de líneas PNG de una serie del BCRP en figuras/ y devuelve la ruta.

    Úsenla cuando pidan un gráfico de una serie del BCRP para un informe. El gráfico lleva título, unidades del
    nombre de la serie, periodo y la fuente con el código. Ejemplo: graficar_serie("PN01652XM", "2019-01", "2024-12").
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ficha, url, datos = _datos(codigo, desde, hasta)
    df = pd.DataFrame(datos)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(range(len(df)), df.valor, color="#1f4e79", linewidth=2)
    paso = max(1, len(df) // 8)
    ax.set_xticks(range(0, len(df), paso), df.periodo[::paso], rotation=0, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dddddd")
    ax.set_title(titulo or ficha["nombre"][:90], loc="left", fontsize=12, fontweight="bold")
    ax.set_ylabel(ficha["nombre"].split(" - ")[-1][:60], fontsize=8)
    fig.text(0.01, 0.01, f"Fuente: BCRP, serie {codigo} ({datos[0]['periodo']} a {datos[-1]['periodo']}).",
             fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    carpeta = RAIZ / "figuras"
    carpeta.mkdir(exist_ok=True)
    salida = carpeta / f"bcrp_{codigo}_{datos[0]['periodo']}_{datos[-1]['periodo']}.png"
    fig.savefig(salida, dpi=200)
    plt.close(fig)
    return {"archivo": str(salida.relative_to(RAIZ)).replace("\\", "/"), "codigo": codigo, "n": len(df),
            "fuente": url}


# ------------------------------------------------------------- recurso y prompt
@mcp.resource("bcrp://serie/{codigo}", mime_type="application/json")
def ficha_serie(codigo: str) -> dict:
    """La ficha de una serie del BCRP: nombre completo, categoría, frecuencia, desde cuándo hay datos y la
    última actualización, más la página oficial para comprobarla."""
    f = _ficha(codigo)
    carpeta = {"diaria": "diarias", "mensual": "mensuales", "trimestral": "trimestrales", "anual": "anuales"}
    return {**f, "pagina": f"https://estadisticas.bcrp.gob.pe/estadisticas/series/"
                           f"{carpeta[_tipo(f['frecuencia'])]}/resultados/{codigo}/html"}


@mcp.prompt
def informe(tema: str) -> str:
    """Plantilla para un informe breve con series del BCRP sobre un tema (por ejemplo «precio del cobre»)."""
    return (
        f"Prepara un informe breve sobre «{tema}» con series oficiales del BCRP.\n"
        "1. Busca las series con buscar_series y elige la más pertinente; di por qué.\n"
        "2. Usa resumen o produccion_minera_departamental para las cifras: no hagas cuentas a mano.\n"
        "3. Si hace falta, guarda un gráfico con graficar_serie.\n"
        "4. Cada cifra va con el código de la serie, el periodo y la URL de la fuente.\n"
        "5. Si una herramienta falla o no hay datos, dilo: no inventes cifras.\n"
        "6. Describe asociaciones; no afirmes causas.")


if __name__ == "__main__":
    mcp.run()

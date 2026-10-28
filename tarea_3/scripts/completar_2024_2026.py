"""Lista completa de casos activos y latentes, oct 2024 (N° 248) a set 2026 (N° 271).

Desde el N° 248, los reportes presentan los casos activos de dos maneras:
- una ficha por caso cuando hubo hechos en el mes (secciones "Conflictos activos
  desarrollados en un solo departamento / en más de un departamento que
  registraron hechos durante el mes");
- una tabla resumida (fecha de inicio, departamento, denominación, tipo) para los
  "Conflictos activos que no registraron hechos durante el mes".
Los latentes van en otra tabla resumida ("Detalle de los conflictos latentes").

Este script lee:
- las fichas desde datos/originales/textos/reporte_NNN.txt;
- las tablas desde el PDF (datos/originales/defensoria/reporte_NNN.pdf) con pymupdf,
  reconstruyendo el texto de cada celda a partir de las palabras que caen en ella;
- el N° 271 desde su HTML (fichas div.caso-card y filas tr.reg-filter-row).

Salida: datos/procesados/casos_2024_10_a_2026_09.csv, con las mismas columnas que
datos/originales/defensoria_casos_por_mes_2015_2026.csv. En las filas que vienen
de tablas, "caso" es la denominación corta del caso (la tabla no trae descripción)
y el ubigeo es el código de 2 dígitos del departamento.

Al final compara activos y latentes extraídos con datos/procesados/resumen_oficial.csv.
Uso:  python tarea_3/scripts/completar_2024_2026.py
"""

import csv
import re
import unicodedata
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parents[1]
DIR_ORIG = RAIZ / "datos" / "originales"
CATALOGO = DIR_ORIG / "catalogo_reportes.csv"
OFICIAL = RAIZ / "datos" / "procesados" / "resumen_oficial.csv"
SALIDA = RAIZ / "datos" / "procesados" / "casos_2024_10_a_2026_09.csv"
PRIMERO, ULTIMO = 248, 271

COLUMNAS = ["reporte_n", "anio", "mes", "estado", "codigo", "caso", "departamento",
            "provincia", "distrito", "ubicacion", "ubigeo", "nivel_ubicacion", "ubigeos",
            "tipo_texto_original", "tipo_conflicto", "hay_dialogo", "sin_hechos_en_mes",
            "archivo_reporte", "url_reporte"]

DEPARTAMENTOS = {
    "Amazonas": "01", "Áncash": "02", "Apurímac": "03", "Arequipa": "04",
    "Ayacucho": "05", "Cajamarca": "06", "Callao": "07", "Cusco": "08",
    "Huancavelica": "09", "Huánuco": "10", "Ica": "11", "Junín": "12",
    "La Libertad": "13", "Lambayeque": "14", "Lima Metropolitana": "15",
    "Lima Provincias": "15", "Lima": "15", "Loreto": "16", "Madre de Dios": "17",
    "Moquegua": "18", "Pasco": "19", "Piura": "20", "Puno": "21", "San Martín": "22",
    "Tacna": "23", "Tumbes": "24", "Ucayali": "25",
    "Nacional": None, "Multirregional": None,
}

TIPOS = [  # (patrón sobre el texto sin tildes y en minúsculas, categoría de la Defensoría)
    (r"socio ?ambient|sociambiental", "Socioambiental"),
    (r"gobierno nacional|gob\. nacional", "Asuntos de gobierno nacional"),
    (r"gobierno regional|gob\. regional", "Asuntos de gobierno regional"),
    (r"gobierno local|gob\. local", "Asuntos de gobierno local"),
    (r"demarcacion", "Demarcación territorial"),
    (r"comunal", "Comunal"),
    (r"laboral", "Laboral"),
    (r"electoral", "Electoral"),
    (r"coca", "Cultivo ilegal de hoja de coca"),
    (r"otros", "Otros asuntos"),
    # Categorías nuevas que aparecen en 2026
    (r"universidad", "Conflictos en universidades"),
    (r"administracion de justicia", "Asuntos de administración de justicia"),
]


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def clave(s):
    return re.sub(r"[^a-z]", "", sin_tildes(s).lower())


CLAVES_DEP = {clave(k): k for k in DEPARTAMENTOS}
CLAVES_DEP.update({"multiregional": "Multirregional", "limaprovincia": "Lima Provincias"})


def departamento(texto):
    return CLAVES_DEP.get(clave(texto or ""))


def tipo_normalizado(texto):
    t = sin_tildes(texto or "").lower()
    for patron, categoria in TIPOS:
        if re.search(patron, t):
            return categoria
    return ""


def fila_base(info, estado, dep, tipo_txt):
    return {
        "reporte_n": info["numero"], "anio": info["anio"], "mes": info["mes"],
        "estado": estado, "departamento": dep or "",
        "ubigeo": DEPARTAMENTOS.get(dep) or "" if dep else "",
        "nivel_ubicacion": "departamento" if dep and DEPARTAMENTOS.get(dep) else "",
        "tipo_texto_original": tipo_txt.strip(), "tipo_conflicto": tipo_normalizado(tipo_txt),
        "archivo_reporte": Path(info["url"]).name, "url_reporte": info["url"],
    }


# ---------------------------------------------------------------- PDF: fichas

RUIDO = re.compile(
    r"^(Reporte (Mensual )?de Conflictos Sociales N|ADJUNT[IÍ]A PARA LA PREVENCI|"
    r"\d+$|Descripci[oó]n$|Hechos del mes$)", re.I)
INICIO_FICHAS = re.compile(r"CONFLICTOS ACTIVOS DESARROLLADOS EN UN SOLO DEPARTAMENTO", re.I)
FIN_FICHAS = re.compile(r"CONFLICTOS ACTIVOS QUE NO REGISTRARON HECHOS", re.I)


def fichas_pdf(info):
    txt = DIR_ORIG / "textos" / f"reporte_{int(info['numero']):03d}.txt"
    lineas = [l.strip() for l in txt.read_text(encoding="utf-8").splitlines()]
    i0 = next(i for i, l in enumerate(lineas) if INICIO_FICHAS.search(l))
    i1 = next(i for i, l in enumerate(lineas) if i > i0 and FIN_FICHAS.search(l))
    lineas = [l for l in lineas[i0:i1] if l and not RUIDO.match(l)
              and not l.startswith("=== PAGINA")]

    fichas, dep, codigo = [], None, ""
    for l in lineas:
        d = departamento(l)
        if d and len(l) < 25:
            dep = d
            continue
        # En el N° 270 un código aparece rotulado por error como "Tipo: 1407-0425".
        m = re.match(r"C[oó]digo:\s*(\S+)", l) or re.match(r"Tipo:\s*(\d{4}-\d{4})\s*$", l)
        if m:
            codigo = m.group(1)
            l = l[m.end():].strip()
            if not l:
                continue
        if l.startswith("Tipo:"):
            fichas.append({"dep": dep, "codigo": codigo, "lineas": []})
            codigo = ""
        if fichas:
            fichas[-1]["lineas"].append(l)

    filas = []
    for f in fichas:
        texto = " ".join(f["lineas"])
        tipo = re.search(r"Tipo:\s*(.+?)(?:\.|\s+Ingres|\s+Caso:|$)", texto)
        caso = re.search(r"Caso:\s*(.+?)\s*(?:Ubicaci[oó]n:|Actores primarios:|$)", texto)
        ubic = re.search(r"Ubicaci[oó]n:\s*(.+?)\s*(?:Actores|HAY DI|NO HAY DI|$)", texto)
        fila = fila_base(info, "activo", f["dep"], tipo.group(1) if tipo else "")
        fila.update({
            "codigo": f["codigo"],
            "caso": caso.group(1) if caso else "",
            "ubicacion": ubic.group(1) if ubic else "",
            "hay_dialogo": "no" if re.search(r"NO HAY DI[AÁ]LOGO", texto)
            else "si" if re.search(r"HAY DI[AÁ]LOGO", texto) else "",
            "sin_hechos_en_mes": False,
        })
        filas.append(fila)
    return filas


# ---------------------------------------------------------------- PDF: tablas

SECCIONES = [
    ("sin_hechos", "ACTIVOS QUE NO REGISTRARON HECHOS"),
    ("otra", "CONFLICTOS REACTIVADOS"),
    ("latentes", "DETALLE DE LOS CONFLICTOS LATENTES"),
    ("otra", "PASADO DE ESTADO ACTIVO A LATENTE"),
    ("otra", "CASOS QUE SALIERON DEL REPORTE"),
]
FECHA = re.compile(r"^(?:[A-Za-zé]{3}\.?\s*-\s*\d{2}|\d{1,2}\s*/\s*\d{4})$")  # "Jul-17" o "07/2017"


def eventos_seccion(doc, desde):
    eventos = []
    for i in range(desde, len(doc)):
        for nombre, frase in SECCIONES:
            for r in doc[i].search_for(frase):
                eventos.append((i, r.y0, nombre))
    return sorted(eventos)


def texto_celda(palabras, bbox):
    x0, y0, x1, y1 = bbox
    dentro = [w for w in palabras
              if (w[0] + w[2]) / 2 > x0 and (w[0] + w[2]) / 2 < x1
              and (w[1] + w[3]) / 2 > y0 and (w[1] + w[3]) / 2 < y1]
    dentro.sort(key=lambda w: (round(w[1]), w[0]))
    return re.sub(r"\s+", " ", " ".join(w[4] for w in dentro)).strip()


def tablas_pdf(info):
    doc = pymupdf.open(DIR_ORIG / "defensoria" / f"reporte_{int(info['numero']):03d}.pdf")
    inicio = next(i for i in range(len(doc))
                  if i > 5 and doc[i].search_for("ACTIVOS QUE NO REGISTRARON HECHOS"))
    eventos = eventos_seccion(doc, inicio)
    fin = max(e[0] for e in eventos)

    filas = {"sin_hechos": [], "latentes": []}
    for i in range(inicio, fin + 1):
        pagina = doc[i]
        palabras = pagina.get_text("words")
        for tb in pagina.find_tables().tables:
            previos = [e for e in eventos if (e[0], e[1]) <= (i, tb.bbox[1])]
            seccion = previos[-1][2] if previos else None
            if seccion not in filas:
                continue
            for row in tb.rows:
                celdas = [texto_celda(palabras, c) for c in row.cells if c]
                celdas = [c for c in celdas if c and not re.fullmatch(r"\d+\s*\.?", c)]
                if not celdas or any(clave(c) in ("departamento", "fechadeinicio") for c in celdas):
                    continue
                if FECHA.match(celdas[0]) and len(celdas) >= 4:
                    filas[seccion].append({"inicio": celdas[0], "dep": celdas[1],
                                           "caso": " ".join(celdas[2:-1]), "tipo": celdas[-1]})
                elif filas[seccion]:  # fila partida entre páginas o celdas
                    filas[seccion][-1]["caso"] += " " + " ".join(celdas)
    return filas


# Lectura alternativa desde el .txt, para los reportes en que pymupdf no detecta
# las tablas: cada caso es "fecha / departamento / denominación (1+ líneas) / tipo".
LINEA_TIPO = re.compile(
    r"^(socio ?ambiental|sociambiental|(por )?asuntos de gobierno (nacional|regional|local)"
    r"|comunal|laboral|demarcaci[oó]n territorial|(por )?otros asuntos|electoral"
    r"|cultivo ilegal de hoja de coca|(por )?asuntos de administraci[oó]n de justicia"
    r"|conflictos en universidades)\.?$", re.I)
SECCION_TXT = {
    "sin_hechos": (r"ACTIVOS QUE NO REGISTRARON HECHOS DURANTE",
                   r"CONFLICTOS REACTIVADOS|DETALLE DE LOS CONFLICTOS LATENTES"),
    "latentes": (r"DETALLE DE LOS CONFLICTOS LATENTES",
                 r"PASADO DE ESTADO ACTIVO A LATENTE|CASOS QUE SALIERON"),
}
DECLARADO = {
    "sin_hechos": r"(\d+) casos activos que no presentaron",
    "latentes": r"existencia de (\d+) conflictos latentes",
}


def tablas_txt(info):
    txt = DIR_ORIG / "textos" / f"reporte_{int(info['numero']):03d}.txt"
    lineas = [l.strip() for l in txt.read_text(encoding="utf-8").splitlines()]
    filas, declarado = {}, {}
    for seccion, (ini, fin) in SECCION_TXT.items():
        i0 = next((i for i, l in enumerate(lineas) if re.search(ini, l)
                   and not l.startswith("Pág")), None)
        i1 = next((i for i, l in enumerate(lineas) if i0 is not None and i > i0
                   and re.search(fin, l)), len(lineas))
        filas[seccion] = []
        if i0 is None:
            continue
        m = re.search(DECLARADO[seccion], " ".join(lineas[i0:i0 + 4]))
        declarado[seccion] = int(m.group(1)) if m else None
        actual = None
        for l in lineas[i0 + 1:i1]:
            if not l or RUIDO.match(l) or l.startswith("=== PAGINA") or re.fullmatch(r"\d+\s*\.", l):
                continue
            if FECHA.match(l):
                actual = {"inicio": l, "dep": "", "caso": "", "tipo": ""}
                filas[seccion].append(actual)
            elif actual is None or actual["tipo"]:
                continue
            elif not actual["dep"]:
                actual["dep"] = l
            elif LINEA_TIPO.match(l) and actual["caso"]:
                actual["tipo"] = l
            else:
                actual["caso"] = (actual["caso"] + " " + l).strip()
                # A veces la denominación y el tipo vienen en la misma línea.
                for k in range(1, 6):
                    cola = " ".join(actual["caso"].split()[-k:])
                    if LINEA_TIPO.match(cola) and len(actual["caso"]) > len(cola):
                        actual["caso"] = actual["caso"][:-len(cola)].strip()
                        actual["tipo"] = cola
                        break
    return filas, declarado


def elegir_tabla(por_tablas, por_texto, declarado):
    """Usa la lectura de tablas salvo que el texto cuadre mejor con lo que declara la sección."""
    if declarado is None:
        return por_tablas if len(por_tablas) >= len(por_texto) else por_texto
    return min([por_tablas, por_texto], key=lambda f: abs(len(f) - declarado))


def filas_de_tabla(info, filas_tabla, estado):
    salida = []
    for r in filas_tabla:
        dep = departamento(r["dep"]) or r["dep"]
        fila = fila_base(info, estado, dep, r["tipo"])
        fila.update({"caso": r["caso"].replace(" - -", " -").strip(),
                     "sin_hechos_en_mes": True if estado == "activo" else ""})
        salida.append(fila)
    return salida


# ---------------------------------------------------------------- HTML (N° 271)

def casos_html(info):
    ruta = DIR_ORIG / "defensoria" / f"reporte_{int(info['numero']):03d}.html"
    s = BeautifulSoup(ruta.read_bytes(), "html.parser")
    filas = []
    for card in s.select("div.caso-card"):
        nombre = card.select_one(".caso-nombre").get_text(" ", strip=True)
        m = re.search(r"\(([^()]+)\)\s*$", nombre)
        dep = departamento(m.group(1)) if m else None
        tipo = card.select_one(".caso-tipo").get_text(" ", strip=True).replace("Tipo:", "")
        chips = {c.select_one(".caso-chip-label").get_text(strip=True).rstrip(":"):
                 c.get_text(" ", strip=True).split(":", 1)[-1].strip()
                 for c in card.select(".caso-chip") if c.select_one(".caso-chip-label")}
        caso = re.sub(r"\s*\([^()]+\)\s*$", "", nombre)  # si la ficha no trae "Caso:"
        for campo in card.select(".ficha-campo"):
            if campo.select_one(".ficha-lbl").get_text(strip=True).startswith("Caso"):
                caso = campo.select_one(".ficha-val").get_text(" ", strip=True)
        banner = card.select_one(".dialogo-banner")
        banner = banner.get_text(" ", strip=True).upper() if banner else ""
        fila = fila_base(info, "activo", dep or (m.group(1) if m else ""), tipo)
        fila.update({"codigo": card.get("data-codigo", ""), "caso": caso,
                     "ubicacion": chips.get("Ubicación", ""),
                     "hay_dialogo": "no" if "NO HAY" in banner else "si" if "HAY" in banner else "",
                     "sin_hechos_en_mes": False})
        filas.append(fila)

    for tr in s.select("tr.reg-filter-row"):
        pagina = tr.find_parent("div", class_="page").get("id", "")
        estado = ("activo" if "sin-hechos" in pagina
                  else "latente" if "latentes" in pagina else None)
        if not estado:
            continue
        celdas = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        dep = departamento(tr.get("data-region", "")) or tr.get("data-region", "")
        fila = fila_base(info, estado, dep, tr.get("data-tipo", "") or celdas[-1])
        fila.update({"caso": celdas[3] if len(celdas) > 3 else "",
                     "sin_hechos_en_mes": True if estado == "activo" else ""})
        filas.append(fila)
    return filas


# ---------------------------------------------------------------- principal

def main():
    with open(CATALOGO, encoding="utf-8") as f:
        catalogo = [r for r in csv.DictReader(f) if PRIMERO <= int(r["numero"]) <= ULTIMO]
    with open(OFICIAL, encoding="utf-8") as f:
        oficial = {r["reporte_n"]: r for r in csv.DictReader(f)}

    todas, control = [], []
    for info in catalogo:
        if info["url"].endswith(".html"):
            filas = casos_html(info)
        else:
            por_tablas = tablas_pdf(info)
            por_texto, declarado = tablas_txt(info)
            tablas = {s: elegir_tabla(por_tablas[s], por_texto[s], declarado.get(s))
                      for s in por_tablas}
            print(info["numero"], {s: (len(por_tablas[s]), len(por_texto[s]), declarado.get(s))
                                   for s in por_tablas})
            filas = (fichas_pdf(info) + filas_de_tabla(info, tablas["sin_hechos"], "activo")
                     + filas_de_tabla(info, tablas["latentes"], "latente"))
        todas += filas
        act = sum(f["estado"] == "activo" for f in filas)
        lat = sum(f["estado"] == "latente" for f in filas)
        sh = sum(f["sin_hechos_en_mes"] is True for f in filas)
        of = oficial.get(info["numero"], {})
        control.append((info["numero"], info["anio"], info["mes"], act - sh, sh, act,
                        of.get("activos", ""), lat, of.get("latentes", "")))

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(todas)

    print(f"{len(todas)} filas -> {SALIDA}")
    print("N°  año mes | fichas sin_hechos activos oficial | latentes oficial")
    for n, a, m, fi, sh, act, oa, lat, ol in control:
        marca = "" if (str(act) == str(oa).split(".")[0] and str(lat) == str(ol).split(".")[0]) else "  <-- no cuadra"
        print(f"{n} {a} {m:>2} | {fi:>6} {sh:>10} {act:>7} {oa:>7} | {lat:>8} {ol:>7}{marca}")


if __name__ == "__main__":
    main()

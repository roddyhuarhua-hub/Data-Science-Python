"""Descarga los Reportes Mensuales de Conflictos Sociales de la Defensoría del Pueblo.

Fuente: el buscador de https://www.defensoria.gob.pe enlaza cada reporte a una
página /documentos/... que contiene el archivo del reporte (PDF hasta 2025;
desde 2026 la Defensoría publica el reporte como un archivo .html).

Pasos:
1. Recolecta las páginas /documentos/ que devuelve el buscador del sitio.
2. En cada página busca el archivo del reporte y deduce su número.
3. Guarda el catálogo en datos/originales/catalogo_reportes.csv
   (numero, anio, mes, url, fecha_descarga); los números sin archivo quedan con url vacía.
4. Descarga cada archivo a datos/originales/defensoria/ (no repite descargas).
5. Extrae el texto a datos/originales/textos/reporte_NNN.txt, con una línea
   "=== PAGINA n ===" antes de cada página (en los HTML, cada <div class="page">).

Uso:  python tarea_3/scripts/obtener_datos.py
"""

import csv
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymupdf
import requests
from bs4 import BeautifulSoup

BASE = "https://www.defensoria.gob.pe"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    )
}
BUSQUEDAS = ["reporte mensual de conflictos sociales", "reporte de conflictos sociales"]

# El N° 131 corresponde a enero de 2015 y la numeración avanza un número por mes.
NUMERO_INICIAL, ANIO_INICIAL = 131, 2015
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

RAIZ = Path(__file__).resolve().parents[1]
DIR_ORIGINALES = RAIZ / "datos" / "originales"
DIR_ARCHIVOS = DIR_ORIGINALES / "defensoria"
DIR_TEXTOS = DIR_ORIGINALES / "textos"
CATALOGO = DIR_ORIGINALES / "catalogo_reportes.csv"

# Palabras que delatan un archivo que no es el reporte mensual en sí.
NO_MENSUAL = re.compile(r"anexo|adjunto|especial|infograf|resumen|nota|np-", re.I)

sesion = requests.Session()
sesion.headers.update(HEADERS)


def get(url, **kwargs):
    for intento in range(4):
        try:
            r = sesion.get(url, timeout=120, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if intento == 3:
                raise
            time.sleep(2 ** (intento + 1))


def mes_anio(numero):
    k = numero - NUMERO_INICIAL
    return ANIO_INICIAL + k // 12, k % 12 + 1


def numero_en(texto):
    """Número de reporte dentro de un título o nombre de archivo (o None)."""
    texto = unquote(texto)
    patrones = [
        r"RCS[_-](\d{3})",
        r"N(?:[.°ºo\s_-]|&#176;)*\s*(\d{2,3})\b",
        r"reporte[-_](\d{2,3})\b",
    ]
    for p in patrones:
        m = re.search(p, texto, re.I)
        if m:
            return int(m.group(1))
    return None


def enlaces_globales():
    """Archivos enlazados en todo el sitio (menú, pie): se ignoran."""
    s = BeautifulSoup(get(BASE + "/").text, "html.parser")
    return {a["href"] for a in s.find_all("a", href=True)}


def paginas_documentos():
    paginas = {}
    for q in BUSQUEDAS:
        for p in range(1, 30):
            url = f"{BASE}/page/{p}/" if p > 1 else BASE + "/"
            try:
                r = get(url, params={"s": q})
            except requests.HTTPError:
                break
            s = BeautifulSoup(r.text, "html.parser")
            nuevas = 0
            for a in s.find_all("a", href=True):
                if "/documentos/" in a["href"] and a["href"] not in paginas:
                    paginas[a["href"]] = a.get_text(" ", strip=True)
                    nuevas += 1
            if nuevas == 0:
                break
            time.sleep(0.5)
    return paginas


def archivos_de(url_pagina, globales):
    s = BeautifulSoup(get(url_pagina).text, "html.parser")
    titulo = s.find("h1").get_text(" ", strip=True) if s.find("h1") else ""
    archivos = []
    for a in s.find_all("a", href=True):
        h = a["href"]
        if h in globales or "/wp-content/uploads/" not in h:
            continue
        if re.search(r"\.pdf$", h, re.I) or re.search(r"RCS_\d+.*\.html?$", h, re.I):
            if h not in archivos:
                archivos.append(h)
    return titulo, archivos


def recolectar_catalogo():
    globales = enlaces_globales()
    candidatos = {}  # numero -> lista de urls
    paginas = paginas_documentos()
    print(f"{len(paginas)} páginas /documentos/ encontradas")
    for url_pagina, titulo_busqueda in paginas.items():
        n_titulo = numero_en(titulo_busqueda)
        if n_titulo is not None and n_titulo < NUMERO_INICIAL:
            continue  # reporte anterior a 2015
        titulo, archivos = archivos_de(url_pagina, globales)
        time.sleep(0.5)
        n_titulo = numero_en(titulo) or n_titulo
        for url in archivos:
            nombre = Path(urlparse(url).path).name
            if NO_MENSUAL.search(unquote(nombre)):
                continue
            n = numero_en(nombre)
            if n is None and len(archivos) == 1:
                n = n_titulo
            if n is None or n < NUMERO_INICIAL:
                continue
            candidatos.setdefault(n, []).append(url)
    return candidatos


def elegir(urls):
    """Si hay varias versiones del mismo reporte, se queda con la más reciente."""
    return sorted(set(urls), key=lambda u: (urlparse(u).path.split("/")[3:5], u))[-1]


def nombre_local(numero, url):
    ext = Path(urlparse(url).path).suffix.lower() or ".pdf"
    return DIR_ARCHIVOS / f"reporte_{numero:03d}{ext}"


def descargar(url, destino):
    r = get(url)
    destino.write_bytes(r.content)


def texto_pdf(ruta):
    partes = []
    with pymupdf.open(ruta) as doc:
        for i, pagina in enumerate(doc, start=1):
            partes.append(f"=== PAGINA {i} ===\n{pagina.get_text()}")
    return "\n".join(partes)


def texto_html(ruta):
    s = BeautifulSoup(ruta.read_bytes(), "html.parser")
    for x in s(["script", "style", "noscript"]):
        x.decompose()
    paginas = [p for p in s.select("div.page")
               if not p.find_parent("div", class_="page")]
    for p in paginas:
        p.extract()
    # Lo que queda fuera de los div.page (portada y resumen) va como página 1.
    bloques = [s.get_text("\n", strip=True)] + [p.get_text("\n", strip=True) for p in paginas]
    return "\n".join(f"=== PAGINA {i} ===\n{b}" for i, b in enumerate(bloques, start=1))


def leer_catalogo_previo():
    if not CATALOGO.exists():
        return {}
    with open(CATALOGO, encoding="utf-8") as f:
        return {int(r["numero"]): r for r in csv.DictReader(f)}


def main():
    for d in (DIR_ARCHIVOS, DIR_TEXTOS):
        d.mkdir(parents=True, exist_ok=True)

    candidatos = recolectar_catalogo()
    previo = leer_catalogo_previo()
    ultimo = max(candidatos)
    filas = []
    for n in range(NUMERO_INICIAL, ultimo + 1):
        anio, mes = mes_anio(n)
        url = elegir(candidatos[n]) if n in candidatos else ""
        fecha = previo.get(n, {}).get("fecha_descarga", "") if url else ""
        if url:
            destino = nombre_local(n, url)
            if not destino.exists():
                print(f"Descargando N° {n} ({MESES[mes - 1]} {anio})")
                descargar(url, destino)
                fecha = date.today().isoformat()
                time.sleep(1)
            fecha = fecha or date.today().isoformat()
            txt = DIR_TEXTOS / f"reporte_{n:03d}.txt"
            if not txt.exists():
                texto = texto_pdf(destino) if destino.suffix == ".pdf" else texto_html(destino)
                txt.write_text(texto, encoding="utf-8")
        else:
            print(f"Falta el N° {n} ({MESES[mes - 1]} {anio})")
        filas.append({"numero": n, "anio": anio, "mes": mes, "url": url,
                      "fecha_descarga": fecha})

    with open(CATALOGO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["numero", "anio", "mes", "url", "fecha_descarga"])
        w.writeheader()
        w.writerows(filas)
    print(f"Catálogo: {len(filas)} filas, {sum(1 for f in filas if f['url'])} con archivo")


if __name__ == "__main__":
    main()

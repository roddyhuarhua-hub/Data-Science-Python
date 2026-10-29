"""Arma el catálogo de recursos del portal de datos abiertos del OEFA (plataforma Junar).

Recorre /search/ página por página y luego abre cada vista para leer su guid,
el id del datastream y la revisión que usa la URL de descarga CSV.

Uso: uv run python scripts/catalogo_oefa.py  (desde tarea_4/)
"""

import csv
import html
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://datosabiertos.oefa.gob.pe"
SALIDA = Path(__file__).resolve().parent.parent / "datos" / "catalogo_oefa_crudo.csv"
RECURSOS = "['ds', 'vz', 'db', 'st']"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (tarea académica)"})
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if intento == 3:
                raise
            time.sleep(2 ** (intento + 1))
    return ""


def limpiar(texto: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", texto)).split())


def buscar_pagina(n: int) -> list[dict]:
    q = urllib.parse.urlencode({"q": "%", "page": n, "category": "", "resource": RECURSOS, "account": ""})
    pagina = get(f"{BASE}/search/?{q}")
    resultados = []
    for panel in re.findall(r'<div class="panel clearfix">(.*?)</div>', pagina, re.S):
        enlace = re.search(r'<h2>\s*<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', panel, re.S)
        if not enlace:
            continue
        categorias = [limpiar(c) for c in re.findall(r'<li>\s*<a [^>]*>(.*?)</a>', panel, re.S)]
        descripcion = re.search(r"</h2>\s*<p>(.*?)</p>", panel, re.S)
        resultados.append({
            "titulo": limpiar(enlace.group(2)),
            "categoria": "; ".join(categorias),
            "descripcion_corta": limpiar(descripcion.group(1)) if descripcion else "",
            "url_vista": enlace.group(1).replace("http://", "https://", 1),
        })
    return resultados


def detalle(url_vista: str) -> dict:
    pagina = get(url_vista)

    def campo(nombre: str) -> str:
        m = re.search(rf'\b{nombre}:\s*"([^"]*)"', pagina)
        return m.group(1) if m else ""

    # data.csv entrega a lo más 1,000 filas por página y 10,000 en total;
    # el archivo original completo está en /datasets/<id>-<slug>.download/
    csv_rel = campo("exportCSVURL")
    original = re.search(r'href="(/datasets/[^"]+\.download/)"', pagina)
    archivo = re.search(r"Data collected from:\s*(?:<[^>]+>\s*)*([^<]+?)\s*<", pagina)
    publicado = re.search(r"Last published:\s*(?:<[^>]+>\s*)*([^<]+?)\s*<", pagina)
    return {
        "datastream_id": campo("datastream_id"),
        "revision_id": campo("revision_id"),
        "guid": campo("guid"),
        "url_csv": f"{BASE}{csv_rel}" if csv_rel else "",
        "url_original": f"{BASE}{original.group(1)}" if original else "",
        "archivo_original": html.unescape(archivo.group(1)) if archivo else "",
        "ultima_publicacion": publicado.group(1) if publicado else "",
    }


def main() -> None:
    filas, vistos, n = [], set(), 1
    while True:
        resultados = [r for r in buscar_pagina(n) if r["url_vista"] not in vistos]
        if not resultados:
            break
        for r in resultados:
            vistos.add(r["url_vista"])
            r.update(detalle(r["url_vista"]) if "/dataviews/" in r["url_vista"] else {})
            filas.append(r)
        print(f"página {n}: {len(resultados)} recursos")
        n += 1

    columnas = ["datastream_id", "revision_id", "guid", "titulo", "categoria",
                "descripcion_corta", "url_vista", "url_csv", "url_original",
                "archivo_original", "ultima_publicacion"]
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} recursos -> {SALIDA}")


if __name__ == "__main__":
    main()

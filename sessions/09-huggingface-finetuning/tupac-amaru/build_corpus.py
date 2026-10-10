"""Build a text corpus about Túpac Amaru II from open sources.

Sources
- Congreso del Perú, Colección Bicentenario: 7 volumes of "La Rebelión de Túpac Amaru II".
  The flipbook viewer publishes the OCR text per page in mobile/javascript/search_config.js
  (variable `textForPages`), so no PDF download is needed.
- PUCP, Revista del Instituto Riva-Agüero: article by S. O'Phelan (PDF, parsed with pypdf).
- Allpanchis (UCSP, CC BY 4.0): 3 articles on Túpac Amaru; metadata read from each article page.

Output: data/tupac_amaru_corpus.csv  (one row per page: fuente, documento, pagina, url, texto, rol,
        texto_fuente, notas)

`rol` separates what is a primary source from what is not:
- fuente_primaria      documents of the period (letters, trials, reports, ...)
- paratexto_editorial  front matter of the Congreso volumes (cover, credits, index, institutional
                       presentations, prologues by Valcárcel [1st ed.] and Walker [2nd ed.], the editor's
                       "Presentación del volumen" by Huerto) and the closing colophon/acknowledgements
- articulo_academico   journal articles (Allpanchis, PUCP)
Within primary-source pages, footnotes (editors' notes such as "[Nota del editor de la primera edición]"
and archive citations) sit below a line of underscores. They are split off:
- texto_fuente  page body, without footnotes  (use this for analysis of the sources)
- notas         the footnotes
Nothing is deleted: `texto` keeps the full page. Filter on `rol` to work only with primary sources.
Limit: a footnote that continues on the next page loses its separator and stays in `texto_fuente`.

Usage:  python build_corpus.py
"""
import html
import re
import time
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from pypdf import PdfReader

OUT = Path(__file__).parent / "data" / "tupac_amaru_corpus.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (research; corpus building for personal study)"}
CONGRESO = "https://www3.congreso.gob.pe/Docs/FondoEditorial/bicentenario/Tupac_Amaru_{n}"
PUCP_PDF = "https://revistas.pucp.edu.pe/index.php/revistaira/article/download/23744/22662"
ALLPANCHIS = "https://revistas.ucsp.edu.pe/index.php/Allpanchis/article/view/{id}"
ALLPANCHIS_IDS = [1096, 868, 1138]  # Huertas 1978; Religión y justicia en Túpac Amaru; Revolución tupamarista
MIN_CHARS = 80  # drop blank / near-empty pages

# First page of primary-source material in each Congreso volume. Everything before it is editorial front
# matter. Boundaries were read page by page (see the first page of each volume):
#   1: p.46 "Representación de la ciudad del Cuzco, 1768"   2: p.23 first "partida" (Antecedentes)
#   3: p.26 "Relación del más horrendo atentado..."          4: p.30 "Versos realistas"
#   5: p.13 "Defensa de D. Juan Manuel Moscoso..."           6: p.15 "Remisión de las causas"
#   7: p.11 "[Causa seguida contra Francisco Túpac Amaru...]"
INICIO_FUENTES = {1: 46, 2: 23, 3: 26, 4: 30, 5: 13, 6: 15, 7: 11}
SEP_NOTAS = re.compile(r"_{6,}")
COLOFON = re.compile(r"esta nueva edici.n no ser.a posible|este libro se termin. de editar", re.I)


def clean(text: str) -> str:
    text = text.replace("﻿", "").replace("\x00", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_js_array(src: str) -> list[str]:
    """Parse a JS array of strings without json (JS allows escapes JSON rejects)."""
    simple = {"n": " ", "t": " ", "r": " ", "b": "", "f": ""}

    def unescape(m: re.Match) -> str:
        code = m.group(1)
        if code[0] in "xu" and len(code) > 1:
            return chr(int(code[1:], 16))
        return simple.get(code[0], code[0])  # \' \" \\ \/ and unknown -> the char itself

    escape = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)", re.S)
    items = re.findall(r'"((?:[^"\\]|\\.)*)"', src, flags=re.S)
    return [escape.sub(unescape, item) for item in items]


def congreso_volume(n: int) -> list[dict]:
    base = CONGRESO.format(n=n)
    url = f"{base}/mobile/javascript/search_config.js"
    raw = requests.get(url, headers=HEADERS, timeout=120).content.decode("utf-8", "replace")
    match = re.search(r"textForPages\s*=\s*(\[.*\])\s*;?", raw, flags=re.S)
    if not match:
        raise ValueError(f"textForPages not found in volume {n}")
    pages = parse_js_array(match.group(1))
    return [
        {
            "fuente": "Congreso del Perú - Colección Bicentenario",
            "documento": f"La Rebelión de Túpac Amaru II, vol. {n}",
            "pagina": i,
            "url": f"{base}/index.html",
            "texto": clean(t),
        }
        for i, t in enumerate(pages, start=1)
    ]


def pucp_article() -> list[dict]:
    pdf = requests.get(PUCP_PDF, headers=HEADERS, timeout=120).content
    reader = PdfReader(BytesIO(pdf))
    return [
        {
            "fuente": "PUCP - Revista del Instituto Riva-Agüero",
            "documento": "O'Phelan, La gran rebelión de Túpac Amaru II y la temprana independencia del Perú",
            "pagina": i,
            "url": PUCP_PDF,
            "texto": clean(page.extract_text() or ""),
        }
        for i, page in enumerate(reader.pages, start=1)
    ]


def meta(page: str, name: str) -> str:
    m = re.search(rf'<meta name="{name}" content="([^"]*)"', page)
    return html.unescape(m.group(1)).strip() if m else ""


def allpanchis_article(article_id: int) -> list[dict]:
    url = ALLPANCHIS.format(id=article_id)
    page = requests.get(url, headers=HEADERS, timeout=60).text
    title, author, year = meta(page, "citation_title"), meta(page, "citation_author"), meta(page, "citation_date")[:4]
    pdf = requests.get(meta(page, "citation_pdf_url"), headers=HEADERS, timeout=120).content
    reader = PdfReader(BytesIO(pdf))
    return [
        {
            "fuente": "Allpanchis (UCSP) - CC BY 4.0",
            "documento": f"{author} ({year}), {title}",
            "pagina": i,
            "url": url,
            "texto": clean(p.extract_text() or ""),
        }
        for i, p in enumerate(reader.pages, start=1)
    ]


def asignar_rol(fila) -> str:
    vol = re.search(r"vol\. (\d)", fila["documento"])
    if not vol:
        return "articulo_academico"
    if fila["pagina"] < INICIO_FUENTES[int(vol.group(1))] or COLOFON.search(fila["texto"]):
        return "paratexto_editorial"
    return "fuente_primaria"


def separar_notas(fila) -> tuple[str, str]:
    if fila["rol"] != "fuente_primaria":
        return fila["texto"], ""
    partes = SEP_NOTAS.split(fila["texto"])
    return partes[0].strip(), " ".join(p.strip() for p in partes[1:])


def main() -> None:
    rows: list[dict] = []
    for n in range(1, 8):
        try:
            vol = congreso_volume(n)
            print(f"Congreso vol. {n}: {len(vol)} páginas")
            rows += vol
        except Exception as exc:  # keep going if one volume fails
            print(f"Congreso vol. {n}: ERROR {exc}")
        time.sleep(1)
    try:
        art = pucp_article()
        print(f"PUCP artículo: {len(art)} páginas")
        rows += art
    except Exception as exc:
        print(f"PUCP artículo: ERROR {exc}")

    for article_id in ALLPANCHIS_IDS:
        try:
            art = allpanchis_article(article_id)
            print(f"Allpanchis {article_id}: {len(art)} páginas")
            rows += art
        except Exception as exc:
            print(f"Allpanchis {article_id}: ERROR {exc}")
        time.sleep(1)

    df = pd.DataFrame(rows)
    df = df[df["texto"].str.len() >= MIN_CHARS].reset_index(drop=True)
    df["rol"] = df.apply(asignar_rol, axis=1)
    df[["texto_fuente", "notas"]] = df.apply(lambda f: pd.Series(separar_notas(f)), axis=1)
    df["caracteres"] = df["texto"].str.len()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n{len(df)} páginas con texto -> {OUT}")
    print(df.groupby("documento")["caracteres"].agg(["count", "sum"]))
    print(df.pivot_table(index="rol", values="caracteres", aggfunc=["count", "sum"]))


if __name__ == "__main__":
    main()

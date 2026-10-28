"""Cifras que la propia Defensoría declara en cada Reporte Mensual de Conflictos Sociales.

Lee los textos de datos/originales/textos/reporte_NNN.txt (generados por
obtener_datos.py) y busca, en la portada y en la sección de información
estadística, las cifras oficiales del mes:

- registrados, activos, latentes
- socioambientales (número) y pct_socioambientales (% del total registrado)
- pct_mineria y pct_hidrocarburos: % de los conflictos socioambientales
  vinculados a minería e hidrocarburos, tal como lo dice el reporte
- en_dialogo, nuevos, resueltos
- fallecidos y heridos del mes (fila TOTAL del cuadro "Muertos y/o heridos")

Lo que no se encuentra queda vacío: no se imputa nada.
pagina_fuente indica la página del .txt donde se leyó cada cifra (campo:página).

Salida: datos/procesados/resumen_oficial.csv
Uso:    python tarea_3/scripts/extraer_resumen_oficial.py
"""

import csv
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIR_TEXTOS = RAIZ / "datos" / "originales" / "textos"
CATALOGO = RAIZ / "datos" / "originales" / "catalogo_reportes.csv"
SALIDA = RAIZ / "datos" / "procesados" / "resumen_oficial.csv"

COLUMNAS = ["reporte_n", "anio", "mes", "registrados", "activos", "latentes",
            "socioambientales", "pct_socioambientales", "pct_mineria",
            "pct_hidrocarburos", "en_dialogo", "nuevos", "resueltos",
            "fallecidos", "heridos", "pagina_fuente"]

PALABRAS = {
    "no": 0, "cero": 0, "ninguno": 0, "ninguna": 0, "ningún": 0, "un": 1, "uno": 1, "una": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "dieciséis": 16, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21,
    "veintidós": 22, "veintidos": 22, "veintitrés": 23, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25,
}
NUM = r"(\d+|" + "|".join(sorted(PALABRAS, key=len, reverse=True)) + r")"


def a_numero(token):
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return PALABRAS.get(token)


def a_pct(token):
    return float(token.replace(",", "."))


# Cada campo se prueba con varios patrones, en orden de preferencia.
# Todos se aplican al texto con los espacios normalizados.
PATRONES = {
    "registrados": [
        r"(\d+) conflictos registrados en el mes",
        r"Se da cuenta de (\d+) conflictos sociales",
        r"(\d+) Conflictos registrados",
    ],
    "activos": [
        r"(\d+) (?:casos|conflictos) activos \(",
        r"Se da cuenta de \d+ conflictos sociales: (\d+) activos",
        r"Se da cuenta de (\d+) conflictos activos",
        r"(\d+) Conflictos activos \d+ Conflictos latentes",
    ],
    "latentes": [
        r"(\d+) (?:casos|conflictos) latentes \(",
        r"(\d+) latentes",
        r"(\d+) conflictos latentes",
        r"(\d+) Conflictos latentes",
    ],
    "en_dialogo": [
        r"(\d+) conflictos en proceso de di[aá]logo",
        r"Casos en proceso de di[aá]logo: (\d+)",
        r"de los cuales (\d+) est[aá]n en (?:proceso de )?di[aá]logo",
        r"Son tratados (\d+) casos mediante procesos de di[aá]logo",
        r"(\d+) En proceso de di[aá]logo",
    ],
    "nuevos": [
        r"Casos nuevos: " + NUM + r"\b",
        r"Conflictos NUEVOS • ?" + NUM + r" casos? nuevos?",
        r"Casos NUEVOS • ?" + NUM + r" casos? nuevos?",
        r"(?:SURGIERON|SURGIÓ) " + NUM + r" (?:NUEVOS? )?CONFLICTOS? SOCIAL(?:ES)?",
        r"Casos nuevos incorporados en el mes: " + NUM,
        r"(\d+) Conflictos nuevos",
        r"(Ning[uú]n) (?:nuevo conflicto|conflicto nuevo|caso nuevo)",
        r"(NO) SURGIERON NUEVOS CONFLICTOS",
    ],
    "resueltos": [
        r"Casos resueltos: " + NUM + r"\b",
        r"Conflictos RESUELTOS • ?" + NUM + r" casos? resueltos?",
        r"Conflictos RESUELTOS • ?(Ning[uú]n) caso",
        r"Casos resueltos en el mes: " + NUM,
        r"(\d+) Casos resueltos",
        r"• ?" + NUM + r" (?:casos?|conflictos?) (?:fueron |fue )?resueltos?",
        r"(Ning[uú]n) (?:caso|conflicto) (?:fue )?resuelto",
        r"CONFLICTOS RESUELTOS Durante el mes se resolvi(?:eron|ó) " + NUM + r"\b",
        r"• ?" + NUM + r" conflictos? se resolvi(?:eron|ó)",
        r"CONFLICTOS RESUELTOS Durante el mes (no) se resolvi",
        r"CONFLICTOS RESUELTOS Durante el mes (ning[uú]n) conflicto",
    ],
}

# Socioambientales y su desagregado por actividad. El último patrón de cada lista
# corresponde al formato HTML de 2026.
PATRONES_SOCIO = [
    r"socioambientales ocuparon el (?P<pct>[\d.,]+) ?% \((?P<n>\d+) ?casos\)",
    r"Socioambiental \(Minería: \d+ casos, [\d.]+%\) (?P<n>\d+) casos \((?P<pct>[\d.]+)%\)",
]
PATRONES_MINERIA = [
    r"el ([\d.,]+) ?% \( ?\d+ ?casos\) corresponde a conflictos relacionados a la actividad minera",
    r"Por sector de actividad Minería: \d+ \(([\d.]+)%\)",
]
PATRONES_HIDRO = [
    r"actividades hidrocarbur\w+ con (?:el )?([\d.,]+) ?%",
    r"Por sector de actividad Minería: \d+ \([\d.]+%\) Hidrocarburos: \d+ \(([\d.]+)%\)",
]
RE_VIOLENCIA = re.compile(r"MUERTOS Y/O HERIDOS EN CONFLICTOS SOCIALES", re.I)
RE_TOTAL = re.compile(r"TOTAL ((?:(?:\d+|-) ){5}(?:\d+|-))")
RE_271_VIOLENCIA = re.compile(r"(\d+) / (\d+) Fallecidos / heridos")


def paginas(ruta):
    texto = ruta.read_text(encoding="utf-8")
    partes = re.split(r"=== PAGINA (\d+) ===", texto)
    # partes = ["", "1", texto1, "2", texto2, ...]
    return [(int(partes[i]), re.sub(r"\s+", " ", partes[i + 1]))
            for i in range(1, len(partes), 2)]


def buscar(pags, patron):
    for n, t in pags:
        m = re.search(patron, t, re.I)
        if m:
            return m, n
    return None, None


def extraer(pags):
    fila, fuente = {}, {}

    for campo, patrones in PATRONES.items():
        for patron in patrones:
            m, n = buscar(pags, patron)
            if m:
                valor = a_numero(m.group(1))
                if valor is not None:
                    fila[campo], fuente[campo] = valor, n
                    break

    for patron in PATRONES_SOCIO:
        m, n = buscar(pags, patron)
        if m:
            fila["pct_socioambientales"] = a_pct(m.group("pct"))
            fila["socioambientales"] = int(m.group("n"))
            fuente["socioambientales"] = n
            break
    for campo, patrones in [("pct_mineria", PATRONES_MINERIA),
                            ("pct_hidrocarburos", PATRONES_HIDRO)]:
        for patron in patrones:
            m, n = buscar(pags, patron)
            if m:
                fila[campo], fuente[campo] = a_pct(m.group(1)), n
                break

    # Fila TOTAL del cuadro de muertos y heridos:
    # muertos (total, civiles, PNP/FFAA) y heridos (total, civiles, PNP/FFAA).
    for n, t in pags:
        m = RE_VIOLENCIA.search(t)
        if not m:
            continue
        tot = RE_TOTAL.search(t, m.end())
        if tot:
            valores = tot.group(1).split()
            fila["fallecidos"] = 0 if valores[0] == "-" else int(valores[0])
            fila["heridos"] = 0 if valores[3] == "-" else int(valores[3])
            fuente["fallecidos"] = fuente["heridos"] = n
            break
    if "fallecidos" not in fila:
        m, n = buscar(pags, RE_271_VIOLENCIA.pattern)
        if m:
            fila["fallecidos"], fila["heridos"] = int(m.group(1)), int(m.group(2))
            fuente["fallecidos"] = fuente["heridos"] = n

    fila["pagina_fuente"] = "; ".join(f"{k}:{v}" for k, v in fuente.items())
    return fila


def main():
    with open(CATALOGO, encoding="utf-8") as f:
        catalogo = list(csv.DictReader(f))

    filas = []
    for r in catalogo:
        fila = {"reporte_n": r["numero"], "anio": r["anio"], "mes": r["mes"]}
        txt = DIR_TEXTOS / f"reporte_{int(r['numero']):03d}.txt"
        if txt.exists():
            fila.update(extraer(paginas(txt)))
        filas.append(fila)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)

    print(f"{len(filas)} reportes -> {SALIDA}")
    for c in COLUMNAS[3:-1]:
        vacios = [f["reporte_n"] for f in filas if f.get(c) in (None, "")]
        print(f"{c:22s} vacíos: {len(vacios):3d} {vacios[:15]}")


if __name__ == "__main__":
    main()

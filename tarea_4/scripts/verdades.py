"""Calcula las respuestas esperadas de evaluacion/preguntas.csv por un camino INDEPENDIENTE del agente.

    uv run scripts/verdades.py            # muestra las verdades y completa q09 y q10 en preguntas.csv

No usa el servidor MCP ni las skills:
  - BCRP: llama a la API directamente con httpx (una sola llamada con varias series).
  - ENAHO: lee la sumaria (módulo 34) del zip y pondera por hogar con factor07 × mieperho, el método del INEI.
    Las skills ponderan por persona con facpob07; si las dos cifras coinciden, la verdad queda confirmada por dos
    caminos distintos.
Corre una sola vez, ANTES de evaluar, y no se vuelve a tocar preguntas.csv después de ver resultados.
"""
from __future__ import annotations

import io
import time
import unicodedata
import zipfile
from pathlib import Path

import httpx
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
# Producción de cobre por departamento, anual (BCRP, grupo «Producción de productos mineros según departamentos»)
COBRE = [f"RD155{n}DA" for n in range(16, 33)]          # RD15516DA (Total) a RD15532DA (Tacna)
CCDD = {"ancash": "02", "apurimac": "03", "arequipa": "04", "ayacucho": "05", "cajamarca": "06", "cusco": "08",
        "huancavelica": "09", "huanuco": "10", "ica": "11", "junin": "12", "la libertad": "13", "lima": "15",
        "moquegua": "18", "pasco": "19", "puno": "21", "tacna": "23"}


def sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFD", texto.lower()).encode("ascii", "ignore").decode().strip()


def bcrp(codigos: list[str], desde: str, hasta: str):
    """(url, nombres de las series, periodos). La API ordena las series a su modo: se leen por su nombre."""
    url = f"{API}/{'-'.join(codigos)}/json/{desde}/{hasta}"
    for intento in range(5):
        r = httpx.get(url, timeout=60)
        if r.text.strip().startswith("{"):
            js = r.json()
            break
        time.sleep(3 * (intento + 1))
    else:
        raise SystemExit(f"El BCRP no respondió con JSON: {url}")
    nombres = [s["name"] for s in js["config"]["series"]]
    return url, nombres, js["periods"]


def main() -> None:
    print("== BCRP ==")
    url, nombres, periodos = bcrp(["PM05568XA", "PM05570XA"], "2023", "2024")
    precios = {p["name"]: [float(v) for v in p["values"]] for p in periodos}
    print(url)
    for n, i in zip(nombres, range(len(nombres))):
        print(f"  {n}: 2023 = {precios['2023'][i]:.2f} · 2024 = {precios['2024'][i]:.2f}")
    cobre23, cobre24 = (precios[a][[k for k, n in enumerate(nombres) if "Cobre" in n][0]] for a in ("2023", "2024"))
    print(f"  q01 cobre 2024 = {cobre24:.2f} · q03 variación 2024/2023 = {(cobre24 / cobre23 - 1) * 100:.2f} %")

    url, nombres, periodos = bcrp(COBRE, "2024", "2024")
    print(url)
    valores = periodos[0]["values"]
    prod = {}
    for nombre, v in zip(nombres, valores):
        lugar = nombre.split(" - ")[-1].replace(" (tm.f)", "")          # "Apurimac", "Total"
        try:
            prod[lugar] = float(v)
        except ValueError:
            pass
    total = prod.pop("Total")
    ranking = sorted(prod.items(), key=lambda x: -x[1])
    print(f"  Total nacional 2024: {total:,.1f} tm.f · suma de departamentos: {sum(prod.values()):,.1f}")
    for i, (lugar, v) in enumerate(ranking, 1):
        print(f"  {i:2d}. {lugar:16s} {v:14,.1f}  ({v / total * 100:.1f} %)  ccdd {CCDD[sin_tildes(lugar)]}")
    top5 = [CCDD[sin_tildes(l)] for l, _ in ranking[:5]]
    print(f"  Top 5 (ccdd): {top5}")

    print("\n== ENAHO (sumaria, factor07 × mieperho) ==")
    with zipfile.ZipFile(RAIZ / "datos" / "966-Modulo34.zip") as z:
        interno = min((n for n in z.namelist() if n.lower().endswith(".dta") and "sumaria-2024" in n.lower()),
                      key=len)
        s = pd.read_stata(io.BytesIO(z.read(interno)), convert_categoricals=False)
    s.columns = [c.lower() for c in s.columns]
    s["ccdd"] = s["ubigeo"].astype(str).str.zfill(6).str[:2]
    s["peso"] = s["factor07"] * s["mieperho"]
    s["pobre"] = (s["pobreza"] <= 2).astype(float)

    def tasa(d):
        return (d.pobre * d.peso).sum() / d.peso.sum() * 100

    print(f"  q05 nacional: {tasa(s):.2f} % · q07 extrema: "
          f"{((s.pobreza == 1) * s.peso).sum() / s.peso.sum() * 100:.2f} %")
    print(f"  q06 rural: {tasa(s[s.estrato > 5]):.2f} % · urbana: {tasa(s[s.estrato <= 5]):.2f} %")
    print(f"  q08 Cajamarca: {tasa(s[s.ccdd == '06']):.2f} %")
    q09 = tasa(s[s.ccdd == top5[0]])
    q10 = tasa(s[s.ccdd.isin(top5)])
    print(f"  q09 {ranking[0][0]} (ccdd {top5[0]}): pobreza {q09:.2f} % · producción {ranking[0][1]:,.1f} tm.f")
    print(f"  q10 top 5 juntos {top5}: {q10:.2f} %")

    archivo = RAIZ / "evaluacion" / "preguntas.csv"
    p = pd.read_csv(archivo, dtype={"id": str})
    if p.loc[p.id.isin(["q09", "q10"]), "verdad"].isna().all():
        p.loc[p.id == "q09", ["verdad", "verdad2"]] = [round(q09, 1), round(ranking[0][1], 1)]
        p.loc[p.id == "q10", "verdad"] = round(q10, 1)
        p.to_csv(archivo, index=False)
        print("\nq09 y q10 completadas en evaluacion/preguntas.csv")
    else:
        print("\npreguntas.csv ya tenía q09 y q10: no se cambia (las verdades se fijan una sola vez)")


if __name__ == "__main__":
    main()

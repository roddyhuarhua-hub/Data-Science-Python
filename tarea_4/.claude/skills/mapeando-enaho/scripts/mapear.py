"""Mapa de la pobreza por departamento con la ENAHO.

Uso (desde la raíz del repositorio):
    uv run .claude/skills/mapeando-enaho/scripts/mapear.py
    uv run .claude/skills/mapeando-enaho/scripts/mapear.py --indicador pobre_extremo

Entra:  salidas/personas_2024.parquet (de la skill limpiando-enaho)
        datos/peru_departamental_simple.geojson (se baja solo si falta)
Sale:   mapas/pobreza_departamento.png y mapas/pobreza_departamento_2024.csv

Reglas que no se discuten:
    une por código (ubigeo[:2] con FIRST_IDDP, como texto), nunca por nombre
    · exige 25 departamentos y ninguno sin dato · Lima (15) y Callao (07) separados
    · un color de claro a oscuro, desde 0 · leyenda «% de personas»
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path.cwd()
URL_GEOJSON = ("https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/"
               "sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson")
INDICADORES = {"pobre": "Pobreza monetaria", "pobre_extremo": "Pobreza extrema"}


def leer_limites() -> gpd.GeoDataFrame:
    archivo = RAIZ / "datos" / "peru_departamental_simple.geojson"
    if not archivo.exists():
        archivo.parent.mkdir(exist_ok=True)
        print(f"Bajando límites departamentales a {archivo.relative_to(RAIZ)}")
        urllib.request.urlretrieve(URL_GEOJSON, archivo)
    limites = gpd.read_file(archivo)
    limites["ccdd"] = limites["FIRST_IDDP"].astype(str).str.strip().str.zfill(2)
    return limites


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indicador", choices=INDICADORES, default="pobre")
    ap.add_argument("--anio", type=int, default=2024)
    args = ap.parse_args()

    archivo = RAIZ / "salidas" / f"personas_{args.anio}.parquet"
    if not archivo.exists():
        sys.exit(f"ERROR: falta {archivo.relative_to(RAIZ)}. Usa primero la skill limpiando-enaho.")
    base = pd.read_parquet(archivo)

    # Pobreza ponderada con facpob07 por código de departamento (texto de 2 dígitos)
    base["ccdd"] = base["ubigeo"].astype(str).str.zfill(6).str[:2]
    base["_num"] = base[args.indicador].astype(float) * base["facpob07"]
    t = base.groupby("ccdd").agg(num=("_num", "sum"), peso=("facpob07", "sum"),
                                 encuestados=("facpob07", "size")).reset_index()
    t["pobreza_pct"] = t["num"] / t["peso"] * 100

    limites = leer_limites()
    mapa = limites.merge(t[["ccdd", "pobreza_pct", "encuestados"]], on="ccdd",
                         how="left", validate="1:1")

    # Controles: 25 departamentos, todos con dato, Lima y Callao separados
    sin_dato = mapa.loc[mapa["pobreza_pct"].isna(), "NOMBDEP"].tolist()
    assert len(mapa) == 25, f"Se esperaban 25 departamentos y hay {len(mapa)}"
    assert not sin_dato, f"Departamentos sin dato (revisa la unión por código): {sin_dato}"
    assert {"07", "15"} <= set(mapa["ccdd"]), "Lima (15) y Callao (07) deben ir separados"

    titulo = f"{INDICADORES[args.indicador]} por departamento, Perú {args.anio}"
    fig, ax = plt.subplots(figsize=(7.5, 9.5))
    mapa.plot(column="pobreza_pct", cmap="Reds", vmin=0, vmax=max(50, mapa["pobreza_pct"].max()),
              edgecolor="white", linewidth=0.6, ax=ax, legend=True,
              legend_kwds={"label": "% de personas", "shrink": 0.55})
    for _, fila in mapa.iterrows():
        p = fila.geometry.representative_point()
        oscuro = fila["pobreza_pct"] > 32
        if fila["ccdd"] == "07":  # Callao es pequeño: su etiqueta va afuera, con una línea
            ax.annotate(f"Callao {fila['pobreza_pct']:.1f}", (p.x, p.y), xytext=(p.x - 2.2, p.y),
                        ha="right", va="center", fontsize=7.5, color="#222222",
                        arrowprops={"arrowstyle": "-", "color": "#555555", "lw": 0.6})
            continue
        ax.annotate(f"{fila['pobreza_pct']:.1f}", (p.x, p.y), ha="center", va="center",
                    fontsize=7.5, color="white" if oscuro else "#222222")
    ax.set_axis_off()
    ax.set_title(titulo, loc="left", fontsize=14, fontweight="bold")
    fig.text(0.02, 0.02, f"Fuente: INEI, ENAHO {args.anio}. Ponderado con facpob07; unido por "
             "código de departamento (ubigeo[:2] = FIRST_IDDP).", fontsize=8, color="#555555")

    carpeta = RAIZ / "mapas"
    carpeta.mkdir(exist_ok=True)
    nombre = "pobreza_departamento" if args.indicador == "pobre" else f"{args.indicador}_departamento"
    fig.savefig(carpeta / f"{nombre}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    tabla = mapa[["ccdd", "NOMBDEP", "pobreza_pct", "encuestados"]].rename(
        columns={"NOMBDEP": "departamento"}).sort_values("ccdd")
    tabla.to_csv(carpeta / f"{nombre}_{args.anio}.csv", index=False, float_format="%.2f")

    # Comparación con la referencia del profesor (si existe)
    ref = RAIZ / "referencias" / f"pobreza_departamento_{args.anio}.csv"
    if args.indicador == "pobre" and ref.exists():
        r = pd.read_csv(ref, dtype={"ccdd": str})
        c = tabla.merge(r[["ccdd", "pobreza_pct"]], on="ccdd", suffixes=("", "_ref"))
        c["dif"] = c["pobreza_pct"] - c["pobreza_pct_ref"]
        print(f"Diferencia máxima con la referencia: {c['dif'].abs().max():.2f} puntos")

    orden = tabla.sort_values("pobreza_pct", ascending=False)
    print(titulo)
    print("Más pobreza: " + ", ".join(f"{d} {v:.1f} %" for d, v in
                                      orden.head(3)[["departamento", "pobreza_pct"]].values))
    print("Menos pobreza: " + ", ".join(f"{d} {v:.1f} %" for d, v in
                                        orden.tail(3)[::-1][["departamento", "pobreza_pct"]].values))
    print(f"25 departamentos con dato. Mapa: mapas/{nombre}.png · Tabla: mapas/{nombre}_{args.anio}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())

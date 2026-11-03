"""Tabla y gráfico del informe: producción de cobre y oro 2024 (BCRP, vía el MCP) frente a pobreza 2024 (ENAHO).

    uv run scripts/analisis_minero.py

Entra:  la herramienta produccion_minera_departamental del servidor MCP (se llama en memoria, como Claude Code)
        y salidas/indicadores.csv (de la skill limpiando-enaho)
Sale:   salidas/mineria_pobreza_2024.csv, figuras/cobre_vs_pobreza_2024.png y los agregados que cita el informe.
Une por código de departamento (ccdd), nunca por nombre.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from fastmcp import Client  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "mcp"))
from server import mcp  # noqa: E402


async def produccion(metal: str, anio: int) -> dict:
    async with Client(mcp) as c:
        return (await c.call_tool("produccion_minera_departamental", {"metal": metal, "anio": anio})).data


def tasa(d: pd.DataFrame) -> float:
    return float((d.pobreza_pct * d.poblacion_expandida).sum() / d.poblacion_expandida.sum())


def main() -> None:
    ind = pd.read_csv(RAIZ / "salidas" / "indicadores.csv", dtype={"codigo": str})
    nac = ind.loc[ind.nivel == "nacional", "pobreza_pct"].iloc[0]
    dep = ind[ind.nivel == "departamento"].rename(columns={"codigo": "ccdd", "grupo": "departamento"})
    dep = dep[["ccdd", "departamento", "pobreza_pct", "pobreza_extrema_pct", "poblacion_expandida", "encuestados"]]

    tabla = dep.copy()
    fuentes = {}
    for metal in ("cobre", "oro"):
        r = asyncio.run(produccion(metal, 2024))
        fuentes[metal] = r["fuente"]
        p = pd.DataFrame(r["departamentos"])[["ccdd", "produccion", "participacion_pct", "puesto", "codigo"]]
        p.columns = ["ccdd", f"{metal}_{r['unidad']}", f"{metal}_part_pct", f"{metal}_puesto", f"{metal}_serie"]
        tabla = tabla.merge(p, on="ccdd", how="left", validate="1:1")
    assert len(tabla) == 25, "deben quedar 25 departamentos"
    tabla = tabla.sort_values("cobre_puesto", na_position="last")
    tabla.to_csv(RAIZ / "salidas" / "mineria_pobreza_2024.csv", index=False, float_format="%.2f")

    cu = tabla["cobre_tm.f"].fillna(0)
    top5 = tabla.nsmallest(5, "cobre_puesto")
    print(f"Pobreza nacional (personas, facpob07): {nac:.2f} %")
    print(f"Top 5 cobre ({', '.join(top5.departamento)}): {tasa(top5):.2f} % · "
          f"{top5.poblacion_expandida.sum() / dep.poblacion_expandida.sum() * 100:.1f} % de la población · "
          f"{top5.cobre_part_pct.sum():.1f} % del cobre")
    resto = tabla[~tabla.ccdd.isin(top5.ccdd)]
    print(f"Resto del país (20 departamentos): {tasa(resto):.2f} %")
    print(f"Resto sin Lima ni Callao: {tasa(resto[~resto.ccdd.isin(['15', '07'])]):.2f} %")
    print(f"Con alguna producción de cobre ({(cu > 0).sum()}): {tasa(tabla[cu > 0]):.2f} % · "
          f"sin cobre ({(cu == 0).sum()}): {tasa(tabla[cu == 0]):.2f} %")
    corr = tabla.assign(c=cu)[["c", "pobreza_pct"]].corr(method="spearman").iloc[0, 1]
    print(f"Correlación de Spearman cobre-pobreza (25 departamentos): {corr:.2f}")
    print("\nTop 5 oro:")
    print(tabla.nsmallest(5, "oro_puesto")[["departamento", "oro_grs.f", "oro_part_pct", "pobreza_pct"]]
          .to_string(index=False))
    print("\n" + tabla[["departamento", "cobre_puesto", "cobre_tm.f", "cobre_part_pct", "oro_puesto",
                        "pobreza_pct"]].to_string(index=False))
    print(f"\nFuentes: {fuentes}")

    # Gráfico: producción de cobre (miles de tm.f) contra pobreza, con la línea nacional
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(cu / 1000, tabla.pobreza_pct, s=tabla.poblacion_expandida / 12000, color="#1f4e79", alpha=0.6,
               edgecolor="white")
    for _, f in tabla.iterrows():
        if f["cobre_tm.f"] > 100_000 or f.pobreza_pct > 38 or f.pobreza_pct < 12 or f.poblacion_expandida > 5e6:
            ax.annotate(f.departamento, (f["cobre_tm.f"] / 1000 if pd.notna(f["cobre_tm.f"]) else 0, f.pobreza_pct),
                        xytext=(5, 4), textcoords="offset points", fontsize=8)
    ax.axhline(nac, color="#999999", linestyle="--", linewidth=1)
    ax.text(ax.get_xlim()[1], nac, f" Perú {nac:.1f} %", va="bottom", ha="right", fontsize=8, color="#555555")
    ax.set_xlim(left=-15)
    ax.set_ylim(0, 50)
    ax.set_xlabel("Producción de cobre 2024 (miles de toneladas métricas finas)")
    ax.set_ylabel("Pobreza monetaria 2024 (% de personas)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Los grandes productores de cobre tienen menos pobreza, pero no todos", loc="left",
                 fontsize=12, fontweight="bold")
    fig.text(0.01, 0.01, "Fuente: BCRP, producción de cobre por departamento (RD15516DA-RD15532DA, MINEM); INEI, "
             "ENAHO 2024 ponderada con facpob07. El tamaño del punto es la población.", fontsize=7.5, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RAIZ / "figuras" / "cobre_vs_pobreza_2024.png", dpi=200)
    print("\nsalidas/mineria_pobreza_2024.csv · figuras/cobre_vs_pobreza_2024.png")


if __name__ == "__main__":
    main()

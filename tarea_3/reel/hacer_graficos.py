"""Gráficos de cada escena del reel (1000 x 760 px), hechos con los datos procesados.

Uso (desde la carpeta tarea_3):  python reel/hacer_graficos.py
Guarda reel/recursos/escena_1.png ... escena_6.png (la escena 7 es una captura del dashboard).
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PROC = BASE / "datos" / "procesados"
SALIDA = BASE / "reel" / "recursos"

AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, GRIS = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#898781"
TINTA, TINTA2, REJILLA = "#0b0b0b", "#52514e", "#e1e0d9"
ACTIVIDADES = ["Minería", "Hidrocarburos", "Energía", "Residuos y saneamiento", "Agroindustria y forestal", "Otros"]
COLORES = [AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, GRIS]

plt.rcParams.update({
    "ytick.major.size": 0, "xtick.major.size": 0,
    "font.family": "DejaVu Sans", "font.size": 22, "axes.edgecolor": REJILLA,
    "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 1, "axes.axisbelow": True,
})


def lienzo(titulo):
    fig, ax = plt.subplots(figsize=(10, 7.6), dpi=100)
    fig.patch.set_facecolor("white")
    fig.suptitle(titulo, x=0.05, y=0.96, ha="left", fontsize=27, fontweight="bold", color=TINTA)
    return fig, ax


def guardar(fig, n):
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(SALIDA / f"escena_{n}.png", facecolor="white")
    plt.close(fig)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PROC / "casos_limpios.csv", dtype={"cod_dep": str})
    of = pd.read_csv(PROC / "resumen_oficial.csv").dropna(subset=["registrados"])
    of.loc[of["reporte_n"] == 249, "registrados"] = 194
    of["fecha"] = pd.to_datetime(of["anio"].astype(int).astype(str) + "-" + of["mes"].astype(int).astype(str) + "-01")
    sa = df[df["socioambiental"]]

    # 1. Serie mensual de conflictos registrados (cifra oficial)
    fig, ax = lienzo("Conflictos registrados cada mes")
    ax.fill_between(of["fecha"], of["registrados"], color=AZUL, alpha=0.18, linewidth=0)
    ax.plot(of["fecha"], of["registrados"], color=AZUL, linewidth=3)
    ax.axhline(of["registrados"].mean(), color=NARANJA, linewidth=2, linestyle="--")
    ax.text(of["fecha"].iloc[4], 120, f"promedio: {of['registrados'].mean():.0f} por mes",
            color=NARANJA, fontsize=24, fontweight="bold")
    ax.set_ylim(0, 260)
    ax.grid(axis="x", visible=False)
    guardar(fig, 1)

    # 2. Tipos de conflicto
    tipos = df["tipo"].replace({"Asuntos de gobierno local": "Gobierno local y regional",
                                "Asuntos de gobierno regional": "Gobierno local y regional",
                                "Asuntos de gobierno nacional": "Gobierno nacional"})
    principales = ["Socioambiental", "Gobierno nacional", "Gobierno local y regional", "Comunal"]
    tipos = tipos.where(tipos.isin(principales), "Otros")
    pct = tipos.value_counts(normalize=True).reindex(principales + ["Otros"])[::-1]
    fig, ax = lienzo("¿De qué tipo son los conflictos?")
    barras = ax.barh(pct.index, pct.values, color=[GRIS] * 4 + [AZUL], height=0.62)
    for b, v in zip(barras, pct.values):
        ax.text(v + 0.01, b.get_y() + b.get_height() / 2, f"{v:.0%}", va="center", fontsize=24, color=TINTA, fontweight="bold")
    ax.set_xlim(0, 0.78); ax.set_xticks([]); ax.grid(False)
    guardar(fig, 2)

    # 3. Actividad de los socioambientales
    pct = sa["actividad"].value_counts(normalize=True).reindex(ACTIVIDADES)[::-1]
    fig, ax = lienzo("Conflictos socioambientales por actividad")
    barras = ax.barh(pct.index, pct.values, color=COLORES[::-1], height=0.62)
    for b, v in zip(barras, pct.values):
        ax.text(v + 0.01, b.get_y() + b.get_height() / 2, f"{v:.0%}", va="center", fontsize=24, color=TINTA, fontweight="bold")
    ax.set_xlim(0, 0.75); ax.set_xticks([]); ax.grid(False)
    guardar(fig, 3)

    # 4. Mapa por departamento (promedio mensual de casos socioambientales)
    geo = json.loads((BASE / "web" / "data" / "departamentos.geojson").read_text(encoding="utf-8"))
    meses = df["periodo"].nunique()
    por_dep = sa[sa["cod_dep"].notna()].groupby("cod_dep").size() / meses
    top5 = por_dep.sort_values(ascending=False).head(5).index
    fig, ax = plt.subplots(figsize=(10, 7.6), dpi=100)
    fig.suptitle("Casos socioambientales por departamento", x=0.05, y=0.96, ha="left",
                 fontsize=25, fontweight="bold", color=TINTA)
    cmap = matplotlib.colormaps["Blues"]
    vmax = por_dep.max()
    for f in geo["features"]:
        cod = f["properties"]["ubigeo"]
        valor = por_dep.get(cod, 0)
        partes = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]
        for poligono in partes:
            ax.add_patch(Polygon(poligono[0], closed=True, facecolor=cmap(0.12 + 0.88 * valor / vmax),
                                 edgecolor=NARANJA if cod in top5 else "white", linewidth=3 if cod in top5 else 0.8))
    ax.autoscale_view(); ax.set_aspect("equal"); ax.axis("off")
    nombres = df.dropna(subset=["cod_dep"]).drop_duplicates("cod_dep").set_index("cod_dep")["dep"]
    texto = "\n".join(f"{nombres[c]}: {por_dep[c]:.1f}" for c in top5)
    ax.text(1.0, 0.5, "Los 5 primeros\n" + texto, transform=ax.transAxes, fontsize=21, va="center", ha="left",
            color=TINTA, linespacing=1.5)
    fig.subplots_adjust(left=0.02, right=0.62, top=0.9, bottom=0.02)
    fig.savefig(SALIDA / "escena_4.png", facecolor="white")
    plt.close(fig)

    # 5. Diálogo por año
    con_dato = sa[(sa["con_hechos"]) & sa["dialogo"].isin(["si", "no"])]
    serie = con_dato.groupby("anio")["dialogo"].apply(lambda s: (s == "si").mean())
    fig, ax = lienzo("Casos socioambientales activos con diálogo")
    ax.plot(serie.index, serie.values, color=AZUL, linewidth=4, marker="o", markersize=12,
            markeredgecolor="white", markeredgewidth=2)
    for a in [serie.index[0], serie.index[-1]]:
        ax.text(a, serie[a] + 0.05, f"{serie[a]:.0%}", ha="center", fontsize=26, fontweight="bold", color=TINTA)
    ax.set_ylim(0, 1.05); ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xticks([2015, 2018, 2021, 2024, 2026]); ax.grid(axis="x", visible=False)
    guardar(fig, 5)

    # 6. Nuevos frente a resueltos (cifras oficiales, todos los tipos)
    anual = of.groupby(of["anio"].astype(int))[["nuevos", "resueltos"]].sum()
    fig, ax = lienzo("Conflictos nuevos y resueltos por año")
    x = anual.index.to_numpy()
    ax.bar(x - 0.21, anual["nuevos"], width=0.4, color=NARANJA, label=f"Nuevos ({anual['nuevos'].sum():.0f})")
    ax.bar(x + 0.21, anual["resueltos"], width=0.4, color=AQUA, label=f"Resueltos ({anual['resueltos'].sum():.0f})")
    ax.legend(frameon=False, fontsize=22, loc="upper left")
    ax.set_xticks([2015, 2018, 2021, 2024, 2026]); ax.grid(axis="x", visible=False)
    ax.set_ylim(0, anual["nuevos"].max() * 1.35)
    guardar(fig, 6)
    print("Gráficos guardados en", SALIDA)


if __name__ == "__main__":
    main()

"""Grafica la pobreza de la ENAHO con reglas fijas.

Uso (desde la raíz del repositorio):
    uv run .claude/skills/graficando-enaho/scripts/graficar.py --por area
    uv run .claude/skills/graficando-enaho/scripts/graficar.py --por sexo --indicador pobre_extremo

Entra:  salidas/personas_2024.parquet (de la skill limpiando-enaho)
Sale:   figuras/<indicador>_por_<por>_2024.png y una tabla impresa

Reglas que no se discuten:
    pondera con facpob07 · barras desde cero y ordenadas · un solo color
    · valor escrito en cada barra · título con qué y cuándo
    · nota «Fuente: INEI, ENAHO 2024» · PNG a 200 dpi en figuras/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path.cwd()
COLOR = "#1f4e79"  # un solo color para todas las barras

# Columna de la base y cómo se llama en el título
GRUPOS = {
    "area": ("area", "área de residencia"),
    "sexo": ("sexo", "sexo"),
    "edad": ("grupo_edad", "grupo de edad"),
    "departamento": ("departamento", "departamento"),
    "lima": ("lima_metropolitana", "Lima Metropolitana y resto del país"),
}
INDICADORES = {"pobre": "Pobreza monetaria", "pobre_extremo": "Pobreza extrema"}
ORDEN_EDAD = ["0-13", "14-29", "30-44", "45-59", "60 y más"]

NOMBRES_DEP = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
    "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
    "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
    "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali",
}


def tabla_ponderada(base: pd.DataFrame, col: str, indicador: str) -> pd.DataFrame:
    """% de personas con el indicador, ponderado con facpob07."""
    b = base.dropna(subset=[col, "facpob07"]).copy()
    b["_num"] = b[indicador].astype(float) * b["facpob07"]
    t = b.groupby(col, observed=True).agg(num=("_num", "sum"), peso=("facpob07", "sum"),
                                          encuestados=("facpob07", "size"))
    t["pct"] = t["num"] / t["peso"] * 100
    t["personas"] = t["peso"].round()
    return t[["pct", "personas", "encuestados"]].reset_index()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--por", choices=GRUPOS, default="area")
    ap.add_argument("--indicador", choices=INDICADORES, default="pobre")
    ap.add_argument("--anio", type=int, default=2024)
    args = ap.parse_args()

    archivo = RAIZ / "salidas" / f"personas_{args.anio}.parquet"
    if not archivo.exists():
        sys.exit(f"ERROR: falta {archivo.relative_to(RAIZ)}. Usa primero la skill limpiando-enaho.")
    base = pd.read_parquet(archivo)

    col, nombre_grupo = GRUPOS[args.por]
    t = tabla_ponderada(base, col, args.indicador)
    if args.por == "departamento":
        t[col] = t[col].map(NOMBRES_DEP)
    if args.por == "lima":
        t[col] = t[col].map({True: "Lima Metropolitana", False: "Resto del país"})

    # Ordenadas: de mayor a menor, salvo la edad, que tiene su propio orden.
    if args.por == "edad":
        t[col] = pd.Categorical(t[col], ORDEN_EDAD, ordered=True)
        t = t.sort_values(col)
    else:
        t = t.sort_values("pct", ascending=False)

    titulo = f"{INDICADORES[args.indicador]} por {nombre_grupo}, Perú {args.anio}"
    horizontal = len(t) > 6
    fig, ax = plt.subplots(figsize=(8, 0.35 * len(t) + 1.8) if horizontal else (7, 4.5))
    etiquetas = t[col].astype(str).tolist()
    if horizontal:
        barras = ax.barh(etiquetas[::-1], t["pct"].tolist()[::-1], color=COLOR)
        ax.set_xlim(0, t["pct"].max() * 1.15)
        ax.set_xlabel("% de personas")
        ax.bar_label(barras, fmt="%.1f %%", padding=3, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    else:
        barras = ax.bar(etiquetas, t["pct"], color=COLOR, width=0.6)
        ax.set_ylim(0, t["pct"].max() * 1.18)  # el eje empieza en cero
        ax.set_ylabel("% de personas")
        ax.bar_label(barras, fmt="%.1f %%", padding=3, fontsize=11)
        ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(titulo, loc="left", fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, f"Fuente: INEI, ENAHO {args.anio}. Ponderado con facpob07; "
             "residentes habituales.", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    carpeta = RAIZ / "figuras"
    carpeta.mkdir(exist_ok=True)
    salida = carpeta / f"{args.indicador}_por_{args.por}_{args.anio}.png"
    fig.savefig(salida, dpi=200)
    plt.close(fig)

    print(titulo)
    print(t.to_string(index=False, formatters={"pct": "{:.1f}".format,
                                                "personas": "{:,.0f}".format}))
    print(f"\nFigura: {salida.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

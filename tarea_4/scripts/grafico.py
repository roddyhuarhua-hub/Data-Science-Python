"""grafico.png: porcentaje de aciertos, errores y «no sé» por modo, a partir de resultados.csv.

Uso (desde tarea_4/): uv run python scripts/grafico.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

AQUI = Path(__file__).resolve().parent.parent
ORDEN_MODOS = ["memoria", "web", "mcp"]
RESULTADOS = {"acierta": ("Acierta", "#2a9d8f"), "se equivoca": ("Se equivoca", "#e76f51"),
              "no sabe": ("No sabe", "#b0b0b0")}

res = pd.read_csv(AQUI / "resultados.csv")
modos = [m for m in ORDEN_MODOS if m in set(res.modo)]
pct = (pd.crosstab(res.modo, res.resultado, normalize="index") * 100).reindex(index=modos, columns=list(RESULTADOS),
                                                                             fill_value=0)

fig, ax = plt.subplots(figsize=(7, 4))
abajo = pd.Series(0.0, index=modos)
for clave, (etiqueta, color) in RESULTADOS.items():
    ax.bar(modos, pct[clave], bottom=abajo, color=color, label=etiqueta, width=0.6)
    for x, (b, v) in enumerate(zip(abajo, pct[clave])):
        if v >= 8:
            ax.text(x, b + v / 2, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=10)
    abajo += pct[clave]

n = res.groupby("modo").id.nunique().max()
ax.set_title(f"¿Acierta Claude (Haiku) las cifras del OEFA? {n} preguntas por modo")
ax.set_ylabel("% de preguntas")
ax.set_ylim(0, 100)
ax.set_xticks(range(len(modos)), ["Sin herramientas" if m == "memoria" else "Búsqueda web" if m == "web"
                                  else "MCP del OEFA" for m in modos])
ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, "Fuente: datos abiertos del OEFA (datosabiertos.oefa.gob.pe), corte a marzo de 2025. "
         "Elaboración propia con evaluar.py.", fontsize=7, color="#555555")
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(AQUI / "grafico.png", dpi=150)
print(f"grafico.png <- {len(res)} respuestas")

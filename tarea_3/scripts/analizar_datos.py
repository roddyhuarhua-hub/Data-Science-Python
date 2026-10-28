"""Indicadores, hallazgos y datos para el dashboard.

Entrada:  datos/procesados/casos_limpios.csv
Salidas:  datos/procesados/indicadores_anuales.csv
          datos/procesados/hallazgos.json
          web/data/panel.json  (conteos por mes, en formato columnar compacto)
          web/data/casos.json  (fichas de casos socioambientales, para el buscador)

Uso (desde la carpeta tarea_3):  python scripts/analizar_datos.py
"""
from pathlib import Path
import json

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PROC = BASE / "datos" / "procesados"
WEB = BASE / "web" / "data"


def guardar_json(obj, ruta):
    ruta.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def columnar(df, categorias):
    """Convierte un DataFrame en {columna: lista}, codificando las columnas de
    texto como índices de un diccionario para que el archivo pese poco."""
    salida = {"n": len(df), "dic": {}, "col": {}}
    for c in df.columns:
        if c in categorias:
            valores = sorted(df[c].fillna("").unique().tolist())
            salida["dic"][c] = valores
            idx = {v: i for i, v in enumerate(valores)}
            salida["col"][c] = df[c].fillna("").map(idx).tolist()
        else:
            salida["col"][c] = df[c].tolist()
    return salida


def main():
    df = pd.read_csv(PROC / "casos_limpios.csv", dtype={"cod_dep": str, "ubigeo": str})
    df["cod_dep"] = df["cod_dep"].fillna("")
    df["actividad"] = df["actividad"].fillna("")
    meses_por_anio = df.groupby("anio")["periodo"].nunique()
    sa = df[df["socioambiental"]]

    # ---------- Indicadores anuales (promedio mensual) ----------
    anual = pd.DataFrame({
        "meses": meses_por_anio,
        "registrados": df.groupby("anio").size() / meses_por_anio,
        "activos": df[df["estado"] == "activo"].groupby("anio").size() / meses_por_anio,
        "socioambientales": sa.groupby("anio").size() / meses_por_anio,
    })
    anual["pct_socioambiental"] = anual["socioambientales"] / anual["registrados"]
    for act in ["Minería", "Hidrocarburos", "Energía"]:
        anual[f"sa_{act.lower()}"] = sa[sa["actividad"] == act].groupby("anio").size() / meses_por_anio
    con_dato = sa[sa["con_hechos"] & sa["dialogo"].isin(["si", "no"])]
    anual["pct_dialogo"] = con_dato.groupby("anio")["dialogo"].apply(lambda s: (s == "si").mean())
    anual = anual.round(3)
    anual.to_csv(PROC / "indicadores_anuales.csv", encoding="utf-8")

    # ---------- Hallazgos ----------
    total_meses = df["periodo"].nunique()
    act = sa["actividad"].value_counts(normalize=True)
    dep_sa = sa[sa["cod_dep"] != ""]["dep"].value_counts(normalize=True)
    hidro = sa[sa["actividad"] == "Hidrocarburos"]["dep"].value_counts(normalize=True)
    dialogo_act = con_dato.groupby("actividad")["dialogo"].apply(lambda s: (s == "si").mean())
    h = {
        "periodo": [df["periodo"].min(), df["periodo"].max()],
        "meses": int(total_meses),
        "filas": int(len(df)),
        "prom_registrados_mes": round(len(df) / total_meses, 1),
        "pct_socioambiental": round(len(sa) / len(df), 3),
        "pct_actividad": act.round(3).to_dict(),
        "top5_dep_socioambiental": dep_sa.head(5).round(3).to_dict(),
        "pct_top5_dep": round(dep_sa.head(5).sum(), 3),
        "hidrocarburos_top_dep": hidro.head(3).round(3).to_dict(),
        "pct_dialogo_por_anio": anual["pct_dialogo"].to_dict(),
        "pct_dialogo_por_actividad": dialogo_act.round(3).to_dict(),
        "socioambientales_por_anio": anual["socioambientales"].round(1).to_dict(),
    }
    (PROC / "hallazgos.json").write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- Datos del dashboard ----------
    WEB.mkdir(parents=True, exist_ok=True)
    df["dialogo_web"] = df["dialogo"].where(df["con_hechos"], "na")
    panel = (df.groupby(["periodo", "cod_dep", "dep", "tipo", "actividad", "estado", "dialogo_web"])
               .size().rename("casos").reset_index()
               .rename(columns={"dialogo_web": "dialogo"}))
    guardar_json(columnar(panel, {"periodo", "cod_dep", "dep", "tipo", "actividad", "estado", "dialogo"}),
                 WEB / "panel.json")

    # Fichas de casos socioambientales: una por descripción distinta, con el
    # primer y último mes en que aparece y el último estado/diálogo informado.
    sa = sa.sort_values("periodo")
    fichas = (sa.groupby(["caso", "dep"], sort=False)
                .agg(provincia=("provincia", "last"), distrito=("distrito", "last"),
                     actividad=("actividad", "last"), desde=("periodo", "first"),
                     hasta=("periodo", "last"), meses=("periodo", "nunique"),
                     estado=("estado", "last"), url=("url_reporte", "last"))
                .reset_index())
    fichas = fichas[fichas["caso"].str.len() > 0]
    fichas["provincia"] = fichas["provincia"].fillna("")
    fichas["distrito"] = fichas["distrito"].fillna("")
    guardar_json(fichas.to_dict(orient="records"), WEB / "casos.json")

    print(anual.to_string())
    print(json.dumps({k: h[k] for k in ["prom_registrados_mes", "pct_socioambiental", "pct_top5_dep"]}))
    print(f"Fichas de casos: {len(fichas):,}")


if __name__ == "__main__":
    main()

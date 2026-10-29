"""Cifras de referencia para test_server.py y preguntas.csv, calculadas con pandas directo sobre los CSV de
datos/ (los xlsx originales del portal convertidos), sin pasar por server.py.

Uso (desde tarea_4/): uv run python scripts/verdades.py
"""
from pathlib import Path

import pandas as pd

DATOS = Path(__file__).resolve().parent.parent / "datos"


def leer(nombre):
    return pd.read_csv(DATOS / f"{nombre}.csv", dtype=str)


def anio(serie):
    return pd.to_datetime(serie, errors="coerce").dt.year


def soles(serie):
    # 'S/.24.866,80' (coma decimal), 'S/.23,000,000.00' (punto decimal) o '15110.1'
    s = serie.str.replace("S/.", "", regex=False).str.strip()
    coma_decimal = s.str.contains(r",\d{1,2}$")
    s = s.where(~coma_decimal, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s.str.replace(",", "", regex=False), errors="coerce")


sinada = leer("sinada").assign(anio=lambda d: anio(d["FECHA DE REGISTRO"]),
                               fecha=lambda d: pd.to_datetime(d["FECHA DE REGISTRO"]))
supervision = leer("supervision").assign(anio=lambda d: anio(d.FECHA_INFORME))
medidas = leer("medidas").assign(anio=lambda d: anio(d.FECHA_RESOLUCION))
multas = leer("multas_firmes").assign(soles=lambda d: soles(d["MULTA (SOLES)"]))
rd = leer("resoluciones_directorales").assign(anio=lambda d: anio(d["FECHA RD"]))
tfa = leer("expedientes_tfa").assign(anio=lambda d: anio(d["FECHA DE RESOLUCIÓN"]))

cifras = {
    # pruebas
    "sinada_cajamarca_2024": len(sinada[(sinada.DEPARTAMENTO == "CAJAMARCA") & (sinada.anio == 2024)]),
    "sinada_marzo_2024": len(sinada[(sinada.fecha >= "2024-03-01") & (sinada.fecha < "2024-04-01")]),
    "sinada_2024_por_departamento_max": sinada[sinada.anio == 2024].DEPARTAMENTO.value_counts().head(1).to_dict(),
    "multas_soles_por_anio": multas.groupby("AÑO").soles.sum().round(2).to_dict(),
    # preguntas
    "sinada_2024": len(sinada[sinada.anio == 2024]),
    "sinada_lima_2023": len(sinada[(sinada.DEPARTAMENTO == "LIMA") & (sinada.anio == 2023)]),
    "sinada_mineria_2024": len(sinada[(sinada["ACTIVIDAD ECONOMICA"].str.upper().isin(["MINERIA", "MINERÍA"]))
                                      & (sinada.anio == 2024)]),
    "supervision_2023": len(supervision[supervision.anio == 2023]),
    "medidas_loreto_2023": len(medidas[(medidas.REGION == "LORETO") & (medidas.anio == 2023)]),
    "multas_mineria_2023": len(multas[(multas.SECTOR.str.upper().isin(["MINERIA", "MINERÍA"])) & (multas.AÑO == "2023")]),
    "multas_soles_2024": round(multas[multas.AÑO == "2024"].soles.sum(), 2),
    "rd_2024": len(rd[rd.anio == 2024]),
    "tfa_2024": len(tfa[tfa.anio == 2024]),
}

if __name__ == "__main__":
    for k, v in cifras.items():
        print(f"{k}: {v}")

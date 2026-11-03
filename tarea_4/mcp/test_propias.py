"""Dos pruebas propias para la herramienta produccion_minera_departamental.
Las 8 pruebas del curso están en test_server.py, sin cambios.

    uv run pytest -q          # esperado: 10 passed
"""
import asyncio

import pandas as pd
import pytest
from fastmcp import Client

import server
from server import mcp


def llamar(herramienta, **args):
    async def f():
        async with Client(mcp) as c:
            return (await c.call_tool(herramienta, args)).data
    return asyncio.run(f())


def test_produccion_minera_asigna_por_nombre_y_no_por_orden(monkeypatch):
    """Sin internet: un catálogo y una respuesta de la API inventados. La API devuelve las series en otro orden que
    el pedido y con un «n.d.»; la herramienta debe asignar cada valor por el nombre de la serie, dar el código INEI
    de cada departamento, ordenar de mayor a menor y calcular la participación sobre el total nacional."""
    grupo = "Producción de productos mineros según departamentos"
    cat = pd.DataFrame({
        "codigo": ["X3", "X1", "X2", "X4", "X9"],
        "categoria": "Producción", "grupo": grupo,
        "nombre": ["Cobre - Arequipa (tm.f)", "Cobre - Total (tm.f)", "Cobre - Apurimac (tm.f)",
                   "Cobre - Junín (tm.f)", "Oro - Cajamarca (grs.f)"],
        "frecuencia": "Anual", "actualizada": "2026-04-30", "inicio": "2001"})
    cat["texto"] = (cat.categoria + " " + cat.grupo + " " + cat.nombre).map(server._sin_tildes)
    pedidos = []

    def falso_bajar(codigos, desde, hasta):
        pedidos.append((codigos, desde, hasta))
        series = [f"{grupo} - Cobre - Total (tm.f)", f"{grupo} - Cobre - Junín (tm.f)",
                  f"{grupo} - Cobre - Apurimac (tm.f)", f"{grupo} - Cobre - Arequipa (tm.f)"]
        return "https://estadisticas.bcrp.gob.pe/fake", {
            "config": {"series": [{"name": n} for n in series]},
            "periods": [{"name": "2024", "values": ["1000", "n.d.", "300", "500"]}]}

    monkeypatch.setattr(server, "catalogo", lambda: cat)
    monkeypatch.setattr(server, "_bajar", falso_bajar)

    r = llamar("produccion_minera_departamental", metal="Cobre", anio=2024)
    assert pedidos == [("X1-X2-X3-X4", "2024", "2024")]            # una sola llamada, sin el oro
    assert [d["departamento"] for d in r["departamentos"]] == ["Arequipa", "Apurimac"]   # Junín: n.d.
    assert [d["ccdd"] for d in r["departamentos"]] == ["04", "03"]
    assert r["departamentos"][0]["produccion"] == pytest.approx(500)
    assert r["departamentos"][0]["participacion_pct"] == pytest.approx(50)
    assert r["departamentos"][1]["puesto"] == 2
    assert r["total_nacional"] == pytest.approx(1000)
    assert r["unidad"] == "tm.f"


def test_produccion_minera_con_datos_reales_del_bcrp():
    """Con datos reales: cobre 2024. Apurímac produjo 321,527 tm.f (BCRP, serie RD15518DA, revisada en la web) y los
    departamentos suman lo mismo que el total nacional (RD15516DA)."""
    r = llamar("produccion_minera_departamental", metal="cobre", anio=2024)
    por_ccdd = {d["ccdd"]: d for d in r["departamentos"]}
    assert por_ccdd["03"]["produccion"] == pytest.approx(321_527.1, abs=1)
    assert por_ccdd["03"]["codigo"] == "RD15518DA"
    assert r["suma_departamentos"] == pytest.approx(r["total_nacional"], rel=0.01)
    assert all(len(d["ccdd"]) == 2 for d in r["departamentos"])
    assert r["departamentos"][0]["produccion"] >= r["departamentos"][-1]["produccion"]
    assert r["fuente"].startswith("https://estadisticas.bcrp.gob.pe")

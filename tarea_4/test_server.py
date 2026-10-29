"""El contrato del servidor: si estas pruebas pasan, Claude Code y evaluar.py pueden usarlo.

    uv run pytest -q

Llaman al servidor en memoria, igual que lo haría Claude Code, con los datos reales del OEFA. Las cifras
esperadas salen de scripts/verdades.py, que lee los CSV con pandas sin pasar por server.py.
"""
import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import mcp

PORTAL = "https://datosabiertos.oefa.gob.pe"


async def _con_cliente(f):
    async with Client(mcp) as c:
        return await f(c)


def llamar(herramienta, **args):
    return asyncio.run(_con_cliente(lambda c: c.call_tool(herramienta, args))).data


def test_buscar_encuentra_sinada():
    r = llamar("buscar_datos", texto="denuncias", limite=5)
    assert "sinada" in [x["clave"] for x in r]
    assert {"clave", "titulo", "categoria", "vista"} <= r[0].keys()


def test_cuatro_herramientas_como_minimo():
    nombres = {t.name for t in asyncio.run(_con_cliente(lambda c: c.list_tools()))}
    assert {"buscar_datos", "datos", "resumen"} <= nombres
    assert len(nombres) >= 4, "falta su herramienta propia"


def test_datos_filtrados_por_departamento():
    r = llamar("datos", dataset="sinada", departamento="Cajamarca", desde="2024", hasta="2024", limite=5)
    assert r["total"] == 133                      # denuncias SINADA de Cajamarca registradas en 2024
    assert len(r["filas"]) == 5
    assert all(f["departamento"] == "CAJAMARCA" for f in r["filas"])
    assert r["fuente"].startswith(PORTAL)


def test_datos_filtrados_por_fecha():
    r = llamar("datos", dataset="sinada", desde="2024-03", hasta="2024-03", limite=500)
    assert r["total"] == 308                      # denuncias SINADA registradas en marzo de 2024
    assert all(f["fecha"].startswith("2024-03") for f in r["filas"])


def test_resumen_sin_cuentas_a_mano():
    r = llamar("resumen", dataset="multas_firmes", agrupar_por="anio", suma="monto")
    por_anio = {g["grupo"]: g["valor"] for g in r["grupos"]}
    assert por_anio["2024"] == pytest.approx(166_468_409.96, abs=1)   # soles en multas firmes de 2024
    assert r["maximo"]["grupo"] == "2023"
    r = llamar("resumen", dataset="sinada", agrupar_por="departamento", desde="2024", hasta="2024")
    assert r["maximo"] == {"grupo": "LIMA", "valor": 1381}             # el departamento con más denuncias
    assert {"total", "grupos", "minimo", "periodo", "fuente"} <= r.keys()


def test_dataset_inexistente_da_un_error_claro():
    with pytest.raises(ToolError, match="petroleo_xyz"):
        llamar("datos", dataset="petroleo_xyz")


def test_un_recurso():
    async def contar(c):
        return len(await c.list_resources()) + len(await c.list_resource_templates())
    assert asyncio.run(_con_cliente(contar)) >= 1


def test_un_prompt():
    assert len(asyncio.run(_con_cliente(lambda c: c.list_prompts()))) >= 1

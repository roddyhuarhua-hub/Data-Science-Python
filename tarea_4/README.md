# Tarea 4 · Un MCP con los datos abiertos del OEFA

Es el mismo procedimiento del proyecto de la sesión 04 (`sessions/04-mcp-claude-code/proyecto`), pero en vez de
las series del BCRP usa los datos de fiscalización ambiental del OEFA: denuncias SINADA, supervisiones,
medidas administrativas, resoluciones y multas firmes. El servidor está hecho con FastMCP, se conecta a Claude
Code y `claude -p` mide cuántas cifras acierta Claude sin el servidor y cuántas con él.

| Archivo | Qué es |
|---|---|
| `server.py` | El servidor: `buscar_datos`, `datos`, `resumen`, `ficha_territorio`, el recurso `oefa://dataset/{clave}` y el prompt `informe_territorio` |
| `test_server.py` | El contrato: 8 pruebas con datos reales del OEFA |
| `preguntas.csv` | 10 preguntas con la cifra de referencia y la tolerancia; las marcadas `verificar_a_mano` se revisan en el portal |
| `evaluar.py` | Le hace cada pregunta a Claude sin herramientas y con el MCP, y califica |
| `.mcp.json` | Los servidores `oefa` y `fetch` |
| `scripts/catalogo_oefa.py` | Arma `datos/catalogo_oefa_crudo.csv` con los 98 recursos del portal |
| `scripts/perfil_datos.py` | Convierte los xlsx a CSV y escribe `datos/perfil_datos.md` |
| `scripts/verdades.py` | Calcula con pandas, sin el servidor, las cifras de las pruebas y de las preguntas |

## Uso

```bash
uv run pytest -q                 # 8 passed; la primera vez baja los xlsx del portal a datos/
claude                           # acepten los servidores de .mcp.json
uv run evaluar.py                # memoria contra mcp, con Haiku; escribe resultados.csv
```

Prueben en Claude Code: *«¿Cuántas denuncias SINADA hubo en Cajamarca en 2024?»*,
`@oefa:oefa://dataset/multas_firmes` y `/mcp__oefa__informe_territorio Cajamarca`.

## Datasets

| Clave | Dataset | Filas |
|---|---|---|
| `sinada` | Denuncias SINADA 2019-2025 | 17,823 |
| `supervision` | Informes de la Dirección de Supervisión 2019-2025 | 53,110 |
| `medidas` | Medidas administrativas 2016-2025 | 4,458 |
| `multas_firmes` | Resoluciones con multa firme 2019-2025 | 7,871 |
| `actos_administrativos` | Registro de actos administrativos 2021-2025 | 9,077 |
| `resoluciones_directorales` | Resoluciones directorales 2018-2025 | 13,000 |
| `resoluciones_subdirectorales` | Resoluciones subdirectorales 2018-2025 | 13,035 |
| `expedientes_tfa` | Expedientes resueltos por el TFA 2021-2025 | 2,560 |

Los datos llegan hasta febrero o marzo de 2025: el portal los publicó por última vez el 29 de abril de 2025.

## Lo que hay que saber de los datos

- `data.csv` de la API devuelve solo 999 filas, así que el servidor baja el xlsx original de cada dataset
  (`/datasets/<id>-<slug>.download/`). La carpeta `datos/` no se sube a git, salvo el catálogo y el perfil.
- Los informes de supervisión no traen ubicación. El departamento se toma de la misma unidad fiscalizable en
  las resoluciones, las medidas y las multas, y cerca de 1 de cada 4 informes queda sin departamento.
- En multas firmes, la columna `MULTA (UIT)` a veces trae soles. Por eso se usa `MULTA (SOLES)`, que además
  mezcla dos formatos de número (`S/.24.866,80` y `S/.23,000,000.00`).
- Un registro con varios departamentos («JUNIN; LIMA») cuenta para cada uno cuando se filtra.
- Las 560 denuncias SINADA de 2025 no tienen departamento.
- El RUIAS de datosabiertos.gob.pe no se pudo bajar porque el firewall de ese sitio bloquea la descarga
  automática. Su equivalente en el portal del OEFA es `actos_administrativos`.

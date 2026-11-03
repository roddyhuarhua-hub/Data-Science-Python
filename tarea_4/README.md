# Tarea 4 · Agente de investigación: cobre, oro y pobreza en el Perú

Tarea individual del curso [Data-Science-Python](https://github.com/d2cml-ai/Data-Science-Python)
(issue [#201](https://github.com/d2cml-ai/Data-Science-Python/issues/201)). Autor: Roddy Huarhua
([@roddyhuarhua-hub](https://github.com/roddyhuarhua-hub)).

## 1. Objetivo del proyecto

Construir un agente de Claude Code que responda preguntas socioeconómicas del Perú con cifras **reproducibles y
verificables**, combinando dos fuentes oficiales:

- las series del **Banco Central de Reserva del Perú (BCRP)**, a través de un servidor MCP propio, y
- los microdatos de la **ENAHO 2024 del INEI**, a través de tres skills que limpian, grafican y mapean la pobreza.

**Pregunta de investigación:** en 2024, con precios altos del cobre y del oro, ¿los departamentos que más cobre
producen tienen menos pobreza monetaria que el resto del Perú?

La pregunta viene de mi trabajo en relaciones comunitarias: en los territorios mineros la expectativa de
desarrollo es una fuente central de conflicto. El análisis es **descriptivo y de un solo año**: muestra
asociaciones, no causas. El informe está en [`informes/informe_final.md`](informes/informe_final.md).

## 2. Arquitectura general del agente

```text
                    Pregunta en lenguaje natural
                               │
                         Claude Code
            ┌──────────────────┴──────────────────┐
     MCP «bcrp» (mcp/server.py)          Skills (.claude/skills/)
     buscar_series · serie · resumen     limpiando-enaho ─► salidas/personas_2024.parquet
     produccion_minera_departamental     │                   salidas/validacion.txt
     graficar_serie                      │                   salidas/indicadores.csv
     recurso bcrp://serie/{codigo}       ├► graficando-enaho ─► figuras/*.png
     prompt informe(tema)                └► mapeando-enaho  ─► mapas/*.png
            │                                       │
   API del BCRP (estadisticas.bcrp.gob.pe)   ENAHO 2024 (INEI) + límites departamentales
            └──────────── unión por código de departamento (ccdd = ubigeo[:2]) ───────────┘
                               │
                 informes/ · evaluacion/ · evidencias_ia/
```

Las cuentas las hace Python, no el modelo: cada cifra sale de una herramienta o de un script que se puede repetir.
La unión entre fuentes se hace por **código INEI de departamento**, nunca por nombre (el BCRP escribe «Apurimac»
y «Ancash» sin tilde).

## 3. Herramientas MCP

Servidor [`mcp/server.py`](mcp/server.py), hecho con FastMCP 4 a partir del proyecto de la Sesión 04.

| Tipo | Nombre | Qué hace |
|---|---|---|
| Herramienta | `buscar_series(texto, frecuencia, limite)` | Busca en las 17,167 series del catálogo del BCRP por palabras |
| Herramienta | `serie(codigo, desde, hasta)` | Baja los datos de una serie (diaria, mensual, trimestral o anual) y da la URL de la fuente |
| Herramienta | `resumen(codigo, desde, hasta)` | Primero, último, cambio, variación %, promedio, máximo y mínimo |
| **Herramienta propia** | `produccion_minera_departamental(metal, anio)` | Ranking de departamentos por producción de cobre, oro, plata, zinc, plomo o molibdeno, con su participación en el total nacional y el **código INEI** de cada departamento para cruzarlo con la ENAHO |
| Herramienta extra | `graficar_serie(codigo, desde, hasta, titulo)` | Guarda un gráfico de líneas de una serie en `figuras/` con su fuente |
| Recurso | `bcrp://serie/{codigo}` | Ficha de la serie: nombre, frecuencia, fechas y página oficial |
| Prompt | `informe(tema)` | Plantilla de informe que exige código, periodo y fuente en cada cifra, y prohíbe inventar o afirmar causas |

**Por qué la herramienta propia es útil.** El BCRP publica la producción minera por departamento en 276 series
sueltas («Cobre - Apurimac (tm.f)», «Oro - Cajamarca (grs.f)»...). Sin la herramienta, el modelo tendría que
encontrar 17 códigos, bajarlos uno por uno y sumarlos. La herramienta los pide en **una sola llamada**, asigna cada
valor por el nombre de la serie (la API los devuelve en otro orden que el pedido), calcula la participación y
agrega el código `ccdd` para unir con la ENAHO sin errores de tildes.

**Pruebas:** [`mcp/test_server.py`](mcp/test_server.py) son las 8 pruebas originales de la Sesión 04, **sin
cambios**. [`mcp/test_propias.py`](mcp/test_propias.py) agrega 2 pruebas de la herramienta propia: una sin internet
(asignación por nombre, «n.d.», orden y participación) y otra con datos reales (Apurímac 2024 = 321,527.1 tm.f y la
suma de departamentos igual al total nacional). Resultado: **10 passed**
([`evidencias_ia/mcp/pruebas.txt`](evidencias_ia/mcp/pruebas.txt)).

## 4. Las tres Skills

| Skill | Entra | Hace | Sale |
|---|---|---|---|
| [`limpiando-enaho`](.claude/skills/limpiando-enaho/SKILL.md) | `datos/966-Modulo34.zip`, `datos/966-Modulo02.zip` | Normaliza nombres; lee llaves como texto con ceros; filtra residentes habituales `((p204==1)&(p205==2))|((p204==2)&(p206==1))`; une con `merge(..., validate="m:1")` por `conglome, vivienda, hogar`; construye pobreza, departamento y área; pondera con factores de expansión; **valida** 15 chequeos y si uno falla no guarda la base | `salidas/personas_2024.parquet`, [`salidas/validacion.txt`](salidas/validacion.txt), [`salidas/indicadores.csv`](salidas/indicadores.csv) |
| [`graficando-enaho`](.claude/skills/graficando-enaho/SKILL.md) | la base limpia | Barras ponderadas con `facpob07`, desde cero, con título, periodo, unidad y fuente | `figuras/pobre_por_{area,sexo,edad,departamento}_2024.png` |
| [`mapeando-enaho`](.claude/skills/mapeando-enaho/SKILL.md) | la base limpia y `peru_departamental_simple.geojson` | Une `ubigeo[:2]` con `FIRST_IDDP` (nunca por nombre), exige 25 unidades con dato, Lima y Callao separados, escala de un color desde 0, leyenda «% de personas», compara con la referencia de la Sesión 16 | `mapas/pobreza_departamento.png` y su tabla |

**Validación ENAHO 2024** ([`salidas/validacion.txt`](salidas/validacion.txt)): pobreza monetaria **27.58 %**
(INEI 27.6 %), urbana 24.81 % (24.8 %), rural 39.30 % (39.3 %), extrema 5.50 % (5.5 %), **108,664** residentes
habituales, **25/25** unidades territoriales. Diferencia máxima del mapa con la referencia de la Sesión 16:
0.52 puntos (Puno), porque aquí se pondera por persona con `facpob07`.

**Activación y coordinación.** Cada skill se llama a mano (`/limpiando-enaho 2024`, `/graficando-enaho sexo`,
`/mapeando-enaho`) o por lenguaje natural según su `description`. Graficando y mapeando empiezan con «si no existe
`salidas/personas_2024.parquet`, usa primero `limpiando-enaho`», así un pedido de mapa o gráfico sin base procesada
encadena dos skills.

## 5. Fuentes y descarga de datos

| Dato | Dónde | Cómo se obtiene |
|---|---|---|
| ENAHO 2024, módulo 34 (sumaria) | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo34.zip | A mano desde el navegador, a `datos/` sin descomprimir |
| ENAHO 2024, módulo 02 (miembros) | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo02.zip | Igual |
| Límites departamentales | [`sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson`](https://github.com/d2cml-ai/Data-Science-Python/blob/main/sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson) | Lo baja solo la skill de mapas |
| Catálogo de series del BCRP | https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata | Lo baja solo el servidor la primera vez (~7 MB) |
| Series del BCRP | https://estadisticas.bcrp.gob.pe/estadisticas/series/ (API sin clave) | Las pide el servidor MCP |

`966` es el código de la ENAHO 2024 en el [portal de microdatos del INEI](https://proyectos.inei.gob.pe/microdatos/).
La carpeta `datos/` está en `.gitignore`: no se suben microdatos.

## 6. Instalación con `uv`

Requisitos: [uv](https://docs.astral.sh/uv/) y [Claude Code](https://code.claude.com) con sesión iniciada.

```bash
git clone https://github.com/roddyhuarhua-hub/Data-Science-Python.git
cd Data-Science-Python
git checkout tarea-4-agente
cd tarea_4
uv sync            # instala Python y las librerías (fastmcp, pandas, geopandas, matplotlib, pytest)
```

En Windows, si la carpeta está dentro de OneDrive y `uv` no puede borrar `.venv`, usen un entorno fuera de OneDrive:
`set UV_PROJECT_ENVIRONMENT=%LOCALAPPDATA%\t4_venv`.

## 7. Conectar el MCP a Claude Code

El archivo [`.mcp.json`](.mcp.json) ya registra dos servidores en el proyecto: `bcrp` (el propio) y `fetch`. Se
creó con:

```bash
claude mcp add --scope project bcrp -- uv run mcp/server.py
claude mcp add --scope project fetch -- uvx mcp-server-fetch
```

Abran `claude` dentro de `tarea_4/` y acepten los servidores del proyecto. Comprueben:

1. `/mcp`: `bcrp` conectado con 5 herramientas.
2. `¿Qué departamento produjo más cobre en 2024?` → debe llamar a `produccion_minera_departamental`.
3. Recurso: `@bcrp:bcrp://serie/PM05568XA ¿desde cuándo hay datos?`
4. Prompt: `/mcp__bcrp__informe precio del cobre`
5. `/skills`: las tres skills.

## 8. Reproducir el procesamiento y las pruebas

```bash
uv run pytest -q                                                    # 10 passed
uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024 # validacion.txt: TODO OK
uv run .claude/skills/graficando-enaho/scripts/graficar.py --por area   # sexo, edad, departamento, lima
uv run .claude/skills/mapeando-enaho/scripts/mapear.py
uv run scripts/verdades.py              # respuestas esperadas de la evaluación, por un camino independiente
uv run scripts/ejecucion_integrada.py   # la ejecución completa de la Parte 3 (claude -p)
uv run evaluacion/evaluar.py            # 10 preguntas × 2 modos (claude -p)
```

## 9. Resultados de la evaluación

Diez preguntas con respuesta fijada de antemano ([`evaluacion/preguntas.csv`](evaluacion/preguntas.csv)): 4 del
BCRP, 4 de la ENAHO y 2 combinadas. Mismo modelo (Sonnet), misma instrucción y una sesión nueva por pregunta.

| Modo | Correctas | Incorrectas | Sin respuesta | Segundos promedio |
|---|---|---|---|---|
| Sin MCP/Skills (carpeta vacía, sin herramientas) | **4/10** | 1 | 5 | 11.6 |
| Con MCP/Skills (copia limpia del proyecto) | **9/10** | 1 | 0 | 20.6 |

Mejoraron con las herramientas q03, q04, q08, q09 y q10: cálculos, datos por departamento y cruces de fuentes. q06
(pobreza rural) falló en ambos: el agente con skills dio 39.4 % (ponderación por persona) en vez del 39.3 % oficial
(ponderación por hogar), por fuera de la tolerancia de 0.1. Detalle, tiempos y análisis:
[`evaluacion/comparacion.md`](evaluacion/comparacion.md) · tabla completa:
[`evaluacion/resultados.csv`](evaluacion/resultados.csv).

## 10. Limitaciones y problemas encontrados

- **Red.** Los portales del INEI y del BCRP bloquean descargas desde servidores en la nube: las pruebas, la limpieza
  y las corridas de `claude -p` se hicieron en mi laptop. Los zip del INEI se bajan a mano.
- **API del BCRP.** A veces responde con una página HTML (control antibots) en vez de JSON: el servidor reintenta con
  pausas, guarda en caché y pide varias series en una sola llamada. Al pedir varias series, la API las devuelve en
  su propio orden: la herramienta propia asigna cada valor por el nombre de la serie, no por la posición.
- **Nombres sin tildes en el BCRP** («Apurimac», «Ancash»): por eso se une por código `ccdd`.
- **Dos ponderaciones de la ENAHO.** Por hogar replica la cifra oficial; por persona difiere algunas décimas (causa
  del error en q06).
- **El agente no siempre usa sus herramientas.** En la primera ejecución integrada leyó los SKILL.md y corrió los
  scripts sin invocar la herramienta Skill; en la evaluación respondió q05 de memoria. Se repitió la ejecución
  pidiendo invocar las skills de forma explícita.
- **OneDrive.** En Windows, `.venv` dentro de OneDrive queda bloqueado; se usó `UV_PROJECT_ENVIRONMENT` fuera de
  OneDrive (los scripts lo respetan).
- **Análisis.** Descriptivo, un solo año, nivel departamental, sin intervalos de confianza (ver informe).

## 11. Ejemplo de una ejecución completa

`uv run scripts/ejecucion_integrada.py` le hace a Claude Code (Sonnet) **un solo pedido** con la pregunta de
investigación, en una copia limpia del proyecto. Herramientas que usó, en orden
([transcripción completa](evidencias_ia/integracion/ejecucion.md)):

```text
mcp__bcrp__buscar_series ×3          → encuentra PM05568XA (cobre), PM05570XA (oro), PN01652XM (cobre mensual)
mcp__bcrp__produccion_minera_departamental("cobre", 2024)  → ranking con ccdd: Moquegua, Arequipa, Áncash...
mcp__bcrp__resumen ×2, mcp__bcrp__serie ×2 → precios 2023 y 2024 (PM05568XA, PM05570XA)
mcp__bcrp__graficar_serie            → figuras/bcrp_PN01652XM_2015-01_2024-12.png
Skill: limpiando-enaho  → Bash ×2     → salidas/validacion.txt: TODO OK
Skill: mapeando-enaho   → Bash, Read  → mapas/pobreza_departamento.png (25/25)
Skill: graficando-enaho → Bash        → figuras/pobre_por_departamento_2024.png, pobre_por_area_2024.png
Bash (uv run python)                  → pobreza de los 5 productores juntos: 19.7 % contra 28.5 % del resto
Bash                                  → informes/borrador_agente.md
```

El resultado revisado y verificado es [`informes/informe_final.md`](informes/informe_final.md).

## 12. Evidencias de uso de IA

Todo el proyecto se hizo con Claude Code. Las corridas de Claude Code se exportaron completas (opción B del issue: `.jsonl` original y `.md` legible). Antes de publicar se
revisó que no hubiera claves, tokens ni datos personales.

| Carpeta | Qué contiene |
|---|---|
| [`evidencias_ia/bitacora_desarrollo.md`](evidencias_ia/bitacora_desarrollo.md) | La bitácora del desarrollo: cada pedido a Claude Code, qué hizo, qué se corrigió y en qué commit quedó (servidor MCP, pruebas, skills, integración, evaluación, informe) |
| [`evidencias_ia/mcp/`](evidencias_ia/mcp/) | Salida de las 10 pruebas; uso del recurso `bcrp://serie/PM05568XA` y del prompt `/mcp__bcrp__informe precio del cobre` desde Claude Code |
| [`evidencias_ia/skills/`](evidencias_ia/skills/) | Invocación manual de skills (`/graficando-enaho sexo`, `/mapeando-enaho`). Con `claude -p`, el slash se expande dentro del pedido: la prueba es la lista `slash_commands` del inicio y los scripts que corre desde la carpeta de la skill. La invocación por lenguaje natural con la herramienta `Skill` está en `integracion/` y en la evaluación |
| [`evidencias_ia/integracion/`](evidencias_ia/integracion/) | La ejecución completa de la Parte 3 (`.jsonl` original y `.md` legible) |
| [`evidencias_ia/evaluacion/`](evidencias_ia/evaluacion/) | Las 20 transcripciones de la evaluación, una por pregunta y modo |

## Estructura

```text
tarea_4/
  README.md  pyproject.toml  uv.lock  .mcp.json  .gitignore
  mcp/            server.py · test_server.py (8 del curso, sin cambios) · test_propias.py (2 propias)
  .claude/skills/ limpiando-enaho/ · graficando-enaho/ · mapeando-enaho/
  scripts/        verdades.py · analisis_minero.py · ejecucion_integrada.py · transcripcion_a_md.py
  datos/          (no se sube) zip del INEI, catálogo del BCRP, geojson
  salidas/        validacion.txt · indicadores.csv · mineria_pobreza_2024.csv
  figuras/  mapas/  informes/  evaluacion/  evidencias_ia/  referencias/
```

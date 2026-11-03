# Comparación: el agente sin y con MCP/Skills

Diez preguntas ([`preguntas.csv`](preguntas.csv)): 4 del BCRP, 4 de la ENAHO 2024 y 2 que combinan ambas fuentes. Las
respuestas esperadas y sus tolerancias se fijaron **antes** de correr la evaluación, con fuentes oficiales (INEI,
BCRP) o con [`scripts/verdades.py`](../scripts/verdades.py), que calcula por un camino independiente del agente (API
del BCRP con `httpx` y la sumaria de la ENAHO ponderada por hogar). No se cambiaron después de ver los resultados.

## Diseño del experimento

| | Modo «sin» | Modo «con» |
|---|---|---|
| Modelo | Sonnet | Sonnet |
| Instrucción | la misma: un número en `valor` (y `valor2` si se pide), `null` si no sabe, y la fuente | igual |
| Carpeta | vacía: no ve el proyecto ni respuestas ya calculadas | copia limpia con `.claude/skills`, `mcp/server.py`, `.mcp.json` y `datos/`; **sin** `salidas/`, `figuras/`, `mapas/`, `referencias/`, `informes/` ni `evaluacion/` |
| Herramientas | ninguna (`--tools ""`, `--strict-mcp-config`) | MCP `bcrp`, `Skill`, `Bash`, `Read`, `Glob`, `Grep` |
| Sesión | nueva por pregunta (`--no-session-persistence`) | igual |

Script: [`evaluar.py`](evaluar.py). Resultados: [`resultados.csv`](resultados.csv) y
[`resumen_modos.csv`](resumen_modos.csv). Transcripciones completas: [`../evidencias_ia/evaluacion/`](../evidencias_ia/evaluacion/).

## Resultados

| Modo | Correctas | Incorrectas | Sin respuesta | Segundos promedio | Costo (US$) |
|---|---|---|---|---|---|
| Sin MCP/Skills | **4/10** | 1 | 5 | 11.6 | 0.16 |
| Con MCP/Skills | **9/10** | 1 | 0 | 20.6 | 0.66 |

| Pregunta | Esperada | Sin | Con | Herramientas en «con» |
|---|---|---|---|---|
| q01 Precio del cobre 2024 (¢US$/lb) | 414.62 ± 0.5 | ✅ 415 (memoria) | ✅ 414.62 | `buscar_series` › `serie` |
| q02 Precio del oro 2024 (US$/oz) | 2,387.98 ± 2 | ✅ 2,386 (memoria) | ✅ 2,387.98 | `buscar_series` › `serie` |
| q03 Variación del cobre 2024/2023 (%) | 7.76 ± 0.1 | ⬜ no sabe | ✅ 7.76 | `buscar_series` › `resumen` |
| q04 Cobre de Apurímac 2024 (tm.f) | 321,527.1 ± 500 | ⬜ no sabe | ✅ 321,527 | `produccion_minera_departamental` |
| q05 Pobreza nacional (%) | 27.6 ± 0.1 | ✅ 27.6 | ✅ 27.6 | ninguna (de memoria) |
| q06 Pobreza rural (%) | 39.3 ± 0.1 | ❌ 39.8 | ❌ 39.4 | `Glob` › `Read` › `Bash` (script de la skill) |
| q07 Pobreza extrema (%) | 5.5 ± 0.1 | ✅ 5.5 | ✅ 5.5 | `buscar_series` (innecesaria) › `Glob` › `Read` › `Bash` |
| q08 Pobreza de Cajamarca (%) | 45.0 ± 0.5 | ⬜ no sabe | ✅ 45.0 | `Skill:limpiando-enaho` › `Bash` |
| q09 Mayor productor de cobre: pobreza (%) y producción (tm.f) | 11.0 ± 0.5 y 475,930 ± 1,000 | ⬜ no sabe (supuso Arequipa) | ✅ 10.9 y 475,930 | `produccion_minera_departamental` › `Skill:limpiando-enaho` › `Bash` |
| q10 Pobreza conjunta de los 5 mayores productores (%) | 19.7 ± 0.3 | ⬜ no sabe | ✅ 19.7 | `produccion_minera_departamental` › `Skill:limpiando-enaho` › `Bash` › `Read` |

Mejoraron con MCP/Skills: q03, q04, q08, q09 y q10. No empeoró ninguna. q01, q02, q05 y q07 acertaron en ambos modos.
q06 falló en ambos.

## Análisis

**Dónde ayudan las herramientas.** Las 5 preguntas que solo acierta el modo «con» son las que piden un cálculo
(q03) o un dato que no está en la memoria del modelo: la producción de un departamento (q04), la pobreza de un
departamento (q08) y, sobre todo, las dos que cruzan fuentes (q09 y q10). En q09 el modo «sin» supuso que el mayor
productor era Arequipa, por Cerro Verde. Según el BCRP, en 2024 fue Moquegua (475,930 tm.f contra 453,836). Tuvo la
prudencia de no dar cifra. En q10, la herramienta propia dio el ranking con el código INEI de cada departamento y la
skill dio la base ponderada. El agente unió las dos por código y ponderó por población, no promedió las tasas.

**Dónde no hacen falta.** Los precios anuales de 2024 (q01, q02) y las cifras nacionales de pobreza (q05, q07) son
públicas y conocidas, y el modelo las recuerda. Aun así, el modo «sin» dio valores redondeados (415, 2,386) y dijo
que eran «de memoria, no verificados». El modo «con» dio el valor exacto con el código de la serie. En q05 el
modo «con» **no usó ninguna herramienta** y contestó de memoria, aunque tenía la skill disponible. Acertó, pero sin
trazabilidad. Es una debilidad: tener las herramientas no garantiza que el agente las use.

**El error de q06 es de método.** El INEI publica 39.3 % calculado con la sumaria, que pondera por hogar con
`factor07 × mieperho`. El agente leyó `salidas/indicadores.csv`, que pondera por persona con `facpob07`, y respondió
39.4 % (39.44). La diferencia es de 0.14 puntos y la tolerancia fijada era 0.1. Su propia fuente dice que con la
sumaria sale 39.30 %, pero eligió la otra cifra. No se cambió la tolerancia después de ver el resultado. La lección
para la skill es que debería decir cuál de los dos métodos replica la cifra oficial cuando se pregunta por ella.
El modo «sin» respondió 39.8 %, de memoria y más lejos.

**Errores e invenciones.** Ningún modo inventó cifras sin avisar. El modo «sin» usó `null` en 5 preguntas y marcó
como «no verificado» lo que respondió de memoria. El único error de cada modo fue q06.

**Tiempo y costo.** El modo «con» tarda casi el doble (20.6 s contra 11.6 s) y cuesta unas cuatro veces más (US$ 0.66
contra 0.16 por las 10 preguntas), porque arranca el servidor MCP, corre la limpieza de la ENAHO y lee archivos. Las
preguntas combinadas fueron las más lentas, con 32 s cada una.

## Conclusión

MCP y Skills subieron los aciertos de 4 a 9 de 10. Son indispensables para preguntas que exigen datos
desagregados, cálculos sobre microdatos o cruzar fuentes, que es justo lo que pide un análisis territorial de
minería y pobreza. Para cifras nacionales muy citadas el modelo ya las recuerda, aunque sin código de serie ni
decimales exactos. Faltan dos ajustes: que el agente use siempre las herramientas en vez de su memoria (q05), y
que la skill aclare qué ponderación replica la cifra oficial (q06).

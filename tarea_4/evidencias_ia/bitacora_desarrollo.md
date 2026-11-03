# Bitácora del desarrollo con IA (Tarea 4)

Todo el proyecto se hizo con **Claude Code**: una sesión en la nube escribió el código y los textos, y una sesión
de Claude Code en mi laptop (Remote Control) corrió lo que necesita internet hacia el BCRP y el INEI, los
microdatos y `claude -p`. Esta bitácora resume, en orden, qué le pedí, qué hizo la IA, qué se corrigió y dónde
quedó la evidencia de cada paso. Los commits de la rama `tarea-4-agente` permiten reconstruir cada cambio.

| # | Fecha (UTC) | Pedido / paso | Qué hizo la IA | Corrección o decisión | Evidencia |
|---|---|---|---|---|---|
| 1 | 2026-11-03 04:00 | «tarea 4: issue #201» | Leyó el issue, la Sesión 04 (servidor BCRP con TODO 1-5 y 8 pruebas) y la Sesión 16 (skills ENAHO). Propuso la pregunta minera | El MCP debía ser del BCRP (las 8 pruebas originales no se cambian), no de OEFA como en la tarea anterior. Rama nueva para no tocar `tarea-4` | Mensaje de plan en el chat del proyecto |
| 2 | 04:10 | Explorar el catálogo del BCRP (en la laptop) | Bajó el catálogo (17,167 series) y encontró el grupo «Producción de productos mineros según departamentos» (276 series, datos del MINEM) | Hallazgos: la API ordena las series a su modo en llamadas combinadas; a veces responde HTML (antibots); nombres sin tildes | Reporte de la laptop (resumido en README §10) |
| 3 | 04:20 | Servidor MCP | Completó `serie` (fechas `Ene.2025`, `01.Oct.26`, `T1.25`, «Set»), `resumen`, recurso `bcrp://serie/{codigo}`, prompt `informe`, `graficar_serie` y la herramienta propia | La primera idea de herramienta propia (`comparar_periodos`) se cambió por `produccion_minera_departamental`, más útil para la pregunta y para unir con la ENAHO por código | commit `f76e96b` · `mcp/server.py` |
| 4 | 04:30 | Pruebas propias | `test_propias.py`: una sin internet (asignación por nombre, «n.d.», ranking) y otra con datos reales (Apurímac 2024) | Se dejó `test_server.py` idéntico al del curso | `mcp/test_propias.py` |
| 5 | 04:35 | Skills | Reutilizó mis skills de la Sesión 16 y agregó: chequeo de 25 códigos con Lima y Callao separados, chequeo de factores de expansión y `salidas/indicadores.csv` | Se probó la limpieza con datos sintéticos: si falla un chequeo, no guarda la base | `.claude/skills/limpiando-enaho/` |
| 6 | 04:45 | Evaluación e integración | Escribió `evaluar.py` (modos sin/con en carpetas limpias), `preguntas.csv` (4 BCRP, 4 ENAHO, 2 combinadas), `verdades.py` (camino independiente) y `ejecucion_integrada.py` | Las verdades de q09 y q10 se calcularon una vez, antes de evaluar | commit `f76e96b` |
| 7 | 05:00 | Laptop, fase 1 | `uv run pytest`: **10 passed**. Limpieza: **TODO OK** (27.58 %, 108,664, 25/25). Figuras, mapa, verdades | `.venv` bloqueado por OneDrive → entorno en `%LOCALAPPDATA%` | commit `2410570` · `mcp/pruebas.txt` |
| 8 | 05:20 | Laptop, ejecución integrada | Primera corrida: el agente leyó los SKILL.md y corrió los scripts **sin** invocar la herramienta Skill | Se repitió pidiendo invocar cada skill con la herramienta Skill: 9 llamadas al MCP + 3 skills | commit `9885212` · `integracion/ejecucion.md` |
| 9 | 11:40 | Laptop, evaluación | 20 corridas con Sonnet: sin 4/10, con 9/10 | q06 falló por ponderación (39.4 vs 39.3). **No** se cambió la tolerancia tras ver el resultado | `evaluacion/*.jsonl` · `evaluacion/resultados.csv` |
| 10 | 12:00 | Informe y README | Escribió `comparacion.md`, `informe_final.md` (a partir del borrador del agente, con cifras verificadas) y el README de 12 secciones | Se suavizaron afirmaciones que no salían de los datos (sin causalidad) | commits `4f15704`, `c0f1ed7` |
| 11 | 12:10 | Laptop, análisis y evidencias | `analisis_minero.py` (cobre y oro vs pobreza), invocación manual de skills, recurso y prompt MCP | Git Bash convertía `/graficando-enaho` en una ruta: se repitió con `MSYS_NO_PATHCONV=1` | commit `57f5ad1` · `skills/` · `mcp/` |
| 12 | — | Verificación manual | PENDIENTE: revisar a mano en la web del BCRP el precio del cobre 2024 y la producción de Apurímac 2024 | — | Informe §5 |

**Revisión antes de publicar.** En cada commit se buscaron claves y datos personales (`sk-ant`, `api_key`,
`token`, `Bearer`, `password`, correo): ninguna coincidencia. Los microdatos del INEI no se suben.

---
name: graficando-enaho
description: Hace gráficos de barras de la pobreza monetaria o extrema de la ENAHO del INEI por área urbana y rural, sexo, grupo de edad, departamento o Lima Metropolitana, siempre ponderados y con las mismas reglas de diseño. Úsala cuando pidan graficar, comparar o visualizar la pobreza del Perú con la ENAHO.
argument-hint: [area|sexo|edad|departamento|lima]
allowed-tools: Bash(uv run *), Read
---
# Graficar la ENAHO

Trabaja desde la raíz del repositorio.

1. Si no existe `salidas/personas_2024.parquet`, usa primero la skill `limpiando-enaho` y espera a que su
   `validacion.txt` diga `TODO OK`.
2. Elige el grupo según el pedido: `area` (urbana y rural), `sexo`, `edad`, `departamento` o `lima`. Si piden
   pobreza extrema agrega `--indicador pobre_extremo`. Si el pedido trae argumento, úsalo: `$ARGUMENTS`.
3. Corre exactamente:
   `uv run ${CLAUDE_SKILL_DIR}/scripts/graficar.py --por <grupo>`
4. El script imprime la tabla y la ruta del PNG en `figuras/`. Abre el PNG con Read para revisar que se vea bien.
5. Responde con las cifras de la tabla (un decimal), la ruta de la figura y la nota de fuente.

## Reglas fijas (ya están en el script; no las cambies en el pedido)

- Pondera siempre con `facpob07`.
- Barras que empiezan en cero, ordenadas de mayor a menor (la edad va en su orden natural).
- Un solo color; el valor escrito en cada barra.
- El título dice qué y cuándo: «Pobreza monetaria por área de residencia, Perú 2024».
- Nota al pie: «Fuente: INEI, ENAHO 2024».
- PNG a 200 dpi en `figuras/`.

Si el usuario pide otro tipo de gráfico (líneas, torta), explica que la skill usa barras para comparar grupos y
ofrece la versión en barras. Nunca grafiques conteos sin ponderar.

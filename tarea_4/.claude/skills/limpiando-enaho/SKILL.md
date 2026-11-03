---
name: limpiando-enaho
description: Limpia los módulos 34 (sumaria) y 02 (miembros) de la ENAHO del INEI y arma una base de personas con pobreza monetaria y factor de expansión, validada contra la cifra oficial. Úsala cuando pidan limpiar, unir o analizar la ENAHO, o calcular la pobreza del Perú por departamento, región, área, sexo o edad (por ejemplo, «¿cuál fue la pobreza en Cusco en 2024?»).
argument-hint: [año]
allowed-tools: Bash(uv run *), Read
---
# Limpiar la ENAHO

Trabaja siempre desde la raíz del repositorio. El año por defecto es 2024 (código INEI 966).

1. Revisa que existan `datos/966-Modulo34.zip` y `datos/966-Modulo02.zip`. Si faltan, detente y pide al usuario
   bajarlos del INEI desde el navegador:
   - https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo34.zip
   - https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo02.zip
2. Si `salidas/personas_2024.parquet` y `salidas/validacion.txt` ya existen y la validación dice `TODO OK`, no
   vuelvas a limpiar: ve al paso 4.
3. Corre exactamente, sin cambiar el script:
   `uv run ${CLAUDE_SKILL_DIR}/scripts/limpiar.py --anio 2024`
   Si el usuario llamó la skill con un año (`$ARGUMENTS`), usa ese año en lugar de 2024.
4. Lee `salidas/validacion.txt`. Si dice `HAY FALLAS` o la pobreza difiere del INEI en más de 0.1 puntos,
   detente y muestra al usuario el chequeo que falló. No inventes cifras.
5. La skill deja también `salidas/indicadores.csv` (pobreza monetaria y extrema ponderadas: nacional, por área,
   sexo y departamento, con el código `ccdd` en la columna `codigo`). Para cifras de esos grupos, léelo con Read.
   Para otros grupos, responde con `salidas/personas_2024.parquet`. Toda cifra va **ponderada con `facpob07`**, nunca cuentes filas.
   Para calcular, usa pandas con `uv run python -c "..."`:
   `pobreza = (pobre * facpob07).sum() / facpob07.sum() * 100` dentro del grupo pedido.
6. Antes de usar una variable que no está en la base, o para filtrar por departamento, lee `reference.md`.

## Al responder

- Da la cifra con un decimal y di que es pobreza monetaria, con su año y la fuente: INEI, ENAHO.
- Aclara que se pondera con `facpob07` sobre residentes habituales.
- Si el usuario pide un gráfico usa la skill `graficando-enaho`; si pide un mapa, `mapeando-enaho`.

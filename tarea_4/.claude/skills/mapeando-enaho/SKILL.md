---
name: mapeando-enaho
description: Hace el mapa coroplético de la pobreza monetaria o extrema por departamento del Perú con la ENAHO del INEI, uniendo por código de ubigeo con los límites departamentales y comprobando que los 25 departamentos tengan dato. Úsala cuando pidan un mapa, mapear o ver en el territorio la pobreza por departamento o región con la ENAHO.
allowed-tools: Bash(uv run *), Read
---
# Mapear la ENAHO

Trabaja desde la raíz del repositorio.

1. Si no existe `salidas/personas_2024.parquet`, usa primero la skill `limpiando-enaho` y espera a que su
   `validacion.txt` diga `TODO OK`.
2. Corre exactamente:
   `uv run ${CLAUDE_SKILL_DIR}/scripts/mapear.py`
   (para pobreza extrema agrega `--indicador pobre_extremo`). Si falta
   `datos/peru_departamental_simple.geojson`, el script lo baja solo.
3. Si el script se detiene por un `assert` (menos de 25 departamentos o alguno sin dato), no lo "arregles" uniendo
   por nombre: revisa que el código tenga dos dígitos como texto y avisa al usuario.
4. Abre `mapas/pobreza_departamento.png` con Read para revisarlo.
5. Responde con los tres departamentos de más y de menos pobreza (un decimal), la ruta del mapa y la tabla
   `mapas/pobreza_departamento_2024.csv`. Menciona la diferencia máxima con `referencias/` que imprime el script.

## Reglas fijas (ya están en el script)

- Une por código: `ubigeo[:2]` con `FIRST_IDDP`, ambos como texto de dos dígitos.
- Nunca por nombre: «APURIMAC» no es «Apurímac».
- Exige 25 departamentos y ninguno sin dato.
- Lima (15) y Callao (07) van separados.
- Un solo color de claro a oscuro que empieza en 0; nunca arcoíris.
- Leyenda con la unidad: «% de personas». Nota: «Fuente: INEI, ENAHO 2024».
- Pondera con `facpob07`.

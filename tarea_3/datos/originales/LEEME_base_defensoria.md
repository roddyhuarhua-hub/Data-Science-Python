# Casos de los Reportes Mensuales de Conflictos Sociales (Defensoría del Pueblo), enero 2015 a agosto 2026

Todos los datos vienen de fuentes públicas: los Reportes Mensuales de Conflictos Sociales de la Defensoría del Pueblo del Perú. 138 meses se descargaron de www.defensoria.gob.pe y 2 de un espejo oficial del Estado (sinia.minam.gob.pe). No hay datos de empresas ni de clientes.

## Archivos

- `defensoria_casos_por_mes_2015_2026.csv` (y la misma tabla en `.xlsx`): una fila por caso y por mes de reporte. Son 27,903 filas: 20,693 de casos activos y 7,210 de casos latentes, en 140 reportes (del N.° 131, enero 2015, al N.° 270, agosto 2026).
- `fuentes_por_mes.csv`: un renglón por mes con el número de reporte, el nombre del archivo, el enlace al PDF y cuántos casos activos y latentes se extrajeron.

## Columnas

| Columna | Qué es |
|---|---|
| `reporte_n`, `anio`, `mes` | Número del reporte y mes/año al que corresponde |
| `estado` | `activo` o `latente`, según la sección del reporte en que aparece el caso |
| `codigo` | Código del caso, cuando el reporte lo trae (casi nunca: 0.7 % de los activos) |
| `caso` | Descripción del caso tal como la escribe la Defensoría; sirve como nombre del caso |
| `departamento`, `provincia`, `distrito` | Ubicación. En los latentes solo se separa el departamento; el resto está en `ubicacion` |
| `ubicacion` | Texto de ubicación del reporte |
| `ubigeo`, `nivel_ubicacion`, `ubigeos` | Ubigeo INEI asignado al lugar (97 % de las filas), si es de distrito, provincia o departamento, y todos los ubigeos cuando el caso abarca varios |
| `tipo_texto_original`, `tipo_conflicto` | Tipo de conflicto como aparece en el texto, y normalizado a las categorías de la Defensoría (socioambiental, asuntos de gobierno local, etc.) |
| `hay_dialogo` | `si` / `no` según la ficha del caso activo ("HAY DIÁLOGO" / "NO HAY DIÁLOGO") |
| `sin_hechos_en_mes` | `True` si el reporte dice que no hubo nuevos hechos ese mes |
| `archivo_reporte`, `url_reporte` | Reporte de donde salió la fila y su enlace |

## Lo que se pidió y no está en la tabla

Estas columnas no se extrajeron y quedan fuera, en vez de inventarlas:

- **Actividad** en los socioambientales (minería, hidrocarburos, energía, etc.): no hay columna aparte. La actividad suele leerse en la descripción del caso.
- **Fase** (temprana, escalamiento, crisis, desescalamiento, diálogo): no se extrajo.
- **Quién conduce el diálogo**: solo está si hay o no diálogo.
- **Muertos y heridos**: no se extrajeron.
- **Casos resueltos o retirados**: solo están los activos y los latentes.
- En los **latentes** no hay dato de diálogo ni de provincia/distrito por separado.

## Cómo se extrajeron

1. Se descargaron los PDF de los reportes mensuales; los enlaces están en `fuentes_por_mes.csv`.
2. Se pasó cada PDF a texto conservando la disposición de las columnas de la página.
3. De la sección de casos activos se leyó cada ficha (ubicación, tipo, caso, diálogo, etc.) y de la sección de casos latentes cada renglón de su tabla.
4. Se asignó el ubigeo comparando el texto de ubicación con la lista de distritos, provincias y departamentos del INEI.
5. Para esta entrega solo se filtró desde enero 2015, se normalizó el tipo de conflicto y el campo de diálogo, y se unieron activos y latentes en una sola tabla.

## Advertencias

- La lectura es automática. En los **latentes**, la tabla del PDF tiene varias columnas, y a veces el texto del caso mezcla trozos del caso vecino o de la columna de tipo. Conviene revisar a mano antes de usar ese texto.
- 783 filas no tienen tipo normalizado porque el texto original no lo trae o vino cortado.
- El reporte de agosto 2026 es el N.° 270, aunque en la tabla de origen estaba anotado como 269. Aquí se corrigió.
- El número de casos por mes puede diferir en uno o dos del total que declara cada reporte.

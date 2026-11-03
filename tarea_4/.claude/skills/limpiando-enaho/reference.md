# Referencia de la base `salidas/personas_2024.parquet`

Una fila por **residente habitual** (108,664 en 2024). Factor de expansión de personas: `facpob07`.

## Columnas

| Columna | Origen | Qué es |
|---|---|---|
| `conglome`, `vivienda`, `hogar`, `codperso` | ambos | Llaves, como **texto** con ceros a la izquierda |
| `anio` | sumaria | Año de la encuesta (en el original se llama `aÑo`) |
| `ubigeo` | sumaria | Código de distrito, texto de 6 dígitos |
| `departamento` | construida | `ubigeo[:2]`, texto de 2 dígitos (ver tabla abajo) |
| `dominio` | sumaria | 1 Costa norte · 2 Costa centro · 3 Costa sur · 4 Sierra norte · 5 Sierra centro · 6 Sierra sur · 7 Selva · 8 Lima Metropolitana |
| `lima_metropolitana` | construida | `dominio == 8` |
| `estrato` | sumaria | 1 a 8; de 1 a 5 es urbano, 6 a 8 rural |
| `urbano`, `area` | construidas | `estrato <= 5`; «Urbana» o «Rural» |
| `p203` | miembros | Parentesco con el jefe: 1 jefe, 2 cónyuge, 3 hijo, 4 yerno/nuera, 5 nieto, 6 padres/suegros, 7 otro pariente, 8 trabajador del hogar, 9 pensionista, 10 otro no pariente |
| `p207`, `sexo` | miembros | 1 Hombre, 2 Mujer |
| `p208a`, `edad` | miembros | Edad en años |
| `grupo_edad` | construida | 0-13 · 14-29 · 30-44 · 45-59 · 60 y más |
| `pobreza` | sumaria | 1 pobre extremo · 2 pobre no extremo · 3 no pobre (**categoría, no promedio**) |
| `pobre` | construida | `pobreza <= 2` |
| `pobre_extremo` | construida | `pobreza == 1` |
| `mieperho` | sumaria | Miembros del hogar |
| `factor07` | sumaria | Factor de expansión del hogar |
| `facpob07` | miembros | Factor de expansión de la persona: **úsalo en toda cifra** |

## Residentes habituales

`(p204 == 1 & p205 == 2) | (p204 == 2 & p206 == 1)`: miembro del hogar que no estuvo ausente más de 30 días, o no
miembro que estuvo presente más de 30 días. El script ya aplica el filtro.

## Códigos de departamento (`departamento`)

| Código | Departamento | Código | Departamento | Código | Departamento |
|---|---|---|---|---|---|
| 01 | Amazonas | 10 | Huánuco | 19 | Pasco |
| 02 | Áncash | 11 | Ica | 20 | Piura |
| 03 | Apurímac | 12 | Junín | 21 | Puno |
| 04 | Arequipa | 13 | La Libertad | 22 | San Martín |
| 05 | Ayacucho | 14 | Lambayeque | 23 | Tacna |
| 06 | Cajamarca | 15 | Lima (incluye Lima Metropolitana) | 24 | Tumbes |
| 07 | Callao | 16 | Loreto | 25 | Ucayali |
| 08 | Cusco | 17 | Madre de Dios | | |
| 09 | Huancavelica | 18 | Moquegua | | |

Filtra siempre por código (`departamento == "08"`), nunca por nombre.

## Ejemplo: pobreza de un departamento

```bash
uv run python -c "import pandas as pd; b=pd.read_parquet('salidas/personas_2024.parquet'); d=b[b.departamento=='08']; print(round((d.pobre*d.facpob07).sum()/d.facpob07.sum()*100,1))"
```

## Cifras oficiales 2024 para contrastar

Pobreza 27.6 % · extrema 5.5 % · urbana 24.8 % · rural 39.3 % · Lima Metropolitana 28.2 %. Por departamento:
`referencias/pobreza_departamento_2024.csv`. Las oficiales se calculan con la sumaria y `factor07 × mieperho`; con la
base de personas y `facpob07` pueden diferir en una o dos décimas.

## Otras variables

Si piden algo que no está (ingreso, gasto, educación, empleo), dilo: hay que agregar otro módulo del INEI
(por ejemplo, 03 Educación, 05 Empleo) y extender `scripts/limpiar.py`; no lo improvises en la respuesta.

# Borrador: cobre, oro y pobreza monetaria por departamento, Perú 2024

## Pregunta
En 2024, con precios altos del cobre y del oro, ¿los departamentos que más cobre producen tienen menos pobreza monetaria que el resto del Perú?

## Fuentes
- BCRP, cotización anual del cobre LME (¢US$/lb): `PM05568XA`.
- BCRP, cotización anual del oro LBMA (US$/onza troy): `PM05570XA`.
- BCRP, cotización mensual del cobre LME: `PN01652XM` (2015-01 a 2024-12).
- BCRP (datos del MINEM), producción de cobre por departamento 2024, series `RD155..DA` (p. ej. Moquegua `RD15529DA`, Arequipa `RD15519DA`, Áncash `RD15517DA`, Apurímac `RD15518DA`, Tacna `RD15532DA`).
- INEI, ENAHO 2024 (código 966): módulo 34 (Sumaria) y módulo 02 (miembros del hogar). Base validada con la skill `limpiando-enaho` (resultado «TODO OK», pobreza nacional 27.5 %, INEI 27.6 %). Todo ponderado con `facpob07`, residentes habituales.

## Definición
«Departamentos cupríferos» = los cinco con más cobre en 2024: Moquegua (18; 475,930 tm.f, 17.4 % del total), Arequipa (04; 453,836; 16.6 %), Áncash (02; 443,516; 16.2 %), Apurímac (03; 321,527; 11.8 %) y Tacna (23; 245,627; 9.0 %).

## Hallazgos
1. **Precios altos.** El cobre promedió 384.8 ¢US$/lb en 2023 y 414.6 en 2024 (+7.8 %). El oro pasó de US$ 1,943.4 a US$ 2,388.0 por onza (+22.9 %). Fuente: BCRP, `PM05568XA` y `PM05570XA`.
2. **Los cinco cupríferos juntos tienen menos pobreza que el resto.** 19.7 % frente a 28.5 % en el resto del país (9 puntos de diferencia). Fuente: INEI, ENAHO 2024, cálculo propio sobre `salidas/personas_2024.parquet`. Sin Lima, el resto sube a 29.4 %.
3. **Pero hay heterogeneidad entre los cinco.** Moquegua 10.9 %, Arequipa 15.8 %, Áncash 22.9 %, Tacna 23.9 %, Apurímac 24.1 %. Los tres últimos son cercanos o algo menores que el nacional (27.5 %), y Lima (26.9 %) y varios departamentos no mineros tienen valores similares. Fuente: INEI, ENAHO 2024.
4. **Hay departamentos con poca pobreza que no son cupríferos y cupríferos no tan bajos.** Ica 5.9 % (puesto 8 en cobre) es el más bajo del país; Cajamarca 45.0 %, Loreto 42.6 % y Puno 40.4 % son los más altos. Fuente: INEI, ENAHO 2024, `mapas/pobreza_departamento_2024.csv`.
5. **Brecha de área.** Pobreza rural 39.4 % y urbana 24.7 %. Fuente: INEI, ENAHO 2024.

## Figuras y mapa
- Precio mensual del cobre LME 2015-2024: `figuras/bcrp_PN01652XM_2015-01_2024-12.png`
- Pobreza por departamento: `figuras/pobre_por_departamento_2024.png`
- Pobreza por área: `figuras/pobre_por_area_2024.png`
- Mapa: `mapas/pobreza_departamento.png` (tabla: `mapas/pobreza_departamento_2024.csv`)

## Limitaciones
- Asociación descriptiva de un solo año (2024); no se afirma ninguna causa. No se evalúa si el precio del cobre o del oro afecta la pobreza (solo se compara 2023-2024 en precios, y la pobreza solo en 2024).
- Los cinco departamentos se eligieron por producción absoluta, no por peso del cobre en su economía. Producción y pobreza pueden depender de otros factores (urbanización, Lima, otros sectores) que no se controlan.
- No se analizó el oro por departamento ni otros metales.
- Los porcentajes de ENAHO tienen error muestral; no se calcularon intervalos de confianza, y las diferencias pequeñas entre departamentos (p. ej. Áncash, Tacna, Apurímac) pueden no ser significativas.
- El mapa difiere de la referencia del repositorio hasta 0.52 puntos (impreso por la skill).
- La pobreza en departamentos mineros puede estar en distritos distintos de las minas; el nivel departamental oculta esa variación.

# datos/raw · respaldo de datos crudos

Aquí se guarda lo que devolvió cada fuente **tal cual llegó**, antes de cualquier limpieza.
Nada de esta carpeta se edita a mano.

| Archivo | Qué es |
|---|---|
| `AAAA-MM-DD/rss_<medio>_<feed>.xml` | Respuesta RSS completa de cada feed ese día |
| `AAAA-MM-DD/manifiesto.csv` | URL, fecha y hora de descarga, código HTTP, bytes y huella `sha256` de cada archivo |

Cómo se genera:

- `python scripts/respaldar_raw.py` descarga los 9 feeds y los guarda aquí, **sin tocar** `datos/noticias.csv`.
- Desde ahora, cada corrida de `01_recoleccion.ipynb` también guarda aquí la respuesta de cada feed (función `descargar_feed`).

**Limitación:** las respuestas originales del 13 y 14 de octubre de 2026 no se guardaron en su momento
y los feeds RSS ya rotaron, así que no se pueden recuperar. Lo que sí queda es el historial de git de
`datos/noticias.csv` (commits `1e1cc78`, `f3f2790`, `621a108`, `506d9a9`). Ver `BITACORA.md`, D14.

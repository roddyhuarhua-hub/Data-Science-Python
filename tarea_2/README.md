# Tarea 2 – Voces y documentos peruanos: del archivo escaneado al texto buscable

**Pregunta:** ¿Podemos convertir documentos escaneados y entrevistas en audio peruanas en un archivo de texto estructurado y buscable?

**Estudiante:** RoddyHuarhua (@roddyhuarhua-hub) · **Dashboard público:** _(pegar aquí el enlace de Streamlit Cloud)_

**Respuesta corta:** sí para impresos y habla clara. Los impresos se leen con un CER de 0,18 y el audio leído se transcribe con un WER de 0,04. Pero las fotos con letras decorativas, los manuscritos y el ruido de la calle todavía necesitan revisión humana, y el LLM acierta en 15 de cada 20 extracciones.

## Corpus y fuentes

| Corpus | Volumen | Fuente y licencia | Fecha de extracción |
|---|---|---|---|
| A. Documentos | 25 imágenes: 8 impresos, 8 fotos con sombra o inclinación, 9 manuscritos | Wikimedia Commons. Licencias: dominio público (14), CC BY-SA 2.0/3.0/4.0, CC BY 3.0/4.0 y CC0. Autor y licencia de cada archivo en `datos/fuentes.csv` | 25–26 oct 2026 |
| B. Audio | 24 clips, 48,2 min: 20 clips de ~80 s de un solo hablante, 1 conversación de 2 hablantes y 3 entrevistas reales | OpenSLR 73, *Crowdsourced high-quality Peruvian Spanish speech data set* (Google, CC BY-SA 4.0; Guevara-Rukoz et al., 2020). Wikimedia Commons (CC BY-SA 4.0): entrevistas en El Agustino (JorgeFlores-pe, Wikimedia Perú) y a Aurora Coronado, de Fenmucarinap (QM Keen) | 25–26 oct 2026 |

Los archivos originales no están en Git (`datos/raw/` está en el `.gitignore`). `datos/fuentes.csv` guarda la URL, la licencia y la forma de recuperar cada archivo; `t2.recolectar_documentos()` y `t2.recolectar_audio()` los vuelven a bajar. La carpeta `datos/ejemplos/` solo trae miniaturas de los 25 documentos y 45 s de 7 clips, todos con licencia libre y sin datos personales.

**Descartes:** 8 imágenes de Commons no eran documentos legibles (retratos, una portada sin texto, una foto de personas con la placa ilegible, un libro en vitrina y dibujos sin texto). Se reemplazaron hasta completar 8/8/9 (lista `EXCLUIR` en `t2.py`). No hubo duplicados por hash ni audios sin voz. El cartel "Picante de cuy" (doc_005) quedó marcado como ilegible para PaddleOCR, pero se mantuvo porque una persona lo lee sin problema y es justo un caso difícil.

**Seudonimización:** en los textos publicados se reemplazaron 7 personas privadas por `[PERSONA_n]`: las 3 vecinas entrevistadas en El Agustino y los 4 ganadores del concurso de la resolución de Mache. En la miniatura de doc_001 esos nombres están difuminados, y el clip de El Agustino donde se escuchan sus nombres no se publica como audio. Se mantienen los nombres de figuras públicas o históricas, como Ricardo Palma, el alcalde firmante o la dirigente que habla en conferencia de prensa.

## Pipeline

1. **OCR (base):** PaddleOCR 3.x, PP-OCRv5 con `lang=es`, en CPU y sin preprocesamiento. **Alternativa:** EasyOCR (`es`).
2. **ASR (base):** faster-whisper `small` (int8, CPU, `beam_size=5`) con VAD Silero. La diarización usa huellas WeSpeaker y clustering (`voz.py` de la Sesión 13) y exporta CSV, SRT y TXT. **Alternativa:** Parakeet TDT 0.6B v3 (NVIDIA).
3. **Seudonimización:** se reemplazan DNI, RUC, teléfonos, correos y una lista de nombres privados (`t2.seudonimizar`) después de leer cada texto.
4. **Evaluación:** se calculan CER y WER sobre la misma muestra fija de 10 documentos (3 impresos, 3 fotos, 4 manuscritos) y 10 clips. Las referencias de documentos las transcribió a mano el estudiante. Las de audio son las transcripciones humanas que trae OpenSLR 73.
5. **LLM:** Qwen2.5-1.5B-Instruct corre en local, en CPU, y extrae campos en JSON para los 49 registros. Luego un humano audita 20 casos.

## Resultados (de `02_evaluacion.ipynb`)

| Modalidad | Modelo | Error | Velocidad |
|---|---|---|---|
| Documentos | **PaddleOCR** (base) | **CER 0,379** | 15,4 s/página |
| Documentos | EasyOCR | CER 0,416 | 9,6 s/página |
| Audio | faster-whisper small (base) | WER 0,070 | RTF 1,94 |
| Audio | **Parakeet TDT 0.6B v3** | **WER 0,038** | RTF 0,08 |

CER por tipo de documento: impresos 0,175 (Paddle) frente a 0,304 (Easy); fotos 0,564 frente a 0,399; manuscritos 0,392 frente a 0,513.

**Acuerdo LLM-Humano: 15/20 (75 %).** Hubo 5 extracciones incorrectas: un tema inventado, una fecha copiada de un error del OCR, una cita sacada de otro clip, una cita no textual y un resumen con temas inventados.

`Resultados Test: WER: 0.04 | CER: 0.38 | Acuerdo LLM-Humano: 15/20`

## Hallazgos

1. **El tipo de documento importa más que el modelo.** PaddleOCR lee los impresos casi perfecto (CER 0,02 en la resolución de Mache y 0,06 en el Mercurio Peruano de 1791), pero falla en las fotos de la calle (0,56): con las letras decorativas del cartel "Picante de cuy" no lee nada. En fotos, EasyOCR le gana. Ningún modelo resuelve bien los manuscritos de Guamán Poma ni las cursivas de Palma.
2. **En audio, el modelo más chico fue también el más preciso y el más rápido.** Parakeet comete la mitad de errores que faster-whisper small (0,038 frente a 0,070) y en la conversación de 2 hablantes la diferencia es mayor (0,033 frente a 0,105). Además corre 24 veces más rápido en la misma CPU (RTF 0,08 frente a 1,94).
3. **El LLM resume bien, pero falla en los datos concretos.** Los 5 errores de la auditoría están en citas y fechas, no en el tema. Por eso las extracciones de fechas y citas necesitan siempre revisión humana.

## Limitaciones

1. **El audio evaluado es habla leída en estudio** (OpenSLR 73), y sus referencias son las transcripciones humanas del dataset. Las entrevistas reales con ruido de calle no tienen referencia y solo se revisan de forma cualitativa. Por eso el WER real en campo será más alto que 0,04.
2. **La diarización sobrecuenta voces en el ruido:** en la entrevista callejera de El Agustino detecta 5 hablantes donde hay 3. La muestra de 10 + 10 es chica: un solo documento (el cartel) mueve el CER de las fotos varios puntos.
3. **Todo corre en CPU.** PaddleOCR y los modelos de voz bajan varios GB la primera vez. Por eso el dashboard no ejecuta modelos: solo lee los resultados ya calculados. El LLM usado (1.5B parámetros) es chico; uno más grande probablemente acertaría más.

**Bonificación no realizada:** quechua de Huaylas con MMS. Los audios de Shansha están en `datos_sesion13.py` pero quedaron fuera del corpus en español.

## Cómo ejecutar en local

```bash
# dashboard (solo lee CSV)
pip install -r requirements.txt
streamlit run app.py

# notebooks (bajan datos y modelos; ~3 GB; Python 3.12)
pip install -r requirements-notebooks.txt
jupyter nbconvert --to notebook --execute --inplace 01_extraccion.ipynb
jupyter nbconvert --to notebook --execute --inplace 02_evaluacion.ipynb
```

## Estructura

| Archivo | Contenido |
|---|---|
| `01_extraccion.ipynb` | corpus, OCR, ASR, seudonimización, limpieza y EDA |
| `02_evaluacion.ipynb` | CER/WER, comparación de modelos, LLM y auditoría |
| `app.py` | dashboard de Streamlit |
| `t2.py` | funciones del pipeline |
| `voz.py`, `datos_sesion13.py` | scripts de la Sesión 13 |
| `datos/` | CSV de resultados, referencias, auditoría y `ejemplos/` publicables |
| `modelos/configuracion.json` | configuración de cada modelo y semillas |
| `evidencias_ia/` | capturas de la conversación con Claude Code |

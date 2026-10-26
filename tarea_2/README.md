# Tarea 2 – Voces y documentos peruanos: del archivo escaneado al texto buscable

**Pregunta:** ¿Podemos convertir documentos escaneados y entrevistas en audio peruanas en un archivo de texto estructurado y buscable?

**Estudiante:** RoddyHuarhua (@roddyhuarhua-hub) · **Dashboard público:** _(enlace de Streamlit Cloud)_

## Corpus y fuentes

| Corpus | Volumen | Fuente y licencia | Fecha de extracción |
|---|---|---|---|
| A. Documentos | 25 imágenes: 8 impresos, 8 fotos con sombra/inclinación, 9 manuscritos | Wikimedia Commons; licencia y autor de cada archivo en `datos/fuentes.csv` (CC BY, CC BY-SA, CC0 o dominio público) | _(ver celda 1 de `01_extraccion.ipynb`)_ |
| B. Audio | 20 clips de ~80 s (OpenSLR 73) + 1 entrevista de 2 hablantes + 3 entrevistas reales | OpenSLR 73, *Crowdsourced high-quality Peruvian Spanish speech* (Google, CC BY-SA 4.0); Wikimedia Commons (CC BY-SA 4.0): JorgeFlores-pe (Wikimedia Perú), QM Keen | _(ídem)_ |

Los archivos originales no están en Git (`datos/raw/` en `.gitignore`). `datos/fuentes.csv` tiene la URL, licencia y forma de recuperar cada uno; `t2.recolectar_documentos()` y `t2.recolectar_audio()` los vuelven a bajar.

## Pipeline

1. **OCR:** PaddleOCR 3.x (PP-OCRv5, `lang=es`, CPU). Alternativa: EasyOCR.
2. **ASR:** faster-whisper `small` (int8, CPU) con VAD Silero; diarización WeSpeaker + clustering (`voz.py` de la Sesión 13). Exporta CSV, SRT y TXT. Alternativa: Parakeet TDT 0.6B v3.
3. **Seudonimización:** DNI, RUC, teléfonos, correos y nombres de personas privadas (`t2.seudonimizar`), con revisión manual.
4. **Evaluación:** CER y WER sobre los mismos 10 documentos y 10 clips, con referencias manuales.
5. **LLM:** extracción de campos JSON (Qwen2.5 local) y auditoría humana de 20 casos.

## Resultados (de `02_evaluacion.ipynb`)

_(se completa con las métricas finales)_

## Hallazgos

1. _(pendiente de resultados)_
2. _(pendiente de resultados)_

## Limitaciones

1. Las referencias de audio parten de la transcripción humana que trae OpenSLR 73 (habla leída, revisada por el estudiante escuchando cada clip); no hay referencia de las entrevistas callejeras, que solo se evalúan cualitativamente.
2. Todo corre en CPU: PaddleOCR y los modelos de voz bajan varios GB la primera vez y el dashboard no ejecuta modelos, solo muestra resultados ya calculados.

## Cómo ejecutar en local

```bash
# dashboard (solo lee CSV)
pip install -r requirements.txt
streamlit run app.py

# notebooks (bajan datos y modelos; ~3 GB)
pip install -r requirements-notebooks.txt
jupyter nbconvert --to notebook --execute --inplace 01_extraccion.ipynb
jupyter nbconvert --to notebook --execute --inplace 02_evaluacion.ipynb
```

## Estructura

`01_extraccion.ipynb` · `02_evaluacion.ipynb` · `app.py` · `t2.py` (funciones) · `voz.py` y `datos_sesion13.py` (de las Sesiones 13) · `datos/` (CSV y `ejemplos/` publicables) · `modelos/configuracion.json` · `evidencias_ia/`

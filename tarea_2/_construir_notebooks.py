"""Genera 01_extraccion.ipynb y 02_evaluacion.ipynb (sin ejecutar). Uso: python _construir_notebooks.py"""
import nbformat as nbf


def nb(celdas):
    n = nbf.v4.new_notebook()
    n.cells = []
    for tipo, txt in celdas:
        n.cells.append(nbf.v4.new_markdown_cell(txt.strip()) if tipo == "md" else nbf.v4.new_code_cell(txt.strip()))
    n.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    return n


COMUN = r'''
import sys, json, platform, datetime, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import plotly.express as px
from IPython.display import Image, display
import t2

pd.set_option("display.max_colwidth", 120)
FIGS = Path("figuras"); FIGS.mkdir(exist_ok=True)

def mostrar(fig, nombre):
    """Muestra el gráfico interactivo y además una copia PNG para que se vea en GitHub."""
    fig.write_html(FIGS / f"{nombre}.html", include_plotlyjs="cdn")
    try:
        fig.write_image(FIGS / f"{nombre}.png", width=900, height=450, scale=1)
        display(Image(filename=str(FIGS / f"{nombre}.png")))
    except Exception as e:
        print("(sin PNG estático:", type(e).__name__, ")")
    fig.show()
'''

E1 = [
("md", r'''
# Tarea 2 · Parte 1 — Corpus y extracción (OCR + ASR)

**Pregunta guía:** ¿Podemos convertir documentos escaneados y entrevistas en audio peruanas en un archivo de texto estructurado y buscable?

| | |
|---|---|
| **Estudiante** | RoddyHuarhua (@roddyhuarhua-hub) |
| **Fecha de extracción** | se imprime en la celda siguiente (ejecución del notebook) |
| **Documentos (corpus A)** | 25 imágenes de Wikimedia Commons: 8 impresos, 8 fotos con sombra o inclinación, 9 manuscritos. Licencias libres (CC BY, CC BY-SA, CC0 o dominio público), registradas archivo por archivo en `datos/fuentes.csv`. 9 de ellos son los que usó la Sesión 10; el resto sale de búsquedas en Commons. |
| **Audio (corpus B)** | OpenSLR 73 *Crowdsourced high-quality Peruvian Spanish speech* (Google, **CC BY-SA 4.0**), 20 clips de ~80 s de un solo hablante + 1 entrevista de 2 hablantes; y 3 entrevistas reales de Wikimedia Commons (**CC BY-SA 4.0**: El Agustino, Lima ×2; Aurora Coronado, Fenmucarinap). Atribución en `datos/fuentes.csv`. |
| **OCR** | PaddleOCR 3.x, PP-OCRv5, `lang="es"`, motor PyTorch (`engine="transformers"`), sin corrección de orientación ni "planchado" de página, CPU. |
| **ASR** | faster-whisper `small` (CTranslate2, int8, CPU), `language="es"`, `beam_size=5`, **VAD activado** (Silero), diarización con huellas WeSpeaker + clustering (voz.py, Sesión 13). |
| **Entorno** | versiones exactas en la celda siguiente. |

Los archivos originales se guardan en `datos/raw/` y **no** se suben a Git (ver `.gitignore`); `datos/fuentes.csv` explica cómo recuperarlos (`python -c "import t2; t2.recolectar_documentos(); t2.recolectar_audio()"`).
'''),
("code", COMUN + r'''
import importlib.metadata as md
def ver(p):
    try: return md.version(p)
    except Exception: return "no instalado"
print("Fecha de extracción:", datetime.date.today().isoformat())
print("Python", platform.python_version(), "|", platform.platform())
for p in ["paddleocr", "paddlex", "torch", "transformers", "faster-whisper", "ctranslate2", "pyannote.audio", "easyocr", "jiwer", "plotly"]:
    print(f"  {p:15s} {ver(p)}")
'''),
("md", "## 1. Corpus A: documentos\nSe descargan con la API de Commons (User-Agent descriptivo, 1 s de pausa entre pedidos), versión de 1600 px de ancho. Solo se aceptan licencias libres; los duplicados se detectan por hash SHA-1 del archivo."),
("code", r'''
docs = t2.recolectar_documentos()
print("Documentos:", len(docs)); print(docs["tipo"].value_counts().to_string())
docs[["id", "tipo", "titulo_commons", "licencia"]]
'''),
("code", r'''
try:
    desc_doc = pd.read_csv("datos/raw/documentos/descartes_descarga.csv")
except Exception:
    desc_doc = pd.DataFrame(columns=["archivo", "motivo"])
print("Candidatos descartados al descargar:", len(desc_doc))
desc_doc
'''),
("md", "## 2. Corpus B: audio\nOpenSLR 73 se lee por partes (HTTP Range) con `datos_sesion13.py` (copia de `datos.py` de la Sesión 13): no se bajan los 900 MB de cada zip. Cada clip une 16 frases seguidas de **un mismo hablante**, con 0,5 s de silencio entre frases."),
("code", r'''
aud = t2.recolectar_audio()
print(f"Clips: {len(aud)} | minutos: {aud.duracion_seg.sum()/60:.1f} | multihablante: {(aud.n_hablantes_real == 2).sum()} + entrevistas reales")
aud[["id", "fuente", "condicion", "duracion_seg", "licencia"]]
'''),
("md", "## 3. Limpieza: duplicados por hash y archivos sin contenido útil"),
("code", r'''
import hashlib
dup_doc = docs[docs.duplicated("sha1")]
dup_aud = aud[aud.duplicated("sha1")]
print("Documentos duplicados por hash:", len(dup_doc), "| audios duplicados por hash:", len(dup_aud))

import voz
voz_seg = {}
for r in aud.itertuples():
    x = voz.cargar_audio(r.archivo_audio)
    voz_seg[r.id] = sum(b - a for a, b in voz.tramos_de_voz(x))
aud["segundos_con_voz"] = aud.id.map(voz_seg).round(1)
sin_voz = aud[aud.segundos_con_voz < 3]
print("Audios sin voz (VAD < 3 s de habla):", len(sin_voz))
aud = aud[~aud.id.isin(sin_voz.id) & ~aud.id.isin(dup_aud.id)].reset_index(drop=True)
aud[["id", "duracion_seg", "segundos_con_voz"]].T
'''),
("md", "## 4. OCR con PaddleOCR (los 25 documentos)\nRespaldo crudo (texto, confianza, número de líneas y tiempo por página) en `datos/raw/documentos/ocr_paddle_base.json`."),
("code", r'''
rutas_doc = [Path(a) for a in docs.archivo]
ocr = t2.ocr_paddle(rutas_doc)
docs = docs.merge(ocr.rename(columns={"archivo": "nombre"}), left_on=docs.archivo.str.split("/").str[-1], right_on="nombre").drop(columns=["key_0", "nombre"], errors="ignore")
docs["n_caracteres"] = docs.texto.str.len()
print(f"Tiempo total OCR: {docs.segundos.sum():.0f} s ({docs.segundos.mean():.1f} s por página)")
docs[["id", "tipo", "n_lineas", "confianza_media", "n_caracteres", "segundos"]].round(2)
'''),
("code", r'''
# Documentos ilegibles: menos de 20 caracteres reconocidos o confianza media < 0,5
ilegibles = docs[(docs.n_caracteres < 20) | (docs.confianza_media < 0.5)]
print("Documentos marcados como ilegibles:", len(ilegibles))
ilegibles[["id", "tipo", "titulo_commons", "n_caracteres", "confianza_media"]]
'''),
("md", "## 5. ASR con faster-whisper + VAD + diarización\nTodos los clips con faster-whisper `small` en CPU y VAD. La diarización se aplica a los audios con más de un hablante: la entrevista de 2 hablantes de OpenSLR (de la que conocemos la verdad) y la entrevista callejera de El Agustino con dos vendedoras. Se exportan SRT y TXT por clip a `datos/raw/audio/salidas/`."),
("code", r'''
multi = list(aud[(aud.n_hablantes_real == 2) | aud.condicion.str.contains("dos vendedoras")].id)
print("Se diarizan:", multi)
asr = t2.asr_faster_whisper([Path(a) for a in aud.archivo_audio], "small", diarizar_ids=tuple(multi))
aud = aud.merge(asr.drop(columns=["duracion_seg"]), left_on=aud.archivo_audio.str.split("/").str[-1], right_on="archivo").drop(columns=["key_0", "archivo"], errors="ignore")
aud["rtf"] = (aud.segundos_proceso / aud.duracion_seg).round(3)
aud["n_palabras"] = aud.texto.str.split().str.len()
print(f"Audio transcrito: {aud.duracion_seg.sum()/60:.1f} min en {aud.segundos_proceso.sum()/60:.1f} min de CPU (RTF medio {aud.rtf.mean():.2f})")
aud[["id", "duracion_seg", "n_palabras", "n_hablantes", "rtf"]]
'''),
("code", r'''
for i in multi:
    print(f"── {i}: diarización ({aud.set_index('id').n_hablantes[i]} hablantes detectados)")
    txt = Path(f"datos/raw/audio/salidas/fw_small/{i}.txt").read_text(encoding="utf-8")
    print(t2.seudonimizar(txt, t2.nombres_privados())[0][:700], "\n")  # ya seudonimizado (ver sección 6)
'''),
("md", "## 6. Seudonimización\nRegla: se reemplazan DNI (8 dígitos), RUC, teléfonos celulares y correos, y los nombres de **personas privadas** que aparezcan (por ejemplo, vendedores entrevistados en la calle). Los nombres de figuras históricas o públicas que firman documentos públicos (Ricardo Palma, firmantes del Acta de Independencia) no son datos personales protegidos y se mantienen. La lista `NOMBRES_PRIVADOS` se completa después de **leer cada texto**: el método automático no reemplaza la revisión humana."),
("code", r'''
# Completar tras la revisión manual de los textos: {"Nombre real": "Seudónimo"}
# Lista {"Nombre real": "Seudónimo"} armada tras leer cada texto; vive en datos/raw/nombres_privados.json (fuera de Git).
# Revisión: las vecinas entrevistadas en la calle (clip_022 y clip_023) son personas privadas, también con las
# variantes que el ASR escribió mal. Aurora Coronado (clip_024) habla como representante de Fenmucarinap: se mantiene.
NOMBRES_PRIVADOS = t2.nombres_privados()
print("Nombres privados en la lista:", len(NOMBRES_PRIVADOS))
conteo = {}
for df, col in [(docs, "texto"), (aud, "texto")]:
    nuevos, ns = zip(*[t2.seudonimizar(t, NOMBRES_PRIVADOS) for t in df[col]])
    df[col] = list(nuevos); conteo[col + ("_ocr" if df is docs else "_asr")] = sum(ns)
    df["reemplazos"] = list(ns)
print("Entidades reemplazadas:", conteo)
print(pd.concat([docs.loc[docs.reemplazos > 0, ["id", "reemplazos"]], aud.loc[aud.reemplazos > 0, ["id", "reemplazos"]]]).to_string(index=False) or "ninguna")
'''),
("md", "## 7. Análisis exploratorio (Plotly Express)"),
("code", r'''
cuenta = docs.tipo.value_counts().rename_axis("tipo").reset_index(name="documentos")
ch = docs.groupby("tipo").n_caracteres.median()
titulo = f"Corpus balanceado (8/8/9), pero los {ch.idxmin()}s rinden menos texto: mediana de {ch.min():.0f} caracteres vs {ch.max():.0f} en {ch.idxmax()}s"
fig = px.bar(cuenta, x="tipo", y="documentos", text="documentos", title=titulo, color="tipo")
mostrar(fig, "g1_documentos_por_tipo")
'''),
("code", r'''
aud["fuente_corta"] = np.where(aud.fuente.str.startswith("OpenSLR"), "OpenSLR 73", "Wikimedia Commons")
m = aud.groupby("fuente_corta").duracion_seg.sum() / 60
titulo = f"{m.get('OpenSLR 73', 0):.0f} de {m.sum():.0f} minutos vienen de habla leída (OpenSLR); las entrevistas reales son pocos clips pero largos"
fig = px.bar(aud.sort_values("duracion_seg"), x="id", y="duracion_seg", color="fuente_corta", title=titulo,
             labels={"duracion_seg": "duración (s)", "id": "clip", "fuente_corta": "fuente"})
mostrar(fig, "g2_duracion_por_clip")
'''),
("code", r'''
largo = pd.concat([pd.DataFrame({"modalidad": "OCR (caracteres)", "longitud": docs.n_caracteres}),
                   pd.DataFrame({"modalidad": "ASR (palabras)", "longitud": aud.n_palabras})])
titulo = (f"El OCR es muy desigual ({docs.n_caracteres.min()}–{docs.n_caracteres.max()} caracteres); "
          f"el ASR es homogéneo salvo las entrevistas largas ({aud.n_palabras.median():.0f} palabras de mediana)")
fig = px.histogram(largo, x="longitud", facet_col="modalidad", nbins=20, title=titulo)
fig.update_xaxes(matches=None)
mostrar(fig, "g3_longitud_textos")
'''),
("md", "## 8. Validación: extremos de cada corpus\nComprobamos que los extremos de los histogramas tienen sentido mirando el texto."),
("code", r'''
cols = ["id", "tipo", "n_caracteres", "confianza_media"]
print("OCR más largos"); display(docs.nlargest(3, "n_caracteres")[cols + ["texto"]])
print("OCR más cortos"); display(docs.nsmallest(3, "n_caracteres")[cols + ["texto"]])
'''),
("code", r'''
cols = ["id", "condicion", "duracion_seg", "n_palabras"]
print("Clips más largos"); display(aud.nlargest(3, "duracion_seg")[cols + ["texto"]])
print("Clips más cortos"); display(aud.nsmallest(3, "duracion_seg")[cols + ["texto"]])
'''),
("md", "## 9. Exportación a CSV"),
("code", r'''
documentos = pd.DataFrame({
    "id": docs.id, "archivo": docs.archivo, "tipo": docs.tipo,
    "fuente": "Wikimedia Commons (" + docs.licencia + ")",
    "texto_ocr": docs.texto,
    "modelo_ocr": "PaddleOCR " + ver("paddleocr") + " PP-OCRv5 (lang=es, engine=transformers, CPU, sin orientación/unwarping)",
    "texto_referencia": "",
})
transcripciones = pd.DataFrame({
    "id": aud.id, "archivo_audio": aud.archivo_audio, "duracion_seg": aud.duracion_seg,
    "idioma": "es (variante peruana documentada por la fuente)", "texto_asr": aud.texto,
    "modelo_asr": "faster-whisper " + ver("faster-whisper") + " small (int8, CPU, VAD on, beam 5)",
    "n_hablantes": aud.n_hablantes.fillna(1).astype(int), "texto_referencia": "",
})
fuentes = pd.concat([
    pd.DataFrame({"id": docs.id, "modalidad": "documento", "fuente_url": docs.fuente_url, "licencia": docs.licencia,
                  "autor": docs.autor, "acceso": "API de Commons; t2.recolectar_documentos() (ancho 1600 px)"}),
    pd.DataFrame({"id": aud.id, "modalidad": "audio", "fuente_url": aud.fuente_url, "licencia": aud.licencia,
                  "autor": aud.fuente, "acceso": "t2.recolectar_audio() (OpenSLR por HTTP Range; Commons Special:FilePath)"}),
])
documentos.to_csv("datos/documentos.csv", index=False)
transcripciones.to_csv("datos/transcripciones.csv", index=False)
fuentes.to_csv("datos/fuentes.csv", index=False)
aud[["id", "referencia_dataset", "condicion", "fuente_corta", "rtf", "segundos_proceso"]].to_csv("datos/raw/audio/meta_clips.csv", index=False)
for nombre, df in [("documentos", documentos), ("transcripciones", transcripciones), ("fuentes", fuentes)]:
    print(nombre, df.shape)
documentos.head()
'''),
("code", "transcripciones.head()"),
("code", "fuentes.head()"),
("code", r'''
# Ejemplos publicables para el dashboard (licencia libre, sin datos personales): todas las imágenes reducidas y 6 clips cortos
from PIL import Image as PImg
import soundfile as sf
(t2.EJEMPLOS / "img").mkdir(exist_ok=True); (t2.EJEMPLOS / "audio").mkdir(exist_ok=True)
for r in docs.itertuples():
    im = PImg.open(r.archivo).convert("RGB"); im.thumbnail((900, 900)); im.save(t2.EJEMPLOS / "img" / f"{r.id}.jpg", quality=80)
# Solo clips de OpenSLR: en las entrevistas de Commons se oyen los nombres reales de las vecinas.
for i in aud.id[:3].tolist() + aud.id[10:13].tolist() + [m for m in multi if aud.set_index("id").fuente_corta[m] == "OpenSLR 73"]:
    x, sr = sf.read(f"datos/raw/audio/{i}.wav"); t2.guardar_ogg(x[: 45 * sr], sr, t2.EJEMPLOS / "audio" / f"{i}.ogg")
print(sum(p.stat().st_size for p in t2.EJEMPLOS.rglob("*") if p.is_file()) / 1e6, "MB en datos/ejemplos/")
'''),
]

E2 = [
("md", r'''
# Tarea 2 · Parte 2 — Evaluación, comparación de modelos y extracción con LLM

**Reglas que sigue este notebook**

1. La muestra de evaluación (10 documentos y 10 clips) se elige **una sola vez** con semilla fija, de los mismos corpus de la Parte 1, antes de ver ninguna métrica.
2. Todos los modelos se evalúan sobre **exactamente** esos 20 archivos, con su configuración definida de antemano (no se ajustan parámetros mirando los resultados).
3. Referencias:
   - **Documentos:** transcripción manual hecha por el estudiante, mirando cada imagen, en `datos/referencias_documentos.csv`.
   - **Audio:** los 10 clips son de OpenSLR 73, cuyo corpus trae una transcripción **humana** frase por frase (hecha por los voluntarios del proyecto de Google). El estudiante escuchó cada clip y corrigió la referencia donde no coincidía con lo que se oye (`datos/referencias_audio.csv`).
4. Normalización idéntica para referencia e hipótesis: minúsculas, sin puntuación, espacios simples, se quitan las marcas `[HABLANTE_n]` (no son palabras habladas). Las tildes se conservan.
'''),
("code", COMUN + r'''
import time
docs = pd.read_csv("datos/documentos.csv")
aud = pd.read_csv("datos/transcripciones.csv").merge(pd.read_csv("datos/raw/audio/meta_clips.csv"), on="id")
'''),
("md", "## 1. Muestra de evaluación (fija)"),
("code", r'''
muestra_doc = pd.concat([docs[docs.tipo == t].sample(n, random_state=42) for t, n in {"impreso": 3, "foto": 3, "manuscrito": 4}.items()])
con_ref = aud[aud.referencia_dataset.notna() & (aud.referencia_dataset != "")]
muestra_aud = pd.concat([con_ref[con_ref.condicion.str.contains("2 hablantes")],
                         con_ref[con_ref.condicion.str.contains("mujer")].sample(5, random_state=42),
                         con_ref[con_ref.condicion.str.contains("hombre")].sample(4, random_state=42)])
print("Documentos:", muestra_doc.id.tolist()); print(muestra_doc.tipo.value_counts().to_string())
print("Clips:", muestra_aud.id.tolist()); print(muestra_aud.condicion.str.split(",").str[-1].value_counts().to_string())
'''),
("code", r'''
# Plantillas de referencia: se crean una vez y el estudiante las completa a mano
ref_doc_csv, ref_aud_csv = Path("datos/referencias_documentos.csv"), Path("datos/referencias_audio.csv")
if not ref_doc_csv.exists():
    muestra_doc.assign(texto_referencia="")[["id", "tipo", "archivo", "texto_referencia"]].to_csv(ref_doc_csv, index=False)
if not ref_aud_csv.exists():
    muestra_aud.assign(texto_referencia=muestra_aud.referencia_dataset, corregido_por_estudiante="")[["id", "archivo_audio", "texto_referencia", "corregido_por_estudiante"]].to_csv(ref_aud_csv, index=False)
ref_doc = pd.read_csv(ref_doc_csv, dtype=str).fillna(""); ref_aud = pd.read_csv(ref_aud_csv, dtype=str).fillna("")
# Referencia e hipótesis se seudonimizan igual (nombres de personas privadas → [PERSONA_n]) antes de medir
ref_doc["texto_referencia"] = [t2.seudonimizar(t, t2.nombres_privados())[0] for t in ref_doc.texto_referencia]
faltan = (ref_doc.texto_referencia.str.strip() == "").sum()
print(f"Referencias de documentos completas: {10 - faltan}/10" + ("  ← FALTA transcribir a mano" if faltan else ""))
REF_DOC = dict(zip(ref_doc.id, ref_doc.texto_referencia)); REF_AUD = dict(zip(ref_aud.id, ref_aud.texto_referencia))
'''),
("code", r'''
# Se copian las referencias a los CSV principales (solo filas de la muestra; el resto queda vacío)
docs["texto_referencia"] = docs.id.map(REF_DOC).fillna("")
aud_out = pd.read_csv("datos/transcripciones.csv"); aud_out["texto_referencia"] = aud_out.id.map(REF_AUD).fillna("")
docs.to_csv("datos/documentos.csv", index=False); aud_out.to_csv("datos/transcripciones.csv", index=False)
'''),
("md", "## 2. Línea base sin ajuste\n- **Documentos:** PaddleOCR por defecto (la misma salida de la Parte 1).\n- **Audio:** faster-whisper `small` en CPU (la misma salida de la Parte 1)."),
("code", r'''
def tabla_cer(textos: dict, modelo: str):
    return pd.DataFrame([{"id": i, "modelo": modelo, "tipo": docs.set_index("id").tipo[i],
                          "CER": t2.cer(REF_DOC[i], textos[i]) if REF_DOC[i].strip() else np.nan} for i in muestra_doc.id])
def tabla_wer(textos: dict, modelo: str, seg: dict, dur: dict):
    return pd.DataFrame([{"id": i, "modelo": modelo, "condicion": aud.set_index("id").condicion[i],
                          "WER": t2.wer(REF_AUD[i], textos[i]), "RTF": seg[i] / dur[i]} for i in muestra_aud.id])

base_doc = tabla_cer(dict(zip(docs.id, docs.texto_ocr)), "PaddleOCR (base)")
a = aud.set_index("id")
base_aud = tabla_wer(a.texto_asr.to_dict(), "faster-whisper small (base)", a.segundos_proceso.to_dict(), a.duracion_seg.to_dict())
print(f"LÍNEA BASE  CER PaddleOCR = {base_doc.CER.mean():.3f}   |   WER faster-whisper small = {base_aud.WER.mean():.3f}")
'''),
("md", "## 3. Modelos alternativos sobre las mismas muestras\n- **OCR:** EasyOCR (detector CRAFT + reconocedor CRNN, `lang=es`, CPU). Justificación: arquitectura distinta a PP-OCRv5, abierto (Apache 2.0) y liviano; Tesseract necesita un instalador de sistema en Windows.\n- **ASR:** Parakeet TDT 0.6B v3 (NVIDIA, CC BY 4.0) con la interfaz de `voz.py`: no es un modelo de lenguaje generativo, así que no debería inventar frases en silencios. Se mide WER y factor de tiempo real (RTF = segundos de proceso / duración)."),
("code", r'''
alt_ocr = t2.ocr_easyocr([Path(p) for p in muestra_doc.archivo])
alt_ocr["id"] = alt_ocr.archivo.str.replace(".jpg", "", regex=False)
alt_ocr["texto"] = [t2.seudonimizar(t, t2.nombres_privados())[0] for t in alt_ocr.texto]  # igual que la línea base
alt_doc = tabla_cer(dict(zip(alt_ocr.id, alt_ocr.texto)), "EasyOCR")
try:
    alt_asr = t2.asr_alternativo([Path(p) for p in muestra_aud.archivo_audio], "parakeet-v3"); nombre_alt = "Parakeet TDT 0.6B v3"
except Exception as e:
    print("Parakeet no pudo correr:", e, "→ se usa Whisper large-v3-turbo (transformers)")
    alt_asr = t2.asr_alternativo([Path(p) for p in muestra_aud.archivo_audio], "whisper-turbo"); nombre_alt = "Whisper large-v3-turbo"
alt_asr["id"] = alt_asr.archivo.str.replace(".wav", "", regex=False)
s = alt_asr.set_index("id")
alt_aud = tabla_wer(s.texto.to_dict(), nombre_alt, s.segundos_proceso.to_dict(), s.duracion_seg.to_dict())
alt_asr.assign(modelo=nombre_alt)[["id", "modelo", "texto"]].to_csv("datos/asr_alternativo.csv", index=False)
pd.concat([base_doc, alt_doc]).pivot(index="id", columns="modelo", values="CER").round(3)
'''),
("md", "## 4. Métricas finales y tabla comparativa"),
("code", r'''
comp = pd.concat([
    pd.concat([base_doc, alt_doc]).groupby("modelo").agg(CER=("CER", "mean")).assign(modalidad="documentos"),
    pd.concat([base_aud, alt_aud]).groupby("modelo").agg(WER=("WER", "mean"), RTF=("RTF", "mean")).assign(modalidad="audio"),
]).reset_index()
seg_doc = {"PaddleOCR (base)": docs.merge(pd.read_json("datos/raw/documentos/ocr_paddle_base.json").assign(id=lambda d: d.archivo.str[:-4]), on="id").query("id in @muestra_doc.id").segundos.mean(),
           "EasyOCR": alt_ocr.segundos.mean()}
comp["seg_por_pagina"] = comp.modelo.map(seg_doc)
comp.round(3).to_csv("datos/metricas.csv", index=False)
comp.round(3)
'''),
("code", r'''
mejor_doc = comp[comp.modalidad == "documentos"].sort_values("CER").iloc[0]
mejor_aud = comp[comp.modalidad == "audio"].sort_values("WER").iloc[0]
print(f"Resultados Test: WER: {mejor_aud.WER:.2f} ({mejor_aud.modelo}) | CER: {mejor_doc.CER:.2f} ({mejor_doc.modelo})")
'''),
("md", "## 5. Casos difíciles: por tipo de documento y por condición de audio"),
("code", r'''
por_tipo = pd.concat([base_doc, alt_doc]).groupby(["tipo", "modelo"]).CER.mean().reset_index()
peor = por_tipo.groupby("tipo").CER.mean()
if peor.isna().all():
    print("Sin referencias de documentos todavía: el gráfico de CER por tipo se genera al completar datos/referencias_documentos.csv")
else:
    fig = px.bar(por_tipo, x="tipo", y="CER", color="modelo", barmode="group",
                 title=f"Los {peor.idxmax()}s son el caso más difícil (CER medio {peor.max():.0%}) y los {peor.idxmin()}s el más fácil ({peor.min():.0%})")
    mostrar(fig, "g4_cer_por_tipo")
por_tipo.pivot(index="tipo", columns="modelo", values="CER").round(3)
'''),
("code", r'''
w = pd.concat([base_aud, alt_aud]); w["condicion"] = w.condicion.str.split(",").str[-1].str.strip()
fig = px.bar(w.groupby(["condicion", "modelo"]).WER.mean().reset_index(), x="condicion", y="WER", color="modelo", barmode="group",
             title="WER por condición de grabación y modelo (mismos 10 clips)")
mostrar(fig, "g5_wer_por_condicion")
w.pivot_table(index="condicion", columns="modelo", values="WER").round(3)
'''),
("code", r'''
# Audio con ruido de calle (sin referencia): revisión cualitativa de la entrevista en El Agustino
calle = aud[aud.condicion.str.contains("El Agustino|vendedora", regex=True)]
for r in calle.itertuples():
    print(f"── {r.id} ({r.duracion_seg:.0f} s, ruido de calle): {r.texto_asr[:600]}\n")
'''),
("md", "## 6. Extracción estructurada con LLM (todos los documentos y clips)"),
("code", r'''
regs = pd.concat([pd.DataFrame({"id": docs.id, "modalidad": "documento", "texto": docs.texto_ocr}),
                  pd.DataFrame({"id": aud.id, "modalidad": "audio", "texto": aud.texto_asr})])
ext = t2.extraer_llm(regs)
ext.to_csv("datos/extraccion_llm.csv", index=False)
print(ext.shape, "| modelo:", ext.modelo_llm.iloc[0])
print("Respuestas sin JSON válido:", ext.campos_json.str.contains('"error"').sum())
ext.head()
'''),
("md", "## 7. Auditoría humana de 20 extracciones al azar (10 documentos + 10 audios)\n**Criterio:** una extracción es *completamente correcta* si (a) el JSON es válido y tiene solo las claves pedidas, (b) `tema` y `resumen` describen bien el texto, (c) todo dato presente (emisor, fecha, monto, citas, n.º de hablantes) aparece de verdad en el texto y (d) los datos ausentes van como `null`. Un solo campo inventado o equivocado la vuelve incorrecta. El estudiante revisa cada caso contra el texto y la imagen o el audio, y anota `correcto` (1/0) y `error` en `datos/auditoria_llm.csv`."),
("code", r'''
aud_csv = Path("datos/auditoria_llm.csv")
if not aud_csv.exists():
    m = pd.concat([ext[ext.modalidad == "documento"].sample(10, random_state=7), ext[ext.modalidad == "audio"].sample(10, random_state=7)])
    m.merge(regs[["id", "texto"]], on="id").assign(correcto="", error="")[["id", "modalidad", "texto", "campos_json", "correcto", "error"]].to_csv(aud_csv, index=False)
audit = pd.read_csv(aud_csv)
hechos = pd.to_numeric(audit.correcto, errors="coerce").notna().sum()
if hechos < 20:
    print(f"Auditoría pendiente: {hechos}/20 casos revisados. Completar la columna 'correcto' en datos/auditoria_llm.csv")
else:
    ok = int(pd.to_numeric(audit.correcto).sum())
    print(f"Acuerdo LLM-Humano: {ok}/20 ({ok/20:.0%})")
    print(audit.groupby("modalidad").correcto.sum().to_string())
    display(audit[pd.to_numeric(audit.correcto) == 0][["id", "modalidad", "error"]])
    pd.DataFrame([{"acuerdo": ok, "total": 20}]).to_csv("datos/auditoria_resumen.csv", index=False)
'''),
("md", r'''
## 8. Decisión y reflexión

*(Esta sección se escribe después de ver las métricas de arriba; se completa con los números finales.)*

- **Documentos:** …
- **Audio:** …
- **Por tipo de documento:** …
- **Por tipo de audio:** …
- **Elección para un entorno real (precisión, costo y latencia):** …
'''),
]

nbf.write(nb(E1), "01_extraccion.ipynb")
nbf.write(nb(E2), "02_evaluacion.ipynb")
print("ok")

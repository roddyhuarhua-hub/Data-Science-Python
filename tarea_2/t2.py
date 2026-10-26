"""Funciones de la Tarea 2: recolectar el corpus, OCR, ASR, seudonimizar, medir y extraer con un LLM.

Los notebooks 01_extraccion.ipynb y 02_evaluacion.ipynb llaman a estas funciones. Cada paso guarda
su resultado en datos/raw/ (fuera de Git): si ya existe, no se vuelve a calcular.

Se apoya en los scripts del curso: voz.py (Sesión 13, VAD + Whisper + diarización + seudonimización)
y datos_sesion13.py (copia de datos.py de la Sesión 13, descarga de OpenSLR 73 por partes).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
RAW = DATOS / "raw"
RAW_DOC = RAW / "documentos"
RAW_AUD = RAW / "audio"
EJEMPLOS = DATOS / "ejemplos"
for d in (RAW_DOC, RAW_AUD, EJEMPLOS):
    d.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "tarea2-ds-python-up/2026 (curso Data Science Python; github.com/roddyhuarhua-hub)"}
API = "https://commons.wikimedia.org/w/api.php"

# ───────────────────────────────────────────── A. documentos (Wikimedia Commons)
# Semillas: los 9 archivos que usó el profe en la Sesión 10, ya verificados.
SEMILLAS = [
    ("Acta de Creación de los Símbolos para el Distrito de Mache.jpg", "impreso"),
    ("500000 Intis 1988(Front).jpg", "impreso"),
    ("Pisco-punch-mercurio-peruano-1791.jpg", "impreso"),
    ("Placa Calle Capon.jpg", "foto"),
    ("Cartel Picante de cuy.JPG", "foto"),
    ("Menu Levaggi 09052010.jpg", "foto"),
    ("Peruvian Telephone Company receipt Lima 1895.JPG", "manuscrito"),
    ("Tarjeta de Ricardo Palma a Luis Antonio Eguiguren Escudero 24 octubre 1912.png", "manuscrito"),
    ("Acta de Independencia Peru.jpg", "manuscrito"),
]
# Búsquedas para completar cada tipo (se toman los primeros resultados con licencia libre).
BUSQUEDAS = {
    "impreso": ["Mercurio Peruano", "El Peruano diario 18", "Gaceta de Lima", "periódico Lima siglo XIX",
                "decreto Perú impreso", "Constitución Perú 1823"],
    "foto": ["Placa conmemorativa Lima", "Placa Centro histórico de Lima", "Placa Arequipa", "Placa Cusco",
             "cartel Lima calle"],
    "manuscrito": ["carta manuscrita Perú", "manuscrito Lima siglo XVIII", "Guaman Poma Nueva coronica",
                   "Archivo General de la Nación Perú manuscrito", "firma carta Bolívar Lima"],
}
META = {"impreso": 8, "foto": 8, "manuscrito": 9}
LICENCIAS_OK = re.compile(r"(CC0|CC BY|Public domain|PD|Dominio público|attribution)", re.I)


def _info_commons(titulos: list[str]) -> list[dict]:
    r = requests.get(API, headers=UA, timeout=60, params={
        "action": "query", "format": "json", "titles": "|".join("File:" + t for t in titulos),
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime|sha1", "iiurlwidth": 1600})
    r.raise_for_status()
    return list(r.json()["query"]["pages"].values())


def _buscar_commons(consulta: str, n: int = 15) -> list[str]:
    r = requests.get(API, headers=UA, timeout=60, params={
        "action": "query", "format": "json", "list": "search", "srnamespace": 6,
        "srsearch": f"{consulta} filetype:bitmap", "srlimit": n})
    r.raise_for_status()
    return [x["title"].removeprefix("File:") for x in r.json()["query"]["search"]]


def _limpio(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def recolectar_documentos() -> pd.DataFrame:
    """Baja 25 documentos (8 impresos, 8 fotos, 9 manuscritos) con su licencia. Guarda datos/raw/documentos/indice.csv."""
    indice = RAW_DOC / "indice.csv"
    if indice.exists():
        return pd.read_csv(indice)
    candidatos = [(t, tipo, "semilla Sesión 10") for t, tipo in SEMILLAS]
    for tipo, consultas in BUSQUEDAS.items():
        for c in consultas:
            candidatos += [(t, tipo, f"búsqueda: {c}") for t in _buscar_commons(c)]
            time.sleep(1)
    filas, vistos, descartes = [], set(), []
    cuenta = {k: 0 for k in META}
    for titulo, tipo, origen in candidatos:
        if cuenta[tipo] >= META[tipo] or titulo in vistos:
            continue
        vistos.add(titulo)
        pag = _info_commons([titulo])[0]
        if "imageinfo" not in pag:
            descartes.append({"archivo": titulo, "motivo": "no existe en Commons"})
            continue
        ii = pag["imageinfo"][0]
        em = ii.get("extmetadata", {})
        lic = _limpio(em.get("LicenseShortName", {}).get("value", ""))
        if not LICENCIAS_OK.search(lic):
            descartes.append({"archivo": titulo, "motivo": f"licencia no libre: {lic}"})
            continue
        url = ii.get("thumburl") or ii["url"]
        contenido = requests.get(url, headers=UA, timeout=120).content
        time.sleep(1)
        h = hashlib.sha1(contenido).hexdigest()
        if h in {f["sha1"] for f in filas}:
            descartes.append({"archivo": titulo, "motivo": "duplicado (mismo hash)"})
            continue
        n = len(filas) + 1
        ruta = RAW_DOC / f"doc_{n:03d}.jpg"
        ruta.write_bytes(contenido)
        cuenta[tipo] += 1
        filas.append({"id": f"doc_{n:03d}", "archivo": f"datos/raw/documentos/doc_{n:03d}.jpg", "tipo": tipo,
                      "titulo_commons": titulo, "autor": _limpio(em.get("Artist", {}).get("value", ""))[:120],
                      "licencia": lic, "fuente_url": ii["descriptionurl"], "origen": origen, "sha1": h})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(indice, index=False)
    pd.DataFrame(descartes).to_csv(RAW_DOC / "descartes_descarga.csv", index=False)
    return tabla


# ───────────────────────────────────────────── B. audio (OpenSLR 73 + Wikimedia Commons)
def recolectar_audio(n_clips_por_sexo: int = 10, frases_por_clip: int = 16, semilla: int = 7) -> pd.DataFrame:
    """Arma el corpus de audio. Guarda datos/raw/audio/indice.csv.

    - 20 clips de ~80 s de OpenSLR 73 (español peruano, Google, CC BY-SA 4.0): cada clip junta
      frases seguidas de UN mismo hablante; su referencia es la transcripción humana del dataset.
    - 1 entrevista multihablante armada con frases reales de dos hablantes (para medir diarización).
    - 3 entrevistas reales de Wikimedia Commons en español de Lima y la sierra central.
    """
    import random
    import zipfile

    import soundfile as sf

    import datos_sesion13 as d13

    indice = RAW_AUD / "indice.csv"
    if indice.exists():
        return pd.read_csv(indice)
    filas = []
    for sexo in ["female", "male"]:
        z = zipfile.ZipFile(d13.ZipRemoto(d13.OPENSLR73.format(sexo=sexo)))
        lineas = z.read("line_index.tsv").decode("utf-8").strip().splitlines()
        tabla = pd.DataFrame([l.split("\t") for l in lineas], columns=["id", "texto"])
        tabla["hablante"] = tabla["id"].str.rsplit("_", n=1).str[0]
        cuenta = tabla.groupby("hablante").size()
        hablantes = sorted(cuenta[cuenta >= frases_por_clip].index)
        random.Random(semilla).shuffle(hablantes)
        for h in hablantes[:n_clips_por_sexo]:
            frases = tabla[tabla["hablante"] == h].head(frases_por_clip)
            pedazos, textos = [], []
            for f in frases.itertuples():
                tmp = RAW_AUD / "tmp.wav"
                d13._guardar_16k(z.read(f"{f.id}.wav"), tmp)
                x, _ = sf.read(tmp, dtype="float32")
                pedazos += [x, np.zeros(int(0.5 * d13.SR), dtype=np.float32)]
                textos.append(f.texto.strip())
            n = len(filas) + 1
            ruta = RAW_AUD / f"clip_{n:03d}.wav"
            sf.write(ruta, np.concatenate(pedazos), d13.SR)
            filas.append({"id": f"clip_{n:03d}", "archivo_audio": f"datos/raw/audio/clip_{n:03d}.wav",
                          "fuente": "OpenSLR 73 (Google)", "licencia": "CC BY-SA 4.0",
                          "fuente_url": f"https://www.openslr.org/73/ (es_pe_{sexo}.zip, hablante {h})",
                          "condicion": f"leído, estudio, {'mujer' if sexo == 'female' else 'hombre'}",
                          "referencia_dataset": " ".join(textos), "n_hablantes_real": 1})
        (RAW_AUD / "tmp.wav").unlink(missing_ok=True)
    # entrevista con dos hablantes reales (turnos alternados, verdad conocida)
    d13.CARPETA = RAW_AUD / "sesion13"
    wav, verdad = d13.entrevista_simulada()
    n = len(filas) + 1
    destino = RAW_AUD / f"clip_{n:03d}.wav"
    destino.write_bytes(Path(wav).read_bytes())
    filas.append({"id": f"clip_{n:03d}", "archivo_audio": f"datos/raw/audio/clip_{n:03d}.wav",
                  "fuente": "OpenSLR 73 (Google), turnos de 2 hablantes", "licencia": "CC BY-SA 4.0",
                  "fuente_url": "https://www.openslr.org/73/", "condicion": "2 hablantes alternados",
                  "referencia_dataset": " ".join(verdad["texto"]), "n_hablantes_real": 2})
    # entrevistas reales de Commons (sin referencia: se revisan a mano en la Parte 2)
    d13.COMMONS = {k: v for k, v in d13.COMMONS.items() if v[2] == "es"}
    atrib = d13.bajar_commons()
    from voz import cargar_audio
    for a in atrib.itertuples():
        n = len(filas) + 1
        x = cargar_audio(str(d13.CARPETA / "entrevistas" / a.archivo))
        sf.write(RAW_AUD / f"clip_{n:03d}.wav", x, d13.SR)
        filas.append({"id": f"clip_{n:03d}", "archivo_audio": f"datos/raw/audio/clip_{n:03d}.wav",
                      "fuente": f"Wikimedia Commons ({a.autor})", "licencia": a.licencia, "fuente_url": a.fuente,
                      "condicion": "entrevista real: " + a.descripcion, "referencia_dataset": "",
                      "n_hablantes_real": None})
    tabla = pd.DataFrame(filas)
    tabla["duracion_seg"] = [round(sf.info(BASE / r).duration, 1) for r in tabla["archivo_audio"]]
    tabla["sha1"] = [hashlib.sha1((BASE / r).read_bytes()).hexdigest() for r in tabla["archivo_audio"]]
    tabla.to_csv(indice, index=False)
    return tabla


# ───────────────────────────────────────────── OCR
OPCIONES_PADDLE = dict(lang="es", use_doc_orientation_classify=False, use_doc_unwarping=False,
                       use_textline_orientation=False)


def ocr_paddle(rutas: list[Path], nombre: str = "paddle_base") -> pd.DataFrame:
    """PaddleOCR 3.x (PP-OCRv5, lang=es) sin personalización. Respaldo crudo en datos/raw/documentos/ocr_<nombre>.json."""
    salida = RAW_DOC / f"ocr_{nombre}.json"
    if salida.exists():
        return pd.DataFrame(json.loads(salida.read_text(encoding="utf-8")))
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(engine="transformers", device="cpu", **OPCIONES_PADDLE)
    filas = []
    for r in rutas:
        t0 = time.perf_counter()
        res = ocr.predict(str(r))[0]
        filas.append({"archivo": Path(r).name, "texto": " ".join(res["rec_texts"]),
                      "confianza_media": float(np.mean(res["rec_scores"])) if len(res["rec_scores"]) else 0.0,
                      "n_lineas": len(res["rec_texts"]), "segundos": round(time.perf_counter() - t0, 2)})
    salida.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return pd.DataFrame(filas)


def ocr_easyocr(rutas: list[Path]) -> pd.DataFrame:
    """OCR alternativo: EasyOCR (CRAFT + CRNN, lang=es), configuración por defecto, en CPU."""
    salida = RAW_DOC / "ocr_easyocr.json"
    if salida.exists():
        return pd.DataFrame(json.loads(salida.read_text(encoding="utf-8")))
    import easyocr
    lector = easyocr.Reader(["es"], gpu=False)
    filas = []
    for r in rutas:
        t0 = time.perf_counter()
        textos = lector.readtext(str(r), detail=0, paragraph=False)
        filas.append({"archivo": Path(r).name, "texto": " ".join(textos), "n_lineas": len(textos),
                      "segundos": round(time.perf_counter() - t0, 2)})
    salida.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return pd.DataFrame(filas)


# ───────────────────────────────────────────── ASR
def asr_faster_whisper(rutas: list[Path], tamano: str = "small", nombre: str | None = None,
                       diarizar_ids: tuple[str, ...] = ()) -> pd.DataFrame:
    """faster-whisper en CPU (int8), idioma es, VAD activado. Exporta SRT y TXT por clip a datos/raw/audio/salidas/."""
    nombre = nombre or f"fw_{tamano}"
    salida = RAW_AUD / f"asr_{nombre}.json"
    if salida.exists():
        return pd.DataFrame(json.loads(salida.read_text(encoding="utf-8")))
    from faster_whisper import WhisperModel

    import voz
    modelo = WhisperModel(tamano, device="cpu", compute_type="int8")
    carpeta = RAW_AUD / "salidas" / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    filas = []
    for r in rutas:
        r = Path(r)
        audio = voz.cargar_audio(str(r))
        t0 = time.perf_counter()
        segs, _ = modelo.transcribe(audio, language="es", beam_size=5, vad_filter=True,
                                    condition_on_previous_text=False)
        segs = [voz.Segmento(s.start, s.end, s.text.strip()) for s in segs]
        seg_asr = time.perf_counter() - t0
        n_h = None
        if r.stem in diarizar_ids and segs:
            segs = voz.diarizar(audio, segs, device="cpu")
            n_h = len({s.hablante for s in segs})
        (carpeta / f"{r.stem}.srt").write_text(voz.a_srt(segs), encoding="utf-8")
        (carpeta / f"{r.stem}.txt").write_text(voz.a_texto(segs), encoding="utf-8")
        texto = " ".join((f"[HABLANTE_{s.hablante[1:]}] " if s.hablante else "") + s.texto for s in segs)
        filas.append({"archivo": r.name, "texto": texto, "n_hablantes": n_h, "segundos_proceso": round(seg_asr, 2),
                      "duracion_seg": round(len(audio) / voz.SR, 1)})
    salida.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return pd.DataFrame(filas)


def asr_alternativo(rutas: list[Path], clave: str = "parakeet-v3") -> pd.DataFrame:
    """ASR alternativo con la interfaz común de voz.py (Parakeet TDT 0.6B v3 por defecto), en CPU."""
    salida = RAW_AUD / f"asr_{clave}.json"
    if salida.exists():
        return pd.DataFrame(json.loads(salida.read_text(encoding="utf-8")))
    import voz
    t = voz.Transcriptor(clave, device="cpu")
    filas = []
    for r in rutas:
        audio = voz.cargar_audio(str(r))
        t0 = time.perf_counter()
        segs = t.segmentos(audio, idioma="es")
        filas.append({"archivo": Path(r).name, "texto": " ".join(s.texto for s in segs),
                      "segundos_proceso": round(time.perf_counter() - t0, 2),
                      "duracion_seg": round(len(audio) / voz.SR, 1)})
    salida.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return pd.DataFrame(filas)


# ───────────────────────────────────────────── seudonimización
PATRONES = {
    "DNI": (re.compile(r"\b\d{8}\b"), "[DNI]"),
    "TELEFONO": (re.compile(r"\b9\d{2}[\s-]?\d{3}[\s-]?\d{3}\b"), "[TELEFONO]"),
    "CORREO": (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[CORREO]"),
    "RUC": (re.compile(r"\b(10|20)\d{9}\b"), "[RUC]"),
}


def seudonimizar(texto: str, nombres: dict[str, str]) -> tuple[str, int]:
    """Reemplaza DNI, RUC, teléfonos, correos y los nombres de personas privadas listados. Devuelve (texto, n_reemplazos)."""
    import voz
    if not isinstance(texto, str):
        return texto, 0
    n = 0
    for _, (patron, marca) in PATRONES.items():
        texto, k = patron.subn(marca, texto)
        n += k
    if nombres:
        nuevo = voz.seudonimizar(texto, nombres)
        n += sum(nuevo.count(s) - texto.count(s) for s in set(nombres.values()))
        texto = nuevo
    return texto, n


# ───────────────────────────────────────────── métricas (mismo criterio para todo)
def normalizar(texto: str) -> str:
    import voz
    texto = re.sub(r"\[HABLANTE_\d+\]", " ", str(texto or ""))  # marcas de hablante no son palabras habladas
    return voz.normalizar(texto)


def cer(ref: str, hip: str) -> float:
    import jiwer
    return jiwer.cer(normalizar(ref), normalizar(hip) or "∅")


def wer(ref: str, hip: str) -> float:
    import jiwer
    return jiwer.wer(normalizar(ref), normalizar(hip) or "∅")


# ───────────────────────────────────────────── extracción estructurada con LLM
PROMPT = """Eres un asistente que extrae datos de documentos y entrevistas peruanas.
Lee el TEXTO (puede tener errores de OCR o de transcripción) y responde SOLO con un objeto JSON con estas claves:
- "modalidad": "{modalidad}"
- "tema": tema principal en 3 a 8 palabras
- "resumen": una o dos oraciones
{extra}
Reglas: usa null si el dato no aparece en el texto. No inventes. No agregues otras claves.

TEXTO:
{texto}
"""
EXTRA = {
    "documento": '- "emisor": quién emite el documento o null\n- "fecha": fecha que aparece o null\n- "monto": monto de dinero que aparece o null',
    "audio": '- "numero_hablantes": número de voces distintas si se puede saber, o null\n- "citas_clave": lista de 1 a 2 frases textuales del texto, o null',
}
MODELO_OLLAMA = "qwen2.5:3b"
MODELO_HF = "Qwen/Qwen2.5-1.5B-Instruct"


def _json_de(respuesta: str) -> dict:
    m = re.search(r"\{.*\}", respuesta, re.S)
    try:
        return json.loads(m.group(0)) if m else {"error": "sin JSON", "crudo": respuesta[:300]}
    except json.JSONDecodeError:
        return {"error": "JSON inválido", "crudo": respuesta[:300]}


def extraer_llm(registros: pd.DataFrame) -> pd.DataFrame:
    """registros: columnas id, modalidad ('documento'/'audio'), texto. Usa Ollama si está prendido; si no, Qwen2.5 con transformers."""
    salida = RAW / "extraccion_llm_crudo.json"
    if salida.exists():
        return pd.DataFrame(json.loads(salida.read_text(encoding="utf-8")))
    try:
        requests.get("http://localhost:11434/api/tags", timeout=3).raise_for_status()
        motor = "ollama"
    except Exception:
        motor = "transformers"
        from transformers import pipeline
        gen = pipeline("text-generation", model=MODELO_HF, device="cpu")
    filas = []
    for r in registros.itertuples():
        prompt = PROMPT.format(modalidad=r.modalidad, extra=EXTRA[r.modalidad], texto=str(r.texto)[:2000])
        if motor == "ollama":
            resp = requests.post("http://localhost:11434/api/generate", timeout=300, json={
                "model": MODELO_OLLAMA, "prompt": prompt, "stream": False, "format": "json",
                "options": {"temperature": 0}}).json()["response"]
            modelo = f"{MODELO_OLLAMA} (Ollama, temperature=0)"
        else:
            resp = gen([{"role": "user", "content": prompt}], max_new_tokens=300, do_sample=False)[0]["generated_text"][-1]["content"]
            modelo = f"{MODELO_HF} (transformers, CPU, greedy)"
        filas.append({"id": r.id, "modalidad": r.modalidad, "campos_json": json.dumps(_json_de(resp), ensure_ascii=False),
                      "modelo_llm": modelo, "fecha": time.strftime("%Y-%m-%d")})
    salida.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return pd.DataFrame(filas)

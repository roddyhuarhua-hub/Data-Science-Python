"""Reel de la Tarea 3: voz clonada con Qwen3-TTS, subtítulos con Whisper, gráficos y música.

Adaptado del flujo de la Sesión 15 (texto a reel). Cada escena del guion trae su gráfico
(reel/recursos/escena_N.png, hecho con reel/hacer_graficos.py a partir de los datos).

Uso (desde la carpeta tarea_3, con la nota de voz propia de 15 a 25 s):
    python reel/hacer_reel.py --voz mi_voz.wav --musica reel/recursos/bach_preludio_do.wav

Prueba rápida sin modelos (tono de relleno, sirve para revisar el diseño del video):
    python reel/hacer_reel.py --prueba --musica reel/recursos/bach_preludio_do.wav

Archivos en reel/: reel.mp4, subtitulos.srt, portada.png, reel.wav
"""

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ANCHO, ALTO, FPS = 1080, 1920, 30
SR = 24000
PAUSA = 0.35          # silencio entre escenas, en segundos
MAX_ERROR = 0.25      # si Whisper entiende mal más del 25 % de las palabras, se repite la escena
NARANJA = (255, 140, 40)
FONDO_ARRIBA, FONDO_ABAJO = (16, 28, 46), (8, 10, 16)
DASHBOARD = "roddyhuarhua-hub.github.io/Data-Science-Python"
MUSICA = "Música: J. S. Bach, Preludio en Do mayor BWV 846 (dominio público), piano sintetizado"
BLANCO = (245, 245, 240)
GRIS = (175, 175, 170)
AVISO = "Voz generada con IA"
FFMPEG = get_ffmpeg_exe()


# ---------- utilidades ----------

def ffmpeg(*args):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True)


def fuente_tipografica(tam, negrita=True):
    candidatos = [
        "C:/Windows/Fonts/arialbd.ttf" if negrita else "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if negrita else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidatos:
        if Path(c).exists():
            return ImageFont.truetype(c, tam)
    return ImageFont.load_default(size=tam)


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9ñ ]+", " ", texto).split()


def tasa_error(esperado, oido):
    import jiwer
    return jiwer.wer(" ".join(normalizar(esperado)), " ".join(normalizar(oido)) or "vacio")


# ---------- paso 2: voz ----------

def preparar_referencia(voz, carpeta):
    """Convierte la nota de voz (m4a, ogg, mp3...) a wav mono y se queda con los primeros 20 s."""
    ref = carpeta / "voz_referencia.wav"
    ffmpeg("-i", str(voz), "-ac", "1", "-ar", str(SR), "-t", "20", str(ref))
    return ref


def cargar_whisper(tam, device):
    from faster_whisper import WhisperModel
    return WhisperModel(tam, device="cuda" if device.startswith("cuda") else "cpu",
                        compute_type="float16" if device.startswith("cuda") else "int8")


def transcribir(whisper, wav, palabras=False):
    # Le pasamos el audio ya leído (16 kHz, mono) para no depender de PyAV,
    # que en versiones nuevas rompe la lectura de archivos de faster-whisper.
    import librosa
    audio, _ = librosa.load(str(wav), sr=16000, mono=True)
    segmentos, _ = whisper.transcribe(audio, language="es", word_timestamps=palabras)
    segmentos = list(segmentos)
    texto = " ".join(s.text.strip() for s in segmentos)
    if not palabras:
        return texto
    return texto, [(w.start, w.end, w.word.strip()) for s in segmentos for w in s.words]


def narrar(escenas, ref, ref_texto, modelo_tts, device, whisper, carpeta):
    import torch
    from qwen_tts import Qwen3TTSModel

    print(f"Cargando {modelo_tts} (la primera vez descarga unos GB)...")
    tts = Qwen3TTSModel.from_pretrained(
        modelo_tts, device_map=device,
        dtype=torch.bfloat16 if device.startswith("cuda") else torch.float32)
    prompt = tts.create_voice_clone_prompt(ref_audio=str(ref), ref_text=ref_texto)

    audios = []
    for i, e in enumerate(escenas, 1):
        for intento in range(1, 4):
            t0 = time.time()
            wavs, sr = tts.generate_voice_clone(text=e["frase"], language="Spanish", voice_clone_prompt=prompt)
            audio = wavs[0].astype(np.float32)
            if sr != SR:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=SR)
            ruta = carpeta / f"escena_{i}.wav"
            sf.write(ruta, audio, SR)
            error = tasa_error(e["frase"], transcribir(whisper, ruta))
            print(f"  escena {i}, intento {intento}: {len(audio) / SR:.1f} s de audio en "
                  f"{time.time() - t0:.0f} s, error de Whisper {error:.0%}")
            if error <= MAX_ERROR:
                break
        audios.append(audio)
    return audios


def audio_de_prueba(escenas):
    """Sin modelos: un tono suave con la duración aproximada de cada frase (2.4 palabras por segundo)."""
    audios = []
    for e in escenas:
        dur = len(e["frase"].split()) / 2.4
        t = np.arange(int(dur * SR)) / SR
        audios.append((0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32))
    return audios


def palabras_de_prueba(escenas, tiempos):
    palabras = []
    for e, (ini, fin) in zip(escenas, tiempos):
        ws = e["frase"].split()
        paso = (fin - ini) / len(ws)
        palabras += [(ini + k * paso, ini + (k + 1) * paso, w) for k, w in enumerate(ws)]
    return palabras


def alinear_con_guion(escenas, tiempos, oidas):
    """Subtítulos con el texto del guion (bien escrito) y los tiempos de Whisper.

    Whisper a veces oye mal («Zikwani» por Sicuani) o parte cifras («13 .297»). Por eso
    mostramos las palabras del guion: las que Whisper reconoce toman su tiempo y las demás
    se reparten entre las vecinas según su largo.
    """
    from difflib import SequenceMatcher
    resultado = []
    for e, (ini, fin) in zip(escenas, tiempos):
        ws = e["frase"].split()
        oido = [w for w in oidas if ini - 0.3 <= w[0] <= fin + 0.1]
        t = [None] * len(ws)
        a = [" ".join(normalizar(x)) for x in ws]
        b = [" ".join(normalizar(x[2])) for x in oido]
        for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
            for k in range(blk.size):
                t[blk.a + k] = oido[blk.b + k][:2]
        anclas = [(-1, (ini, ini))] + [(k, v) for k, v in enumerate(t) if v] + [(len(ws), (fin, fin))]
        for (k0, v0), (k1, v1) in zip(anclas, anclas[1:]):
            hueco = range(k0 + 1, k1)
            if not hueco:
                continue
            desde, hasta = v0[1], max(v1[0], v0[1])
            pesos = [len(ws[k]) + 1 for k in hueco]
            x = desde
            for k, peso in zip(hueco, pesos):
                d = (hasta - desde) * peso / sum(pesos)
                t[k] = (x, x + d)
                x += d
        resultado += [(s, f, w) for (s, f), w in zip(t, ws)]
    return resultado


def tiempos_de_escenas(carpeta, n):
    """Para rehacer solo el video: los tiempos salen de las escenas ya narradas."""
    tiempos, t = [], PAUSA
    for i in range(1, n + 1):
        dur = sf.info(str(carpeta / f"escena_{i}.wav")).duration
        tiempos.append((t, t + dur))
        t += dur + PAUSA
    return tiempos


def acelerar(audio, factor, carpeta):
    """Habla más rápido sin cambiar el tono (filtro atempo de ffmpeg)."""
    if abs(factor - 1) < 1e-3:
        return audio
    ent, sal = carpeta / "_tmp_lento.wav", carpeta / "_tmp_rapido.wav"
    sf.write(ent, audio, SR)
    ffmpeg("-i", str(ent), "-af", f"atempo={factor}", "-ar", str(SR), str(sal))
    rapido, _ = sf.read(str(sal), dtype="float32")
    ent.unlink(); sal.unlink()
    return rapido


def con_musica(voz, musica, carpeta, volumen=0.3):
    """Mezcla música de fondo que baja sola cuando hablas (sidechain) y sube en las pausas."""
    dur = sf.info(str(voz)).duration
    salida = carpeta / "reel_con_musica.wav"
    filtro = (f"[1:a]aformat=sample_rates=48000:channel_layouts=mono,atrim=0:{dur:.2f},volume={volumen},"
              f"afade=t=in:d=1.5,afade=t=out:st={max(dur - 3, 0):.2f}:d=3[m];"
              "[0:a]asplit=2[v][sc];"
              "[m][sc]sidechaincompress=threshold=0.02:ratio=4:attack=30:release=500[md];"
              "[v][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    ffmpeg("-i", str(voz), "-stream_loop", "-1", "-i", str(musica), "-filter_complex", filtro,
           "-map", "[out]", "-ar", "48000", str(salida))
    return salida


def unir(audios, carpeta):
    silencio = np.zeros(int(PAUSA * SR), dtype=np.float32)
    partes, tiempos, t = [silencio], [], PAUSA
    for a in audios:
        tiempos.append((t, t + len(a) / SR))
        partes += [a, silencio]
        t += len(a) / SR + PAUSA
    partes.append(np.zeros(int(2.0 * SR), dtype=np.float32))   # 2 s para la tarjeta final
    crudo = carpeta / "reel_crudo.wav"
    sf.write(crudo, np.concatenate(partes), SR)
    final = carpeta / "reel.wav"
    ffmpeg("-i", str(crudo), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(final))
    return final, tiempos


# ---------- paso 3: subtítulos y video ----------

def bloques_de_subtitulo(palabras, max_palabras=5):
    """Agrupa palabras en bloques cortos; cada bloque se muestra entero y la palabra que suena va en naranja."""
    bloques, actual = [], []
    for w in palabras:
        actual.append(w)
        if len(actual) >= max_palabras or w[2].endswith((".", ",", "?", "!", ";", ":")):
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def srt(bloques, ruta):
    def ts(s):
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    lineas = []
    for i, b in enumerate(bloques, 1):
        lineas += [str(i), f"{ts(b[0][0])} --> {ts(b[-1][1])}", " ".join(w[2] for w in b), ""]
    ruta.write_text("\n".join(lineas), encoding="utf-8")


def fondo(imagen):
    """Fondo vertical: la imagen recortada y nítida, con un velo oscuro que deja leer el texto."""
    if imagen and Path(imagen).exists():
        im = Image.open(imagen).convert("RGB")
        escala = max(ANCHO / im.width, ALTO / im.height)
        im = im.resize((int(im.width * escala) + 1, int(im.height * escala) + 1), Image.LANCZOS)
        x, y = (im.width - ANCHO) // 2, (im.height - ALTO) // 2
        im = im.crop((x, y, x + ANCHO, y + ALTO)).filter(ImageFilter.UnsharpMask(radius=2, percent=80))
        return Image.blend(im, Image.new("RGB", (ANCHO, ALTO), (12, 10, 10)), 0.35)
    arriba, abajo = np.array(FONDO_ARRIBA), np.array(FONDO_ABAJO)
    k = np.linspace(0, 1, ALTO)[:, None, None]
    return Image.fromarray(np.broadcast_to(arriba * (1 - k) + abajo * k, (ALTO, ANCHO, 3)).astype(np.uint8))


def panel(ruta, ancho=980):
    """Gráfico de la escena como tarjeta con esquinas redondeadas (RGBA)."""
    g = Image.open(ruta).convert("RGB")
    g = g.resize((ancho, int(g.height * ancho / g.width)), Image.LANCZOS)
    mascara = Image.new("L", g.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, g.width - 1, g.height - 1), radius=28, fill=255)
    g.putalpha(mascara)
    return g


def centrado(d, y, texto, letra, color, borde=0):
    w = d.textlength(texto, font=letra)
    d.text(((ANCHO - w) / 2, y), texto, font=letra, fill=color, stroke_width=borde, stroke_fill=(0, 0, 0))


def partir(d, texto, letra, ancho_max):
    lineas, linea = [], ""
    for w in texto.split():
        prueba = (linea + " " + w).strip()
        if d.textlength(prueba, font=letra) > ancho_max and linea:
            lineas.append(linea)
            linea = w
        else:
            linea = prueba
    return lineas + [linea] if linea else lineas


def dibujar_subtitulo(d, bloque, t, letra):
    """Hasta dos líneas centradas en la zona media-baja, lejos de los botones de la app."""
    lineas, linea = [], []
    for w in bloque:
        prueba = " ".join(x[2] for x in linea + [w])
        if d.textlength(prueba, font=letra) > ANCHO - 160 and linea:
            lineas.append(linea)
            linea = [w]
        else:
            linea.append(w)
    lineas.append(linea)
    y = 1500
    for ln in lineas:
        total = d.textlength(" ".join(x[2] for x in ln), font=letra)
        x = (ANCHO - total) / 2
        for ini, fin, palabra in ln:
            color = NARANJA if ini <= t < fin + 0.05 else BLANCO
            d.text((x, y), palabra, font=letra, fill=color, stroke_width=4, stroke_fill=(0, 0, 0))
            x += d.textlength(palabra + " ", font=letra)
        y += 92


def video(guion, tiempos, palabras, audio, args, carpeta):
    escenas = guion["escenas"]
    duracion = sf.info(str(audio)).duration
    bloques = bloques_de_subtitulo(palabras)
    srt(bloques, carpeta / "subtitulos.srt")

    base = fondo(None)
    graficos = []
    for e in escenas:
        ruta = carpeta / e["imagen"] if e.get("imagen") else None
        graficos.append(panel(ruta) if ruta and ruta.exists() else None)
    f_cifra, f_etiq, f_sub = fuente_tipografica(150), fuente_tipografica(46), fuente_tipografica(60)
    f_peq, f_tit = fuente_tipografica(34, negrita=False), fuente_tipografica(70)

    def escena_en(t):
        for i, (ini, fin) in enumerate(tiempos):
            if t < fin + PAUSA:
                return i
        return None   # tarjeta final

    def cuadro(t):
        i = escena_en(t)
        im = base.copy()
        d = ImageDraw.Draw(im)
        # cabecera: autor, fuente y aviso de IA (todo el video)
        centrado(d, 110, args.autor, f_peq, BLANCO, borde=3)
        centrado(d, 156, f"Fuente: {args.fuente}", f_peq, GRIS, borde=3)
        d.rounded_rectangle((340, 210, 740, 266), radius=28, fill=(0, 0, 0), outline=NARANJA, width=2)
        centrado(d, 216, AVISO, f_peq, NARANJA)
        if i is None:
            y = 380
            for ln in partir(d, guion.get("titulo", ""), f_tit, ANCHO - 160):
                centrado(d, y, ln, f_tit, BLANCO, borde=5)
                y += 90
            if graficos[-1] is not None:
                g = graficos[-1].resize((760, int(760 * graficos[-1].height / graficos[-1].width)))
                im.paste(g, ((ANCHO - g.width) // 2, y + 40), g)
                y += g.height + 80
            centrado(d, y + 20, "Explora el dashboard:", f_etiq, BLANCO, borde=4)
            centrado(d, y + 84, DASHBOARD, f_peq, NARANJA, borde=3)
            centrado(d, y + 160, args.autor, f_etiq, BLANCO, borde=4)
            for k, ln in enumerate(partir(d, AVISO + " a partir de la voz del autor. " + MUSICA, f_peq, ANCHO - 160)):
                centrado(d, 1700 + 44 * k, ln, f_peq, GRIS, borde=2)
        else:
            e = escenas[i]
            ini = tiempos[i][0]
            entrada = min(1.0, max(0.0, (t - ini + PAUSA) / 0.4))   # la cifra y el gráfico entran suavemente
            cifra = e["cifra"].replace("¡¡", "")
            y = 330 + int(30 * (1 - entrada))
            color = tuple(int(c * entrada) for c in NARANJA)
            centrado(d, y, cifra, f_cifra, color, borde=7)
            y = 510
            for ln in partir(d, e["etiqueta"], f_etiq, ANCHO - 160):
                centrado(d, y, ln, f_etiq, BLANCO, borde=4)
                y += 58
            if graficos[i] is not None:
                g = graficos[i]
                if entrada < 1:
                    g = g.copy()
                    g.putalpha(g.getchannel("A").point(lambda a: int(a * entrada)))
                im.paste(g, ((ANCHO - g.width) // 2, 650 + int(40 * (1 - entrada))), g)
            actual = [b for b in bloques if b[0][0] - 0.1 <= t <= b[-1][1] + 0.25]
            if actual:
                dibujar_subtitulo(d, actual[-1], t, f_sub)
        # barra de avance
        d.rectangle((0, ALTO - 12, int(ANCHO * t / duracion), ALTO), fill=NARANJA)
        return im

    cuadro(tiempos[0][0] + 0.6).save(carpeta / "portada.png")

    salida = carpeta / "reel.mp4"
    proc = subprocess.Popen([
        FFMPEG, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
        "-i", str(audio),
        "-c:v", "libx264", "-preset", "medium", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(salida)],
        stdin=subprocess.PIPE)
    n = int(duracion * FPS)
    for k in range(n):
        proc.stdin.write(cuadro(k / FPS).tobytes())
        if k % (FPS * 10) == 0:
            print(f"  video: {k / FPS:.0f} de {duracion:.0f} s")
    proc.stdin.close()
    proc.wait()
    return salida


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--guion", default=str(Path(__file__).parent / "guion.json"))
    p.add_argument("--voz", help="tu nota de voz de unos 15 s (m4a, ogg, mp3 o wav)")
    p.add_argument("--autor", default="Roddy Huarhua")
    p.add_argument("--fuente", default=None, help="por defecto, la del guion")
    p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    p.add_argument("--whisper", default="small", help="tiny, base, small o medium")
    p.add_argument("--device", default="cpu", help="cpu, cuda:0 o mps")
    p.add_argument("--prueba", action="store_true", help="sin modelos: tono de relleno para probar el video")
    p.add_argument("--velocidad", type=float, default=1.0, help="1.1 = 10 %% más rápido, sin cambiar el tono")
    p.add_argument("--musica", help="archivo de música de fondo (por ejemplo musica/bach_preludio_do.wav)")
    p.add_argument("--rehacer-video", action="store_true",
                   help="usa la narración ya hecha (escena_*.wav y reel.wav) y solo rearma subtítulos y video")
    args = p.parse_args()

    guion = json.loads(Path(args.guion).read_text(encoding="utf-8"))
    args.fuente = args.fuente or guion.get("fuente", "")
    escenas = guion["escenas"]
    if any("¡¡" in e["cifra"] for e in escenas) and not args.prueba:
        sys.exit("Hay cifras marcadas con ¡¡ en el guion: corrígelas contra el texto antes de narrar.")
    carpeta = Path(args.guion).parent

    t0 = time.time()
    if args.prueba:
        audio, tiempos = unir(audio_de_prueba(escenas), carpeta)
        palabras = palabras_de_prueba(escenas, tiempos)
    elif args.rehacer_video:
        whisper = cargar_whisper(args.whisper, args.device)
        narradas = [sf.read(str(carpeta / f"escena_{i}.wav"), dtype="float32")[0] for i in range(1, len(escenas) + 1)]
        audio, tiempos = unir([acelerar(a, args.velocidad, carpeta) for a in narradas], carpeta)
        _, oidas = transcribir(whisper, audio, palabras=True)
        palabras = alinear_con_guion(escenas, tiempos, oidas)
    else:
        if not args.voz:
            sys.exit("Falta --voz con tu nota de voz.")
        whisper = cargar_whisper(args.whisper, args.device)
        ref = preparar_referencia(args.voz, carpeta)
        ref_texto = transcribir(whisper, ref)
        print(f"Tu grabación dice: «{ref_texto}»")
        narradas = narrar(escenas, ref, ref_texto, args.tts, args.device, whisper, carpeta)
        audio, tiempos = unir([acelerar(a, args.velocidad, carpeta) for a in narradas], carpeta)
        _, oidas = transcribir(whisper, audio, palabras=True)
        palabras = alinear_con_guion(escenas, tiempos, oidas)

    if args.musica:
        audio = con_musica(audio, args.musica, carpeta)
    print("Armando el video...")
    salida = video(guion, tiempos, palabras, audio, args, carpeta)
    mb = salida.stat().st_size / 1e6
    print(f"\nListo en {time.time() - t0:.0f} s: {salida} ({mb:.1f} MB, {sf.info(str(audio)).duration:.0f} s)")
    print(f"También: {carpeta / 'subtitulos.srt'} y {carpeta / 'portada.png'}")
    if mb > 10:
        print("Pesa más de 10 MB: GitHub no lo aceptará en un comentario. Avísame y bajamos la calidad.")


if __name__ == "__main__":
    main()

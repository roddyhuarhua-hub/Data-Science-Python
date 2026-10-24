"""Paso 1: del texto largo al guion del reel.

Uso:
    python guion.py --texto texto_fuente.md --solo-prompt > prompt.txt
    (pegar prompt.txt en chat.qwen.ai y guardar la respuesta en respuesta_qwen.txt)
    python guion.py --texto texto_fuente.md --respuesta respuesta_qwen.txt

Guarda salidas/guion.json y salidas/posts.md. Marca con ¡¡ toda cifra que no
aparece tal cual en el texto fuente: esas hay que revisarlas a mano.
"""

import argparse
import json
import re
import sys
from pathlib import Path

AVISO_IA = "Voz generada con IA a partir de mi propia voz."

PROMPT = """Eres guionista de reels de divulgación científica en español del Perú.
Convierte el TEXTO de abajo en el guion de un reel vertical de 45 a 55 segundos,
narrado en primera persona por su autor.

Reglas:
1. Exactamente 6 escenas. Entre todas, de 110 a 130 palabras habladas.
2. Cada escena tiene una sola idea y una sola cifra que salga tal cual en el TEXTO.
3. "frase" es lo que se dice en voz alta: escribe los números en palabras
   (por ejemplo "trece mil doscientas noventa y siete hectáreas").
4. "cifra" es el número como aparece en el TEXTO (por ejemplo "13 297" o "75 %").
5. "etiqueta" explica la cifra en pantalla, en 6 palabras o menos.
6. No inventes nada que no diga el TEXTO. No exageres: si el texto dice "cerca de",
   no digas "dentro de". Incluye al menos una limitación del estudio.
7. La primera escena engancha con una pregunta; la última cierra con la idea principal.
8. Además escribe tres posts para acompañar el reel: "linkedin" (80 a 120 palabras),
   "x" (menos de 260 caracteres) y "facebook" (50 a 80 palabras). En los posts las
   cifras van en números.

Responde SOLO con un JSON válido, sin texto antes ni después, con esta forma:
{
  "titulo": "...",
  "escenas": [
    {"frase": "...", "cifra": "...", "etiqueta": "..."}
  ],
  "posts": {"linkedin": "...", "x": "...", "facebook": "..."}
}

TEXTO:
<<<
{texto}
>>>
"""


def leer_texto(ruta):
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(ruta).pages)
    return ruta.read_text(encoding="utf-8")


def numeros(texto):
    """Cifras del texto sin separadores de miles: '13 297' -> '13297', '0,70' -> '0,70'."""
    encontrados = set()
    for m in re.finditer(r"\d+(?:[  .]\d{3})*(?:,\d+)?", texto):
        n = re.sub(r"[  .](?=\d{3}\b)", "", m.group())
        encontrados.add(n)
        encontrados.add(n.replace(",", "."))
    return encontrados


def extraer_json(respuesta):
    """El chat a veces envuelve el JSON en ```json ... ``` o añade texto: tomamos el bloque { }."""
    inicio, fin = respuesta.find("{"), respuesta.rfind("}")
    if inicio < 0 or fin < 0:
        sys.exit("No encontré un JSON en la respuesta. Pide al chat que responda solo con JSON.")
    return json.loads(respuesta[inicio:fin + 1])


def revisar(guion, fuente):
    validos = numeros(fuente)
    alertas = []
    for i, escena in enumerate(guion["escenas"], 1):
        for n in numeros(escena.get("cifra", "")):
            if n not in validos:
                alertas.append(f"Escena {i}: la cifra {escena['cifra']} no está en el texto")
                escena["cifra"] = "¡¡" + escena["cifra"]
                break
    for red, post in guion.get("posts", {}).items():
        for n in sorted(numeros(post)):
            if n not in validos and "." not in n:
                alertas.append(f"Post {red}: la cifra {n} no está en el texto")
    return alertas


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--texto", required=True, help="texto largo: .md, .txt o .pdf")
    p.add_argument("--solo-prompt", action="store_true", help="imprime el prompt para pegarlo en un chat")
    p.add_argument("--respuesta", help="archivo con lo que respondió el chat")
    p.add_argument("--salida", default="salidas")
    a = p.parse_args()

    fuente = leer_texto(a.texto)
    if a.solo_prompt or not a.respuesta:
        sys.stdout.reconfigure(encoding="utf-8")
        print(PROMPT.replace("{texto}", fuente.strip()))
        return

    guion = extraer_json(Path(a.respuesta).read_text(encoding="utf-8"))
    alertas = revisar(guion, fuente)

    salida = Path(a.salida)
    salida.mkdir(exist_ok=True)
    (salida / "guion.json").write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")

    posts = guion.get("posts", {})
    md = [f"# {guion.get('titulo', 'Reel')}", ""]
    for red in ("linkedin", "x", "facebook"):
        if red in posts:
            md += ["## " + {"linkedin": "LinkedIn", "x": "X", "facebook": "Facebook"}[red], "", posts[red].strip(), "", f"_{AVISO_IA}_", ""]
    (salida / "posts.md").write_text("\n".join(md), encoding="utf-8")

    palabras = sum(len(e["frase"].split()) for e in guion["escenas"])
    print(f"{len(guion['escenas'])} escenas, {palabras} palabras (unos {palabras / 2.4:.0f} s de audio)")
    for i, e in enumerate(guion["escenas"], 1):
        print(f"\n[{i}] {e['cifra']} · {e['etiqueta']}\n    {e['frase']}")
    print("\nAlertas:" if alertas else "\nSin alertas de cifras. Igual hay que leer cada frase contra el texto.")
    for x in alertas:
        print("  ¡¡ " + x)
    print(f"\nGuardé {salida / 'guion.json'} y {salida / 'posts.md'}")


if __name__ == "__main__":
    main()

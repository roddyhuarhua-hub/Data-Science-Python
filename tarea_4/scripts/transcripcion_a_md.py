"""Convierte una transcripción de `claude -p --output-format stream-json` en Markdown legible.

    uv run scripts/transcripcion_a_md.py evidencias_ia/integracion/ejecucion.jsonl

Escribe el .md al lado del .jsonl: cada mensaje, cada herramienta llamada con sus argumentos y un extracto de lo que
devolvió. Sirve como evidencia de uso de IA (opción B del issue: historial completo exportado).
"""
import json
import sys
from pathlib import Path


def corto(texto, n=1500):
    texto = str(texto)
    return texto if len(texto) <= n else texto[:n] + f"\n... [{len(texto) - n} caracteres más en el .jsonl]"


def main(archivo: Path) -> Path:
    lineas = ["# Transcripción: " + archivo.stem, ""]
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(linea)
        except json.JSONDecodeError:
            continue
        tipo = ev.get("type")
        if tipo == "system" and ev.get("subtype") == "init":
            lineas += [f"**Modelo:** {ev.get('model')} · **Servidores MCP:** "
                       f"{', '.join(s.get('name', '') + ' (' + s.get('status', '') + ')' for s in ev.get('mcp_servers', []))}",
                       f"**Skills:** {', '.join(ev.get('skills', []) or [])}", ""]
        elif tipo == "user" and isinstance(ev.get("message", {}).get("content"), str):
            lineas += ["## Pedido", "", ev["message"]["content"], ""]
        elif tipo in ("assistant", "user"):
            for b in ev.get("message", {}).get("content", []):
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    lineas += ["### Claude", "", b["text"], ""]
                elif b.get("type") == "tool_use":
                    lineas += [f"#### Herramienta: `{b.get('name')}`", "", "```json",
                               corto(json.dumps(b.get("input", {}), ensure_ascii=False, indent=1), 2000), "```", ""]
                elif b.get("type") == "tool_result":
                    contenido = b.get("content")
                    if isinstance(contenido, list):
                        contenido = "\n".join(c.get("text", "") for c in contenido if isinstance(c, dict))
                    lineas += ["<details><summary>Resultado</summary>", "", "```", corto(contenido), "```",
                               "", "</details>", ""]
        elif tipo == "result":
            lineas += ["## Resultado final", "", f"Turnos: {ev.get('num_turns')} · segundos: "
                       f"{round((ev.get('duration_ms') or 0) / 1000)} · costo USD: {ev.get('total_cost_usd')}", "",
                       str(ev.get("result", "")), ""]
    salida = archivo.with_suffix(".md")
    salida.write_text("\n".join(lineas), encoding="utf-8")
    return salida


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(main(Path(a)))

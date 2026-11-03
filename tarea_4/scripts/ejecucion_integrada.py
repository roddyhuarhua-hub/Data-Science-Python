"""La ejecución integrada de la Parte 3: UN solo pedido a Claude Code que orquesta el MCP del BCRP y las skills.

    uv run scripts/ejecucion_integrada.py               # con Sonnet
    uv run scripts/ejecucion_integrada.py --modelo opus

Corre en una copia limpia del proyecto (sin salidas/, figuras/, mapas/ ni informes/), para que se vea que Claude
limpia la ENAHO con la skill antes de graficar y mapear. Al terminar copia lo que produjo a tarea_4/ y deja:
  evidencias_ia/integracion/ejecucion.jsonl  la transcripción completa (herramientas, argumentos, resultados)
  evidencias_ia/integracion/ejecucion.md     la misma transcripción en Markdown legible
  informes/borrador_agente.md                el borrador que escribió el agente (el informe final se revisa a mano)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from transcripcion_a_md import main as a_markdown  # noqa: E402

PEDIDO = """Invoca cada skill con la herramienta Skill (limpiando-enaho, graficando-enaho, mapeando-enaho), no leyendo su SKILL.md a mano.

Pregunta de investigación: en 2024, con precios altos del cobre y del oro, ¿los departamentos que más
cobre producen tienen menos pobreza monetaria que el resto del Perú?

Responde con datos, en este orden, y sin hacer cuentas a mano:
1. Con el MCP bcrp: el precio promedio anual del cobre y del oro en 2023 y 2024 (busca las series de cotizaciones
   internacionales anuales y usa resumen), y guarda con graficar_serie un gráfico del precio mensual del cobre
   (LME) de 2015-01 a 2024-12.
2. Con el MCP bcrp: produccion_minera_departamental de cobre en 2024. Define como «departamentos cupríferos» los
   cinco con más producción y anota su código ccdd.
3. Invoca la skill limpiando-enaho con la herramienta Skill: la base de la ENAHO 2024 validada. Si la validación
   falla, detente y dilo.
4. Invoca la skill mapeando-enaho con la herramienta Skill: el mapa de pobreza por departamento. Invoca la skill
   graficando-enaho con la herramienta Skill: el gráfico de
   pobreza por departamento y el de área urbana y rural.
5. Con uv run python sobre salidas/personas_2024.parquet (ponderando con facpob07): la pobreza monetaria de los
   cinco departamentos cupríferos juntos, la del resto del país, y la de cada uno de los cinco.
6. Escribe informes/borrador_agente.md con: la pregunta, las fuentes (códigos de serie del BCRP y módulos de la
   ENAHO), al menos tres hallazgos con cifras y su fuente, las rutas de las figuras y el mapa, y las limitaciones.
   Son asociaciones descriptivas de un solo año: no afirmes causas.
Si una herramienta falla o no encuentra datos, dilo; no inventes cifras."""

COPIAR = [".claude/skills", "mcp/server.py", ".mcp.json", "pyproject.toml", "uv.lock", "datos", "referencias"]


def ruta_claude() -> str:
    ruta = shutil.which("claude")
    if ruta and ruta.lower().endswith(".cmd"):
        exe = Path(ruta).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return ruta or "claude"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", default="sonnet")
    a = p.parse_args()

    carpeta = Path(tempfile.mkdtemp(prefix="t4_integrada_"))
    for rel in COPIAR:
        o, d = RAIZ / rel, carpeta / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        if o.is_dir():
            shutil.copytree(o, d, ignore=shutil.ignore_patterns("__pycache__"))
        elif o.exists():
            shutil.copy(o, d)
    (carpeta / ".mcp.json").write_text(json.dumps({"mcpServers": {"bcrp": {
        "type": "stdio", "command": "uv", "args": ["run", "mcp/server.py"]}}}, indent=2), encoding="utf-8")

    cmd = [ruta_claude(), "-p", PEDIDO, "--output-format", "stream-json", "--verbose", "--model", a.modelo,
           "--strict-mcp-config", "--mcp-config", ".mcp.json",
           "--tools", "Bash,Read,Write,Edit,Glob,Grep,Skill",
           "--allowedTools", "mcp__bcrp,Skill,Bash,Read,Write,Edit,Glob,Grep"]
    entorno = dict(os.environ, UV_PROJECT_ENVIRONMENT=os.environ.get("UV_PROJECT_ENVIRONMENT", str(RAIZ / ".venv")))
    print(f"Corriendo en {carpeta} con {a.modelo} (tarda unos minutos)...", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=carpeta, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=3600, env=entorno)
    print(f"Terminó en {time.time() - t0:.0f} s (código {proc.returncode})")

    ev = RAIZ / "evidencias_ia" / "integracion"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "ejecucion.jsonl").write_text(proc.stdout, encoding="utf-8")
    if proc.stderr.strip():
        (ev / "ejecucion_stderr.txt").write_text(proc.stderr, encoding="utf-8")
    print(a_markdown(ev / "ejecucion.jsonl"))

    # Lo que produjo el agente pasa a la carpeta del proyecto
    for sub in ["salidas", "figuras", "mapas", "informes"]:
        for f in (carpeta / sub).glob("*") if (carpeta / sub).exists() else []:
            if f.is_file():
                (RAIZ / sub).mkdir(exist_ok=True)
                shutil.copy(f, RAIZ / sub / f.name)
                print(f"  {sub}/{f.name}")

    usadas = []
    for linea in proc.stdout.splitlines():
        try:
            e = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "assistant":
            for b in e["message"].get("content", []):
                if b.get("type") == "tool_use":
                    n = b["name"]
                    if n == "Skill":
                        n += ":" + str(b.get("input", {}).get("skill"))
                    usadas.append(n)
    print("\nHerramientas en orden:\n  " + "\n  ".join(usadas))
    shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == "__main__":
    main()

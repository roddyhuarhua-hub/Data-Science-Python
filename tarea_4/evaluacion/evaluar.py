"""Evalúa el agente: las mismas 10 preguntas sin y con MCP/Skills, con `claude -p`, y las califica.

Uso (desde la carpeta tarea_4/, con datos/ completo y preguntas.csv con sus verdades ya fijadas):
    uv run evaluacion/evaluar.py                       # los dos modos, con Sonnet
    uv run evaluacion/evaluar.py --modos con --solo q05 q09
    uv run evaluacion/evaluar.py --modelo haiku

Modos (mismo modelo, misma instrucción, una sesión nueva e independiente por pregunta):
  - sin: Claude en una carpeta vacía, sin herramientas (--tools ""), sin MCP (--strict-mcp-config) y sin skills.
         No ve el proyecto, así que no puede leer respuestas ya calculadas.
  - con: Claude en una copia limpia del proyecto (.claude/skills, mcp/, .mcp.json, datos/), con el MCP bcrp,
         las tres skills y Bash/Read para correrlas. La copia NO lleva salidas/, figuras/, mapas/, referencias/,
         informes/ ni evaluacion/: cada respuesta se calcula desde los microdatos y la API.

Escribe:
  evaluacion/resultados.csv                          una fila por pregunta y modo
  evaluacion/resumen_modos.csv                       aciertos, errores, sin respuesta y tiempo por modo
  evidencias_ia/evaluacion/<id>_<modo>.jsonl         la transcripción completa de cada corrida
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
EVIDENCIAS = RAIZ / "evidencias_ia" / "evaluacion"

ESQUEMA = {"type": "object", "required": ["valor", "fuente"],
           "properties": {"valor": {"type": ["number", "null"]}, "valor2": {"type": ["number", "null"]},
                          "unidad": {"type": "string"}, "fuente": {"type": "string"}}}
INSTRUCCION = ("Responde la pregunta. Pon el número principal en «valor», en la unidad que pide la pregunta; si la "
               "pregunta pide un segundo número, ponlo en «valor2». Si no puedes saberlo con certeza, pon null: no "
               "estimes. En «fuente» di de dónde sale cada cifra (serie, base de datos o cálculo).\n\n")

# Lo que se copia al modo «con»: solo lo necesario para calcular, nada de resultados.
COPIAR = [".claude/skills", "mcp/server.py", ".mcp.json", "pyproject.toml", "uv.lock", "datos"]
MODOS = {
    "sin": ["--tools", "", "--strict-mcp-config"],
    "con": ["--strict-mcp-config", "--mcp-config", ".mcp.json",
            "--tools", "Bash,Read,Glob,Grep,Skill",
            "--allowedTools", "mcp__bcrp,Skill,Bash,Read,Glob,Grep"],
}


def ruta_claude() -> str:
    """En Windows, npm instala claude.cmd, que subprocess no ejecuta sin shell: busca el claude.exe real."""
    ruta = shutil.which("claude")
    if ruta and ruta.lower().endswith(".cmd"):
        exe = Path(ruta).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return ruta or "claude"


def preparar(modo: str) -> Path:
    carpeta = Path(tempfile.mkdtemp(prefix=f"t4_eval_{modo}_"))
    if modo == "con":
        for rel in COPIAR:
            origen = RAIZ / rel
            destino = carpeta / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            if origen.is_dir():
                shutil.copytree(origen, destino, ignore=shutil.ignore_patterns("__pycache__"))
            elif origen.exists():
                shutil.copy(origen, destino)
        # .mcp.json solo con el servidor bcrp: fetch no hace falta y tarda en arrancar
        (carpeta / ".mcp.json").write_text(json.dumps({"mcpServers": {"bcrp": {
            "type": "stdio", "command": "uv", "args": ["run", "mcp/server.py"]}}}, indent=2), encoding="utf-8")
    return carpeta


def preguntar(q, modo: str, modelo: str) -> dict:
    carpeta = preparar(modo)
    cmd = [ruta_claude(), "-p", INSTRUCCION + q.pregunta, "--output-format", "stream-json", "--verbose",
           "--json-schema", json.dumps(ESQUEMA), "--no-session-persistence", "--model", modelo, *MODOS[modo]]
    entorno = dict(os.environ)
    entorno["UV_PROJECT_ENVIRONMENT"] = str(RAIZ / ".venv")      # reutiliza el entorno: no reinstala en cada copia
    t0 = time.time()
    error = ""
    try:
        proc = subprocess.run(cmd, cwd=carpeta, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900, env=entorno)
        salida = proc.stdout
        if proc.returncode != 0:
            error = f"código {proc.returncode}: {proc.stderr[-300:]}"
    except subprocess.TimeoutExpired as e:
        salida, error = (e.stdout or "") if isinstance(e.stdout, str) else "", "tiempo agotado (900 s)"
    segundos = round(time.time() - t0, 1)

    herramientas, final = [], {}
    for linea in salida.splitlines():
        try:
            ev = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for b in ev.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    nombre = b.get("name", "")
                    if nombre == "Skill":
                        nombre = "Skill:" + str(b.get("input", {}).get("skill") or b.get("input", {}).get("command"))
                    elif nombre == "Bash":
                        nombre = "Bash"
                    herramientas.append(nombre.replace("mcp__bcrp__", "bcrp:"))
        if ev.get("type") == "result":
            final = ev
    r = final.get("structured_output") or {}
    if not r and final.get("result"):
        try:
            r = json.loads(final["result"])
        except (json.JSONDecodeError, TypeError):
            r = {}
    if final.get("is_error"):
        error = error or str(final.get("result", ""))[:300]

    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    (EVIDENCIAS / f"{q.id}_{modo}.jsonl").write_text(salida, encoding="utf-8")
    shutil.rmtree(carpeta, ignore_errors=True)
    # orden de aparición, sin repetir
    vistas = list(dict.fromkeys(herramientas))
    return {"valor": r.get("valor"), "valor2": r.get("valor2"), "unidad": r.get("unidad", ""),
            "fuente": str(r.get("fuente", ""))[:400], "herramientas": " > ".join(vistas) or "ninguna",
            "llamadas": len(herramientas), "segundos": segundos, "turnos": final.get("num_turns"),
            "costo_usd": final.get("total_cost_usd"), "texto": str(final.get("result", ""))[:500], "error": error}


def calificar(q, r) -> str:
    def ok(valor, verdad, tol):
        return valor is not None and abs(float(valor) - float(verdad)) <= float(tol)
    if r["valor"] is None:
        return "sin respuesta"
    bien = ok(r["valor"], q.verdad, q.tolerancia)
    if pd.notna(q.verdad2):
        bien = bien and ok(r["valor2"], q.verdad2, q.tolerancia2)
    return "correcta" if bien else "incorrecta"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--modos", nargs="+", default=["sin", "con"], choices=list(MODOS))
    p.add_argument("--modelo", default="sonnet")
    p.add_argument("--solo", nargs="*", help="ids de preguntas, por ejemplo q01 q05")
    a = p.parse_args()

    preguntas = pd.read_csv(RAIZ / "evaluacion" / "preguntas.csv", dtype={"id": str})
    if preguntas.verdad.isna().any():
        raise SystemExit("Hay preguntas sin verdad en preguntas.csv: fíjenlas ANTES de evaluar.")
    if a.solo:
        preguntas = preguntas[preguntas.id.isin(a.solo)]
    for falta in ["datos/966-Modulo34.zip", "datos/966-Modulo02.zip"]:
        if "con" in a.modos and not (RAIZ / falta).exists():
            raise SystemExit(f"Falta {falta}: el modo «con» necesita los microdatos (ver README).")

    filas = []
    for q in preguntas.itertuples():
        for modo in a.modos:
            print(f"-> {q.id} · {modo}", flush=True)
            r = preguntar(q, modo, a.modelo)
            res = calificar(q, r)
            print(f"   {res}: valor={r['valor']} valor2={r['valor2']} · {r['segundos']} s · {r['herramientas']}",
                  flush=True)
            esperada = f"{q.verdad:g}" + (f" y {q.verdad2:g}" if pd.notna(q.verdad2) else "")
            generada = "" if r["valor"] is None else f"{r['valor']:g}" + (
                f" y {r['valor2']:g}" if pd.notna(q.verdad2) and r["valor2"] is not None else "")
            filas.append({"id": q.id, "tipo": q.tipo, "modo": modo, "modelo": a.modelo, "pregunta": q.pregunta,
                          "respuesta_esperada": esperada, "tolerancia": q.tolerancia, "unidad": q.unidad,
                          "respuesta_generada": generada, "resultado": res,
                          "correcta": res == "correcta", **r})

    nuevo = pd.DataFrame(filas)
    archivo = RAIZ / "evaluacion" / "resultados.csv"
    if a.solo and archivo.exists():      # actualizar solo las filas que se volvieron a correr
        viejo = pd.read_csv(archivo, dtype={"id": str})
        viejo = viejo[~(viejo.id.isin(nuevo.id) & viejo.modo.isin(nuevo.modo))]
        nuevo = pd.concat([viejo, nuevo]).sort_values(["id", "modo"])
    nuevo.to_csv(archivo, index=False)

    resumen = nuevo.groupby("modo").agg(
        correctas=("resultado", lambda s: (s == "correcta").sum()),
        incorrectas=("resultado", lambda s: (s == "incorrecta").sum()),
        sin_respuesta=("resultado", lambda s: (s == "sin respuesta").sum()),
        segundos_promedio=("segundos", "mean"), costo_usd=("costo_usd", "sum")).round(2)
    resumen.to_csv(RAIZ / "evaluacion" / "resumen_modos.csv")
    print("\n" + resumen.to_string())
    print("\n" + nuevo.pivot(index="id", columns="modo", values="resultado").to_string())


if __name__ == "__main__":
    main()

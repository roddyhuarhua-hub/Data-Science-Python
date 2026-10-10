"""Eje 1 del análisis del discurso: designaciones y calificativos en las fuentes primarias.

Solo usa páginas con rol == "fuente_primaria" y su texto_fuente (sin notas del editor).

Funciones
- cargar()                 corpus de fuentes primarias, con texto limpio y número de volumen
- kwic(df, patron)         concordancias (contexto izquierdo / término / contexto derecho)
- colocaciones(df, patron) palabras que acompañan a un término, con log-likelihood
- rotulos_actor(df)        qué términos del léxico aparecen junto al nombre de Túpac Amaru, por volumen

Ejecutado como script escribe los CSV de data/discurso/.
"""
import re
from collections import Counter
from math import log
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
SALIDA = BASE / "data" / "discurso"

# Mismo largo que el original, para que los índices de la versión sin tildes sirvan en el texto mostrado.
_SIN_TILDE = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU")

# Léxico de designaciones. Cada patrón se aplica sobre texto en minúsculas y sin tildes.
LEXICO = {
    "rebeldía": {
        "rebelde": r"rebelde[s]?",
        "rebelión": r"rebeli[oó]n(?:es)?",
        "sublevado/sublevación": r"subleva(?:do|dos|cion|ciones)",
        "insurgente": r"insurgente[s]?",
        "alboroto/tumulto": r"(?:alboroto|alborotado|tumulto)[s]?",
        "sedición/conmoción": r"(?:sedici(?:on|ones|oso|osos)|conmocion(?:es)?)",
        "levantamiento": r"levantamiento[s]?",
        "revolución": r"revoluci[oó]n(?:es)?",
    },
    "criminalización": {
        "traidor": r"traidor(?:es)?",
        "tirano": r"tirano[s]?",
        "infame": r"infame[s]?",
        "malvado/facineroso": r"(?:malvado|malvados|facineroso|facinerosos|bandido|bandidos)",
        "insolente": r"insolente[s]?",
        "reo": r"reo[s]?",
    },
    "autoridad y linaje": {
        "inca": r"(?:inca|inga|ynga|yncas|ingas)",
        "cacique": r"cacique[s]?",
        "caudillo": r"caudillo[s]?",
        "gobernador": r"gobernador(?:es)?",
        "don": r"\bdon\b",
    },
    "adscripción étnica": {
        "indio": r"indio[s]?",
        "natural": r"naturales",
        "mestizo": r"mestizo[s]?",
        "español": r"espa[nñ]ole?s?",
    },
}

# Nombres con que se refiere a Túpac Amaru en el corpus (grafías antiguas incluidas).
ACTOR = r"(?:tupac|tupa|tupamaro|tupamaros|condorcanqui|jose gabriel)(?:\s+amaru)?"

STOP = set(
    """a al algo ante aquel aquella aquellos asi aun aunque bien cada como con contra cual cuales cuando de del desde donde
    dos e el ella ellos en entre era eran es esa esas ese eso esos esta estaba estan estas este esto estos fue fueron ha
    haber han hasta hay la las le les lo los mas me mi mismo muy ni no nos nuestro o otra otras otro otros para pero por
    porque que quien quienes se sea segun ser si sido sin sobre su sus tal tambien tan tanto te tiene todo todos tu un una
    uno unos va ya y yo""".split()
)


# Encabezados corridos que el OCR repite en cada página y que inflarían los conteos
# (p. ej. "Causas criminales ... contra los rebeldes" en los vols. 6 y 7).
_ENCABEZADOS = re.compile(
    r"nueva colecci.n documental de la independencia del per. la rebeli.n de t.pac amaru ii"
    r"|volumen \d+ (?:causas criminales (?:seguidas )?contra los rebeldes"
    r"|la defensa del obispo moscoso: cargo \d+.?)"
    r"|volumen \d+\b",
    re.IGNORECASE,
)


def limpiar(texto: str) -> str:
    """Une palabras cortadas por guion de fin de línea ("rei- no" -> "reino"), quita encabezados corridos
    y compacta espacios."""
    texto = re.sub(r"(\w)-\s+(\w)", r"\1\2", texto)
    texto = _ENCABEZADOS.sub(" ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def cargar() -> pd.DataFrame:
    df = pd.read_csv(BASE / "data" / "tupac_amaru_corpus.csv")
    df = df[df["rol"] == "fuente_primaria"].copy()
    df["volumen"] = df["documento"].str.extract(r"vol\.\s*(\d+)").astype(int)
    df["limpio"] = df["texto_fuente"].fillna("").map(limpiar).str.lower()
    df["match"] = df["limpio"].str.translate(_SIN_TILDE)
    return df.reset_index(drop=True)


def _regex(patron: str) -> re.Pattern:
    return re.compile(rf"\b{patron}\b")


def kwic(df: pd.DataFrame, patron: str, ancho: int = 70, volumen: int | None = None) -> pd.DataFrame:
    """Concordancias de `patron` (regex sobre texto sin tildes)."""
    rx = _regex(patron)
    sub = df if volumen is None else df[df["volumen"] == volumen]
    filas = []
    for r in sub.itertuples():
        for m in rx.finditer(r.match):
            a, b = m.span()
            filas.append(
                {
                    "volumen": r.volumen,
                    "pagina": r.pagina,
                    "izquierda": r.limpio[max(0, a - ancho) : a],
                    "termino": r.limpio[a:b],
                    "derecha": r.limpio[b : b + ancho],
                    "url": r.url,
                }
            )
    return pd.DataFrame(filas)


def _tokens(texto: str) -> list[str]:
    return re.findall(r"[a-zñ]+", texto)


def colocaciones(df: pd.DataFrame, patron: str, ventana: int = 5, min_n: int = 5, top: int = 40) -> pd.DataFrame:
    """Palabras a ±`ventana` del término, ordenadas por log-likelihood (Dunning) frente al corpus."""
    rx = _regex(patron)
    total, vecinas, n_objetivo = Counter(), Counter(), 0
    for texto in df["match"]:
        toks = _tokens(texto)
        total.update(toks)
        for i, t in enumerate(toks):
            if rx.fullmatch(t):
                n_objetivo += 1
                ctx = toks[max(0, i - ventana) : i] + toks[i + 1 : i + 1 + ventana]
                vecinas.update(w for w in ctx if w not in STOP and len(w) > 2)
    N = sum(total.values())
    n_ventana = n_objetivo * 2 * ventana
    filas = []
    for w, o11 in vecinas.items():
        if o11 < min_n:
            continue
        o12, o21 = n_ventana - o11, total[w] - o11
        o22 = N - n_ventana - o21
        if min(o12, o21, o22) <= 0:
            continue
        e11 = n_ventana * total[w] / N
        if o11 <= e11:  # solo atracciones, no repulsiones
            continue
        e12, e21, e22 = n_ventana * (N - total[w]) / N, (N - n_ventana) * total[w] / N, (N - n_ventana) * (N - total[w]) / N
        ll = 2 * sum(o * log(o / e) for o, e in ((o11, e11), (o12, e12), (o21, e21), (o22, e22)) if o > 0)
        filas.append({"palabra": w, "con_termino": o11, "en_corpus": total[w], "log_likelihood": round(ll, 1)})
    out = pd.DataFrame(filas)
    if out.empty:
        return out
    return out.sort_values("log_likelihood", ascending=False).head(top).reset_index(drop=True)


def frecuencia_por_volumen(df: pd.DataFrame) -> pd.DataFrame:
    """Frecuencia por 10 000 palabras de cada término del léxico, por volumen."""
    palabras = df.assign(n=df["match"].str.split().str.len()).groupby("volumen")["n"].sum()
    filas = []
    for cat, terminos in LEXICO.items():
        for nombre, pat in terminos.items():
            rx = _regex(pat)
            cuenta = df.groupby("volumen")["match"].apply(lambda s: sum(len(rx.findall(t)) for t in s))
            for vol, n in cuenta.items():
                filas.append(
                    {"categoria": cat, "termino": nombre, "volumen": vol, "n": int(n),
                     "por_10k": round(n / palabras[vol] * 1e4, 2)}
                )
    return pd.DataFrame(filas)


def rotulos_actor(df: pd.DataFrame, ventana: int = 8) -> pd.DataFrame:
    """Términos del léxico que aparecen a ±`ventana` palabras del nombre de Túpac Amaru."""
    nombre = re.compile(rf"\b{ACTOR}\b")
    lex = [(cat, n, _regex(p)) for cat, ts in LEXICO.items() for n, p in ts.items() if n != "don"]
    cuenta, menciones = Counter(), Counter()
    for r in df.itertuples():
        for m in nombre.finditer(r.match):
            menciones[r.volumen] += 1
            ctx = r.match[max(0, m.start() - ventana * 9) : m.end() + ventana * 9]
            for cat, n, rx in lex:
                if rx.search(ctx):
                    cuenta[(cat, n, r.volumen)] += 1
    filas = [
        {"categoria": c, "termino": n, "volumen": v, "n": k, "menciones_actor": menciones[v],
         "por_100_menciones": round(k / menciones[v] * 100, 1)}
        for (c, n, v), k in cuenta.items()
    ]
    return pd.DataFrame(filas).sort_values(["categoria", "termino", "volumen"]).reset_index(drop=True)


if __name__ == "__main__":
    SALIDA.mkdir(parents=True, exist_ok=True)
    corpus = cargar()
    print(f"{len(corpus):,} páginas de fuente primaria")
    frecuencia_por_volumen(corpus).to_csv(SALIDA / "frecuencia_por_volumen.csv", index=False)
    rotulos_actor(corpus).to_csv(SALIDA / "rotulos_actor.csv", index=False)
    for nombre, pat in {"rebelde": r"rebelde[s]?", "traidor": r"traidor(?:es)?", "inca": r"(?:inca|inga|ynga)",
                        "cacique": r"cacique[s]?", "tirano": r"tirano[s]?"}.items():
        colocaciones(corpus, pat).to_csv(SALIDA / f"colocaciones_{nombre}.csv", index=False)
    print("CSV escritos en", SALIDA)

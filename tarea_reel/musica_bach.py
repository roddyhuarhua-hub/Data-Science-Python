"""Música de fondo sin problemas de derechos: el Preludio en Do mayor de Bach (BWV 846, 1722),
interpretado nota por nota con un piano sintético hecho con numpy.

La obra es de dominio público y esta grabación la generamos nosotros, así que se puede publicar.

    python musica_bach.py            # guarda musica/bach_preludio_do.wav
"""
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
NEGRA = 0.85                     # segundos por tiempo (unos 70 por minuto, tranquilo)
SEMI = NEGRA / 4                 # cada compás tiene 16 semicorcheas

# Cada compás: cinco notas que se arpegian 1-2-3-4-5-3-4-5, dos veces.
COMPASES = """C4 E4 G4 C5 E5 | C4 D4 A4 D5 F5 | B3 D4 G4 D5 F5 | C4 E4 G4 C5 E5 |
C4 E4 A4 E5 A5 | C4 D4 F#4 A4 D5 | B3 D4 G4 D5 G5 | B3 C4 E4 G4 C5 |
A3 C4 E4 G4 C5 | D3 A3 D4 F#4 C5 | G3 B3 D4 G4 B4 | G3 Bb3 E4 G4 C#5 |
F3 A3 D4 A4 D5 | F3 Ab3 D4 F4 B4 | E3 G3 C4 G4 C5 | E3 F3 A3 C4 F4 |
D3 F3 A3 C4 F4 | G2 D3 G3 B3 F4 | C3 E3 G3 C4 E4"""

NOTAS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def frecuencia(nota):
    base, octava = nota[:-1], int(nota[-1])
    semitono = NOTAS[base[0]] + base[1:].count("#") - base[1:].count("b")
    midi = 12 * (octava + 1) + semitono
    return 440.0 * 2 ** ((midi - 69) / 12)


def piano(f, dur):
    """Un tono de piano sencillo: armónicos que se apagan, ataque corto y caída exponencial."""
    t = np.arange(int(dur * SR)) / SR
    tono = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (1.2 + 0.9 * k))
               for k, a in enumerate([1.0, 0.45, 0.22, 0.12, 0.06], start=1))
    ataque = np.minimum(1, t / 0.006)
    return (tono * ataque).astype(np.float32)


def preludio(repeticiones=1):
    compases = [c.split() for c in COMPASES.replace("\n", " ").split("|")] * repeticiones
    total = len(compases) * 16 * SEMI + 4
    pista = np.zeros(int(total * SR), dtype=np.float32)
    patron = [0, 1, 2, 3, 4, 2, 3, 4] * 2
    for c, notas in enumerate(compases):
        for s, i in enumerate(patron):
            ini = (c * 16 + s) * SEMI
            # la nota dura hasta el final del compás (como con pedal); la del bajo, más fuerte
            dur = (16 - s) * SEMI + 1.5
            vol = 0.5 if i == 0 else 0.32
            onda = piano(frecuencia(notas[i]), dur) * vol
            a = int(ini * SR)
            pista[a:a + len(onda)] += onda[:len(pista) - a]
    return pista / np.abs(pista).max() * 0.8


if __name__ == "__main__":
    salida = Path(__file__).parent / "musica" / "bach_preludio_do.wav"
    salida.parent.mkdir(exist_ok=True)
    sf.write(salida, preludio(), SR)
    print(f"Guardé {salida} ({sf.info(str(salida)).duration:.0f} s)")

"""Respaldo de datos crudos en datos/raw/.

Guarda, sin tocar, lo que devuelve cada fuente:
  datos/raw/AAAA-MM-DD/rss_<medio>_<feed>.xml   la respuesta RSS tal cual llegó
  datos/raw/AAAA-MM-DD/manifiesto.csv           url, fecha y hora, código HTTP, bytes y huella sha256

Mismas reglas del notebook 01: robots.txt, User-Agent con contacto, pausa de 1.5 s
y un solo reintento. NO modifica datos/noticias.csv (la Parte 1 queda igual).

Correr desde la carpeta tarea_1:   python scripts/respaldar_raw.py
"""
import hashlib
import time
from datetime import datetime
from pathlib import Path
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests

CABECERAS = {"User-Agent": "TareaDiplomadoPUCP/1.0 (uso academico; contacto: huarhuarojas@gmail.com)"}
PAUSA = 1.5

PLANTILLA_EC = "https://elcomercio.pe/arc/outboundfeeds/google-news-feed/category/{}/?outputType=xml"
FUENTES = {
    ("larepublica", "https://larepublica.pe"): {
        "home": "https://larepublica.pe/rss/home.xml",
        "politica": "https://larepublica.pe/rss/politica.xml",
        "economia": "https://larepublica.pe/rss/economia.xml",
        "deportes": "https://larepublica.pe/rss/deportes.xml",
        "ciencia": "https://larepublica.pe/rss/ciencia.xml",
    },
    ("elcomercio", "https://elcomercio.pe"): {
        "politica": PLANTILLA_EC.format("politica"),
        "economia": PLANTILLA_EC.format("economia"),
        "deporte-total": PLANTILLA_EC.format("deporte-total"),
        "tecnologia": PLANTILLA_EC.format("tecnologia"),
    },
}


def descargar(url):
    for intento in range(2):
        try:
            respuesta = requests.get(url, headers=CABECERAS, timeout=30)
            if respuesta.status_code == 200:
                return respuesta
        except requests.RequestException:
            pass
        time.sleep(PAUSA)
    return None


def main():
    carpeta = Path("datos/raw") / datetime.now().strftime("%Y-%m-%d")
    carpeta.mkdir(parents=True, exist_ok=True)
    manifiesto = []

    for (medio, sitio), feeds in FUENTES.items():
        robots = RobotFileParser()
        robots.set_url(sitio + "/robots.txt")
        robots.read()
        for nombre, url in feeds.items():
            fila = {"archivo": "", "medio": medio, "feed": nombre, "url": url,
                    "descargado": datetime.now().isoformat(timespec="seconds"),
                    "http": None, "bytes": 0, "sha256": ""}
            if not robots.can_fetch(CABECERAS["User-Agent"], url):
                fila["http"] = "bloqueado_por_robots"
            else:
                respuesta = descargar(url)
                if respuesta is not None:
                    archivo = carpeta / f"rss_{medio}_{nombre}.xml"
                    archivo.write_bytes(respuesta.content)      # bytes tal cual, sin limpiar
                    fila.update(archivo=archivo.name, http=respuesta.status_code,
                                bytes=len(respuesta.content),
                                sha256=hashlib.sha256(respuesta.content).hexdigest())
                else:
                    fila["http"] = "error"
            manifiesto.append(fila)
            print(medio, nombre, fila["http"], fila["bytes"])
            time.sleep(PAUSA)

    pd.DataFrame(manifiesto).to_csv(carpeta / "manifiesto.csv", index=False, encoding="utf-8")
    print("Respaldo guardado en", carpeta)


if __name__ == "__main__":
    main()

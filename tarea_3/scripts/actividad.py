"""Clasifica la actividad de un caso socioambiental leyendo la descripción
que escribe la Defensoría. Es una clasificación por palabras clave: el orden
de las reglas importa (la primera que coincide gana)."""
import re
import unicodedata


def sin_tildes(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


# (actividad, patrón). Los patrones se buscan sobre el texto en minúsculas y sin tildes.
REGLAS = [
    ("Hidrocarburos", r"hidrocarbur|petrole|petroperu|oleoducto|gasoducto|\blote\s*\d|\blotes\b|"
                      r"pluspetrol|camisea|gas natural|perupetro|crudo|refineria|frontera energy|"
                      r"\bcnpc\b|savia|olympic|repsol|\bgnv\b|\bglp\b|\btgp\b|transportadora de gas|\bgas\b|"
                      r"saramurillo|estacion 1|puinahua|curaray|chambira|urituyacu|cuenca del (rio )?(corrientes|pastaza|tigre|maranon)"),
    ("Minería", r"miner|\bmina\b|\bminas\b|relave|metalurg|fundicion|\bsouthern\b|antamina|las bambas|"
                r"\bmmg\b|yanacocha|barrick|buenaventura|glencore|hudbay|volcan|minsur|chinalco|"
                r"cerro verde|shougang|tia maria|conga|quellaveco|anglo american|toquepala|cuajone|"
                r"antapaccay|constancia|marcobre|nexa|milpo|chancadora|socavon|extraccion de oro|"
                r"majaz|rio blanco|doe run|first quantum|\bares\b|suyamarca|canariaco|canaris|bear creek|"
                r"hochschild|ananea|la rinconada|poderosa|coimolache|lagunas norte|cobriza|tintaya|ciemsa|"
                r"\bspcc\b|antapite|colpayoc|el algarrobo|metales pesados|"
                r"material de acarreo|cantera|aurifer|concesion(es)? de beneficio|pasivos ambientales"),
    ("Energía", r"hidroelectric|central electrica|central termica|termoelectric|linea(s)? de transmision|"
                r"subestacion|eolic|fotovoltai|parque solar|energia electrica|electrific|electro\w+ s\.?a|"
                r"torres de alta tension|\bkv\b|represa|generacion electrica|\benergy\b|\benel\b|engie|kallpa|"
                r"statkraft|celepsa|electroperu"),
    ("Residuos y saneamiento", r"residuos solidos|botadero|relleno sanitario|basura|aguas residuales|"
                               r"desague|alcantarillado|planta de tratamiento|saneamiento|lagunas de oxidacion|\bptar\b|"
                               r"monorelleno|celdas transitorias"),
    ("Agroindustria y forestal", r"agroindustr|palma aceitera|tala|forestal|madera|deforest|"
                                 r"agricola|langostin|pesquer|harina de pescado|avicola|granja|porcin|camal"),
]
OTROS = "Otros"


def clasificar(caso):
    t = sin_tildes(caso)
    for actividad, patron in REGLAS:
        if re.search(patron, t):
            return actividad
    return OTROS

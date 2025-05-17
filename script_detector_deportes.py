import requests
import re
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
import time
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
import os
import sys
from openmoji_logos import OPENMOJI_LOGOS

# ------------- CONFIGURACIÓN -------------
URLS_EVENTOS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]
URL_PALABRAS_CLAVE = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/LISTA%20DE%20PALABRAS%20CLAVE.txt"

# GUARDA SIEMPRE EN LA RAÍZ DEL REPO (donde está este script)
SALIDA_XML = os.path.abspath(os.path.join(os.path.dirname(__file__), "deportes_detectados.xml"))
DELAY_BETWEEN_REQUESTS = 1
MAX_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[logging.StreamHandler()]
)

def normalizar_texto(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = re.sub(r'[^\w\s]', '', texto)
    return texto

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def robust_get(url, retries=MAX_RETRIES, delay=DELAY_BETWEEN_REQUESTS):
    for intento in range(retries):
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            logging.error(f"Error descargando {url}: {e} (intento {intento+1}/{retries})")
            if intento < retries - 1:
                time.sleep(delay)
    logging.error(f"No se pudo descargar {url} tras {retries} intentos.")
    return None

def extraer_diccionario_deportes(url_txt):
    logging.info("Descargando lista de palabras clave de deportes...")
    r = robust_get(url_txt)
    if not r:
        logging.error("No se pudo descargar el archivo de palabras clave.")
        return {}
    lines = r.text.splitlines()
    deportes = {}
    deporte_actual = None
    for line in lines:
        deporte_match = re.match(r'^([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ \-/&()]+)\s*$', line.strip())
        if deporte_match and not line.strip().startswith("Palabras clave"):
            deporte_actual = deporte_match.group(1).strip()
            continue
        if line.lower().startswith("palabras clave:"):
            palabras_str = line.split(":", 1)[1]
            palabras = [p.strip().lower() for p in re.split(r',|\(|\)|/|;', palabras_str) if p.strip()]
            if deporte_actual:
                if deporte_actual not in deportes:
                    deportes[deporte_actual] = set()
                deportes[deporte_actual].update([normalizar_texto(p) for p in palabras])
    deportes = {dep: set([normalizar_texto(p) for p in palabras if len(p) > 2]) for dep, palabras in deportes.items() if dep}
    # Palabras clave extra manuales y multilingües
    deportes.setdefault("Ciclismo", set()).update([
        "giro de italia", "giro", "tour de francia", "tour", "vuelta a espana", "etapa", "ciclismo", "uci world tour",
        "cycling", "bicycle", "bicicleta"
    ])
    deportes.setdefault("Fútbol", set()).update([
        "laliga", "la liga", "champions", "uefa", "premier league", "bundesliga", "serie a", "ligue 1",
        "mls", "liga mx", "superliga", "fa cup", "copa del rey", "libertadores", "sudamericana", "concacaf",
        "gold cup", "mundial", "world cup", "eurocopa", "fifa", "ucl", "epl",
        "futbol", "fútbol", "soccer", "football", "fußball", "calcio", "foot", "futebol"
    ])
    deportes.setdefault("Baloncesto", set()).update([
        "nba", "acb", "liga endesa", "euroleague", "baloncesto", "basket", "basketball", "bàsquet", "basquete"
    ])
    deportes.setdefault("Motociclismo", set()).update([
        "motogp", "superbike", "motocross", "enduro", "trial", "moto", "gran premio", "motorcycle"
    ])
    deportes.setdefault("Automovilismo", set()).update([
        "f1", "formula 1", "rally", "nascar", "indycar", "karting", "gt", "dakar", "automovilismo", "racing", "car"
    ])
    logging.info(f"Diccionario de deportes generado con {len(deportes)} deportes.")
    return deportes

def parse_m3u(url):
    eventos = []
    logging.info(f"Descargando y procesando archivo M3U: {url}")
    r = robust_get(url)
    if not r:
        return eventos
    for line in r.text.splitlines():
        if line.startswith("#EXTINF"):
            match = re.search(r',(.+)$', line)
            if match:
                nombre_evento = match.group(1).strip()
                eventos.append(nombre_evento)
    logging.info(f"{len(eventos)} eventos extraídos de {url}")
    return eventos

def parse_xml(url):
    eventos = []
    logging.info(f"Descargando y procesando archivo XML: {url}")
    r = robust_get(url)
    if not r:
        return eventos
    try:
        root = ET.fromstring(r.content)
        for elem in root.iter():
            if elem.text and elem.text.strip() and len(elem.text.strip()) > 4:
                eventos.append(elem.text.strip())
        logging.info(f"{len(eventos)} eventos extraídos de {url}")
    except Exception as e:
        logging.error(f"Error parseando {url}: {e}")
    return eventos

def detectar_deporte(nombre_evento, deportes_dict, umbral=0.80):
    texto = normalizar_texto(nombre_evento)
    for deporte, palabras in deportes_dict.items():
        for palabra in palabras:
            palabra = palabra.strip()
            if not palabra:
                continue
            if palabra in texto:
                return deporte
            tokens_evento = texto.split()
            tokens_palabra = palabra.split()
            for i in range(len(tokens_evento) - len(tokens_palabra) + 1):
                fragmento = ' '.join(tokens_evento[i:i+len(tokens_palabra)])
                if similar(fragmento, palabra) >= umbral:
                    return deporte
    return "desconocido"

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent(e, level + 1)
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def guardar_xml(eventos, archivo=SALIDA_XML):
    try:
        root = ET.Element("eventos")
        for evento, deporte, fuente in eventos:
            nodo_evento = ET.SubElement(root, "evento")
            ET.SubElement(nodo_evento, "nombre").text = evento
            ET.SubElement(nodo_evento, "deporte").text = deporte
            ET.SubElement(nodo_evento, "fuente").text = fuente
            logo_url = OPENMOJI_LOGOS.get(deporte, "")
            if not logo_url:
                logo_url = OPENMOJI_LOGOS.get(deporte.capitalize(), "")
            if not logo_url:
                logo_url = OPENMOJI_LOGOS.get(deporte.lower(), "")
            ET.SubElement(nodo_evento, "logo").text = logo_url
        indent(root)
        tree = ET.ElementTree(root)
        tree.write(archivo, encoding="utf-8", xml_declaration=True)
        logging.info(f"Archivo XML guardado con {len(eventos)} eventos: {archivo}")
        print(f"\nArchivo XML actualizado: {archivo}\n")
    except Exception as exc:
        print(f"ERROR al guardar XML: {exc}")
        logging.error("EXCEPCIÓN al guardar XML", exc_info=True)
        sys.exit(1)

def sugerir_palabras_clave(no_detectados, topn=15):
    palabras = []
    frases = []
    for evento in no_detectados:
        evento_norm = normalizar_texto(evento)
        palabras += [w for w in evento_norm.split() if len(w) >= 4]
        tokens = evento_norm.split()
        for i in range(len(tokens)-1):
            frases.append(' '.join(tokens[i:i+2]))
        for i in range(len(tokens)-2):
            frases.append(' '.join(tokens[i:i+3]))
    counter_palabras = Counter(palabras)
    counter_frases = Counter(frases)
    print("\n=== SUGERENCIAS DE PALABRAS CLAVE (palabras sueltas) ===")
    for palabra, freq in counter_palabras.most_common(topn):
        print(f"- '{palabra}' aparece en {freq} eventos no detectados")
    print("\n=== SUGERENCIAS DE PALABRAS CLAVE (frases de 2-3 palabras) ===")
    for frase, freq in counter_frases.most_common(topn):
        print(f"- '{frase}' aparece en {freq} eventos no detectados")
    print("Revisa estos términos y considera añadirlos a los deportes correspondientes en el diccionario manualmente.\n")

if __name__ == "__main__":
    try:
        inicio = datetime.now()
        print(f"Guardará el XML en: {SALIDA_XML}")
        logging.info("Inicio de ejecución de script_detector_deportes.py")
        deportes_dict = extraer_diccionario_deportes(URL_PALABRAS_CLAVE)
        if not deportes_dict:
            logging.error("No se pudo construir el diccionario de deportes. Fin del script.")
            sys.exit(1)
        resultados = []
        no_detectados = []
        total_eventos = 0

        for url in URLS_EVENTOS:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            if url.endswith(".m3u"):
                eventos = parse_m3u(url)
            elif url.endswith(".xml"):
                eventos = parse_xml(url)
            else:
                logging.warning(f"Extensión no reconocida: {url}")
                continue
            for evento in eventos:
                total_eventos += 1
                deporte = detectar_deporte(evento, deportes_dict)
                if not deporte or deporte == "desconocido":
                    no_detectados.append(evento)
                    logging.debug(f"No detectado: {evento}")
                else:
                    logging.debug(f"Detectado: '{evento}' => {deporte}")
                resultados.append((evento, deporte if deporte else "desconocido", url))

        print("Eventos a guardar:", len(resultados))
        print("Ruta de guardado:", SALIDA_XML)
        guardar_xml(resultados, archivo=SALIDA_XML)
        fin = datetime.now()
        logging.info(f"Procesados {total_eventos} eventos en total.")
        logging.info(f"Deportes no detectados: {len(no_detectados)}")
        if no_detectados:
            logging.info("Ejemplos de eventos NO detectados:")
            for e in no_detectados[:10]:
                logging.info(f"  - {e}")
            sugerir_palabras_clave(no_detectados, topn=15)
            logging.info("Considera ampliar el diccionario de palabras clave si algunos deportes conocidos no se detectan.")
        logging.info(f"Duración total: {fin-inicio}")
        print(f"FIN. XML generado en: {SALIDA_XML}\n")
    except Exception as e:
        print(f"\nERROR FATAL: {e}\n")
        logging.error("EXCEPCIÓN NO CAPTURADA", exc_info=True)
        sys.exit(1)

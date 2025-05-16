import requests
import re
import xml.etree.ElementTree as ET
import logging
from datetime import datetime

URLS_EVENTOS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]

URL_PALABRAS_CLAVE = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/LISTA%20DE%20PALABRAS%20CLAVE.txt"
SALIDA_XML = "deportes_detectados.xml"

# Configura logs detallados
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[logging.StreamHandler()]
)

def extraer_diccionario_deportes(url_txt):
    logging.info("Descargando lista de palabras clave de deportes...")
    r = requests.get(url_txt)
    if r.status_code != 200:
        logging.error("No se pudo descargar el archivo de palabras clave")
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
                deportes[deporte_actual].update(palabras)
    deportes = {dep: set([p for p in palabras if len(p) > 2]) for dep, palabras in deportes.items() if dep}
    logging.info(f"Diccionario de deportes generado con {len(deportes)} deportes.")
    return deportes

def parse_m3u(url):
    eventos = []
    logging.info(f"Descargando y procesando archivo M3U: {url}")
    r = requests.get(url)
    if r.status_code != 200:
        logging.error(f"No se pudo descargar {url}")
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
    try:
        r = requests.get(url)
        if r.status_code != 200:
            logging.error(f"No se pudo descargar {url}")
            return eventos
        root = ET.fromstring(r.content)
        for elem in root.iter():
            if elem.text and elem.text.strip() and len(elem.text.strip()) > 4:
                eventos.append(elem.text.strip())
        logging.info(f"{len(eventos)} eventos extraídos de {url}")
    except Exception as e:
        logging.error(f"Error parseando {url}: {e}")
    return eventos

def detectar_deporte(nombre_evento, deportes_dict):
    nombre = nombre_evento.lower()
    for deporte, palabras in deportes_dict.items():
        for palabra in palabras:
            if palabra and palabra in nombre:
                return deporte
    return "desconocido"

def guardar_xml(eventos, archivo=SALIDA_XML):
    root = ET.Element("eventos")
    for evento, deporte, fuente in eventos:
        nodo_evento = ET.SubElement(root, "evento")
        ET.SubElement(nodo_evento, "nombre").text = evento
        ET.SubElement(nodo_evento, "deporte").text = deporte
        ET.SubElement(nodo_evento, "fuente").text = fuente
    tree = ET.ElementTree(root)
    tree.write(archivo, encoding="utf-8", xml_declaration=True)
    logging.info(f"Archivo XML guardado con {len(eventos)} eventos: {archivo}")

if __name__ == "__main__":
    inicio = datetime.now()
    logging.info("Inicio de ejecución de script_detector_deportes.py")
    deportes_dict = extraer_diccionario_deportes(URL_PALABRAS_CLAVE)
    resultados = []
    no_detectados = []
    total_eventos = 0

    for url in URLS_EVENTOS:
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

    guardar_xml(resultados, archivo=SALIDA_XML)
    fin = datetime.now()
    logging.info(f"Procesados {total_eventos} eventos en total.")
    logging.info(f"Deportes no detectados: {len(no_detectados)}")
    if no_detectados:
        logging.info("Ejemplos de eventos NO detectados:")
        for e in no_detectados[:5]:
            logging.info(f"  - {e}")
    logging.info(f"Duración total: {fin-inicio}")

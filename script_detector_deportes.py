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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[logging.StreamHandler()]
)

OPENMOJI_LOGOS = {
    "Fútbol": "https://openmoji.org/data/color/svg/26BD.svg",
    # ... agrega los demás deportes y logos aquí ...
    "Skibobbing": "",
}

def extraer_diccionario_deportes(url_txt):
    deportes_dict = {}
    try:
        response = requests.get(url_txt)
        response.raise_for_status()
        for line in response.text.splitlines():
            if line.strip():
                partes = line.split(":")
                if len(partes) == 2:
                    clave, valor = partes
                    deportes_dict[clave.strip().lower()] = valor.strip()
    except Exception as e:
        logging.error(f"Error al extraer el diccionario de deportes: {e}")
    return deportes_dict

def parse_m3u(url):
    eventos = []
    try:
        response = requests.get(url)
        response.raise_for_status()
        for line in response.text.splitlines():
            if line.startswith("#EXTINF"):
                # Extrae el nombre del evento después de la coma
                partes = line.split(",", 1)
                if len(partes) == 2:
                    eventos.append(partes[1].strip())
    except Exception as e:
        logging.error(f"Error al analizar el archivo M3U {url}: {e}")
    return eventos

def parse_xml(url):
    eventos = []
    try:
        response = requests.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        for elem in root.iter():
            if elem.tag.lower() in ["event", "evento", "title", "nombre"]:
                if elem.text and elem.text.strip():
                    eventos.append(elem.text.strip())
    except Exception as e:
        logging.error(f"Error al analizar el archivo XML {url}: {e}")
    return eventos

def detectar_deporte(nombre_evento, deportes_dict):
    nombre_evento_lower = nombre_evento.lower()
    for palabra_clave, deporte in deportes_dict.items():
        if palabra_clave in nombre_evento_lower:
            return deporte
    return "desconocido"

# --- NUEVA FUNCIÓN PARA INDENTAR EL XML ---
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
# --- FIN NUEVA FUNCIÓN ---

def guardar_xml(eventos, archivo=SALIDA_XML):
    root = ET.Element("eventos")
    for evento, deporte, fuente in eventos:
        nodo_evento = ET.SubElement(root, "evento")
        ET.SubElement(nodo_evento, "nombre").text = evento
        ET.SubElement(nodo_evento, "deporte").text = deporte
        ET.SubElement(nodo_evento, "fuente").text = fuente
        logo_url = OPENMOJI_LOGOS.get(deporte, "")
        ET.SubElement(nodo_evento, "logo").text = logo_url

    indent(root)  # <--- INDENTA EL XML ANTES DE GUARDAR
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
        if eventos is None:  # Protección extra, aunque las funciones ya devuelven lista
            eventos = []
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

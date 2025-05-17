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
    # ... (se mantiene igual, omito aquí por espacio, pero en tu script va completo)
    "Fútbol": "https://openmoji.org/data/color/svg/26BD.svg",
    # ...
    "Skibobbing": "",
}

def extraer_diccionario_deportes(url_txt):
    # ... (igual que en tu script)
    # (código omitido aquí por brevedad)
    pass  # Aquí va la función completa como ya la tienes

def parse_m3u(url):
    # ... (igual que en tu script)
    pass

def parse_xml(url):
    # ... (igual que en tu script)
    pass

def detectar_deporte(nombre_evento, deportes_dict):
    # ... (igual que en tu script)
    pass

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

import requests
from bs4 import BeautifulSoup
import re
from xml.dom.minidom import Document
import os
import logging
from typing import Set, List

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URLs base para scrapear
BASE_URLS_TO_SCRAPE = [
    f"https://livetv.sx/es/allupcomingsports/{i}/" for i in range(1, 201)
]

# Archivo XML de salida
OUTPUT_XML_FILE = "eventos_livetv_sx.xml"

# Patrón de regex para encontrar los enlaces de eventos
# /es/eventinfo/DIGITOS__/  O  /es/eventinfo/DIGITOS_TEXTO_ADICIONAL/
EVENT_PATH_REGEX = r"^/es/eventinfo/(\d+(__)?([a-zA-Z0-9_-]+)?)/?$"

# User-Agent para simular un navegador
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_html(url: str) -> str | None:
    """Obtiene el contenido HTML de una URL."""
    try:
        # === CAMBIO CLAVE AQUÍ: verify=False ===
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        response.raise_for_status()  # Lanza una excepción para códigos de error HTTP
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener la URL {url}: {e}")
        return None

def parse_event_urls(html_content: str) -> Set[str]:
    """Analiza el contenido HTML y extrae las URLs de eventos."""
    found_urls = set()
    if not html_content:
        return found_urls

    soup = BeautifulSoup(html_content, 'html.parser')
    links = soup.find_all('a', href=True)

    for link in links:
        href = link['href']
        # Usamos re.match para asegurar que el patrón coincide desde el inicio del string href
        if re.match(EVENT_PATH_REGEX, href):
            full_url = f"https://livetv.sx{href}"
            # Asegurarse de que la URL termine con una barra si no la tiene
            if not full_url.endswith('/'):
                full_url += '/'
            found_urls.add(full_url)
            logging.debug(f"Encontrada URL de evento coincidente: {full_url}")

    return found_urls

def create_or_update_xml(event_urls: List[str], xml_filepath: str):
    """Crea o actualiza el archivo XML con las URLs de eventos."""
    doc = Document()
    root_element = doc.createElement('events')
    doc.appendChild(root_element)

    sorted_urls = sorted(list(event_urls)) # Ordenar para consistencia

    for url_str in sorted_urls:
        item_element = doc.createElement('event')
        root_element.appendChild(item_element)

        url_node = doc.createElement('url')
        url_node.appendChild(doc.createTextNode(url_str))
        item_element.appendChild(url_node)

    try:
        with open(xml_filepath, 'w', encoding='utf-8') as f:
            # Usar toprettyxml para una salida indentada (vertical)
            # Eliminar líneas vacías extra que toprettyxml puede generar
            xml_content = doc.toprettyxml(indent="  ")
            clean_xml_content = "\n".join([line for line in xml_content.splitlines() if line.strip()])
            f.write(clean_xml_content)
        logging.info(f"Archivo XML '{xml_filepath}' actualizado con {len(sorted_urls)} eventos.")
    except IOError as e:
        logging.error(f"Error al escribir el archivo XML '{xml_filepath}': {e}")

def main():
    """Función principal del script."""
    logging.info("Iniciando el proceso de scraping de eventos...")
    all_event_urls: Set[str] = set()

    for page_url in BASE_URLS_TO_SCRAPE:
        logging.info(f"Scrapeando página: {page_url}")
        html = fetch_html(page_url)
        if html:
            urls_from_page = parse_event_urls(html)
            if urls_from_page:
                all_event_urls.update(urls_from_page)
            logging.info(f"Encontrados {len(urls_from_page)} eventos en {page_url}. Total únicos hasta ahora: {len(all_event_urls)}")

    if not all_event_urls:
        logging.warning("No se encontraron URLs de eventos. El archivo XML no se modificará si ya existe y está vacío, o se creará vacío.")

    create_or_update_xml(list(all_event_urls), OUTPUT_XML_FILE)
    logging.info("Proceso de scraping finalizado.")

if __name__ == "__main__":
    # Opcional: Para evitar advertencias de SSL en el log si verify=False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()

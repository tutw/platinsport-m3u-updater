import requests
from bs4 import BeautifulSoup
import re
from xml.dom.minidom import Document
import os
import logging
from typing import Set, List, Dict, TypedDict, Any
from datetime import datetime

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
# Aseguramos que capture el ID y el posible nombre en la URL
EVENT_PATH_REGEX = r"^/es/eventinfo/(\d+(_+)?([a-zA-Z0-9_-]+)?)/?$"

# User-Agent para simular un navegador
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Definimos un tipo para la estructura de un evento
class Event(TypedDict):
    url: str
    name: str
    date: str # Formato YYYY-MM-DD
    time: str # Formato HH:MM

def fetch_html(url: str) -> str | None:
    """Obtiene el contenido HTML de una URL."""
    try:
        # Desactivamos la verificación SSL debido a posibles errores
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        response.raise_for_status()  # Lanza una excepción para códigos de error HTTP
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener la URL {url}: {e}")
        return None

def parse_event_urls_and_details(html_content: str) -> List[Event]:
    """
    Analiza el contenido HTML y extrae las URLs, nombres, fechas y horas de los eventos.
    Basado en la estructura HTML proporcionada.
    """
    found_events: List[Event] = []
    if not html_content:
        return found_events

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Cada evento relevante está dentro de una <td> que contiene una tabla interna.
    # Estas <td> tienen un atributo OnMouseOver que contiene el ID del evento.
    # Buscamos estas <td> que contienen los enlaces de los eventos.
    event_tds = soup.find_all('td', attrs={'onmouseover': re.compile(r'\$\(\'#cv\d+\'\)\.show\(\);')})

    current_date_str = "" # Para almacenar la fecha que precede a los eventos si no está en evdesc
    
    for td in event_tds:
        # Los eventos están en una tabla interna dentro de este <td>
        inner_table = td.find('table', cellpadding='1', cellspacing='2', width='100%')
        
        if inner_table:
            # El enlace del evento es el primer <a> con class="live" o "bottomgray"
            link = inner_table.find('a', class_=['live', 'bottomgray'])
            
            if link and 'href' in link.attrs:
                href = link['href']
                match = re.match(EVENT_PATH_REGEX, href)
                
                if match:
                    full_url = f"https://livetv.sx{href}"
                    if not full_url.endswith('/'):
                        full_url += '/'

                    # El nombre del evento es el texto directamente dentro del enlace
                    event_name = link.get_text(strip=True).replace('&ndash;', '–').strip()
                    
                    # La fecha y la hora están en el <span> con clase 'evdesc'
                    evdesc_span = inner_table.find('span', class_='evdesc')
                    
                    event_time = "N/A"
                    event_date = "N/A" # Default a N/A, será la fecha actual si no se encuentra o 'Hoy'
                    
                    if evdesc_span:
                        desc_text = evdesc_span.get_text(strip=True)
                        # Ejemplo: "11:00 (ATP. Roland Garros)"
                        # El primer grupo captura la hora, el segundo la categoría/deporte
                        time_category_match = re.match(r'(\d{1,2}:\d{2})\s*\((.+)\)', desc_text)
                        
                        if time_category_match:
                            event_time = time_category_match.group(1) # Ej: "11:00"
                            # La categoría es time_category_match.group(2), no la guardamos directamente en name/date/time
                            
                            # La fecha se obtiene del encabezado previo 'Hoy' o '26 de mayo, lunes'
                            # Sin embargo, el HTML no tiene la fecha del día/mes/año en cada evento.
                            # Para obtener la fecha real, tendríamos que buscar el span.date de "Hoy" o "26 de mayo, lunes"
                            # que se encuentra en un <tr> diferente.

                            # Estrategia para la fecha:
                            # 1. Buscar el <tr> padre del td. Si está debajo de un <tr> con class="date", usarlo.
                            # 2. Si no, asumir la fecha actual (del día en que se ejecuta el script).

                            # En tu HTML de ejemplo, la fecha "Hoy (26 de mayo, lunes)" está en:
                            # <tr bgcolor="#f0f0f0">...<td><span class="date">Hoy (26 de mayo, lunes)</span></td></tr>
                            # Y los eventos vienen después de este <tr>.

                            # Buscamos el <tr> padre de la <td> actual
                            # parent_tr_of_event_td = td.find_parent('tr') # Esto es incorrecto, el TD es el padre más directo
                            
                            # Para encontrar la fecha, vamos a buscar el <tr> con la clase 'date' que
                            # precede a la tabla del evento.
                            # Esto es un poco más complejo porque BeautifulSoup no tiene un "previous_sibling_until".
                            # Vamos a buscar todos los spans con clase 'date' y ver cuál es el más reciente.
                            
                            # Recorre los siblings de 'td' hacia atrás para encontrar el tr con la fecha
                            current_node = td.previous_sibling
                            while current_node:
                                if hasattr(current_node, 'name') and current_node.name == 'tr':
                                    date_span = current_node.find('span', class_='date')
                                    if date_span and date_span.get_text(strip=True) not in ["Top Events LIVE", "Hoy", "Hoy ("]:
                                        date_text = date_span.get_text(strip=True)
                                        # Parsear "Hoy (26 de mayo, lunes)" o "Mañana (27 de mayo, martes)"
                                        date_match = re.search(r'\((\d{1,2}\s+de\s+\w+,\s+\w+)\)', date_text)
                                        if date_match:
                                            # Formato "26 de mayo, lunes"
                                            parsed_date_str = date_match.group(1).replace('de ', '') # "26 mayo, lunes"
                                            try:
                                                # Asumimos el año actual, ya que no se proporciona en la página.
                                                # Si el script se usa en años diferentes, esto debe ajustarse o la web debe proveer el año.
                                                current_year = datetime.now().year
                                                # Convertir nombre del mes a número
                                                month_map = {
                                                    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                                                    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                                                    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                                                }
                                                date_parts = parsed_date_str.split(' ')
                                                day = int(date_parts[0])
                                                month_name = date_parts[1].replace(',', '').strip()
                                                month = month_map.get(month_name.lower())

                                                if month:
                                                    event_date = f"{current_year}-{month:02d}-{day:02d}"
                                                    # Actualizar la fecha actual encontrada para futuros eventos en el mismo bloque
                                                    current_date_str = event_date
                                                else:
                                                    logging.warning(f"No se pudo parsear el mes de la fecha: {date_text}")
                                            except ValueError as ve:
                                                logging.warning(f"Error parseando fecha '{date_text}': {ve}")
                                        elif "Hoy (" in date_text: # Si es "Hoy (26 de mayo, lunes)"
                                            current_date_str = datetime.now().strftime("%Y-%m-%d")
                                        elif "Mañana (" in date_text: # Si es "Mañana (27 de mayo, martes)"
                                            current_date_str = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime("%Y-%m-%d")
                                        else:
                                            logging.warning(f"Formato de fecha de encabezado desconocido: {date_text}")
                                        break # Encontramos la fecha, salimos del bucle
                                current_node = current_node.previous_sibling
                            
                            # Si no encontramos una fecha específica en un encabezado, usamos la última fecha encontrada
                            # o la fecha actual del día en que se ejecuta el script.
                            if event_date == "N/A":
                                event_date = current_date_str if current_date_str else datetime.now().strftime("%Y-%m-%d")
                        else:
                            # Si no se pudo parsear el time_category_match, pero hay evdesc, puede ser solo categoría
                            # En este caso, el tiempo será N/A y el nombre del evento es el que ya tenemos.
                            pass # time and date remain N/A or from current_date_str
                    
                    event_data: Event = {
                        "url": full_url,
                        "name": event_name,
                        "date": event_date,
                        "time": event_time
                    }
                    found_events.append(event_data)
                    logging.debug(f"Encontrado evento: {event_data}")

    return found_events

def create_or_update_xml(events: List[Event], xml_filepath: str):
    """Crea o actualiza el archivo XML con los detalles de los eventos."""
    doc = Document()
    root_element = doc.createElement('events')
    doc.appendChild(root_element)

    # Ordenar los eventos para una salida consistente (ej. por URL o nombre)
    sorted_events = sorted(events, key=lambda x: x['url'])

    for event_data in sorted_events:
        item_element = doc.createElement('event')
        root_element.appendChild(item_element)

        # URL
        url_node = doc.createElement('url')
        url_node.appendChild(doc.createTextNode(event_data['url']))
        item_element.appendChild(url_node)

        # Nombre
        name_node = doc.createElement('name')
        name_node.appendChild(doc.createTextNode(event_data['name']))
        item_element.appendChild(name_node)

        # Fecha
        date_node = doc.createElement('date')
        date_node.appendChild(doc.createTextNode(event_data['date']))
        item_element.appendChild(date_node)

        # Hora
        time_node = doc.createElement('time')
        time_node.appendChild(doc.createTextNode(event_data['time']))
        item_element.appendChild(time_node)

    try:
        with open(xml_filepath, 'w', encoding='utf-8') as f:
            xml_content = doc.toprettyxml(indent="  ")
            # Eliminar líneas en blanco que toprettymxl añade
            clean_xml_content = "\n".join([line for line in xml_content.splitlines() if line.strip()])
            f.write(clean_xml_content)
        logging.info(f"Archivo XML '{xml_filepath}' actualizado con {len(sorted_events)} eventos.")
    except IOError as e:
        logging.error(f"Error al escribir el archivo XML '{xml_filepath}': {e}")

def main():
    """Función principal del script."""
    logging.info("Iniciando el proceso de scraping de eventos...")
    all_unique_events: Dict[str, Event] = {} # Usamos un diccionario para deduplicar por URL

    from datetime import timedelta # Importar aquí para uso local si solo se usa en main o parse_event_urls_and_details
    global current_date_str # Necesitamos que current_date_str sea global para que parse_event_urls_and_details pueda usarlo o pasarlo como parámetro

    for page_url in BASE_URLS_TO_SCRAPE:
        logging.info(f"Scrapeando página: {page_url}")
        html = fetch_html(page_url)
        if html:
            events_from_page = parse_event_urls_and_details(html)
            for event in events_from_page:
                # Deduplicación: La URL es la clave única
                if event['url'] not in all_unique_events:
                    all_unique_events[event['url']] = event
            logging.info(f"Encontrados {len(events_from_page)} eventos en {page_url}. Total únicos hasta ahora: {len(all_unique_events)}")

    if not all_unique_events:
        logging.warning("No se encontraron URLs de eventos. El archivo XML no se modificará si ya existe y está vacío, o se creará vacío.")

    create_or_update_xml(list(all_unique_events.values()), OUTPUT_XML_FILE)
    logging.info("Proceso de scraping finalizado.")

if __name__ == "__main__":
    # Opcional: Para evitar advertencias de SSL en el log si verify=False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()

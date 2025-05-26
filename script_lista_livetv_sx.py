import requests
from bs4 import BeautifulSoup
import re
from xml.dom.minidom import Document
import os
import logging
from typing import List, Dict, TypedDict
from datetime import datetime, timedelta

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URLs base para scrapear
# Mantendremos el rango alto, asumiendo que eventualmente las páginas sí tendrán contenido distinto
BASE_URLS_TO_SCRAPE = [
    f"https://livetv.sx/es/allupcomingsports/{i}/" for i in range(1, 201)
]

# Archivo XML de salida
OUTPUT_XML_FILE = "eventos_livetv_sx.xml"

# Patrón de regex para encontrar los enlaces de eventos
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
    sport: str

def fetch_html(url: str) -> str | None:
    """Obtiene el contenido HTML de una URL."""
    try:
        # Desactivamos la verificación SSL debido a posibles errores con algunos servidores.
        # En un entorno de producción, es preferible verificar certificados SSL.
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        response.raise_for_status()  # Lanza una excepción para códigos de error HTTP (4xx o 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener la URL {url}: {e}")
        return None

def parse_event_urls_and_details(html_content: str) -> List[Event]:
    """
    Analiza el contenido HTML y extrae las URLs, nombres, fechas, horas y deportes de los eventos.
    Utiliza un selector CSS muy específico para encontrar la tabla de eventos correcta.
    """
    found_events: List[Event] = []
    if not html_content:
        return found_events

    soup = BeautifulSoup(html_content, 'html.parser')
    
    current_date_str = datetime.now().strftime("%Y-%m-%d") # Fecha por defecto
    parsing_events_after_date = False # Flag para saber si estamos en una sección de eventos procesables

    # === NUEVO ENFOQUE: Usar el selector CSS completo para encontrar la tabla de eventos ===
    # Este selector apunta directamente a la tabla que contiene los eventos listados por fecha.
    main_table_selector = "body > table > tbody > tr > td:nth-child(2) > table > tbody > tr:nth-child(4) > td > table > tbody > tr > td:nth-child(2) > table > tbody > tr > td > table > tbody > tr:nth-child(2) > td > table > tbody > tr > td > table > tbody > tr > td > table:nth-child(5) > tbody > tr > td:nth-child(2) > table:nth-child(4)"
    
    main_table = soup.select_one(main_table_selector)

    if not main_table:
        logging.warning(f"No se encontró la tabla principal de eventos con el selector CSS: {main_table_selector}")
        logging.warning("Esto podría significar que la estructura HTML ha cambiado o que la tabla no está presente en esta página.")
        return found_events

    # Iterar sobre las filas (<tr>) de la tabla principal
    # Usamos .children para asegurarnos de obtener solo los hijos directos del tbody,
    # que deberían ser los tr's de los eventos y las fechas.
    for tr in main_table.find_all('tr', recursive=False):
        # === Detección de encabezados de fecha ===
        date_span = tr.find('span', class_='date')
        if date_span:
            date_text = date_span.get_text(strip=True)
            
            # Si encontramos "Top Events LIVE", desactivamos el flag.
            # Asumimos que esta sección es la primera en aparecer en la tabla si existe.
            if "Top Events LIVE" in date_text:
                parsing_events_after_date = False
                logging.debug(f"Ignorando sección: {date_text}")
                continue # Saltamos al siguiente tr para evitar procesar los Top Events LIVE

            # Si es un encabezado de fecha real, activamos el flag y actualizamos la fecha
            if "Hoy (" in date_text or "Mañana (" in date_text or re.search(r'\d{1,2}\s+de\s+\w+,\s+\w+', date_text):
                parsing_events_after_date = True
                if "Hoy (" in date_text:
                    current_date_str = datetime.now().strftime("%Y-%m-%d")
                elif "Mañana (" in date_text:
                    current_date_str = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime("%Y-%m-%d")
                else: # Parsear fechas futuras como "26 de mayo, lunes"
                    date_match = re.search(r'\((\d{1,2}\s+de\s+\w+,\s+\w+)\)', date_text)
                    if date_match:
                        parsed_date_str = date_match.group(1).replace('de ', '') # "26 mayo, lunes"
                        try:
                            current_year = datetime.now().year
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
                                event_candidate_date = datetime(current_year, month, day)
                                if event_candidate_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                                    calculated_year = current_year + 1
                                else:
                                    calculated_year = current_year
                                
                                event_date_obj = datetime(calculated_year, month, day)
                                current_date_str = event_date_obj.strftime("%Y-%m-%d")
                            else:
                                logging.warning(f"No se pudo parsear el mes de la fecha de encabezado: {date_text}")
                        except (ValueError, IndexError) as ve:
                            logging.warning(f"Error parseando fecha de encabezado '{date_text}': {ve}")
                    else:
                        logging.warning(f"Formato de fecha de encabezado desconocido: {date_text}")
                continue # Saltamos al siguiente tr porque este ya fue un encabezado de fecha

        # === Detección de eventos individuales ===
        # Solo procesamos eventos si el flag 'parsing_events_after_date' está activado
        if parsing_events_after_date:
            # Buscar el <td> contenedor del evento dentro de la fila actual (tr)
            event_td_container = tr.find('td', attrs={'onmouseover': re.compile(r'\$\(\'#cv\d+\'\)\.show\(\);')})
            
            if event_td_container:
                # La tabla interna con los detalles del evento
                inner_table = event_td_container.find('table', cellpadding='1', cellspacing='2', width='100%')
                
                if inner_table:
                    link = inner_table.find('a', class_=['live', 'bottomgray'])
                    
                    if link and 'href' in link.attrs:
                        href = link['href']
                        match = re.match(EVENT_PATH_REGEX, href)
                        
                        if match:
                            full_url = f"https://livetv.sx{href}"
                            if not full_url.endswith('/'):
                                full_url += '/'

                            event_name = link.get_text(strip=True).replace('&ndash;', '–').strip()
                            
                            event_time = "N/A"
                            event_sport = "N/A"

                            # Extraer hora y deporte de evdesc_span
                            evdesc_span = inner_table.find('span', class_='evdesc')
                            if evdesc_span:
                                desc_text = evdesc_span.get_text(strip=True)
                                time_category_match = re.match(r'(\d{1,2}:\d{2})\s*\((.+)\)', desc_text)
                                if time_category_match:
                                    event_time = time_category_match.group(1)
                                    event_sport = time_category_match.group(2).strip()
                                elif desc_text and ':' not in desc_text and '(' not in desc_text:
                                    event_sport = desc_text.strip()
                            
                            # Fallback: Siempre intentar obtener deporte de la imagen alt para robustez
                            img_tag = inner_table.find('td', width='34').find('img', alt=True)
                            if img_tag and img_tag['alt']:
                                sport_from_img = img_tag['alt'].strip()
                                # Limpiar el nombre del deporte de la imagen
                                sport_from_img = re.sub(r'^(Tenis|Fútbol|Críquet|Automovilismo|Baloncesto|Hockey|Voleibol|Rugby|Béisbol|Boxeo|MMMA)\.\s*', '', sport_from_img, flags=re.IGNORECASE).strip()
                                sport_from_img = re.sub(r'^(ATP|WTA|NHL|NBA|Liga MX|Ligue 1|Premier League|Serie A|Bundesliga|LaLiga)\.\s*', '', sport_from_img, flags=re.IGNORECASE).strip()
                                
                                # Si evdesc_span no dio un deporte o era menos específico, usar el de la imagen
                                if event_sport == "N/A" or not event_sport or \
                                   (sport_from_img and sport_from_img != event_sport and len(sport_from_img) > len(event_sport) and sport_from_img not in event_sport):
                                    event_sport = sport_from_img
                                # Si la imagen es más específica y evdesc es genérico
                                elif sport_from_img and len(sport_from_img) > len(event_sport) and event_sport in sport_from_img:
                                    event_sport = sport_from_img
                                
                                # Si el deporte aún es muy genérico (ej. solo "Tenis") y la imagen da más, usar imagen
                                if event_sport == "N/A" and sport_from_img:
                                    event_sport = sport_from_img


                            event_data: Event = {
                                "url": full_url,
                                "name": event_name,
                                "date": current_date_str,
                                "time": event_time,
                                "sport": event_sport if event_sport else "N/A" # Asegurar que no sea None o vacio
                            }
                            found_events.append(event_data)
                            logging.debug(f"Encontrado evento: {event_data}")
        # else:
        #     logging.debug("Saltando TR, no es un evento o no estamos en una sección post-fecha activa.")


    return found_events

def create_or_update_xml(events: List[Event], xml_filepath: str):
    """Crea o actualiza el archivo XML con los detalles de los eventos."""
    doc = Document()
    root_element = doc.createElement('events')
    doc.appendChild(root_element)

    # Ordenar los eventos para una salida consistente (ej. por URL o nombre)
    sorted_events = sorted(events, key=lambda x: (x['date'], x['time'], x['name']))

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

        # Deporte (nuevo)
        sport_node = doc.createElement('sport')
        sport_node.appendChild(doc.createTextNode(event_data['sport']))
        item_element.appendChild(sport_node)

    try:
        with open(xml_filepath, 'w', encoding='utf-8') as f:
            xml_content = doc.toprettyxml(indent="  ")
            # Eliminar líneas en blanco añadidas por toprettymxl
            clean_xml_content = "\n".join([line for line in xml_content.splitlines() if line.strip()])
            f.write(clean_xml_content)
        logging.info(f"Archivo XML '{xml_filepath}' actualizado con {len(sorted_events)} eventos.")
    except IOError as e:
        logging.error(f"Error al escribir el archivo XML '{xml_filepath}': {e}")

def main():
    """Función principal del script."""
    logging.info("Iniciando el proceso de scraping de eventos...")
    all_unique_events: Dict[str, Event] = {} # Usamos un diccionario para deduplicar por URL

    for page_url in BASE_URLS_TO_SCRAPE:
        logging.info(f"Scrapeando página: {page_url}")
        html = fetch_html(page_url)
        if html:
            events_from_page = parse_event_urls_and_details(html)
            logging.info(f"Eventos encontrados en {page_url}: {len(events_from_page)}")
            for event in events_from_page:
                # Deduplicación: La URL es la clave única
                if event['url'] not in all_unique_events:
                    all_unique_events[event['url']] = event
            logging.info(f"Total únicos hasta ahora: {len(all_unique_events)}")

    if not all_unique_events:
        logging.warning("No se encontraron URLs de eventos. El archivo XML no se modificará si ya existe y está vacío, o se creará vacío.")

    create_or_update_xml(list(all_unique_events.values()), OUTPUT_XML_FILE)
    logging.info("Proceso de scraping finalizado.")

if __name__ == "__main__":
    # Opcional: Para evitar advertencias de SSL en el log si verify=False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()

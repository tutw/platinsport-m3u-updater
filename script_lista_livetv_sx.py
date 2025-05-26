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
BASE_URLS_TO_SCRAPE = [
    f"https://livetv.sx/es/allupcomingsports/{i}/" for i in range(1, 201)
]

# Archivo XML de salida
OUTPUT_XML_FILE = "eventos_livetv_sx.xml"

# Patrón de regex para encontrar los enlaces de eventos
# /es/eventinfo/DIGITOS__/  O  /es/eventinfo/DIGITOS_TEXTO_ADICIONAL/
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
    sport: str # Nuevo campo para el deporte

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
    Analiza el contenido HTML y extrae las URLs, nombres, fechas, horas y deportes de los eventos.
    Basado en la estructura HTML proporcionada.
    """
    found_events: List[Event] = []
    if not html_content:
        return found_events

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # La tabla principal que contiene todos los eventos
    main_table = soup.find('table', width=230, cellspacing=0)

    if not main_table:
        logging.warning("No se encontró la tabla principal de eventos (width=230).")
        return found_events

    current_date_str = datetime.now().strftime("%Y-%m-%d") # Fecha por defecto, asumimos hoy

    # Iterar sobre las filas (<tr>) de la tabla principal
    for tr in main_table.find_all('tr'):
        # === Detección de encabezados de fecha ===
        date_span = tr.find('span', class_='date')
        if date_span:
            date_text = date_span.get_text(strip=True)
            if "Hoy (" in date_text:
                current_date_str = datetime.now().strftime("%Y-%m-%d")
            elif "Mañana (" in date_text:
                current_date_str = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime("%Y-%m-%d")
            elif date_text not in ["Top Events LIVE", "Hoy"]: # Evitar encabezados no relacionados con fecha
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
                            # Comprobación de año para fechas futuras (ej. un evento en diciembre que se scrapea en enero)
                            # Si el mes es anterior al actual, y el día es anterior, asumimos que es el próximo año.
                            if month < datetime.now().month:
                                calculated_year = current_year + 1
                            elif month == datetime.now().month and day < datetime.now().day:
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
        # Un evento se encuentra dentro de un <td> con OnMouseOver, que a su vez contiene una <table> interna.
        event_td = tr.find('td', attrs={'onmouseover': re.compile(r'\$\(\'#cv\d+\'\)\.show\(\);')})
        
        if event_td:
            inner_table = event_td.find('table', cellpadding='1', cellspacing='2', width='100%')
            
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
                        event_sport = "N/A" # Inicializar deporte

                        # Extraer hora y deporte de evdesc_span
                        evdesc_span = inner_table.find('span', class_='evdesc')
                        if evdesc_span:
                            desc_text = evdesc_span.get_text(strip=True)
                            time_category_match = re.match(r'(\d{1,2}:\d{2})\s*\((.+)\)', desc_text)
                            if time_category_match:
                                event_time = time_category_match.group(1)
                                event_sport = time_category_match.group(2).strip() # Extrae el deporte/categoría
                            elif desc_text and ':' not in desc_text and '(' not in desc_text: # Si solo es categoría sin hora (ej: "Clasificatoria")
                                event_sport = desc_text.strip()
                            else: # Intentar extraer el deporte de la imagen, si evdesc_span falla o es incompleto
                                img_tag = inner_table.find('img', alt=True)
                                if img_tag and img_tag['alt']:
                                    event_sport = img_tag['alt'].strip()
                                    # Limpiar si contiene "Tenis." o "Fútbol."
                                    if event_sport.lower().startswith("tenis."):
                                        event_sport = event_sport[len("Tenis."):].strip()
                                    elif event_sport.lower().startswith("fútbol."):
                                        event_sport = event_sport[len("Fútbol."):].strip()
                                    # Opcional: Eliminar "ATP.", "WTA." si no queremos el circuito en el deporte
                                    event_sport = re.sub(r'^(ATP|WTA)\.\s*', '', event_sport, flags=re.IGNORECASE).strip()

                        # Si el deporte sigue siendo N/A, intentarlo de la imagen alt (más fiable a veces)
                        if event_sport == "N/A":
                            img_tag = inner_table.find('img', alt=True)
                            if img_tag and img_tag['alt']:
                                event_sport = img_tag['alt'].strip()
                                # Limpiar si contiene "Tenis." o "Fútbol."
                                if event_sport.lower().startswith("tenis."):
                                    event_sport = event_sport[len("Tenis."):].strip()
                                elif event_sport.lower().startswith("fútbol."):
                                    event_sport = event_sport[len("Fútbol."):].strip()
                                # Opcional: Eliminar "ATP.", "WTA." si no queremos el circuito en el deporte
                                event_sport = re.sub(r'^(ATP|WTA)\.\s*', '', event_sport, flags=re.IGNORECASE).strip()


                        event_data: Event = {
                            "url": full_url,
                            "name": event_name,
                            "date": current_date_str, # Usamos la última fecha de encabezado encontrada
                            "time": event_time,
                            "sport": event_sport
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

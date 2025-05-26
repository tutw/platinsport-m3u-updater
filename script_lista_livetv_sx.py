import asyncio
import requests # Se mantiene solo si hubiera alguna otra necesidad, pero no para el scraping principal
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from xml.dom.minidom import Document
import os
import logging
from typing import List, Dict, TypedDict
from datetime import datetime, timedelta

# Configuración del logging
# Configuración del logging para que DEBUG también se muestre si lo necesitas para depuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Para ver los logs de DEBUG, cambia la línea de arriba a:
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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
# (Playwright maneja su propio User-Agent por defecto, pero se mantiene aquí para claridad
# o si en el futuro se usara requests para algo más)
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

# --- FUNCIÓN PARA OBTENER HTML CON PLAYWRIGHT ---
async def fetch_html_with_playwright(url: str) -> str | None:
    """
    Obtiene el contenido HTML de una URL utilizando Playwright para ejecutar JavaScript.
    """
    async with async_playwright() as p:
        # Se puede cambiar p.chromium, p.firefox, o p.webkit
        # headless=True: el navegador no se abre visualmente (recomendado para scraping)
        # headless=False: el navegador se abre visualmente (útil para depuración)
        browser = await p.chromium.launch(headless=True) 
        page = await browser.new_page()
        try:
            logging.info(f"Navegando a {url} con Playwright...")
            # wait_until='networkidle' espera a que no haya actividad de red durante 500ms
            # Esto ayuda a asegurar que el JavaScript haya cargado el contenido.
            await page.goto(url, wait_until='networkidle', timeout=60000) # 60 segundos de timeout
            
            # --- Opcional: Esperar a que la tabla específica esté visible ---
            # Si `wait_until='networkidle'` no es suficiente, se puede esperar a un selector.
            # await page.wait_for_selector('table#allmatches', timeout=15000) # Espera 15 segundos a que el elemento aparezca

            html_content = await page.content()

            # --- Opcional para depuración: Guardar el HTML renderizado ---
            # Descomenta las siguientes líneas si necesitas ver el HTML que Playwright está obteniendo
            # para verificar que 'id="allmatches"' está presente.
            # filename = f"debug_playwright_html_{url.replace('https://', '').replace('/', '_').replace('.', '_')}.html"
            # with open(filename, 'w', encoding='utf-8') as f:
            #     f.write(html_content)
            # logging.info(f"HTML renderizado para {url} guardado en {filename}")
            
            return html_content
        except Exception as e:
            logging.error(f"Error con Playwright al obtener {url}: {e}")
            return None
        finally:
            await browser.close()

# --- FUNCION PARA PARSEAR EL HTML CON BEAUTIFULSOUP ---
def parse_event_urls_and_details(html_content: str) -> List[Event]:
    """
    Analiza el contenido HTML y extrae las URLs, nombres, fechas, horas y deportes de los eventos.
    Se enfoca en la tabla con id='allmatches' y procesa los eventos después de los encabezados de fecha.
    """
    found_events: List[Event] = []
    if not html_content:
        return found_events

    soup = BeautifulSoup(html_content, 'html.parser')
    
    current_date_str = datetime.now().strftime("%Y-%m-%d") # Fecha por defecto
    parsing_events_after_date = False # Flag para saber si estamos en una sección de eventos procesables

    # === ENFOQUE FINAL: Encontrar la tabla por su ID 'allmatches' ===
    # Esta es la parte crucial que ahora debería funcionar porque Playwright renderiza el JS.
    main_table = soup.find('table', id='allmatches')

    if not main_table:
        logging.warning("No se encontró la tabla principal de eventos con id='allmatches'.")
        # logging.debug(f"HTML para depuración (primeros 500 chars): {html_content[:500]}") # Útil para depurar si falla
        return found_events

    # Iterar sobre las filas (<tr>) dentro de la tabla principal
    # find_all('tr') sin recursive=False busca todos los tr dentro de la tabla, anidados o no.
    for tr in main_table.find_all('tr'): 
        # === Detección de encabezados de fecha ===
        date_span = tr.find('span', class_='date')
        if date_span:
            date_text = date_span.get_text(strip=True)
            
            # Si encontramos "Top Events LIVE", desactivamos el flag para ignorar esa sección.
            if "Top Events LIVE" in date_text:
                parsing_events_after_date = False 
                logging.debug(f"Ignorando sección 'Top Events LIVE'.")
                continue 

            # Si es un encabezado de fecha real, activamos el flag y actualizamos la fecha
            # Usamos un regex más específico para evitar "Hoy" sin paréntesis si no es un encabezado de fecha.
            if re.search(r'\((\d{1,2}\s+de\s+\w+,\s+\w+)\)', date_text) or \
               "Hoy (" in date_text or "Mañana (" in date_text:
                
                parsing_events_after_date = True
                if "Hoy (" in date_text:
                    current_date_str = datetime.now().strftime("%Y-%m-%d")
                elif "Mañana (" in date_text:
                    current_date_str = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime("%Y-%m-%d")
                else: # Parsear fechas futuras como "26 de mayo, lunes"
                    date_match = re.search(r'\((\d{1,2}\s+de\s+\w+,\s+\w+)\)', date_text)
                    if date_match:
                        parsed_date_str = date_match.group(1).replace('de ', '')
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
                                # Si la fecha del evento es anterior a hoy en el mismo año, asumimos el próximo año.
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
            event_td_container = tr.find('td', attrs={'onmouseover': re.compile(r'\$\(\'#cv\d+\'\)\.show\(\);')})
            
            if event_td_container:
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

                            evdesc_span = inner_table.find('span', class_='evdesc')
                            if evdesc_span:
                                desc_text = evdesc_span.get_text(strip=True)
                                time_category_match = re.match(r'(\d{1,2}:\d{2})\s*\((.+)\)', desc_text)
                                if time_category_match:
                                    event_time = time_category_match.group(1)
                                    event_sport = time_category_match.group(2).strip()
                                elif desc_text and ':' not in desc_text and '(' not in desc_text:
                                    event_sport = desc_text.strip()
                            
                            img_tag = inner_table.find('td', width='34').find('img', alt=True)
                            if img_tag and img_tag['alt']:
                                sport_from_img = img_tag['alt'].strip()
                                # Limpiar el nombre del deporte de la imagen
                                sport_from_img = re.sub(r'^(Tenis|Fútbol|Críquet|Automovilismo|Baloncesto|Hockey|Voleibol|Rugby|Béisbol|Boxeo|MMA|Formula 1)\.\s*', '', sport_from_img, flags=re.IGNORECASE).strip()
                                sport_from_img = re.sub(r'^(ATP|WTA|NHL|NBA|Liga MX|Ligue 1|Premier League|Serie A|Bundesliga|LaLiga|Champions League|Europa League|Copa Libertadores|Copa Sudamericana|NFL|MLB|UFC)\.\s*', '', sport_from_img, flags=re.IGNORECASE).strip()
                                
                                # Lógica para preferir el deporte más específico o completo
                                if event_sport == "N/A" or not event_sport:
                                    event_sport = sport_from_img
                                elif sport_from_img and sport_from_img not in event_sport:
                                    # Si la imagen tiene una versión más corta y precisa, preferirla
                                    if len(sport_from_img) < len(event_sport) and sport_from_img in event_sport:
                                        event_sport = sport_from_img
                                    # Si la imagen tiene algo completamente diferente o más detallado
                                    elif sport_from_img not in event_sport:
                                        # Aquí optamos por mantener evdesc_span si ya tiene algo decente,
                                        # a menos que img_tag sea claramente superior (ej. más descriptivo).
                                        # Para este caso, si el de la imagen es más largo, lo preferimos.
                                        if len(sport_from_img) > len(event_sport):
                                            event_sport = sport_from_img
                                
                                if event_sport == "N/A" and sport_from_img: # Último recurso si no se encontró nada
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

# --- FUNCION PARA CREAR/ACTUALIZAR EL XML ---
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
            # Eliminar líneas en blanco añadidas por toprettymxl para un XML más limpio
            clean_xml_content = "\n".join([line for line in xml_content.splitlines() if line.strip()])
            f.write(clean_xml_content)
        logging.info(f"Archivo XML '{xml_filepath}' actualizado con {len(sorted_events)} eventos.")
    except IOError as e:
        logging.error(f"Error al escribir el archivo XML '{xml_filepath}': {e}")

# --- FUNCIÓN PRINCIPAL ASÍNCRONA ---
async def main_async(): # Esta es la función principal que se ejecutará
    """Función principal del script utilizando Playwright para el scraping."""
    logging.info("Iniciando el proceso de scraping de eventos con Playwright...")
    all_unique_events: Dict[str, Event] = {} # Usamos un diccionario para deduplicar por URL

    for page_url in BASE_URLS_TO_SCRAPE:
        logging.info(f"Scrapeando página: {page_url}")
        html = await fetch_html_with_playwright(page_url) # <--- Aquí se llama a la función de Playwright
        if html:
            events_from_page = parse_event_urls_and_details(html)
            logging.info(f"Eventos encontrados en {page_url} (antes de deduplicación): {len(events_from_page)}")
            for event in events_from_page:
                # Deduplicación: La URL es la clave única
                if event['url'] not in all_unique_events:
                    all_unique_events[event['url']] = event
            logging.info(f"Total únicos hasta ahora: {len(all_unique_events)}")
        else:
            logging.warning(f"No se pudo obtener HTML para {page_url}. Saltando esta página.")

    if not all_unique_events:
        logging.warning("No se encontraron URLs de eventos. El archivo XML no se modificará si ya existe y está vacío, o se creará vacío.")

    create_or_update_xml(list(all_unique_events.values()), OUTPUT_XML_FILE)
    logging.info("Proceso de scraping finalizado.")

# --- PUNTO DE ENTRADA DEL SCRIPT ---
if __name__ == "__main__":
    # Importar urllib3 para deshabilitar advertencias SSL si se usa verify=False en requests
    # (aunque Playwright maneja las conexiones de forma diferente, es una buena práctica si requests se usara en otro lado)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Ejecuta la función principal asíncrona.
    # asyncio.run() es necesario para ejecutar funciones async/await.
    asyncio.run(main_async())

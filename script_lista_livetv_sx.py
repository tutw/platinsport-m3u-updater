#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import re
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import datetime
import time
import random
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import logging
import urllib3
import os
import sys

# Deshabilitar advertencias de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurar logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# PatrÃ³n de regex para encontrar los enlaces de eventos
EVENT_PATH_REGEX = r"^/es/eventinfo/(\d+(_+)?([a-zA-Z0-9_-]+)?)/?$"

# Headers para simular un navegador real
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
    'Referer': 'https://livetv.sx/es/',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
}

class EventScraper:
    def __init__(self, base_url="http://livetv.sx", max_pages=200, max_workers=5):
        self.base_url = base_url
        self.max_pages = max_pages
        self.max_workers = max_workers
        self.all_events = []
        self.session = requests.Session()

    def extract_events_from_page(self, page_num):
        url = f"{self.base_url}/es/allupcomingsports/{page_num}"
        logging.info(f"Procesando pÃ¡gina {page_num}: {url}")

        try:
            # Agregar delay aleatorio para evitar bloqueos
            time.sleep(random.uniform(2, 5))

            response = self.session.get(url, headers=headers, verify=False, timeout=30)
            if response.status_code != 200:
                logging.warning(f"Error {response.status_code} al acceder a la pÃ¡gina {page_num}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            events = []

            # Buscar enlaces que coincidan con el patrÃ³n de eventos
            for link in soup.find_all('a', href=True):
                href = link['href']
                if re.match(EVENT_PATH_REGEX, href):
                    try:
                        event_container = link.parent

                        # Buscar el nombre del evento
                        event_name = link.text.strip()

                        # Buscar el deporte (puede estar en un div cercano o como parte de la estructura)
                        sport_elem = event_container.find_previous('div', class_='lslc')
                        sport = sport_elem.text.strip() if sport_elem else "No especificado"

                        # Buscar fecha y hora
                        date_elem = event_container.find_next('span')
                        date_time_text = date_elem.text.strip() if date_elem else "No especificado"

                        # Dividir en fecha y hora si es posible
                        if date_time_text and date_time_text != "No especificado":
                            parts = date_time_text.split()
                            if len(parts) >= 2:
                                date = parts[0]
                                time_part = parts[1]
                            else:
                                date = date_time_text
                                time_part = "No especificado"
                        else:
                            date = "No especificado"
                            time_part = "No especificado"

                        # Construir URL completa
                        full_url = urljoin(self.base_url, href)

                        # Crear objeto de evento
                        event = {
                            "nombre": event_name,
                            "deporte": sport,
                            "fecha": date,
                            "hora": time_part,
                            "url": full_url
                        }

                        events.append(event)

                    except Exception as e:
                        logging.error(f"Error al procesar evento en pÃ¡gina {page_num}: {e}")
                        continue

            logging.info(f"ExtraÃ­dos {len(events)} eventos de la pÃ¡gina {page_num}")
            return events
        except requests.RequestException as e:
            logging.error(f"Error de conexiÃ³n en pÃ¡gina {page_num}: {e}")
            return []
        except Exception as e:
            logging.error(f"Error general en pÃ¡gina {page_num}: {e}")
            return []

    def create_xml(self, events, output_file="eventos_livetv_sx.xml"):
        root = ET.Element("eventos")
        root.set("generado", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        root.set("total", str(len(events)))

        # Crear un conjunto para rastrear URLs ya vistas (para eliminar duplicados)
        seen_urls = set()
        unique_count = 0

        for event in events:
            # Verificar duplicados por URL
            if event["url"] in seen_urls:
                continue

            seen_urls.add(event["url"])
            unique_count += 1

            # Crear elemento XML para el evento
            evento_elem = ET.SubElement(root, "evento")

            # AÃ±adir subelementos con la informaciÃ³n del evento
            nombre_elem = ET.SubElement(evento_elem, "nombre")
            nombre_elem.text = event["nombre"]

            deporte_elem = ET.SubElement(evento_elem, "deporte")
            deporte_elem.text = event["deporte"]

            fecha_elem = ET.SubElement(evento_elem, "fecha")
            fecha_elem.text = event["fecha"]

            hora_elem = ET.SubElement(evento_elem, "hora")
            hora_elem.text = event["hora"]

            url_elem = ET.SubElement(evento_elem, "url")
            url_elem.text = event["url"]

        # Crear un XML formateado
        rough_string = ET.tostring(root, encoding="utf-8")
        reparsed = xml.dom.minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

        # Guardar el XML
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(pretty_xml)

        return unique_count

    def run(self):
        start_time = datetime.now()
        logging.info(f"Iniciando scraping de eventos deportivos en {start_time}")

        try:
            # Probar con una sola pÃ¡gina primero para verificar conexiÃ³n
            test_events = self.extract_events_from_page(1)
            if not test_events:
                logging.error("No se pudieron extraer eventos de la primera pÃ¡gina. Verificar la conexiÃ³n y el sitio web.")
                return False

            self.all_events.extend(test_events)

            # Procesar el resto de pÃ¡ginas
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_page = {executor.submit(self.extract_events_from_page, page_num): page_num 
                                for page_num in range(2, self.max_pages + 1)}

                for future in future_to_page:
                    try:
                        page_events = future.result()
                        self.all_events.extend(page_events)
                    except Exception as exc:
                        page_num = future_to_page[future]
                        logging.error(f"PÃ¡gina {page_num} generÃ³ una excepciÃ³n: {exc}")

            logging.info(f"Total de eventos extraÃ­dos antes de eliminar duplicados: {len(self.all_events)}")

            # Crear el archivo XML
            unique_count = self.create_xml(self.all_events)
            logging.info(f"Total de eventos Ãºnicos guardados en XML: {unique_count}")

            end_time = datetime.now()
            duration = end_time - start_time
            logging.info(f"Proceso completado en {duration.total_seconds():.2f} segundos")
            return True

        except Exception as e:
            logging.error(f"Error crÃ­tico durante la ejecuciÃ³n: {e}")
            return False

# Script principal
if __name__ == "__main__":
    try:
        # Obtener el nÃºmero de pÃ¡ginas de los argumentos o usar el valor por defecto
        import argparse
        parser = argparse.ArgumentParser(description='Scraper de eventos deportivos de livetv.sx')
        parser.add_argument('--pages', type=int, default=200, help='NÃºmero mÃ¡ximo de pÃ¡ginas a procesar (default: 200)')
        parser.add_argument('--workers', type=int, default=5, help='NÃºmero mÃ¡ximo de trabajadores concurrentes (default: 5)')
        parser.add_argument('--output', type=str, default="eventos_livetv_sx.xml", help='Nombre del archivo XML de salida')
        args = parser.parse_args()

        # Crear y ejecutar el scraper
        scraper = EventScraper(max_pages=args.pages, max_workers=args.workers)
        success = scraper.run()

        # Establecer el cÃ³digo de salida
        sys.exit(0 if success else 1)
    except Exception as e:
        logging.critical(f"Error fatal: {e}")
        sys.exit(1)

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

# Patrón de regex para encontrar los enlaces de eventos (mejorado)
EVENT_PATH_REGEX = r"^/es/eventinfo/(\d+(_+)?([a-zA-Z0-9_-]+)?)/?$"

# Patrones para extraer información de fecha y hora
DATE_TIME_PATTERNS = [
    r'(\d{1,2})\s+de\s+(\w+)[\s,]*(\d{1,2}):(\d{2})',  # "4 de junio, 15:00"
    r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})',  # "04/06/2024 15:00"
    r'(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})',  # "04-06-2024 15:00"
    r'(\d{1,2}):(\d{2})',  # Solo hora "15:00"
]

# Diccionario de meses en español
MESES_ES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}

# Headers mejorados para simular un navegador real
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://livetv.sx/es/',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

class EventScraper:
    def __init__(self, base_url="https://livetv.sx", max_pages=200, max_workers=5):
        self.base_url = base_url
        self.max_pages = max_pages
        self.max_workers = max_workers
        self.all_events = []
        self.session = requests.Session()
        self.session.headers.update(headers)

    def parse_date_time(self, text):
        """Función mejorada para extraer fecha y hora del texto"""
        if not text:
            return "No especificado", "No especificado"
        
        text = text.strip().lower()
        
        # Intentar diferentes patrones
        for pattern in DATE_TIME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) == 4:  # Formato con mes en texto
                    dia, mes, hora, minuto = groups
                    mes_num = MESES_ES.get(mes.lower(), mes)
                    fecha = f"{dia.zfill(2)}/{mes_num}/{datetime.now().year}"
                    tiempo = f"{hora.zfill(2)}:{minuto}"
                    return fecha, tiempo
                elif len(groups) == 5:  # Formato completo con año
                    dia, mes, año, hora, minuto = groups
                    fecha = f"{dia.zfill(2)}/{mes.zfill(2)}/{año}"
                    tiempo = f"{hora.zfill(2)}:{minuto}"
                    return fecha, tiempo
                elif len(groups) == 2:  # Solo hora
                    hora, minuto = groups
                    tiempo = f"{hora.zfill(2)}:{minuto}"
                    return "Hoy", tiempo
        
        return "No especificado", "No especificado"

    def extract_sport_and_competition(self, event_container, soup):
        """Función mejorada para extraer deporte y competición"""
        sport = "No especificado"
        competition = "No especificado"
        
        try:
            # Buscar el contenedor del deporte (lado izquierdo de la página)
            sport_containers = soup.find_all('div', class_='lsrowHead')
            
            # Buscar en contenedores de categorías deportivas
            sport_links = soup.find_all('a', href=re.compile(r'/es/sport/'))
            for sport_link in sport_links:
                sport_text = sport_link.get_text(strip=True)
                if sport_text and len(sport_text) > 2:
                    # Verificar si este deporte está cerca del evento actual
                    parent = sport_link.find_parent()
                    if parent and event_container in parent.find_all():
                        sport = sport_text
                        break
            
            # Buscar información de competición en el texto del evento
            event_text = event_container.get_text()
            
            # Patrones comunes para competiciones
            competition_patterns = [
                r'\((.*?)\)',  # Texto entre paréntesis
                r'-(.*?)$',    # Texto después del último guión
                r'Copa\s+.*',  # Copa
                r'Liga\s+.*',  # Liga
                r'Championship\s+.*', # Championship
                r'Premier\s+.*', # Premier
                r'Champions\s+.*', # Champions
            ]
            
            for pattern in competition_patterns:
                match = re.search(pattern, event_text, re.IGNORECASE)
                if match:
                    competition = match.group(1).strip() if match.group(1) else match.group(0).strip()
                    break
            
        except Exception as e:
            logging.debug(f"Error al extraer deporte y competición: {e}")
        
        return sport, competition

    def extract_events_from_page(self, page_num):
        url = f"{self.base_url}/es/allupcomingsports/{page_num}"
        logging.info(f"Procesando página {page_num}: {url}")

        try:
            # Agregar delay aleatorio para evitar bloqueos
            time.sleep(random.uniform(1, 3))

            response = self.session.get(url, verify=False, timeout=30)
            if response.status_code != 200:
                logging.warning(f"Error {response.status_code} al acceder a la página {page_num}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            events = []

            # Buscar las filas de eventos (estructura mejorada)
            event_rows = soup.find_all('tr', class_=['evdesc', 'evdesc_LIVE'])
            
            if not event_rows:
                # Buscar enlaces que coincidan con el patrón de eventos (método alternativo)
                event_links = soup.find_all('a', href=re.compile(EVENT_PATH_REGEX))
            else:
                event_links = []
                for row in event_rows:
                    links = row.find_all('a', href=re.compile(EVENT_PATH_REGEX))
                    event_links.extend(links)

            for link in event_links:
                try:
                    href = link['href']
                    event_container = link.find_parent('tr') or link.parent

                    # Extraer nombre del evento
                    event_name = link.get_text(strip=True)
                    if not event_name:
                        continue

                    # Extraer deporte y competición
                    sport, competition = self.extract_sport_and_competition(event_container, soup)

                    # Buscar fecha y hora en la fila del evento
                    date_time_text = ""
                    
                    # Buscar en celdas de tiempo
                    time_cells = event_container.find_all('td', class_=['time', 'time_LIVE']) if event_container else []
                    for cell in time_cells:
                        date_time_text += " " + cell.get_text(strip=True)
                    
                    # Buscar en spans de tiempo
                    time_spans = event_container.find_all('span', class_=['time', 'evdatetime']) if event_container else []
                    for span in time_spans:
                        date_time_text += " " + span.get_text(strip=True)
                    
                    # Si no se encuentra, buscar en el texto general del contenedor
                    if not date_time_text.strip() and event_container:
                        date_time_text = event_container.get_text()

                    # Procesar fecha y hora
                    fecha, hora = self.parse_date_time(date_time_text)

                    # Construir URL completa
                    full_url = urljoin(self.base_url, href)

                    # Crear objeto de evento
                    event = {
                        "nombre": event_name,
                        "deporte": sport,
                        "competicion": competition,
                        "fecha": fecha,
                        "hora": hora,
                        "url": full_url
                    }

                    events.append(event)
                    logging.debug(f"Evento extraído: {event_name} - {sport} - {fecha} {hora}")

                except Exception as e:
                    logging.error(f"Error al procesar evento en página {page_num}: {e}")
                    continue

            logging.info(f"Extraídos {len(events)} eventos de la página {page_num}")
            return events
            
        except requests.RequestException as e:
            logging.error(f"Error de conexión en página {page_num}: {e}")
            return []
        except Exception as e:
            logging.error(f"Error general en página {page_num}: {e}")
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

            # Añadir subelementos con la información del evento
            nombre_elem = ET.SubElement(evento_elem, "nombre")
            nombre_elem.text = event["nombre"]

            deporte_elem = ET.SubElement(evento_elem, "deporte")
            deporte_elem.text = event["deporte"]

            competicion_elem = ET.SubElement(evento_elem, "competicion")
            competicion_elem.text = event["competicion"]

            fecha_elem = ET.SubElement(evento_elem, "fecha")
            fecha_elem.text = event["fecha"]

            hora_elem = ET.SubElement(evento_elem, "hora")
            hora_elem.text = event["hora"]

            url_elem = ET.SubElement(evento_elem, "url")
            url_elem.text = event["url"]

        # Actualizar el total de eventos únicos
        root.set("total", str(unique_count))

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
            # Probar con una sola página primero para verificar conexión
            test_events = self.extract_events_from_page(1)
            if not test_events:
                logging.warning("No se pudieron extraer eventos de la primera página. Continuando con método alternativo...")
            
            self.all_events.extend(test_events)

            # Procesar el resto de páginas con ThreadPoolExecutor
            if self.max_pages > 1:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_page = {executor.submit(self.extract_events_from_page, page_num): page_num 
                                    for page_num in range(2, min(self.max_pages + 1, 51))}  # Limitado a 50 páginas para evitar sobrecarga

                    for future in future_to_page:
                        try:
                            page_events = future.result()
                            self.all_events.extend(page_events)
                        except Exception as exc:
                            page_num = future_to_page[future]
                            logging.error(f"Página {page_num} generó una excepción: {exc}")

            logging.info(f"Total de eventos extraídos antes de eliminar duplicados: {len(self.all_events)}")

            if not self.all_events:
                logging.error("No se extrajo ningún evento. Verifique la conectividad y la estructura del sitio web.")
                return False

            # Crear el archivo XML
            unique_count = self.create_xml(self.all_events)
            logging.info(f"Total de eventos únicos guardados en XML: {unique_count}")

            end_time = datetime.now()
            duration = end_time - start_time
            logging.info(f"Proceso completado en {duration.total_seconds():.2f} segundos")
            return True

        except Exception as e:
            logging.error(f"Error crítico durante la ejecución: {e}")
            return False

# Script principal
if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser(description='Scraper mejorado de eventos deportivos de livetv.sx')
        parser.add_argument('--pages', type=int, default=10, help='Número máximo de páginas a procesar (default: 10)')
        parser.add_argument('--workers', type=int, default=3, help='Número máximo de trabajadores concurrentes (default: 3)')
        parser.add_argument('--output', type=str, default="eventos_livetv_sx.xml", help='Nombre del archivo XML de salida')
        parser.add_argument('--debug', action='store_true', help='Activar logging de debug')
        args = parser.parse_args()

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Crear y ejecutar el scraper
        scraper = EventScraper(max_pages=args.pages, max_workers=args.workers)
        success = scraper.run()

        if success:
            print(f"✅ Scraping completado exitosamente. Resultados guardados en {args.output}")
        else:
            print("❌ El scraping falló. Revise los logs para más detalles.")

        # Establecer el código de salida
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logging.info("Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"Error fatal: {e}")
        sys.exit(1)

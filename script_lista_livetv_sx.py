#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import re
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import datetime, timedelta
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

# Mapeo de números de página a deportes (basado en la estructura de livetv.sx)
SPORT_MAPPING = {
    1: "Fútbol",
    2: "Hockey sobre hielo", 
    3: "Baloncesto",
    4: "Tenis",
    5: "Voleibol",
    6: "Boxeo",
    7: "Automovilismo",
    8: "Futsal",
    9: "Balonmano",
    10: "Rugby League",
    11: "Béisbol",
    12: "Fútbol americano",
    13: "Billar",
    14: "Dardos",
    15: "Badminton",
    16: "Rugby Union",
    17: "Ciclismo",
    18: "Críquet",
    19: "Fútbol australiano",
    20: "Deporte de combate",
    # Agregar más según sea necesario
}

# Patrón de regex para encontrar los enlaces de eventos
EVENT_PATH_REGEX = r"^/es/eventinfo/(\d+(_+)?([a-zA-Z0-9_-]+)?)/?$"

# Patrones para extraer información de fecha y hora mejorados
DATE_TIME_PATTERNS = [
    # Patrones completos con fecha y hora
    r'(\d{1,2})\s+de\s+(\w+)[\s,]*(\d{1,2}):(\d{2})',  # "4 de junio, 15:00"
    r'(\d{1,2})\s+de\s+(\w+)[\s,]+\w+[\s,]*(\d{1,2}):(\d{2})',  # "4 de junio, miércoles, 15:00"
    r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})',  # "04/06/2024 15:00"
    r'(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})',  # "04-06-2024 15:00"
    # Patrones solo de hora (para asociar con fecha del contexto)
    r'(\d{1,2}):(\d{2})',  # Solo hora "15:00"
]

# Patrones para extraer solo fechas
DATE_PATTERNS = [
    r'(\d{1,2})\s+de\s+(\w+)[\s,]*(\w+)?',  # "4 de junio, miércoles" o "4 de junio"
    r'Hoy\s*\((\d{1,2})\s+de\s+(\w+)[\s,]*(\w+)?\)',  # "Hoy (3 de junio, martes)"
    r'(\d{1,2})\s+(\w+)[\s,]*(\w+)?',  # "4 junio, miércoles"
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
        self.current_date_context = None

    def extract_date_from_context(self, soup):
        """Extrae la fecha del contexto de la página"""
        try:
            # Buscar encabezados de fecha como "Hoy (3 de junio, martes)"
            date_headers = soup.find_all(text=re.compile(r'(Hoy|Mañana|\d+\s+de\s+\w+)'))
            
            for header in date_headers:
                header_text = header.strip()
                
                # Buscar patrones de fecha en el encabezado
                for pattern in DATE_PATTERNS:
                    match = re.search(pattern, header_text, re.IGNORECASE)
                    if match:
                        groups = match.groups()
                        
                        if "hoy" in header_text.lower():
                            # Es "Hoy (3 de junio, martes)"
                            if len(groups) >= 2:
                                dia, mes = groups[0], groups[1]
                                mes_num = MESES_ES.get(mes.lower(), mes)
                                return f"{dia} de {mes}"
                        else:
                            # Es una fecha normal "4 de junio"
                            if len(groups) >= 2:
                                dia, mes = groups[0], groups[1]
                                return f"{dia} de {mes}"
            
            # Si no se encuentra fecha específica, usar fecha actual
            today = datetime.now()
            mes_nombre = list(MESES_ES.keys())[int(today.strftime('%m')) - 1]
            return f"{today.day} de {mes_nombre}"
            
        except Exception as e:
            logging.debug(f"Error al extraer fecha del contexto: {e}")
            today = datetime.now()
            mes_nombre = list(MESES_ES.keys())[int(today.strftime('%m')) - 1]
            return f"{today.day} de {mes_nombre}"

    def parse_date_time(self, text, page_soup=None):
        """Función mejorada para extraer fecha y hora del texto"""
        if not text:
            fecha_contexto = self.extract_date_from_context(page_soup) if page_soup else "No especificado"
            return fecha_contexto, "No especificado"
        
        text = text.strip()
        original_text = text
        text_lower = text.lower()
        
        # Primero intentar extraer fecha y hora juntas
        for pattern in DATE_TIME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) == 4:  # Formato con mes en texto
                    dia, mes, hora, minuto = groups
                    mes_lower = mes.lower()
                    if mes_lower in MESES_ES:
                        fecha = f"{dia} de {mes}"
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
                    # Usar fecha del contexto de la página
                    fecha_contexto = self.extract_date_from_context(page_soup) if page_soup else "No especificado"
                    return fecha_contexto, tiempo
        
        # Si no se encontró fecha completa, buscar solo hora
        hora_match = re.search(r'(\d{1,2}):(\d{2})', text)
        if hora_match:
            hora, minuto = hora_match.groups()
            tiempo = f"{hora.zfill(2)}:{minuto}"
            fecha_contexto = self.extract_date_from_context(page_soup) if page_soup else "No especificado"
            return fecha_contexto, tiempo
        
        # Como último recurso, buscar cualquier fecha en el texto
        for pattern in DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    dia, mes = groups[0], groups[1]
                    if mes.lower() in MESES_ES:
                        fecha = f"{dia} de {mes}"
                        return fecha, "No especificado"
        
        # Si no se encuentra nada, usar contexto de la página
        fecha_contexto = self.extract_date_from_context(page_soup) if page_soup else "No especificado"
        return fecha_contexto, "No especificado"

    def extract_sport_and_competition(self, event_container, soup, page_num):
        """Función mejorada para extraer deporte y competición"""
        # Obtener deporte basado en el número de página
        sport = SPORT_MAPPING.get(page_num, f"Deporte_{page_num}")
        
        competition = "No especificado"
        
        try:
            # Buscar información de competición en el texto del evento
            if event_container:
                event_text = event_container.get_text()
                
                # Patrones comunes para competiciones mejorados
                competition_patterns = [
                    r'\(([^)]+)\)',  # Texto entre paréntesis
                    r'(\w+\.\s*\w+(?:\s+\w+)*)',  # Formato "Liga. Nombre"
                    r'(Copa\s+[^,\n]+)',  # Copa
                    r'(Liga\s+[^,\n]+)',  # Liga
                    r'(Championship\s+[^,\n]+)', # Championship
                    r'(Premier\s+[^,\n]+)', # Premier
                    r'(Champions\s+[^,\n]+)', # Champions
                    r'(\w+\s+Division)', # Division
                    r'(\w+\.\s*\w+)', # Formato con punto
                ]
                
                for pattern in competition_patterns:
                    matches = re.findall(pattern, event_text, re.IGNORECASE)
                    if matches:
                        # Tomar la primera coincidencia que sea relevante
                        for match in matches:
                            if len(match.strip()) > 3 and not re.match(r'^\d+:\d+$', match.strip()):
                                competition = match.strip()
                                break
                        if competition != "No especificado":
                            break
            
        except Exception as e:
            logging.debug(f"Error al extraer deporte y competición: {e}")
        
        return sport, competition

    def extract_events_from_page(self, page_num):
        url = f"{self.base_url}/es/allupcomingsports/{page_num}/"
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

            # Extraer el contexto de fecha de la página
            self.current_date_context = self.extract_date_from_context(soup)

            # Método principal: buscar enlaces de eventos
            event_links = soup.find_all('a', href=re.compile(EVENT_PATH_REGEX))
            
            # Método alternativo: buscar en filas específicas
            if not event_links:
                event_rows = soup.find_all('tr', class_=['evdesc', 'evdesc_LIVE'])
                for row in event_rows:
                    links = row.find_all('a', href=re.compile(EVENT_PATH_REGEX))
                    event_links.extend(links)

            for link in event_links:
                try:
                    href = link['href']
                    event_container = link.find_parent('tr') or link.parent

                    # Extraer nombre del evento
                    event_name = link.get_text(strip=True)
                    if not event_name or len(event_name) < 3:
                        continue

                    # Extraer deporte y competición usando el número de página
                    sport, competition = self.extract_sport_and_competition(event_container, soup, page_num)

                    # Buscar fecha y hora en el contexto del evento
                    date_time_text = ""
                    
                    if event_container:
                        # Buscar en celdas hermanas del enlace
                        parent_row = event_container
                        all_text = parent_row.get_text()
                        date_time_text = all_text
                    
                    # Procesar fecha y hora
                    fecha, hora = self.parse_date_time(date_time_text, soup)

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

            logging.info(f"Extraídos {len(events)} eventos de la página {page_num} ({SPORT_MAPPING.get(page_num, 'Desconocido')})")
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
            # Procesar páginas específicas de deportes
            pages_to_process = list(range(1, min(self.max_pages + 1, 21)))  # Máximo 20 deportes principales
            
            # Procesar primera página para verificar conectividad
            test_events = self.extract_events_from_page(1)
            if test_events:
                self.all_events.extend(test_events)
                logging.info("✅ Conexión verificada exitosamente")
            else:
                logging.warning("⚠️ No se pudieron extraer eventos de la primera página. Continuando...")

            # Procesar el resto de páginas con ThreadPoolExecutor
            if len(pages_to_process) > 1:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_page = {executor.submit(self.extract_events_from_page, page_num): page_num 
                                    for page_num in pages_to_process[1:]}

                    for future in future_to_page:
                        try:
                            page_events = future.result()
                            self.all_events.extend(page_events)
                        except Exception as exc:
                            page_num = future_to_page[future]
                            logging.error(f"Página {page_num} generó una excepción: {exc}")

            logging.info(f"Total de eventos extraídos antes de eliminar duplicados: {len(self.all_events)}")

            if not self.all_events:
                logging.error("❌ No se extrajo ningún evento. Verifique la conectividad y la estructura del sitio web.")
                return False

            # Crear el archivo XML
            unique_count = self.create_xml(self.all_events)
            logging.info(f"✅ Total de eventos únicos guardados en XML: {unique_count}")

            # Mostrar resumen por deporte
            sport_summary = {}
            for event in self.all_events:
                sport = event["deporte"]
                sport_summary[sport] = sport_summary.get(sport, 0) + 1
            
            logging.info("📊 Resumen por deporte:")
            for sport, count in sorted(sport_summary.items()):
                logging.info(f"   {sport}: {count} eventos")

            end_time = datetime.now()
            duration = end_time - start_time
            logging.info(f"🎯 Proceso completado en {duration.total_seconds():.2f} segundos")
            return True

        except Exception as e:
            logging.error(f"💥 Error crítico durante la ejecución: {e}")
            return False

# Script principal
if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser(description='Scraper mejorado de eventos deportivos de livetv.sx')
        parser.add_argument('--pages', type=int, default=20, help='Número máximo de páginas a procesar (default: 20)')
        parser.add_argument('--workers', type=int, default=3, help='Número máximo de trabajadores concurrentes (default: 3)')
        parser.add_argument('--output', type=str, default="eventos_livetv_sx.xml", help='Nombre del archivo XML de salida')
        parser.add_argument('--debug', action='store_true', help='Activar logging de debug')
        parser.add_argument('--sports', type=str, help='Lista de deportes específicos separados por coma (ej: 1,2,3 para Fútbol,Hockey,Baloncesto)')
        args = parser.parse_args()

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Mostrar mapeo de deportes disponibles
        logging.info("🏆 Deportes disponibles:")
        for num, sport in list(SPORT_MAPPING.items())[:20]:
            logging.info(f"   {num}: {sport}")

        # Crear y ejecutar el scraper
        scraper = EventScraper(max_pages=args.pages, max_workers=args.workers)
        
        # Si se especificaron deportes específicos, modificar las páginas a procesar
        if args.sports:
            try:
                sport_pages = [int(x.strip()) for x in args.sports.split(',')]
                scraper.max_pages = max(sport_pages)
                logging.info(f"🎯 Procesando deportes específicos: {[SPORT_MAPPING.get(p, f'Página {p}') for p in sport_pages]}")
            except ValueError:
                logging.error("❌ Error en formato de deportes. Use números separados por coma (ej: 1,2,3)")
                sys.exit(1)
        
        success = scraper.run()

        if success:
            print(f"✅ Scraping completado exitosamente. Resultados guardados en {args.output}")
        else:
            print("❌ El scraping falló. Revise los logs para más detalles.")

        # Establecer el código de salida
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logging.info("⏹️ Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"💥 Error fatal: {e}")
        sys.exit(1)

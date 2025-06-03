#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
from datetime import datetime
import os
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Suprimir advertencias de certificados SSL
warnings.simplefilter('ignore', InsecureRequestWarning)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("update_streams.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# FunciÃ³n para obtener una sesiÃ³n con reintentos
def get_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    # Usar un User-Agent comÃºn
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
    ]
    user_agent = random.choice(user_agents)

    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
        'Referer': 'https://livetv.sx/es/'
    })

    # Desactivar verificaciÃ³n SSL
    session.verify = False

    return session

# FunciÃ³n mejorada para extraer links de reproductores
def extract_reproductor_links(html_content, url_base):
    soup = BeautifulSoup(html_content, 'lxml')
    reproductores = []

    # MÃ©todo 1: Buscar por XPath especÃ­fico (convertido a selectores CSS)
    xpath_converted = 'body > table > tbody > tr > td:nth-child(2) > table > tbody > tr:nth-child(4) > td > table > tbody > tr > td:nth-child(2) > table > tbody > tr > td > table > tbody > tr:nth-child(3) > td > table > tbody > tr > td:nth-child(1) > table:nth-child(1) > tbody > tr > td > div:nth-child(4)'
    specific_element = soup.select_one(xpath_converted)

    if specific_element:
        logger.info("Elemento encontrado con XPath especÃ­fico")
        links = specific_element.find_all('a')
        for link in links:
            href = link.get('href')
            text = link.get_text().strip()
            if href:
                reproductores.append({
                    'tipo': 'xpath-match',
                    'texto': text or 'Enlace de reproductor',
                    'enlace': href if href.startswith(('http', '//')) else urljoin(url_base, href)
                })

    # MÃ©todo 2: Buscar contenedores de reproductores especÃ­ficos
    player_containers = soup.select('.livecover, .lv-player, .player, div#player, .embed-responsive, .video-container')
    for container in player_containers:
        links = container.find_all('a')
        for link in links:
            href = link.get('href')
            text = link.get_text().strip()
            if href:
                reproductores.append({
                    'tipo': 'player-container',
                    'texto': text or 'Reproductor',
                    'enlace': href if href.startswith(('http', '//')) else urljoin(url_base, href)
                })

    # MÃ©todo 3: Buscar enlaces con patrones especÃ­ficos de reproductores
    player_links = soup.find_all('a', href=re.compile(r'(acestream|sopcast|stream|player|vip|embed|channel|watch|canal|ver|directo)'))
    for link in player_links:
        href = link.get('href')
        text = link.get_text().strip()
        if href:
            reproductores.append({
                'tipo': 'player-link',
                'texto': text or 'Enlace de reproductor',
                'enlace': href if href.startswith(('http', '//')) else urljoin(url_base, href)
            })

    # MÃ©todo 4: Buscar iframes que pueden ser reproductores embebidos
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src')
        if src:
            reproductores.append({
                'tipo': 'iframe',
                'texto': 'Reproductor embebido',
                'enlace': src if src.startswith(('http', '//')) else urljoin(url_base, src)
            })

    # MÃ©todo 5: Buscar scripts que puedan contener URLs de reproductores
    scripts = soup.find_all('script')
    for script in scripts:
        content = script.string
        if content:
            # Buscar URLs en el script - Regex corregida
            urls = re.findall(r'(?:http|https|//)[^"'\s]+\.(?:m3u8|mp4|ts|mpd|ism)[^"'\s]*', content)
            for url in urls:
                reproductores.append({
                    'tipo': 'script-url',
                    'texto': 'Stream URL',
                    'enlace': url if url.startswith(('http', '//')) else urljoin(url_base, url)
                })

    # Eliminar duplicados basados en URL
    seen_urls = set()
    unique_reproductores = []
    for rep in reproductores:
        if rep['enlace'] not in seen_urls:
            seen_urls.add(rep['enlace'])
            unique_reproductores.append(rep)

    return unique_reproductores

# FunciÃ³n para hacer scraping de cada URL
def scrape_url(evento_data, session, delay_min=2, delay_max=5):
    url = evento_data['url']
    try:
        # Agregar un delay aleatorio entre solicitudes
        time.sleep(random.uniform(delay_min, delay_max))

        logger.info(f"Procesando: {url}")
        response = session.get(url, timeout=15)

        if response.status_code != 200:
            logger.warning(f"Error al acceder a {url}. Status code: {response.status_code}")
            return evento_data

        # Extraer reproductores
        reproductores = extract_reproductor_links(response.text, url)

        if reproductores:
            evento_data['reproductores'] = reproductores
            logger.info(f"Encontrados {len(reproductores)} reproductores para {url}")
        else:
            logger.warning(f"No se encontraron reproductores para {url}")
            evento_data['reproductores'] = []

        return evento_data
    except requests.exceptions.Timeout:
        logger.error(f"Timeout al acceder a {url}")
    except requests.exceptions.ConnectionError:
        logger.error(f"Error de conexiÃ³n al acceder a {url}")
    except Exception as e:
        logger.error(f"Error al procesar {url}: {str(e)}")

    evento_data['reproductores'] = []
    return evento_data

# FunciÃ³n para crear el XML con los reproductores
def create_xml_with_reproductores(eventos_data):
    root = ET.Element("eventos")
    root.set("generado", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set("total", str(len(eventos_data)))

    for evento_data in eventos_data:
        evento = ET.SubElement(root, "evento")

        # AÃ±adir elementos bÃ¡sicos
        for key, value in evento_data.items():
            if key != 'reproductores':
                elem = ET.SubElement(evento, key)
                elem.text = value

        # AÃ±adir secciÃ³n de reproductores
        reproductores_elem = ET.SubElement(evento, "reproductores")

        for rep_data in evento_data.get('reproductores', []):
            reproductor = ET.SubElement(reproductores_elem, "reproductor")

            tipo = ET.SubElement(reproductor, "tipo")
            tipo.text = rep_data['tipo']

            texto = ET.SubElement(reproductor, "texto")
            texto.text = rep_data['texto']

            enlace = ET.SubElement(reproductor, "enlace")
            enlace.text = rep_data['enlace']

    # Convertir a string XML con formato
    xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent="  ")

    return xml_str

def main():
    start_time = time.time()
    logger.info("Iniciando actualizaciÃ³n de enlaces de streaming")

    # EstadÃ­sticas
    stats = {
        'total_eventos': 0,
        'eventos_con_reproductores': 0,
        'total_reproductores': 0,
        'errores': 0
    }

    try:
        # Descargar el archivo XML
        xml_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml"
        logger.info(f"Descargando XML desde {xml_url}")
        response = requests.get(xml_url)
        xml_content = response.content

        # Parsear el XML
        root = ET.fromstring(xml_content)
        eventos = []

        # Obtener una sesiÃ³n
        session = get_session()

        # Extraer URLs y datos de eventos
        for evento in root.findall('./evento'):
            try:
                evento_data = {}
                for child in evento:
                    evento_data[child.tag] = child.text

                # Solo procesar si hay URL
                if 'url' in evento_data and evento_data['url']:
                    stats['total_eventos'] += 1
                    # Hacer scraping de la URL
                    evento_data = scrape_url(evento_data, session)
                    eventos.append(evento_data)

                    # Actualizar estadÃ­sticas
                    if evento_data.get('reproductores'):
                        stats['eventos_con_reproductores'] += 1
                        stats['total_reproductores'] += len(evento_data['reproductores'])
                else:
                    logger.warning(f"Evento sin URL: {evento_data.get('nombre', 'Desconocido')}")
            except Exception as e:
                logger.error(f"Error procesando evento: {str(e)}")
                stats['errores'] += 1

        # Crear el nuevo XML con reproductores
        logger.info("Generando nuevo archivo XML con reproductores")
        xml_con_reproductores = create_xml_with_reproductores(eventos)

        # Guardar el nuevo XML
        with open("eventos_livetv_sx_con_reproductores.xml", "w", encoding='utf-8') as f:
            f.write(xml_con_reproductores)

        # Tiempo total
        elapsed_time = time.time() - start_time
        logger.info(f"Proceso completado en {elapsed_time:.2f} segundos")

        # Mostrar estadÃ­sticas
        logger.info(f"EstadÃ­sticas:")
        logger.info(f"- Total de eventos procesados: {stats['total_eventos']}")
        logger.info(f"- Eventos con reproductores: {stats['eventos_con_reproductores']}")
        logger.info(f"- Total de reproductores encontrados: {stats['total_reproductores']}")
        logger.info(f"- Errores: {stats['errores']}")

        # Generar reporte adicional
        with open("reporte_scraping.txt", "w", encoding='utf-8') as f:
            f.write(f"Reporte de Scraping - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n")
            f.write(f"Total de eventos procesados: {stats['total_eventos']}\n")
            f.write(f"Eventos con reproductores: {stats['eventos_con_reproductores']} ({stats['eventos_con_reproductores']*100/stats['total_eventos']:.2f}%)\n")
            f.write(f"Total de reproductores encontrados: {stats['total_reproductores']}\n")
            f.write(f"Promedio de reproductores por evento: {stats['total_reproductores']/stats['total_eventos'] if stats['total_eventos'] > 0 else 0:.2f}\n")
            f.write(f"Errores: {stats['errores']}\n")
            f.write("="*60 + "\n")

    except Exception as e:
        logger.error(f"Error general: {str(e)}")

if __name__ == "__main__":
    main()

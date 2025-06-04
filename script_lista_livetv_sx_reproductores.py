#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
from datetime import datetime
import json
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

def get_session():
    """Crear una sesión HTTP con configuración optimizada para LiveTV.sx"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # User-Agents actualizados
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
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
        'Referer': 'https://livetv.sx/es/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin'
    })
    
    session.verify = False
    return session

def extract_reproductor_links(html_content, url_base):
    """
    Función mejorada para extraer enlaces de reproductores de LiveTV.sx
    
    Estrategias implementadas:
    1. Detección de URLs webplayer.php mediante regex
    2. Análisis de iframes embebidos 
    3. Búsqueda en sección Browser Links
    4. Extracción de JavaScript con URLs
    5. Reconstrucción de URLs desde parámetros
    6. Detección de enlaces acestream/sopcast
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    reproductores = []
    
    # Extraer ID del evento desde la URL base para reconstruir URLs
    event_id_match = re.search(r'/eventinfo/(\d+)_', url_base)
    event_id = event_id_match.group(1) if event_id_match else None
    
    # Método 1: Buscar URLs webplayer.php directamente en el HTML
    webplayer_pattern = r'https?://[^"\'\s]*\.livetv\d*\.(?:sx|me)/[^"\'\s]*webplayer\.php[^"\'\s]*'
    webplayer_urls = re.findall(webplayer_pattern, html_content)
    for url in webplayer_urls:
        reproductores.append({
            'tipo': 'webplayer-direct',
            'texto': 'WebPlayer directo',
            'enlace': url
        })
    
    # Método 2: Buscar en la sección "Browser Links" específica
    browser_links_section = soup.find('td', string=re.compile(r'Browser Links|Enlaces del navegador'))
    if browser_links_section:
        parent_section = browser_links_section.find_parent('table')
        if parent_section:
            links = parent_section.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and ('webplayer' in href or 'player' in href or 'stream' in href):
                    reproductores.append({
                        'tipo': 'browser-links',
                        'texto': link.get_text().strip() or 'Browser Link',
                        'enlace': href if href.startswith('http') else urljoin(url_base, href)
                    })
    
    # Método 3: Buscar todos los iframes (reproductores embebidos)
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src')
        if src:
            if any(domain in src for domain in ['webplayer', 'player', 'stream', 'daddylive', 'livetv']):
                reproductores.append({
                    'tipo': 'iframe-embed',
                    'texto': 'Reproductor embebido',
                    'enlace': src if src.startswith('http') else urljoin(url_base, src)
                })
    
    # Método 4: Extraer desde JavaScript - URLs de streaming
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            content = script.string
            
            # Buscar URLs webplayer en JavaScript
            js_webplayer_urls = re.findall(r'["\']([^"\']*webplayer\.php[^"\']*)["\']', content)
            for url in js_webplayer_urls:
                if url.startswith('http'):
                    reproductores.append({
                        'tipo': 'javascript-webplayer',
                        'texto': 'WebPlayer desde JS',
                        'enlace': url
                    })
            
            # Buscar otros tipos de URLs de streaming
            streaming_patterns = [
                r'["\']([^"\']*\.m3u8[^"\']*)["\']',
                r'["\']([^"\']*acestream[^"\']*)["\']',
                r'["\']([^"\']*sopcast[^"\']*)["\']',
                r'["\']([^"\']*\.mp4[^"\']*)["\']'
            ]
            
            for pattern in streaming_patterns:
                urls = re.findall(pattern, content)
                for url in urls:
                    if url.startswith('http'):
                        reproductores.append({
                            'tipo': 'javascript-stream',
                            'texto': 'Stream desde JS',
                            'enlace': url
                        })
    
    # Método 5: Reconstruir URLs webplayer desde parámetros encontrados
    if event_id:
        # Buscar patrones de parámetros de streaming
        lid_matches = re.findall(r'lid[=:](\d+)', html_content)
        c_matches = re.findall(r'[&?]c[=:](\d+)', html_content)
        ci_matches = re.findall(r'ci[=:](\d+)', html_content)
        
        # Combinar parámetros encontrados para crear URLs
        lids = set(lid_matches + c_matches)
        cis = set(ci_matches) if ci_matches else ['1']
        
        for lid in lids:
            for ci in cis:
                for si in ['1', '2', '3']:  # Intentar diferentes streams
                    webplayer_url = f"https://cdn.livetv853.me/webplayer.php?t=ifr&c={lid}&lang=es&eid={event_id}&lid={lid}&ci={ci}&si={si}"
                    reproductores.append({
                        'tipo': 'reconstructed-webplayer',
                        'texto': f'WebPlayer reconstruido (lid:{lid}, ci:{ci}, si:{si})',
                        'enlace': webplayer_url
                    })
    
    # Método 6: Buscar enlaces con patrones específicos de reproductores
    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link.get('href')
        text = link.get_text().strip()
        
        if href and any(pattern in href.lower() for pattern in [
            'webplayer', 'player', 'stream', 'acestream', 'sopcast', 
            'embed', 'watch', 'live', 'directo', 'ver'
        ]):
            full_url = href if href.startswith('http') else urljoin(url_base, href)
            reproductores.append({
                'tipo': 'pattern-link',
                'texto': text or 'Enlace de reproductor',
                'enlace': full_url
            })
    
    # Método 7: Buscar contenido específico de LiveTV
    # Buscar texto que contenga porcentajes y "Web" (indicador de reproductores web)
    web_indicators = soup.find_all(text=re.compile(r'\d+%.*Web'))
    for indicator in web_indicators:
        parent = indicator.parent
        if parent:
            nearby_links = parent.find_all('a', href=True, limit=5)
            for link in nearby_links:
                href = link.get('href')
                if href:
                    reproductores.append({
                        'tipo': 'web-indicator',
                        'texto': f'Web ({indicator.strip()})',
                        'enlace': href if href.startswith('http') else urljoin(url_base, href)
                    })
    
    # Eliminar duplicados manteniendo el orden
    seen_urls = set()
    unique_reproductores = []
    for rep in reproductores:
        if rep['enlace'] not in seen_urls:
            seen_urls.add(rep['enlace'])
            unique_reproductores.append(rep)
    
    # Filtrar URLs obviamente no válidas
    filtered_reproductores = []
    for rep in unique_reproductores:
        url = rep['enlace']
        if (url.startswith('http') and 
            not any(skip in url.lower() for skip in ['javascript:', 'mailto:', '#', 'facebook.com', 'twitter.com']) and
            len(url) > 10):
            filtered_reproductores.append(rep)
    
    return filtered_reproductores

def verify_webplayer_url(session, webplayer_url):
    """Verificar si una URL de webplayer es válida y extraer contenido adicional"""
    try:
        response = session.get(webplayer_url, timeout=10)
        if response.status_code == 200:
            # Buscar iframes en el contenido del webplayer
            soup = BeautifulSoup(response.text, 'html.parser')
            iframes = soup.find_all('iframe')
            
            additional_players = []
            for iframe in iframes:
                src = iframe.get('src')
                if src and src.startswith('http'):
                    additional_players.append({
                        'tipo': 'webplayer-iframe',
                        'texto': 'Stream desde webplayer',
                        'enlace': src
                    })
            
            return True, additional_players
    except:
        pass
    
    return False, []

def scrape_url(evento_data, session, delay_min=2, delay_max=5):
    """Función mejorada para hacer scraping de cada URL"""
    url = evento_data['url']
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        logger.info(f"Procesando: {url}")
        
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Error al acceder a {url}. Status code: {response.status_code}")
            return evento_data
        
        # Extraer reproductores usando la función mejorada
        reproductores = extract_reproductor_links(response.text, url)
        
        # Verificar URLs webplayer y extraer contenido adicional
        additional_players = []
        for rep in reproductores[:3]:  # Solo verificar los primeros 3 para no sobrecargar
            if 'webplayer' in rep['enlace']:
                is_valid, extra_players = verify_webplayer_url(session, rep['enlace'])
                if extra_players:
                    additional_players.extend(extra_players)
        
        reproductores.extend(additional_players)
        
        if reproductores:
            evento_data['reproductores'] = reproductores
            logger.info(f"Encontrados {len(reproductores)} reproductores para {url}")
            
            # Log de tipos de reproductores encontrados
            tipos = [rep['tipo'] for rep in reproductores]
            tipo_counts = {}
            for tipo in tipos:
                tipo_counts[tipo] = tipo_counts.get(tipo, 0) + 1
            logger.info(f"Tipos encontrados: {tipo_counts}")
        else:
            logger.warning(f"No se encontraron reproductores para {url}")
            evento_data['reproductores'] = []
        
        return evento_data
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout al acceder a {url}")
    except requests.exceptions.ConnectionError:
        logger.error(f"Error de conexión al acceder a {url}")
    except Exception as e:
        logger.error(f"Error al procesar {url}: {str(e)}")
    
    evento_data['reproductores'] = []
    return evento_data

def create_xml_with_reproductores(eventos_data):
    """Crear XML con reproductores encontrados"""
    root = ET.Element("eventos")
    root.set("generado", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set("total", str(len(eventos_data)))
    
    for evento_data in eventos_data:
        evento = ET.SubElement(root, "evento")
        
        # Añadir elementos básicos
        for key, value in evento_data.items():
            if key != 'reproductores':
                elem = ET.SubElement(evento, key)
                elem.text = str(value) if value is not None else ""
        
        # Añadir sección de reproductores
        reproductores_elem = ET.SubElement(evento, "reproductores")
        reproductores_elem.set("total", str(len(evento_data.get('reproductores', []))))
        
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
    logger.info("Iniciando actualización de enlaces de streaming con detección mejorada")
    
    # Estadísticas mejoradas
    stats = {
        'total_eventos': 0,
        'eventos_con_reproductores': 0,
        'total_reproductores': 0,
        'errores': 0,
        'tipos_reproductores': {}
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
        
        # Obtener una sesión
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
                    
                    # Limitar el procesamiento a los primeros eventos para pruebas
                    if stats['total_eventos'] > 20:  # Cambiar este número según necesites
                        logger.info(f"Limitando procesamiento a {stats['total_eventos']-1} eventos para pruebas")
                        break
                    
                    # Hacer scraping de la URL
                    evento_data = scrape_url(evento_data, session)
                    eventos.append(evento_data)
                    
                    # Actualizar estadísticas
                    if evento_data.get('reproductores'):
                        stats['eventos_con_reproductores'] += 1
                        stats['total_reproductores'] += len(evento_data['reproductores'])
                        
                        # Contar tipos de reproductores
                        for rep in evento_data['reproductores']:
                            tipo = rep['tipo']
                            stats['tipos_reproductores'][tipo] = stats['tipos_reproductores'].get(tipo, 0) + 1
                else:
                    logger.warning(f"Evento sin URL: {evento_data.get('nombre', 'Desconocido')}")
                    
            except Exception as e:
                logger.error(f"Error procesando evento: {str(e)}")
                stats['errores'] += 1
        
        # Crear el nuevo XML con reproductores
        logger.info("Generando nuevo archivo XML con reproductores")
        xml_con_reproductores = create_xml_with_reproductores(eventos)
        
        # Guardar el nuevo XML
        with open("eventos_livetv_sx_con_reproductores_mejorado.xml", "w", encoding='utf-8') as f:
            f.write(xml_con_reproductores)
        
        # Tiempo total
        elapsed_time = time.time() - start_time
        logger.info(f"Proceso completado en {elapsed_time:.2f} segundos")
        
        # Mostrar estadísticas detalladas
        logger.info("=== ESTADÍSTICAS DETALLADAS ===")
        logger.info(f"Total de eventos procesados: {stats['total_eventos']}")
        logger.info(f"Eventos con reproductores: {stats['eventos_con_reproductores']}")
        logger.info(f"Total de reproductores encontrados: {stats['total_reproductores']}")
        logger.info(f"Promedio de reproductores por evento: {stats['total_reproductores']/max(stats['total_eventos'], 1):.2f}")
        logger.info(f"Tasa de éxito: {stats['eventos_con_reproductores']*100/max(stats['total_eventos'], 1):.1f}%")
        logger.info(f"Errores: {stats['errores']}")
        
        logger.info("\n=== TIPOS DE REPRODUCTORES ENCONTRADOS ===")
        for tipo, count in sorted(stats['tipos_reproductores'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"{tipo}: {count}")
        
        # Generar reporte detallado
        with open("reporte_scraping_detallado.txt", "w", encoding='utf-8') as f:
            f.write(f"Reporte de Scraping Detallado - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            f.write(f"Total de eventos procesados: {stats['total_eventos']}\n")
            f.write(f"Eventos con reproductores: {stats['eventos_con_reproductores']} ({stats['eventos_con_reproductores']*100/max(stats['total_eventos'], 1):.1f}%)\n")
            f.write(f"Total de reproductores encontrados: {stats['total_reproductores']}\n")
            f.write(f"Promedio de reproductores por evento: {stats['total_reproductores']/max(stats['total_eventos'], 1):.2f}\n")
            f.write(f"Errores: {stats['errores']}\n")
            f.write(f"Tiempo de ejecución: {elapsed_time:.2f} segundos\n\n")
            
            f.write("DISTRIBUCIÓN DE TIPOS DE REPRODUCTORES:\n")
            f.write("-" * 50 + "\n")
            for tipo, count in sorted(stats['tipos_reproductores'].items(), key=lambda x: x[1], reverse=True):
                f.write(f"{tipo}: {count}\n")
            
            f.write("\n" + "="*80 + "\n")
    
    except Exception as e:
        logger.error(f"Error general: {str(e)}")

if __name__ == "__main__":
    main()

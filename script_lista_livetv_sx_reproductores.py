import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
import time
import random
import logging
from urllib.parse import urljoin, urlparse, quote, parse_qs
import concurrent.futures
from bs4 import BeautifulSoup
import urllib3
from pathlib import Path
import threading
import json

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class CompleteImprovedLiveTVExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.base_url = "https://livetv.sx"
        self.reference_xml_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml"
        self.current_date = "15 de junio"  # Día actual especificado
        self.stats = {
            'events_processed': 0,
            'streams_found': 0,
            'failed_events': 0,
            'iframe_patterns_matched': {},
            'stream_types_found': {}
        }
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        ]
        
        # Patrones específicos mejorados para LiveTV.sx
        self.iframe_patterns = [
            # Patrones básicos de iframe
            r'<iframe[^>]+src=["\']([^"\']*(?:webplayer|embed|player|stream)[^"\']*)["\'][^>]*>',
            r'<iframe[^>]+src=["\']([^"\']*cdn[^"\']*livetv[^"\']*)["\'][^>]*>',
            
            # Patrones específicos de LiveTV CDN
            r'<iframe[^>]+src=["\']([^"\']*cdn\.livetv\d+\.me[^"\']*)["\'][^>]*>',
            r'<iframe[^>]+src=["\']([^"\']*livetv\d+\.me[^"\']*webplayer[^"\']*)["\'][^>]*>',
            
            # Patrones para voodc y otros embeds
            r'<iframe[^>]+src=["\']([^"\']*voodc\.com[^"\']*)["\'][^>]*>',
            r'<iframe[^>]+src=["\']([^"\']*embedme\.top[^"\']*)["\'][^>]*>',
            
            # Patrones para URLs con parámetros específicos
            r'<iframe[^>]+src=["\']([^"\']*\?[^"\']*[ct]=\d+[^"\']*)["\'][^>]*>',
            r'<iframe[^>]+src=["\']([^"\']*\?[^"\']*eid=\d+[^"\']*)["\'][^>]*>',
        ]
        
        # Patrones para detectar links de streams en el contenido
        self.stream_link_patterns = [
            # URLs directas en JavaScript
            r'(?:src|url|href)["\'\s]*[:=]\s*["\']([^"\']*(?:webplayer|embed|cdn)[^"\']*)["\']',
            r'["\']([^"\']*cdn\.livetv\d+\.me[^"\']*)["\']',
            r'["\']([^"\']*voodc\.com[^"\']*)["\']',
            
            # URLs con parámetros específicos de LiveTV
            r'["\']([^"\']*\?[^"\']*[ct]=\d+[^"\']*)["\']',
            r'["\']([^"\']*webplayer2?\.php[^"\']*)["\']',
            
            # URLs de YouTube embebidas
            r'["\']([^"\']*youtube\.com/embed/[^"\']*)["\']',
            r'["\']([^"\']*youtu\.be/[^"\']*)["\']',
        ]
        
        # Dominios de streams conocidos (expandido)
        self.stream_domains = [
            'cdn.livetv853.me', 'cdn2.livetv853.me', 'cdn3.livetv853.me',
            'cdn.livetv854.me', 'cdn2.livetv854.me', 'cdn3.livetv854.me',
            'cdn.livetv855.me', 'cdn2.livetv855.me', 'cdn3.livetv855.me',
            'voodc.com', 'embedme.top', 'streamable.com', 'vidoza.net',
            'daddylive.me', 'player.livetv.sx', 'stream.livetv.sx',
            'youtube.com', 'youtu.be', 'dailymotion.com', 'vimeo.com'
        ]
        
        # Tipos de player identificados en LiveTV
        self.player_types = ['ifr', 'alieztv', 'youtube', 'twitch', 'dailymotion', 'voodc', 'web']
        
        self.lock = threading.Lock()

    def get_dynamic_headers(self, referer=None):
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        }
        if referer:
            headers['Referer'] = referer
        return headers

    def robust_request(self, url, timeout=20, max_retries=3):
        for attempt in range(max_retries):
            try:
                headers = self.get_dynamic_headers()
                response = self.session.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return response
                elif response.status_code in [429, 503]:
                    wait_time = min(2 ** attempt + random.uniform(1, 3), 30)
                    logger.warning(f"Rate limit/Service unavailable, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Status {response.status_code} for {url[:60]}...")
            except requests.exceptions.RequestException as e:
                logger.debug(f"Request failed in attempt {attempt + 1}: {str(e)[:80]}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(1, 3))
            except Exception as e:
                logger.debug(f"Unexpected error: {str(e)[:80]}")
                break
        return None

    def load_reference_events(self):
        logger.info("Descargando eventos de referencia desde XML...")
        response = self.robust_request(self.reference_xml_url)
        if not response:
            logger.error("Error al descargar el XML de referencia")
            return []
        
        try:
            root = ET.fromstring(response.content)
            events = []
            
            for evento_elem in root.findall('evento'):
                event_data = {}
                
                # Extraer todos los campos del evento
                for child in evento_elem:
                    if child.text:
                        event_data[child.tag] = child.text.strip()
                
                # Filtrar solo eventos del día actual
                if event_data.get('fecha') == self.current_date and event_data.get('url'):
                    event_data['id'] = self.extract_event_id(event_data['url'])
                    event_data['datetime_iso'] = self.create_datetime_iso(event_data.get('fecha'), event_data.get('hora'))
                    event_data['cerca_hora_actual'] = self.is_near_current_time(event_data.get('hora'))
                    events.append(event_data)
            
            logger.info(f"Cargados {len(events)} eventos para {self.current_date}")
            return events
            
        except ET.ParseError as e:
            logger.error(f"Error al parsear XML: {e}")
            return []

    def extract_event_id(self, url):
        if not url:
            return str(random.randint(100000, 999999))
        
        patterns = [
            r'/eventinfo/(\d+)_',
            r'eventinfo/(\d+)_',
            r'eventinfo/(\d+)',
            r'id=(\d+)',
            r'/(\d+)_'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return str(abs(hash(url)) % 10000000)

    def create_datetime_iso(self, fecha, hora):
        try:
            if not hora:
                return "2025-06-15T00:00:00"
            
            # Limpiar la hora y extraer solo HH:MM
            hora_clean = re.sub(r'[^\d:]', '', hora)
            if ':' in hora_clean:
                return f"2025-06-15T{hora_clean}:00"
            else:
                return f"2025-06-15T{hora_clean}:00:00"
        except:
            return "2025-06-15T00:00:00"

    def is_near_current_time(self, hora):
        try:
            if not hora:
                return "False"
            
            # Limpiar la hora
            hora_clean = re.sub(r'[^\d:]', '', hora)
            if ':' not in hora_clean:
                return "False"
            
            # Obtener hora actual (simulada para el ejemplo)
            current_hour = 21  # 21:00 como hora actual de ejemplo
            event_hour = int(hora_clean.split(':')[0])
            
            # Considerar "cerca" si está dentro de 2 horas
            return "True" if abs(event_hour - current_hour) <= 2 else "False"
        except:
            return "False"

    def extract_comprehensive_streams(self, event_url, event_name):
        logger.info(f"Extrayendo streams para: {event_name[:50]}...")
        all_streams = set()
        event_id = self.extract_event_id(event_url)

        # 1. Extraer streams directos de la página del evento
        direct_streams = self._extract_direct_streams_enhanced(event_url)
        all_streams.update(direct_streams)

        # 2. Analizar estructura específica de LiveTV para detectar enlaces ocultos
        hidden_streams = self._extract_hidden_stream_links(event_url, event_id)
        all_streams.update(hidden_streams)

        # 3. Generar streams basados en patrones conocidos (mejorado)
        pattern_streams = self._generate_comprehensive_pattern_streams(event_id, event_url)
        all_streams.update(pattern_streams)

        # 4. Buscar streams en JavaScript y contenido dinámico
        js_streams = self._extract_javascript_streams(event_url)
        all_streams.update(js_streams)

        # 5. Análisis profundo de enlaces embebidos
        embedded_streams = self._deep_analyze_embedded_content(event_url)
        all_streams.update(embedded_streams)

        # Filtrar y validar streams con análisis mejorado
        valid_streams = []
        for url in all_streams:
            if self.is_valid_stream_url_enhanced(url):
                stream_info = self._analyze_stream_url(url)
                valid_streams.append(stream_info)

        with self.lock:
            self.stats['streams_found'] += len(valid_streams)

        logger.info(f"Encontrados {len(valid_streams)} streams válidos para {event_name[:30]}")
        return valid_streams

    def _extract_direct_streams_enhanced(self, event_url):
        streams = set()
        response = self.robust_request(event_url)
        if not response:
            return streams

        content = response.text
        soup = BeautifulSoup(content, 'html.parser')

        # Análisis de iframes mejorado
        for pattern in self.iframe_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                normalized = self.normalize_url(match, event_url)
                if normalized:
                    streams.add(normalized)
                    with self.lock:
                        pattern_name = pattern[:50] + "..."
                        self.stats['iframe_patterns_matched'][pattern_name] = \
                            self.stats['iframe_patterns_matched'].get(pattern_name, 0) + 1

        # Búsqueda en elementos HTML específicos
        for tag in ['iframe', 'embed', 'video', 'source', 'object']:
            elements = soup.find_all(tag)
            for elem in elements:
                for attr in ['src', 'data-src', 'data', 'data-url', 'href']:
                    url = elem.get(attr)
                    if url:
                        normalized = self.normalize_url(url, event_url)
                        if normalized:
                            streams.add(normalized)

        # Búsqueda en links con texto específico de LiveTV
        stream_keywords = ['ver', 'watch', 'stream', 'play', 'live', 'aliez', 'voodc', 'youtube', 'web']
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text().lower().strip()
            
            # Detectar por texto del enlace
            if any(keyword in text for keyword in stream_keywords):
                normalized = self.normalize_url(href, event_url)
                if normalized:
                    streams.add(normalized)
            
            # Detectar por estructura del href
            if any(domain in href for domain in self.stream_domains):
                normalized = self.normalize_url(href, event_url)
                if normalized:
                    streams.add(normalized)

        return streams

    def _extract_hidden_stream_links(self, event_url, event_id):
        """Extrae enlaces que no están directamente visibles en iframes"""
        streams = set()
        response = self.robust_request(event_url)
        if not response:
            return streams

        content = response.text
        soup = BeautifulSoup(content, 'html.parser')

        # Buscar en todos los scripts por patrones de URL
        for script in soup.find_all('script', string=True):
            if script.string:
                for pattern in self.stream_link_patterns:
                    urls = re.findall(pattern, script.string, re.IGNORECASE)
                    for url in urls:
                        normalized = self.normalize_url(url, event_url)
                        if normalized:
                            streams.add(normalized)

        # Buscar en atributos data-* y onclick
        for elem in soup.find_all(attrs={'data-url': True}):
            url = elem.get('data-url')
            normalized = self.normalize_url(url, event_url)
            if normalized:
                streams.add(normalized)

        for elem in soup.find_all(onclick=True):
            onclick = elem.get('onclick')
            # Buscar URLs en JavaScript onclick
            url_matches = re.findall(r'["\']([^"\']*(?:webplayer|embed|cdn)[^"\']*)["\']', onclick)
            for url in url_matches:
                normalized = self.normalize_url(url, event_url)
                if normalized:
                    streams.add(normalized)

        return streams

    def _generate_comprehensive_pattern_streams(self, event_id, event_url):
        streams = set()
        
        # URLs base más completas
        cdn_variants = [
            'https://cdn.livetv853.me/webplayer.php',
            'https://cdn.livetv853.me/webplayer2.php',
            'https://cdn2.livetv853.me/webplayer.php',
            'https://cdn2.livetv853.me/webplayer2.php',
            'https://cdn3.livetv853.me/webplayer.php',
            'https://cdn3.livetv853.me/webplayer2.php',
            'https://cdn.livetv854.me/webplayer.php',
            'https://cdn.livetv854.me/webplayer2.php',
            'https://cdn2.livetv854.me/webplayer.php',
            'https://cdn2.livetv854.me/webplayer2.php'
        ]
        
        # IDs de canales expandidos basados en los patrones observados
        channel_ranges = [
            range(2760000, 2765000),  # Rango principal observado
            range(238000, 239000),    # Rango secundario
            range(234000, 235000),    # Rango adicional
            range(237000, 238000)     # Otro rango
        ]
        
        # Todos los tipos de player observados
        player_types = ['ifr', 'alieztv', 'youtube', 'twitch', 'dailymotion', 'voodc', 'web']
        
        # Parámetros adicionales observados
        ci_values = ['1995', '598', '3650']  # Valores de ci observados
        si_values = ['37', '75', '7']        # Valores de si observados
        
        for cdn_base in cdn_variants:
            for channel_range in channel_ranges:
                # Tomar muestra de cada rango para no generar demasiados
                sample_channels = list(channel_range)[::100]  # Cada 100
                
                for channel in sample_channels:
                    for player_type in player_types:
                        for ci in ci_values:
                            for si in si_values:
                                # Generar lid basado en el canal
                                lid = str(channel)
                                
                                params = {
                                    'lang': 'es',
                                    'eid': event_id,
                                    'c': str(channel),
                                    't': player_type,
                                    'lid': lid,
                                    'ci': ci,
                                    'si': si
                                }
                                query_string = '&'.join(f"{k}={v}" for k, v in params.items())
                                stream_url = f"{cdn_base}?{query_string}"
                                streams.add(stream_url)
        
        return streams

    def _extract_javascript_streams(self, event_url):
        """Analizar JavaScript para encontrar URLs de streams dinámicos"""
        streams = set()
        response = self.robust_request(event_url)
        if not response:
            return streams

        content = response.text
        
        # Patrones específicos para JavaScript en LiveTV
        js_patterns = [
            r'(?:webplayer|embed|stream)["\'\s]*[:=]\s*["\']([^"\']+)["\']',
            r'(?:url|src|href)["\'\s]*[:=]\s*["\']([^"\']*(?:cdn|webplayer|embed)[^"\']*)["\']',
            r'cdn\.livetv\d+\.me[^"\']*',
            r'voodc\.com[^"\']*',
            r'youtube\.com/embed/[^"\']*',
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                normalized = self.normalize_url(match, event_url)
                if normalized:
                    streams.add(normalized)
        
        return streams

    def _deep_analyze_embedded_content(self, event_url):
        """Análisis profundo del contenido embebido"""
        streams = set()
        response = self.robust_request(event_url)
        if not response:
            return streams

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar en comentarios HTML (a veces contienen URLs)
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            for pattern in self.stream_link_patterns:
                matches = re.findall(pattern, str(comment), re.IGNORECASE)
                for match in matches:
                    normalized = self.normalize_url(match, event_url)
                    if normalized:
                        streams.add(normalized)
        
        # Buscar en metadatos
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            content = meta.get('content', '')
            if any(domain in content for domain in self.stream_domains):
                for pattern in self.stream_link_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        normalized = self.normalize_url(match, event_url)
                        if normalized:
                            streams.add(normalized)
        
        return streams

    def _analyze_stream_url(self, url):
        """Analizar URL de stream para extraer información adicional"""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        stream_info = {'url': url}
        
        # Extraer tipo de player
        if 't' in params:
            stream_info['player_type'] = params['t'][0]
            with self.lock:
                player_type = params['t'][0]
                self.stats['stream_types_found'][player_type] = \
                    self.stats['stream_types_found'].get(player_type, 0) + 1
        
        # Extraer información de calidad si está disponible
        if 'q' in params:
            stream_info['quality'] = params['q'][0]
        
        # Identificar dominio
        stream_info['domain'] = parsed.netloc
        
        # Identificar tipo basado en URL
        if 'youtube' in url.lower():
            stream_info['type'] = 'youtube'
        elif 'voodc' in url.lower():
            stream_info['type'] = 'voodc'
        elif 'webplayer' in url.lower():
            stream_info['type'] = 'webplayer'
        else:
            stream_info['type'] = 'unknown'
        
        return stream_info

    def normalize_url(self, url, base_url):
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip().replace('\\', '').replace('\n', '').replace('\r', '')
        url = re.sub(r'\s+', '', url)  # Eliminar espacios
        
        if url.startswith(('http://', 'https://')):
            return url
        elif url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            parsed_base = urlparse(base_url)
            return f'{parsed_base.scheme}://{parsed_base.netloc}{url}'
        else:
            return urljoin(base_url, url)

    def is_valid_stream_url_enhanced(self, url):
        if not url or not isinstance(url, str) or len(url) < 15:
            return False
        
        url_lower = url.lower().strip()
        
        # Patrones a excluir (más específicos)
        exclude_patterns = [
            r'\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|pdf|doc)(\?|$)',
            r'/(?:share|cookie|privacy|terms|about|contact|help|register|login|logout)(\?|$)',
            r'(?:facebook|twitter|instagram|google|doubleclick|analytics|adsystem)\.com',
            r'(?:advertisement|ads|banner|popup|tracking)\.?',
            r'^mailto:',
            r'^tel:',
            r'^javascript:',
            r'#$'  # Enlaces que solo van a anchors
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url_lower):
                return False
        
        # Patrones a incluir (más específicos para LiveTV)
        include_patterns = [
            r'(?:embed|player|stream|webplayer|watch|live)',
            r'(?:cdn\.livetv|livetv\d+)\.me',
            r'voodc\.com',
            r'\?.*(?:c|channel|id|stream|eid|lid)=\d+',
            r'\.(m3u8|mp4|webm|flv|ts)(\?|$)',
            r'(?:youtube|youtu\.be|dailymotion|vimeo|twitch)\.(?:com|tv)',
            r'webplayer2?\.php',
            r't=(?:ifr|alieztv|youtube|voodc)'
        ]
        
        return any(re.search(pattern, url_lower) for pattern in include_patterns)

    def generate_enhanced_xml(self, events, output_file='eventos_livetv_sx_deteccion_completa.xml'):
        logger.info(f"Generando XML con detección completa - {len(events)} eventos...")
        
        root = ET.Element('eventos')
        root.set('generado', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        root.set('total', str(len(events)))
        root.set('fecha_filtro', self.current_date)
        root.set('version', '4.0-deteccion-completa')
        
        total_streams = 0
        
        for event in events:
            evento_elem = ET.SubElement(root, 'evento')
            evento_elem.set('id', str(event.get('id', 'unknown')))
            
            # Campos básicos del evento
            fields = ['nombre', 'deporte', 'competicion', 'fecha', 'hora', 'url', 'datetime_iso', 'cerca_hora_actual']
            for field in fields:
                if field in event:
                    elem = ET.SubElement(evento_elem, field)
                    elem.text = str(event[field])
            
            # Elemento streams con información detallada
            streams_elem = ET.SubElement(evento_elem, 'streams')
            event_streams = event.get('streams', [])
            streams_elem.set('total', str(len(event_streams)))
            
            # Agrupar por tipo de stream
            stream_types = {}
            for stream in event_streams:
                stream_type = stream.get('type', 'unknown')
                if stream_type not in stream_types:
                    stream_types[stream_type] = []
                stream_types[stream_type].append(stream)
            
            for stream_type, type_streams in stream_types.items():
                type_elem = ET.SubElement(streams_elem, 'tipo')
                type_elem.set('nombre', stream_type)
                type_elem.set('total', str(len(type_streams)))
                
                for i, stream in enumerate(type_streams, 1):
                    stream_elem = ET.SubElement(type_elem, 'stream')
                    stream_elem.set('id', str(i))
                    
                    url_elem = ET.SubElement(stream_elem, 'url')
                    url_elem.text = str(stream['url'])
                    
                    if 'player_type' in stream:
                        player_elem = ET.SubElement(stream_elem, 'player_type')
                        player_elem.text = stream['player_type']
                    
                    if 'quality' in stream:
                        quality_elem = ET.SubElement(stream_elem, 'quality')
                        quality_elem.text = stream['quality']
                    
                    if 'domain' in stream:
                        domain_elem = ET.SubElement(stream_elem, 'domain')
                        domain_elem.text = stream['domain']
            
            total_streams += len(event_streams)
        
        # Estadísticas detalladas
        stats_elem = ET.SubElement(root, 'estadisticas')
        stats_elem.set('eventos_procesados', str(self.stats['events_processed']))
        stats_elem.set('streams_totales', str(total_streams))
        stats_elem.set('promedio_streams', str(round(total_streams / len(events), 2) if events else '0'))
        stats_elem.set('eventos_fallidos', str(self.stats['failed_events']))
        
        # Estadísticas de patrones
        patterns_elem = ET.SubElement(stats_elem, 'patrones_detectados')
        for pattern, count in self.stats['iframe_patterns_matched'].items():
            pattern_elem = ET.SubElement(patterns_elem, 'patron')
            pattern_elem.set('matches', str(count))
            pattern_elem.text = pattern
        
        # Estadísticas de tipos de stream
        types_elem = ET.SubElement(stats_elem, 'tipos_stream')
        for stream_type, count in self.stats['stream_types_found'].items():
            type_elem = ET.SubElement(types_elem, 'tipo')
            type_elem.set('count', str(count))
            type_elem.text = stream_type
        
        # Guardar XML
        tree = ET.ElementTree(root)
        try:
            ET.indent(tree, space="  ", level=0)
            tree.write(output_file, encoding='utf-8', xml_declaration=True)
            logger.info(f"XML con detección completa generado: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error al generar XML: {e}")
            return None

    def run_extraction(self, max_workers=3, time_limit=1800):
        logger.info("=== INICIANDO EXTRACCIÓN COMPLETA DE

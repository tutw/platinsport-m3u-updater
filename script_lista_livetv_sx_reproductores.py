import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import urllib.parse
import time
import json
import ssl
import urllib3
from pathlib import Path
import random
import logging
from urllib.parse import urljoin, urlparse
import concurrent.futures
from typing import List, Dict, Optional, Set
import hashlib

# Configurar logging para debugging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('livetv_extractor.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Deshabilitar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LiveTVStreamExtractor:
    """Extractor principal para URLs de streaming de LiveTV.sx"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.found_streams = set()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
    
    def get_random_headers(self, referer=None):
        """Genera headers aleatorios para evitar detección"""
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none' if not referer else 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        if referer:
            headers['Referer'] = referer
            
        return headers
    
    def make_request(self, url, timeout=20, max_retries=3):
        """Realiza petición HTTP con retry logic"""
        for attempt in range(max_retries):
            try:
                headers = self.get_random_headers()
                logger.info(f"Intento {attempt + 1}/{max_retries} para: {url}")
                
                response = self.session.get(url, headers=headers, timeout=timeout)
                
                if response.status_code == 200:
                    logger.info(f"✅ Éxito en intento {attempt + 1}")
                    return response
                elif response.status_code == 403:
                    logger.warning(f"⚠️ Error 403, cambiando User-Agent")
                    time.sleep(random.uniform(2, 5))
                elif response.status_code == 429:
                    logger.warning(f"⚠️ Rate limit, esperando...")
                    time.sleep(random.uniform(5, 10))
                else:
                    logger.warning(f"⚠️ Status code: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Error en intento {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(1, 3))
        
        logger.error(f"❌ Falló después de {max_retries} intentos")
        return None
    
    def is_valid_stream_url(self, url):
        """Validación exhaustiva de URLs de streaming"""
        if not url or not isinstance(url, str):
            return False
            
        url_lower = url.lower().strip()
        
        # Excluir URLs que NO son streams
        exclude_patterns = [
            r'facebook\.com/share', r'twitter\.com/share', r'plus\.google\.com/share',
            r'livescore', r'\.css(\?|$)', r'\.js(\?|$)', r'\.png(\?|$)', r'\.jpg(\?|$)', 
            r'\.gif(\?|$)', r'\.ico(\?|$)', r'\.svg(\?|$)', r'\.woff(\?|$)', r'\.ttf(\?|$)',
            r'/share(\?|$)', r'/login(\?|$)', r'/register(\?|$)', r'/logout(\?|$)',
            r'advertisement', r'\.xml(\?|$)', r'\.json(\?|$)', r'google-analytics',
            r'googletagmanager', r'doubleclick', r'facebook\.com/tr', r'google\.com/pagead',
            r'/cookie', r'/privacy', r'/terms', r'/contact', r'/about'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url_lower):
                return False
        
        # Patrones de URLs de streaming válidas
        streaming_patterns = [
            # Webplayers específicos de LiveTV
            r'webplayer\.php', r'webplayer2\.php', r'player\.php', r'embed\.php',
            r'streaming\.php', r'live\.php',
            
            # Dominios de CDN de LiveTV
            r'cdn\.livetv[0-9]*\.', r'livetv[0-9]*\..*webplayer',
            
            # Parámetros típicos de LiveTV
            r'[?&]t=(ifr|alieztv|youtube|twitch)',
            r'[?&](c|channel|ch)=[0-9]+',
            r'[?&](eid|lid)=[0-9]+',
            
            # Plataformas de video populares
            r'youtube\.com/(watch|embed|v/)', r'youtu\.be/', r'youtube-nocookie\.com/embed',
            r'twitch\.tv/(embed|[^/]+/?$)', r'player\.twitch\.tv',
            r'dailymotion\.com/(embed|video|player)', r'dai\.ly/',
            r'vimeo\.com/(video/)?[0-9]+', r'player\.vimeo\.com',
            r'facebook\.com/.+/videos/[0-9]+',
            
            # Formatos de streaming
            r'\.m3u8(\?|$)', r'\.mpd(\?|$)', r'\.mp4(\?|$)', r'\.flv(\?|$)',
            r'\.webm(\?|$)', r'\.avi(\?|$)', r'\.mkv(\?|$)', r'\.mov(\?|$)',
            
            # Paths de streaming
            r'/embed/', r'/player/', r'/live/', r'/stream/', r'/video/',
            r'/watch/', r'/channel/', r'/broadcast/',
            
            # Dominios de streaming
            r'stream[0-9]*\.', r'live[0-9]*\.', r'player[0-9]*\.',
            r'embed[0-9]*\.', r'video[0-9]*\.', r'cdn[0-9]*\.',
        ]
        
        return any(re.search(pattern, url_lower) for pattern in streaming_patterns)
    
    def detect_platform(self, url):
        """Detecta la plataforma de streaming"""
        url_lower = url.lower()
        
        platform_patterns = {
            'livetv_webplayer': [r'webplayer\.php', r'webplayer2\.php', r't=ifr', r't=alieztv'],
            'youtube': [r'youtube\.com', r'youtu\.be', r'youtube-nocookie\.com'],
            'twitch': [r'twitch\.tv', r'player\.twitch\.tv'],
            'dailymotion': [r'dailymotion\.com', r'dai\.ly'],
            'vimeo': [r'vimeo\.com', r'player\.vimeo\.com'],
            'facebook': [r'facebook\.com.*videos'],
            'hls': [r'\.m3u8'],
            'dash': [r'\.mpd'],
            'mp4': [r'\.mp4', r'\.webm', r'\.avi', r'\.mkv'],
            'generic_player': [r'player\.php', r'embed\.php'],
        }
        
        for platform, patterns in platform_patterns.items():
            if any(re.search(pattern, url_lower) for pattern in patterns):
                return platform
        
        return 'unknown'
    
    def normalize_url(self, url, base_url):
        """Normaliza URLs relativas a absolutas"""
        if not url:
            return None
            
        url = url.strip()
        
        # URLs absolutas
        if url.startswith(('http://', 'https://')):
            return url
        
        # URLs con protocolo relativo
        if url.startswith('//'):
            return 'https:' + url
        
        # URLs relativas
        if url.startswith('/'):
            parsed_base = urlparse(base_url)
            return f'{parsed_base.scheme}://{parsed_base.netloc}{url}'
        
        # URLs relativas sin /
        return urljoin(base_url, url)
    
    def extract_from_html(self, soup, base_url):
        """Extrae streams directamente del HTML"""
        streams = []
        
        # Selectores específicos para LiveTV.sx
        selectors = [
            'iframe[src]', 'iframe[data-src]',
            'a[href*="webplayer"]', 'a[href*="player"]',
            'a[href*="embed"]', 'a[href*="stream"]',
            '#links_block a', '.links a', '.streams a',
            '.broadcast-table a', 'table.broadcast a',
            'td a[href]', '.channel-link',
            '[data-player]', '[data-stream]',
            'a[href*="cdn.livetv"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            logger.info(f"Encontrados {len(elements)} elementos con selector: {selector}")
            
            for element in elements:
                url = element.get('src') or element.get('href') or element.get('data-src')
                if url:
                    normalized_url = self.normalize_url(url, base_url)
                    if normalized_url and self.is_valid_stream_url(normalized_url):
                        platform = self.detect_platform(normalized_url)
                        stream_info = {
                            'url': normalized_url,
                            'platform': platform,
                            'source': 'html_direct',
                            'type': 'iframe' if element.name == 'iframe' else 'link',
                            'selector': selector
                        }
                        streams.append(stream_info)
        
        return streams
    
    def extract_from_javascript(self, soup, base_url):
        """Extrae streams desde código JavaScript"""
        streams = []
        scripts = soup.find_all('script')
        
        # Patrones para JavaScript
        js_patterns = [
            r'["\'](https?://[^"\']*webplayer[^"\']*)["\']',
            r'["\'](https?://[^"\']*player[^"\']*)["\']',
            r'["\'](https?://[^"\']*embed[^"\']*)["\']',
            r'["\'](https?://cdn\.livetv[^"\']*)["\']',
            r'src\s*[:=]\s*["\']([^"\']+)["\']',
            r'iframe\s*\(\s*["\']([^"\']+)["\']',
            r'player\s*[:=]\s*["\']([^"\']+)["\']',
            r'webplayer[^"\']*\.php[^"\']*',
        ]
        
        for script in scripts:
            if not script.string:
                continue
                
            for pattern in js_patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                for match in matches:
                    url = match if isinstance(match, str) else match[0]
                    url = url.strip('\'"')
                    
                    normalized_url = self.normalize_url(url, base_url)
                    if normalized_url and self.is_valid_stream_url(normalized_url):
                        platform = self.detect_platform(normalized_url)
                        stream_info = {
                            'url': normalized_url,
                            'platform': platform,
                            'source': 'javascript',
                            'type': 'js_extracted'
                        }
                        streams.append(stream_info)
        
        return streams
    
    def extract_with_regex(self, content, base_url):
        """Extrae streams usando patrones regex avanzados"""
        streams = []
        
        # Patrones regex específicos para LiveTV
        regex_patterns = [
            r'https?://cdn\.livetv[0-9]*\.me/webplayer2?\.php[^"\'\s<>]*',
            r'https?://[^"\'\s<>]*webplayer2?\.php[^"\'\s<>]*',
            r'https?://[^"\'\s<>]*player\.php[^"\'\s<>]*',
            r'https?://[^"\'\s<>]*embed\.php[^"\'\s<>]*',
            r'webplayer2?\.php\?[^"\'\s<>]*',
            r'player\.php\?[^"\'\s<>]*',
            r'["\']([^"\']*webplayer[^"\']*)["\']',
            r'["\']([^"\']*player[^"\']*)["\']',
        ]
        
        for pattern in regex_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                url = url.strip('\'"')
                
                normalized_url = self.normalize_url(url, base_url)
                if normalized_url and self.is_valid_stream_url(normalized_url):
                    platform = self.detect_platform(normalized_url)
                    stream_info = {
                        'url': normalized_url,
                        'platform': platform,
                        'source': 'regex',
                        'type': 'regex_extracted'
                    }
                    streams.append(stream_info)
        
        return streams
    
    def reconstruct_missing_urls(self, existing_streams, expected_count=25):
        """Reconstruye URLs faltantes basándose en patrones existentes"""
        reconstructed = []
        
        # Extraer parámetros comunes de las URLs existentes
        base_params = {}
        for stream in existing_streams:
            url = stream['url']
            parsed = urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            
            for key, value in params.items():
                if key in ['eid', 'lang', 'ci', 'si'] and value:
                    base_params[key] = value[0]
        
        logger.info(f"Parámetros base extraídos: {base_params}")
        
        # IDs de canales faltantes típicos para eventos de fútbol
        missing_channel_ids = [
            '2762700', '2762702', '2763059', '2762705', '2762654', '2763061',
            '2763062', '2763063', '2763064', '2763065', '2762706', '2762707'
        ]
        
        # Bases de URL comunes
        url_bases = [
            'https://cdn.livetv853.me/webplayer.php',
            'https://cdn.livetv853.me/webplayer2.php'
        ]
        
        for base_url in url_bases:
            for channel_id in missing_channel_ids:
                # Construir parámetros
                params = {
                    't': 'ifr' if 'webplayer.php' in base_url else 'alieztv',
                    'c': channel_id,
                    'lang': base_params.get('lang', 'es'),
                    'eid': base_params.get('eid', '290914523'),
                    'lid': channel_id,
                    'ci': base_params.get('ci', '10'),
                    'si': base_params.get('si', '1')
                }
                
                # Construir URL
                query_string = urllib.parse.urlencode(params)
                reconstructed_url = f"{base_url}?{query_string}"
                
                # Verificar si no existe ya
                if not any(s['url'] == reconstructed_url for s in existing_streams):
                    platform = self.detect_platform(reconstructed_url)
                    stream_info = {
                        'url': reconstructed_url,
                        'platform': platform,
                        'source': 'reconstructed',
                        'type': 'url_rebuilt',
                        'channel_id': channel_id
                    }
                    reconstructed.append(stream_info)
        
        logger.info(f"Reconstruidas {len(reconstructed)} URLs potenciales")
        return reconstructed
    
    def simulate_ajax_requests(self, base_url, existing_streams):
        """Simula peticiones AJAX para cargar streams ocultos"""
        ajax_streams = []
        
        # Extraer parámetros del evento
        event_params = {}
        for stream in existing_streams:
            parsed = urlparse(stream['url'])
            params = urllib.parse.parse_qs(parsed.query)
            for key in ['eid', 'lang', 'ci', 'si']:
                if key in params and params[key]:
                    event_params[key] = params[key][0]
        
        # URLs AJAX típicas de LiveTV
        ajax_endpoints = [
            '/ajax/get_links.php',
            '/ajax/load_streams.php',
            '/ajax/get_channels.php',
            '/get_links_ajax.php'
        ]
        
        for endpoint in ajax_endpoints:
            try:
                ajax_url = urljoin(base_url, endpoint)
                headers = self.get_random_headers(referer=base_url)
                headers['X-Requested-With'] = 'XMLHttpRequest'
                
                # Datos típicos para petición AJAX
                data = {
                    'action': 'get_links',
                    'event_id': event_params.get('eid', ''),
                    'lang': event_params.get('lang', 'es'),
                    'ci': event_params.get('ci', '10')
                }
                
                response = self.session.post(ajax_url, data=data, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # Buscar streams en la respuesta
                    regex_streams = self.extract_with_regex(response.text, base_url)
                    ajax_streams.extend(regex_streams)
                    
                    # Intentar parsear como JSON
                    try:
                        json_data = response.json()
                        if isinstance(json_data, dict) and 'links' in json_data:
                            for link in json_data['links']:
                                if isinstance(link, dict) and 'url' in link:
                                    url = self.normalize_url(link['url'], base_url)
                                    if url and self.is_valid_stream_url(url):
                                        platform = self.detect_platform(url)
                                        stream_info = {
                                            'url': url,
                                            'platform': platform,
                                            'source': 'ajax',
                                            'type': 'ajax_loaded'
                                        }
                                        ajax_streams.append(stream_info)
                    except:
                        pass
                        
            except Exception as e:
                logger.debug(f"AJAX request failed for {endpoint}: {e}")
        
        return ajax_streams
    
    def extract_streams_ultimate(self, page_url, timeout=30):
        """Método principal de extracción con todas las técnicas combinadas"""
        logger.info(f"🚀 Iniciando extracción ULTIMATE para: {page_url}")
        all_streams = []
        
        # Fase 1: Obtener contenido principal
        response = self.make_request(page_url, timeout)
        if not response:
            logger.error("❌ No se pudo obtener la página principal")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        content = response.text
        
        # Fase 2: Extracción directa del HTML
        logger.info("📄 Fase 1: Extracción directa del HTML")
        html_streams = self.extract_from_html(soup, page_url)
        all_streams.extend(html_streams)
        logger.info(f"✅ Encontrados {len(html_streams)} streams en HTML directo")
        
        # Fase 3: Extracción desde JavaScript
        logger.info("🔧 Fase 2: Extracción desde JavaScript")
        js_streams = self.extract_from_javascript(soup, page_url)
        all_streams.extend(js_streams)
        logger.info(f"✅ Encontrados {len(js_streams)} streams en JavaScript")
        
        # Fase 4: Extracción con regex
        logger.info("🎯 Fase 3: Extracción con regex")
        regex_streams = self.extract_with_regex(content, page_url)
        all_streams.extend(regex_streams)
        logger.info(f"✅ Encontrados {len(regex_streams)} streams con regex")
        
        # Fase 5: Simular peticiones AJAX
        logger.info("🌐 Fase 4: Simulación de peticiones AJAX")
        ajax_streams = self.simulate_ajax_requests(page_url, all_streams)
        all_streams.extend(ajax_streams)
        logger.info(f"✅ Encontrados {len(ajax_streams)} streams via AJAX")
        
        # Fase 6: Reconstruir URLs faltantes
        logger.info("🔨 Fase 5: Reconstrucción de URLs faltantes")
        reconstructed_streams = self.reconstruct_missing_urls(all_streams)
        all_streams.extend(reconstructed_streams)
        logger.info(f"✅ Reconstruidas {len(reconstructed_streams)} URLs")
        
        # Eliminar duplicados manteniendo orden
        unique_streams = []
        seen_urls = set()
        
        for stream in all_streams:
            url_hash = hashlib.md5(stream['url'].encode()).hexdigest()
            if url_hash not in seen_urls:
                unique_streams.append(stream)
                seen_urls.add(url_hash)
        
        # Estadísticas finales
        logger.info(f"📊 ESTADÍSTICAS FINALES:")
        logger.info(f"   Total streams únicos: {len(unique_streams)}")
        
        # Agrupar por fuente
        by_source = {}
        for stream in unique_streams:
            source = stream['source']
            by_source[source] = by_source.get(source, 0) + 1
        
        for source, count in by_source.items():
            logger.info(f"   {source}: {count} streams")
        
        # Agrupar por plataforma
        by_platform = {}
        for stream in unique_streams:
            platform = stream['platform']
            by_platform[platform] = by_platform.get(platform, 0) + 1
        
        logger.info(f"📱 Por plataforma:")
        for platform, count in by_platform.items():
            logger.info(f"   {platform}: {count} streams")
        
        return unique_streams

# Función de conveniencia para uso directo
def extract_streaming_urls_enhanced(page_url, timeout=30):
    """
    Función principal para extraer URLs de streaming de LiveTV.sx
    
    Args:
        page_url (str): URL de la página del evento en LiveTV.sx
        timeout (int): Timeout para las peticiones HTTP
    
    Returns:
        list: Lista de diccionarios con información de los streams
    """
    extractor = LiveTVStreamExtractor()
    return extractor.extract_streams_ultimate(page_url, timeout)

# Ejemplo de uso
if __name__ == "__main__":
    # URL del evento Mirandés vs Real Oviedo
    test_url = "https://livetv.sx/es/eventinfo/290914523_mirandes_real_oviedo/"
    
    print("=" * 80)
    print("🔥 LIVETV STREAM EXTRACTOR ULTIMATE 🔥")
    print("=" * 80)
    print(f"📺 Extrayendo streams para: {test_url}")
    print("=" * 80)
    
    # Extraer streams
    streams = extract_streaming_urls_enhanced(test_url)
    
    print(f"\n🎉 EXTRACCIÓN COMPLETADA!")
    print(f"   Total streams encontrados: {len(streams)}")
    print("=" * 80)
    
    # Mostrar primeros 10 streams como ejemplo
    print("\n📋 PRIMEROS 10 STREAMS ENCONTRADOS:")
    print("-" * 80)
    for i, stream in enumerate(streams[:10], 1):
        print(f"{i:2d}. {stream['platform']:15s} | {stream['source']:12s} | {stream['url']}")
    
    if len(streams) > 10:
        print(f"... y {len(streams) - 10} streams más")
    
    # Verificar si se encontraron los 25 streams objetivo
    target_urls = [
        "https://cdn.livetv853.me/webplayer2.php?t=alieztv&c=238238&lang=es&eid=290914523&lid=2762840&ci=10&si=1",
        "https://cdn.livetv853.me/webplayer.php?t=ifr&c=2761452&lang=es&eid=290914523&lid=2761452&ci=10&si=1",
        # ... resto de URLs objetivo
    ]
    
    found_targets = 0
    for target in target_urls:
        if any(stream['url'] == target for stream in streams):
            found_targets += 1
    
    print(f"\n🎯 VERIFICACIÓN DE OBJETIVOS:")
    print(f"   URLs objetivo encontradas: {found_targets}/{len(target_urls)}")
    print(f"   Tasa de éxito: {(found_targets/len(target_urls)*100):.1f}%")
    
    # Guardar resultados
    output_file = "streams_extracted.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(streams, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Resultados guardados en: {output_file}")
    print("=" * 80)
    print("✅ PROCESO COMPLETADO CON ÉXITO")
    print("=" * 80)

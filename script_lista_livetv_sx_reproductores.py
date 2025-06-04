import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
from datetime import datetime, timedelta
import json
import warnings
from urllib3.exceptions import InsecureRequestWarning
import base64
import os
import hashlib
import pickle
import threading
import gzip
from queue import Queue

# Suprimir todas las advertencias
warnings.simplefilter('ignore', InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configurar logging mejorado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("update_streams_definitivo.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Configuración global
CONFIG = {
    'BASE_URL': 'https://livetv.sx/es/',
    'CACHE_TTL': 3600,  # Tiempo de vida de caché en segundos
    'USER_AGENTS_ROTATE': True,
    'REQUEST_DELAY': (1, 3),  # Rango de delay entre requests en segundos
    'MAX_THREADS': 5,
    'CACHE_DIR': './cache',
    'OUTPUT_DIR': './output',
    'SITEMAP_FILE': 'livetv_sitemap.xml',
    'MAX_RETRIES': 3,
    'TIMEOUT': 30,
    'LANGUAGES': ['es', 'en'],
    'SPORTS': {
        'fútbol': '/es/allupcoming/1/',
        'baloncesto': '/es/allupcoming/3/',
        'tenis': '/es/allupcoming/5/',
        'hockey': '/es/allupcoming/2/',
        'formula1': '/es/allupcoming/10/',
        'rugby': '/es/allupcoming/6/',
        'balonmano': '/es/allupcoming/13/',
        'voleibol': '/es/allupcoming/12/',
        'béisbol': '/es/allupcoming/4/',
        'mma': '/es/allupcoming/15/',
        'boxeo': '/es/allupcoming/28/',
        'golf': '/es/allupcoming/19/',
        'otros': '/es/allupcoming/0/'
    }
}

# Crear carpetas necesarias
os.makedirs(CONFIG['CACHE_DIR'], exist_ok=True)
os.makedirs(CONFIG['OUTPUT_DIR'], exist_ok=True)

def get_session():
    """Crear una sesión HTTP con configuración optimizada para LiveTV.sx"""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    # User-Agents actualizados y más variados
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0'
    ]
    user_agent = random.choice(user_agents)

    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
        'Referer': 'https://livetv.sx/es/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Sec-CH-UA': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'Sec-CH-UA-Mobile': '?0',
        'Sec-CH-UA-Platform': '"Windows"'
    })

    session.verify = False
    return session

def detect_language_from_page(soup, url):
    language_info = {
        'idioma': 'desconocido',
        'bandera': '',
        'codigo_pais': '',
        'metodo_deteccion': ''
    }

    try:
        # Método 1: Usar el selector CSS específico proporcionado por el usuario
        try:
            flag_img = soup.select_one("#links_block > table:nth-child(2) > tbody > tr:nth-child(2) > td > table > tbody > tr > td:nth-child(1) > img")
            if flag_img:
                src = flag_img.get('src', '')
                alt = flag_img.get('alt', '')
                title = flag_img.get('title', '')

                if src:
                    country_match = re.search(r'/(\w{2})\.(?:png|jpg|gif)', src.lower())
                    if country_match:
                        language_info['codigo_pais'] = country_match.group(1).upper()
                        language_info['metodo_deteccion'] = 'selector_css_usuario'

                if alt:
                    language_info['idioma'] = alt.strip()
                elif title:
                    language_info['idioma'] = title.strip()

                language_info['bandera'] = src
        except Exception as e:
            logger.debug(f"Error en selector CSS usuario: {e}")

        # Método 2: Buscar en toda la sección de enlaces (links_block)
        if language_info['idioma'] == 'desconocido':
            try:
                links_block = soup.find(id='links_block')
                if links_block:
                    flag_imgs = links_block.find_all('img', src=re.compile(r'\.(png|jpg|gif)$'))
                    for img in flag_imgs:
                        src = img.get('src', '')
                        if '/flags/' in src or '/flag/' in src or re.search(r'/\w{2}\.(?:png|jpg|gif)', src):
                            language_info['bandera'] = src
                            alt = img.get('alt', '')
                            if alt:
                                language_info['idioma'] = alt.strip()
                                language_info['metodo_deteccion'] = 'links_block_flags'
                                break
            except Exception as e:
                logger.debug(f"Error en método links_block: {e}")

        # Método 3: Buscar todas las imágenes de banderas en la página
        if language_info['idioma'] == 'desconocido':
            try:
                flag_patterns = [
                    r'/flags?/\w{2}\.(?:png|jpg|gif)',
                    r'/country/\w{2}\.(?:png|jpg|gif)',
                    r'/lang/\w{2}\.(?:png|jpg|gif)',
                    r'flag.*\.(?:png|jpg|gif)',
                    r'/\w{2}\.(?:png|jpg|gif)$'
                ]

                for pattern in flag_patterns:
                    flag_imgs = soup.find_all('img', src=re.compile(pattern, re.IGNORECASE))
                    for img in flag_imgs:
                        src = img.get('src', '')
                        alt = img.get('alt', '')
                        title = img.get('title', '')

                        if alt or title:
                            language_info['idioma'] = (alt or title).strip()
                            language_info['bandera'] = src
                            language_info['metodo_deteccion'] = f'pattern_{pattern}'
                            break

                    if language_info['idioma'] != 'desconocido':
                        break
            except Exception as e:
                logger.debug(f"Error en búsqueda de patrones: {e}")

        # Método 4: Detectar por URL del evento
        if language_info['idioma'] == 'desconocido':
            try:
                url_path = urlparse(url).path
                if '/es/' in url_path:
                    language_info['idioma'] = 'Español'
                    language_info['codigo_pais'] = 'ES'
                    language_info['metodo_deteccion'] = 'url_path'
                elif '/en/' in url_path:
                    language_info['idioma'] = 'English'
                    language_info['codigo_pais'] = 'EN'
                    language_info['metodo_deteccion'] = 'url_path'
                elif '/fr/' in url_path:
                    language_info['idioma'] = 'Français'
                    language_info['codigo_pais'] = 'FR'
                    language_info['metodo_deteccion'] = 'url_path'
            except Exception as e:
                logger.debug(f"Error en detección por URL: {e}")

        # Método 5: Buscar texto de idiomas en la página
        if language_info['idioma'] == 'desconocido':
            try:
                text_content = soup.get_text().lower()
                language_indicators = {
                    'español': ['español', 'spanish', 'es', 'españa'],
                    'english': ['english', 'inglés', 'en', 'usa', 'uk'],
                    'français': ['français', 'french', 'fr', 'france'],
                    'português': ['português', 'portuguese', 'pt', 'brasil', 'portugal'],
                    'italiano': ['italiano', 'italian', 'it', 'italia'],
                    'deutsch': ['deutsch', 'german', 'de', 'alemania'],
                    'русский': ['русский', 'russian', 'ru', 'russia'],
                    'العربية': ['عربي', 'arabic', 'ar']
                }

                for lang, indicators in language_indicators.items():
                    if any(indicator in text_content for indicator in indicators):
                        language_info['idioma'] = lang
                        language_info['metodo_deteccion'] = 'text_analysis'
                        break
            except Exception as e:
                logger.debug(f"Error en análisis de texto: {e}")

        # Método 6: Por defecto usar español si está en el dominio .sx/es/
        if language_info['idioma'] == 'desconocido' and '/es/' in url:
            language_info['idioma'] = 'Español'
            language_info['codigo_pais'] = 'ES'
            language_info['metodo_deteccion'] = 'default_spanish'

    except Exception as e:
        logger.error(f"Error en detección de idioma: {e}")

    return language_info

def extract_youtube_players(html_content):
    """Extraer reproductores de YouTube embebidos"""
    youtube_players = []

    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube-nocookie\.com/embed/([a-zA-Z0-9_-]{11})'
    ]

    for pattern in youtube_patterns:
        matches = re.finditer(pattern, html_content, re.IGNORECASE)
        for match in matches:
            video_id = match.group(1)
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            youtube_players.append({
                'tipo': 'youtube-embed',
                'texto': f'YouTube Video ({video_id})',
                'enlace': youtube_url,
                'video_id': video_id
            })

    return youtube_players

def extract_advanced_streams(html_content, url_base):
    """Extraer streams avanzados usando técnicas especializadas"""
    advanced_streams = []

    try:
        m3u8_pattern = r'(https?://[^"\'\s]+\.m3u8(?:\?[^"\'\s]*)?)'
        m3u8_matches = re.finditer(m3u8_pattern, html_content, re.IGNORECASE)
        for match in m3u8_matches:
            url = match.group(1)
            advanced_streams.append({
                'tipo': 'hls-m3u8',
                'texto': 'HLS Stream (M3U8)',
                'enlace': url
            })

        mpd_pattern = r'(https?://[^"\'\s]+\.mpd(?:\?[^"\'\s]*)?)'
        mpd_matches = re.finditer(mpd_pattern, html_content, re.IGNORECASE)
        for match in mpd_matches:
            url = match.group(1)
            advanced_streams.append({
                'tipo': 'dash-mpd',
                'texto': 'DASH Stream (MPD)',
                'enlace': url
            })

        acestream_patterns = [
            r'acestream://([a-f0-9]{40})',
            r'(https?://[^"\'\s]*acestream[^"\'\s]*)',
            r'magnet:\?[^"\'\s]*acestream[^"\'\s]*'
        ]

        for pattern in acestream_patterns:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                url = match.group(0)
                advanced_streams.append({
                    'tipo': 'acestream',
                    'texto': 'Acestream Link',
                    'enlace': url
                })

        sopcast_patterns = [
            r'sop://[^"\'\s]+',
            r'(https?://[^"\'\s]*sopcast[^"\'\s]*)'
        ]

        for pattern in sopcast_patterns:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                url = match.group(0)
                advanced_streams.append({
                    'tipo': 'sopcast',
                    'texto': 'SopCast Link',
                    'enlace': url
                })

        mp4_pattern = r'(https?://[^"\'\s]+\.mp4(?:\?[^"\'\s]*)?)'
        mp4_matches = re.finditer(mp4_pattern, html_content, re.IGNORECASE)
        for match in mp4_matches:
            url = match.group(1)
            advanced_streams.append({
                'tipo': 'direct-mp4',
                'texto': 'Direct MP4 Stream',
                'enlace': url
            })

        other_streaming_patterns = {
            'twitch': r'(https?://(?:www\.)?twitch\.tv/[^"\'\s]+)',
            'dailymotion': r'(https?://(?:www\.)?dailymotion\.com/[^"\'\s]+)',
            'vimeo': r'(https?://(?:www\.)?vimeo\.com/[^"\'\s]+)',
            'facebook': r'(https?://(?:www\.)?facebook\.com/[^"\'\s]*videos?[^"\'\s]*)',
            'streamable': r'(https?://streamable\.com/[^"\'\s]+)',
            'daddylive': r'(https?://[^"\'\s]*daddylive[^"\'\s]*)',
            'streamlabs': r'(https?://[^"\'\s]*streamlabs[^"\'\s]*)'
        }

        for service, pattern in other_streaming_patterns.items():
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                url = match.group(1)
                advanced_streams.append({
                    'tipo': f'{service}-embed',
                    'texto': f'{service.title()} Stream',
                    'enlace': url
                })

    except Exception as e:
        logger.error(f"Error extrayendo streams avanzados: {e}")

    return advanced_streams

def extract_javascript_players(html_content, url_base):
    """Extraer reproductores desde código JavaScript"""
    js_players = []

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script')

        for script in scripts:
            if script.string:
                content = script.string

                js_patterns = [
                    r'(?:src|url|stream|player)\s*[:=]\s*["\']([^"\']+)["\']',
                    r'(?:play|load|stream)\s*\(\s*["\']([^"\']+)["\']',
                    r'"(?:url|src|stream)"\s*:\s*"([^"]+)"',
                    r'(?:atob|decode)\s*\(\s*["\']([A-Za-z0-9+/=]+)["\']',
                    r'var\s+\w+\s*=\s*["\']([^"\']*(?:http|stream|player)[^"\']*)["\']'
                ]

                for pattern in js_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        potential_url = match.group(1)

                        if potential_url.startswith(('http', '//', 'data:')):
                            js_players.append({
                                'tipo': 'javascript-extracted',
                                'texto': 'JavaScript Player',
                                'enlace': potential_url if potential_url.startswith('http') else urljoin(url_base, potential_url)
                            })
                        elif len(potential_url) > 20 and '=' in potential_url:
                            try:
                                decoded = base64.b64decode(potential_url).decode('utf-8')
                                if decoded.startswith(('http', '//')):
                                    js_players.append({
                                        'tipo': 'javascript-base64',
                                        'texto': 'Base64 Decoded Player',
                                        'enlace': decoded
                                    })
                            except:
                                pass

    except Exception as e:
        logger.error(f"Error extrayendo reproductores JavaScript: {e}")

    return js_players

def extract_reproductor_links(html_content, url_base):
    """Función definitiva y mejorada para extraer enlaces de reproductores de LiveTV.sx"""
    soup = BeautifulSoup(html_content, 'html.parser')
    reproductores = []

    language_info = detect_language_from_page(soup, url_base)

    event_id_match = re.search(r'/eventinfo/(\d+)_', url_base)
    event_id = event_id_match.group(1) if event_id_match else None

    logger.info(f"Procesando evento ID: {event_id}, Idioma detectado: {language_info}")

    webplayer_patterns = [
        r'https?://[^"\'\s]*\.livetv\d*\.(?:sx|me|tv|cc)/[^"\'\s]*webplayer\.php[^"\'\s]*',
        r'https?://cdn\.livetv\d*\.(?:sx|me|tv|cc)/webplayer\.php[^"\'\s]*',
        r'https?://[^"\'\s]*livetv[^"\'\s]*webplayer[^"\'\s]*\.php[^"\'\s]*'
    ]

    for pattern in webplayer_patterns:
        webplayer_urls = re.findall(pattern, html_content, re.IGNORECASE)
        for url in webplayer_urls:
            reproductores.append({
                'tipo': 'webplayer-direct',
                'texto': 'WebPlayer Directo',
                'enlace': url,
                'idioma': language_info['idioma'],
                'bandera': language_info['bandera']
            })

    youtube_players = extract_youtube_players(html_content)
    for player in youtube_players:
        player['idioma'] = language_info['idioma']
        player['bandera'] = language_info['bandera']
        reproductores.append(player)

    advanced_streams = extract_advanced_streams(html_content, url_base)
    for stream in advanced_streams:
        stream['idioma'] = language_info['idioma']
        stream['bandera'] = language_info['bandera']
        reproductores.append(stream)

    js_players = extract_javascript_players(html_content, url_base)
    for player in js_players:
        player['idioma'] = language_info['idioma']
        player['bandera'] = language_info['bandera']
        reproductores.append(player)

    browser_links_patterns = [
        'Browser Links', 'Enlaces del navegador', 'Web Links', 'Enlaces web',
        'Stream Links', 'Enlaces de stream', 'Direct Links', 'Enlaces directos'
    ]

    for pattern in browser_links_patterns:
        browser_links_section = soup.find('td', string=re.compile(pattern, re.IGNORECASE))
        if browser_links_section:
            parent_section = browser_links_section.find_parent('table')
            if parent_section:
                links = parent_section.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href and any(keyword in href.lower() for keyword in ['webplayer', 'player', 'stream', 'watch', 'live']):
                        reproductores.append({
                            'tipo': 'browser-links',
                            'texto': link.get_text().strip() or 'Browser Link',
                            'enlace': href if href.startswith('http') else urljoin(url_base, href),
                            'idioma': language_info['idioma'],
                            'bandera': language_info['bandera']
                        })

    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src')
        if src:
            valid_domains = [
                'webplayer', 'player', 'stream', 'daddylive', 'livetv', 'youtube', 'youtu.be',
                'dailymotion', 'vimeo', 'twitch', 'facebook', 'streamable', 'embed'
            ]

            if any(domain in src.lower() for domain in valid_domains):
                reproductores.append({
                    'tipo': 'iframe-embed',
                    'texto': f'Reproductor embebido ({urlparse(src).netloc})',
                    'enlace': src if src.startswith('http') else urljoin(url_base, src),
                    'idioma': language_info['idioma'],
                    'bandera': language_info['bandera']
                })

    if event_id:
        param_patterns = {
            'lid': re.findall(r'(?:lid|linkid)[=:]\s*(\d+)', html_content, re.IGNORECASE),
            'c': re.findall(r'[&?]c[=:]\s*(\d+)', html_content, re.IGNORECASE),
            'ci': re.findall(r'ci[=:]\s*(\d+)', html_content, re.IGNORECASE),
            'si': re.findall(r'si[=:]\s*(\d+)', html_content, re.IGNORECASE),
            'eid': re.findall(r'eid[=:]\s*(\d+)', html_content, re.IGNORECASE)
        }

        lids = set(param_patterns['lid'] + param_patterns['c'])
        cis = set(param_patterns['ci']) if param_patterns['ci'] else ['1', '2']
        sis = set(param_patterns['si']) if param_patterns['si'] else ['1', '2', '3']

        domains = ['cdn.livetv853.me', 'cdn.livetv854.me', 'cdn.livetv855.me']

        for domain in domains:
            for lid in lids:
                for ci in cis:
                    for si in sis:
                        webplayer_url = f"https://{domain}/webplayer.php?t=ifr&c={lid}&lang=es&eid={event_id}&lid={lid}&ci={ci}&si={si}"
                        reproductores.append({
                            'tipo': 'reconstructed-webplayer',
                            'texto': f'WebPlayer Reconstruido ({domain} - lid:{lid}, ci:{ci}, si:{si})',
                            'enlace': webplayer_url,
                            'idioma': language_info['idioma'],
                            'bandera': language_info['bandera']
                        })

    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link.get('href')
        text = link.get_text().strip()

        if href:
            reproductor_keywords = [
                'webplayer', 'player', 'stream', 'acestream', 'sopcast', 'torrent',
                'embed', 'watch', 'live', 'directo', 'ver', 'play', 'video',
                'canal', 'channel', 'link', 'enlace', 'mirror', 'servidor'
            ]

            if any(keyword in href.lower() for keyword in reproductor_keywords):
                full_url = href if href.startswith('http') else urljoin(url_base, href)
                reproductores.append({
                    'tipo': 'pattern-link',
                    'texto': text or f'Enlace de reproductor ({urlparse(full_url).netloc})',
                    'enlace': full_url,
                    'idioma': language_info['idioma'],
                    'bandera': language_info['bandera']
                })

    seen_urls = set()
    unique_reproductores = []

    for reproductor in reproductores:
        url = reproductor['enlace']
        if url not in seen_urls:
            seen_urls.add(url)
            unique_reproductores.append(reproductor)

    return unique_reproductores

class CacheManager:
    """Gestor de caché para URLs y contenido HTML para optimizar peticiones"""

    def __init__(self, cache_dir='./cache', ttl=3600):
        self.cache_dir = cache_dir
        self.ttl = ttl
        os.makedirs(cache_dir, exist_ok=True)
        self.lock = threading.Lock()

    def _get_cache_path(self, url):
        """Generar ruta de archivo para una URL"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.cache")

    def get(self, url):
        """Obtener contenido cacheado si existe y no ha expirado"""
        cache_path = self._get_cache_path(url)

        if os.path.exists(cache_path):
            with self.lock:
                try:
                    with open(cache_path, 'rb') as f:
                        cache_data = pickle.load(f)

                    timestamp = cache_data.get('timestamp', 0)
                    content = cache_data.get('content')

                    if time.time() - timestamp <= self.ttl:
                        logger.debug(f"Cache hit: {url}")
                        return content

                    logger.debug(f"Cache expired: {url}")
                except Exception as e:
                    logger.error(f"Error al leer caché para {url}: {e}")

        return None

    def set(self, url, content):
        """Guardar contenido en caché"""
        if not content:
            return

        cache_path = self._get_cache_path(url)

        with self.lock:
            try:
                cache_data = {
                    'timestamp': time.time(),
                    'url': url,
                    'content': content
                }

                with open(cache_path, 'wb') as f:
                    pickle.dump(cache_data, f)

                logger.debug(f"Cache guardado: {url}")
            except Exception as e:
                logger.error(f"Error al guardar caché para {url}: {e}")

    def clear(self, url=None):
        """Limpiar caché para una URL específica o todo el caché"""
        with self.lock:
            if url:
                cache_path = self._get_cache_path(url)
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    logger.debug(f"Cache eliminado para: {url}")
            else:
                for cache_file in os.listdir(self.cache_dir):
                    if cache_file.endswith('.cache'):
                        os.remove(os.path.join(self.cache_dir, cache_file))
                logger.debug("Cache limpiado completamente")

    def clean_expired(self):
        """Limpiar entradas de caché expiradas"""
        current_time = time.time()

        with self.lock:
            for cache_file in os.listdir(self.cache_dir):
                if cache_file.endswith('.cache'):
                    cache_path = os.path.join(self.cache_dir, cache_file)

                    try:
                        with open(cache_path, 'rb') as f:
                            cache_data = pickle.load(f)

                        timestamp = cache_data.get('timestamp', 0)

                        if current_time - timestamp > self.ttl:
                            os.remove(cache_path)
                            logger.debug(f"Caché expirado eliminado: {cache_data.get('url', 'unknown')}")

                    except Exception as e:
                        logger.error(f"Error al limpiar caché expirado {cache_file}: {e}")
                        os.remove(cache_path)

class CompressedCacheManager(CacheManager):
    """Gestor de caché con compresión"""

    def set(self, url, content):
        """Guardar contenido en caché con compresión"""
        if not content:
            return

        cache_path = self._get_cache_path(url)

        with self.lock:
            try:
                compressed_content = compress_content(content)

                cache_data = {
                    'timestamp': time.time(),
                    'url': url,
                    'content': compressed_content,
                    'compressed': True
                }

                with open(cache_path, 'wb') as f:
                    pickle.dump(cache_data, f)

                logger.debug(f"Cache comprimido guardado: {url}")
            except Exception as e:
                logger.error(f"Error al guardar caché para {url}: {e}")
                super().set(url, content)

    def get(self, url):
        """Obtener contenido cacheado con descompresión si es necesario"""
        cache_path = self._get_cache_path(url)

        if os.path.exists(cache_path):
            with self.lock:
                try:
                    with open(cache_path, 'rb') as f:
                        cache_data = pickle.load(f)

                    timestamp = cache_data.get('timestamp', 0)
                    content = cache_data.get('content')
                    is_compressed = cache_data.get('compressed', False)

                    if time.time() - timestamp <= self.ttl:
                        if is_compressed:
                            content = decompress_content(content)

                        logger.debug(f"Cache hit: {url}")
                        return content

                    logger.debug(f"Cache expired: {url}")
                except Exception as e:
                    logger.error(f"Error al leer caché para {url}: {e}")

        return None

class RequestThrottler:
    """Control de frecuencia de peticiones para evitar bloqueos"""

    def __init__(self, min_delay=1, max_delay=3):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request = 0
        self.lock = threading.Lock()

    def wait(self):
        """Esperar antes de hacer una nueva petición"""
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request

            if elapsed < self.min_delay:
                delay = random.uniform(self.min_delay, self.max_delay)
                sleep_time = max(0, delay - elapsed)

                if sleep_time > 0:
                    logger.debug(f"Throttling: esperando {sleep_time:.2f}s")
                    time.sleep(sleep_time)

            self.last_request = time.time()

def fetch_html(url, use_cache=True, session=None, throttler=None, cache_manager=None):
    """Obtener HTML de una URL con caché y control de frecuencia"""
    if not session:
        session = get_session()

    if not throttler:
        throttler = RequestThrottler(*CONFIG['REQUEST_DELAY'])

    if not cache_manager:
        cache_manager = CacheManager(CONFIG['CACHE_DIR'], CONFIG['CACHE_TTL'])

    if use_cache:
        cached_content = cache_manager.get(url)
        if cached_content:
            return cached_content

    throttler.wait()

    try:
        resp = session.get(url, timeout=CONFIG['TIMEOUT'])
        resp.raise_for_status()
        html_content = resp.text

        if use_cache and html_content:
            cache_manager.set(url, html_content)

        return html_content
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener {url}: {e}")
        return None

def extract_event_info(event_url, session=None, throttler=None, cache_manager=None):
    """Extraer información detallada de un evento deportivo"""
    if not session:
        session = get_session()

    if not throttler:
        throttler = RequestThrottler(*CONFIG['REQUEST_DELAY'])

    if not cache_manager:
        cache_manager = CacheManager(CONFIG['CACHE_DIR'], CONFIG['CACHE_TTL'])

    html_content = fetch_html(event_url, True, session, throttler, cache_manager)
    if not html_content:
        logger.error(f"No se pudo obtener contenido HTML para {event_url}")
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        title_elem = soup.find('span', class_='mar')
        title = title_elem.get_text().strip() if title_elem else "Evento sin título"

        date_time = None
        date_elem = soup.find('td', string=re.compile(r'start|inicio|comienzo', re.IGNORECASE))
        if date_elem and date_elem.find_next('td'):
            date_time_text = date_elem.find_next('td').get_text().strip()
            date_formats = [
                '%d.%m.%Y %H:%M',
                '%d.%m.%Y, %H:%M',
                '%d/%m/%Y %H:%M',
                '%Y-%m-%d %H:%M',
                '%d %b %Y %H:%M'
            ]

            for fmt in date_formats:
                try:
                    date_time = datetime.strptime(date_time_text, fmt)
                    break
                except ValueError:
                    continue

        sport = "Desconocido"
        competition = "Desconocida"

        category_elem = soup.find('td', {'height': '28'})
        if category_elem:
            category_text = category_elem.get_text().strip()
            parts = category_text.split('»')

            if len(parts) >= 1:
                sport = parts[0].strip()
            if len(parts) >= 2:
                competition = parts[1].strip()

        teams = []
        team_elem = soup.find('td', {'width': '100%'})
        if team_elem:
            team_text = team_elem.get_text().strip()
            teams = re.split(r'\s+[–-]\s+', team_text)

        reproductores = extract_reproductor_links(html_content, event_url)

        event_info = {
            'url': event_url,
            'title': title,
            'teams': teams,
            'sport': sport,
            'competition': competition,
            'datetime': date_time.strftime('%Y-%m-%d %H:%M:%S') if date_time else None,
            'reproductores': reproductores,
            'scrape_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        return event_info

    except Exception as e:
        logger.error(f"Error al extraer información del evento {event_url}: {e}")
        return None

def extract_upcoming_events(sport_url, max_events=100, session=None, throttler=None, cache_manager=None):
    """Extraer eventos próximos desde una URL de deporte"""
    if not session:
        session = get_session()

    if not throttler:
        throttler = RequestThrottler(*CONFIG['REQUEST_DELAY'])

    if not cache_manager:
        cache_manager = CacheManager(CONFIG['CACHE_DIR'], CONFIG['CACHE_TTL'])

    html_content = fetch_html(urljoin(CONFIG['BASE_URL'], sport_url), True, session, throttler, cache_manager)
    if not html_content:
        logger.error(f"No se pudo obtener contenido HTML para {sport_url}")
        return []

    event_links = []
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        main_content = soup.find('div', class_='main')
        if main_content:
            links = main_content.find_all('a', href=re.compile(r'/eventinfo/\d+'))

            for link in links[:max_events]:
                href = link.get('href')
                if href:
                    event_url = urljoin(CONFIG['BASE_URL'], href)
                    if event_url not in event_links:
                        event_links.append(event_url)

    except Exception as e:
        logger.error(f"Error al extraer eventos próximos de {sport_url}: {e}")

    return event_links

def generate_sitemap(events_info, output_file):
    """Generar sitemap XML con eventos y reproductores"""
    try:
        urlset = ET.Element('urlset', {'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9'})

        for event in events_info:
            url_elem = ET.SubElement(urlset, 'url')

            loc = ET.SubElement(url_elem, 'loc')
            loc.text = event['url']

            lastmod = ET.SubElement(url_elem, 'lastmod')
            lastmod.text = datetime.now().strftime('%Y-%m-%d')

            changefreq = ET.SubElement(url_elem, 'changefreq')
            changefreq.text = 'hourly'

            priority = ET.SubElement(url_elem, 'priority')
            priority.text = '0.8'

            for reproductor in event.get('reproductores', []):
                if 'enlace' in reproductor and reproductor['enlace'].startswith('http'):
                    player_url_elem = ET.SubElement(urlset, 'url')

                    player_loc = ET.SubElement(player_url_elem, 'loc')
                    player_loc.text = reproductor['enlace']

                    player_lastmod = ET.SubElement(player_url_elem, 'lastmod')
                    player_lastmod.text = datetime.now().strftime('%Y-%m-%d')

                    player_changefreq = ET.SubElement(player_url_elem, 'changefreq')
                    player_changefreq.text = 'hourly'

                    player_priority = ET.SubElement(player_url_elem, 'priority')
                    player_priority.text = '0.6'

        rough_string = ET.tostring(urlset, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)

        logger.info(f"Sitemap generado: {output_file}")
        return True

    except Exception as e:
        logger.error(f"Error al generar sitemap XML: {e}")
        return False

def compress_content(content):
    """Comprimir contenido para ahorrar espacio en caché"""
    try:
        pickled = pickle.dumps(content)
        compressed = gzip.compress(pickled)
        return compressed
    except Exception:
        return content

def decompress_content(compressed_content):
    """Descomprimir contenido de caché"""
    try:
        decompressed = gzip.decompress(compressed_content)
        content = pickle.loads(decompressed)
        return content
    except Exception:
        return compressed_content

class ScrapingStats:
    """Clase para mantener estadísticas del scraping"""

    def __init__(self):
        self.start_time = time.time()
        self.events_processed = 0
        self.reproductores_found = 0
        self.reproductor_types = {}
        self.errors = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.successful_requests = 0
        self.failed_requests = 0

    def add_event(self, event_info):
        """Registrar un evento procesado"""
        self.events_processed += 1

        if event_info and 'reproductores' in event_info:
            reps = event_info['reproductores']
            self.reproductores_found += len(reps)

            for rep in reps:
                tipo = rep.get('tipo', 'unknown')
                self.reproductor_types[tipo] = self.reproductor_types.get(tipo, 0) + 1

    def add_error(self):
        """Registrar un error"""
        self.errors += 1

    def add_cache_hit(self):
        """Registrar un hit de caché"""
        self.cache_hits += 1

    def add_cache_miss(self):
        """Registrar un miss de caché"""
        self.cache_misses += 1

    def add_request(self, success=True):
        """Registrar una petición HTTP"""
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def get_summary(self):
        """Obtener resumen de estadísticas"""
        elapsed = time.time() - self.start_time

        return {
            'duration_seconds': elapsed,
            'duration_formatted': time.strftime('%H:%M:%S', time.gmtime(elapsed)),
            'events_processed': self.events_processed,
            'reproductores_found': self.reproductores_found,
            'reproductor_types': self.reproductor_types,
            'errors': self.errors,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'cache_hit_ratio': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'request_success_ratio': self.successful_requests / (self.successful_requests + self.failed_requests) if (self.successful_requests + self.failed_requests) > 0 else 0,
            'reproductores_per_event': self.reproductores_found / self.events_processed if self.events_processed > 0 else 0
        }

def scrape_livetv_improved(
    max_events_per_sport=10,
    languages=['es'],
    sports=None,
    validate_reproductores=False,
    use_compressed_cache=True,
    max_threads=5,
    output_dir='./output'
):
    """Versión mejorada de la función principal de scraping"""
    logger.info("Iniciando scraping mejorado de LiveTV.sx")
    stats = ScrapingStats()

    session = get_session()
    throttler = RequestThrottler(*CONFIG['REQUEST_DELAY'])

    if use_compressed_cache:
        cache_manager = CompressedCacheManager(CONFIG['CACHE_DIR'], CONFIG['CACHE_TTL'])
    else:
        cache_manager = CacheManager(CONFIG['CACHE_DIR'], CONFIG['CACHE_TTL'])

    cache_manager.clean_expired()

    if not sports:
        sports = CONFIG['SPORTS']

    all_event_urls = []

    for sport_name, sport_url in sports.items():
        logger.info(f"Obteniendo eventos de {sport_name}")

        for lang in languages:
            lang_sport_url = sport_url.replace('/es/', f'/{lang}/')

            event_urls = extract_upcoming_events(
                lang_sport_url,
                max_events_per_sport,
                session,
                throttler,
                cache_manager
            )

            logger.info(f"Se encontraron {len(event_urls)} eventos de {sport_name} en idioma {lang}")
            all_event_urls.extend(event_urls)

    all_event_urls = list(set(all_event_urls))
    logger.info(f"Total de eventos únicos encontrados: {len(all_event_urls)}")

    events_info = []

    event_queue = Queue()
    results = []
    lock = threading.Lock()

    def worker():
        while True:
            event_url = event_queue.get()
            if event_url is None:
                break

            try:
                logger.info(f"Procesando evento: {event_url}")
                event_info = extract_event_info(event_url, session, throttler, cache_manager)

                if event_info:
                    if validate_reproductores:
                        event_info['reproductores'] = filter_validate_reproductores(
                            event_info['reproductores'],
                            session
                        )

                    with lock:
                        results.append(event_info)
                        stats.add_event(event_info)
                else:
                    stats.add_error()

            except Exception as e:
                logger.error(f"Error al procesar {event_url}: {e}")
                stats.add_error()

            finally:
                event_queue.task_done()

    threads = []
    for _ in range(min(max_threads, len(all_event_urls))):
        t = Thread(target=worker)
        t.daemon = True
        t.start()
        threads.append(t)

    for event_url in all_event_urls:
        event_queue.put(event_url)

    event_queue.join()

    for _ in range(len(threads)):
        event_queue.put(None)

    for t in threads:
        t.join()

    events_info = sorted(
        results,
        key=lambda e: e.get('datetime', '9999-99-99') if e.get('datetime') else '9999-99-99'
    )

    output_file = os.path.join(output_dir, 'livetv_events.json')
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(events_info, f, ensure_ascii=False, indent=2)
        logger.info(f"Resultados guardados en {output_file}")
    except Exception as e:
        logger.error(f"Error al guardar resultados: {e}")

    sitemap_file = os.path.join(output_dir, CONFIG['SITEMAP_FILE'])
    generate_sitemap(events_info, sitemap_file)

    stats_summary = stats.get_summary()
    stats_file = os.path.join(output_dir, 'scraping_stats.json')
    try:
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_summary, f, ensure_ascii=False, indent=2)
        logger.info(f"Estadísticas guardadas en {stats_file}")
    except Exception as e:
        logger.error(f"Error al guardar estadísticas: {e}")

    logger.info(f"Scraping completado en {stats_summary['duration_formatted']}")
    logger.info(f"Eventos procesados: {stats_summary['events_processed']}")
    logger.info(f"Reproductores encontrados: {stats_summary['reproductores_found']}")
    logger.info(f"Errores: {stats_summary['errors']}")

    return events_info, stats_summary

def filter_validate_reproductores(reproductores, session=None):
    """Filtrar y validar reproductores, eliminando duplicados y no funcionales"""
    if not session:
        session = get_session()

    unique_reproductores = []
    seen_urls = set()

    for reproductor in reproductores:
        url = reproductor.get('enlace', '')

        if not url or url in seen_urls:
            continue

        skip_domains = ['facebook.com', 'twitter.com', 'instagram.com', 'reddit.com']
        if any(domain in url.lower() for domain in skip_domains) and not any(keyword in url.lower() for keyword in ['video', 'player', 'stream', 'watch']):
            continue

        seen_urls.add(url)

        if url.startswith(('http://', 'https://')):
            validate_types = ['webplayer-direct', 'reconstructed-webplayer', 'hls-m3u8', 'dash-mpd', 'direct-mp4']
            if reproductor.get('tipo', '') in validate_types:
                is_valid, content_type = test_reproductor_url(url, 5, session)
                reproductor['validado'] = is_valid
                reproductor['content_type'] = content_type

        unique_reproductores.append(reproductor)

    return unique_reproductores

def test_reproductor_url(url, timeout=5, session=None):
    """Verificar si una URL de reproductor parece funcionar"""
    if not session:
        session = get_session()

    try:
        headers = session.headers.copy()
        headers['Referer'] = 'https://livetv.sx/'

        resp = session.head(url, timeout=timeout, headers=headers, allow_redirects=True)

        if resp.status_code == 200:
            return True, resp.headers.get('Content-Type', '')

        if resp.status_code in [403, 405]:
            resp = session.get(url, timeout=timeout, headers=headers, stream=True, allow_redirects=True)
            content = next(resp.iter_content(1024), None)
            return resp.status_code == 200, resp.headers.get('Content-Type', '')

        return False, f"Status: {resp.status_code}"

    except requests.exceptions.RequestException as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error: {e}"

def save_script():
    """Guardar todo el código en un solo archivo"""
    script_content = []

    script_content.append("""
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
from datetime import datetime, timedelta
import json
import warnings
from urllib3.exceptions import InsecureRequestWarning
import base64
import os
import hashlib
import pickle
import threading
import gzip
from queue import Queue

# Suprimir todas las advertencias
warnings.simplefilter('ignore', InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
""")

    script_content.append("""
# Configuración global
CONFIG = {
    'BASE_URL': 'https://livetv.sx/es/',
    'CACHE_TTL': 3600,
    'USER_AGENTS_ROTATE': True,
    'REQUEST_DELAY': (1, 3),
    'MAX_THREADS': 5,
    'CACHE_DIR': './cache',
    'OUTPUT_DIR': './output',
    'SITEMAP_FILE': 'livetv_sitemap.xml',
    'MAX_RETRIES': 3,
    'TIMEOUT': 30,
    'LANGUAGES': ['es', 'en'],
    'SPORTS': {
        'fútbol': '/es/allupcoming/1/',
        'baloncesto': '/es/allupcoming/3/',
        'tenis': '/es/allupcoming/5/',
        'hockey': '/es/allupcoming/2/',
        'formula1': '/es/allupcoming/10/',
        'rugby': '/es/allupcoming/6/',
        'balonmano': '/es/allupcoming/13/',
        'voleibol': '/es/allupcoming/12/',
        'béisbol': '/es/allupcoming/4/',
        'mma': '/es/allupcoming/15/',
        'boxeo': '/es/allupcoming/28/',
        'golf': '/es/allupcoming/19/',
        'otros': '/es/allupcoming/0/'
    }
}

# Configurar logging mejorado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("update_streams_definitivo.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Crear carpetas necesarias
os.makedirs(CONFIG['CACHE_DIR'], exist_ok=True)
os.makedirs(CONFIG['OUTPUT_DIR'], exist_ok=True)
""")

    for name, obj in globals().items():
        if inspect.isclass(obj) and obj.__module__ == '__main__':
            script_content.append(inspect.getsource(obj))

    for name, obj in globals().items():
        if inspect.isfunction(obj) and obj.__module__ == '__main__':
            script_content.append(inspect.getsource(obj))

    script_content.append("""
# Ejecución del script
if __name__ == "__main__":
    exit_code = main_improved()
    exit(exit_code)
""")

    full_script = "\n".join(script_content)

    with open(os.path.join(CONFIG['OUTPUT_DIR'], 'livetv_scraper_completo.py'), 'w', encoding='utf-8') as f:
        f.write(full_script)

    logger.info(f"Script completo guardado en {os.path.join(CONFIG['OUTPUT_DIR'], 'livetv_scraper_completo.py')}")

def main_improved():
    """Función principal mejorada"""
    try:
        logger.info("Inicio del script mejorado de scraping LiveTV.sx")

        os.makedirs(CONFIG['OUTPUT_DIR'], exist_ok=True)
        os.makedirs(CONFIG['CACHE_DIR'], exist_ok=True)

        max_events_per_sport = 10
        languages = CONFIG['LANGUAGES']

        events, stats = scrape_livetv_improved(
            max_events_per_sport,
            languages,
            validate_reproductores=True,
            use_compressed_cache=True,
            max_threads=CONFIG['MAX_THREADS'],
            output_dir=CONFIG['OUTPUT_DIR']
        )

        logger.info(f"Script completado con éxito. Se procesaron {len(events)} eventos.")

        logger.info("Resumen de tipos de reproductores:")
        for tipo, count in sorted(stats['reproductor_types'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  - {tipo}: {count}")

        return 0

    except Exception as e:
        logger.error(f"Error en la ejecución principal: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main_improved()
    exit(exit_code)

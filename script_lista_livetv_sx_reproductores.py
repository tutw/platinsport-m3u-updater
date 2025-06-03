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
from datetime import datetime
import json
import warnings
from urllib3.exceptions import InsecureRequestWarning
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import os

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

def get_selenium_driver():
    """Crear driver de Selenium para casos complejos"""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--silent')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logger.warning(f"No se pudo inicializar Selenium: {e}")
        return None

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
    """
    Detectar el idioma del reproductor usando múltiples métodos
    Incluyendo el selector CSS proporcionado por el usuario
    """
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
                
                # Extraer información del idioma de la imagen de bandera
                if src:
                    # Buscar código de país en la URL de la imagen
                    country_match = re.search(r'/(\w{2})\.(?:png|jpg|gif)', src.lower())
                    if country_match:
                        language_info['codigo_pais'] = country_match.group(1).upper()
                        language_info['metodo_deteccion'] = 'selector_css_usuario'
                
                # Usar alt o title para obtener el nombre del idioma
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
    
    # Patrones para URLs de YouTube
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
        # 1. Extraer streams M3U8
        m3u8_pattern = r'(https?://[^"\'\s]+\.m3u8(?:\?[^"\'\s]*)?)'
        m3u8_matches = re.finditer(m3u8_pattern, html_content, re.IGNORECASE)
        for match in m3u8_matches:
            url = match.group(1)
            advanced_streams.append({
                'tipo': 'hls-m3u8',
                'texto': 'HLS Stream (M3U8)',
                'enlace': url
            })
        
        # 2. Extraer streams DASH (MPD)
        mpd_pattern = r'(https?://[^"\'\s]+\.mpd(?:\?[^"\'\s]*)?)'
        mpd_matches = re.finditer(mpd_pattern, html_content, re.IGNORECASE)
        for match in mpd_matches:
            url = match.group(1)
            advanced_streams.append({
                'tipo': 'dash-mpd',
                'texto': 'DASH Stream (MPD)',
                'enlace': url
            })
        
        # 3. Extraer Acestream links
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
        
        # 4. Extraer SopCast links
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
        
        # 5. Extraer streams MP4 directos
        mp4_pattern = r'(https?://[^"\'\s]+\.mp4(?:\?[^"\'\s]*)?)'
        mp4_matches = re.finditer(mp4_pattern, html_content, re.IGNORECASE)
        for match in mp4_matches:
            url = match.group(1)
            advanced_streams.append({
                'tipo': 'direct-mp4',
                'texto': 'Direct MP4 Stream',
                'enlace': url
            })
        
        # 6. Extraer streams de otros servicios populares
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
        # Buscar scripts
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string:
                content = script.string
                
                # Patrones para detectar reproductores en JavaScript
                js_patterns = [
                    # Variables que contienen URLs de streaming
                    r'(?:src|url|stream|player)\s*[:=]\s*["\']([^"\']+)["\']',
                    # Llamadas a funciones de reproducción
                    r'(?:play|load|stream)\s*\(\s*["\']([^"\']+)["\']',
                    # URLs en formato JSON
                    r'"(?:url|src|stream)"\s*:\s*"([^"]+)"',
                    # Base64 encoded URLs
                    r'(?:atob|decode)\s*\(\s*["\']([A-Za-z0-9+/=]+)["\']',
                    # Variables de configuración
                    r'var\s+\w+\s*=\s*["\']([^"\']*(?:http|stream|player)[^"\']*)["\']'
                ]
                
                for pattern in js_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        potential_url = match.group(1)
                        
                        # Verificar si es una URL válida
                        if potential_url.startswith(('http', '//', 'data:')):
                            js_players.append({
                                'tipo': 'javascript-extracted',
                                'texto': 'JavaScript Player',
                                'enlace': potential_url if potential_url.startswith('http') else urljoin(url_base, potential_url)
                            })
                        elif len(potential_url) > 20 and '=' in potential_url:
                            # Podría ser base64
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

def extract_reproductor_links(html_content, url_base, driver=None):
    """
    Función definitiva y mejorada para extraer enlaces de reproductores de LiveTV.sx
    
    Estrategias implementadas:
    1. Detección de URLs webplayer.php mediante regex avanzado
    2. Análisis de iframes embebidos con filtros inteligentes
    3. Búsqueda en sección Browser Links mejorada
    4. Extracción de JavaScript con decodificación
    5. Reconstrucción de URLs desde parámetros optimizada
    6. Detección de enlaces acestream/sopcast/torrent
    7. Extracción de YouTube y otros servicios populares
    8. Streams HLS (M3U8) y DASH (MPD)
    9. Uso de Selenium para contenido dinámico
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    reproductores = []
    
    # Detectar idioma de la página
    language_info = detect_language_from_page(soup, url_base)
    
    # Extraer ID del evento desde la URL base para reconstruir URLs
    event_id_match = re.search(r'/eventinfo/(\d+)_', url_base)
    event_id = event_id_match.group(1) if event_id_match else None
    
    logger.info(f"Procesando evento ID: {event_id}, Idioma detectado: {language_info}")
    
    # Método 1: Buscar URLs webplayer.php con patrones mejorados
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
    
    # Método 2: Extraer YouTube players
    youtube_players = extract_youtube_players(html_content)
    for player in youtube_players:
        player['idioma'] = language_info['idioma']
        player['bandera'] = language_info['bandera']
        reproductores.append(player)
    
    # Método 3: Extraer streams avanzados
    advanced_streams = extract_advanced_streams(html_content, url_base)
    for stream in advanced_streams:
        stream['idioma'] = language_info['idioma']
        stream['bandera'] = language_info['bandera']
        reproductores.append(stream)
    
    # Método 4: Extraer desde JavaScript
    js_players = extract_javascript_players(html_content, url_base)
    for player in js_players:
        player['idioma'] = language_info['idioma']
        player['bandera'] = language_info['bandera']
        reproductores.append(player)
    
    # Método 5: Buscar en la sección "Browser Links" específica con mejoras
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
    
    # Método 6: Buscar todos los iframes con filtros inteligentes
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src')
        if src:
            # Filtros para identificar reproductores válidos
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
    
    # Método 7: Reconstruir URLs webplayer desde parámetros mejorado
    if event_id:
        # Buscar patrones de parámetros más comprehensivos
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
        
        # Dominios a probar
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
    
    # Método 8: Buscar enlaces con patrones específicos mejorados
    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link.get('href')
        text = link.get_text().strip()
        
        if href:
            # Patrones mejorados para reproductores
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
    
    # Método 9: Usar Selenium para contenido dinámico (si está disponible)
    if driver:
        try:
            driver.get(url_base)
            time.sleep(3)  # Esperar a que cargue el contenido dinámico
            
            # Buscar elementos generados dinámicamente
            dynamic_links = driver.find_elements(By.TAG_NAME, "a")
            for link in dynamic_links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip()
                    
                    if href an

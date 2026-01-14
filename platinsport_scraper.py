#!/usr/bin/env python3
"""
PlatinSport Acestream Scraper - VERSIÓN ULTIMATE
================================================
✅ Extrae TODOS los eventos de la página principal
✅ Mapea cada evento con sus URLs Acestream desde source-list.php
✅ Manejo robusto de errores con retry logic
✅ Generación de M3U con información completa
✅ Logging detallado y estadísticas
✅ Validación completa de URLs Acestream
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
import time
import base64
import logging
from typing import Dict, List, Optional
from collections import defaultdict

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UltimatePlatinSportScraper:
    """Scraper optimizado que extrae TODOS los enlaces Acestream de eventos"""
    
    def __init__(self):
        self.base_url = "https://platinsport.com"
        self.session = requests.Session()
        self.retry_count = 3
        self.retry_delay = 2
        
        # Configurar headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://platinsport.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin'
        })
        
        self._set_disclaimer_cookie()
        logger.info("✅ Scraper Ultimate inicializado correctamente")
    
    def _set_disclaimer_cookie(self):
        """Configura la cookie de disclaimer"""
        try:
            self.session.cookies.set(
                'disclaimer_accepted',
                'true',
                domain='.platinsport.com',
                path='/',
                secure=True
            )
            logger.debug("✅ Cookie configurada")
        except Exception as e:
            logger.warning(f"⚠️  Error configurando cookie: {e}")
    
    def generate_key(self) -> str:
        """Genera la key de acceso basada en la fecha actual"""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        key_string = today + "PLATINSPORT"
        key = base64.b64encode(key_string.encode()).decode()
        return key
    
    def validate_acestream_url(self, url: str) -> bool:
        """Valida formato de URL Acestream (acestream:// + 40 hex chars)"""
        if not url:
            return False
        pattern = r'^acestream://[a-f0-9]{40}$'
        return bool(re.match(pattern, url, re.IGNORECASE))

    def build_flag_icon_url(self, code: str, variant: str = '4x3') -> str:
        """Construye la URL del SVG de bandera exactamente como en la web (flag-icons)."""
        code = (code or '').strip().lower()
        if not code:
            return ''
        return f"https://www.platinsport.com/style/flag-icons-main/flags/{variant}/{code}.svg"

    def extract_language_flag_code_from_anchor(self, a_tag) -> Optional[str]:
        """Extrae el código ISO (fi-xx) del <span class='fi fi-xx'> dentro del enlace."""
        if not a_tag:
            return None
        span = a_tag.find('span', class_=lambda x: x and 'fi' in x)
        if not span:
            return None
        for c in (span.get('class') or []):
            if isinstance(c, str) and c.startswith('fi-') and len(c) == 5:
                return c.split('-', 1)[1]
        return None
    
    def _make_request(self, url: str, timeout: int = 20) -> Optional[requests.Response]:
        """Hace request con retry logic y backoff exponencial"""
        for attempt in range(self.retry_count):
            try:
                # Asegurarse de que requests decodifique automáticamente
                response = self.session.get(url, timeout=timeout, allow_redirects=True)
                response.raise_for_status()
                
                # Verificar decodificación Brotli
                if response.headers.get('Content-Encoding') == 'br':
                    try:
                        import brotli
                        if response.content[:2] == b'\x83\xff' or response.content[:1] == b'\x8b':
                            logger.debug("🔧 Decodificando Brotli manualmente")
                            response._content = brotli.decompress(response.content)
                    except Exception as e:
                        logger.warning(f"⚠️  Error decodificando Brotli: {e}")
                
                # Verificar decodificación gzip
                elif response.content[:2] == b'\x1f\x8b':
                    try:
                        import gzip
                        logger.debug("🔧 Decodificando gzip manualmente")
                        response._content = gzip.decompress(response.content)
                    except Exception as e:
                        logger.warning(f"⚠️  Error decodificando gzip: {e}")
                
                # Forzar encoding UTF-8
                if response.encoding is None or response.encoding == 'ISO-8859-1':
                    response.encoding = 'utf-8'
                
                return response
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️  Timeout en intento {attempt + 1}/{self.retry_count}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
            
            except requests.exceptions.HTTPError as e:
                logger.error(f"❌ HTTP Error {e.response.status_code}: {url}")
                return None
            
            except requests.exceptions.ConnectionError:
                logger.warning(f"🔌 Error de conexión en intento {attempt + 1}/{self.retry_count}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
            
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request error: {e}")
                return None
        
        logger.error(f"❌ Falló después de {self.retry_count} intentos: {url}")
        return None
    
    def normalize_team_name(self, name: str) -> str:
        """Normaliza nombres de equipos para matching"""
        if not name:
            return ""
        # Eliminar espacios extras y normalizar
        name = re.sub(r'\s+', ' ', name).strip()
        # Normalizar caracteres especiales comunes
        replacements = {
            ''': "'",
            ''': "'",
            '"': '"',
            '"': '"',
            '—': '-',
            '–': '-'
        }
        for old, new in replacements.items():
            name = name.replace(old, new)
        return name
    
    def extract_events_from_main_page(self) -> List[Dict]:
        """Extrae eventos de la página principal"""
        logger.info("🔍 Obteniendo página principal...")
        response = self._make_request(self.base_url)
        
        if not response:
            logger.error("❌ No se pudo obtener la página principal")
            return []
        
        soup = BeautifulSoup(response.text, 'lxml')
        events = []
        
        # Buscar todos los elementos <time> que indican eventos
        time_elements = soup.find_all('time')
        logger.info(f"✅ Encontrados {len(time_elements)} elementos <time> en la página principal")
        
        # Debug: verificar contenido
        if len(time_elements) == 0:
            logger.warning(f"⚠️  No se encontraron elementos <time>. Longitud HTML: {len(response.text)}")
            logger.warning(f"⚠️  Primeros 500 chars: {response.text[:500]}")
        
        for time_elem in time_elements:
            try:
                # Navegar hacia arriba para encontrar el contenedor del evento
                container = None
                current = time_elem
                
                for _ in range(5):  # Máximo 5 niveles hacia arriba
                    current = current.parent
                    if not current:
                        break
                    
                    # Verificar si tiene un botón PLAY
                    play_link = current.find('a', href=re.compile(r'javascript:go'))
                    if play_link:
                        container = current
                        break
                
                if not container:
                    continue
                
                # Extraer información del evento
                datetime_str = time_elem.get('datetime', '')
                
                # Buscar nombres de equipos
                team_spans = container.find_all(
                    'span',
                    style=lambda x: x and 'font-size: 12px' in x and 'color: #fff' in x
                )
                
                teams = []
                for span in team_spans:
                    team_name = span.get_text(strip=True)
                    if team_name and team_name not in ['VS', '']:
                        teams.append(self.normalize_team_name(team_name))
                
                if len(teams) >= 2:
                    team1 = teams[0]
                    team2 = teams[1]
                elif len(teams) == 1:
                    team1 = teams[0]
                    team2 = "TBD"
                else:
                    continue  # Skip si no hay nombres de equipos
                
                # Extraer logos/banderas de equipos (si existen)
                img_tags = container.find_all('img') if container else []
                team_logo_urls = [img.get('src') for img in img_tags if img.get('src')]
                team1_logo_url = team_logo_urls[0] if len(team_logo_urls) >= 1 else ''
                team2_logo_url = team_logo_urls[1] if len(team_logo_urls) >= 2 else ''

                # Formatear hora
                match_time = "Unknown"
                if datetime_str:
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        match_time = dt.strftime('%H:%M UTC')
                    except ValueError:
                        match_time = datetime_str
                
                # Crear clave de matching normalizada
                match_key = f"{team1} vs {team2}".lower()
                
                events.append({
                    'team1': team1,
                    'team2': team2,
                    'time': match_time,
                    'datetime': datetime_str,
                    'match_key': match_key,
                    'team1_logo_url': team1_logo_url,
                    'team2_logo_url': team2_logo_url,
                    'acestream_links': []
                })
                
            except (AttributeError, KeyError) as e:
                logger.debug(f"⚠️  Error extrayendo evento: {e}")
                continue
        
        logger.info(f"📊 Eventos válidos extraídos: {len(events)}")
        return events
    
    def extract_acestream_links_from_source_list(self) -> Dict[str, List[Dict]]:
        """
        Extrae todos los enlaces Acestream de source-list.php
        Returns: Dict con match_key -> lista de enlaces
        """
        key = self.generate_key()
        url = f"https://www.platinsport.com/link/source-list.php?key={key}"
        
        logger.info("🎯 Accediendo a source-list.php...")
        response = self._make_request(url)
        
        if not response:
            logger.error("❌ No se pudo acceder a source-list.php")
            return {}
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Buscar match-title-bars
        match_bars = soup.find_all('div', class_='match-title-bar')
        logger.info(f"✅ Encontrados {len(match_bars)} partidos en source-list.php")
        
        links_by_match = {}
        
        for bar in match_bars:
            try:
                # Extraer título del partido
                bar_text = bar.get_text(' ', strip=True)
                
                # Remover hora si está visible
                time_elem = bar.find('time')
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    if time_text:
                        bar_text = bar_text.replace(time_text, '').strip()
                
                # Normalizar para matching
                match_key = self.normalize_team_name(bar_text).lower()
                
                # Buscar button-group con enlaces
                button_group = bar.find_next_sibling('div', class_='button-group')
                if not button_group:
                    continue
                
                # Extraer todos los enlaces acestream
                ace_links = button_group.find_all('a', href=re.compile(r'acestream://'))
                
                valid_links = []
                for link in ace_links:
                    url = link.get('href', '')
                    
                    if not self.validate_acestream_url(url):
                        logger.debug(f"⚠️  URL inválida: {url[:50]}")
                        continue
                    
                    quality = link.get_text(strip=True) or 'STREAM'

                    # Bandera de idioma/canal tal como aparece en la web: <span class="fi fi-es"></span>
                    flag_code = self.extract_language_flag_code_from_anchor(link)
                    flag_url = self.build_flag_icon_url(flag_code) if flag_code else ''

                    valid_links.append({
                        'url': url,
                        'quality': quality,
                        'channel': quality,  # Alias para compatibilidad
                        'flag_code': flag_code or '',
                        'flag_url': flag_url
                    })
                
                if valid_links:
                    links_by_match[match_key] = valid_links
                    logger.debug(f"  ✓ {match_key}: {len(valid_links)} enlaces")
                
            except (AttributeError, TypeError) as e:
                logger.debug(f"⚠️  Error extrayendo enlaces: {e}")
                continue
        
        total_links = sum(len(links) for links in links_by_match.values())
        logger.info(f"📊 Total enlaces extraídos: {total_links} de {len(links_by_match)} partidos")
        
        return links_by_match
    
    def match_events_with_links(self, events: List[Dict], links_by_match: Dict[str, List[Dict]]) -> List[Dict]:
        """Mapea eventos con sus enlaces Acestream correspondientes"""
        logger.info("🔗 Mapeando eventos con enlaces Acestream...")
        
        matched = 0
        total_links = 0
        
        for event in events:
            match_key = event['match_key']
            
            # Búsqueda exacta
            if match_key in links_by_match:
                event['acestream_links'] = links_by_match[match_key]
                matched += 1
                total_links += len(event['acestream_links'])
                continue
            
            # Búsqueda fuzzy - buscar coincidencias parciales
            found = False
            for key, links in links_by_match.items():
                # Verificar si ambos equipos están en la key
                if event['team1'].lower() in key and event['team2'].lower() in key:
                    event['acestream_links'] = links
                    matched += 1
                    total_links += len(links)
                    found = True
                    logger.debug(f"  ✓ Match fuzzy: {match_key} <-> {key}")
                    break
            
            if not found:
                logger.debug(f"  ⚠️  Sin enlaces para: {match_key}")
        
        logger.info(f"✅ Eventos mapeados: {matched}/{len(events)}")
        logger.info(f"📊 Total enlaces asignados: {total_links}")
        
        return events
    
    def scrape(self) -> Optional[Dict]:
        """Ejecuta el scraping completo"""
        logger.info("=" * 80)
        logger.info("🏆 PLATINSPORT ULTIMATE SCRAPER")
        logger.info(f"📅 Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"🔑 Key: {self.generate_key()}")
        logger.info("=" * 80)
        
        # Paso 1: Extraer eventos de la página principal
        events = self.extract_events_from_main_page()
        if not events:
            logger.error("❌ No se encontraron eventos")
            return None
        
        # Paso 2: Extraer todos los enlaces de source-list.php
        links_by_match = self.extract_acestream_links_from_source_list()
        if not links_by_match:
            logger.warning("⚠️  No se encontraron enlaces Acestream")
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_events': len(events),
                'events': events
            }
        
        # Paso 3: Mapear eventos con enlaces
        events = self.match_events_with_links(events, links_by_match)
        
        # Estadísticas finales
        events_with_links = sum(1 for e in events if e['acestream_links'])
        total_links = sum(len(e['acestream_links']) for e in events)
        
        logger.info("=" * 80)
        logger.info("📊 ESTADÍSTICAS FINALES:")
        logger.info(f"   • Total eventos:           {len(events)}")
        logger.info(f"   • Eventos con enlaces:     {events_with_links}")
        logger.info(f"   • Total enlaces Acestream: {total_links}")
        if events_with_links > 0:
            logger.info(f"   • Promedio por evento:     {total_links/events_with_links:.1f}")
        logger.info("=" * 80)
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_events': len(events),
            'events_with_links': events_with_links,
            'total_links': total_links,
            'events': events
        }
    
    def generate_m3u(self, result: Dict) -> Optional[str]:
        """Genera archivo M3U desde los resultados"""
        if not result or 'events' not in result:
            return None
        
        m3u_lines = ['#EXTM3U']
        
        for event in result['events']:
            team1 = event.get('team1', 'Unknown')
            team2 = event.get('team2', 'Unknown')
            match_time = event.get('time', 'Unknown')
            links = event.get('acestream_links', [])
            
            if not links:
                continue
            
            for idx, link in enumerate(links, 1):
                quality = link.get('quality', 'HD')
                url = link.get('url', '')
                
                if not self.validate_acestream_url(url):
                    continue
                
                # Formato M3U
                channel_name = f"{team1} vs {team2} - {match_time} - {quality}"

                flag_url = link.get('flag_url', '')
                if flag_url:
                    m3u_lines.append(f"#EXTINF:-1 tvg-logo=\"{flag_url}\",{channel_name}")
                else:
                    m3u_lines.append(f"#EXTINF:-1,{channel_name}")

                m3u_lines.append(url)
        
        return '\n'.join(m3u_lines)


def main():
    """Función principal"""
    logger.info("=" * 80)
    logger.info(" 🏆 PLATINSPORT ULTIMATE SCRAPER 🏆")
    logger.info("=" * 80)
    
    scraper = UltimatePlatinSportScraper()
    result = scraper.scrape()
    
    if result:
        # Generar M3U
        m3u_content = scraper.generate_m3u(result)
        
        if m3u_content:
            output_file = "platinsport_ultimate.m3u"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(m3u_content)
            
            logger.info(f"\n💾 ARCHIVO M3U GUARDADO: {output_file}")
            
            # Contar líneas en M3U
            lines = m3u_content.split('\n')
            entry_count = sum(1 for line in lines if line.startswith('#EXTINF'))
            
            logger.info(f"📄 Entradas en M3U: {entry_count}")
            logger.info("=" * 80)
            logger.info("✅ SCRAPING COMPLETADO CON ÉXITO")
            logger.info("=" * 80)
        else:
            logger.error("\n❌ Error generando archivo M3U")
    else:
        logger.error("\n❌ Error durante el scraping")


if __name__ == "__main__":
    main()

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
import os

# Deshabilitar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_event_datetime(fecha_str, hora_str):
    """Parsea fecha y hora de evento y las convierte a datetime"""
    try:
        meses = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }

        parts = fecha_str.lower().split()
        if len(parts) >= 3 and parts[1] == 'de':
            dia = int(parts[0])
            mes_str = parts[2]
            mes = meses.get(mes_str, 6)
            año = datetime.now().year

            if ':' in hora_str:
                hora_parts = hora_str.split(':')
                hora = int(hora_parts[0])
                minuto = int(hora_parts[1])

                return datetime(año, mes, dia, hora, minuto)

        return None
    except Exception:
        return None

def is_near_current_time(event_datetime, threshold_hours=3):
    """Determina si un evento está cerca de la hora actual"""
    if not event_datetime:
        return False

    current_time = datetime.now()
    time_diff = abs((event_datetime - current_time).total_seconds() / 3600)
    return time_diff <= threshold_hours

def is_valid_stream_url_improved(url):
    """Versión mejorada de validación de URLs de streaming"""
    if not url or not isinstance(url, str):
        return False

    url_lower = url.lower()

    exclude_patterns = [
        r'facebook\.com/share', r'twitter\.com/home', r'plus\.google\.com/share',
        r'livescore', r'\.css', r'\.js', r'\.png', r'\.jpg', r'\.gif',
        r'/share', r'/login', r'/register'
    ]

    for pattern in exclude_patterns:
        if re.search(pattern, url_lower):
            return False

    streaming_patterns = [
        r'youtube\.com/(watch|embed)', r'youtu\.be/', r'twitch\.tv/(embed|[^/]+$)',
        r'dailymotion\.com/(embed|video)', r'vimeo\.com/(video/)?[0-9]+',
        r'facebook\.com/.+/videos/[0-9]+', r'\.m3u8', r'\.mpd', r'\.mp4',
        r'stream[0-9]*\.', r'live[0-9]*\.', r'player[0-9]*\.',
        r'embed\.', r'/embed/', r'/player/', r'/live/', r'/stream/',
        r'webplayer\.php'
    ]

    return any(re.search(pattern, url_lower) for pattern in streaming_patterns)

def detect_platform_improved(url):
    """Versión mejorada de detección de plataforma"""
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower or 't=youtube' in url_lower:
        return 'youtube'
    elif 'twitch.tv' in url_lower or 't=twitch' in url_lower:
        return 'twitch'
    elif 'dailymotion.com' in url_lower or 't=dailymotion' in url_lower:
        return 'dailymotion'
    elif 'vimeo.com' in url_lower or 't=vimeo' in url_lower:
        return 'vimeo'
    elif 'facebook.com' in url_lower and 'videos' in url_lower:
        return 'facebook'
    elif '.m3u8' in url_lower or 't=hls' in url_lower:
        return 'hls'
    elif '.mpd' in url_lower or 't=dash' in url_lower:
        return 'dash'
    elif 'webplayer.php' in url_lower:
        return 'webplayer'
    elif 'cdn.' in url_lower or 'stream' in url_lower:
        return 'cdn_stream'
    else:
        return 'unknown'

def process_iframe_url(src, base_url):
    """Procesa y normaliza URLs de iframe"""
    if not src:
        return None

    if src.startswith('//'):
        src = 'https:' + src
    elif src.startswith('/'):
        parsed_base = urllib.parse.urlparse(base_url)
        src = f'{parsed_base.scheme}://{parsed_base.netloc}{src}'
    elif not src.startswith('http'):
        parsed_base = urllib.parse.urlparse(base_url)
        src = f'{parsed_base.scheme}://{parsed_base.netloc}/{src}'

    return src

def extract_iframe_from_webplayer(webplayer_url, timeout=10):
    """Extrae iframe real desde una URL de webplayer"""
    iframes_found = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.5',
            'Referer': 'https://livetv.sx/',
            'Connection': 'keep-alive',
        }

        session = requests.Session()
        session.verify = False
        
        response = session.get(webplayer_url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            return iframes_found

        soup = BeautifulSoup(response.content, 'html.parser')
        
        iframes = soup.find_all('iframe')
        
        for iframe in iframes:
            src = iframe.get('src') or iframe.get('data-src')
            if src:
                processed_url = process_iframe_url(src, webplayer_url)
                if processed_url and not processed_url.startswith(webplayer_url):
                    platform = detect_platform_improved(processed_url)
                    iframes_found.append({
                        'url': processed_url,
                        'platform': platform,
                        'source': 'webplayer_iframe',
                        'type': 'iframe_extracted'
                    })
        
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                js_urls = re.findall(r'["\']https?://[^"\']+["\']', script.string)
                for url_match in js_urls:
                    clean_url = url_match.strip('"\'')
                    if is_valid_stream_url_improved(clean_url) and 'webplayer.php' not in clean_url:
                        platform = detect_platform_improved(clean_url)
                        iframes_found.append({
                            'url': clean_url,
                            'platform': platform,
                            'source': 'webplayer_javascript',
                            'type': 'js_extracted'
                        })
        
        print(f"    -> Webplayer procesado: {len(iframes_found)} streams extraídos")
        
    except Exception as e:
        print(f"    -> Error procesando webplayer: {e}")
    
    return iframes_found

def extract_streaming_urls_final(page_url, timeout=15):
    """Versión final de extracción de URLs de streaming"""
    streams = []

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.5',
            'Referer': 'https://livetv.sx/',
            'Connection': 'keep-alive',
        }

        session = requests.Session()
        session.verify = False

        response = session.get(page_url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            return streams

        soup = BeautifulSoup(response.content, 'html.parser')

        containers = []

        links_block = soup.find(id='links_block')
        if links_block:
            containers.append(('links_block', links_block))

        for selector in ['.links', '.streams', '.player-links', '.broadcast-links', '.live-links']:
            elements = soup.select(selector)
            for elem in elements:
                containers.append((selector, elem))

        if not containers:
            containers.append(('full_page', soup))

        for container_name, container in containers:
            iframes = container.find_all('iframe')

            for iframe in iframes:
                src = iframe.get('src') or iframe.get('data-src')
                if src:
                    processed_url = process_iframe_url(src, page_url)
                    if processed_url and is_valid_stream_url_improved(processed_url):
                        if 'webplayer.php' in processed_url:
                            webplayer_streams = extract_iframe_from_webplayer(processed_url)
                            streams.extend(webplayer_streams)
                        else:
                            platform = detect_platform_improved(processed_url)
                            streams.append({
                                'url': processed_url,
                                'platform': platform,
                                'source': f'iframe_{container_name}',
                                'type': 'iframe'
                            })

            links = container.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and is_valid_stream_url_improved(href):
                    processed_url = process_iframe_url(href, page_url)
                    if 'webplayer.php' in processed_url:
                        webplayer_streams = extract_iframe_from_webplayer(processed_url)
                        streams.extend(webplayer_streams)
                    else:
                        platform = detect_platform_improved(processed_url)
                        streams.append({
                            'url': processed_url,
                            'platform': platform,
                            'source': f'link_{container_name}',
                            'type': 'link'
                        })

        unique_streams = []
        seen_urls = set()
        for stream in streams:
            if stream['url'] not in seen_urls:
                unique_streams.append(stream)
                seen_urls.add(stream['url'])

        return unique_streams

    except Exception as e:
        print(f"Error: {e}")
        return streams

def extract_youtube_id_from_stream(stream_url):
    """Extrae ID de YouTube si está disponible en el stream"""
    patterns = [
        r'[?&]c=([a-zA-Z0-9_-]+)',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'youtu\.be/([a-zA-Z0-9_-]+)',
        r'youtube\.com/embed/([a-zA-Z0-9_-]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, stream_url)
        if match:
            return match.group(1)
    return None

def process_extracted_streams(streams, event_datetime, current_time):
    """Procesa streams extraídos y determina tipo (live/highlight)"""
    processed_streams = []

    for stream in streams:
        platform = detect_platform_improved(stream['url'])
        is_near_time = is_near_current_time(event_datetime, threshold_hours=2)
        stream_type = 'live' if is_near_time else 'highlight'

        youtube_id = extract_youtube_id_from_stream(stream['url'])

        processed_stream = {
            'url': stream['url'],
            'platform': platform,
            'type': stream_type,
            'source': stream.get('source', 'unknown'),
            'extraction_method': stream.get('type', 'unknown')
        }

        if youtube_id:
            processed_stream['youtube_id'] = youtube_id
            processed_stream['youtube_url'] = f'https://www.youtube.com/watch?v={youtube_id}'

        processed_streams.append(processed_stream)

    return processed_streams

def create_enhanced_xml(root_xml):
    """Crea XML mejorado con streams extraídos - SIN LÍMITE DE EVENTOS"""

    new_root = ET.Element('eventos_con_streams')
    new_root.set('generado', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    new_root.set('version', '2.0')
    new_root.set('procesamiento', 'ilimitado')

    eventos_procesados = 0
    eventos_con_streams = 0
    total_streams = 0
    
    total_eventos = len(root_xml.findall('evento'))
    print(f"Procesando TODOS los eventos ({total_eventos})...")

    for i, evento in enumerate(root_xml.findall('evento')):
        try:
            nombre = evento.find('nombre').text if evento.find('nombre') is not None else ""
            deporte = evento.find('deporte').text if evento.find('deporte') is not None else ""
            competicion = evento.find('competicion').text if evento.find('competicion') is not None else ""
            fecha = evento.find('fecha').text if evento.find('fecha') is not None else ""
            hora = evento.find('hora').text if evento.find('hora') is not None else ""
            url = evento.find('url').text if evento.find('url') is not None else ""

            if not url or not nombre:
                continue

            event_datetime = parse_event_datetime(fecha, hora)

            nuevo_evento = ET.SubElement(new_root, 'evento')
            nuevo_evento.set('id', str(eventos_procesados + 1))

            ET.SubElement(nuevo_evento, 'nombre').text = nombre
            ET.SubElement(nuevo_evento, 'deporte').text = deporte
            ET.SubElement(nuevo_evento, 'competicion').text = competicion
            ET.SubElement(nuevo_evento, 'fecha').text = fecha
            ET.SubElement(nuevo_evento, 'hora').text = hora
            ET.SubElement(nuevo_evento, 'url').text = url

            if event_datetime:
                ET.SubElement(nuevo_evento, 'datetime_iso').text = event_datetime.isoformat()
                is_near = is_near_current_time(event_datetime)
                ET.SubElement(nuevo_evento, 'cerca_hora_actual').text = str(is_near)

            porcentaje = (eventos_procesados + 1) / total_eventos * 100
            print(f"  {eventos_procesados + 1}/{total_eventos} ({porcentaje:.1f}%): {nombre[:50]}{'...' if len(nombre) > 50 else ''}")

            streams = extract_streaming_urls_final(url)
            processed_streams = process_extracted_streams(streams, event_datetime, datetime.now())

            streams_element = ET.SubElement(nuevo_evento, 'streams')
            streams_element.set('total', str(len(processed_streams)))

            for stream in processed_streams:
                stream_element = ET.SubElement(streams_element, 'stream')
                ET.SubElement(stream_element, 'url').text = stream['url']
                ET.SubElement(stream_element, 'plataforma').text = stream['platform']
                ET.SubElement(stream_element, 'tipo').text = stream['type']
                ET.SubElement(stream_element, 'fuente').text = stream['source']
                ET.SubElement(stream_element, 'metodo_extraccion').text = stream['extraction_method']

                if 'youtube_url' in stream:
                    ET.SubElement(stream_element, 'youtube_url').text = stream['youtube_url']
                    ET.SubElement(stream_element, 'youtube_id').text = stream.get('youtube_id', '')

            if processed_streams:
                eventos_con_streams += 1
                total_streams += len(processed_streams)
                print(f"    -> {len(processed_streams)} streams encontrados")
            else:
                print(f"    -> Sin streams")

            eventos_procesados += 1
            time.sleep(0.2)

        except Exception as e:
            print(f"    -> Error en evento {eventos_procesados + 1}: {e}")
            continue

    stats = ET.SubElement(new_root, 'estadisticas')
    ET.SubElement(stats, 'eventos_procesados').text = str(eventos_procesados)
    ET.SubElement(stats, 'eventos_con_streams').text = str(eventos_con_streams)
    ET.SubElement(stats, 'total_streams').text = str(total_streams)
    ET.SubElement(stats, 'fecha_procesamiento').text = datetime.now().isoformat()
    ET.SubElement(stats, 'procesamiento_completo').text = 'true'

    return new_root, {
        'eventos_procesados': eventos_procesados,
        'eventos_con_streams': eventos_con_streams,
        'total_streams': total_streams
    }

def save_enhanced_xml(xml_root, filename):
    """Guarda XML con formato mejorado"""
    xml_str = ET.tostring(xml_root, encoding='unicode', method='xml')

    from xml.dom import minidom
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ', encoding=None)

    lines = pretty_xml.split('\n')
    cleaned_lines = [line for line in lines if line.strip()]
    final_xml = '\n'.join(cleaned_lines)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(final_xml)

    return filename

def main():
    """Función principal"""
    print("=== EXTRACTOR DE STREAMS LIVETV.SX - GITHUB ACTIONS ===")
    print("✓ Procesamiento ILIMITADO de eventos")
    print("✓ Extracción mejorada de iframes desde webplayers")
    print(f"Iniciando procesamiento: {datetime.now()}")

    xml_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml"

    try:
        response = requests.get(xml_url, timeout=30)
        response.raise_for_status()
        xml_content = response.text
        print(f"XML descargado: {len(xml_content)} caracteres")

        root = ET.fromstring(xml_content)
        total_eventos = len(root.findall('evento'))
        print(f"Total eventos a procesar: {total_eventos}")

    except Exception as e:
        print(f"Error al descargar XML: {e}")
        return

    enhanced_xml, stats = create_enhanced_xml(root)

    # Nombre específico solicitado
    output_filename = 'eventos_livetv_sx_con_reproductores.xml'
    save_enhanced_xml(enhanced_xml, output_filename)

    summary_data = {
        'fecha_procesamiento': datetime.now().isoformat(),
        'version': '2.0',
        'github_actions': True,
        'estadisticas': stats,
        'archivo_generado': output_filename
    }

    with open('resumen_procesamiento.json', 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    print(f"\n=== PROCESAMIENTO COMPLETADO ===")
    print(f"✓ Eventos procesados: {stats['eventos_procesados']}")
    print(f"✓ Eventos con streams: {stats['eventos_con_streams']}")  
    print(f"✓ Total streams extraídos: {stats['total_streams']}")
    print(f"✓ Archivo generado: {output_filename}")

if __name__ == "__main__":
    main()

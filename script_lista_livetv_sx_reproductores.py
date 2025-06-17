import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import json
import time
import re
from urllib.parse import urljoin, urlparse
import warnings
import ssl
from bs4 import BeautifulSoup

warnings.filterwarnings('ignore')
ssl._create_default_https_context = ssl._create_unverified_context

def obtener_eventos_xml():
    """Descarga y parsea el XML fuente"""
    url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        return root
    except Exception as e:
        print(f"Error al obtener XML: {e}")
        return None

def filtrar_eventos_hoy(root):
    """Filtra eventos del día actual"""
    eventos_hoy = []
    fecha_hoy = datetime.now().strftime("%d de %B").replace("June", "junio").replace("December", "diciembre")

    # Mapeo de meses en inglés a español
    meses_map = {
        "January": "enero", "February": "febrero", "March": "marzo", "April": "abril",
        "May": "mayo", "June": "junio", "July": "julio", "August": "agosto",
        "September": "septiembre", "October": "octubre", "November": "noviembre", "December": "diciembre"
    }

    fecha_actual = datetime.now()
    dia = fecha_actual.day
    mes_ingles = fecha_actual.strftime("%B")
    mes_español = meses_map.get(mes_ingles, mes_ingles.lower())
    fecha_buscar = f"{dia} de {mes_español}"

    for evento in root.findall('evento'):
        fecha_elem = evento.find('fecha')
        if fecha_elem is not None and fecha_elem.text == fecha_buscar:
            eventos_hoy.append(evento)

    return eventos_hoy

def extraer_streams_evento(url):
    """Extrae streams de un evento específico con búsqueda de iframes ocultos y idiomas"""
    streams = []

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        links_block = soup.find(id='links_block')

        if links_block:
            enlaces = links_block.find_all('a', href=True)

            for i, enlace in enumerate(enlaces):
                href = enlace.get('href')
                if href:
                    if href.startswith('/'):
                        href = urljoin(url, href)
                    elif not href.startswith('http'):
                        href = urljoin(url, href)

                    # Extraer idioma usando el selector específico (ajustado aquí)
                    idioma_img = extraer_idioma_stream(soup, i)
                    
                    iframe_url = extraer_iframe_real(href)
                    if iframe_url:
                        stream_data = {
                            'url': iframe_url,
                            'idioma': idioma_img
                        }
                        streams.append(stream_data)

            # MEJORA 1: Buscar iframes adicionales que puedan estar ocultos
            iframes_ocultos = buscar_iframes_ocultos(soup, url)
            for iframe_oculto in iframes_ocultos:
                # Evitar duplicados
                if not any(stream['url'] == iframe_oculto['url'] for stream in streams):
                    streams.append(iframe_oculto)

        return streams

    except Exception as e:
        print(f"Error al extraer streams de {url}: {e}")
        return []

def buscar_iframes_ocultos(soup, base_url):
    """MEJORA 1: Busca iframes adicionales que puedan estar ocultos"""
    iframes_ocultos = []
    
    try:
        # Buscar iframes directamente en el HTML que puedan estar ocultos
        all_iframes = soup.find_all('iframe', src=True)
        
        for iframe in all_iframes:
            src = iframe.get('src')
            if src and ('embed' in src or 'player' in src or 'stream' in src):
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                
                iframe_data = {
                    'url': src,
                    'idioma': ''  # No hay información de idioma para iframes ocultos
                }
                iframes_ocultos.append(iframe_data)

        # Buscar scripts que puedan contener URLs de iframes
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Buscar URLs de embed en el JavaScript
                iframe_urls = re.findall(r'["\']https?://[^"\']*(?:embed|player|stream)[^"\']*["\']', script.string)
                for url_match in iframe_urls:
                    clean_url = url_match.strip('"\'')
                    iframe_data = {
                        'url': clean_url,
                        'idioma': ''
                    }
                    iframes_ocultos.append(iframe_data)

    except Exception as e:
        print(f"Error buscando iframes ocultos: {e}")
    
    return iframes_ocultos

def extraer_idioma_stream(soup, stream_index):
    """Extrae la imagen de bandera del idioma usando el selector específico"""
    try:
        # El primer stream está en tr:nth-child(2), el segundo en tr:nth-child(3), etc.
        selector = f"#links_block > table:nth-child(2) > tbody > tr:nth-child({stream_index+2}) > td:nth-child(1) > table > tbody > tr > td:nth-child(1) > img"
        img_element = soup.select_one(selector)
        if img_element and img_element.get('src'):
            src = img_element.get('src')
            # Si ya es una url absoluta del CDN, solo asegúrate que lleva https:
            if "cdn.livetv853.me" in src:
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("http"):
                    pass  # Ya está bien
                else:
                    src = "https://" + src.lstrip("/")
                return src
            # Convertir URL relativa a absoluta si es necesario
            if src.startswith("/"):
                src = 'https://livetv.sx' + src
            elif src.startswith("//"):
                src = 'https:' + src
            return src

        return ''
    except Exception as e:
        return ''

def extraer_iframe_real(stream_url):
    """Extrae el iframe real de una URL de stream"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }

        response = requests.get(stream_url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        iframes = soup.find_all('iframe', src=True)

        for iframe in iframes:
            src = iframe.get('src')
            if src and ('antenasport' in src or 'embed' in src or 'player' in src or 'stream' in src):
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(stream_url, src)
                return src

        if iframes:
            src = iframes[0].get('src')
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(stream_url, src)
            return src

        return None

    except Exception as e:
        return None

def convertir_a_datetime_iso(fecha_str, hora_str):
    """Convierte fecha y hora en formato español a datetime ISO"""
    try:
        meses = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }

        partes_fecha = fecha_str.split(' de ')
        if len(partes_fecha) == 2:
            dia = int(partes_fecha[0])
            mes_nombre = partes_fecha[1].lower()
            mes = meses.get(mes_nombre, 6)
            año = datetime.now().year

            if ':' in hora_str:
                hora_partes = hora_str.split(':')
                hora = int(hora_partes[0])
                minuto = int(hora_partes[1])
            else:
                hora = 0
                minuto = 0

            dt = datetime(año, mes, dia, hora, minuto)
            return dt.strftime('%Y-%m-%dT%H:%M:%S')

        return f"{datetime.now().year}-{datetime.now().month:02d}-{datetime.now().day:02d}T00:00:00"

    except Exception as e:
        return f"{datetime.now().year}-{datetime.now().month:02d}-{datetime.now().day:02d}T00:00:00"

def procesar_todos_los_eventos(eventos_hoy, max_eventos=None):
    """Procesa todos los eventos del día y extrae sus streams"""
    eventos_procesados = []
    total_eventos = len(eventos_hoy) if max_eventos is None else min(len(eventos_hoy), max_eventos)

    print(f"Procesando {total_eventos} eventos...")

    for i, evento in enumerate(eventos_hoy[:total_eventos]):
        try:
            nombre = evento.find('nombre').text if evento.find('nombre') is not None else "N/A"
            deporte = evento.find('deporte').text if evento.find('deporte') is not None else "N/A"
            competicion = evento.find('competicion').text if evento.find('competicion') is not None else "N/A"
            fecha = evento.find('fecha').text if evento.find('fecha') is not None else ""
            hora = evento.find('hora').text if evento.find('hora') is not None else "00:00"
            url = evento.find('url').text if evento.find('url') is not None else ""

            print(f"Procesando evento {i+1}/{total_eventos}: {nombre}")

            streams = extraer_streams_evento(url)
            datetime_iso = convertir_a_datetime_iso(fecha, hora)

            evento_procesado = {
                'id': i + 1,
                'nombre': nombre,
                'deporte': deporte,
                'competicion': competicion,
                'fecha': fecha,
                'hora': hora,
                'url': url,
                'datetime_iso': datetime_iso,
                'streams': streams
            }

            eventos_procesados.append(evento_procesado)
            print(f"Evento {i+1} procesado: {len(streams)} streams encontrados")

            time.sleep(1)  # Pausa para no sobrecargar el servidor

        except Exception as e:
            print(f"Error procesando evento {i+1}: {e}")
            continue

    # MEJORA 3: Ordenar eventos por orden cronológico
    eventos_procesados.sort(key=lambda x: x['datetime_iso'])
    
    # Reasignar IDs después del ordenamiento
    for i, evento in enumerate(eventos_procesados):
        evento['id'] = i + 1

    return eventos_procesados

def generar_xml_final(eventos_procesados):
    """Genera el XML final con la estructura solicitada incluyendo idiomas"""
    root = ET.Element("eventos")
    root.set("generado", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set("total", str(len(eventos_procesados)))

    for evento_data in eventos_procesados:
        evento_elem = ET.SubElement(root, "evento")
        evento_elem.set("id", str(evento_data['id']))

        nombre_elem = ET.SubElement(evento_elem, "nombre")
        nombre_elem.text = evento_data['nombre']

        deporte_elem = ET.SubElement(evento_elem, "deporte")
        deporte_elem.text = evento_data['deporte']

        competicion_elem = ET.SubElement(evento_elem, "competicion")
        competicion_elem.text = evento_data['competicion']

        fecha_elem = ET.SubElement(evento_elem, "fecha")
        fecha_elem.text = evento_data['fecha']

        hora_elem = ET.SubElement(evento_elem, "hora")
        hora_elem.text = evento_data['hora']

        url_elem = ET.SubElement(evento_elem, "url")
        url_elem.text = evento_data['url']

        datetime_iso_elem = ET.SubElement(evento_elem, "datetime_iso")
        datetime_iso_elem.text = evento_data['datetime_iso']

        streams_elem = ET.SubElement(evento_elem, "streams")
        streams_elem.set("total", str(len(evento_data['streams'])))

        for stream_data in evento_data['streams']:
            stream_elem = ET.SubElement(streams_elem, "stream")
            
            url_stream_elem = ET.SubElement(stream_elem, "url")
            if isinstance(stream_data, dict):
                url_stream_elem.text = stream_data['url']
                
                # MEJORA 2: Agregar elemento idioma con la URL de la imagen
                if stream_data.get('idioma'):
                    idioma_elem = ET.SubElement(stream_elem, "idioma")
                    idioma_elem.text = stream_data['idioma']
            else:
                # Compatibilidad con streams antiguos (solo URL)
                url_stream_elem.text = stream_data

    return root

def formatear_xml(elem, level=0):
    """Formatea XML con indentación apropiada"""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            formatear_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def main():
    """Función principal"""
    print("=== EXTRACTOR DE EVENTOS DEPORTIVOS LIVETV.SX ===")
    print(f"Ejecutado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Paso 1: Descargar XML fuente
    print("1. Descargando XML fuente...")
    xml_root = obtener_eventos_xml()
    if xml_root is None:
        print("❌ Error: No se pudo descargar el XML fuente")
        return

    print(f"✅ XML descargado. Total eventos: {xml_root.get('total', 'N/A')}")

    # Paso 2: Filtrar eventos del día
    print("\n2. Filtrando eventos del día actual...")
    eventos_hoy = filtrar_eventos_hoy(xml_root)
    print(f"✅ Eventos encontrados para hoy: {len(eventos_hoy)}")

    if not eventos_hoy:
        print("⚠️  No hay eventos para procesar hoy")
        return

    # Paso 3: Procesar eventos
    print("\n3. Procesando eventos y extrayendo streams...")
    eventos_procesados = procesar_todos_los_eventos(eventos_hoy)
    print(f"✅ Total eventos procesados: {len(eventos_procesados)}")

    # Paso 4: Generar XML final
    print("\n4. Generando XML final...")
    xml_final = generar_xml_final(eventos_procesados)
    formatear_xml(xml_final)

    # Guardar archivo
    output_path = 'eventos_livetv_sx_con_reproductores.xml'
    tree = ET.ElementTree(xml_final)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)

    print(f"✅ XML generado exitosamente: {output_path}")
    print(f"📊 Resumen: {len(eventos_procesados)} eventos procesados")

    # Mostrar estadísticas
    total_streams = sum(len(evento['streams']) for evento in eventos_procesados)
    print(f"📺 Total streams encontrados: {total_streams}")

    print("\n🎉 Proceso completado exitosamente!")

if __name__ == "__main__":
    main()

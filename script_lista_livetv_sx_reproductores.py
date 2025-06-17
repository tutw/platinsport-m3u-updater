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

def extraer_iframe_real_con_idioma(stream_url, evento_url):
    """Extrae el iframe real y el idioma (bandera) de una URL de stream - MEJORA 2"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }

        response = requests.get(stream_url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # MEJORA 2: Extraer idioma de la bandera usando el selector específico
        idioma_url = None
        try:
            # Selector específico para la bandera del idioma
            bandera_img = soup.select_one("#links_block > table:nth-child(2) > tbody > tr:nth-child(2) > td:nth-child(1) > table > tbody > tr > td:nth-child(1) > img")
            if bandera_img and bandera_img.get('src'):
                idioma_url = bandera_img.get('src')
                # Convertir a URL absoluta si es necesaria
                if idioma_url.startswith('//'):
                    idioma_url = 'https:' + idioma_url
                elif idioma_url.startswith('/'):
                    idioma_url = urljoin(evento_url, idioma_url)
                elif not idioma_url.startswith('http'):
                    idioma_url = urljoin(evento_url, idioma_url)
        except Exception as e:
            # Si falla la extracción de idioma, continuamos sin él
            pass

        # Extraer iframe (lógica original)
        iframes = soup.find_all('iframe', src=True)

        for iframe in iframes:
            src = iframe.get('src')
            if src and ('antenasport' in src or 'embed' in src or 'player' in src or 'stream' in src):
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(stream_url, src)
                return src, idioma_url

        if iframes:
            src = iframes[0].get('src')
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(stream_url, src)
            return src, idioma_url

        return None, idioma_url

    except Exception as e:
        return None, None

def extraer_iframe_real(stream_url):
    """Función original mantenida para compatibilidad"""
    iframe_url, _ = extraer_iframe_real_con_idioma(stream_url, stream_url)
    return iframe_url

def extraer_streams_evento(url):
    """Extrae streams de un evento específico - MEJORADO con búsqueda de iframes ocultos - MEJORA 1"""
    streams = []
    idiomas = []  # Lista para almacenar idiomas correspondientes

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
            # MEJORA 1: Buscar enlaces directos
            enlaces = links_block.find_all('a', href=True)

            for enlace in enlaces:
                href = enlace.get('href')
                if href:
                    if href.startswith('/'):
                        href = urljoin(url, href)
                    elif not href.startswith('http'):
                        href = urljoin(url, href)

                    # MEJORA 1: Extraer idioma y iframe
                    iframe_url, idioma_url = extraer_iframe_real_con_idioma(href, url)
                    if iframe_url:
                        streams.append(iframe_url)
                        idiomas.append(idioma_url)

            # MEJORA 1: Buscar iframes ocultos adicionales en el bloque de enlaces
            iframes_ocultos = links_block.find_all('iframe', src=True)
            for iframe in iframes_ocultos:
                src = iframe.get('src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(url, src)

                    if src not in streams:  # Evitar duplicados
                        streams.append(src)
                        idiomas.append(None)  # No hay idioma asociado para iframes directos

            # MEJORA 1: Buscar más iframes en elementos ocultos (display:none, visibility:hidden)
            elementos_ocultos = soup.find_all(style=re.compile(r'display\s*:\s*none|visibility\s*:\s*hidden'))
            for elemento in elementos_ocultos:
                iframes_en_oculto = elemento.find_all('iframe', src=True)
                for iframe in iframes_en_oculto:
                    src = iframe.get('src')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = urljoin(url, src)

                        if src not in streams:  # Evitar duplicados
                            streams.append(src)
                            idiomas.append(None)

        return streams, idiomas

    except Exception as e:
        print(f"Error al extraer streams de {url}: {e}")
        return [], []

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
    """Procesa todos los eventos del día y extrae sus streams con idiomas - MEJORADO"""
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

            # MEJORA: Usar la función mejorada que devuelve streams e idiomas
            streams, idiomas = extraer_streams_evento(url)

            # Combinar streams únicos con sus idiomas correspondientes
            streams_con_idiomas = []
            streams_unicos = []

            for j, stream in enumerate(streams):
                if stream not in streams_unicos:  # Evitar duplicados
                    streams_unicos.append(stream)
                    idioma = idiomas[j] if j < len(idiomas) else None
                    streams_con_idiomas.append({
                        'url': stream,
                        'idioma': idioma
                    })

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
                'streams': streams_unicos,  # Para compatibilidad con código existente
                'streams_con_idiomas': streams_con_idiomas  # Nueva estructura con idiomas
            }

            eventos_procesados.append(evento_procesado)
            print(f"Evento {i+1} procesado: {len(streams_unicos)} streams únicos")

            time.sleep(1)  # Pausa para no sobrecargar el servidor

        except Exception as e:
            print(f"Error procesando evento {i+1}: {e}")
            continue

    return eventos_procesados

def generar_xml_final(eventos_procesados):
    """Genera el XML final con ordenación cronológica y idiomas - MEJORA 3"""

    # MEJORA 3: Ordenar eventos cronológicamente
    def obtener_datetime_para_ordenar(evento):
        try:
            return datetime.fromisoformat(evento['datetime_iso'])
        except:
            return datetime.min  # Si hay error, ponerlo al principio

    eventos_ordenados = sorted(eventos_procesados, key=obtener_datetime_para_ordenar)
    print(f"✅ Eventos ordenados cronológicamente: {len(eventos_ordenados)}")

    root = ET.Element("eventos")
    root.set("generado", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set("total", str(len(eventos_ordenados)))

    # Reasignar IDs después del ordenamiento
    for i, evento_data in enumerate(eventos_ordenados):
        evento_elem = ET.SubElement(root, "evento")
        evento_elem.set("id", str(i + 1))  # ID secuencial tras ordenamiento

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

        # MEJORA 2: Usar streams con idiomas si están disponibles
        if 'streams_con_idiomas' in evento_data and evento_data['streams_con_idiomas']:
            streams_elem = ET.SubElement(evento_elem, "streams")
            streams_elem.set("total", str(len(evento_data['streams_con_idiomas'])))

            for stream_data in evento_data['streams_con_idiomas']:
                stream_elem = ET.SubElement(streams_elem, "stream")

                url_stream_elem = ET.SubElement(stream_elem, "url")
                url_stream_elem.text = stream_data['url']

                # MEJORA 2: Agregar idioma si está disponible
                if stream_data['idioma']:
                    idioma_elem = ET.SubElement(stream_elem, "idioma")
                    idioma_elem.text = stream_data['idioma']
        else:
            # Fallback a estructura original si no hay streams con idiomas
            streams_elem = ET.SubElement(evento_elem, "streams")
            streams_elem.set("total", str(len(evento_data['streams'])))

            for stream_url in evento_data['streams']:
                stream_elem = ET.SubElement(streams_elem, "stream")
                url_stream_elem = ET.SubElement(stream_elem, "url")
                url_stream_elem.text = stream_url

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
    """Función principal - VERSIÓN MEJORADA con todas las mejoras"""
    print("=== EXTRACTOR DE EVENTOS DEPORTIVOS LIVETV.SX (MEJORADO) ===")
    print(f"Ejecutado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("🚀 MEJORAS IMPLEMENTADAS:")
    print("   1. Búsqueda de iframes ocultos")
    print("   2. Extracción de idiomas con banderas")
    print("   3. Ordenación cronológica de eventos")
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

    # Paso 3: Procesar eventos (CON MEJORAS)
    print("\n3. Procesando eventos y extrayendo streams (CON MEJORAS)...")
    eventos_procesados = procesar_todos_los_eventos(eventos_hoy)
    print(f"✅ Total eventos procesados: {len(eventos_procesados)}")

    # Paso 4: Generar XML final (CON MEJORAS)
    print("\n4. Generando XML final (CON MEJORAS)...")
    xml_final = generar_xml_final(eventos_procesados)
    formatear_xml(xml_final)

    # Guardar archivo
    output_path = 'eventos_livetv_sx_con_reproductores_mejorado.xml'
    tree = ET.ElementTree(xml_final)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)

    print(f"✅ XML generado exitosamente: {output_path}")
    print(f"📊 Resumen: {len(eventos_procesados)} eventos procesados")

    # Mostrar estadísticas mejoradas
    total_streams = sum(len(evento['streams']) for evento in eventos_procesados)
    total_streams_con_idioma = sum(
        len([s for s in evento.get('streams_con_idiomas', []) if s.get('idioma')])
        for evento in eventos_procesados
    )

    print(f"📺 Total streams encontrados: {total_streams}")
    print(f"🌍 Streams con idioma identificado: {total_streams_con_idioma}")
    print(f"🔍 Streams con iframes ocultos encontrados: {total_streams - len(eventos_procesados)}")

    print("\n🎉 Proceso completado exitosamente con todas las mejoras!")
    print("\n📋 MEJORAS APLICADAS:")
    print("   ✅ Búsqueda ampliada de iframes (incluyendo ocultos)")
    print("   ✅ Extracción de idiomas mediante banderas")
    print("   ✅ Ordenación cronológica automática")

if __name__ == "__main__":
    main()

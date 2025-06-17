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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os

warnings.filterwarnings('ignore')
ssl._create_default_https_context = ssl._create_unverified_context

def configurar_driver():
    """Configura el driver de Selenium"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-plugins')
    chrome_options.add_argument('--disable-images')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error configurando driver: {e}")
        return None

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

def extraer_streams_con_selenium(url, driver):
    """Extrae streams usando Selenium para manejar JavaScript y elementos ocultos"""
    streams_data = []

    try:
        print(f"Navegando a: {url}")
        driver.get(url)

        # Esperar a que cargue la página
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "links_block"))
        )

        # Buscar el botón para mostrar más enlaces
        try:
            expand_button = driver.find_element(By.CSS_SELECTOR, "#links_block > a")
            if expand_button and expand_button.is_displayed():
                print("Encontrado botón para expandir enlaces ocultos, haciendo clic...")
                driver.execute_script("arguments[0].click();", expand_button)
                time.sleep(2)  # Esperar a que se carguen los enlaces adicionales
        except NoSuchElementException:
            print("No se encontró botón de expansión, continuando con enlaces visibles")

        # Obtener todos los enlaces de streams
        links_block = driver.find_element(By.ID, "links_block")
        enlaces = links_block.find_elements(By.TAG_NAME, "a")

        print(f"Total enlaces encontrados: {len(enlaces)}")

        for i, enlace in enumerate(enlaces):
            try:
                href = enlace.get_attribute('href')
                if href and '/link/' in href:
                    print(f"Procesando enlace {i+1}: {href}")

                    # Extraer stream y datos de idioma
                    stream_data = extraer_stream_individual(href, driver)
                    if stream_data:
                        streams_data.append(stream_data)

            except Exception as e:
                print(f"Error procesando enlace {i+1}: {e}")
                continue

        return streams_data

    except Exception as e:
        print(f"Error extrayendo streams de {url}: {e}")
        return []

def extraer_stream_individual(stream_url, driver):
    """Extrae un stream individual y su información de idioma"""
    try:
        print(f"Extrayendo stream individual: {stream_url}")
        driver.get(stream_url)

        # Esperar a que cargue la página
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Buscar iframe del reproductor
        iframe_url = None
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = iframe.get_attribute('src')
                if src and ('embed' in src or 'player' in src or 'stream' in src):
                    iframe_url = src
                    if src.startswith('//'):
                        iframe_url = 'https:' + src
                    elif src.startswith('/'):
                        iframe_url = urljoin(stream_url, src)
                    break
        except Exception as e:
            print(f"Error buscando iframe: {e}")

        # Buscar imagen de idioma
        idioma_img = None
        try:
            # Intentar varios selectores para la imagen de idioma
            selectores_idioma = [
                "#links_block > table:nth-child(2) > tbody > tr:nth-child(2) > td:nth-child(1) > table > tbody > tr > td:nth-child(1) > img",
                "img[src*='linkflag']",
                "img[src*='flag']",
                "td img[src*='cdn.livetv']"
            ]

            for selector in selectores_idioma:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    idioma_img = img_element.get_attribute('src')
                    if idioma_img:
                        print(f"Imagen de idioma encontrada: {idioma_img}")
                        break
                except NoSuchElementException:
                    continue

        except Exception as e:
            print(f"Error extrayendo imagen de idioma: {e}")

        if iframe_url:
            return {
                'url': iframe_url,
                'idioma': idioma_img or "N/A"
            }

        return None

    except Exception as e:
        print(f"Error en extraer_stream_individual: {e}")
        return None

def extraer_streams_evento(url):
    """Extrae streams de un evento específico usando método tradicional como fallback"""
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

            for enlace in enlaces:
                href = enlace.get('href')
                if href:
                    if href.startswith('/'):
                        href = urljoin(url, href)
                    elif not href.startswith('http'):
                        href = urljoin(url, href)

                    iframe_url = extraer_iframe_real(href)
                    if iframe_url:
                        streams.append({
                            'url': iframe_url,
                            'idioma': 'N/A'  # Método fallback no puede extraer imagen
                        })

        return streams

    except Exception as e:
        print(f"Error al extraer streams de {url}: {e}")
        return []

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

    # Configurar driver de Selenium
    driver = configurar_driver()
    usar_selenium = driver is not None

    if usar_selenium:
        print("✅ Selenium configurado correctamente - usando método avanzado")
    else:
        print("⚠️ Selenium no disponible - usando método tradicional")

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

            # Usar Selenium si está disponible, sino usar método tradicional
            if usar_selenium:
                streams_data = extraer_streams_con_selenium(url, driver)
            else:
                streams_data = extraer_streams_evento(url)

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
                'streams': streams_data
            }

            eventos_procesados.append(evento_procesado)
            print(f"Evento {i+1} procesado: {len(streams_data)} streams encontrados")

            time.sleep(2)  # Pausa para no sobrecargar el servidor

        except Exception as e:
            print(f"Error procesando evento {i+1}: {e}")
            continue

    # Cerrar driver si se usó
    if usar_selenium and driver:
        driver.quit()

    return eventos_procesados

def generar_xml_final(eventos_procesados):
    """Genera el XML final con la estructura solicitada incluyendo imágenes de idioma"""
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
                url_stream_elem.text = stream_data.get('url', '')

                idioma_elem = ET.SubElement(stream_elem, "idioma")
                idioma_elem.text = stream_data.get('idioma', 'N/A')
            else:
                # Compatibilidad con formato anterior
                url_stream_elem.text = str(stream_data)

                idioma_elem = ET.SubElement(stream_elem, "idioma")
                idioma_elem.text = 'N/A'

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

def test_selenium_setup():
    """Prueba la configuración de Selenium"""
    print("🧪 Probando configuración de Selenium...")
    driver = configurar_driver()

    if driver:
        try:
            driver.get("https://www.google.com")
            print("✅ Selenium funcionando correctamente")
            driver.quit()
            return True
        except Exception as e:
            print(f"❌ Error en prueba de Selenium: {e}")
            driver.quit()
            return False
    else:
        print("❌ No se pudo configurar Selenium")
        return False

def main():
    """Función principal"""
    print("=== EXTRACTOR MEJORADO DE EVENTOS DEPORTIVOS LIVETV.SX ===")
    print(f"Ejecutado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Probar Selenium
    selenium_ok = test_selenium_setup()

    if not selenium_ok:
        print("⚠️ Selenium no está disponible. Instalando dependencias...")
        print("Para usar todas las funcionalidades, instala selenium y chromedriver:")
        print("pip install selenium")
        print("Y descarga ChromeDriver desde: https://chromedriver.chromium.org/")
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
        print("⚠️ No hay eventos para procesar hoy")
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
    streams_con_idioma = sum(1 for evento in eventos_procesados 
                           for stream in evento['streams'] 
                           if isinstance(stream, dict) and stream.get('idioma') != 'N/A')

    print(f"📺 Total streams encontrados: {total_streams}")
    print(f"🌍 Streams con información de idioma: {streams_con_idioma}")

    print("\n🎉 Proceso completado exitosamente!")
    print(f"📁 Archivo generado: {output_path}")

if __name__ == "__main__":
    main()

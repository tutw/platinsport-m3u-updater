import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor

URLS = [
    "https://livetv.sx/es/allupcomingsports/1/",
    "https://livetv.sx/es/allupcomingsports/2/",
    "https://livetv.sx/es/allupcomingsports/3/",
    "https://livetv.sx/es/allupcomingsports/4/",
    "https://livetv.sx/es/allupcomingsports/5/",
    "https://livetv.sx/es/allupcomingsports/6/",
    "https://livetv.sx/es/allupcomingsports/7/",
    "https://livetv.sx/es/allupcomingsports/9/",
    "https://livetv.sx/es/allupcomingsports/12/",
    "https://livetv.sx/es/allupcomingsports/13/",
    "https://livetv.sx/es/allupcomingsports/17/",
    "https://livetv.sx/es/allupcomingsports/19/",
    "https://livetv.sx/es/allupcomingsports/23/",
    "https://livetv.sx/es/allupcomingsports/27/",
    "https://livetv.sx/es/allupcomingsports/29/",
    "https://livetv.sx/es/allupcomingsports/30/",
    "https://livetv.sx/es/allupcomingsports/31/",
    "https://livetv.sx/es/allupcomingsports/33/",
    "https://livetv.sx/es/allupcomingsports/37/",
    "https://livetv.sx/es/allupcomingsports/38/",
    "https://livetv.sx/es/allupcomingsports/39/",
    "https://livetv.sx/es/allupcomingsports/40/",
    "https://livetv.sx/es/allupcomingsports/41/",
    "https://livetv.sx/es/allupcomingsports/52/",
    "https://livetv.sx/es/allupcomingsports/66/",
    "https://livetv.sx/es/allupcomingsports/75/",
    "https://livetv.sx/es/allupcomingsports/93/",
]

# Patrón corregido para detectar /es/eventinfo/ID_nombre/ 
PATTERN = re.compile(r"/es/eventinfo/\d+_[^/]+/")

def get_page_source_with_age_confirm(driver, url):
    driver.get(url)
    try:
        btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/table/tbody/tr/td[2]/table/tbody/tr[7]/td/noindex/table/tbody/tr/td[2]/div[2]/table/tr/td[2]/table/tr[3]/td/button[1]'))
        )
        btn.click()
    except Exception as e:
        print(f"No apareció el popup de edad o falló el click en {url}. Error: {e}. Continuando...")

    WebDriverWait(driver, 5).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    return driver.page_source

def extract_event_info(html, link):
    # Escapar el link para usar en regex
    escaped_link = re.escape(link)
    
    # Patrón para extraer el nombre del evento
    event_name_pattern = re.compile(
        r'<a class="live" href="' + escaped_link + r'"[^>]*>(.*?)</a>', 
        re.DOTALL
    )
    
    # Patrón para extraer la información del evento (fecha, hora y liga)
    # Busca el patrón: <span class="evdesc">FECHA a HORA<br>(LIGA)</span>
    evdesc_pattern = re.compile(
        r'<a class="live" href="' + escaped_link + r'"[^>]*>.*?</a>.*?'
        r'<span class="evdesc"[^>]*>(.*?)<br[^>]*>\s*\((.*?)\)</span>', 
        re.DOTALL
    )
    
    # Buscar coincidencias
    event_name_match = event_name_pattern.search(html)
    evdesc_match = evdesc_pattern.search(html)
    
    # Extraer nombre del evento
    if event_name_match:
        event_name = event_name_match.group(1).replace('&ndash;', '-').strip()
        # Limpiar etiquetas HTML del nombre
        event_name = re.sub(r'<[^>]+>', '', event_name)
    else:
        event_name = "Nombre no encontrado"
    
    # Extraer fecha/hora y liga
    if evdesc_match:
        datetime_info = evdesc_match.group(1).strip()
        league = evdesc_match.group(2).strip()
        
        # Limpiar etiquetas HTML de la información de fecha/hora
        datetime_clean = re.sub(r'<[^>]+>', '', datetime_info).strip()
        
        # Separar fecha y hora (formato: "25 de mayo a 21:00")
        if ' a ' in datetime_clean:
            parts = datetime_clean.split(' a ')
            date = parts[0].strip()
            time = parts[1].strip()
        else:
            date = datetime_clean
            time = "Hora no especificada"
    else:
        date = "Fecha no encontrada"
        time = "Hora no encontrada"
        league = "Liga no encontrada"
    
    return event_name, date, time, league

def scrape_links_from_url(driver, url):
    try:
        print(f"Accediendo a: {url}")
        html = get_page_source_with_age_confirm(driver, url)
        matches = PATTERN.findall(html)
        
        if not matches:
            print(f"No se encontraron enlaces en {url}.")
        else:
            print(f"Enlaces encontrados en {url}: {len(matches)}")

        events_info = []
        for link in matches:
            full_url = f"https://livetv.sx{link}"
            event_name, date, time, league = extract_event_info(html, link)
            events_info.append({
                "nombre": event_name,
                "fecha": date,
                "hora": time,
                "liga": league,
                "url": full_url
            })
            print(f"  - {event_name} | {date} {time} | {league}")

        return events_info
    except StaleElementReferenceException:
        print(f"Error de referencia de elemento obsoleto en {url}. Recargando la página...")
        return scrape_links_from_url(driver, url)
    except Exception as e:
        print(f"Error accediendo a {url}: {e}")
        return []

def scrape_links():
    found_events = []
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    with ThreadPoolExecutor(max_workers=5) as executor:
        with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
            futures = [executor.submit(scrape_links_from_url, driver, url) for url in URLS]
            for future in futures:
                found_events.extend(future.result())

    # Eliminar duplicados basados en URL
    unique_events = {event['url']: event for event in found_events}.values()
    return list(unique_events)

def save_to_xml(events, filename="eventos_livetv_sx.xml"):
    root = ET.Element("eventos")
    for event in events:
        evento = ET.SubElement(root, "evento")
        ET.SubElement(evento, "nombre").text = event["nombre"]
        ET.SubElement(evento, "fecha").text = event["fecha"]
        ET.SubElement(evento, "hora").text = event["hora"]
        ET.SubElement(evento, "liga").text = event["liga"]
        ET.SubElement(evento, "url").text = event["url"]

    # Guardado indentado con minidom
    xml_str = ET.tostring(root, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_str)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(parsed_xml.toprettyxml(indent="  "))

if __name__ == "__main__":
    events = scrape_links()
    print(f"\nTotal de eventos únicos encontrados: {len(events)}")
    save_to_xml(events)
    print("Archivo XML guardado como 'eventos_livetv_sx.xml'")

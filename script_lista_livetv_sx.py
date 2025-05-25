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

# Detecta enlaces /es/eventinfo/nnn__/ o similares
PATTERN = re.compile(r'/es/eventinfo/\d+__?/')

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def get_page_source_with_age_confirm(driver, url):
    driver.get(url)
    try:
        btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/table/tbody/tr/td[2]/table/tbody/tr[7]/td/noindex/table/tbody/tr/td[2]/div[2]/table/tr/td[2]/table/tr[3]/td/button[1]'))
        )
        btn.click()
    except Exception:
        # Si no aparece el popup, continuar sin problema
        pass
    WebDriverWait(driver, 5).until(lambda d: d.execute_script('return document.readyState') == 'complete')
    return driver.page_source

def extract_event_info(html, link):
    # Encontrar el bloque <tr> que contiene el enlace
    block_pattern = re.compile(
        r'(<tr.*?>.*?<a class="live" href="' + re.escape(link) + r'".*?</tr>)',
        re.DOTALL
    )
    block_match = block_pattern.search(html)
    if not block_match:
        # Fallback simple
        event_name_pattern = re.compile(r'<a class="live" href="' + re.escape(link) + r'">(.*?)</a>')
        evdesc_pattern = re.compile(r'<span class="evdesc">(.*?)<br>.*?<br>.*?\((.*?)\)</span>')
        event_name_match = event_name_pattern.search(html)
        evdesc_match = evdesc_pattern.search(html)
        event_name = event_name_match.group(1).replace('&ndash;', '-').strip() if event_name_match else "Nombre no encontrado"
        evdesc = evdesc_match.group(1).strip() if evdesc_match else "Fecha y hora no encontradas"
        league = evdesc_match.group(2).strip() if evdesc_match else "Liga no encontrada"
    else:
        block = block_match.group(1)
        event_name_pattern = re.compile(r'<a class="live" href="' + re.escape(link) + r'">(.*?)</a>')
        evdesc_pattern = re.compile(r'<span class="evdesc">(.*?)<br>.*?<br>.*?\((.*?)\)</span>')
        event_name_match = event_name_pattern.search(block)
        evdesc_match = evdesc_pattern.search(block)
        event_name = event_name_match.group(1).replace('&ndash;', '-').strip() if event_name_match else "Nombre no encontrado"
        evdesc = evdesc_match.group(1).strip() if evdesc_match else "Fecha y hora no encontradas"
        league = evdesc_match.group(2).strip() if evdesc_match else "Liga no encontrada"

    evdesc_clean = re.sub(r'<.*?>', '', evdesc)
    date_time = evdesc_clean.split(' a ')
    date = date_time[0].strip() if len(date_time) > 0 else "Fecha no encontrada"
    time = date_time[1].strip() if len(date_time) > 1 else "Hora no encontrada"

    return event_name, date, time, league

def scrape_links_from_url(url):
    driver = get_driver()
    try:
        print(f"Accediendo a: {url}")
        html = get_page_source_with_age_confirm(driver, url)
        matches = PATTERN.findall(html)
        if not matches:
            print(f"No se encontraron enlaces en {url}.")
            return []
        else:
            print(f"Enlaces encontrados en {url}: {len(matches)}")
        events_info = []
        seen_urls = set()
        for link in matches:
            full_url = f"https://livetv.sx{link}"
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            event_name, date, time, league = extract_event_info(html, link)
            events_info.append({
                "nombre": event_name,
                "fecha": date,
                "hora": time,
                "liga": league,
                "url": full_url
            })
        return events_info
    except StaleElementReferenceException:
        print(f"Error de referencia obsoleta en {url}. Recargando...")
        driver.quit()
        return scrape_links_from_url(url)
    except Exception as e:
        print(f"Error accediendo a {url}: {e}")
        return []
    finally:
        driver.quit()

def scrape_links():
    found_events = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(scrape_links_from_url, URLS)
        for events in results:
            found_events.extend(events)
    # Eliminar duplicados por URL
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

    xml_str = ET.tostring(root, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_str)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(parsed_xml.toprettyxml(indent="  "))

if __name__ == "__main__":
    events = scrape_links()
    print(f"Total de eventos encontrados: {len(events)}")
    save_to_xml(events)

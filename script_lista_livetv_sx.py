iimport re
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
from bs4 import BeautifulSoup

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

def get_page_source_with_age_confirm(driver, url):
    driver.get(url)
    try:
        btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Sí, tengo más de 18 años")]'))
        )
        btn.click()
    except Exception as e:
        print(f"No apareció el popup de edad o falló el click en {url}. Error: {e}. Continuando...")

    WebDriverWait(driver, 5).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    return driver.page_source

def extract_event_info(html):
    soup = BeautifulSoup(html, 'html.parser')
    events_info = []

    for a_tag in soup.find_all("a", class_="live", href=True):
        href = a_tag["href"]
        if "/es/eventinfo/" in href:
            full_url = f"https://livetv.sx{href}"
            event_name = a_tag.get_text(strip=True).replace('&ndash;', '-')

            evdesc_span = a_tag.find_next("span", class_="evdesc")
            if evdesc_span:
                evdesc_text = evdesc_span.get_text(separator=" ", strip=True)
                match = re.match(r"(.+?)\s+a\s+(\d{1,2}:\d{2})\s+\((.+)\)", evdesc_text)
                if match:
                    date = match.group(1).strip()
                    time = match.group(2).strip()
                    league = match.group(3).strip()
                else:
                    date = time = league = "Información no disponible"
            else:
                date = time = league = "Información no disponible"

            events_info.append({
                "nombre": event_name,
                "fecha": date,
                "hora": time,
                "liga": league,
                "url": full_url
            })

    return events_info

def scrape_links_from_url(url):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
        try:
            print(f"Accediendo a: {url}")
            html = get_page_source_with_age_confirm(driver, url)
            events_info = extract_event_info(html)
            print(f"Eventos encontrados en {url}: {len(events_info)}")
            return events_info
        except StaleElementReferenceException:
            print(f"Error de referencia de elemento obsoleto en {url}. Recargando la página...")
            return scrape_links_from_url(url)
        except Exception as e:
            print(f"Error accediendo a {url}: {e}")
            return []

def scrape_links():
    found_events = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scrape_links_from_url, url) for url in URLS]
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

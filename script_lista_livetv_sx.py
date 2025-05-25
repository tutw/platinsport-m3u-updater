import re
import xml.etree.ElementTree as ET
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

def scrape_links_from_url(driver, url):
    try:
        print(f"Accediendo a: {url}")
        html = get_page_source_with_age_confirm(driver, url)
        matches = PATTERN.findall(html)
        if not matches:
            print(f"No se encontraron enlaces en {url}. Verifica el patrón de expresión regular y el HTML.")
        else:
            print(f"Enlaces encontrados en {url}: {matches}")
        return matches
    except StaleElementReferenceException:
        print(f"Error de referencia de elemento obsoleto en {url}. Recargando la página...")
        return scrape_links_from_url(driver, url)
    except Exception as e:
        print(f"Error accediendo a {url}: {e}")
        return []

def extract_event_info(html, link):
    # Extraer información del evento
    event_name_pattern = re.compile(r'<a class="live" href="' + re.escape(link) + r'">(.*?)</a>')
    evdesc_pattern = re.compile(r'<span class="evdesc">(.*?)<br>.*?<br>.*?\((.*?)\)</span>')

    event_name_match = event_name_pattern.search(html)
    evdesc_match = evdesc_pattern.search(html)

    event_name = event_name_match.group(1).replace('&ndash;', '-').strip() if event_name_match else "Nombre no encontrado"
    evdesc = evdesc_match.group(1).strip() if evdesc_match else "Fecha y hora no encontradas"
    league = evdesc_match.group(2).strip() if evdesc_match else "Liga no encontrada"

    # Separar fecha y hora
    date_time = evdesc.split(' a ')
    date = date_time[0] if len(date_time) > 0 else "Fecha no encontrada"
    time = date_time[1] if len(date_time) > 1 else "Hora no encontrada"

    return event_name, date, time, league

def scrape_links():
    found_links = set()
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    with ThreadPoolExecutor(max_workers=5) as executor:
        with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
            futures = [executor.submit(scrape_links_from_url, driver, url) for url in URLS]
            for future in futures:
                found_links.update(future.result())

    return sorted(found_links)

def save_to_xml(links, filename="eventos_livetv_sx.xml"):
    root = ET.Element("eventos")
    for link in links:
        # Convertir enlace a formato absoluto
        absolute_link = f"https://livetv.sx{link}"

        # Extraer información del evento
        event_name, date, time, league = extract_event_info(driver.page_source, link)

        evento = ET.SubElement(root, "evento")
        ET.SubElement(evento, "nombre").text = event_name
        ET.SubElement(evento, "fecha").text = date
        ET.SubElement(evento, "hora").text = time
        ET.SubElement(evento, "liga").text = league
        ET.SubElement(evento, "url").text = absolute_link

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    links = scrape_links()
    print(f"Total de enlaces encontrados: {len(links)}")
    save_to_xml(links)

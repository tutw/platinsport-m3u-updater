import re
import xml.etree.ElementTree as ET
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

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

# Solo los enlaces que terminan en __/ (número + dos guiones bajos + barra)
PATTERN = re.compile(r"https://livetv\.sx/es/eventinfo/\d+__/")

def get_page_source_with_age_confirm(driver, url):
    driver.get(url)
    try:
        # Espera a que aparezca el botón y haz clic (el texto puede variar ligeramente por idioma)
        WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Tengo mas de 18')]"))
        ).click()
        # Espera a que desaparezca el popup (o se cargue el contenido)
        time.sleep(1)
    except Exception:
        # Si no aparece el popup, sigue como si nada
        pass
    return driver.page_source

def scrape_links():
    found_links = set()
    options = Options()
    options.add_argument("--headless=new")  # Borra esta línea si quieres ver el navegador
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        for url in URLS:
            try:
                print(f"Accediendo a: {url}")
                html = get_page_source_with_age_confirm(driver, url)
                matches = PATTERN.findall(html)
                for match in matches:
                    found_links.add(match)
            except Exception as e:
                print(f"Error accediendo a {url}: {e}")
                traceback.print_exc()
    finally:
        driver.quit()
    return sorted(found_links)

def save_to_xml(links, filename="eventos_livetv_sx.xml"):
    root = ET.Element("eventos")
    for link in links:
        evento = ET.SubElement(root, "evento")
        url_elem = ET.SubElement(evento, "url")
        url_elem.text = link
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    links = scrape_links()
    print(f"Total de enlaces encontrados: {len(links)}")
    save_to_xml(links)

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
"https://livetv.sx/es/allupcomingsports/8/",
"https://livetv.sx/es/allupcomingsports/9/",
"https://livetv.sx/es/allupcomingsports/10/",
"https://livetv.sx/es/allupcomingsports/11/",
"https://livetv.sx/es/allupcomingsports/12/",
"https://livetv.sx/es/allupcomingsports/13/",
"https://livetv.sx/es/allupcomingsports/14/",
"https://livetv.sx/es/allupcomingsports/15/",
"https://livetv.sx/es/allupcomingsports/16/",
"https://livetv.sx/es/allupcomingsports/17/",
"https://livetv.sx/es/allupcomingsports/18/",
"https://livetv.sx/es/allupcomingsports/19/",
"https://livetv.sx/es/allupcomingsports/20/",
"https://livetv.sx/es/allupcomingsports/21/",
"https://livetv.sx/es/allupcomingsports/22/",
"https://livetv.sx/es/allupcomingsports/23/",
"https://livetv.sx/es/allupcomingsports/24/",
"https://livetv.sx/es/allupcomingsports/25/",
"https://livetv.sx/es/allupcomingsports/26/",
"https://livetv.sx/es/allupcomingsports/27/",
"https://livetv.sx/es/allupcomingsports/28/",
"https://livetv.sx/es/allupcomingsports/29/",
"https://livetv.sx/es/allupcomingsports/30/",
"https://livetv.sx/es/allupcomingsports/31/",
"https://livetv.sx/es/allupcomingsports/32/",
"https://livetv.sx/es/allupcomingsports/33/",
"https://livetv.sx/es/allupcomingsports/34/",
"https://livetv.sx/es/allupcomingsports/35/",
"https://livetv.sx/es/allupcomingsports/36/",
"https://livetv.sx/es/allupcomingsports/37/",
"https://livetv.sx/es/allupcomingsports/38/",
"https://livetv.sx/es/allupcomingsports/39/",
"https://livetv.sx/es/allupcomingsports/40/",
"https://livetv.sx/es/allupcomingsports/41/",
"https://livetv.sx/es/allupcomingsports/42/",
"https://livetv.sx/es/allupcomingsports/43/",
"https://livetv.sx/es/allupcomingsports/44/",
"https://livetv.sx/es/allupcomingsports/45/",
"https://livetv.sx/es/allupcomingsports/46/",
"https://livetv.sx/es/allupcomingsports/47/",
"https://livetv.sx/es/allupcomingsports/48/",
"https://livetv.sx/es/allupcomingsports/49/",
"https://livetv.sx/es/allupcomingsports/50/",
"https://livetv.sx/es/allupcomingsports/51/",
"https://livetv.sx/es/allupcomingsports/52/",
"https://livetv.sx/es/allupcomingsports/53/",
"https://livetv.sx/es/allupcomingsports/54/",
"https://livetv.sx/es/allupcomingsports/55/",
"https://livetv.sx/es/allupcomingsports/56/",
"https://livetv.sx/es/allupcomingsports/57/",
"https://livetv.sx/es/allupcomingsports/58/",
"https://livetv.sx/es/allupcomingsports/59/",
"https://livetv.sx/es/allupcomingsports/60/",
"https://livetv.sx/es/allupcomingsports/61/",
"https://livetv.sx/es/allupcomingsports/62/",
"https://livetv.sx/es/allupcomingsports/63/",
"https://livetv.sx/es/allupcomingsports/64/",
"https://livetv.sx/es/allupcomingsports/65/",
"https://livetv.sx/es/allupcomingsports/66/",
"https://livetv.sx/es/allupcomingsports/67/",
"https://livetv.sx/es/allupcomingsports/68/",
"https://livetv.sx/es/allupcomingsports/69/",
"https://livetv.sx/es/allupcomingsports/70/",
"https://livetv.sx/es/allupcomingsports/71/",
"https://livetv.sx/es/allupcomingsports/72/",
"https://livetv.sx/es/allupcomingsports/73/",
"https://livetv.sx/es/allupcomingsports/74/",
"https://livetv.sx/es/allupcomingsports/75/",
"https://livetv.sx/es/allupcomingsports/76/",
"https://livetv.sx/es/allupcomingsports/77/",
"https://livetv.sx/es/allupcomingsports/78/",
"https://livetv.sx/es/allupcomingsports/79/",
"https://livetv.sx/es/allupcomingsports/80/",
"https://livetv.sx/es/allupcomingsports/81/",
"https://livetv.sx/es/allupcomingsports/82/",
"https://livetv.sx/es/allupcomingsports/83/",
"https://livetv.sx/es/allupcomingsports/84/",
"https://livetv.sx/es/allupcomingsports/85/",
"https://livetv.sx/es/allupcomingsports/86/",
"https://livetv.sx/es/allupcomingsports/87/",
"https://livetv.sx/es/allupcomingsports/88/",
"https://livetv.sx/es/allupcomingsports/89/",
"https://livetv.sx/es/allupcomingsports/90/",
"https://livetv.sx/es/allupcomingsports/91/",
"https://livetv.sx/es/allupcomingsports/92/",
"https://livetv.sx/es/allupcomingsports/93/",
"https://livetv.sx/es/allupcomingsports/94/",
"https://livetv.sx/es/allupcomingsports/95/",
"https://livetv.sx/es/allupcomingsports/96/",
"https://livetv.sx/es/allupcomingsports/97/",
"https://livetv.sx/es/allupcomingsports/98/",
"https://livetv.sx/es/allupcomingsports/99/",
"https://livetv.sx/es/allupcomingsports/100/",
"https://livetv.sx/es/allupcomingsports/101/",
"https://livetv.sx/es/allupcomingsports/102/",
"https://livetv.sx/es/allupcomingsports/103/",
"https://livetv.sx/es/allupcomingsports/104/",
"https://livetv.sx/es/allupcomingsports/105/",
"https://livetv.sx/es/allupcomingsports/106/",
"https://livetv.sx/es/allupcomingsports/107/",
"https://livetv.sx/es/allupcomingsports/108/",
"https://livetv.sx/es/allupcomingsports/109/",
"https://livetv.sx/es/allupcomingsports/110/",
"https://livetv.sx/es/allupcomingsports/111/",
"https://livetv.sx/es/allupcomingsports/112/",
"https://livetv.sx/es/allupcomingsports/113/",
"https://livetv.sx/es/allupcomingsports/114/",
"https://livetv.sx/es/allupcomingsports/115/",
"https://livetv.sx/es/allupcomingsports/116/",
"https://livetv.sx/es/allupcomingsports/117/",
"https://livetv.sx/es/allupcomingsports/118/",
"https://livetv.sx/es/allupcomingsports/119/",
"https://livetv.sx/es/allupcomingsports/120/",
"https://livetv.sx/es/allupcomingsports/121/",
"https://livetv.sx/es/allupcomingsports/122/",
"https://livetv.sx/es/allupcomingsports/123/",
"https://livetv.sx/es/allupcomingsports/124/",
"https://livetv.sx/es/allupcomingsports/125/",
"https://livetv.sx/es/allupcomingsports/126/",
"https://livetv.sx/es/allupcomingsports/127/",
"https://livetv.sx/es/allupcomingsports/128/",
"https://livetv.sx/es/allupcomingsports/129/",
"https://livetv.sx/es/allupcomingsports/130/",
"https://livetv.sx/es/allupcomingsports/131/",
"https://livetv.sx/es/allupcomingsports/132/",
"https://livetv.sx/es/allupcomingsports/133/",
"https://livetv.sx/es/allupcomingsports/134/",
"https://livetv.sx/es/allupcomingsports/135/",
"https://livetv.sx/es/allupcomingsports/136/",
"https://livetv.sx/es/allupcomingsports/137/",
"https://livetv.sx/es/allupcomingsports/138/",
"https://livetv.sx/es/allupcomingsports/139/",
"https://livetv.sx/es/allupcomingsports/140/",
"https://livetv.sx/es/allupcomingsports/141/",
"https://livetv.sx/es/allupcomingsports/142/",
"https://livetv.sx/es/allupcomingsports/143/",
"https://livetv.sx/es/allupcomingsports/144/",
"https://livetv.sx/es/allupcomingsports/145/",
"https://livetv.sx/es/allupcomingsports/146/",
"https://livetv.sx/es/allupcomingsports/147/",
"https://livetv.sx/es/allupcomingsports/148/",
"https://livetv.sx/es/allupcomingsports/149/",
"https://livetv.sx/es/allupcomingsports/150/",
"https://livetv.sx/es/allupcomingsports/151/",
"https://livetv.sx/es/allupcomingsports/152/",
"https://livetv.sx/es/allupcomingsports/153/",
"https://livetv.sx/es/allupcomingsports/154/",
"https://livetv.sx/es/allupcomingsports/155/",
"https://livetv.sx/es/allupcomingsports/156/",
"https://livetv.sx/es/allupcomingsports/157/",
"https://livetv.sx/es/allupcomingsports/158/",
"https://livetv.sx/es/allupcomingsports/159/",
"https://livetv.sx/es/allupcomingsports/160/",
"https://livetv.sx/es/allupcomingsports/161/",
"https://livetv.sx/es/allupcomingsports/162/",
"https://livetv.sx/es/allupcomingsports/163/",
"https://livetv.sx/es/allupcomingsports/164/",
"https://livetv.sx/es/allupcomingsports/165/",
"https://livetv.sx/es/allupcomingsports/166/",
"https://livetv.sx/es/allupcomingsports/167/",
"https://livetv.sx/es/allupcomingsports/168/",
"https://livetv.sx/es/allupcomingsports/169/",
"https://livetv.sx/es/allupcomingsports/170/",
"https://livetv.sx/es/allupcomingsports/171/",
"https://livetv.sx/es/allupcomingsports/172/",
"https://livetv.sx/es/allupcomingsports/173/",
"https://livetv.sx/es/allupcomingsports/174/",
"https://livetv.sx/es/allupcomingsports/175/",
"https://livetv.sx/es/allupcomingsports/176/",
"https://livetv.sx/es/allupcomingsports/177/",
"https://livetv.sx/es/allupcomingsports/178/",
"https://livetv.sx/es/allupcomingsports/179/",
"https://livetv.sx/es/allupcomingsports/180/",
"https://livetv.sx/es/allupcomingsports/181/",
"https://livetv.sx/es/allupcomingsports/182/",
"https://livetv.sx/es/allupcomingsports/183/",
"https://livetv.sx/es/allupcomingsports/184/",
"https://livetv.sx/es/allupcomingsports/185/",
"https://livetv.sx/es/allupcomingsports/186/",
"https://livetv.sx/es/allupcomingsports/187/",
"https://livetv.sx/es/allupcomingsports/188/",
"https://livetv.sx/es/allupcomingsports/189/",
"https://livetv.sx/es/allupcomingsports/190/",
"https://livetv.sx/es/allupcomingsports/191/",
"https://livetv.sx/es/allupcomingsports/192/",
"https://livetv.sx/es/allupcomingsports/193/",
"https://livetv.sx/es/allupcomingsports/194/",
"https://livetv.sx/es/allupcomingsports/195/",
"https://livetv.sx/es/allupcomingsports/196/",
"https://livetv.sx/es/allupcomingsports/197/",
"https://livetv.sx/es/allupcomingsports/198/",
"https://livetv.sx/es/allupcomingsports/199/",
"https://livetv.sx/es/allupcomingsports/200/",

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

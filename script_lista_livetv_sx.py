from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
import time
import os

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

TODAY = datetime.now().strftime('%d %b %Y')
LOGFILE = 'scraping_log.txt'

def log_step(msg):
    print(f"[INFO] {msg}")
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write("[INFO] " + msg + "\n")

def log_warning(msg):
    print(f"[WARN] {msg}")
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write("[WARN] " + msg + "\n")

def log_error(msg):
    print(f"[ERROR] {msg}")
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write("[ERROR] " + msg + "\n")

def get_events_from_url(url, save_html=False):
    events = []
    log_step(f"Procesando URL: {url}")
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        driver.get(url)
        time.sleep(4)  # Espera a que cargue JS

        html = driver.page_source

        if save_html:
            with open("debug_livetv.html", "w", encoding="utf-8") as f:
                f.write(html)
            log_step("Guardado el HTML de la primera URL en debug_livetv.html para inspección manual.")

        soup = BeautifulSoup(html, 'html.parser')

        # Busca la tabla de eventos por contenido
        all_tables = soup.find_all('table')
        target_table = None
        for table in all_tables:
            if ("Hora" in table.text and "Fecha" in table.text) or ("Time" in table.text and "Date" in table.text):
                target_table = table
                break
        if not target_table:
            log_warning("No se encontró la tabla de eventos por contenido.")
            driver.quit()
            return events

        rows = target_table.find_all('tr')
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 5:
                time_str = tds[0].get_text(strip=True)
                date_str = tds[1].get_text(strip=True)
                name_tag = tds[2].find('a')
                if not name_tag:
                    continue
                event_name = name_tag.get_text(strip=True)
                event_url = "https://livetv.sx" + name_tag['href']
                if TODAY in date_str:
                    events.append({
                        'hora': time_str,
                        'nombre': event_name,
                        'url': event_url
                    })
        driver.quit()
        if not events:
            log_warning("No se encontraron eventos en esta URL para la fecha de hoy.")
        else:
            log_step(f"Eventos encontrados en esta URL: {len(events)}")
    except Exception as e:
        log_error(f"Excepción procesando {url}: {e}")
    return events

def main():
    if os.path.exists(LOGFILE):
        os.remove(LOGFILE)

    all_events = []
    for i, url in enumerate(URLS):
        eventos = get_events_from_url(url, save_html=(i == 0))
        all_events.extend(eventos)

    log_step(f"Total de eventos encontrados: {len(all_events)}")

    root = ET.Element('eventos')
    for ev in all_events:
        evento = ET.SubElement(root, 'evento')
        hora = ET.SubElement(evento, 'hora')
        hora.text = ev['hora']
        nombre = ET.SubElement(evento, 'nombre')
        nombre.text = ev['nombre']
        url = ET.SubElement(evento, 'url')
        url.text = ev['url']

    tree = ET.ElementTree(root)
    tree.write('eventos_livetv_sx.xml', encoding='utf-8', xml_declaration=True)
    print('Archivo eventos_livetv_sx.xml generado con éxito.')
    print(f'Consulta el log detallado en {LOGFILE}')
    print('Si necesitas depuración avanzada, revisa también debug_livetv.html (solo para la primera URL).')

if __name__ == '__main__':
    main()

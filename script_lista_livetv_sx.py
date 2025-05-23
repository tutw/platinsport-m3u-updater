import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

HEADERS = {'User-Agent': 'Mozilla/5.0'}
TODAY = datetime.now().strftime('%d %b %Y')  # Por ejemplo '23 May 2025'

def log_step(msg):
    print(f"[INFO] {msg}")

def log_warning(msg):
    print(f"[WARN] {msg}")

def log_error(msg):
    print(f"[ERROR] {msg}")

def get_events_from_url(url):
    events = []
    log_step(f"Procesando URL: {url}")
    try:
        page = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        soup = BeautifulSoup(page.content, 'html.parser')

        current = soup.body
        if not current:
            log_warning("No se encontró <body>")
            return events
        log_step("Encontrado <body>")

        current = current.find('table')
        if not current:
            log_warning("No se encontró primer <table> en <body>")
            return events
        log_step("Encontrada primera <table>")

        current = current.find('tbody')
        if not current:
            log_warning("No se encontró <tbody> en la primera tabla")
            return events
        log_step("Encontrado <tbody> en la primera tabla")

        trs = current.find_all('tr')
        if len(trs) < 1:
            log_warning("No hay <tr> en el primer <tbody>")
            return events
        current = trs[0]
        log_step("Seleccionado primer <tr>")

        tds = current.find_all('td')
        if len(tds) < 2:
            log_warning("No hay suficientes <td> en primer <tr>")
            return events
        current = tds[1].find('table')
        if not current:
            log_warning("No se encontró <table> en segundo <td> del primer <tr>")
            return events
        log_step("Descendiendo a siguiente <table>")

        current = current.find('tbody')
        trs = current.find_all('tr')
        if len(trs) < 4:
            log_warning("No hay suficientes <tr> en este <tbody>")
            return events
        current = trs[3]
        log_step("Selección: cuarto <tr>")

        tds = current.find_all('td')
        if len(tds) < 1:
            log_warning("No hay <td> en cuarto <tr>")
            return events
        current = tds[0].find('table')
        if not current:
            log_warning("No se encontró <table> en primer <td> del cuarto <tr>")
            return events
        log_step("Descendiendo a siguiente <table>")

        current = current.find('tbody')
        current = current.find('tr')
        tds = current.find_all('td')
        if len(tds) < 2:
            log_warning("No hay suficientes <td> en este <tr>")
            return events
        current = tds[1].find('table')
        if not current:
            log_warning("No se encontró <table> en segundo <td>")
            return events
        log_step("Descendiendo a siguiente <table>")

        current = current.find('tbody')
        current = current.find('tr')
        tds = current.find_all('td')
        if len(tds) < 1:
            log_warning("No hay <td> en <tr>")
            return events
        current = tds[0].find('table')
        if not current:
            log_warning("No se encontró <table> en primer <td>")
            return events
        log_step("Descendiendo a siguiente <table>")

        current = current.find('tbody')
        current = current.find('tr')
        tds = current.find_all('td')
        if len(tds) < 1:
            log_warning("No hay <td> en <tr>")
            return events
        current = tds[0].find('table')
        if not current:
            log_warning("No se encontró <table> en primer <td>")
            return events
        log_step("Descendiendo a siguiente <table>")

        current = current.find('tbody')
        current = current.find('tr')
        tds = current.find_all('td')
        if len(tds) < 1:
            log_warning("No hay <td> en <tr>")
            return events
        target_tables = tds[0].find_all('table')
        if not target_tables:
            log_warning("No se encontraron <table> en último <td>")
            return events
        log_step(f"Encontradas {len(target_tables)} tablas en el último <td>")

        current = target_tables[0]
        current = current.find('tbody')
        tds = current.find_all('tr')[0].find_all('td')
        if len(tds) < 2:
            log_warning("No hay suficientes <td> en <tr> final")
            return events
        tables_list = tds[1].find_all('table')
        if len(tables_list) < 4:
            log_warning(f"Esperaba al menos 4 tablas en el último <td>, encontradas: {len(tables_list)}")
            return events
        log_step("Tomando la cuarta tabla (target)")

        target_table = tables_list[3]
        tbody = target_table.find('tbody')
        if not tbody:
            log_warning("No se encontró <tbody> en la tabla objetivo")
            return events
        rows = tbody.find_all('tr')
        log_step(f"Total filas en la tabla objetivo: {len(rows)}")

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
        log_step(f"Eventos encontrados en esta URL: {len(events)}")
    except Exception as e:
        log_error(f"Excepción procesando {url}: {e}")
    return events

def main():
    all_events = []
    for url in URLS:
        eventos = get_events_from_url(url)
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

if __name__ == '__main__':
    main()

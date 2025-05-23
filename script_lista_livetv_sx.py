import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
import urllib3

# Desactivar advertencias por deshabilitar la verificación SSL
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

def get_events_from_url(url):
    events = []
    try:
        page = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        soup = BeautifulSoup(page.content, 'html.parser')
        for row in soup.select("table.table-main tr[onmouseover]"):
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
    except Exception as e:
        print(f"Error en {url}: {e}")
    return events

def main():
    all_events = []
    for url in URLS:
        eventos = get_events_from_url(url)
        all_events.extend(eventos)

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

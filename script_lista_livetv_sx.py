import requests
import xml.etree.ElementTree as ET
import urllib3
import traceback
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dateparser
import subprocess

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

def normaliza_fecha(fecha_str):
    meses = {
        'Ene': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Abr': 'Apr', 'May': 'May', 'Jun': 'Jun',
        'Jul': 'Jul', 'Ago': 'Aug', 'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dic': 'Dec',
        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr', 'may': 'May', 'jun': 'Jun',
        'jul': 'Jul', 'ago': 'Aug', 'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }
    for esp, eng in meses.items():
        if f" {esp} " in fecha_str:
            fecha_str = fecha_str.replace(f" {esp} ", f" {eng} ")
    try:
        return dateparser.parse(fecha_str, dayfirst=True).date()
    except Exception:
        return None

def scrape_events():
    all_events = []
    today = datetime.now().date()
    print(f"[DEBUG] Hoy (sistema): {today}")
    for url in URLS:
        try:
            print(f"Accediendo a: {url}")
            resp = requests.get(url, verify=False, timeout=25)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for row in soup.find_all('tr'):
                tds = row.find_all('td')
                if len(tds) >= 3:
                    a = tds[2].find('a', href=True)
                    if a and a['href'].startswith('/es/eventinfo/'):
                        hora = tds[0].get_text(strip=True)
                        fecha = tds[1].get_text(strip=True)
                        nombre = a.get_text(strip=True)
                        url_evento = "https://livetv.sx" + a['href']
                        fecha_evento = normaliza_fecha(fecha)
                        print(f"[DEBUG] Fecha extraída: '{fecha}' -> '{fecha_evento}'")
                        if fecha_evento == today:
                            all_events.append({
                                'hora': hora,
                                'fecha': fecha,
                                'nombre': nombre,
                                'url': url_evento
                            })
        except Exception as e:
            print(f"Error accediendo a {url}: {e}")
            traceback.print_exc()
    return all_events

def save_to_xml(events, filename="eventos_livetv_sx.xml"):
    root = ET.Element("eventos")
    for ev in events:
        evento = ET.SubElement(root, "evento")
        hora = ET.SubElement(evento, "hora")
        hora.text = ev["hora"]
        fecha = ET.SubElement(evento, "fecha")
        fecha.text = ev["fecha"]
        nombre = ET.SubElement(evento, "nombre")
        nombre.text = ev["nombre"]
        url_elem = ET.SubElement(evento, "url")
        url_elem.text = ev["url"]
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

def git_commit_push():
    try:
        subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions[bot]@users.noreply.github.com'], check=True)
        subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions[bot]'], check=True)
        subprocess.run(['git', 'add', 'eventos_livetv_sx.xml'], check=True)
        subprocess.run(['git', 'commit', '-m', f'update eventos_livetv_sx.xml with today\'s events'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("Commit y push realizados correctamente.")
    except Exception as e:
        print(f"Error en commit/push: {e}")

if __name__ == "__main__":
    eventos = scrape_events()
    print(f"Total de eventos de hoy encontrados: {len(eventos)}")
    save_to_xml(eventos)
    git_commit_push()

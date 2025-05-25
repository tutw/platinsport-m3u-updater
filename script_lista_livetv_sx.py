import requests
import re
import xml.etree.ElementTree as ET
import urllib3
import traceback

# Silencia los warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Todas las URLs posibles de eventos próximos en LiveTV.sx (puedes agregar/quitar según necesidad)
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

PATTERN = re.compile(r"https://livetv\.sx/es/eventinfo/(\d+)__/")

def scrape_links():
    found_links = set()
    for url in URLS:
        try:
            print(f"Accediendo a: {url}")
            resp = requests.get(url, verify=False, timeout=20)
            resp.raise_for_status()
            matches = PATTERN.findall(resp.text)
            for match in matches:
                found_links.add(f"https://livetv.sx/es/eventinfo/{match}__/")
        except Exception as e:
            print(f"Error accediendo a {url}: {e}")
            traceback.print_exc()  # Muestra el traceback completo
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
    save_to_xml(links)

import requests
import re
import xml.etree.ElementTree as ET
import urllib3

# Silencia los warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Todas las URLs posibles de eventos próximos en LiveTV.sx (puedes agregar/quitar según necesidad)
URLS = [
    "https://livetv.sx/es/allupcoming/",
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
    "https://livetv.sx/es/allupcoming/1/",
    "https://livetv.sx/es/allupcoming/2/",
    "https://livetv.sx/es/allupcoming/3/",
    "https://livetv.sx/es/allupcoming/4/",
    "https://livetv.sx/es/allupcoming/5/",
    "https://livetv.sx/es/allupcoming/6/",
    "https://livetv.sx/es/allupcoming/7/",
    "https://livetv.sx/es/allupcoming/8/",
    "https://livetv.sx/es/allupcoming/9/",
    "https://livetv.sx/es/allupcoming/10/",
]

# Patrón para solo los enlaces con números + "__/" al final, nada de texto
PATTERN = re.compile(r"https://livetv\.sx/es/eventinfo/(\d+)__/")

def scrape_links():
    found_links = set()
    for url in URLS:
        try:
            resp = requests.get(url, verify=False, timeout=20)
            resp.raise_for_status()
            matches = PATTERN.findall(resp.text)
            for match in matches:
                found_links.add(f"https://livetv.sx/es/eventinfo/{match}__/")
        except Exception as e:
            print(f"Error accediendo a {url}: {e}")
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

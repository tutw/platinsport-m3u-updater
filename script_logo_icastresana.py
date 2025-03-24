import requests
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree

URL_SCRAPING = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
XML_FILE = "logos_icastresana.xml"

def scrape_url():
    response = requests.get(URL_SCRAPING)
    response.raise_for_status()
    lines = response.text.strip().split('\n')
    
    if len(lines) % 2 != 0:
        raise ValueError("El número de líneas en la respuesta no es par, lo cual es necesario para formar pares de id y URL.")
    
    return [(lines[i], lines[i + 1]) for i in range(0, len(lines), 2)]

def update_xml(data):
    root = Element('logos')
    for id_acestream, url_logo in data:
        item = SubElement(root, 'item')
        id_elem = SubElement(item, 'id')
        id_elem.text = id_acestream
        url_elem = SubElement(item, 'url')
        url_elem.text = url_logo

    tree = ElementTree(root)
    with open(XML_FILE, "wb") as fh:
        tree.write(fh)

def main():
    data = scrape_url()
    update_xml(data)

if __name__ == "__main__":
    main()

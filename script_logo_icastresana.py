import requests
from xml.etree.ElementTree import Element, SubElement, ElementTree
import os

URL_SCRAPING = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
XML_FILE = "logos_icastresana.xml"

def scrape_url():
    try:
        response = requests.get(URL_SCRAPING)
        response.raise_for_status()  # Lanza una excepción si el código de estado es distinto de 200
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener la URL: {e}")
        return []  # Devuelve una lista vacía para evitar fallos más adelante

    lines = response.text.strip().split('\n')

    if not lines:
        print("Advertencia: La respuesta de la URL está vacía.")
        return []

    if len(lines) % 2 != 0:
        print("Advertencia: El número de líneas en la respuesta no es par. Se omitirá la última línea.")
        lines = lines[:-1]  

    return [(lines[i], lines[i + 1]) for i in range(0, len(lines), 2)]

def update_xml(data):
    if not data:
        print("No hay datos para actualizar el XML.")
        return

    root = Element('logos')
    for id_acestream, url_logo in data:
        print(f"Agregando id_acestream: {id_acestream}, url_logo: {url_logo}")  
        item = SubElement(root, 'item')
        id_elem = SubElement(item, 'id')
        id_elem.text = id_acestream
        url_elem = SubElement(item, 'url')
        url_elem.text = url_logo

    tree = ElementTree(root)
    abs_path = os.path.abspath(XML_FILE)
    
    try:
        with open(XML_FILE, "wb") as fh:
            tree.write(fh, encoding='utf-8', xml_declaration=True)
            print(f"Archivo {abs_path} actualizado correctamente.")
    except Exception as e:
        print(f"Error al escribir en el archivo {abs_path}: {e}")

def main():
    data = scrape_url()
    print(f"Datos scrapeados: {data}")
    update_xml(data)

if __name__ == "__main__":
    main()

import xml.etree.ElementTree as ET

def generar_lista_de_logos():
    root = ET.Element("logos")
    
    canales = [
        {"nombre": "ESPN", "url_logo": "https://example.com/logos/espn.png"},
        {"nombre": "Fox Sports", "url_logo": "https://example.com/logos/foxsports.png"},
        {"nombre": "Sky Sports", "url_logo": "https://example.com/logos/skysports.png"},
        {"nombre": "NBC Sports", "url_logo": "https://example.com/logos/nbcsports.png"},
        # Añade más canales según sea necesario
    ]
    
    for canal in canales:
        canal_element = ET.SubElement(root, "canal")
        nombre = ET.SubElement(canal_element, "nombre")
        nombre.text = canal["nombre"]
        url_logo = ET.SubElement(canal_element, "url_logo")
        url_logo.text = canal["url_logo"]
    
    tree = ET.ElementTree(root)
    tree.write("logos.xml", encoding="utf-8", xml_declaration=True)
    print("Archivo logos.xml creado con éxito.")

if __name__ == "__main__":
    generar_lista_de_logos()

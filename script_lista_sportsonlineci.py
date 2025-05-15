import requests
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree

# URL del archivo de texto
URL_PROG_TXT = "https://sportsonline.ci/prog.txt"
# Nombre del archivo XML generado
OUTPUT_FILE = "lista_sportsonlineci.xml"

def descargar_contenido(url):
    """Descarga el contenido del archivo de texto desde la URL proporcionada."""
    response = requests.get(url)
    response.raise_for_status()  # Lanza una excepción si la solicitud falla
    return response.text

def generar_lista_xml(contenido):
    """Genera el contenido de un archivo XML válido a partir del contenido del archivo de texto."""
    root = Element("playlist")
    root.set("version", "1")

    for linea in contenido.strip().split("\n"):
        try:
            # Separar los componentes de la línea
            partes = linea.split(" | ")
            info_evento = partes[0]
            url_streaming = partes[1]

            # Crear un elemento XML para cada entrada
            track = SubElement(root, "track")
            title = SubElement(track, "title")
            title.text = info_evento
            location = SubElement(track, "location")
            location.text = url_streaming
        except IndexError:
            print(f"Línea no válida, se omitirá: {linea}")

    return root

def guardar_archivo_xml(root):
    """Guarda el contenido generado en un archivo .xml."""
    tree = ElementTree(root)
    with open(OUTPUT_FILE, "wb") as archivo:
        tree.write(archivo, encoding="utf-8", xml_declaration=True)

def main():
    """Función principal para ejecutar el script."""
    print("Descargando contenido del archivo...")
    contenido = descargar_contenido(URL_PROG_TXT)
    print("Generando lista XML...")
    lista_xml = generar_lista_xml(contenido)
    print("Guardando archivo XML...")
    guardar_archivo_xml(lista_xml)
    print(f"Archivo {OUTPUT_FILE} generado con éxito.")

if __name__ == "__main__":
    main()

import requests
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.dom.minidom

# URL del archivo de texto
URL_PROG_TXT = "https://sportsonline.ci/prog.txt"
# Nombre del archivo XML generado
OUTPUT_FILE = "lista_sportsonlineci.xml"

def descargar_contenido(url):
    """Descarga el contenido del archivo de texto desde la URL proporcionada."""
    response = requests.get(url)
    response.raise_for_status()  # Lanza una excepción si la solicitud falla
    # Decodificar el contenido para evitar problemas con caracteres especiales
    return response.text.strip()

def limpiar_linea(linea):
    """Limpia una línea eliminando caracteres no deseados."""
    return linea.strip()

def generar_lista_xml(contenido):
    """Genera el contenido de un archivo XML válido a partir del contenido del archivo de texto."""
    root = Element("playlist")
    root.set("version", "1")

    for linea in contenido.split("\n"):
        linea = limpiar_linea(linea)
        if not linea or " | " not in linea:
            print(f"Línea no válida, se omitirá: {linea}")
            continue
        
        try:
            # Separar los componentes de la línea
            partes = linea.split(" | ")
            info_evento = partes[0].strip()
            url_streaming = partes[1].strip()

            # Crear un elemento XML para cada entrada
            track = SubElement(root, "track")
            title = SubElement(track, "title")
            title.text = info_evento
            location = SubElement(track, "location")
            location.text = url_streaming
        except Exception as e:
            print(f"Error procesando la línea: {linea}, {e}")

    return root

def guardar_archivo_xml(root):
    """Guarda el contenido generado en un archivo XML con formato legible."""
    # Convertir el árbol XML a una cadena con formato
    xml_bytes = tostring(root, encoding="utf-8")
    pretty_xml = xml.dom.minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    # Guardar el archivo con formato legible
    with open(OUTPUT_FILE, "w", encoding="utf-8") as archivo:
        archivo.write(pretty_xml)

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

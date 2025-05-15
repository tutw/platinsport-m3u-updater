import requests
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.dom.minidom

# URL del archivo de texto
URL_PROG_TXT = "https://sportsonline.ci/prog.txt"
# Nombre del archivo XML generado
OUTPUT_FILE = "lista_sportsonlineci.xml"

# Diccionario para traducir días de la semana al español
DIAS_SEMANA = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sábado",
    "Sunday": "Domingo"
}

def descargar_contenido(url):
    """Descarga el contenido del archivo de texto desde la URL proporcionada."""
    response = requests.get(url)
    response.raise_for_status()  # Lanza una excepción si la solicitud falla
    return response.text.strip()

def limpiar_linea(linea):
    """Limpia una línea eliminando caracteres no deseados."""
    return linea.strip()

def traducir_dia(dia_ingles):
    """Traduce un día de la semana del inglés al español."""
    return DIAS_SEMANA.get(dia_ingles.capitalize(), dia_ingles)

def generar_lista_xml(contenido):
    """Genera el contenido de un archivo XML válido agrupando por título."""
    root = Element("playlist")
    root.set("version", "1")

    # Diccionario para agrupar URLs por título
    agrupados = {}
    dia_actual = None  # Día actual al procesar el archivo

    for linea in contenido.split("\n"):
        linea = limpiar_linea(linea)

        # Detectar si la línea indica un día de la semana
        if linea.upper() in DIAS_SEMANA.keys():
            dia_actual = traducir_dia(linea)
            continue

        # Ignorar líneas vacías o irrelevantes
        if not linea or " | " not in linea:
            print(f"Línea no válida, se omitirá: {linea}")
            continue
        
        try:
            # Separar los componentes de la línea
            partes = linea.split(" | ")
            hora_evento = partes[0].strip()
            nombre_evento = partes[1].strip()
            url_streaming = partes[2].strip()
            
            # Crear el título con el día de la semana incluido
            titulo_evento = f"{hora_evento} ({dia_actual}) {nombre_evento}" if dia_actual else nombre_evento
            
            # Agrupar las URLs bajo el mismo título
            if titulo_evento not in agrupados:
                agrupados[titulo_evento] = []
            agrupados[titulo_evento].append(url_streaming)
        except Exception as e:
            print(f"Error procesando la línea: {linea}, {e}")

    # Crear los elementos XML
    for titulo, urls in agrupados.items():
        track = SubElement(root, "track")
        title = SubElement(track, "title")
        title.text = titulo
        for url in urls:
            url_element = SubElement(track, "url")
            url_element.text = url

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

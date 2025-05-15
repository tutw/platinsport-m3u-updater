import requests
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.dom.minidom
from datetime import datetime, timezone
import re

# URL del archivo de texto
URL_PROG_TXT = "https://sportsonline.ci/prog.txt"
# Nombre del archivo XML generado
OUTPUT_FILE = "lista_sportsonlineci.xml"

# Patrones de líneas irrelevantes
LINEAS_IRRELEVANTES = [
    "INFO:",
    "PLEASE USE DOMAIN",
    "ANY INFO/ISSUES",
    "IMPORTANT:",
    "============================================================",
    "*(W) - Women Event",
    "READ!",
    "UPDATE",
]

# Días de la semana en inglés
DIAS_SEMANA = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

def descargar_contenido(url):
    """Descarga el contenido del archivo de texto desde la URL proporcionada."""
    response = requests.get(url)
    response.raise_for_status()  # Lanza una excepción si la solicitud falla
    return response.content.decode('utf-8-sig').strip()

def limpiar_linea(linea):
    """Limpia una línea eliminando espacios innecesarios."""
    return linea.strip()

def es_linea_irrelevante(linea):
    """Determina si una línea es irrelevante."""
    for patron in LINEAS_IRRELEVANTES:
        if patron in linea:
            return True
    return False

def obtener_dia_actual():
    """Devuelve el día de la semana actual en inglés."""
    return datetime.now(timezone.utc).strftime("%A").upper()  # Día en inglés y en mayúsculas.

def procesar_linea(linea):
    """
    Procesa una línea para extraer hora, evento y URL.
    Devuelve el título y URL si es válido.
    """
    # Usar una expresión regular para capturar los componentes de la línea
    match = re.match(r"^(\d{2}:\d{2})\s+(.*?)\s+\|\s+(https?://\S+)", linea)
    if not match:
        raise ValueError("La línea no tiene el formato esperado (hora | evento | url).")
    
    hora_evento = match.group(1).strip()
    nombre_evento = match.group(2).strip()
    url_streaming = match.group(3).strip()

    # Crear el título simplificado (sin día)
    titulo_evento = f"{hora_evento} {nombre_evento}"
    return titulo_evento, url_streaming

def generar_lista_xml(contenido):
    """Genera el contenido de un archivo XML agrupando eventos bajo títulos."""
    root = Element("playlist")
    root.set("version", "1")

    agrupados = {}
    dia_actual = obtener_dia_actual()  # Día actual en inglés
    dia_encontrado = None  # Día encontrado en el archivo de texto
    adicionales = []  # Para guardar las líneas adicionales como HD2, BR1, etc.

    eventos_encontrados = 0  # Contador para eventos procesados

    for linea in contenido.split("\n"):
        linea = limpiar_linea(linea)

        # Ignorar líneas irrelevantes o vacías
        if es_linea_irrelevante(linea) or not linea:
            print(f"Línea irrelevante, se omitirá: {linea}")
            continue

        # Detectar si la línea indica un día de la semana
        if linea.upper() in DIAS_SEMANA:
            dia_encontrado = linea.upper()
            print(f"Día detectado: {dia_encontrado}")
            continue

        # Detectar bloques adicionales al final del día
        if dia_encontrado == dia_actual and re.match(r"^(HD\d+|BR\d+)\s+\w+", linea):
            adicionales.append(linea)
            print(f"Línea adicional detectada: {linea}")
            continue

        # Procesar líneas de eventos solo si el día coincide con el actual
        if dia_encontrado == dia_actual:
            try:
                titulo_evento, url_streaming = procesar_linea(linea)
                if titulo_evento not in agrupados:
                    agrupados[titulo_evento] = []
                agrupados[titulo_evento].append(url_streaming)
                eventos_encontrados += 1
            except ValueError as e:
                print(f"Línea no válida, se omitirá: {linea}. Error: {e}")
            except Exception as e:
                print(f"Error procesando la línea: {linea}. Detalles: {e}")

    if eventos_encontrados == 0:
        print(f"No se encontraron eventos para el día actual: {dia_actual}")

    # Crear los elementos XML para los eventos
    for titulo, urls in agrupados.items():
        track = SubElement(root, "track")
        title = SubElement(track, "title")
        title.text = titulo
        for url in urls:
            url_element = SubElement(track, "url")
            url_element.text = url

    # Agregar las líneas adicionales al final del XML
    if adicionales:
        adicionales_section = SubElement(root, "additional")
        for linea in adicionales:
            additional_item = SubElement(adicionales_section, "item")
            additional_item.text = linea

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

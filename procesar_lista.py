import requests
import os
import xml.etree.ElementTree as ET

# Configuración de la API desde variables de entorno
API_KEY = os.getenv("GOOGLE_API_KEY_LOGOS")
CX = os.getenv("GOOGLE_CX")

# Verificar que las variables estén definidas
if not API_KEY or not CX:
    raise ValueError("Faltan GOOGLE_API_KEY_LOGOS o GOOGLE_CX en las variables de entorno")

# URLs de las listas
LISTAS = {
    "listas_con_logos_google.xml": "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/listas_con_logos_google.xml"
}

# Función para buscar el logo usando la API
def buscar_logo(evento):
    query = f"logo {evento} filetype:png site:*.org | site:*.com -inurl:(login | signup)"
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": API_KEY,
        "cx": CX,
        "searchType": "image",
        "num": 1,
        "fileType": "png",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            return data["items"][0]["link"]
        else:
            print(f"No se encontró logo para {evento}")
            return "https://via.placeholder.com/150"
    except Exception as e:
        print(f"Error buscando logo para {evento}: {e}")
        return "https://via.placeholder.com/150"

# Función para descargar un archivo desde una URL
def descargar_archivo(url, nombre_salida):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    with open(nombre_salida, "w", encoding="utf-8") as file:
        file.write(response.text)
    return nombre_salida

# Procesar lista XML
def procesar_xml(entrada, salida):
    tree = ET.parse(entrada)
    root = tree.getroot()

    for item in root.findall(".//channel") or root.findall(".//event"):
        nombre = item.find("display-name") or item.find("title")
        if nombre is not None and nombre.text:
            logo_url = buscar_logo(nombre.text.strip())
            logo_elem = item.find("icon") or ET.SubElement(item, "icon")
            logo_elem.set("src", logo_url)

    tree.write(salida, encoding="utf-8", xml_declaration=True)

# Función principal
def main():
    for nombre, url in LISTAS.items():
        try:
            print(f"Descargando {nombre}...")
            archivo_entrada = descargar_archivo(url, f"entrada_{nombre}")
            archivo_salida = f"salida_{nombre}"

            if nombre.endswith(".xml"):
                print(f"Procesando XML: {nombre}...")
                procesar_xml(archivo_entrada, archivo_salida)

            print(f"Completado: {archivo_salida}")
        except Exception as e:
            print(f"Error procesando {nombre}: {e}")

if __name__ == "__main__":
    main()

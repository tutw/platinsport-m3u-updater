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
    "lista.m3u": "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u",
    "lista_agenda_DEPORTE-LIBRE.FANS.xml": "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_agenda_DEPORTE-LIBRE.FANS.xml",
    "lista_reproductor_web.xml": "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_reproductor_web.xml"
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

# Procesar lista M3U
def procesar_m3u(entrada, salida):
    with open(entrada, "r", encoding="utf-8") as file:
        lineas = file.readlines()

    nuevas_lineas = []
    for linea in lineas:
        if linea.startswith("#EXTINF:"):
            nombre_evento = linea.split(",")[-1].strip()
            logo_url = buscar_logo(nombre_evento)
            nueva_linea = linea.strip() + f' tvg-logo="{logo_url}"\n'
            nuevas_lineas.append(nueva_linea)
        else:
            nuevas_lineas.append(linea)

    with open(salida, "a", encoding="utf-8") as file:
        file.writelines(nuevas_lineas)

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

    tree.write(salida, encoding="utf-8", xml_declaration=True, method="xml")

# Función principal
def main():
    salida = "listas_con_logos_google.xml"
    if os.path.exists(salida):
        os.remove(salida)
    
    for nombre, url in LISTAS.items():
        try:
            print(f"Descargando {nombre}...")
            archivo_entrada = descargar_archivo(url, f"entrada_{nombre}")

            if nombre.endswith(".m3u"):
                print(f"Procesando M3U: {nombre}...")
                procesar_m3u(archivo_entrada, salida)
            elif nombre.endswith(".xml"):
                print(f"Procesando XML: {nombre}...")
                procesar_xml(archivo_entrada, salida)

            print(f"Completado: {nombre}")
        except Exception as e:
            print(f"Error procesando {nombre}: {e}")

if __name__ == "__main__":
    main()

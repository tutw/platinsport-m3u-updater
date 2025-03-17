import requests
import gzip
import xml.etree.ElementTree as ET

def descargar_epg(url, archivo_salida):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if response.status_code != 200:
            print(f"Error al descargar el EPG desde {url}")
            return False
        
        # Leer y descomprimir el contenido del archivo gz
        epg_data = b""
        with gzip.open(response.raw, 'rb') as f:
            epg_data = f.read()
        
        # Verificar que se ha leído algún contenido
        if not epg_data:
            print("El archivo EPG descargado está vacío.")
            return False

        # Guardar el contenido descomprimido en el archivo de salida
        with open(archivo_salida, 'wb') as f:
            f.write(epg_data)
        
        print(f"EPG descargado y guardado en {archivo_salida}")
        return True
    except Exception as e:
        print(f"Error al procesar el EPG desde {url}: {e}")
        return False

def verificar_epg_xml(archivo):
    try:
        tree = ET.parse(archivo)
        root = tree.getroot()
        print(f"El archivo {archivo} es un XML válido.")
        return True
    except ET.ParseError as e:
        print(f"Error al analizar el archivo XML {archivo}: {e}")
        return False

if __name__ == "__main__":
    epg_url = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
    archivo_salida = "epg.xml"
    
    if descargar_epg(epg_url, archivo_salida):
        if verificar_epg_xml(archivo_salida):
            print("El archivo EPG se ha descargado y verificado correctamente.")
        else:
            print("El archivo EPG descargado no es un XML válido.")
    else:
        print("No se pudo descargar el archivo EPG.")

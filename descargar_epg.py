import requests
import gzip
import shutil
import xml.etree.ElementTree as ET
import os

def descargar_epg(url, archivo_comprimido, archivo_salida):
    try:
        print(f"Descargando EPG desde {url}...")
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        
        if response.status_code != 200:
            print(f"Error al descargar el EPG. Código de estado: {response.status_code}")
            return False

        # Guardar el archivo comprimido para verificar si se descargó correctamente
        with open(archivo_comprimido, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        
        print(f"Archivo comprimido guardado en {archivo_comprimido}")

        # Verificar tamaño del archivo descargado
        if os.path.getsize(archivo_comprimido) == 0:
            print("El archivo descargado está vacío.")
            return False

        # Descomprimir el archivo
        print(f"Descomprimiendo {archivo_comprimido}...")
        with gzip.open(archivo_comprimido, 'rb') as f_in:
            with open(archivo_salida, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        print(f"EPG descomprimido y guardado en {archivo_salida}")

        # Verificar tamaño del archivo descomprimido
        if os.path.getsize(archivo_salida) == 0:
            print("El archivo descomprimido está vacío.")
            return False

        return True

    except Exception as e:
        print(f"Error al procesar el EPG: {e}")
        return False

def verificar_epg_xml(archivo):
    try:
        print(f"Verificando el archivo XML {archivo}...")
        tree = ET.parse(archivo)
        root = tree.getroot()
        print(f"El archivo {archivo} es un XML válido.")
        return True
    except ET.ParseError as e:
        print(f"Error al analizar el archivo XML {archivo}: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado al verificar el XML: {e}")
        return False

if __name__ == "__main__":
    epg_url = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
    archivo_comprimido = "epg.xml.gz"
    archivo_salida = "epg.xml"

    if descargar_epg(epg_url, archivo_comprimido, archivo_salida):
        if verificar_epg_xml(archivo_salida):
            print("El archivo EPG se ha descargado y verificado correctamente.")
        else:
            print("El archivo EPG descargado no es un XML válido.")
    else:
        print("No se pudo descargar el archivo EPG.")

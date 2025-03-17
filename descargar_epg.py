import requests
import gzip
import xml.etree.ElementTree as ET

def descargar_epg(url):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if response.status_code != 200:
            print(f"Error al descargar el EPG desde {url}")
            return None
        
        # Leer y descomprimir el contenido del archivo gz
        with gzip.open(response.raw, 'rb') as f:
            epg_data = f.read()
        
        # Verificar que se ha leído algún contenido
        if not epg_data:
            print("El archivo EPG descargado está vacío.")
            return None

        return epg_data
    except Exception as e:
        print(f"Error al procesar el EPG desde {url}: {e}")
        return None

def actualizar_epg(epg_data, archivo_salida):
    try:
        tree = ET.parse(archivo_salida)
        root = tree.getroot()
        
        # Parse the new EPG data
        new_root = ET.fromstring(epg_data)
        
        # Append new EPG data to the existing one
        for elem in new_root:
            root.append(elem)
        
        # Write the updated tree back to the file
        tree.write(archivo_salida, encoding='utf-8', xml_declaration=True)
        print(f"El archivo {archivo_salida} ha sido actualizado con nuevos datos EPG.")
    except ET.ParseError as e:
        print(f"Error al analizar el archivo XML {archivo_salida}: {e}")
    except Exception as e:
        print(f"Error al actualizar el archivo {archivo_salida}: {e}")

if __name__ == "__main__":
    epg_url = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
    archivo_salida = "epg.xml"
    
    epg_data = descargar_epg(epg_url)
    if epg_data:
        actualizar_epg(epg_data, archivo_salida)
    else:
        print("No se pudo descargar o procesar el archivo EPG.")

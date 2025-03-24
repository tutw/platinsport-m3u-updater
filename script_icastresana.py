import requests
import re
import xml.etree.ElementTree as ET
from difflib import get_close_matches

# URLs de los archivos
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"
peticiones_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
logos_xml_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/logos.xml"
socialcreator_url = "https://www.socialcreator.com/xupimarc2/?s=289267&integ_ch=1"

# Nombre del archivo de salida
output_file = "lista_icastresana.m3u"

def download_file(url):
    """Descarga el contenido de un archivo desde una URL y lo devuelve como una cadena."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Descarga exitosa del archivo desde {url}")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar el archivo desde {url}: {e}")
        return None

def parse_peticiones(peticiones_content):
    """Parses the peticiones content and returns a dictionary mapping hash IDs to logo URLs."""
    hash_logo_map = {}
    lines = peticiones_content.splitlines()
    
    for i in range(0, len(lines), 2):
        try:
            if i + 1 >= len(lines):  
                print(f"Advertencia: Línea sin pareja en peticiones. Línea: {lines[i]}")
                continue  

            extinf_line = lines[i].strip()
            acestream_line = lines[i + 1].strip()

            if extinf_line.startswith("#EXTINF") and "acestream://" in acestream_line:
                logo_url_match = re.search(r'tvg-logo="([^"]+)"', extinf_line)
                if logo_url_match:
                    logo_url = logo_url_match.group(1)
                    hash_id = acestream_line.split("acestream://")[1].strip()
                    hash_logo_map[hash_id] = logo_url

        except (AttributeError, IndexError) as e:
            print(f"Error processing lines: {lines[i]} - {e}")

    return hash_logo_map

def parse_logos_xml(logos_xml_content):
    """Parses the logos XML content and returns a dictionary mapping names to logo URLs."""
    logo_map = {}
    root = ET.fromstring(logos_xml_content)
    for logo in root.findall('logo'):
        name = logo.find('name').text
        url = logo.find('url').text
        logo_map[name] = url
    return logo_map

def parse_socialcreator(socialcreator_content):
    """Parses the socialcreator content and returns a dictionary mapping hash IDs to logo URLs."""
    hash_logo_map = {}
    lines = socialcreator_content.splitlines()
    for line in lines:
        match = re.search(r'acestream://([a-f0-9]+).*tvg-logo="([^"]+)"', line)
        if match:
            hash_id = match.group(1)
            logo_url = match.group(2)
            hash_logo_map[hash_id] = logo_url
    return hash_logo_map

def normalizar_nombre(nombre):
    """Normaliza el nombre eliminando espacios adicionales y convirtiendo a minúsculas."""
    return re.sub(r'\s+', ' ', nombre).strip().lower()

def buscar_logo_en_archive(nombre_canal, logo_map):
    """Busca el logo en el archivo logos.xml."""
    nombre_canal_normalizado = normalizar_nombre(nombre_canal)
    closest_matches = get_close_matches(nombre_canal_normalizado, logo_map.keys(), n=3, cutoff=0.6)
    if closest_matches:
        for match in closest_matches:
            if nombre_canal_normalizado in match:
                return logo_map[match]
        return logo_map[closest_matches[0]]
    return None

def buscar_logo_url(nombre_canal):
    """Busca el logo en la URL de peticiones."""
    response = requests.get(peticiones_url)
    if response.status_code != 200:
        print("Error al acceder a la URL de logos")
        return None
    
    logos_data = response.text.split('\n')
    nombre_canal_normalizado = normalizar_nombre(nombre_canal)
    nombres_logos = {}
    for line in logos_data:
        match = re.search(r'tvg-logo="([^"]+)" .*?tvg-id="[^"]+", ([^,]+)', line)
        if match:
            logo_url = match.group(1)
            canal_name = match.group(2).strip().lower()
            nombres_logos[canal_name] = logo_url
    
    closest_matches = get_close_matches(nombre_canal_normalizado, nombres_logos.keys(), n=3, cutoff=0.6)
    if closest_matches:
        for match in closest_matches:
            if nombre_canal_normalizado in match:
                return nombres_logos[match]
        return nombres_logos[closest_matches[0]]
    return None

def get_logo_url(hash_id, hash_logo_map, logo_map, socialcreator_map):
    """Gets the logo URL from hash_logo_map, logo_map, or socialcreator_map."""
    logo_url = hash_logo_map.get(hash_id)
    if not logo_url:
        logo_url = socialcreator_map.get(hash_id)
    if not logo_url:
        logo_url = buscar_logo_en_archive(hash_id, logo_map)
    if not logo_url:
        logo_url = buscar_logo_url(hash_id)
    return logo_url or "https://i.ibb.co/5cV48dM/handball.png"

def format_eventos(eventos_content, hash_logo_map, logo_map, socialcreator_map):
    """Formats the eventos content by replacing logos based on hash IDs."""
    formatted_lines = []
    lines = eventos_content.splitlines()
    extinf_line = None  

    for line in lines:
        if line.startswith("#EXTINF"):
            extinf_line = line  

        elif "acestream://" in line:
            try:
                hash_id = line.split("acestream://")[1].strip()
                logo_url = get_logo_url(hash_id, hash_logo_map, logo_map, socialcreator_map)

                if extinf_line:
                    extinf_line = replace_logo(extinf_line, logo_url)
                    formatted_lines.append(extinf_line)
                    extinf_line = None  

                formatted_lines.append(f"http://127.0.0.1:6878/ace/getstream?id={hash_id}")

            except IndexError:
                print(f"Error processing line: {line}")

    return "\n".join(formatted_lines)

def replace_logo(extinf_line, logo_url):
    """Replaces or inserts the tvg-logo attribute in the #EXTINF line."""
    if 'tvg-logo="' in extinf_line:
        return re.sub(r'tvg-logo="([^"]+)"', f'tvg-logo="{logo_url}"', extinf_line)
    else:
        return extinf_line.replace("#EXTINF:", f'#EXTINF:-1 tvg-logo="{logo_url}",', 1)

def main():
    """Main function to execute the script."""
    eventos_content = download_file(eventos_url)
    peticiones_content = download_file(peticiones_url)
    logos_xml_content = download_file(logos_xml_url)
    socialcreator_content = download_file(socialcreator_url)

    if not eventos_content or not peticiones_content or not logos_xml_content or not socialcreator_content:
        print("No se pudo descargar el contenido necesario.")
        return  

    print("Archivos descargados correctamente.")

    hash_logo_map = parse_peticiones(peticiones_content)
    logo_map = parse_logos_xml(logos_xml_content)
    socialcreator_map = parse_socialcreator(socialcreator_content)
    formatted_content = format_eventos(eventos_content, hash_logo_map, logo_map, socialcreator_map)

    with open(output_file, 'w') as file:
        file.write(formatted_content)

    print(f"Archivo formateado y guardado como {output_file}")

if __name__ == "__main__":
    main()

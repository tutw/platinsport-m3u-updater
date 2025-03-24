import requests
import re

# URLs de los archivos
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"
lista_full_url = "http://tvrextv.mywebcommunity.org/1RFEF/LISTA_1RFEF_FULL.html"

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

def parse_lista_full(lista_full_content):
    """Parses the lista_full content and returns a dictionary mapping hash IDs to logo URLs."""
    hash_logo_map = {}
    lines = lista_full_content.splitlines()
    for line in lines:
        match = re.search(r'acestream://([a-f0-9]+).*tvg-logo="([^"]+)"', line)
        if match:
            hash_id = match.group(1)
            logo_url = match.group(2)
            hash_logo_map[hash_id] = logo_url
    return hash_logo_map

def format_eventos(eventos_content, hash_logo_map):
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
                logo_url = hash_logo_map.get(hash_id, "https://i.ibb.co/5cV48dM/handball.png")

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
    lista_full_content = download_file(lista_full_url)

    if not eventos_content or not lista_full_content:
        print("No se pudo descargar el contenido necesario.")
        return  

    print("Archivos descargados correctamente.")

    hash_logo_map = parse_lista_full(lista_full_content)
    formatted_content = format_eventos(eventos_content, hash_logo_map)

    with open(output_file, 'w') as file:
        file.write(formatted_content)

    print(f"Archivo formateado y guardado como {output_file}")

if __name__ == "__main__":
    main()

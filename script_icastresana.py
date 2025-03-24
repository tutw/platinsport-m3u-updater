import requests

# URL del archivo eventos.m3u
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"
# URL del archivo peticiones
peticiones_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
# Nombre del archivo de salida
output_file = "lista_icastresana.m3u"

def download_file(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar el archivo desde {url}: {e}")
        return None

def parse_peticiones(peticiones_content):
    hash_logo_map = {}
    lines = peticiones_content.splitlines()
    for line in lines:
        if line.strip():
            parts = line.split(',')
            if len(parts) == 2:
                hash_logo_map[parts[0].strip()] = parts[1].strip()
    return hash_logo_map

def format_eventos(eventos_content, hash_logo_map):
    formatted_lines = []
    lines = eventos_content.splitlines()
    for line in lines:
        if line.startswith("#EXTINF"):
            formatted_lines.append(line)
        elif "acestream://" in line:
            hash_id = line.split("acestream://")[1]
            logo_url = hash_logo_map.get(hash_id, "https://i.ibb.co/5cV48dM/handball.png")
            formatted_lines[-1] = formatted_lines[-1].replace('tvg-logo=""', f'tvg-logo="{logo_url}"')
            formatted_lines.append(f"http://127.0.0.1:6878/ace/getstream?id={hash_id}")
    return "\n".join(formatted_lines)

def main():
    eventos_content = download_file(eventos_url)
    peticiones_content = download_file(peticiones_url)

    if eventos_content:
        print("Contenido de eventos.m3u descargado correctamente")
    else:
        print("Error al descargar eventos.m3u")

    if peticiones_content:
        print("Contenido de peticiones descargado correctamente")
    else:
        print("Error al descargar peticiones")

    if eventos_content and peticiones_content:
        hash_logo_map = parse_peticiones(peticiones_content)
        formatted_content = format_eventos(eventos_content, hash_logo_map)
        with open(output_file, 'w') as file:
            file.write(formatted_content)
        print(f"Archivo formateado y guardado como {output_file}")
    else:
        print("No se pudo descargar el contenido necesario.")

if __name__ == "__main__":
    main()

import requests
import re

# URL del archivo eventos.m3u
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"

# URL del archivo peticiones
peticiones_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"

# Nombre del archivo de salida
output_file = "lista_icastresana.m3u"


def download_file(url):
    """Descarga el contenido de un archivo desde una URL y lo devuelve como una cadena."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Descarga exitosa del archivo desde {url}")
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar el archivo desde {url}: {e}")
        return None


def parse_peticiones(peticiones_content):
    """Parses the peticiones content and returns a dictionary mapping hash IDs to logo URLs."""
    hash_logo_map = {}
    lines = peticiones_content.splitlines()

    if len(lines) < 2:
        print("Advertencia: El archivo de peticiones tiene menos de dos líneas, no se procesará.")
        return hash_logo_map

    for i in range(0, len(lines) - 1, 2):  # Asegurar que hay pares de líneas
        try:
            extinf_line = lines[i].strip()
            acestream_line = lines[i + 1].strip()

            if extinf_line.startswith("#EXTINF") and "acestream://" in acestream_line:
                match = re.search(r'tvg-logo="([^"]+)"', extinf_line)
                if match:
                    logo_url = match.group(1)
                    hash_id = acestream_line.split("acestream://")[1].strip()
                    hash_logo_map[hash_id] = logo_url
        except (IndexError, AttributeError) as e:
            print(f"Error procesando las líneas {i} y {i+1}: {e}")

    print(f"Hash logo map generado: {hash_logo_map}")
    return hash_logo_map


def format_eventos(eventos_content, hash_logo_map):
    """Formats the eventos content by replacing logos based on hash IDs."""
    formatted_lines = []
    lines = eventos_content.splitlines()
    extinf_line = ""

    for line in lines:
        if line.startswith("#EXTINF"):
            extinf_line = line
        elif "acestream://" in line:
            try:
                hash_id = line.split("acestream://")[1].strip()
                logo_url = hash_logo_map.get(hash_id, "https://i.ibb.co/5cV48dM/handball.png")

                # Reemplazar o agregar el logo en la línea #EXTINF
                if extinf_line:
                    extinf_line = replace_logo(extinf_line, logo_url)
                    formatted_lines.append(extinf_line)

                formatted_lines.append(f"http://127.0.0.1:6878/ace/getstream?id={hash_id}")
                extinf_line = ""  # Reset para la siguiente entrada
            except IndexError:
                print(f"Error procesando la línea: {line}")

    print(f"Contenido formateado:\n{formatted_lines}")
    return "\n".join(formatted_lines)


def replace_logo(extinf_line, logo_url):
    """Replaces or inserts the tvg-logo attribute in the #EXTINF line."""
    if 'tvg-logo="' in extinf_line:
        extinf_line = re.sub(r'tvg-logo="([^"]+)"', f'tvg-logo="{logo_url}"', extinf_line)
    else:
        extinf_line = extinf_line.replace("#EXTINF:", f'#EXTINF:-1 tvg-logo="{logo_url}",', 1)
    return extinf_line


def main():
    """Main function to execute the script."""
    eventos_content = download_file(eventos_url)
    peticiones_content = download_file(peticiones_url)

    if not eventos_content:
        print("Error al descargar eventos.m3u")
        return

    if not peticiones_content:
        print("Advertencia: No se pudo descargar peticiones. Se usará el logo por defecto.")
        peticiones_content = ""

    hash_logo_map = parse_peticiones(peticiones_content)
    formatted_content = format_eventos(eventos_content, hash_logo_map)

    with open(output_file, 'w') as file:
        file.write(formatted_content)

    print(f"Archivo formateado y guardado como {output_file}")


if __name__ == "__main__":
    main()

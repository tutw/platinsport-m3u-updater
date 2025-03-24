import requests

def descargar_archivo(url):
    """Descarga el contenido de un archivo desde una URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Descarga exitosa del archivo desde {url}")
        return response.text
    except requests.RequestException as e:
        print(f"Error descargando {url}: {e}")
        return None

def parse_peticiones(content):
    """Parsea el contenido del archivo peticiones."""
    lines = content.split("\n")
    hash_logo_map = {}

    i = 0
    while i < len(lines):
        lines[i] = lines[i].strip()

        if not lines[i] or lines[i].startswith("#"):
            i += 1
            continue  # Ignorar líneas vacías o comentarios

        if i + 1 < len(lines):  # Verificar que hay una línea siguiente
            acestream_line = lines[i + 1].strip()
            hash_logo_map[lines[i]] = acestream_line
            i += 2  # Saltar a la siguiente entrada válida
        else:
            print(f"Warning: No corresponding acestream link for {lines[i]}")
            i += 1

    return hash_logo_map

def main():
    """Función principal del script."""
    url_eventos = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"
    url_peticiones = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"

    eventos_content = descargar_archivo(url_eventos)
    peticiones_content = descargar_archivo(url_peticiones)

    if eventos_content:
        print("Contenido de eventos.m3u descargado correctamente")

    if peticiones_content:
        print("Contenido de peticiones descargado correctamente")
        hash_logo_map = parse_peticiones(peticiones_content)
        print("Mapa generado correctamente:", hash_logo_map)

    print("Proceso completado.")

if __name__ == "__main__":
    main()

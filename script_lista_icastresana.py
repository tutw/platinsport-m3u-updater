import requests
import xml.etree.ElementTree as ET

# URLs de los archivos en GitHub
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/main/eventos.m3u"
logos_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/logos_icastresana.xml"

# Ruta de salida
output_path = "lista_icastresana.m3u"

def download_file(url, description):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error al descargar {description}: {e}")
        exit(1)

def parse_logos_xml(logos_content):
    try:
        root = ET.fromstring(logos_content)
        acestream_to_logo = {}
        for logo in root.findall("logo"):
            id_elem = logo.find("id")
            url_elem = logo.find("url")
            if id_elem is not None and id_elem.text and url_elem is not None and url_elem.text:
                acestream_id = id_elem.text.strip()
                logo_url = url_elem.text.strip()
                if acestream_id and logo_url:
                    acestream_to_logo[acestream_id] = logo_url
        return acestream_to_logo
    except ET.ParseError as e:
        print(f"Error al parsear logos_icastresana.xml: {e}")
        exit(1)

def process_eventos_m3u(eventos_content, acestream_to_logo):
    new_eventos_lines = []
    i = 0
    while i < len(eventos_content):
        line = eventos_content[i].strip()
        if line.startswith("#EXTINF:") and (i + 1 < len(eventos_content)):
            next_line = eventos_content[i + 1].strip()
            acestream_id = None
            if "acestream://" in next_line:
                acestream_id = next_line.split("acestream://")[1]
            elif "ace/getstream?id=" in next_line:
                acestream_id = next_line.split("ace/getstream?id=")[1]
            else:
                new_eventos_lines.append(line)
                i += 1
                continue

            if acestream_id and acestream_id in acestream_to_logo:
                logo_url = acestream_to_logo[acestream_id]
                print(f"Reemplazando logo para {acestream_id} -> {logo_url}")
                parts = line.split(",", 1)
                if len(parts) > 1:
                    new_extinf_line = f'{parts[0].split(" tvg-logo=")[0]} tvg-logo="{logo_url}",{parts[1]}'
                else:
                    new_extinf_line = line
                new_eventos_lines.append(new_extinf_line)
            else:
                new_eventos_lines.append(line)

            new_eventos_lines.append(next_line.replace('acestream://', 'http://127.0.0.1:6878/ace/getstream?id='))
            i += 2
        else:
            new_eventos_lines.append(line)
            i += 1
    return new_eventos_lines

def main():
    print("Descargando archivos...")
    eventos_content = download_file(eventos_url, "eventos.m3u").splitlines()
    logos_content = download_file(logos_url, "logos_icastresana.xml")

    print("Parseando logos_icastresana.xml...")
    acestream_to_logo = parse_logos_xml(logos_content)

    print("Procesando eventos.m3u...")
    new_eventos_lines = process_eventos_m3u(eventos_content, acestream_to_logo)

    print(f"Guardando archivo actualizado como {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_eventos_lines) + "\n")

    print(f"Archivo actualizado guardado como {output_path}")

if __name__ == "__main__":
    main()

import requests
import xml.etree.ElementTree as ET

# URLs de los archivos en GitHub
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"
logos_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/logos_icastresana.xml"

# Ruta de salida
output_path = "lista_icastresana.m3u"

# Descargar eventos.m3u
try:
    eventos_response = requests.get(eventos_url)
    eventos_response.raise_for_status()
    eventos_content = eventos_response.text.splitlines()
except requests.RequestException as e:
    print(f"Error al descargar eventos.m3u: {e}")
    exit(1)

# Descargar logos_icastresana.xml
try:
    logos_response = requests.get(logos_url)
    logos_response.raise_for_status()
    logos_content = logos_response.text
except requests.RequestException as e:
    print(f"Error al descargar logos_icastresana.xml: {e}")
    exit(1)

# Parsear el XML
try:
    logos_root = ET.fromstring(logos_content)
except ET.ParseError as e:
    print(f"Error al parsear logos_icastresana.xml: {e}")
    exit(1)

# Crear el diccionario {id_acestream: url_logo}
acestream_to_logo = {}
for logo in logos_root.findall("logo"):
    id_elem = logo.find("id")
    url_elem = logo.find("url")
    
    if id_elem is not None and url_elem is not None:
        acestream_id = id_elem.text.strip()
        logo_url = url_elem.text.strip()
        if acestream_id and logo_url:
            acestream_to_logo[acestream_id] = logo_url

# Procesar eventos.m3u y reemplazar logos
new_eventos_lines = []
i = 0

while i < len(eventos_content):
    line = eventos_content[i].strip()
    
    if line.startswith("#EXTINF:") and (i + 1 < len(eventos_content)):
        next_line = eventos_content[i + 1].strip()

        # Detectar ID de AceStream
        if "acestream://" in next_line:
            acestream_id = next_line.split("acestream://")[1]
        elif "ace/getstream?id=" in next_line:
            acestream_id = next_line.split("ace/getstream?id=")[1]
        else:
            new_eventos_lines.append(line)
            i += 1
            continue

        # Reemplazar el logo si hay coincidencia
        if acestream_id in acestream_to_logo:
            logo_url = acestream_to_logo[acestream_id]
            print(f"Reemplazando logo para {acestream_id} -> {logo_url}")
            parts = line.split(",", 1)
            if len(parts) > 1:
                new_extinf_line = f'{parts[0]} tvg-logo="{logo_url}",{parts[1]}'
            else:
                new_extinf_line = line
            new_eventos_lines.append(new_extinf_line)
        else:
            new_eventos_lines.append(line)

        # Guardar la línea del stream sin modificar
        new_eventos_lines.append(next_line)
        i += 2  
    else:
        new_eventos_lines.append(line)
        i += 1

# Guardar el archivo actualizado
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(new_eventos_lines) + "\n")

print(f"Archivo actualizado guardado como {output_path}")

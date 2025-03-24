import requests
import xml.etree.ElementTree as ET

# URLs de origen
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"
logos_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/logos_icastresana.xml"

# Descargar el contenido de eventos.m3u
try:
    eventos_response = requests.get(eventos_url)
    eventos_response.raise_for_status()
    eventos_content = eventos_response.text
except Exception as e:
    print("Error al obtener eventos.m3u:", e)
    exit(1)

# Descargar el contenido de logos_icastresana.xml
try:
    logos_response = requests.get(logos_url)
    logos_response.raise_for_status()
    logos_content = logos_response.text
except Exception as e:
    print("Error al obtener logos_icastresana.xml:", e)
    exit(1)

# Parsear el contenido XML de logos
try:
    logos_root = ET.fromstring(logos_content)
except ET.ParseError as e:
    print("Error al parsear el XML de logos:", e)
    exit(1)

# Crear un diccionario para mapear los IDs de AceStream a los logos
acestream_to_logo = {}
for logo in logos_root.findall('logo'):
    acestream_id_elem = logo.find('acestream_id')
    logo_url_elem = logo.find('url')
    if acestream_id_elem is not None and logo_url_elem is not None:
        acestream_id = acestream_id_elem.text.strip() if acestream_id_elem.text else ""
        logo_url = logo_url_elem.text.strip() if logo_url_elem.text else ""
        if acestream_id and logo_url:
            acestream_to_logo[acestream_id] = logo_url

# Mostrar en consola el mapeo obtenido (para depuración)
print("Mapping de AceStream a Logos:")
for key, value in acestream_to_logo.items():
    print(f"{key} -> {value}")

# Procesar el contenido de eventos.m3u y reemplazar logos
new_eventos_lines = []
lines = eventos_content.splitlines()
i = 0

while i < len(lines):
    line = lines[i]
    # Si la línea es una entrada EXTINF
    if line.startswith('#EXTINF:'):
        # Comprobar que la siguiente línea existe y corresponde al stream
        if i + 1 < len(lines) and lines[i + 1].startswith('acestream://'):
            extinf_line = line
            stream_line = lines[i + 1]
            # Extraer el ID de AceStream
            acestream_id = stream_line.split('acestream://')[1].strip()
            if acestream_id in acestream_to_logo:
                logo_url = acestream_to_logo[acestream_id]
                # Separamos en dos partes por la primera coma y actualizamos la URL del logo
                parts = extinf_line.split(',', 1)
                if len(parts) > 1:
                    new_extinf_line = f'#EXTINF:-1 tvg-logo="{logo_url}",{parts[1]}'
                    new_eventos_lines.append(new_extinf_line)
                    print(f"Reemplazado logo para ID {acestream_id} con URL {logo_url}")
                else:
                    # En caso de que no haya coma, se deja la línea original
                    new_eventos_lines.append(extinf_line)
                    print(f"Línea EXTINF sin coma para ID {acestream_id}. No se pudo reemplazar el logo.")
            else:
                new_eventos_lines.append(extinf_line)
                print(f"No se encontró logo para ID {acestream_id}")
            # Reemplazar la línea del stream por la URL local del proxy
            new_eventos_lines.append(f'http://127.0.0.1:6878/ace/getstream?id={acestream_id}')
            i += 2
            continue
        else:
            new_eventos_lines.append(line)
    # Si la línea es un enlace directo de AceStream sin EXTINF previo (caso atípico)
    elif line.startswith('acestream://'):
        acestream_id = line.split('acestream://')[1].strip()
        if acestream_id in acestream_to_logo:
            logo_url = acestream_to_logo[acestream_id]
            print(f"ID {acestream_id} encontrado sin EXTINF. Logo: {logo_url}")
        new_eventos_lines.append(f'http://127.0.0.1:6878/ace/getstream?id={acestream_id}')
    else:
        new_eventos_lines.append(line)
    i += 1

# Escribir el contenido actualizado en el archivo lista_icastresana.m3u
with open('lista_icastresana.m3u', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_eventos_lines))

print('Logos actualizados en lista_icastresana.m3u basado en los IDs de AceStream.')

import xml.etree.ElementTree as ET

# Cargar los archivos
eventos_path = "/mnt/data/eventos.m3u"
logos_path = "/mnt/data/logos_icastresana.xml"
output_path = "/mnt/data/lista_icastresana_actualizada.m3u"

# Leer el contenido del archivo de eventos
with open(eventos_path, "r", encoding="utf-8") as f:
    eventos_content = f.readlines()

# Leer y parsear el archivo XML de logos
tree = ET.parse(logos_path)
root = tree.getroot()

# Crear un diccionario {id_acestream: url_logo}
acestream_to_logo = {}
for logo in root.findall("logo"):
    id_elem = logo.find("id")
    url_elem = logo.find("url")
    
    if id_elem is not None and url_elem is not None:
        acestream_id = id_elem.text.strip()
        logo_url = url_elem.text.strip()
        if acestream_id and logo_url:  # Solo guardamos si hay ID y URL
            acestream_to_logo[acestream_id] = logo_url

# Procesar el archivo de eventos y reemplazar los logos
new_eventos_lines = []
i = 0

while i < len(eventos_content):
    line = eventos_content[i].strip()
    
    # Si es una línea #EXTINF, miramos la siguiente
    if line.startswith("#EXTINF:") and (i + 1 < len(eventos_content)):
        next_line = eventos_content[i + 1].strip()

        # Detectar ID de AceStream en la siguiente línea
        if "acestream://" in next_line:
            acestream_id = next_line.split("acestream://")[1]
        elif "ace/getstream?id=" in next_line:
            acestream_id = next_line.split("ace/getstream?id=")[1]
        else:
            # Si no es un stream válido, agregar la línea tal cual
            new_eventos_lines.append(line)
            i += 1
            continue

        # Si encontramos un logo, lo reemplazamos en la línea EXTINF
        if acestream_id in acestream_to_logo:
            logo_url = acestream_to_logo[acestream_id]
            print(f"Reemplazando logo para {acestream_id} -> {logo_url}")
            # Reemplazamos el logo en la línea EXTINF
            parts = line.split(",", 1)
            if len(parts) > 1:
                new_extinf_line = f'{parts[0]} tvg-logo="{logo_url}",{parts[1]}'
            else:
                new_extinf_line = line  # Si no hay coma, no modificamos

            new_eventos_lines.append(new_extinf_line)
        else:
            # Si no hay logo en la base de datos, se deja igual
            new_eventos_lines.append(line)

        # Guardamos la línea del stream sin modificar
        new_eventos_lines.append(next_line)
        i += 2  # Saltamos ambas líneas procesadas

    else:
        new_eventos_lines.append(line)
        i += 1

# Escribir el archivo actualizado solo si hay cambios
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(new_eventos_lines) + "\n")

print(f"Archivo actualizado y guardado en {output_path}")

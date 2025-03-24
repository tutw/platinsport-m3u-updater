import os
import re
import requests
import time
import xml.etree.ElementTree as ET
import sys

# Expresión regular para extraer el valor del atributo tvg-logo en la línea EXTINF
TVG_LOGO_REGEX = re.compile(r'tvg-logo="([^"]*)"')

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def update_logos():
    peticiones_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
    try:
        response = requests.get(peticiones_url)
        response.raise_for_status()
        lines = response.text.splitlines()
        
        logos_list = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                # Extraer logo
                match = TVG_LOGO_REGEX.search(line)
                logo_url = match.group(1) if match else ""
                # Se espera que la siguiente línea contenga el id con prefijo "acestream://"
                if i + 1 < len(lines):
                    id_line = lines[i+1].strip()
                    if id_line.startswith("acestream://"):
                        # Quitar el prefijo
                        id_val = id_line.replace("acestream://", "")
                        logos_list.append((id_val, logo_url))
                    else:
                        print(f"Se esperaba 'acestream://' en la línea: {id_line}")
                    i += 2  # saltamos la línea del id
                else:
                    i += 1
            else:
                i += 1

        # Construir XML
        root = ET.Element("logos")
        for id_val, url_val in logos_list:
            logo_elem = ET.SubElement(root, "logo")
            ET.SubElement(logo_elem, "id").text = id_val
            ET.SubElement(logo_elem, "url").text = url_val

        indent(root)
        tree = ET.ElementTree(root)
        abs_path = os.path.abspath("logos_icastresana.xml")
        print(f"Actualizando archivo en: {abs_path}")
        try:
            tree.write(abs_path, encoding="utf-8", xml_declaration=True)
            print(f"Archivo 'logos_icastresana.xml' actualizado con éxito.")
        except Exception as e:
            print(f"Error al escribir en el archivo {abs_path}: {e}")
        
        # Imprimir el contenido del archivo XML para verificación
        ET.dump(root)

    except Exception as e:
        print("Error al actualizar logos:", e)

def main():
    # Si se ejecuta en GitHub Actions, se corre una sola vez para evitar bucles infinitos.
    if os.getenv("GITHUB_ACTIONS", "false").lower() == "true":
        update_logos()
        return

    # Si se pasa "manual" como argumento se actualiza una sola vez
    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        update_logos()
    else:
        # Modo autoactualización: se actualiza cada 1 hora.
        while True:
            update_logos()
            time.sleep(3600)

if __name__ == "__main__":
    main()

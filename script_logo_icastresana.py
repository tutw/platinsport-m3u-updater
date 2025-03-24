import requests
import time
import xml.etree.ElementTree as ET
import sys

def update_logos():
    # URL a scrapear
    peticiones_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
    try:
        response = requests.get(peticiones_url)
        response.raise_for_status()  # verifica errores en la petición
        # Separa el contenido en líneas
        lines = response.text.strip().splitlines()

        # Lista para almacenar (id, url)
        logos_list = []
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    logos_list.append((parts[0], parts[1]))
                else:
                    print(f"Formato inesperado en la línea: {line}")

        # Construcción del XML
        root = ET.Element("logos")
        for id_val, url_val in logos_list:
            logo_elem = ET.SubElement(root, "logo")
            id_elem = ET.SubElement(logo_elem, "id")
            id_elem.text = id_val
            url_elem = ET.SubElement(logo_elem, "url")
            url_elem.text = url_val

        tree = ET.ElementTree(root)
        tree.write("logos_icastresana.xml", encoding="utf-8", xml_declaration=True)
        print("Archivo 'logos_icastresana.xml' actualizado con éxito.")
    except Exception as e:
        print("Error al actualizar logos:", e)

def main():
    # Si se pasa "manual" como argumento se actualiza una sola vez.
    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        update_logos()
    else:
        # Modo autoactualización: se actualiza cada 1 hora.
        while True:
            update_logos()
            # Espera 3600 segundos (1 hora) antes de la siguiente actualización
            time.sleep(3600)

if __name__ == "__main__":
    main()

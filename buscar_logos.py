import requests
import xml.etree.ElementTree as ET

# URL del repositorio de logos
REPO_API_URL = 'https://api.github.com/repos/tv-logo/tv-logos/contents/countries'

def obtener_logos_desde_github():
    response = requests.get(REPO_API_URL)
    if response.status_code != 200:
        print(f"Error al acceder al repositorio: {response.status_code} - {response.text}")
        return None

    paises = response.json()
    logos = []

    for pais in paises:
        if pais['type'] == 'dir':
            response_pais = requests.get(pais['url'])
            if response_pais.status_code == 200:
                archivos = response_pais.json()
                for archivo in archivos:
                    if archivo['type'] == 'file' and archivo['name'].endswith('.png'):
                        logos.append({
                            'nombre': archivo['name'],
                            'url_logo': archivo['download_url']
                        })
            else:
                print(f"Error al acceder al directorio {pais['name']}: {response_pais.status_code} - {response_pais.text}")

    return logos

def generar_lista_de_logos():
    logos = obtener_logos_desde_github()
    if logos:
        root = ET.Element("logos")
        for logo in logos:
            canal = ET.SubElement(root, "canal")
            nombre = ET.SubElement(canal, "nombre")
            nombre.text = logo['nombre']
            url_logo = ET.SubElement(canal, "url_logo")
            url_logo.text = logo['url_logo']

        tree = ET.ElementTree(root)
        tree.write("logos.xml", encoding="utf-8", xml_declaration=True)
        print("Archivo logos.xml creado con éxito.")

if __name__ == "__main__":
    generar_lista_de_logos()

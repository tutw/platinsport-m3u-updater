import requests
import xml.etree.ElementTree as ET
import os

API_KEY = os.getenv('e29ce6ba90msh5ba551dfe893059p142633jsndbbb353521bb')
API_URL = 'https://www.thesportsdb.com/api/v1/json/{API_KEY}/search_all_teams.php?l=English%20Premier%20League'

def buscar_logos_deportivos(api_key):
    response = requests.get(API_URL.format(API_KEY=api_key))
    if response.status_code == 200:
        resultados = response.json()
        return resultados
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def generar_lista_de_logos():
    resultados = buscar_logos_deportivos(API_KEY)
    if resultados:
        root = ET.Element("logos")
        for equipo in resultados['teams']:
            canal = ET.SubElement(root, "canal")
            nombre = ET.SubElement(canal, "nombre")
            nombre.text = equipo['strTeam']
            url_logo = ET.SubElement(canal, "url_logo")
            url_logo.text = equipo['strTeamBadge']

        tree = ET.ElementTree(root)
        tree.write("logos.xml", encoding="utf-8", xml_declaration=True)
        print("Archivo logos.xml creado con éxito.")

if __name__ == "__main__":
    generar_lista_de_logos()

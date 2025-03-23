import requests
import xml.etree.ElementTree as ET
import os

API_KEY = os.getenv('AIzaSyCJEsuyu1X762eIMhc-mFod9_uE3SWuxb8')
API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

def buscar_logos_deportivos(api_key):
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        "contents": [{
            "parts": [{"text": "List sports TV channel logos with names and URLs"}]
        }]
    }

    response = requests.post(API_URL, headers=headers, json=data, params={'key': api_key})
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
        for logo in resultados['contents'][0]['parts']:
            canal = ET.SubElement(root, "canal")
            nombre = ET.SubElement(canal, "nombre")
            nombre.text = logo['name']
            url_logo = ET.SubElement(canal, "url_logo")
            url_logo.text = logo['url']

        tree = ET.ElementTree(root)
        tree.write("logos.xml", encoding="utf-8", xml_declaration=True)
        print("Archivo logos.xml creado con éxito.")

if __name__ == "__main__":
    generar_lista_de_logos()

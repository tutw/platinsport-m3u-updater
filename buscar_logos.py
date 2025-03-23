import requests
import xml.etree.ElementTree as ET

API_KEY = 'AIzaSyCJEsuyu1X762eIMhc-mFod9_uE3SWuxb8'

def buscar_logos_deportivos(api_key):
    url = "https://vision.googleapis.com/v1/images:annotate"
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        "requests": [
            {
                "image": {
                    "source": {
                        "imageUri": "URL_DE_EJEMPLO_DE_UN_LOGO_DE_CANAL_DE_TV"
                    }
                },
                "features": [
                    {
                        "type": "LOGO_DETECTION",
                        "maxResults": 10
                    }
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data, params={'key': api_key})
    if response.status_code == 200:
        resultados = response.json()
        return resultados
    else:
        print(f"Error: {response.status_code}")
        return None

def generar_lista_de_logos():
    resultados = buscar_logos_deportivos(API_KEY)
    if resultados:
        root = ET.Element("logos")
        for logo in resultados['responses'][0]['logoAnnotations']:
            canal = ET.SubElement(root, "canal")
            nombre = ET.SubElement(canal, "nombre")
            nombre.text = logo['description']
            url_logo = ET.SubElement(canal, "url_logo")
            url_logo.text = logo['score']

        tree = ET.ElementTree(root)
        tree.write("logos.xml", encoding="utf-8", xml_declaration=True)
        print("Archivo logos.xml creado con éxito.")

if __name__ == "__main__":
    generar_lista_de_logos()

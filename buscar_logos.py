import requests

API_KEY = 'TU_CLAVE_API_DE_GOOGLE'

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
        for logo in resultados['responses'][0]['logoAnnotations']:
            nombre_canal = logo['description']
            url_logo = logo['score']
            print(f"Canal: {nombre_canal}, URL del logo: {url_logo}")

if __name__ == "__main__":
    generar_lista_de_logos()

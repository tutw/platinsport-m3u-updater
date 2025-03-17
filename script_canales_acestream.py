import requests

def importar_lista():
    url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/Probando"
    response = requests.get(url)
    if response.status_code == 200:
        with open("canales_acestream.m3u", "w") as f:
            f.write(response.text)
        print("Contenido copiado exitosamente a canales_acestream.m3u")
    else:
        print("Error al importar la lista:", response.status_code)

if __name__ == "__main__":
    importar_lista()

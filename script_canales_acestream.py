import requests

def importar_lista():
    url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
    response = requests.get(url)
    if response.status_code == 200:
        lines = response.text.splitlines()
        with open("canales_acestream.m3u", "w") as f:
            for line in lines:
                if '[ID_ACESTREAM]' in line:
                    id_acestream = line.split('=')[1]
                    formatted_link = f"http://127.0.0.1:6878/ace/getstream?id={id_acestream}"
                    f.write(formatted_link + "\n")
                else:
                    f.write(line + "\n")
        print("Contenido copiado exitosamente a canales_acestream.m3u")
    else:
        print("Error al importar la lista:", response.status_code)

if __name__ == "__main__":
    importar_lista()

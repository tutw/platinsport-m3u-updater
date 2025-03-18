import requests

def importar_lista():
    url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones"
    response = requests.get(url)
    if response.status_code == 200:
        contenido_lista = response.text
        lineas_modificadas = []
        for linea in contenido_lista.splitlines():
            if "acestream://" in linea:
                id_acestream = linea.split("acestream://")[1]
                nuevo_enlace = f"http://127.0.0.1:6878/ace/getstream?id={id_acestream}"
                lineas_modificadas.append(nuevo_enlace)
            else:
                lineas_modificadas.append(linea)
        
        with open("canales_acestream.m3u", "w") as f:
            f.write("\n".join(lineas_modificadas))
        print("Lista modificada guardada en 'canales_acestream.m3u'.")
    else:
        print("Error al importar la lista:", response.status_code)

if __name__ == "__main__":
    importar_lista()

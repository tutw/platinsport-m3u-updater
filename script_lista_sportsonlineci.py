import requests

# URL del archivo de texto
URL_PROG_TXT = "https://sportsonline.ci/prog.txt"
# Nombre del archivo M3U generado
OUTPUT_FILE = "lista_sportsonlineci.m3u"

def descargar_contenido(url):
    """Descarga el contenido del archivo de texto desde la URL proporcionada."""
    response = requests.get(url)
    response.raise_for_status()  # Lanza una excepción si la solicitud falla
    return response.text

def generar_lista_m3u(contenido):
    """Genera el contenido de una lista M3U válida a partir del contenido del archivo de texto."""
    m3u_lines = ["#EXTM3U"]
    for linea in contenido.strip().split("\n"):
        try:
            # Separar los componentes de la línea
            partes = linea.split(" | ")
            info_evento = partes[0]
            url_streaming = partes[1]

            # Extraer el título descriptivo
            m3u_lines.append(f"#EXTINF:-1,{info_evento}")
            m3u_lines.append(url_streaming)
        except IndexError:
            print(f"Línea no válida, se omitirá: {linea}")
    return "\n".join(m3u_lines)

def guardar_archivo_m3u(contenido):
    """Guarda el contenido generado en un archivo .m3u."""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as archivo:
        archivo.write(contenido)

def main():
    """Función principal para ejecutar el script."""
    print("Descargando contenido del archivo...")
    contenido = descargar_contenido(URL_PROG_TXT)
    print("Generando lista M3U...")
    lista_m3u = generar_lista_m3u(contenido)
    print("Guardando archivo M3U...")
    guardar_archivo_m3u(lista_m3u)
    print(f"Archivo {OUTPUT_FILE} generado con éxito.")

if __name__ == "__main__":
    main()

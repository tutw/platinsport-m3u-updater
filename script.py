import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def obtener_url_lista_m3u():
    base_url = "https://www.platinsport.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a la página principal")
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    # Buscamos el enlace que contiene el texto "DOWNLOAD ALL THE LINKS AS A M3U8 PLAYLIST"
    enlace_m3u = soup.find("a", string="DOWNLOAD ALL THE LINKS AS A M3U8 PLAYLIST", href=True)
    if enlace_m3u:
        url_m3u = base_url + enlace_m3u["href"]
        print("URL de la lista M3U encontrada:", url_m3u)
        return url_m3u
    else:
        print("No se encontró el enlace a la lista M3U")
        return None

def descargar_lista_m3u(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    # Dividimos el contenido de la lista M3U en líneas
    lineas = response.text.splitlines()
    enlaces_info = []
    hora_encontrada = None
    nombre_evento = None
    for linea in lineas:
        # Buscamos las líneas que comienzan con #EXTINF
        if linea.startswith("#EXTINF"):
            # Extraemos la hora y el nombre del evento
            match = re.search(r"#EXTINF:-1 tvg-id=\"[^\"]+\" tvg-name=\"([^\"]+)\",([^\n]+)", linea)
            if match:
                nombre_evento = match.group(2).strip()
                hora_texto = match.group(1).strip()
                try:
                    hora_encontrada = datetime.strptime(hora_texto, "%H:%M").time()
                except ValueError:
                    hora_encontrada = datetime.strptime("23:59", "%H:%M").time()
        # Buscamos las líneas que contienen las URLs de los streams
        elif linea.startswith("acestream://"):
            if nombre_evento and hora_encontrada:
                enlaces_info.append({
                    "nombre": nombre_evento,
                    "hora": hora_encontrada,
                    "url": linea.strip()
                })
                nombre_evento = None
                hora_encontrada = None
    return enlaces_info

def guardar_lista_m3u(enlaces_info, archivo="lista.m3u"):
    # Ordenamos las entradas por la hora extraída
    enlaces_info.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in enlaces_info:
            canal_id = item["nombre"].lower().replace(" ", "_")
            extinf_line = f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\",{item['nombre']} ({item['hora'].strftime('%H:%M')})\n"
            f.write(extinf_line)
            f.write(f"{item['url']}\n")

if __name__ == "__main__":
    # 1. Obtener la URL de la lista M3U
    url_lista_m3u = obtener_url_lista_m3u()
    if not url_lista_m3u:
        print("No se pudo obtener la URL de la lista M3U.")
        exit(1)
    print("URL de la lista M3U:", url_lista_m3u)

    # 2. Descargar y procesar la lista M3U
    enlaces_info = descargar_lista_m3u(url_lista_m3u)
    if not enlaces_info:
        print("No se encontraron enlaces AceStream en la lista M3U.")
        exit(1)

    # 3. Generar y guardar la lista M3U ordenada por hora
    guardar_lista_m3u(enlaces_info)
    print("Lista M3U actualizada correctamente.")

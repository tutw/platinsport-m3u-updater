import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def obtener_url_diaria():
    base_url = "https://www.platinsport.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a la página principal")
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces = soup.find_all("a", href=True)
    for a in enlaces:
        href = a["href"]
        # Buscamos un enlace que cumpla con el patrón deseado
        match = re.search(r"(https://www\.platinsport\.com/link/\d{2}[a-z]{3}[a-z0-9]+/01\.php)", href, re.IGNORECASE)
        if match:
            # Eliminar el prefijo del acortador, si existe, para quedarnos solo con la URL de Platinsport
            url_platinsport = re.sub(r"^http://bc\.vc/\d+/", "", href)
            print("URL diaria encontrada:", url_platinsport)
            return url_platinsport
    print("No se encontró la URL diaria")
    return None

def extraer_eventos_y_enlaces(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    eventos_info = []
    # Buscamos los contenedores que podrían tener la información de los eventos
    for div in soup.find_all("div", class_=re.compile(".*schedule.*", re.IGNORECASE)):
        texto = div.get_text(" ", strip=True)
        # Buscamos la hora y el evento en el texto
        match = re.search(r"(\d{1,2}:\d{2})\s+([A-Z\s\-]+)(acestream://[a-f0-9]+)", texto, re.IGNORECASE)
        if match:
            hora = datetime.strptime(match.group(1), "%H:%M").time()
            evento = match.group(2).strip()
            enlace = match.group(3)
            eventos_info.append({
                "hora": hora,
                "evento": evento,
                "enlace": enlace
            })
    return eventos_info

def guardar_lista_m3u(eventos_info, archivo="lista.m3u"):
    eventos_info.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos_info:
            canal_id = item["evento"].lower().replace(" ", "_")
            extinf_line = f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['evento']}\",{item['evento']} ({item['hora'].strftime('%H:%M')})\n"
            f.write(extinf_line)
            f.write(f"{item['enlace']}\n")

if __name__ == "__main__":
    url_diaria = obtener_url_diaria()
    if not url_diaria:
        print("No se pudo determinar la URL de programación diaria.")
        exit(1)
    eventos_info = extraer_eventos_y_enlaces(url_diaria)
    if not eventos_info:
        print("No se encontraron eventos con enlaces AceStream.")
        exit(1)
    guardar_lista_m3u(eventos_info)
    print("Lista M3U actualizada correctamente.")

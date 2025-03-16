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

def extraer_enlaces_acestream(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces_info = []

    # Encuentra todos los enlaces con AceStream
    for a in soup.find_all("a", href=True):
        if "acestream://" in a["href"]:
            texto = a.get_text(strip=True)
            
            # Intentamos extraer la hora y el nombre del evento desde el HTML
            hora_encontrada = None
            nombre_evento = None
            
            # Buscar la hora
            time_tag = a.find_previous("time")
            if time_tag:
                try:
                    hora_encontrada = datetime.strptime(time_tag.get_text(strip=True), "%H:%M").time()
                except Exception:
                    hora_encontrada = datetime.strptime("23:59", "%H:%M").time()  # Si no se puede parsear, asignamos 23:59

            # Buscar el nombre del evento
            div_evento = a.find_next("div", class_="separator")
            if div_evento:
                nombre_evento = div_evento.get_text(strip=True)
            
            # Si no se encuentra hora o evento, asignamos valores por defecto
            if hora_encontrada is None:
                hora_encontrada = datetime.strptime("23:59", "%H:%M").time()
            if nombre_evento is None:
                nombre_evento = "Evento no disponible"
                
            enlaces_info.append({
                "nombre": nombre_evento,
                "url": a["href"],
                "hora": hora_encontrada
            })
    
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
    # 1. Detectar la URL diaria
    url_diaria = obtener_url_diaria()
    if not url_diaria:
        print("No se pudo determinar la URL diaria.")
        exit(1)
    print("URL diaria:", url_diaria)

    # 2. Extraer los enlaces AceStream
    enlaces_info = extraer_enlaces_acestream(url_diaria)
    if not enlaces_info:
        print("No se encontraron enlaces AceStream.")
        exit(1)

    # 3. Generar y guardar la lista M3U ordenada por hora
    guardar_lista_m3u(enlaces_info)
    print("Lista M3U actualizada correctamente.")

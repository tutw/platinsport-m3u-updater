import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Función para detectar la URL diaria usando el patrón:
# https://www.platinsport.com/link/<día><abreviatura><cadena>/01.php
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
        # Buscamos un enlace que cumpla con el patrón:
        # Dos dígitos, tres letras (día de la semana) y una cadena aleatoria, terminando en /01.php
        if re.search(r"https://www\.platinsport\.com/link/\d{2}[a-z]{3}[a-z0-9]+/01\.php", href, re.IGNORECASE):
            print("URL diaria encontrada:", href)
            return href
    print("No se encontró la URL diaria")
    return None

# Función para extraer los enlaces AceStream de la página de la URL diaria
def extraer_enlaces_acestream(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces_info = []
    # Se asume que los enlaces AceStream están en <a> y su texto puede contener el horario (por ejemplo, "20:00")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "acestream://" in href:
            texto = a.get_text(strip=True)
            # Buscar un patrón de hora en el texto (formato HH:MM)
            hora_encontrada = None
            match = re.search(r'\b(\d{1,2}:\d{2})\b', texto)
            if match:
                try:
                    hora_encontrada = datetime.strptime(match.group(1), "%H:%M").time()
                except Exception:
                    hora_encontrada = None
            # Si no se encuentra hora, se asigna un valor que lo haga quedar al final (por ejemplo, 23:59)
            if hora_encontrada is None:
                hora_encontrada = datetime.strptime("23:59", "%H:%M").time()
            enlaces_info.append({
                "nombre": texto if texto else "Canal AceStream",
                "url": href,
                "hora": hora_encontrada
            })
    return enlaces_info

# Función para guardar la lista M3U ordenada por hora
def guardar_lista_m3u(enlaces_info, archivo="lista.m3u"):
    # Ordenar las entradas por la hora extraída
    enlaces_info.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        # Encabezado estándar de M3U
        f.write("#EXTM3U\n")
        for item in enlaces_info:
            # Se crea un id de canal a partir del nombre (normalizado)
            canal_id = item["nombre"].lower().replace(" ", "_")
            # La línea EXTINF incluye el nombre y, opcionalmente, el horario (en formato HH:MM)
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
    
    # 3. Guardar la lista M3U ordenada por hora
    guardar_lista_m3u(enlaces_info)
    print("Lista M3U actualizada correctamente.")

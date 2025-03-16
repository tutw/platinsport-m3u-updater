import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz

# Definir la zona horaria local
tz_local = pytz.timezone("Europe/Madrid")  # Cambia según tu ubicación

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
        match = re.search(r"(https://www\.platinsport\.com/link/\d{2}[a-z]{3}[a-z0-9]+/01\.php)", href, re.IGNORECASE)
        if match:
            print("URL diaria encontrada:", href)
            return href
    
    print("No se encontró la URL diaria")
    return None

def obtener_eventos(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print("Error al acceder a la página del evento")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    eventos = []
    
    # Buscar todas las entradas de partidos
    partidos = soup.find_all("div", class_="match-container")  # Ajustar la clase según el HTML real
    
    for partido in partidos:
        # Obtener la hora del evento
        time_tag = partido.find("time")
        if time_tag:
            hora_utc = time_tag["datetime"]
            hora_evento = datetime.strptime(hora_utc, "%Y-%m-%dT%H:%M:%SZ")
            hora_evento = hora_evento.replace(tzinfo=pytz.utc).astimezone(tz_local)
            hora_formateada = hora_evento.strftime("%H:%M")
        else:
            hora_formateada = "Desconocido"
        
        # Obtener el nombre del evento
        titulo = partido.find("div", class_="event-title")  # Ajustar la clase según el HTML real
        if titulo:
            nombre_evento = titulo.get_text(strip=True)
        else:
            nombre_evento = "Evento Desconocido"
        
        # Obtener el enlace AceStream
        acestream_tag = partido.find("a", href=re.compile(r"acestream://"))
        if acestream_tag:
            acestream_link = acestream_tag["href"]
        else:
            acestream_link = "No disponible"
        
        eventos.append((nombre_evento, hora_formateada, acestream_link))
    
    return eventos

def generar_m3u(eventos):
    with open("lista.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for evento in eventos:
            nombre, hora, link = evento
            if link != "No disponible":
                f.write(f'#EXTINF:-1 tvg-name="{nombre}" tvg-id="{nombre.lower().replace(" ", "_")}",{nombre} ({hora})\n')
                f.write(f"{link}\n")

# Ejecutar las funciones
url_diaria = obtener_url_diaria()
if url_diaria:
    eventos = obtener_eventos(url_diaria)
    generar_m3u(eventos)
    print("Lista M3U actualizada correctamente.")
else:
    print("No se pudo actualizar la lista M3U.")

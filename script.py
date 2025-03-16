import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------------------
# Fuente 1: Platinsport
# ---------------------------
def obtener_url_diaria():
    base_url = "https://www.platinsport.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a la página principal de Platinsport")
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces = soup.find_all("a", href=True)
    for a in enlaces:
        href = a["href"]
        # Buscamos un enlace que cumpla con el patrón deseado
        match = re.search(r"(https://www\.platinsport\.com/link/\d{2}[a-z]{3}[a-z0-9]+/01\.php)", href, re.IGNORECASE)
        if match:
            # Eliminamos el prefijo del acortador, si existe, para quedarnos solo con la URL de Platinsport
            url_platinsport = re.sub(r"^http://bc\.vc/\d+/", "", href)
            print("URL diaria encontrada en Platinsport:", url_platinsport)
            return url_platinsport
    print("No se encontró la URL diaria en Platinsport")
    return None

def extraer_enlaces_acestream(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces_info = []
    # Se recorre cada enlace y se extrae el texto (aquí asumimos que el texto contiene la información del evento)
    for a in soup.find_all("a", href=True):
        if "acestream://" in a["href"]:
            texto = a.get_text(strip=True)
            # Se intenta extraer un horario en formato "HH:MM" del texto
            hora_encontrada = None
            match = re.search(r'\b(\d{1,2}:\d{2})\b', texto)
            if match:
                try:
                    hora_encontrada = datetime.strptime(match.group(1), "%H:%M").time()
                except Exception:
                    hora_encontrada = None
            # Si no se encuentra hora, se asigna 23:59 por defecto
            if hora_encontrada is None:
                hora_encontrada = datetime.strptime("23:59", "%H:%M").time()
            enlaces_info.append({
                "nombre": texto if texto else "Canal AceStream",
                "url": a["href"],
                "hora": hora_encontrada
            })
    return enlaces_info

# ---------------------------
# Fuente 2: Tarjeta Roja en Vivo
# ---------------------------
def extraer_eventos_tarjetaroja(url):
    """
    Extrae la información de eventos de Tarjeta Roja en Vivo.
    Se asume que cada evento está en un contenedor <div class="match">.
      - Se obtiene la hora del evento desde el atributo `datetime` de un <time>.
      - El nombre del evento se extrae de un <div class="separator" style="user-select: auto;">.
      - El canal de TV se extrae de un <div class="channel">.
      - Se extrae el enlace AceStream (de un <a> cuyo href inicia con "acestream://").
    (Si la estructura real difiere, ajusta los selectores CSS a la estructura actual de la web).
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    eventos = []
    # Supongamos que cada evento se encuentra en un contenedor con clase "match"
    containers = soup.find_all("div", class_="match")
    for container in containers:
        # Extraer la hora utilizando <time datetime="...">
        time_tag = container.find("time")
        if time_tag and time_tag.get("datetime"):
            time_val = time_tag["datetime"].strip()
            try:
                # Se supone que el atributo datetime tiene el formato "HH:MM"
                event_time = datetime.strptime(time_val, "%H:%M").time()
            except ValueError:
                try:
                    event_time = datetime.fromisoformat(time_val.replace("Z", "")).time()
                except Exception:
                    event_time = datetime.strptime("23:59", "%H:%M").time()
        else:
            event_time = datetime.strptime("23:59", "%H:%M").time()

        # Extraer el nombre del evento desde <div class="separator" style="user-select: auto;">
        separator_div = container.find("div", class_="separator", style="user-select: auto;")
        if separator_div:
            event_name = separator_div.get_text(strip=True)
        else:
            event_name = "Evento Desconocido"

        # Extraer el canal de TV (suponemos que está en <div class="channel">)
        channel_div = container.find("div", class_="channel")
        if channel_div:
            tv_channel = channel_div.get_text(strip=True)
        else:
            tv_channel = "Canal Desconocido"

        # Extraer el enlace AceStream (se asume que hay un <a> cuyo href inicia con "acestream://")
        a_tag = container.find("a", href=lambda h: h and h.startswith("acestream://"))
        if a_tag:
            stream_url = a_tag["href"]
        else:
            stream_url = ""
        
        # Solo agregamos si se encontró un enlace
        if stream_url:
            eventos.append({
                "nombre": event_name,
                "hora": event_time,
                "canal": tv_channel,
                "url": stream_url
            })
    return eventos

# ---------------------------
# Guardar la lista M3U (actualizada para incluir canal si existe)
# ---------------------------
def guardar_lista_m3u(eventos, archivo="lista.m3u"):
    # Ordenamos los eventos por la hora
    eventos.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos:
            canal_id = item["nombre"].lower().replace(" ", "_")
            if "canal" in item:
                extinf_line = (f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\","
                               f"{item['nombre']} ({item['hora'].strftime('%H:%M')}) - {item['canal']}\n")
            else:
                extinf_line = (f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\","
                               f"{item['nombre']} ({item['hora'].strftime('%H:%M')})\n")
            f.write(extinf_line)
            f.write(f"{item['url']}\n")

# ---------------------------
# Bloque principal: combinar ambas fuentes
# ---------------------------
if __name__ == "__main__":
    eventos_totales = []
    
    # Fuente 1: Platinsport
    url_diaria = obtener_url_diaria()
    if url_diaria:
        eventos_platinsport = extraer_enlaces_acestream(url_diaria)
        print("Eventos extraídos de Platinsport:", len(eventos_platinsport))
        eventos_totales.extend(eventos_platinsport)
    else:
        print("No se encontró URL diaria en Platinsport.")
    
    # Fuente 2: Tarjeta Roja en Vivo
    url_tarjeta = "https://tarjetarojaenvivo.lat"
    eventos_tarjeta = extraer_eventos_tarjetaroja(url_tarjeta)
    print("Eventos extraídos de Tarjeta Roja en Vivo:", len(eventos_tarjeta))
    eventos_totales.extend(eventos_tarjeta)
    
    if not eventos_totales:
        print("No se encontraron eventos en ninguna fuente.")
        exit(1)
    
    # Guardar la lista M3U combinada
    guardar_lista_m3u(eventos_totales)
    print("Lista M3U actualizada correctamente con", len(eventos_totales), "eventos.")

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gzip
import xml.etree.ElementTree as ET

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
            url_platinsport = re.sub(r"^http://bc\.vc/\d+/", "", href)
            print("URL diaria encontrada:", url_platinsport)
            return url_platinsport
    print("No se encontró la URL diaria")
    return None

def extraer_eventos(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    eventos = []

    contenedor = soup.find("div", class_="myDiv1")
    if not contenedor:
        print("No se encontró el contenedor de eventos (.myDiv1)")
        return eventos

    time_tags = contenedor.find_all("time")
    for tag in time_tags:
        time_val = tag.get("datetime", "").strip()
        try:
            hora_evento = datetime.fromisoformat(time_val.replace("Z", "")).time()
        except Exception:
            try:
                hora_evento = datetime.strptime(time_val, "%H:%M").time()
            except Exception:
                hora_evento = datetime.strptime("23:59", "%H:%M").time()

        event_text = ""
        canales = []
        for sib in tag.next_siblings:
            if hasattr(sib, "name") and sib.name == "time":
                break
            if isinstance(sib, str):
                event_text += sib.strip() + " "
            elif hasattr(sib, "name"):
                if sib.name == "a" and "acestream://" in sib["href"]:
                    canales.append(sib)
                else:
                    event_text += sib.get_text(" ", strip=True) + " "
        event_text = event_text.strip()

        # Asegurar que no haya espacios innecesarios
        event_text = " ".join(event_text.split())
        
        # Eliminar el texto "LIVE STREAM" repetido
        event_text = eliminar_repeticiones_live_stream(event_text)

        if canales:
            for a_tag in canales:
                canal_text = a_tag.get_text(" ", strip=True)
                eventos.append({
                    "hora": hora_evento,
                    "nombre": event_text if event_text else "Evento Desconocido",
                    "canal": canal_text,
                    "url": a_tag["href"]
                })
    return eventos

def eliminar_repeticiones_live_stream(event_text):
    # Elimina las repeticiones de "LIVE STREAM"
    while "LIVE STREAM" in event_text:
        event_text = event_text.replace("LIVE STREAM", "").strip()
    return event_text

def convertir_a_utc_mas_1(hora):
    dt = datetime.combine(datetime.today(), hora)
    dt_utc1 = dt + timedelta(hours=1)
    return dt_utc1.time()

def descargar_epg(epg_urls):
    for url in epg_urls:
        try:
            response = requests.get(url, stream=True)
            if response.status_code != 200:
                print(f"Error al descargar el EPG desde {url}")
                continue
            with gzip.open(response.raw, 'rb') as f:
                epg_data = f.read()
            print(f"EPG descargado exitosamente desde {url}")
            return epg_data
        except Exception as e:
            print(f"Error al procesar el EPG desde {url}: {e}")
    return None

def parsear_epg(epg_data):
    if not epg_data:
        print("El archivo EPG está vacío o no se pudo descargar correctamente.")
        return {}
    epg = {}
    root = ET.fromstring(epg_data)
    for channel in root.findall(".//channel"):
        channel_id = channel.get("id")
        logo = channel.find("icon").get("src") if channel.find("icon") is not None else ""
        epg[channel_id] = logo
    return epg

def guardar_lista_m3u(eventos, epg, archivo="lista.m3u"):
    eventos.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos:
            hora_ajustada = convertir_a_utc_mas_1(item["hora"])
            canal_id = item["canal"]
            nombre_evento = " ".join(item['nombre'].split())
            logo = epg.get(canal_id, "")
            extinf_line = (f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{nombre_evento}\" tvg-logo=\"{logo}\","  
                           f"{hora_ajustada.strftime('%H:%M')} - {nombre_evento} - {item['canal']}\n")
            f.write(extinf_line)
            f.write(f"{item['url']}\n")

if __name__ == "__main__":
    url_diaria = obtener_url_diaria()
    if not url_diaria:
        print("No se pudo determinar la URL diaria.")
        exit(1)
    print("URL diaria:", url_diaria)

    eventos_platinsport = extraer_eventos(url_diaria)
    print("Eventos extraídos de Platinsport:", len(eventos_platinsport))

    if not eventos_platinsport:
        print("No se encontraron eventos.")
        exit(1)

    epg_urls = [
        "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.pdf",
        "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.txt"
    ]
    epg_data = descargar_epg(epg_urls)
    if not epg_data:
        print("No se pudo descargar el EPG.")
        exit(1)

    epg = parsear_epg(epg_data)
    guardar_lista_m3u(eventos_platinsport, epg)
    print("Lista M3U actualizada correctamente con", len(eventos_platinsport), "eventos.")

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from difflib import get_close_matches

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

def normalizar_nombre(nombre):
    # Normaliza el nombre eliminando espacios adicionales y convirtiendo a minúsculas
    return re.sub(r'\s+', ' ', nombre).strip().lower()

def buscar_logo_en_archive(nombre_canal, region=None):
    tree = ET.parse('logos.xml')
    root = tree.getroot()
    
    nombres_logos = {normalizar_nombre(logo.find('name').text): logo.find('url').text for logo in root.findall('logo') if logo.find('name') is not None}
    nombre_canal_normalizado = normalizar_nombre(nombre_canal)
    
    # Incorporar la región en la búsqueda si está disponible
    if region:
        nombre_canal_normalizado = f"{region.lower()} {nombre_canal_normalizado}"
    
    closest_match = get_close_matches(nombre_canal_normalizado, nombres_logos.keys(), n=1, cutoff=0.6)
    
    if closest_match:
        return nombres_logos[closest_match[0]]
    return None

def extraer_region(nombre_evento):
    # Extrae la región del nombre del evento si está presente
    regiones = ["EUROPE", "SPAIN", "NORTH AMERICA", "SOUTH AMERICA", "ASIA", "AFRICA", "OCEANIA"]
    for region in regiones:
        if region in nombre_evento.upper():
            return region
    return None

def guardar_lista_m3u(eventos, archivo="lista.m3u"):
    eventos.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos:
            hora_ajustada = convertir_a_utc_mas_1(item["hora"])
            canal_id = normalizar_nombre(item["nombre"]).replace(" ", "_")
            # Eliminar espacios innecesarios en el nombre
            nombre_evento = " ".join(item['nombre'].split())
            region = extraer_region(nombre_evento)
            logo_url = buscar_logo_en_archive(item["canal"], region)
            extinf_line = (f"#EXTINF:-1 tvg-logo=\"{logo_url}\" tvg-id=\"{canal_id}\" tvg-name=\"{nombre_evento}\","
                           f"{hora_ajustada.strftime('%H:%M')} - {nombre_evento} - {item['canal']}\n")
            f.write(extinf_line)
            
            # Generar el enlace acestream con el nuevo formato
            acestream_id = item['url'].split('acestream://')[-1]
            nuevo_enlace = f"http://127.0.0.1:6878/ace/getstream?id={acestream_id}"
            f.write(f"{nuevo_enlace}\n")

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

    guardar_lista_m3u(eventos_platinsport)
    print("Lista M3U actualizada correctamente con", len(eventos_platinsport), "eventos.")

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

    liga_actual = None
    elements = list(contenedor.children)
    i = 0
    while i < len(elements):
        element = elements[i]
        if hasattr(element, "name") and element.name == 'p':
            liga_actual = element.get_text(strip=True)
        elif hasattr(element, "name") and element.name == 'time':
            time_val = element.get("datetime", "").strip()
            try:
                hora_evento = datetime.fromisoformat(time_val.replace("Z", "")).time()
            except Exception:
                try:
                    hora_evento = datetime.strptime(time_val, "%H:%M").time()
                except Exception:
                    hora_evento = datetime.strptime("23:59", "%H:%M").time()

            hora_evento = convertir_a_utc_mas_1(hora_evento)

            event_text = ""
            canales = []

            j = i + 1
            while j < len(elements):
                sib = elements[j]
                if hasattr(sib, "name") and (sib.name == "time" or sib.name == "p"):
                    break
                if isinstance(sib, str):
                    event_text += sib.strip() + " "
                elif hasattr(sib, "name"):
                    if sib.name == "a" and "acestream://" in sib.get("href", ""):
                        canales.append(sib)
                    else:
                        event_text += sib.get_text(" ", strip=True) + " "
                j += 1

            event_text = event_text.strip()
            event_text = " ".join(event_text.split())
            event_text = eliminar_repeticiones_live_stream(event_text)

            for a_tag in canales:
                canal_text = a_tag.get_text(" ", strip=True)
                eventos.append({
                    "hora": hora_evento,
                    "nombre": f"{liga_actual} - {event_text}" if event_text else f"{liga_actual} - Evento Desconocido",
                    "canal": canal_text,
                    "url": a_tag["href"]
                })
            i = j - 1
        i += 1
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

def buscar_logo_en_archive(nombre_canal):
    tree = ET.parse('logos.xml')
    root = tree.getroot()
    
    # Normalizar nombres y URLs de logos
    nombres_logos = {normalizar_nombre(logo.find('name').text): logo.find('url').text for logo in root.findall('logo') if logo.find('name') is not None}
    nombre_canal_normalizado = normalizar_nombre(nombre_canal)
    
    # Mejorar la precisión de la coincidencia
    closest_matches = get_close_matches(nombre_canal_normalizado, nombres_logos.keys(), n=3, cutoff=0.6)
    
    if closest_matches:
        for match in closest_matches:
            if nombre_canal_normalizado in match:
                return nombres_logos[match]
        return nombres_logos[closest_matches[0]]
    return None

def buscar_logo_en_url(nombre_canal):
    response = requests.get("https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/peticiones")
    if response.status_code != 200:
        print("Error al acceder a la URL de logos")
        return None
    
    logos_data = response.text.split('\n')
    nombre_canal_normalizado = normalizar_nombre(nombre_canal)
    
    nombres_logos = {}
    for line in logos_data:
        match = re.search(r'tvg-logo="([^"]+)" .*?tvg-id="[^"]+", ([^,]+)', line)
        if match:
            logo_url = match.group(1)
            canal_name = match.group(2).strip().lower()
            nombres_logos[canal_name] = logo_url
    
    closest_matches = get_close_matches(nombre_canal_normalizado, nombres_logos.keys(), n=3, cutoff=0.6)
    
    if closest_matches:
        for match in closest_matches:
            if nombre_canal_normalizado in match:
                return nombres_logos[match]
        return nombres_logos[closest_matches[0]]
    return None

def buscar_logo(nombre_canal):
    # Prioridad 1: Buscar en el archivo logos.xml
    logo_url = buscar_logo_en_archive(nombre_canal)
    if logo_url:
        return logo_url
    
    # Prioridad 2: Buscar en la URL proporcionada
    logo_url = buscar_logo_en_url(nombre_canal)
    if logo_url:
        return logo_url
    
    # Prioridad 3: Buscar el logo más probable utilizando solo la primera palabra del nombre del canal
    primera_palabra = nombre_canal.split(' ')[0]
    logo_url = buscar_logo_en_archive(primera_palabra)
    if logo_url:
        return logo_url
    logo_url = buscar_logo_en_url(primera_palabra)
    if logo_url:
        return logo_url
    
    return None

def limpiar_nombre_evento(nombre_evento):
    # Elimina prefijos como "NORTH AMERICA -", "SPAIN -", etc.
    return re.sub(r'^[A-Z ]+- ', '', nombre_evento)

def guardar_lista_m3u(eventos, archivo="lista.m3u"):
    eventos.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos:
            hora_ajustada = convertir_a_utc_mas_1(item["hora"])
            canal_id = normalizar_nombre(item["nombre"]).replace(" ", "_")
            # Eliminar espacios innecesarios en el nombre
            nombre_evento = limpiar_nombre_evento(" ".join(item['nombre'].split()))
            logo_url = buscar_logo(item["canal"])

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

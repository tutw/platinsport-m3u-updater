import re
import requests
import gzip
import xml.etree.ElementTree as ET
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
        match = re.search(r"(https://www\.platinsport\.com/link/\d{2}[a-z]{3}[a-z0-9]+/01\.php)", href, re.IGNORECASE)
        if match:
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
    for a in soup.find_all("a", href=True):
        if "acestream://" in a["href"]:
            texto = a.get_text(strip=True)
            hora_encontrada = None
            match = re.search(r'\b(\d{1,2}:\d{2})\b', texto)
            if match:
                try:
                    hora_encontrada = datetime.strptime(match.group(1), "%H:%M").time()
                except Exception:
                    hora_encontrada = None
            if hora_encontrada is None:
                hora_encontrada = datetime.strptime("23:59", "%H:%M").time()
            enlaces_info.append({
                "nombre": texto if texto else "Canal AceStream",
                "url": a["href"],
                "hora": hora_encontrada
            })
    return enlaces_info

def descargar_epg(url_epg):
    response = requests.get(url_epg)
    if response.status_code != 200:
        print("Error al descargar el EPG")
        return None
    with open("epg.xml.gz", "wb") as f:
        f.write(response.content)
    with gzip.open("epg.xml.gz", "rb") as gz:
        with open("epg.xml", "wb") as xml_file:
            xml_file.write(gz.read())
    print("EPG descargado y extraído correctamente")
    return "epg.xml"

def parsear_epg(epg_file):
    tree = ET.parse(epg_file)
    root = tree.getroot()
    epg_data = {}
    for channel in root.findall("channel"):
        channel_id = channel.get("id")
        display_name = channel.find("display-name").text if channel.find("display-name") is not None else None
        logo = channel.find("icon").get("src") if channel.find("icon") is not None else None
        epg_data[channel_id] = {"name": display_name, "logo": logo, "programs": []}
    for program in root.findall("programme"):
        start_time = datetime.strptime(program.get("start")[:12], "%Y%m%d%H%M")
        channel_id = program.get("channel")
        title = program.find("title").text if program.find("title") is not None else "Sin título"
        if channel_id in epg_data:
            epg_data[channel_id]["programs"].append({"start": start_time, "title": title})
    return epg_data

def enriquecer_m3u_con_epg(enlaces_info, epg_data, archivo="lista.m3u"):
    enlaces_info.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in enlaces_info:
            canal_id = item["nombre"].lower().replace(" ", "_")
            epg_info = epg_data.get(canal_id, {"logo": None, "programs": []})
            logo = epg_info["logo"]
            programa_actual = "Sin información"
            for programa in epg_info["programs"]:
                if programa["start"].time() <= item["hora"]:
                    programa_actual = programa["title"]
            extinf_line = f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\""
            if logo:
                extinf_line += f" tvg-logo=\"{logo}\""
            extinf_line += f",{item['nombre']} ({item['hora'].strftime('%H:%M')}) - {programa_actual}\n"
            f.write(extinf_line)
            f.write(f"{item['url']}\n")

if __name__ == "__main__":
    # 1. Detectar la URL diaria
    url_diaria = obtener_url_diaria()
    if not url_diaria:
        print("No se pudo determinar la URL diaria.")
        exit(1)

    # 2. Extraer los enlaces AceStream
    enlaces_info = extraer_enlaces_acestream(url_diaria)
    if not enlaces_info:
        print("No se encontraron enlaces AceStream.")
        exit(1)

    # 3. Descargar y procesar el EPG
    epg_file = descargar_epg("https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz")
    epg_data = parsear_epg(epg_file)

    # 4. Generar y guardar la lista M3U enriquecida con EPG
    enriquecer_m3u_con_epg(enlaces_info, epg_data)
    print("Lista M3U actualizada correctamente.")

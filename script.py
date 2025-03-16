import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def obtener_url_diaria():
    base_url = "https://www.platinsport.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a la página principal")
        return None
    return response.text

def extraer_eventos_y_acestream(contenido_html):
    soup = BeautifulSoup(contenido_html, "html.parser")
    eventos_info = []

    # Buscamos las secciones que contienen los eventos
    secciones_eventos = soup.find_all("p", string=re.compile(r"\d{2}:\d{2}"))
    for seccion in secciones_eventos:
        texto = seccion.get_text(strip=True)
        # Buscamos la hora (formato HH:MM)
        match_hora = re.search(r"(\d{2}:\d{2})", texto)
        if match_hora:
            hora = datetime.strptime(match_hora.group(1), "%H:%M").time()
        else:
            continue

        # Buscamos el nombre del evento
        match_evento = re.search(r"([A-Z\s]+(?:VS|vS)[A-Z\s]+)", texto)
        if match_evento:
            evento = match_evento.group(1).strip()
        else:
            evento = "Evento desconocido"

        # Buscamos los enlaces AceStream
        enlaces_acestream = re.findall(r"acestream://[a-f0-9]+", texto)
        if enlaces_acestream:
            for enlace in enlaces_acestream:
                eventos_info.append({
                    "hora": hora,
                    "evento": evento,
                    "acestream": enlace,
                    "canal": "Canal AceStream"
                })

    return eventos_info

def guardar_lista_m3u(eventos_info, archivo="lista.m3u"):
    # Ordenamos los eventos por hora
    eventos_info.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos_info:
            canal_id = item["evento"].lower().replace(" ", "_")
            extinf_line = f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['evento']}\",{item['evento']} ({item['hora'].strftime('%H:%M')})\n"
            f.write(extinf_line)
            f.write(f"{item['acestream']}\n")

if __name__ == "__main__":
    # 1. Obtener el contenido de la página diaria
    contenido_html = obtener_url_diaria()
    if not contenido_html:
        print("No se pudo obtener el contenido de la página.")
        exit(1)

    # 2. Extraer los eventos y enlaces AceStream
    eventos_info = extraer_eventos_y_acestream(contenido_html)
    if not eventos_info:
        print("No se encontraron eventos con enlaces AceStream.")
        exit(1)

    # 3. Generar y guardar la lista M3U ordenada por hora
    guardar_lista_m3u(eventos_info)
    print("Lista M3U actualizada correctamente.")

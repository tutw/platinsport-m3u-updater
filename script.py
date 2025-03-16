import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def obtener_url_diaria():
    """Obtiene la URL diaria desde la página principal de Platinsport."""
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
        # Buscar un enlace que cumpla con el patrón deseado
        match = re.search(r"(https://www\.platinsport\.com/link/\d{2}[a-z]{3}[a-z0-9]+/01\.php)", href, re.IGNORECASE)
        if match:
            url_platinsport = re.sub(r"^http://bc\.vc/\d+/", "", href)
            print("URL diaria encontrada:", url_platinsport)
            return url_platinsport
    print("No se encontró la URL diaria")
    return None

def extraer_enlaces_acestream(url):
    """Extrae los enlaces AceStream, los nombres de los eventos y sus horarios desde la URL."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces_info = []

    # Buscar todos los enlaces AceStream
    for a in soup.find_all("a", href=True):
        if "acestream://" in a["href"]:
            url_acestream = a["href"]
            
            # Buscar el contenedor de texto cercano al enlace AceStream
            contenedor_evento = a.find_parent()  # Intenta buscar información en el contenedor padre
            texto_evento = contenedor_evento.get_text(strip=True) if contenedor_evento else ""

            # Extraer el nombre del evento
            nombre_evento = "Evento Desconocido"
            if len(texto_evento) > 2:  # Validamos que el texto tenga longitud mínima
                nombre_evento = texto_evento

            # Extraer la hora asociada al evento
            hora_encontrada = None
            match_hora = re.search(r'\b(\d{1,2}:\d{2})\b', texto_evento)  # Buscar un patrón de hora HH:MM
            if match_hora:
                try:
                    hora_encontrada = datetime.strptime(match_hora.group(1), "%H:%M").time()
                except ValueError:
                    hora_encontrada = None
            
            # Si no se encuentra la hora, asignamos un valor predeterminado
            if not hora_encontrada:
                hora_encontrada = datetime.strptime("23:59", "%H:%M").time()

            # Agregar los datos recopilados a la lista de resultados
            enlaces_info.append({
                "nombre": nombre_evento.strip(),
                "url": url_acestream,
                "hora": hora_encontrada
            })

    return enlaces_info

def guardar_lista_m3u(enlaces_info, archivo="lista.m3u"):
    """Guarda los enlaces AceStream en un archivo M3U, ordenados por hora."""
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

    # 2. Extraer los enlaces AceStream
    enlaces_info = extraer_enlaces_acestream(url_diaria)
    if not enlaces_info:
        print("No se encontraron enlaces AceStream.")
        exit(1)

    # 3. Generar y guardar la lista M3U ordenada por hora
    guardar_lista_m3u(enlaces_info)
    print("Lista M3U actualizada correctamente.")

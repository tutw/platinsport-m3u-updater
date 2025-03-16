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
    """
    Extrae la información de cada evento de la página:
      - La hora del evento (usando el selector: body > div.myDiv1 > time:nth-child(1))
      - El nombre del evento (usando el selector: body > div.myDiv1 > div:nth-child(2))
      - El enlace AceStream encontrado dentro del contenedor.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces_info = []
    
    # Seleccionar cada contenedor que agrupa los datos del evento
    containers = soup.select("div.myDiv1")
    for container in containers:
        # Extraer la hora con el selector especificado
        time_tag = container.select_one("time:nth-child(1)")
        if time_tag:
            time_str = time_tag.get_text(strip=True)
            try:
                event_time = datetime.strptime(time_str, "%H:%M").time()
            except Exception:
                event_time = datetime.strptime("23:59", "%H:%M").time()
        else:
            event_time = datetime.strptime("23:59", "%H:%M").time()
            
        # Extraer el nombre del evento con el selector indicado (el elemento justo debajo)
        name_tag = container.select_one("div:nth-child(2)")
        if name_tag:
            event_name = name_tag.get_text(strip=True)
        else:
            event_name = "Evento Desconocido"
        
        # Buscar el enlace AceStream dentro de este contenedor
        a_tag = container.find("a", href=lambda href: href and href.startswith("acestream://"))
        if a_tag:
            acestream_url = a_tag["href"]
        else:
            continue
        
        # Agregar la información extraída a la lista
        enlaces_info.append({
            "nombre": event_name,
            "url": acestream_url,
            "hora": event_time
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
    
    # 2. Extraer los enlaces AceStream junto con los datos de cada evento
    enlaces_info = extraer_enlaces_acestream(url_diaria)
    if not enlaces_info:
        print("No se encontraron enlaces AceStream.")
        exit(1)
    
    # 3. Generar y guardar la lista M3U ordenada por hora
    guardar_lista_m3u(enlaces_info)
    print("Lista M3U actualizada correctamente.")

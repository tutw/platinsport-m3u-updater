import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ------------------------------------
# Fuente 1: Platinsport
# ------------------------------------
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
    eventos = []
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
            # Para los eventos de Platinsport se asigna "Platinsport" en el campo canal
            eventos.append({
                "nombre": texto if texto else "Canal AceStream",
                "url": a["href"],
                "hora": hora_encontrada,
                "canal": "Platinsport"
            })
    return eventos

# ------------------------------------
# Fuente 2: Tarjeta Roja en Vivo
# ------------------------------------
def extraer_eventos_tarjetaroja(url):
    """
    Extrae los eventos de tarjetarojaenvivo.lat.

    Se asume que cada evento aparece en un contenedor <div class="match"> con el texto:
          "(18:30) Laliga : Osasuna - Getafe"
    y, en la tabla de la derecha (con id "tablaCanales"), se listan los canales en celdas <td> en el mismo orden.
    Se utiliza un mapeo para transformar, por ejemplo, "CH10" en "beIN max 10".
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a Tarjeta Roja en Vivo:", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    
    eventos = []
    # Se asume que cada evento está en un <div class="match">
    event_containers = soup.find_all("div", class_="match")
    for container in event_containers:
        # Extraer el texto completo del contenedor (que se espera tenga formato: "(18:30) Laliga : Osasuna - Getafe")
        event_text = container.get_text(strip=True)
        m = re.match(r'^\((\d{1,2}:\d{2})\)\s*(.+)$', event_text)
        if m:
            time_str = m.group(1)
            event_name = m.group(2)
            try:
                event_time = datetime.strptime(time_str, "%H:%M").time()
            except Exception:
                event_time = datetime.strptime("23:59", "%H:%M").time()
        else:
            event_time = datetime.strptime("23:59", "%H:%M").time()
            event_name = "Evento Desconocido"
        # Intentar extraer el enlace AceStream dentro de este contenedor, si existe:
        a_tag = container.find("a", href=lambda h: h and h.startswith("acestream://"))
        stream_url = a_tag["href"] if a_tag else ""
        
        eventos.append({
            "nombre": event_name,
            "hora": event_time,
            "url": stream_url,
            "canal": ""  # se asignará luego
        })
    
    # Extraer los canales de la tabla de la derecha.
    # Se asume que la tabla tiene id "tablaCanales" y cada canal está en una celda <td>.
    channel_elements = soup.select("table#tablaCanales td")
    canales = [elem.get_text(strip=True) for elem in channel_elements]
    
    # Mapeo simple: se extrae el código de canal (por ejemplo, "CH10" de "CH10fr")
    # y se mapea a su nombre completo, por ejemplo: "CH10" -> "beIN max 10"
    channel_mapping = {
        "CH10": "beIN max 10"
        # Se pueden agregar más mapeos según sea necesario.
    }
    
    # Asumimos que la cantidad de canales corresponde (por orden) a la cantidad de eventos detectados
    for i, ev in enumerate(eventos):
        if i < len(canales):
            canal_text = canales[i]
            m_channel = re.match(r'(CH\d+)', canal_text)
            if m_channel:
                canal_code = m_channel.group(1)
            else:
                canal_code = canal_text
            ev["canal"] = channel_mapping.get(canal_code, canal_code)
        else:
            ev["canal"] = "Canal Desconocido"
    
    return eventos

# ------------------------------------
# Guardar la lista M3U combinada
# ------------------------------------
def guardar_lista_m3u(eventos, archivo="lista.m3u"):
    # Ordenamos los eventos por la hora
    eventos.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos:
            canal_id = item["nombre"].lower().replace(" ", "_")
            # Se incluye el canal (si existe) en la descripción
            if item.get("canal"):
                extinf_line = (
                    f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\","
                    f"{item['nombre']} ({item['hora'].strftime('%H:%M')}) - {item['canal']}\n"
                )
            else:
                extinf_line = (
                    f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\","
                    f"{item['nombre']} ({item['hora'].strftime('%H:%M')})\n"
                )
            f.write(extinf_line)
            f.write(f"{item['url']}\n")

# ------------------------------------
# Bloque principal: combinar ambas fuentes
# ------------------------------------
if __name__ == "__main__":
    eventos_totales = []
    
    # Fuente 1: Platinsport
    url_platinsport = obtener_url_diaria()
    if url_platinsport:
        eventos_platinsport = extraer_enlaces_acestream(url_platinsport)
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
    
    guardar_lista_m3u(eventos_totales)
    print("Lista M3U actualizada correctamente con", len(eventos_totales), "eventos.")

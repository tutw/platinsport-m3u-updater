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

def extraer_eventos(url):
    """
    Recorre el contenedor .myDiv1 para detectar cada bloque de evento.
    Cada bloque se supone que inicia con un <time> (con atributo datetime),
    seguido del texto del evento y de algunos enlaces <a> con enlaces AceStream para cada canal.
    
    Para cada <time> se recogen:
      - Hora: extraída de time['datetime'] (convertida a un objeto time)
      - Nombre del evento: el texto que aparece después del <time> hasta el siguiente <time>
      - Canales: cada enlace <a> que aparece en ese bloque; del enlace se extrae:
            * El texto (nombre del canal)
            * La URL (que comienza con "acestream://")
    Se crea una entrada por cada enlace <a> en el bloque.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    eventos = []
    
    # Obtén el contenedor de los eventos
    contenedor = soup.find("div", class_="myDiv1")
    if not contenedor:
        print("No se encontró el contenedor de eventos (.myDiv1)")
        return eventos

    # Si usas .find_all("time"), obtendrás cada elemento <time> del contenedor.
    time_tags = contenedor.find_all("time")
    for tag in time_tags:
        # Extraer la hora del evento
        time_val = tag.get("datetime", "").strip()
        try:
            # Usamos fromisoformat; se quita la 'Z' en caso de que exista
            hora_evento = datetime.fromisoformat(time_val.replace("Z", "")).time()
        except Exception:
            try:
                hora_evento = datetime.strptime(time_val, "%H:%M").time()
            except Exception:
                hora_evento = datetime.strptime("23:59", "%H:%M").time()
        
        # Ahora, obtener el contenido (texto y enlaces) entre este <time> y el siguiente <time>
        # Usamos next_siblings y detenemos cuando encontramos otro <time>.
        event_text = ""
        canales = []
        for sib in tag.next_siblings:
            # Si encontramos otro <time>, detenemos el bucle
            if hasattr(sib, "name") and sib.name == "time":
                break
            # Si es un string, lo agregamos al texto
            if isinstance(sib, str):
                event_text += sib.strip() + " "
            # Si es un etiqueta, dependiendo de su tipo
            elif hasattr(sib, "name"):
                if sib.name == "a":
                    # Este es un enlace; lo agregamos a la lista de canales
                    canales.append(sib)
                else:
                    # Para otros elementos, tomamos su texto
                    event_text += sib.get_text(" ", strip=True) + " "
        event_text = event_text.strip()
        
        # Por cada enlace <a> (cada canal) en este bloque, creamos una entrada de evento.
        if canales:
            for a_tag in canales:
                canal_text = a_tag.get_text(" ", strip=True)
                eventos.append({
                    "hora": hora_evento,
                    "nombre": event_text if event_text else "Evento Desconocido",
                    "canal": canal_text,
                    "url": a_tag["href"]
                })
        else:
            # Si no hay enlaces, generamos un evento "genérico" (opcional)
            eventos.append({
                "hora": hora_evento,
                "nombre": event_text if event_text else "Evento Desconocido",
                "canal": "",
                "url": ""
            })
    return eventos

def guardar_lista_m3u(eventos, archivo="lista.m3u"):
    # Ordenamos los eventos por hora
    eventos.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos:
            # Generamos un canal_id a partir del nombre del evento
            canal_id = item["nombre"].lower().replace(" ", "_")
            extinf_line = (f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\","
                           f"{item['nombre']} ({item['hora'].strftime('%H:%M')}) - {item['canal']}\n")
            f.write(extinf_line)
            f.write(f"{item['url']}\n")

if __name__ == "__main__":
    # 1. Detectar la URL diaria de Platinsport
    url_diaria = obtener_url_diaria()
    if not url_diaria:
        print("No se pudo determinar la URL diaria.")
        exit(1)
    print("URL diaria:", url_diaria)
    
    # 2. Extraer los eventos de Platinsport (hora, nombre y canal para cada enlace AceStream)
    eventos_platinsport = extraer_eventos(url_diaria)
    print("Eventos extraídos de Platinsport:", len(eventos_platinsport))
    
    if not eventos_platinsport:
        print("No se encontraron eventos.")
        exit(1)
    
    # 3. Generar y guardar la lista M3U
    guardar_lista_m3u(eventos_platinsport)
    print("Lista M3U actualizada correctamente con", len(eventos_platinsport), "eventos.")

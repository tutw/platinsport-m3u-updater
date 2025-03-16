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

    # Recorremos todos los nodos hijos y separamos por cada <time>
    nodo_actual = None
    for elem in contenedor.contents:
        if hasattr(elem, 'name') and elem.name == "time":
            # Es el inicio de un nuevo bloque de evento.
            if nodo_actual:
                evento = procesar_bloque_evento(nodo_actual)
                if evento:
                    eventos.extend(evento)
            nodo_actual = [elem]
        else:
            if nodo_actual is not None:
                nodo_actual.append(elem)
    # Procesamos el último bloque
    if nodo_actual:
        evento = procesar_bloque_evento(nodo_actual)
        if evento:
            eventos.extend(evento)
    
    return eventos

def procesar_bloque_evento(nodos):
    """
    Procesa un bloque de nodos correspondiente a un evento.
    Se espera que el primer elemento sea un <time> y luego contenga:
    - El nombre del evento (texto plano)
    - Varias etiquetas <a> con enlaces AceStream, de las cuales se extrae el canal de TV.
    Retorna una lista de diccionarios, uno por cada enlace AceStream encontrado, incluyendo:
      "hora", "nombre", "canal" y "url"
    """
    # Extraer la hora desde el primer nodo <time>
    time_tag = nodos[0]
    hora = None
    if time_tag.has_attr("datetime"):
        time_val = time_tag["datetime"]
        try:
            hora = datetime.fromisoformat(time_val.replace("Z", "")).time()
        except Exception:
            try:
                hora = datetime.strptime(time_val, "%H:%M").time()
            except Exception:
                hora = datetime.strptime("23:59", "%H:%M").time()
    else:
        hora = datetime.strptime("23:59", "%H:%M").time()
    
    # Concatenar el texto de los nodos (ignorando los <time>) para obtener el nombre completo del evento.
    textos = []
    for nodo in nodos[1:]:
        if isinstance(nodo, str):
            textos.append(nodo.strip())
        else:
            # Si se trata de una etiqueta que no es <a>, puede tener texto
            if nodo.name != "a":
                textos.append(nodo.get_text(" ", strip=True))
    nombre_evento = " ".join(textos).strip()
    
    # Buscar todos los enlaces AceStream en los nodos y extraer el canal
    eventos_link = []
    for nodo in nodos:
        if hasattr(nodo, "find_all"):
            a_tags = nodo.find_all("a", href=True)
            for a in a_tags:
                if a["href"].startswith("acestream://"):
                    canal = a.get_text(" ", strip=True)
                    eventos_link.append({
                        "hora": hora,
                        "nombre": nombre_evento,
                        "canal": canal,
                        "url": a["href"]
                    })
    return eventos_link

def guardar_lista_m3u(eventos, archivo="lista.m3u"):
    # Ordenamos los eventos por hora
    eventos.sort(key=lambda x: x["hora"])
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in eventos:
            canal_id = item["nombre"].lower().replace(" ", "_")
            # Modificamos la descripción para que la hora aparezca primero
            extinf_line = (f"#EXTINF:-1 tvg-id=\"{canal_id}\" tvg-name=\"{item['nombre']}\","
                           f"({item['hora'].strftime('%H:%M')}) {item['nombre']} - {item['canal']}\n")
            f.write(extinf_line)
            f.write(f"{item['url']}\n")

if __name__ == "__main__":
    # URL diaria de Platinsport
    url_diaria = obtener_url_diaria()
    if not url_diaria:
        print("No se pudo determinar la URL diaria.")
        exit(1)
    print("URL diaria:", url_diaria)
    
    # Extraer eventos desde la URL diaria (Platinsport)
    eventos_platinsport = extraer_eventos(url_diaria)
    print("Eventos extraídos de Platinsport:", len(eventos_platinsport))
    
    if not eventos_platinsport:
        print("No se encontraron eventos.")
        exit(1)
        
    guardar_lista_m3u(eventos_platinsport)
    print("Lista M3U actualizada correctamente con", len(eventos_platinsport), "eventos.")

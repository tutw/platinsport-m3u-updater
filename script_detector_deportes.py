import requests
import re
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
import time

# ------------- CONFIGURACIÓN -------------
URLS_EVENTOS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]
URL_PALABRAS_CLAVE = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/LISTA%20DE%20PALABRAS%20CLAVE.txt"
SALIDA_XML = "deportes_detectados.xml"
DELAY_BETWEEN_REQUESTS = 1  # segundos
MAX_RETRIES = 3  # reintentos en caso de fallo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[logging.StreamHandler()]
)

# ------------- DICCIONARIO DE LOGOS -------------
OPENMOJI_LOGOS = {
    "Fútbol": "https://openmoji.org/data/color/svg/26BD.svg",
    "Fútbol Sala": "https://openmoji.org/data/color/svg/26BD.svg",
    "Fútbol Playa": "https://openmoji.org/data/color/svg/26BD.svg",
    "Baloncesto": "https://openmoji.org/data/color/svg/1F3C0.svg",
    "Béisbol": "https://openmoji.org/data/color/svg/26BE.svg",
    "Sóftbol": "https://openmoji.org/data/color/svg/26BE.svg",
    "Fútbol Americano": "https://openmoji.org/data/color/svg/1F3C8.svg",
    "Fútbol Canadiense": "https://openmoji.org/data/color/svg/1F3C8.svg",
    "Rugby": "https://openmoji.org/data/color/svg/1F3C9.svg",
    "Hockey sobre Hielo": "https://openmoji.org/data/color/svg/1F3D2.svg",
    "Hockey sobre Hierba": "https://openmoji.org/data/color/svg/1F3D1.svg",
    "Críquet": "https://openmoji.org/data/color/svg/1F3CF.svg",
    "Voleibol": "https://openmoji.org/data/color/svg/1F3D0.svg",
    "Vóley Playa": "https://openmoji.org/data/color/svg/1F3D0.svg",
    "Balonmano": "https://openmoji.org/data/color/svg/1F93E.svg",
    "Tenis": "https://openmoji.org/data/color/svg/1F3BE.svg",
    "Bádminton": "https://openmoji.org/data/color/svg/1F3F8.svg",
    "Tenis de Mesa": "https://openmoji.org/data/color/svg/1F3D3.svg",
    "Golf": "https://openmoji.org/data/color/svg/26F3.svg",
    "Atletismo": "https://openmoji.org/data/color/svg/1F3C3.svg",
    "Natación": "https://openmoji.org/data/color/svg/1F3CA.svg",
    "Natación Artística": "https://openmoji.org/data/color/svg/1F3CA.svg",
    "Saltos": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Waterpolo": "https://openmoji.org/data/color/svg/1F3CA.svg",
    "Natación en Aguas Abiertas": "https://openmoji.org/data/color/svg/1F3CA.svg",
    "Ciclismo en Ruta": "https://openmoji.org/data/color/svg/1F6B4.svg",
    "Ciclismo en Pista": "https://openmoji.org/data/color/svg/1F6B4.svg",
    "Ciclismo de Montaña": "https://openmoji.org/data/color/svg/1F6B4.svg",
    "BMX": "https://openmoji.org/data/color/svg/1F6B2.svg",
    "Ciclocrós": "https://openmoji.org/data/color/svg/1F6B2.svg",
    "Gimnasia Artística": "https://openmoji.org/data/color/svg/1F938.svg",
    "Gimnasia Rítmica": "https://openmoji.org/data/color/svg/1F938.svg",
    "Gimnasia en Trampolín": "https://openmoji.org/data/color/svg/1F938.svg",
    "Gimnasia Acrobática": "https://openmoji.org/data/color/svg/1F938.svg",
    "Gimnasia Aeróbica": "https://openmoji.org/data/color/svg/1F938.svg",
    "Boxeo": "https://openmoji.org/data/color/svg/1F94A.svg",
    "Judo": "https://openmoji.org/data/color/svg/1F94B.svg",
    "Taekwondo": "https://openmoji.org/data/color/svg/1F94B.svg",
    "Lucha": "https://openmoji.org/data/color/svg/1F93C.svg",
    "Esgrima": "https://openmoji.org/data/color/svg/1F5E1.svg",
    "Karate": "https://openmoji.org/data/color/svg/1F94B.svg",
    "Artes Marciales Mixtas": "https://openmoji.org/data/color/svg/1F94B.svg",
    "Kickboxing": "https://openmoji.org/data/color/svg/1F94A.svg",
    "Muay Thai": "https://openmoji.org/data/color/svg/1F94A.svg",
    "Sumo": "https://openmoji.org/data/color/svg/1F93C.svg",
    "Kendo": "",
    "Aikido": "",
    "Jiu-Jitsu Brasileño": "",
    "Sambo": "",
    "Savate": "",
    "Esquí Alpino": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Esquí de Fondo": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Saltos de Esquí": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Combinada Nórdica": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Biatlón": "",
    "Snowboard": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Esquí Acrobático / Estilo Libre": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Patinaje Artístico sobre Hielo": "",
    "Patinaje de Velocidad sobre Hielo": "",
    "Patinaje de Velocidad sobre Hielo en Pista Corta": "",
    "Curling": "https://openmoji.org/data/color/svg/1F94C.svg",
    "Bobsleigh": "",
    "Skeleton": "",
    "Luge": "",
    "Esquí de Montaña": "https://openmoji.org/data/color/svg/1F3C2.svg",
    "Surf": "https://openmoji.org/data/color/svg/1F3C4.svg",
    "Windsurf": "",
    "Kitesurf / Kiteboard": "",
    "Vela": "https://openmoji.org/data/color/svg/26F5.svg",
    "Remo": "https://openmoji.org/data/color/svg/1F6A3.svg",
    "Piragüismo / Canotaje": "https://openmoji.org/data/color/svg/1F6F6.svg",
    "Kayak Polo": "https://openmoji.org/data/color/svg/1F6F6.svg",
    "Bote Dragón": "",
    "Motonáutica": "",
    "Esquí Acuático": "",
    "Wakeboard": "",
    "Pesca Deportiva": "https://openmoji.org/data/color/svg/1F3A3.svg",
    "Apnea / Buceo Libre": "",
    "Hockey Subacuático": "",
    "Rugby Subacuático": "",
    "Fórmula 1": "https://openmoji.org/data/color/svg/1F3CE.svg",
    "Rally": "https://openmoji.org/data/color/svg/1F698.svg",
    "Carreras de Resistencia": "https://openmoji.org/data/color/svg/1F3CE.svg",
    "Turismos": "https://openmoji.org/data/color/svg/1F698.svg",
    "NASCAR": "https://openmoji.org/data/color/svg/1F3CE.svg",
    "IndyCar Series": "https://openmoji.org/data/color/svg/1F3CE.svg",
    "Fórmula E": "https://openmoji.org/data/color/svg/1F3CE.svg",
    "Karting": "https://openmoji.org/data/color/svg/1F3CE.svg",
    "Drifting": "",
    "Carreras de Aceleración": "",
    "MotoGP": "https://openmoji.org/data/color/svg/1F3CD.svg",
    "Superbikes": "https://openmoji.org/data/color/svg/1F3CD.svg",
    "Motocross": "https://openmoji.org/data/color/svg/1F3CD.svg",
    "Enduro": "https://openmoji.org/data/color/svg/1F3CD.svg",
    "Speedway": "https://openmoji.org/data/color/svg/1F3CD.svg",
    "Trial": "",
    "Carreras de Resistencia (Endurance Racing - Motos)": "",
    "Tiro con Arco": "https://openmoji.org/data/color/svg/1F3F9.svg",
    "Tiro Deportivo": "",
    "Billar": "https://openmoji.org/data/color/svg/1F3B1.svg",
    "Dardos": "https://openmoji.org/data/color/svg/1F3AF.svg",
    "Bolos": "https://openmoji.org/data/color/svg/1F3B3.svg",
    "Petanca": "",
    "Bochas / Bocce": "",
    "Skateboarding": "https://openmoji.org/data/color/svg/1F6F9.svg",
    "Escalada Deportiva": "https://openmoji.org/data/color/svg/1F9D7.svg",
    "Parkour / Freerunning": "",
    "Slackline": "",
    "Salto BASE": "",
    "Paracaidismo": "",
    "Ala Delta": "",
    "Parapente": "",
    "Raids de Aventura": "",
    "Carreras de Obstáculos": "",
    "Sandboarding / Surf de Arena": "",
    "Zorbing / Esferismo": "",
    "Street Luge": "",
    "Patinaje en Línea Agresivo": "",
    "Scootering": "",
    "Ajedrez": "https://openmoji.org/data/color/svg/265F.svg",
    "Go": "",
    "Shogi": "https://openmoji.org/data/color/svg/1F004.svg",
    "Xiangqi": "",
    "Bridge": "https://openmoji.org/data/color/svg/1F0CF.svg",
    "Damas": "https://openmoji.org/data/color/svg/1F3B2.svg",
    "Póker": "https://openmoji.org/data/color/svg/1F0CF.svg",
    "Esports": "https://openmoji.org/data/color/svg/1F579.svg",
    "Cubo de Rubik": "",
    "Pelota Vasca": "",
    "Fútbol Gaélico": "https://openmoji.org/data/color/svg/26BD.svg",
    "Hurling": "",
    "Camogie": "",
    "Sepak Takraw": "",
    "Kabaddi": "",
    "Netball": "",
    "Korfball": "",
    "Floorball": "",
    "Ultimate Frisbee": "https://openmoji.org/data/color/svg/1F94F.svg",
    "Disc Golf": "",
    "Fistball": "",
    "Orientación": "",
    "Lacrosse": "",
    "Polo": "",
    "Patinaje de Velocidad sobre Ruedas": "",
    "Hockey sobre Patines": "",
    "Hockey Línea": "",
    "Patinaje Artístico sobre Ruedas": "",
    "Squash": "",
    "Raquetbol": "",
    "Vuelo a Vela / Planeador": "",
    "Acrobacia Aérea": "",
    "Tchoukball": "",
    "Bossaball": "",
    "Roller Derby": "",
    "Quidditch": "",
    "Tiro de Cuerda / Sokatira": "",
    "Carreras de Drones": "",
    "Woodchopping / Deportes de Hacheros": "",
    "Puenting": "",
    "Juegos de Fuerza": "",
    "Halterofilia / Levantamiento de Pesas": "https://openmoji.org/data/color/svg/1F4AA.svg",
    "Levantamiento de Potencia": "https://openmoji.org/data/color/svg/1F4AA.svg",
    "Culturismo": "https://openmoji.org/data/color/svg/1F4AA.svg",
    "Doma Clásica": "",
    "Salto Ecuestre": "",
    "Concurso Completo": "",
    "Enganches": "",
    "Volteo": "",
    "Enduro Ecuestre / Raid": "",
    "Reining": "",
    "Pentatlón Moderno": "",
    "Triatlón": "",
    "Duatlón": "",
    "Acuatlón": "",
    "Canicross": "",
    "Mushing / Trineo de Perros": "",
    "Patinaje sobre Hielo Sincronizado": "",
    "Bandy": "",
    "Skibobbing": "",
}

# ------------- FUNCIONES AUXILIARES -------------

def robust_get(url, retries=MAX_RETRIES, delay=DELAY_BETWEEN_REQUESTS):
    for intento in range(retries):
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            logging.error(f"Error descargando {url}: {e} (intento {intento+1}/{retries})")
            if intento < retries - 1:
                time.sleep(delay)
    logging.error(f"No se pudo descargar {url} tras {retries} intentos.")
    return None

def extraer_diccionario_deportes(url_txt):
    logging.info("Descargando lista de palabras clave de deportes...")
    r = robust_get(url_txt)
    if not r:
        logging.error("No se pudo descargar el archivo de palabras clave.")
        return {}
    lines = r.text.splitlines()
    deportes = {}
    deporte_actual = None
    for line in lines:
        deporte_match = re.match(r'^([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ \-/&()]+)\s*$', line.strip())
        if deporte_match and not line.strip().startswith("Palabras clave"):
            deporte_actual = deporte_match.group(1).strip()
            continue
        if line.lower().startswith("palabras clave:"):
            palabras_str = line.split(":", 1)[1]
            palabras = [p.strip().lower() for p in re.split(r',|\(|\)|/|;', palabras_str) if p.strip()]
            if deporte_actual:
                if deporte_actual not in deportes:
                    deportes[deporte_actual] = set()
                deportes[deporte_actual].update(palabras)
    deportes = {dep: set([p for p in palabras if len(p) > 2]) for dep, palabras in deportes.items() if dep}
    
    # Ejemplo para ampliar palabras clave:
    # deportes.setdefault("Ciclismo", set()).update({"giro", "tour", "vuelta", "ciclismo", "etapa"})
    # Puedes añadir más deportes y palabras clave aquí según los eventos no detectados

    logging.info(f"Diccionario de deportes generado con {len(deportes)} deportes.")
    return deportes

def parse_m3u(url):
    eventos = []
    logging.info(f"Descargando y procesando archivo M3U: {url}")
    r = robust_get(url)
    if not r:
        return eventos
    for line in r.text.splitlines():
        if line.startswith("#EXTINF"):
            match = re.search(r',(.+)$', line)
            if match:
                nombre_evento = match.group(1).strip()
                eventos.append(nombre_evento)
    logging.info(f"{len(eventos)} eventos extraídos de {url}")
    return eventos

def parse_xml(url):
    eventos = []
    logging.info(f"Descargando y procesando archivo XML: {url}")
    r = robust_get(url)
    if not r:
        return eventos
    try:
        root = ET.fromstring(r.content)
        for elem in root.iter():
            if elem.text and elem.text.strip() and len(elem.text.strip()) > 4:
                eventos.append(elem.text.strip())
        logging.info(f"{len(eventos)} eventos extraídos de {url}")
    except Exception as e:
        logging.error(f"Error parseando {url}: {e}")
    return eventos

def detectar_deporte(nombre_evento, deportes_dict):
    nombre = nombre_evento.lower()
    for deporte, palabras in deportes_dict.items():
        for palabra in palabras:
            if palabra and palabra in nombre:
                return deporte
    return "desconocido"

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent(e, level + 1)
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def guardar_xml(eventos, archivo=SALIDA_XML):
    root = ET.Element("eventos")
    for evento, deporte, fuente in eventos:
        nodo_evento = ET.SubElement(root, "evento")
        ET.SubElement(nodo_evento, "nombre").text = evento
        ET.SubElement(nodo_evento, "deporte").text = deporte
        ET.SubElement(nodo_evento, "fuente").text = fuente
        logo_url = OPENMOJI_LOGOS.get(deporte, "")
        ET.SubElement(nodo_evento, "logo").text = logo_url
    indent(root)
    tree = ET.ElementTree(root)
    tree.write(archivo, encoding="utf-8", xml_declaration=True)
    logging.info(f"Archivo XML guardado con {len(eventos)} eventos: {archivo}")

# ------------- EJECUCIÓN PRINCIPAL -------------
if __name__ == "__main__":
    inicio = datetime.now()
    logging.info("Inicio de ejecución de script_detector_deportes.py")
    deportes_dict = extraer_diccionario_deportes(URL_PALABRAS_CLAVE)
    if not deportes_dict:
        logging.error("No se pudo construir el diccionario de deportes. Fin del script.")
        exit(1)
    resultados = []
    no_detectados = []
    total_eventos = 0

    for url in URLS_EVENTOS:
        time.sleep(DELAY_BETWEEN_REQUESTS)  # Espera entre descargas para evitar 429
        if url.endswith(".m3u"):
            eventos = parse_m3u(url)
        elif url.endswith(".xml"):
            eventos = parse_xml(url)
        else:
            logging.warning(f"Extensión no reconocida: {url}")
            continue
        for evento in eventos:
            total_eventos += 1
            deporte = detectar_deporte(evento, deportes_dict)
            if not deporte or deporte == "desconocido":
                no_detectados.append(evento)
                logging.debug(f"No detectado: {evento}")
            else:
                logging.debug(f"Detectado: '{evento}' => {deporte}")
            resultados.append((evento, deporte if deporte else "desconocido", url))

    guardar_xml(resultados, archivo=SALIDA_XML)
    fin = datetime.now()
    logging.info(f"Procesados {total_eventos} eventos en total.")
    logging.info(f"Deportes no detectados: {len(no_detectados)}")
    if no_detectados:
        logging.info("Ejemplos de eventos NO detectados:")
        for e in no_detectados[:10]:
            logging.info(f"  - {e}")
        logging.info("Considera ampliar el diccionario de palabras clave si algunos deportes conocidos no se detectan.")
    logging.info(f"Duración total: {fin-inicio}")

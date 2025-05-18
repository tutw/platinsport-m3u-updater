import requests
import xml.etree.ElementTree as ET
import re
from transformers import pipeline

# Modelo ligero y rápido
classifier = pipeline("zero-shot-classification", model="joeddav/distilbert-base-uncased-mnli")

deportes = [
"fútbol", "fútbol sala", "baloncesto", "balonmano", "voleibol", "tenis", "pádel",
    "tenis de mesa", "ping pong", "bádminton", "squash", "béisbol", "softbol", "hockey",
    "hockey sobre hielo", "hockey sobre césped", "rugby", "fútbol americano", "cricket",
    "golf", "atletismo", "natación", "waterpolo", "saltos", "nado sincronizado", "remo",
    "piragüismo", "surf", "windsurf", "vela", "esquí", "snowboard", "patinaje artístico",
    "patinaje velocidad", "ciclismo", "ciclismo en pista", "ciclismo de montaña", "bmx",
    "motociclismo", "motoGP", "superbike", "automovilismo", "fórmula 1", "rally", "karting",
    "boxeo", "kickboxing", "muay thai", "mma", "judo", "karate", "taekwondo", "lucha libre",
    "lucha grecorromana", "halterofilia", "esgrima", "gimnasia artística", "gimnasia rítmica",
    "triatlón", "duatlón", "pentatlón", "biatlón", "escalada", "alpinismo", "paracaidismo",
    "tiro con arco", "tiro olímpico", "polo", "cróquet", "curling", "billar", "snooker",
    "dardos", "ajedrez", "eSports", "sumo", "petanca", "pesca deportiva", "boccia",
    "deportes adaptados", "skate", "parkour", "orientación", "canicross", "mountain bike",
    "maratón", "ultra maratón", "trail running", "senderismo", "marchas", "caminar deportivo",
    "trineo", "bobsleigh", "luge", "skeleton", "rugby 7", "rugby league", "netball",
    "floorball", "ultimate frisbee", "lacrosse", "softball", "campeonatos escolares",
    "campeonatos universitarios", "culturismo", "powerlifting", "strongman", "parkour",
    "crossfit"
]

urls = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]

def detectar_deporte_ia(nombre_evento):
    try:
        resultado = classifier(nombre_evento, deportes)
        return resultado["labels"][0]
    except Exception:
        return "desconocido"

def parse_m3u(content):
    eventos = []
    for line in content.splitlines():
        if line.startswith("#EXTINF"):
            m = re.search(r',(.+)$', line)
            if m:
                nombre_evento = m.group(1).strip()
                eventos.append(nombre_evento)
    return eventos

def parse_xml(content):
    eventos = []
    try:
        root = ET.fromstring(content)
        for channel in root.findall(".//channel"):
            nombre_evento = None
            for tag in ["display-name", "name"]:
                elem = channel.find(tag)
                if elem is not None and elem.text:
                    nombre_evento = elem.text.strip()
                    break
            if nombre_evento:
                eventos.append(nombre_evento)
    except Exception:
        pass
    return eventos

resultados = []

for url in urls:
    print(f"Procesando {url}")
    r = requests.get(url)
    if r.status_code == 200:
        content = r.text
        if url.endswith('.m3u'):
            eventos = parse_m3u(content)
        elif url.endswith('.xml'):
            eventos = parse_xml(content)
        else:
            continue
        for evento in eventos:
            deporte = detectar_deporte_ia(evento)
            print(f"Evento: {evento} | Deporte: {deporte}")
            resultados.append((evento, deporte))
    else:
        print(f"No se pudo obtener {url}")

# Crea el XML de salida
root = ET.Element("eventos")
for nombre, deporte in resultados:
    evento_elem = ET.SubElement(root, "evento")
    ET.SubElement(evento_elem, "nombre").text = nombre
    ET.SubElement(evento_elem, "deporte").text = deporte

tree = ET.ElementTree(root)
tree.write("deportes-detectados.xml", encoding="utf-8", xml_declaration=True)
print("Archivo deportes-detectados.xml generado correctamente.")

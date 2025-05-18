import requests
import xml.etree.ElementTree as ET
import re
from transformers import pipeline

# Inicializa el modelo zero-shot de HuggingFace
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Lista de deportes candidatos (puedes añadir más si lo deseas)
deportes = [
    "fútbol", "baloncesto", "tenis", "motociclismo", "fórmula 1",
    "béisbol", "boxeo", "ciclismo", "golf", "rugby", "voleibol", "atletismo"
]

# URLs de las listas a analizar
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
    except Exception as e:
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
        # Busca nodos con display-name o name
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

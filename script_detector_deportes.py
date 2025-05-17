import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

DICCIONARIO_XML = "LISTA DE PALABRAS CLAVE.xml"
SALIDA_XML = os.path.abspath("deportes_detectados.xml")
URLS_EVENTOS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]

def normalizar_texto(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = re.sub(r'[^\w\s]', '', texto)
    return texto.strip()

def cargar_diccionario_xml(ruta_xml):
    if not os.path.exists(ruta_xml):
        raise FileNotFoundError(f"No se encontró el diccionario XML: {ruta_xml}")
    tree = ET.parse(ruta_xml)
    root = tree.getroot()
    deportes = {}
    for deporte in root.findall("Deporte"):
        nombre = deporte.get("Nombre")
        palabras = set()
        for palabra in deporte.find("PalabrasClave").findall("Palabra"):
            palabras.add(normalizar_texto(palabra.text or ""))
        deportes[nombre] = palabras
    return deportes

def parse_m3u(url):
    import requests
    eventos = []
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        for line in r.text.splitlines():
            if line.startswith("#EXTINF"):
                match = re.search(r',(.+)$', line)
                if match:
                    nombre_evento = match.group(1).strip()
                    eventos.append(nombre_evento)
    except Exception:
        pass
    return eventos

def parse_xml(url):
    import requests
    eventos = []
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for elem in root.iter():
            if elem.text and elem.text.strip() and len(elem.text.strip()) > 4:
                eventos.append(elem.text.strip())
    except Exception:
        pass
    return eventos

def detectar_deporte(nombre_evento, deportes_dict):
    texto = normalizar_texto(nombre_evento)
    for deporte, palabras in deportes_dict.items():
        for palabra in palabras:
            if palabra and palabra in texto:
                return deporte
    return None

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
        ET.SubElement(nodo_evento, "logo").text = ""  # Opcional
    indent(root)
    tree = ET.ElementTree(root)
    tree.write(archivo, encoding="utf-8", xml_declaration=True)
    print(f"Archivo XML guardado con {len(eventos)} eventos: {archivo}")

def sugerir_palabras_eventos(eventos):
    palabras = []
    frases = []
    for evento in eventos:
        evento_norm = normalizar_texto(evento)
        tokens = evento_norm.split()
        palabras += [w for w in tokens if len(w) >= 4]
        for i in range(len(tokens)-1):
            frases.append(' '.join(tokens[i:i+2]))
        for i in range(len(tokens)-2):
            frases.append(' '.join(tokens[i:i+3]))
    counter_palabras = Counter(palabras)
    counter_frases = Counter(frases)
    sugeridas = set()
    for palabra, freq in counter_palabras.most_common(10):
        sugeridas.add(palabra)
    for frase, freq in counter_frases.most_common(10):
        sugeridas.add(frase)
    return sugeridas

def retroalimentar_diccionario_xml(ruta_xml, no_detectados_por_deporte):
    tree = ET.parse(ruta_xml)
    root = tree.getroot()
    deportes_xml = {deporte.get("Nombre"): deporte for deporte in root.findall("Deporte")}
    for deporte, eventos in no_detectados_por_deporte.items():
        nuevas_claves = sugerir_palabras_eventos(eventos)
        if deporte not in deportes_xml:
            # Crear nuevo bloque Deporte
            bloque_dep = ET.SubElement(root, "Deporte", Nombre=deporte)
            palabras_elem = ET.SubElement(bloque_dep, "PalabrasClave")
        else:
            bloque_dep = deportes_xml[deporte]
            palabras_elem = bloque_dep.find("PalabrasClave")
            if palabras_elem is None:
                palabras_elem = ET.SubElement(bloque_dep, "PalabrasClave")
        # Añadir solo palabras/frases nuevas
        existentes = set(normalizar_texto(palabra.text or "") for palabra in palabras_elem.findall("Palabra"))
        añadidas = 0
        for clave in nuevas_claves:
            if clave not in existentes:
                ET.SubElement(palabras_elem, "Palabra").text = clave
                añadidas += 1
        if añadidas:
            print(f"Retroalimentado '{deporte}' con {añadidas} nuevas palabras/frases.")
    indent(root)
    tree.write(ruta_xml, encoding="utf-8", xml_declaration=True)
    print("Diccionario XML retroalimentado correctamente.")

if __name__ == "__main__":
    inicio = datetime.now()
    print(f"Guardará el XML en: {SALIDA_XML}")
    deportes_dict = cargar_diccionario_xml(DICCIONARIO_XML)
    resultados = []
    no_detectados = []
    no_detectados_por_deporte = {}
    total_eventos = 0

    for url in URLS_EVENTOS:
        if url.endswith(".m3u"):
            eventos = parse_m3u(url)
        elif url.endswith(".xml"):
            eventos = parse_xml(url)
        else:
            continue
        for evento in eventos:
            total_eventos += 1
            deporte = detectar_deporte(evento, deportes_dict)
            if not deporte:
                deporte = "desconocido"
                no_detectados.append(evento)
                no_detectados_por_deporte.setdefault(deporte, []).append(evento)
            resultados.append((evento, deporte, url))

    print("Eventos a guardar:", len(resultados))
    print("Ruta de guardado:", SALIDA_XML)
    guardar_xml(resultados, archivo=SALIDA_XML)

    # Retroalimenta el diccionario XML salvo para "desconocido"
    dict_sin_desconocido = {k: v for k, v in no_detectados_por_deporte.items() if k != "desconocido"}
    if dict_sin_desconocido:
        print("\nRetroalimentando el diccionario LISTA DE PALABRAS CLAVE.xml ...")
        retroalimentar_diccionario_xml(DICCIONARIO_XML, dict_sin_desconocido)

    fin = datetime.now()
    print(f"Procesados {total_eventos} eventos en total.")
    print(f"Deportes no detectados: {len(no_detectados)}")
    if no_detectados:
        print("Ejemplos de eventos NO detectados:")
        for e in no_detectados[:10]:
            print(f"  - {e}")
    print(f"Duración total: {fin-inicio}")
    print(f"FIN. XML generado en: {SALIDA_XML}\n")

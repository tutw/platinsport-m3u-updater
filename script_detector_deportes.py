import os
import re
import time
import requests
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

DICCIONARIO = "LISTA DE PALABRAS CLAVE.txt"
SALIDA_XML = os.path.abspath("deportes_detectados.xml")
URLS_EVENTOS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]
URL_PALABRAS_CLAVE = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/LISTA%20DE%20PALABRAS%20CLAVE.txt"

def normalizar_texto(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = re.sub(r'[^\w\s]', '', texto)
    return texto

def robust_get(url, retries=3, delay=1):
    for _ in range(retries):
        try:
            r = requests.get(url)
            r.raise_for_status()
            return r
        except Exception:
            time.sleep(delay)
    return None

def extraer_diccionario_deportes(local_path):
    if not os.path.exists(local_path):
        r = robust_get(URL_PALABRAS_CLAVE)
        if not r:
            print("No se pudo descargar el archivo de palabras clave.")
            return {}
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(r.text)
    lines = open(local_path, encoding="utf-8").read().splitlines()
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
                deportes.setdefault(deporte_actual, set()).update([normalizar_texto(p) for p in palabras])
    deportes = {dep: set([normalizar_texto(p) for p in palabras if len(p) > 2]) for dep, palabras in deportes.items() if dep}
    return deportes

def parse_m3u(url):
    eventos = []
    r = robust_get(url)
    if not r:
        return eventos
    for line in r.text.splitlines():
        if line.startswith("#EXTINF"):
            match = re.search(r',(.+)$', line)
            if match:
                nombre_evento = match.group(1).strip()
                eventos.append(nombre_evento)
    return eventos

def parse_xml(url):
    eventos = []
    r = robust_get(url)
    if not r:
        return eventos
    try:
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
            palabra = palabra.strip()
            if not palabra:
                continue
            if palabra in texto:
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
    try:
        root = ET.Element("eventos")
        for evento, deporte, fuente in eventos:
            nodo_evento = ET.SubElement(root, "evento")
            ET.SubElement(nodo_evento, "nombre").text = evento
            ET.SubElement(nodo_evento, "deporte").text = deporte
            ET.SubElement(nodo_evento, "fuente").text = fuente
            ET.SubElement(nodo_evento, "logo").text = ""  # Pon aquí lógica para logos si quieres
        indent(root)
        tree = ET.ElementTree(root)
        tree.write(archivo, encoding="utf-8", xml_declaration=True)
        print(f"Archivo XML guardado con {len(eventos)} eventos: {archivo}")
    except Exception as exc:
        print(f"ERROR al guardar XML: {exc}")

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

def buscar_deporte_duckduckgo(evento):
    # Rotación de user-agent
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    }
    url = f"https://duckduckgo.com/html/?q={requests.utils.quote(evento)}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if not r.ok:
            return "desconocido"
        html = r.text.lower()
        # Inferencia simple por keywords de deporte en SERP
        claves_deporte = {
            "Fútbol": ["futbol", "fútbol", "soccer", "liga", "champions", "bundesliga", "serie a", "laliga", "premier league", "segunda division"],
            "Baloncesto": ["basket", "baloncesto", "nba", "acb", "liga endesa", "bàsquet", "basketball"],
            "Ciclismo": ["ciclismo", "cycling", "giro", "tour", "vuelta", "uci"],
            "Automovilismo": ["f1", "formula 1", "nascar", "rally", "indycar", "motogp", "gran premio", "superbike"],
            "Tenis": ["tenis", "atp", "wta", "grand slam", "open"],
            "Rugby": ["rugby", "six nations", "top 14", "super rugby"],
            "Voleibol": ["voleibol", "volleyball", "volei", "superliga", "cev", "liga mundial"],
            "Balonmano": ["balonmano", "handball", "asobal", "ehf", "liga asobal"],
            "Hockey": ["hockey", "nhl", "khl", "liga hockey"],
            "Golf": ["golf", "pga", "masters"],
            "Beisbol": ["beisbol", "béisbol", "mlb", "major league"],
            "Esgrima": ["esgrima", "fencing"],
        }
        for deporte, palabras in claves_deporte.items():
            if any(p in html for p in palabras):
                return deporte
    except Exception:
        pass
    return "desconocido"

def actualizar_diccionario(no_detectados_por_deporte):
    if not os.path.exists(DICCIONARIO):
        print(f"¡No se encuentra el diccionario {DICCIONARIO}!")
        return
    with open(DICCIONARIO, encoding="utf-8") as f:
        texto = f.read()
    for deporte, eventos in no_detectados_por_deporte.items():
        nuevas_claves = sugerir_palabras_eventos(eventos)
        patron = r"({}\s*\nPalabras clave:)([^\n]+)".format(re.escape(deporte))
        m = re.search(patron, texto, re.IGNORECASE)
        if not m:
            texto += f"\n{deporte}\nPalabras clave: {', '.join(nuevas_claves)}\n"
            print(f"Creada nueva sección en el diccionario para: {deporte}")
            continue
        inicio, claves = m.groups()
        lista = [x.strip() for x in claves.split(",")]
        añadidas = 0
        for n in nuevas_claves:
            if n not in lista:
                lista.append(n)
                añadidas += 1
        if añadidas:
            nuevas_linea = ", ".join(lista)
            texto = re.sub(patron, r"\1 " + nuevas_linea, texto, flags=re.IGNORECASE)
            print(f"Actualizado {deporte} con {añadidas} nuevas palabras/frases.")
    with open(DICCIONARIO, "w", encoding="utf-8") as f:
        f.write(texto)
    print("Diccionario retroalimentado automáticamente.")

if __name__ == "__main__":
    inicio = datetime.now()
    print(f"Guardará el XML en: {SALIDA_XML}")
    deportes_dict = extraer_diccionario_deportes(DICCIONARIO)
    resultados = []
    no_detectados = []
    no_detectados_por_deporte = {}
    total_eventos = 0

    for url in URLS_EVENTOS:
        time.sleep(1)
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
                deporte_sugerido = buscar_deporte_duckduckgo(evento)
                no_detectados.append(evento)
                no_detectados_por_deporte.setdefault(deporte_sugerido, []).append(evento)
            resultados.append((evento, deporte if deporte else deporte_sugerido, url))

    print("Eventos a guardar:", len(resultados))
    print("Ruta de guardado:", SALIDA_XML)
    guardar_xml(resultados, archivo=SALIDA_XML)

    if no_detectados_por_deporte:
        print("\nRetroalimentando el diccionario LISTA DE PALABRAS CLAVE.txt ...")
        actualizar_diccionario(no_detectados_por_deporte)

    fin = datetime.now()
    print(f"Procesados {total_eventos} eventos en total.")
    print(f"Deportes no detectados: {len(no_detectados)}")
    if no_detectados:
        print("Ejemplos de eventos NO detectados:")
        for e in no_detectados[:10]:
            print(f"  - {e}")
    print(f"Duración total: {fin-inicio}")
    print(f"FIN. XML generado en: {SALIDA_XML}\n")

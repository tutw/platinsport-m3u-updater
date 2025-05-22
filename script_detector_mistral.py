import requests
import xml.etree.ElementTree as ET
import os
import re
import sys
import traceback
import time
import subprocess
from xml.dom import minidom

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}

LISTAS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]

ARCHIVO_XML = "lista_deportes_detectados_mistral.xml"
ARCHIVO_LOGOS = "openmoji_logos.txt"

DEPORTES_VALIDOS = """
Fútbol / Soccer, Fútbol Sala / Futsal, Fútbol Playa / Beach Soccer, Baloncesto / Basketball, Béisbol / Baseball, Sóftbol / Softball, Fútbol Americano / American Football, Fútbol Canadiense / Canadian Football, Rugby / Rugby, Hockey sobre Hielo / Ice Hockey, Hockey sobre Hierba / Field Hockey, Críquet / Cricket, Voleibol / Volleyball, Vóley Playa / Beach Volleyball, Balonmano / Handball, Tenis / Tennis, Bádminton / Badminton, Tenis de Mesa / Table Tennis, Golf / Golf, Atletismo / Athletics, Natación / Swimming, Natación Artística / Artistic Swimming, Saltos / Diving, Waterpolo / Water Polo, Natación en Aguas Abiertas / Open Water Swimming, Ciclismo en Ruta / Road Cycling, Ciclismo en Pista / Track Cycling, Ciclismo de Montaña / Mountain Biking, BMX / BMX, Ciclocrós / Cyclocross, Gimnasia Artística / Artistic Gymnastics, Gimnasia Rítmica / Rhythmic Gymnastics, Gimnasia en Trampolín / Trampoline Gymnastics, Gimnasia Acrobática / Acrobatic Gymnastics, Gimnasia Aeróbica / Aerobic Gymnastics, Boxeo / Boxing, Judo / Judo, Taekwondo / Taekwondo, Lucha / Wrestling, Esgrima / Fencing, Karate / Karate, Artes Marciales Mixtas / Mixed Martial Arts, Kickboxing / Kickboxing, Muay Thai / Muay Thai, Sumo / Sumo, Kendo / Kendo, Aikido / Aikido, Jiu-Jitsu Brasileño / Brazilian Jiu-Jitsu, Sambo / Sambo, Savate / Savate, Esquí Alpino / Alpine Skiing, Esquí de Fondo / Cross-Country Skiing, Saltos de Esquí / Ski Jumping, Combinada Nórdica / Nordic Combined, Biatlón / Biathlon, Snowboard / Snowboarding, Esquí Acrobático / Freestyle Skiing, Patinaje Artístico sobre Hielo / Figure Skating, Patinaje de Velocidad sobre Hielo / Speed Skating, Patinaje de Velocidad sobre Hielo en Pista Corta / Short Track Speed Skating, Curling / Curling, Bobsleigh / Bobsleigh, Skeleton / Skeleton, Luge / Luge, Esquí de Montaña / Mountain Skiing, Surf / Surfing, Windsurf / Windsurfing, Kitesurf / Kiteboarding, Vela / Sailing, Remo / Rowing, Piragüismo / Canoeing, Kayak Polo / Kayak Polo, Bote Dragón / Dragon Boat, Motonáutica / Powerboating, Esquí Acuático / Water Skiing, Wakeboard / Wakeboarding, Pesca Deportiva / Sport Fishing, Apnea / Freediving, Hockey Subacuático / Underwater Hockey, Rugby Subacuático / Underwater Rugby, Fórmula 1 / Formula 1, Rally / Rally, Carreras de Resistencia / Endurance Racing, Turismos / Touring Car Racing, NASCAR / NASCAR, IndyCar Series / IndyCar Series, Fórmula E / Formula E, Karting / Karting, Drifting / Drifting, Carreras de Aceleración / Drag Racing, MotoGP / MotoGP, Superbikes / Superbikes, Motocross / Motocross, Enduro / Enduro, Speedway / Speedway, Trial / Trial, Carreras de Resistencia (Endurance Racing - Motos) / Endurance Racing (Motorcycles), Tiro con Arco / Archery, Tiro Deportivo / Shooting, Billar / Billiards, Dardos / Darts, Bolos / Bowling, Petanca / Pétanque, Bochas / Bocce, Skateboarding / Skateboarding, Escalada Deportiva / Sport Climbing, Parkour / Parkour, Slackline / Slacklining, Salto BASE / BASE Jumping, Paracaidismo / Skydiving, Ala Delta / Hang Gliding, Parapente / Paragliding, Raids de Aventura / Adventure Racing, Carreras de Obstáculos / Obstacle Racing, Sandboarding / Sandboarding, Zorbing / Zorbing, Street Luge / Street Luge, Patinaje en Línea Agresivo / Aggressive Inline Skating, Scootering / Scootering, Ajedrez / Chess, Go / Go, Shogi / Shogi, Xiangqi / Xiangqi, Bridge / Bridge, Damas / Checkers, Póker / Poker, Esports / Esports, Cubo de Rubik / Rubik's Cube, Pelota Vasca / Basque Pelota, Fútbol Gaélico / Gaelic Football, Hurling / Hurling, Camogie / Camogie, Sepak Takraw / Sepak Takraw, Kabaddi / Kabaddi, Netball / Netball, Korfball / Korfball, Floorball / Floorball, Ultimate Frisbee / Ultimate Frisbee, Disc Golf / Disc Golf, Fistball / Fistball, Orientación / Orienteering, Lacrosse / Lacrosse, Polo / Polo, Patinaje de Velocidad sobre Ruedas / Roller Speed Skating, Hockey sobre Patines / Roller Hockey, Hockey Línea / Inline Hockey, Patinaje Artístico sobre Ruedas / Artistic Roller Skating, Squash / Squash, Raquetbol / Racquetball, Vuelo a Vela / Gliding, Acrobacia Aérea / Aerobatics, Tchoukball / Tchoukball, Bossaball / Bossaball, Roller Derby / Roller Derby, Quidditch / Quidditch, Tiro de Cuerda / Tug of War, Carreras de Drones / Drone Racing, Woodchopping / Woodchopping, Puenting / Bungee Jumping, Juegos de Fuerza / Strength Sports, Halterofilia / Weightlifting, Levantamiento de Potencia / Powerlifting, Culturismo / Bodybuilding, Doma Clásica / Dressage, Salto Ecuestre / Show Jumping, Concurso Completo / Eventing, Enganches / Driving, Volteo / Vaulting, Enduro Ecuestre / Endurance Riding, Reining / Reining, Pentatlón Moderno / Modern Pentathlon, Triatlón / Triathlon, Duatlón / Duathlon, Acuatlón / Aquathlon, Canicross / Canicross, Mushing / Dog Sledding, Patinaje sobre Hielo Sincronizado / Synchronized Skating, Bandy / Bandy, Skibobbing / Skibobbing
""".replace('\n', '').strip()

def cargar_logos(filepath):
    logos = {}
    if not os.path.isfile(filepath):
        print(f"[ERROR] No se encontró el archivo de logos ({filepath}).")
        return logos
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    for match in re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', content):
        key, url = match.groups()
        logos[key.strip().lower()] = url.strip()
    return logos

def obtener_logo(deporte, logos_dict):
    deporte_norm = deporte.lower()
    if deporte_norm in logos_dict:
        return logos_dict[deporte_norm]
    for key, url in logos_dict.items():
        key_norm = key.lower()
        if deporte_norm in key_norm or key_norm in deporte_norm:
            return url
        deporte_tokens = set(deporte_norm.split())
        key_tokens = set(key_norm.split())
        if deporte_tokens & key_tokens:
            return url
    return "https://openmoji.org/data/color/svg/2753.svg"

def extraer_eventos_m3u(url):
    eventos = []
    try:
        print(f"Descargando lista M3U: {url}")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        for line in resp.text.splitlines():
            if line.startswith("#EXTINF"):
                nombre = line.split(",", 1)[-1].strip()
                if nombre:
                    eventos.append(nombre)
    except Exception as e:
        print(f"[ERROR] Leyendo {url}: {e}")
        traceback.print_exc()
    return eventos

def extraer_eventos_xml(url):
    eventos = []
    try:
        print(f"Descargando lista XML: {url}")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for event in root.findall(".//event"):
            name = event.findtext("name") or ""
            time_ = event.findtext("time") or ""
            if name.strip():
                evento = f"{time_.strip()} - {name.strip()}" if time_.strip() else name.strip()
                eventos.append(evento)
        for prog in root.findall(".//programme"):
            title = prog.findtext("title") or ""
            name = prog.findtext("name") or ""
            desc = prog.findtext("desc") or ""
            category = prog.findtext("category") or ""
            main_name = title if title.strip() else name
            if main_name.strip():
                partes = [main_name]
                if category and category.lower() not in main_name.lower():
                    partes.append(f"[{category}]")
                if desc and desc.lower() not in main_name.lower():
                    partes.append(desc)
                evento = " - ".join([p for p in partes if p.strip()])
                eventos.append(evento)
        for track in root.findall(".//track"):
            title = track.findtext("title") or ""
            if title.strip():
                eventos.append(title.strip())
    except Exception as e:
        print(f"[ERROR] Leyendo {url}: {e}")
        traceback.print_exc()
    return eventos

def quitar_nombre_canal(evento):
    # Quita el último " - Canal" si existe al final del string
    return re.sub(r'\s*-\s*[^-]+$', '', evento).strip()

def obtener_eventos_unicos(eventos):
    """
    Devuelve un diccionario: evento original -> evento base (sin canal)
    Y una lista de eventos base únicos para consultar a Mistral.
    """
    evento_base_map = {}
    eventos_base_set = set()
    for ev in eventos:
        ev_base = quitar_nombre_canal(ev)
        evento_base_map[ev] = ev_base
        eventos_base_set.add(ev_base)
    return evento_base_map, sorted(eventos_base_set)

def construir_prompt(eventos):
    prompt = (
        f"Para cada evento de la lista, indica únicamente el deporte principal al que corresponde, "
        f"seleccionando solo entre los siguientes deportes (usa exactamente el nombre de la lista):\n\n"
        f"{DEPORTES_VALIDOS}\n\n"
        "Si no puedes determinar el deporte o el evento no encaja con ninguno de la lista, responde exactamente con \"Desconocido\".\n"
        "No expliques nada, solo responde con este formato (uno por línea):\n"
        "Evento: <nombre_evento>\nDeporte: <nombre_deporte>\n\n"
        "Ejemplo de respuesta:\n"
        "Evento: Real Madrid vs Barcelona\nDeporte: Fútbol / Soccer\n"
        "Evento: Roland Garros - Final\nDeporte: Tenis / Tennis\n"
        "Evento: Equipo A vs Equipo B\nDeporte: Desconocido\n\n"
    )
    for ev in eventos:
        prompt += f"Evento: {ev}\n"
    return prompt

def preguntar_mistral(eventos, max_retries=5):
    prompt = construir_prompt(eventos)
    data = {
        "model": "mistral-small-2312",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    retries = 0
    wait_times = [30, 300]
    while retries <= max_retries:
        try:
            print("\n[DEBUG] Enviando a Mistral el siguiente prompt:")
            print(prompt)
            print("[/DEBUG]\n")
            resp = requests.post(MISTRAL_API_URL, headers=HEADERS, json=data, timeout=180)
            if resp.status_code == 429:
                wait = wait_times[retries] if retries < len(wait_times) else wait_times[-1]
                print(f"[WARNING] Rate limit excedido. Esperando {wait} segundos antes de reintentar...")
                time.sleep(wait)
                retries += 1
                continue
            resp.raise_for_status()
            respuesta = resp.json()["choices"][0]["message"]["content"]
            print("\n[DEBUG] Respuesta de Mistral:")
            print(respuesta)
            print("[/DEBUG]\n")
            return respuesta
        except Exception as e:
            print("\n[ERROR] Fallo al consultar la API de Mistral.")
            print("Petición enviada:")
            print(data)
            print("Traceback:")
            traceback.print_exc()
            if hasattr(e, 'response') and e.response is not None:
                print("Respuesta de la API:")
                print(e.response.text)
            retries += 1
            time.sleep(15)
    print(f"[FATAL ERROR] Número máximo de reintentos alcanzado al consultar Mistral.")
    sys.exit(1)

def parsear_respuesta_mistral(respuesta, eventos_enviados):
    resultados = {}
    if not respuesta:
        print("[WARNING] Respuesta vacía de Mistral.")
        for ev in eventos_enviados:
            resultados[ev] = "Desconocido"
        return resultados
    encontrados = set()
    for nombre, deporte in re.findall(r"Evento:\s*(.*?)\s*Deporte:\s*(.*?)(?:\n|$)", respuesta, re.DOTALL):
        nombre = nombre.strip()
        deporte = deporte.strip()
        if nombre:
            resultados[nombre] = deporte if deporte else "Desconocido"
            encontrados.add(nombre)
    for ev in eventos_enviados:
        if ev not in encontrados:
            print(f"[WARNING] Evento '{ev}' no devuelto por Mistral. Se asigna 'Desconocido'.")
            resultados[ev] = "Desconocido"
    return resultados

def trocear_lista(lista, n):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]

def actualizar_y_guardar_xml(deportes_dict, logos_dict, filepath):
    root = ET.Element("deportes_detectados")
    for nombre, deporte in sorted(deportes_dict.items()):
        evento_elem = ET.SubElement(root, "evento")
        ET.SubElement(evento_elem, "nombre").text = nombre
        ET.SubElement(evento_elem, "deporte").text = deporte
        ET.SubElement(evento_elem, "logo").text = obtener_logo(deporte, logos_dict)
    xmlstr = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(indent="  ", encoding="utf-8")
    with open(filepath, "wb") as f:
        f.write(xmlstr)
    print(f"[OK] Archivo {filepath} actualizado (pretty-printed).")

def subir_archivo_a_git(filepath, mensaje_commit):
    try:
        subprocess.run(["git", "add", filepath], check=True)
        res = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if res.returncode == 0:
            print(f"[INFO] No hay cambios en {filepath}, no se hace commit.")
            return
        subprocess.run([
            "git", "-c", "user.name=GitHub Action", "-c", "user.email=action@github.com",
            "commit", "-m", mensaje_commit
        ], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"[OK] El archivo {filepath} fue subido al repositorio.")
    except Exception as e:
        print(f"[ERROR] Error al subir el archivo {filepath} al repositorio.")
        traceback.print_exc()

def main():
    deportes_dict = {}
    logos_dict = cargar_logos(ARCHIVO_LOGOS)
    try:
        for url in LISTAS:
            if url.endswith(".m3u"):
                eventos = extraer_eventos_m3u(url)
            else:
                eventos = extraer_eventos_xml(url)
            evento_base_map, eventos_base_unicos = obtener_eventos_unicos(eventos)
            if not eventos_base_unicos:
                print(f"[INFO] No se encontraron eventos en {url}")
                continue
            print(f"[INFO] {url}: {len(eventos_base_unicos)} eventos base únicos detectados")
            deportes_detectados = {}
            eventos_pendientes = [e for e in eventos_base_unicos if e not in deportes_detectados]
            for chunk in trocear_lista(eventos_pendientes, 10):
                print(f"[INFO] Consultando Mistral para un lote de {len(chunk)} eventos base.")
                respuesta_mistral = preguntar_mistral(chunk)
                resultados = parsear_respuesta_mistral(respuesta_mistral, chunk)

                # Reintento extra para los eventos NO resueltos
                faltantes = [ev for ev in chunk if resultados.get(ev, "Desconocido") == "Desconocido"]
                if faltantes:
                    print(f"[INFO] Reintentando Mistral para {len(faltantes)} eventos base faltantes...")
                    time.sleep(2)
                    respuesta_reintento = preguntar_mistral(faltantes)
                    resultados_reintento = parsear_respuesta_mistral(respuesta_reintento, faltantes)
                    for nombre, deporte in resultados_reintento.items():
                        if deporte != "Desconocido":
                            resultados[nombre] = deporte
                for nombre, deporte in resultados.items():
                    if nombre not in deportes_detectados:
                        deportes_detectados[nombre] = deporte
                print("[INFO] Esperando 5 segundos para el siguiente lote...")
                time.sleep(5)
            # Asignar a cada evento original el deporte de su evento base
            for evento_original, evento_base in evento_base_map.items():
                deportes_dict[evento_original] = deportes_detectados.get(evento_base, "Desconocido")
        actualizar_y_guardar_xml(deportes_dict, logos_dict, ARCHIVO_XML)
        subir_archivo_a_git(ARCHIVO_XML, "Actualiza lista_deportes_detectados_mistral.xml")
        print("[OK] Todos los eventos han sido procesados y guardados.")
    except Exception as ex:
        print("[FATAL ERROR] Excepción no controlada:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

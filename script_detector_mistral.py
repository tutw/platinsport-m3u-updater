import requests
import xml.etree.ElementTree as ET
import os
import re
import sys
import traceback
import time
import subprocess

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
        # 1. Extraer de <event>
        for event in root.findall(".//event"):
            name = event.findtext("name") or ""
            time_ = event.findtext("time") or ""
            if name.strip():
                evento = f"{time_.strip()} - {name.strip()}" if time_.strip() else name.strip()
                eventos.append(evento)
        # 2. Extraer de <programme>
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
        # 3. Extraer de <track>
        for track in root.findall(".//track"):
            title = track.findtext("title") or ""
            if title.strip():
                eventos.append(title.strip())
        # NO extraer <name> de <channel>
        # NO extraer <display-name> de <channel>
        # NO extraer <name> sueltos fuera de <event> o <programme>
    except Exception as e:
        print(f"[ERROR] Leyendo {url}: {e}")
        traceback.print_exc()
    return eventos

def construir_prompt(eventos):
    prompt = (
        "Para cada evento, indica solo el deporte principal (por ejemplo: Fútbol, Baloncesto, Tenis, Ciclismo, etc). "
        "Si no lo sabes, pon 'Desconocido'. "
        "Si el evento contiene solo nombres de equipos o es muy escueto, intenta inferir el deporte. "
        "Formato:\nEvento: <nombre_evento>\nDeporte: <nombre_deporte>\n"
    )
    for ev in eventos:
        prompt += f"- {ev}\n"
    return prompt

def preguntar_mistral(eventos, max_retries=5):
    prompt = construir_prompt(eventos)
    data = {
        "model": "mistral-small-2312",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    retries = 0
    wait_times = [30, 300]  # 30s, 5min
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

def parsear_respuesta_mistral(respuesta):
    resultados = []
    if not respuesta:
        print("[WARNING] Respuesta vacía de Mistral.")
        return resultados
    eventos = re.findall(r"Evento:\s*(.*?)\s*Deporte:\s*(.*?)(?:\n|$)", respuesta, re.DOTALL)
    if not eventos:
        print("[WARNING] No se encontraron pares evento-deporte en la respuesta de Mistral.")
        print("Respuesta recibida:")
        print(respuesta)
    for nombre, deporte in eventos:
        nombre = nombre.strip()
        deporte = deporte.strip()
        if nombre and deporte:
            resultados.append((nombre, deporte))
    return resultados

def trocear_lista(lista, n):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]

def cargar_xml_existente(filepath):
    deportes_dict = {}
    if not os.path.isfile(filepath):
        return deportes_dict
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        for evento_elem in root.findall("evento"):
            nombre = evento_elem.findtext("nombre") or ""
            deporte = evento_elem.findtext("deporte") or ""
            if nombre and deporte:
                deportes_dict[nombre] = deporte
    except Exception as e:
        print(f"[ERROR] Al leer {filepath}: {e}")
        traceback.print_exc()
    return deportes_dict

def actualizar_y_guardar_xml(deportes_dict, filepath):
    root = ET.Element("deportes_detectados")
    for nombre, deporte in sorted(deportes_dict.items()):
        evento_elem = ET.SubElement(root, "evento")
        ET.SubElement(evento_elem, "nombre").text = nombre
        ET.SubElement(evento_elem, "deporte").text = deporte
    tree = ET.ElementTree(root)
    tree.write(filepath, encoding="utf-8", xml_declaration=True)
    print(f"[OK] Archivo {filepath} actualizado.")

def subir_archivo_a_git(filepath, mensaje_commit):
    try:
        subprocess.run(["git", "add", filepath], check=True)
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
    deportes_dict = cargar_xml_existente(ARCHIVO_XML)
    try:
        for url in LISTAS:
            if url.endswith(".m3u"):
                eventos = extraer_eventos_m3u(url)
            else:
                eventos = extraer_eventos_xml(url)
            eventos_unicos = sorted(set(eventos))
            if not eventos_unicos:
                print(f"[INFO] No se encontraron eventos en {url}")
                continue
            print(f"[INFO] {url}: {len(eventos_unicos)} eventos únicos detectados")
            eventos_pendientes = [e for e in eventos_unicos if e not in deportes_dict]
            for chunk in trocear_lista(eventos_pendientes, 10):
                print(f"[INFO] Consultando Mistral para un lote de {len(chunk)} eventos.")
                respuesta_mistral = preguntar_mistral(chunk)
                resultados = parsear_respuesta_mistral(respuesta_mistral)
                for nombre, deporte in resultados:
                    # Solo agrega si todavía no existe (evita sobrescribir)
                    if nombre not in deportes_dict:
                        deportes_dict[nombre] = deporte
                actualizar_y_guardar_xml(deportes_dict, ARCHIVO_XML)
                subir_archivo_a_git(ARCHIVO_XML, "Actualiza lista_deportes_detectados_mistral.xml (parcial)")
                print("[INFO] Esperando 5 segundos para el siguiente lote...")
                time.sleep(5)
        print("[OK] Todos los eventos han sido procesados y guardados.")
    except Exception as ex:
        print("[FATAL ERROR] Excepción no controlada:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

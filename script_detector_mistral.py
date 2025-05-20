import requests
import xml.etree.ElementTree as ET
import os
import re

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}

LISTAS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_sportsonlineci.xml",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/lista_agenda_DEPORTE-LIBRE.FANS.xml"
]

def extraer_eventos_m3u(url):
    eventos = []
    try:
        resp = requests.get(url, timeout=60)
        for line in resp.text.splitlines():
            if line.startswith("#EXTINF"):
                nombre = line.split(",", 1)[-1].strip()
                if nombre:
                    eventos.append(nombre)
    except Exception as e:
        print(f"Error leyendo {url}: {e}")
    return eventos

def extraer_eventos_xml(url):
    eventos = []
    try:
        resp = requests.get(url, timeout=60)
        root = ET.fromstring(resp.content)
        for prog in root.findall(".//programme"):
            title = prog.findtext("title")
            if title:
                eventos.append(title.strip())
        for channel in root.findall(".//channel"):
            display_name = channel.findtext("display-name")
            if display_name:
                eventos.append(display_name.strip())
    except Exception as e:
        print(f"Error leyendo {url}: {e}")
    return eventos

def construir_prompt(eventos):
    prompt = (
        "Te proporciono una lista de nombres de eventos deportivos. "
        "Para cada evento, responde solo con el nombre exacto del deporte principal al que pertenece el evento. "
        "Si no puedes identificar el deporte, responde únicamente 'Desconocido'. "
        "Devuelve la respuesta en el siguiente formato exacto, sin explicaciones ni frases adicionales:\n\n"
        "Evento: <nombre_evento>\nDeporte: <nombre_deporte>\n\n"
        "Lista de eventos:\n"
    )
    for ev in eventos:
        prompt += f"- {ev}\n"
    prompt += "\nRecuerda: responde solo con la lista en el formato indicado, un bloque por cada evento."
    return prompt

def preguntar_mistral(eventos):
    prompt = construir_prompt(eventos)
    data = {
        "model": "mistral-small-2312",  # Mistral Small 3.1 (25.03)
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    try:
        # Timeout largo para esperar la respuesta completa de Mistral
        resp = requests.post(MISTRAL_API_URL, headers=HEADERS, json=data, timeout=180)
        resp.raise_for_status()
        respuesta = resp.json()["choices"][0]["message"]["content"]
        return respuesta
    except Exception as e:
        print(f"Error consultando Mistral: {e}")
        return ""

def parsear_respuesta_mistral(respuesta):
    resultados = []
    # Busca pares Evento: ... Deporte: ... en la respuesta (soporta saltos de línea y variantes)
    eventos = re.findall(r"Evento:\s*(.*?)\s*Deporte:\s*(.*?)(?:\n|$)", respuesta)
    for nombre, deporte in eventos:
        resultados.append((nombre.strip(), deporte.strip()))
    return resultados

def main():
    todos_resultados = []
    for url in LISTAS:
        if url.endswith(".m3u"):
            eventos = extraer_eventos_m3u(url)
        else:
            eventos = extraer_eventos_xml(url)
        eventos_unicos = sorted(set(eventos))
        if not eventos_unicos:
            continue
        print(f"{url}: {len(eventos_unicos)} eventos únicos detectados")
        respuesta_mistral = preguntar_mistral(eventos_unicos)
        resultados = parsear_respuesta_mistral(respuesta_mistral)
        todos_resultados.extend(resultados)
    
    # Elimina duplicados globalmente (por nombre de evento)
    vistos = set()
    resultados_finales = []
    for nombre, deporte in todos_resultados:
        if nombre not in vistos:
            vistos.add(nombre)
            resultados_finales.append((nombre, deporte))

    # Generar XML vertical
    root = ET.Element("deportes_detectados")
    for nombre, deporte in resultados_finales:
        evento_elem = ET.SubElement(root, "evento")
        ET.SubElement(evento_elem, "nombre").text = nombre
        ET.SubElement(evento_elem, "deporte").text = deporte

    tree = ET.ElementTree(root)
    tree.write("lista_deportes_detectados_mistral.xml", encoding="utf-8", xml_declaration=True)
    print("Archivo lista_deportes_detectados_mistral.xml generado.")

if __name__ == "__main__":
    main()

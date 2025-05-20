import requests
import xml.etree.ElementTree as ET
import os
import re
import sys
import traceback

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
        # Enriquecemos cada evento con información adicional si existe
        for prog in root.findall(".//programme"):
            title = prog.findtext("title") or ""
            desc = prog.findtext("desc") or ""
            category = prog.findtext("category") or ""
            # Unimos los campos disponibles para dar máximo contexto
            partes = [title]
            if category and category.lower() not in title.lower():
                partes.append(f"[{category}]")
            if desc and desc.lower() not in title.lower():
                partes.append(desc)
            evento = " - ".join([p for p in partes if p.strip()])
            if evento.strip():
                eventos.append(evento.strip())
        for channel in root.findall(".//channel"):
            display_name = channel.findtext("display-name")
            if display_name:
                eventos.append(display_name.strip())
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

def preguntar_mistral(eventos):
    prompt = construir_prompt(eventos)
    data = {
        "model": "mistral-small-2312",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    try:
        print("\n[DEBUG] Enviando a Mistral el siguiente prompt:")
        print(prompt)
        print("[/DEBUG]\n")
        resp = requests.post(MISTRAL_API_URL, headers=HEADERS, json=data, timeout=180)
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

def main():
    todos_resultados = []
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
            # Procesar por lotes de 3 para evitar truncamientos
            for chunk in trocear_lista(eventos_unicos, 3):
                print(f"[INFO] Consultando Mistral para un lote de {len(chunk)} eventos.")
                respuesta_mistral = preguntar_mistral(chunk)
                resultados = parsear_respuesta_mistral(respuesta_mistral)
                if resultados:
                    todos_resultados.extend(resultados)
                else:
                    print("[WARNING] El lote de eventos no devolvió resultados válidos.")
        vistos = set()
        resultados_finales = []
        for nombre, deporte in todos_resultados:
            if nombre not in vistos:
                vistos.add(nombre)
                resultados_finales.append((nombre, deporte))
        if not resultados_finales:
            print("[ERROR] No se obtuvieron resultados finales. El XML no se generará.")
            sys.exit(1)
        root = ET.Element("deportes_detectados")
        for nombre, deporte in resultados_finales:
            evento_elem = ET.SubElement(root, "evento")
            ET.SubElement(evento_elem, "nombre").text = nombre
            ET.SubElement(evento_elem, "deporte").text = deporte
        tree = ET.ElementTree(root)
        tree.write("lista_deportes_detectados_mistral.xml", encoding="utf-8", xml_declaration=True)
        print("[OK] Archivo lista_deportes_detectados_mistral.xml generado correctamente.")
    except Exception as ex:
        print("[FATAL ERROR] Excepción no controlada:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

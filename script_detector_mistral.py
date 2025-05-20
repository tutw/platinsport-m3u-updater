import requests
import xml.etree.ElementTree as ET
import os

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
        resp = requests.get(url)
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
        resp = requests.get(url)
        root = ET.fromstring(resp.content)
        # Intenta extraer títulos de programas (EPG)
        for prog in root.findall(".//programme"):
            title = prog.findtext("title")
            if title:
                eventos.append(title.strip())
        # Intenta extraer nombres de canales (por si acaso)
        for channel in root.findall(".//channel"):
            display_name = channel.findtext("display-name")
            if display_name:
                eventos.append(display_name.strip())
    except Exception as e:
        print(f"Error leyendo {url}: {e}")
    return eventos

def preguntar_mistral(nombres_eventos):
    resultados = []
    for nombre in nombres_eventos:
        prompt = (
            "Para el siguiente evento deportivo, responde solo con el nombre exacto del deporte principal al que pertenece el evento. "
            "Si no puedes identificar el deporte, responde únicamente 'Desconocido'. No incluyas explicaciones ni frases adicionales.\n"
            f"Evento: '{nombre}'"
        )
        data = {
            "model": "mistral-tiny",  # Cambia si usas otro modelo
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0
        }
        try:
            resp = requests.post(MISTRAL_API_URL, headers=HEADERS, json=data, timeout=10)
            resp.raise_for_status()
            deporte = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error con Mistral para '{nombre}': {e}")
            deporte = "Desconocido"
        resultados.append((nombre, deporte))
    return resultados

def main():
    eventos = []
    for url in LISTAS:
        if url.endswith(".m3u"):
            eventos += extraer_eventos_m3u(url)
        else:
            eventos += extraer_eventos_xml(url)
    nombres_unicos = sorted(set(eventos))  # Solo nombres únicos, ordenados

    print(f"Total eventos únicos detectados: {len(nombres_unicos)}")

    resultados = preguntar_mistral(nombres_unicos)

    # Generar XML vertical
    root = ET.Element("deportes_detectados")
    for nombre, deporte in resultados:
        evento_elem = ET.SubElement(root, "evento")
        ET.SubElement(evento_elem, "nombre").text = nombre
        ET.SubElement(evento_elem, "deporte").text = deporte

    tree = ET.ElementTree(root)
    tree.write("lista_deportes_detectados_mistral.xml", encoding="utf-8", xml_declaration=True)
    print("Archivo lista_deportes_detectados_mistral.xml generado.")

if __name__ == "__main__":
    main()

import requests
import xml.etree.ElementTree as ET
import difflib
import re

M3U_URLS = [
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_icastresana.m3u",
    "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u"
]
XML_URL = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_deportes_detectados_mistral.xml"
OUTPUT_M3U = "lista_eventos_UNIFICADOS.m3u"

def descargar_archivo(url):
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.text

def parsear_logos_xml(xml_content):
    logos_dict = {}
    root = ET.fromstring(xml_content)
    for evento in root.findall(".//evento"):
        nombre_evento = evento.findtext("nombre")
        logo = evento.findtext("logo")
        if nombre_evento and logo:
            logos_dict[nombre_evento.strip().lower()] = logo.strip()
    return logos_dict

def buscar_logo_laxo(nombre_evento, logos_dict):
    nombre_evento = nombre_evento.lower().strip()
    posibles = difflib.get_close_matches(nombre_evento, logos_dict.keys(), n=1, cutoff=0.6)
    if posibles:
        return logos_dict[posibles[0]]
    return None

def reemplazar_logo_por_evento(linea, logos_dict):
    if ',' in linea:
        nombre_evento = linea.split(',', 1)[1].strip()
        logo_nuevo = buscar_logo_laxo(nombre_evento, logos_dict)
        if logo_nuevo:
            if 'tvg-logo="' in linea:
                linea = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo_nuevo}"', linea)
            else:
                linea = linea.replace('#EXTINF:-1', f'#EXTINF:-1 tvg-logo="{logo_nuevo}"')
    return linea

def unificar_m3u_y_reemplazar_logos():
    # Descargar y unir los M3U
    eventos = []
    for url in M3U_URLS:
        contenido = descargar_archivo(url)
        lineas = contenido.strip().splitlines()
        eventos.extend(lineas)

    # Descargar y parsear el XML
    xml_content = descargar_archivo(XML_URL)
    logos_dict = parsear_logos_xml(xml_content)

    # Procesar y escribir el archivo unificado
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        encabezado = "#EXTM3U"
        if eventos and eventos[0].startswith("#EXTM3U"):
            f.write(encabezado + "\n")
            eventos = [l for l in eventos if l.strip() != "#EXTM3U"]
        for linea in eventos:
            if linea.startswith("#EXTINF"):
                linea = reemplazar_logo_por_evento(linea, logos_dict)
            f.write(linea + "\n")

if __name__ == "__main__":
    unificar_m3u_y_reemplazar_logos()
    print(f"Archivo unificado guardado como: {OUTPUT_M3U}")

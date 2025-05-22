import requests
import xml.etree.ElementTree as ET
import difflib
import re

M3U_URLS = [
    ("https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_icastresana.m3u", "eventos_icastresana_OPENMOJI.m3u"),
    ("https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista.m3u", "eventos_platinsport_OPENMOJI.m3u")
]
XML_URL = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_deportes_detectados_mistral.xml"

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

def procesar_y_guardar_m3u(url, nombre_salida, logos_dict):
    contenido = descargar_archivo(url)
    lineas = contenido.strip().splitlines()
    with open(nombre_salida, "w", encoding="utf-8") as f:
        encabezado = "#EXTM3U"
        if lineas and lineas[0].startswith("#EXTM3U"):
            f.write(encabezado + "\n")
            lineas = [l for l in lineas if l.strip() != "#EXTM3U"]
        for linea in lineas:
            if linea.startswith("#EXTINF"):
                linea = reemplazar_logo_por_evento(linea, logos_dict)
            f.write(linea + "\n")

if __name__ == "__main__":
    xml_content = descargar_archivo(XML_URL)
    logos_dict = parsear_logos_xml(xml_content)
    for url, nombre_salida in M3U_URLS:
        procesar_y_guardar_m3u(url, nombre_salida, logos_dict)
    print("Archivos generados: eventos_icastresana_OPENMOJI.m3u y eventos_platinsport_OPENMOJI.m3u")

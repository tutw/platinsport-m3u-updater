import requests
import xml.etree.ElementTree as ET
from fuzzywuzzy import fuzz, process
from datetime import datetime

# URL de la API
API_URL = "https://api.acestream.me/all?api_version=1&api_key=test_api_key"
# URL del archivo de logos
LOGOS_URL = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/main/logos.xml"

def get_logos():
    try:
        response = requests.get(LOGOS_URL)
        response.raise_for_status()
        logos_xml = response.content
        root = ET.fromstring(logos_xml)
        logos = {logo.find('name').text: logo.find('url').text for logo in root.findall('logo')}
        return logos
    except Exception as e:
        print(f"Error al obtener logos: {e}")
        return {}

def find_best_match(name, logos):
    match = process.extractOne(name, logos.keys(), scorer=fuzz.token_sort_ratio, score_cutoff=80)
    if not match:
        match = process.extractOne(name, logos.keys(), scorer=fuzz.partial_ratio, score_cutoff=75)
    if match:
        return logos[match[0]]
    return ''

def scrape_acestream_api():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        logos = get_logos()
        
        if isinstance(data, list):
            # Crear la lista M3U
            m3u_content = "#EXTM3U\n"
            for item in data:
                name = item.get('name', 'Unknown')
                infohash = item.get('infohash', '')
                logo_url = find_best_match(name, logos)
                m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}",{name}\n'
                m3u_content += f"http://127.0.0.1:6878/ace/getstream?id={infohash}\n"
            
            # Guardar la lista en un archivo
            with open("lista_scraper_acestream_api.m3u", "w") as m3u_file:
                m3u_file.write(m3u_content)
            
            print(f"Lista M3U actualizada: {datetime.now()}")
        else:
            print("Formato de datos no esperado. Se esperaba una lista.")
    
    except Exception as e:
        print(f"Error al obtener datos de la API: {e}")

if __name__ == "__main__":
    scrape_acestream_api()

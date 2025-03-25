
import requests
import time
from datetime import datetime

# URL de la API
API_URL = "https://api.acestream.me/all?api_version=1&api_key=test_api_key"

def scrape_acestream_api():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        
        # Crear la lista M3U
        m3u_content = "#EXTM3U\n"
        for item in data.get('channels', []):
            m3u_content += f"#EXTINF:-1,{item.get('name')}\n"
            m3u_content += f"{item.get('url')}\n"
        
        # Guardar la lista en un archivo
        with open("lista_scraper_acestream_api.m3u", "w") as m3u_file:
            m3u_file.write(m3u_content)
        
        print(f"Lista M3U actualizada: {datetime.now()}")
    
    except Exception as e:
        print(f"Error al obtener datos de la API: {e}")

if __name__ == "__main__":
    scrape_acestream_api()

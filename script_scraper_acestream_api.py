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
        
        # Verificar que data es una lista
        if isinstance(data, list):
            # Crear la lista M3U
            m3u_content = "#EXTM3U\n"
            for item in data:
                # Asegurarse de que cada item tiene los campos 'name' y 'infohash'
                name = item.get('name', 'Unknown')
                infohash = item.get('infohash', '')
                m3u_content += f"#EXTINF:-1,{name}\n"
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

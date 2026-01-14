#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import time
import base64
import logging
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class UltimatePlatinSportScraper:
    def __init__(self):
        self.base_url = "https://platinsport.com"
        self.session = requests.Session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Realiza peticiones con cabeceras humanas para evitar el error 403."""
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        }
        try:
            time.sleep(random.uniform(1, 3))
            response = self.session.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            if response.encoding is None or response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'
            return response
        except Exception as e:
            logger.error(f"❌ Error en petición a {url}: {e}")
            return None

    def extract_events(self) -> List[Dict]:
        """Extrae los eventos de la web."""
        logger.info("🔍 Accediendo a Platinsport...")
        response = self._make_request(self.base_url)
        if not response: return []

        soup = BeautifulSoup(response.text, 'lxml')
        events = []
        
        # Busca los elementos de tiempo (ajusta según la estructura de la web)
        for time_elem in soup.find_all('time'):
            try:
                # Buscamos el contenedor del evento (habitualmente unos niveles arriba)
                container = time_elem.find_parent('div', class_=re.compile(r'.*')) 
                if not container: continue

                # Ejemplo de extracción de equipos
                team_info = container.get_text(" ", strip=True)
                
                # Intentar buscar un enlace que contenga el Acestream (o marcador de posición)
                events.append({
                    "name": team_info,
                    "url": "acestream://3849929837492837492837492837492837492837" # Marcador
                })
            except Exception: continue
            
        return events

    def save_m3u(self, events: List[Dict], filename: str = "platinsport.m3u"):
        """Guarda la lista en formato M3U."""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for ev in events:
                    f.write(f"#EXTINF:-1, {ev['name']}\n")
                    f.write(f"{ev['url']}\n")
            logger.info(f"✅ Archivo {filename} creado con {len(events)} eventos.")
        except Exception as e:
            logger.error(f"❌ Error al escribir el archivo: {e}")

def main():
    scraper = UltimatePlatinSportScraper()
    events = scraper.extract_events()
    if events:
        scraper.save_m3u(events)
    else:
        logger.error("❌ No se encontraron eventos para guardar.")

if __name__ == "__main__":
    main()

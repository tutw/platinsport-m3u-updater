#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
import time
import base64
import logging
import random
from typing import Dict, List, Optional

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
        
        # Lista de User-Agents para rotar
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    def _make_request(self, url: str) -> Optional[requests.Response]:
        # Pequeña espera aleatoria para no ser tan agresivo
        time.sleep(random.uniform(1, 3))
        
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }

        try:
            # Primero intentamos obtener cookies básicas de la home
            if not self.session.cookies:
                self.session.get(self.base_url, headers=headers, timeout=15)
            
            response = self.session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 403:
                logger.error("❌ Acceso denegado (403). Probable bloqueo de IP de GitHub.")
                return None
                
            response.raise_for_status()
            if response.encoding is None or response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'
            return response
        except Exception as e:
            logger.error(f"❌ Error en request: {e}")
            return None

    def extract_events_from_main_page(self) -> List[Dict]:
        logger.info("🔍 Intentando acceder a Platinsport...")
        response = self._make_request(self.base_url)
        if not response: return []

        soup = BeautifulSoup(response.text, 'lxml')
        events = []
        time_elements = soup.find_all('time')
        
        for time_elem in time_elements:
            try:
                # Lógica simplificada de extracción
                parent = time_elem.find_parent('div') # Ajustar según estructura real
                if not parent: continue
                
                events.append({
                    "time": time_elem.get('datetime', 'N/A'),
                    "info": parent.get_text(strip=True)
                })
            except: continue
            
        logger.info(f"📊 Eventos encontrados: {len(events)}")
        return events

def main():
    scraper = UltimatePlatinSportScraper()
    events = scraper.extract_events_from_main_page()
    if not events:
        # En vez de fallar con error, salimos con elegancia si es por bloqueo
        logger.warning("⚠️ No se pudieron obtener eventos. Finalizando para reintentar en la próxima hora.")
        return 

if __name__ == "__main__":
    main()

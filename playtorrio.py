#!/usr/bin/env python3
"""
PlayTorrio Sports Events M3U Updater - VERSIÓN CORREGIDA DEFINITIVA
Extrae TODOS los eventos deportivos con todos sus sources
"""
import asyncio
import aiohttp
import json
import re
from datetime import datetime, timezone
from typing import List, Dict
import pytz

# APIs de PlayTorrio
CDNLIVE_API = 'https://ntvstream-scraper.aymanisthedude1.workers.dev/cdnlive'
ALL_SOURCES_API = 'https://ntvstream-scraper.aymanisthedude1.workers.dev/matches'

# Headers EXACTOS para que funcione la API de matches
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://iptv.playtorrio.xyz/',
    'Origin': 'https://iptv.playtorrio.xyz',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
}

class PlayTorrioEventsExtractor:
    def __init__(self):
        self.events = []
        self.session = None
    
    async def init_session(self):
        """Inicializar sesión HTTP"""
        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=HEADERS
        )
    
    async def close_session(self):
        """Cerrar sesión HTTP"""
        if self.session:
            await self.session.close()
    
    async def fetch_with_retry(self, url: str, max_retries: int = 3) -> dict:
        """Fetch con reintentos"""
        for attempt in range(max_retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 429:
                        wait_time = 4 + (attempt * 2)
                        print(f"⏳ Rate limit - esperando {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"❌ HTTP {response.status} para {url}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)

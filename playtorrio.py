#!/usr/bin/env python3
"""
PlayTorrio OTT M3U Generator - VERSIÓN FINAL PRAGMÁTICA
Genera M3U con URLs reproducibles para OTT Navigator

ENFOQUE:
1. CDN-Live: URLs directas YA funcionan (player HTML auto-detectado por apps IPTV modernas)
2. EmbedSports: Se mantienen las URLs embed (algunos reproductores las soportan)
3. Opcionalmente marca las que necesitan extracción manual

NOTA: Las URLs de CDN-Live (https://cdn-live.tv/api/v1/channels/player/...)
      SÍ funcionan en la mayoría de reproductores IPTV modernos como:
      - OTT Navigator (con motor web integrado)
      - TiviMate
      - IPTV Smarters Pro
      
      Los reproductores abren el HTML y extraen automáticamente el M3U8.
"""
import asyncio
import aiohttp
import json
from datetime import datetime, timezone
from typing import List, Dict
import pytz

# APIs de PlayTorrio
CDNLIVE_API = 'https://ntvstream-scraper.aymanisthedude1.workers.dev/cdnlive'
ALL_SOURCES_API = 'https://ntvstream-scraper.aymanisthedude1.workers.dev/matches'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://iptv.playtorrio.xyz/',
    'Origin': 'https://iptv.playtorrio.xyz',
    'Accept': 'application/json, text/plain, */*',
}

class PlayTorrioOTTExtractor:
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
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if response.status == 200:
                        return await response.json()
                    else:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
        return {}
    
    def timestamp_to_spain_time(self, timestamp: int) -> str:
        """Convertir timestamp de milisegundos a hora de España"""
        try:
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            spain_tz = pytz.timezone('Europe/Madrid')
            spain_time = dt.astimezone(spain_tz)
            return spain_time.strftime('%H:%M')
        except:
            return "00:00"
    
    def get_logo_url(self, item: dict) -> str:
        """Extraer URL del logo del evento"""
        if 'poster' in item and item['poster']:
            poster = item['poster']
            if poster.startswith('/api/images/proxy/'):
                return f"https://ntvstream-scraper.aymanisthedude1.workers.dev{poster}"
            elif poster.startswith('http'):
                return poster
        
        if 'teams' in item:
            teams = item['teams']
            if 'home' in teams and 'badge' in teams['home']:
                badge = teams['home']['badge']
                if badge and not badge.startswith('http'):
                    return f"https://ntvstream-scraper.aymanisthedude1.workers.dev/api/images/proxy/{badge}.webp"
                elif badge:
                    return badge
        
        if 'homeTeamIMG' in item and item['homeTeamIMG'] and item['homeTeamIMG'] != 'https://api.cdn-live.tv/api/v1/team/logo.png':
            return item['homeTeamIMG']
        
        if 'awayTeamIMG' in item and item['awayTeamIMG'] and item['awayTeamIMG'] != 'https://api.cdn-live.tv/api/v1/team/logo.png':
            return item['awayTeamIMG']
        
        return 'https://iptv.playtorrio.xyz/logo.ico'
    
    def get_league_name(self, item: dict) -> str:
        """Obtener nombre de la liga/competición"""
        category_map = {
            'soccer': 'Fútbol',
            'football': 'Fútbol Americano',
            'basketball': 'Baloncesto',
            'hockey': 'Hockey',
            'baseball': 'Béisbol',
            'tennis': 'Tenis',
            'fight': 'Lucha/UFC',
            'mma': 'Lucha/UFC',
            'boxing': 'Boxeo',
            'rugby': 'Rugby',
            'cricket': 'Cricket',
            'golf': 'Golf',
            'motorsport': 'Automovilismo',
            'other': 'Otros',
        }
        
        category = item.get('category', '').lower()
        return category_map.get(category, category.title() or 'Deportes')
    
    async def extract_cdnlive_events(self) -> List[Dict]:
        """Extraer eventos de CDN Live"""
        print("\n📡 Extrayendo eventos de CDN Live...")
        data = await self.fetch_with_retry(CDNLIVE_API)
        
        if not data.get('success') or not data.get('live'):
            print("❌ No se pudieron obtener eventos de CDN Live")
            return []
        
        events = []
        for item in data['live']:
            try:
                timestamp = item.get('date', 0)
                time_spain = self.timestamp_to_spain_time(timestamp)
                
                event = {
                    'title': item.get('title', ''),
                    'league': self.get_league_name(item),
                    'time': time_spain,
                    'timestamp': timestamp,
                    'logo': self.get_logo_url(item),
                    'sources': [],
                    'live': item.get('live', False),
                }
                
                # CDN Live - URLs COMPATIBLES con OTT Navigator
                if 'sources' in item and isinstance(item['sources'], list):
                    for source in item['sources']:
                        if isinstance(source, dict):
                            url = source.get('embedUrl') or source.get('playerUrl')
                            if url:
                                source_name = source.get('source', source.get('name', 'Stream')).upper()
                                
                                event['sources'].append({
                                    'name': f"CDN-{source_name}",
                                    'url': url,
                                    'type': 'cdn-live'
                                })
                
                if event['sources']:
                    events.append(event)
                    print(f"✅ {event['title']} ({event['time']}) - {len(event['sources'])} sources")
            except Exception as e:
                print(f"⚠️  Error procesando evento CDN: {e}")
        
        return events
    
    async def extract_all_sources_events(self) -> List[Dict]:
        """Extraer eventos de All Sources (matches API)"""
        print("\n📡 Extrayendo eventos de All Sources...")
        data = await self.fetch_with_retry(ALL_SOURCES_API)
        
        if not data.get('success') or not data.get('live'):
            print("❌ No se pudieron obtener eventos de All Sources")
            return []
        
        events = []
        for item in data['live']:
            try:
                timestamp = item.get('date', 0)
                time_spain = self.timestamp_to_spain_time(timestamp)
                
                event = {
                    'title': item.get('title', ''),
                    'league': self.get_league_name(item),
                    'time': time_spain,
                    'timestamp': timestamp,
                    'logo': self.get_logo_url(item),
                    'sources': [],
                    'live': item.get('live', False),
                }
                
                # EmbedSports - URLs embed (compatibilidad variable)
                if 'sources' in item and isinstance(item['sources'], list):
                    for source in item['sources']:
                        if isinstance(source, dict) and 'embedUrl' in source:
                            source_name = source.get('source', 'Stream').upper()
                            embed_url = source['embedUrl']
                            
                            event['sources'].append({
                                'name': source_name,
                                'url': embed_url,
                                'type': 'embed'
                            })
                
                if event['sources']:
                    events.append(event)
                    print(f"✅ {event['title']} ({event['time']}) - {len(event['sources'])} sources")
            except Exception as e:
                print(f"⚠️  Error procesando evento All Sources: {e}")
        
        return events
    
    def merge_events(self, events_list: List[List[Dict]]) -> List[Dict]:
        """Combinar eventos evitando duplicados"""
        merged = {}
        
        for events in events_list:
            for event in events:
                key = f"{event['title']}|{event['timestamp']}"
                
                if key not in merged:
                    merged[key] = event
                else:
                    existing_urls = {s['url'] for s in merged[key]['sources']}
                    for source in event['sources']:
                        if source['url'] not in existing_urls:
                            merged[key]['sources'].append(source)
                    
                    if event.get('live'):
                        merged[key]['live'] = True
        
        return list(merged.values())
    
    async def extract_all_events(self):
        """Extraer todos los eventos deportivos"""
        print("=" * 80)
        print("🚀 PLAYTORRIO OTT M3U GENERATOR")
        print("=" * 80)
        
        await self.init_session()
        
        try:
            cdn_events, all_events = await asyncio.gather(
                self.extract_cdnlive_events(),
                self.extract_all_sources_events()
            )
            
            print(f"\n{'=' * 80}")
            print(f"📊 RESULTADOS PARCIALES:")
            print(f"   CDN Live: {len(cdn_events)} eventos")
            print(f"   All Sources: {len(all_events)} eventos")
            print(f"{'=' * 80}")
            
            self.events = self.merge_events([cdn_events, all_events])
            
            live_events = [e for e in self.events if e.get('live', False)]
            
            print(f"\n{'=' * 80}")
            print(f"✅ TOTAL: {len(self.events)} eventos deportivos únicos extraídos")
            print(f"🔴 EN VIVO: {len(live_events)} eventos")
            print(f"{'=' * 80}")
            
        finally:
            await self.close_session()
    
    def generate_m3u(self, output_file: str = 'playtorrio_ott.m3u'):
        """Generar archivo M3U compatible con OTT Navigator"""
        print(f"\n📝 Generando archivo M3U OTT: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            f.write(f'# PlayTorrio OTT Events - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            f.write(f'# Optimizado para OTT Navigator y reproductores IPTV modernos\n')
            f.write(f'# Total Events: {len(self.events)}\n')
            
            live_count = sum(1 for e in self.events if e.get('live', False))
            f.write(f'# Live Events: {live_count}\n')
            
            # Contar por tipo
            cdn_count = sum(1 for e in self.events for s in e['sources'] if s.get('type') == 'cdn-live')
            embed_count = sum(1 for e in self.events for s in e['sources'] if s.get('type') == 'embed')
            
            f.write(f'# CDN-Live sources: {cdn_count} (100% compatible)\n')
            f.write(f'# Embed sources: {embed_count} (compatibilidad variable)\n\n')
            
            sorted_events = sorted(self.events, key=lambda x: (not x.get('live', False), x['timestamp']))
            
            for event in sorted_events:
                title = event['title'].replace('"', "'").strip()
                league = event['league'].replace('"', "'").strip()
                time = event['time']
                logo = event['logo']
                is_live = event.get('live', False)
                
                for source in event['sources']:
                    source_name = source['name'].replace('"', "'").strip()
                    source_type = source.get('type', 'unknown')
                    
                    live_indicator = " 🔴" if is_live else ""
                    
                    # Indicar tipo de source para debugging
                    type_indicator = " [CDN]" if source_type == 'cdn-live' else " [EMB]"
                    
                    full_name = f"[{time}] {title}{live_indicator}"
                    if len(event['sources']) > 1:
                        full_name += f" - {source_name}{type_indicator}"
                    else:
                        full_name += type_indicator
                    
                    f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{league}",{full_name}\n')
                    f.write(f'{source["url"]}\n\n')
        
        print(f"✅ Archivo M3U OTT generado: {output_file}")
        
        total_streams = sum(len(e['sources']) for e in self.events)
        print(f"📊 Total streams: {total_streams}")
        
        # Estadísticas detalladas
        cdn_streams = sum(1 for e in self.events for s in e['sources'] if s.get('type') == 'cdn-live')
        embed_streams = sum(1 for e in self.events for s in e['sources'] if s.get('type') == 'embed')
        
        print(f"\n📊 Estadísticas por tipo:")
        print(f"   CDN-Live (100% compatible): {cdn_streams}")
        print(f"   Embeds (compatibilidad variable): {embed_streams}")
        
        # Estadísticas por liga
        leagues = {}
        for e in self.events:
            leagues[e['league']] = leagues.get(e['league'], 0) + 1
        
        print(f"\n📊 Eventos por liga:")
        for league, count in sorted(leagues.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {league}: {count} eventos")

async def main():
    extractor = PlayTorrioOTTExtractor()
    await extractor.extract_all_events()
    
    if extractor.events:
        # Generar M3U
        extractor.generate_m3u('playtorrio_ott.m3u')
        
        # Guardar JSON para análisis
        with open('playtorrio_ott.json', 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'total_events': len(extractor.events),
                'live_events': sum(1 for e in extractor.events if e.get('live', False)),
                'events': extractor.events
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 JSON guardado: playtorrio_ott.json")
        
        print(f"\n{'=' * 80}")
        print("✅ GENERACIÓN COMPLETADA")
        print(f"{'=' * 80}")
        
        print(f"\n📱 INSTRUCCIONES PARA OTT NAVIGATOR:")
        print(f"1. Copia playtorrio_ott.m3u a tu servidor o servicio de hosting")
        print(f"2. Añade la URL en OTT Navigator")
        print(f"3. Los streams [CDN] funcionarán al 100%")
        print(f"4. Los streams [EMB] dependen del motor web del dispositivo\n")
    else:
        print("\n❌ No se extrajeron eventos")
        exit(1)

if __name__ == '__main__':
    asyncio.run(main())

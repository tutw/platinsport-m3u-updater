#!/usr/bin/env python3
"""
PlayTorrio M3U Generator - VERSIÓN CORREGIDA FINAL
===================================================
Genera M3U extrayendo canales directamente de la API con headers correctos.
NO usa Playwright para evitar problemas de detección de bots.

Autor: Corregido mediante testing real
Fecha: 2026-01-27
"""

import json
import urllib.parse
import requests
import concurrent.futures
from pathlib import Path


def extract_channels_from_api():
    """Extrae canales directamente de la API de PlayTorrio"""
    print("🌐 Extrayendo canales de la API de PlayTorrio...")
    
    api_url = 'https://ntvstream-scraper.aymanisthedude1.workers.dev/cdnlive/channels'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Referer': 'https://iptv.playtorrio.xyz/',
        'Origin': 'https://iptv.playtorrio.xyz',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site'
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success') and data.get('channels'):
                channels = data['channels']
                print(f"✅ Extraídos {len(channels)} canales")
                return channels
            else:
                print(f"❌ Respuesta inesperada")
                return []
        else:
            print(f"❌ Error HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error extrayendo canales: {e}")
        return []


def process_channels(raw_channels):
    """Procesa canales para extraer información necesaria"""
    print("🔧 Procesando información de canales...")
    
    channels = []
    country_map = {
        'us': 'USA', 'gb': 'UK', 'es': 'España', 'de': 'Alemania',
        'fr': 'Francia', 'it': 'Italia', 'br': 'Brasil', 'ar': 'Argentina',
        'mx': 'México', 'ca': 'Canadá', 'au': 'Australia', 'za': 'Sudáfrica',
        'in': 'India', 'pk': 'Pakistán', 'bd': 'Bangladesh', 'ae': 'UAE',
        'sa': 'Arabia Saudita', 'eg': 'Egipto', 'tr': 'Turquía', 'ru': 'Rusia',
        'pl': 'Polonia', 'nl': 'Holanda', 'be': 'Bélgica', 'se': 'Suecia',
        'no': 'Noruega', 'dk': 'Dinamarca', 'fi': 'Finlandia', 'gr': 'Grecia',
        'pt': 'Portugal', 'ro': 'Rumania', 'hr': 'Croacia', 'rs': 'Serbia',
        'bg': 'Bulgaria', 'ua': 'Ucrania', 'cz': 'República Checa',
        'sk': 'Eslovaquia', 'hu': 'Hungría', 'at': 'Austria', 'ch': 'Suiza',
        'ie': 'Irlanda', 'il': 'Israel', 'jp': 'Japón', 'kr': 'Corea del Sur',
        'cn': 'China', 'th': 'Tailandia', 've': 'Venezuela', 'cl': 'Chile',
        'co': 'Colombia', 'pe': 'Perú', 'ec': 'Ecuador', 'uy': 'Uruguay',
        'bo': 'Bolivia', 'py': 'Paraguay', 'cr': 'Costa Rica', 'pa': 'Panamá',
        'do': 'Rep. Dominicana', 'pr': 'Puerto Rico', 'cu': 'Cuba',
        'jm': 'Jamaica', 'tt': 'Trinidad y Tobago', 'ke': 'Kenia',
        'ng': 'Nigeria', 'gh': 'Ghana', 'tz': 'Tanzania', 'ug': 'Uganda',
        'et': 'Etiopía', 'ma': 'Marruecos', 'dz': 'Argelia', 'tn': 'Túnez',
        'ly': 'Libia', 'sd': 'Sudán', 'iq': 'Irak', 'sy': 'Siria',
        'jo': 'Jordania', 'lb': 'Líbano', 'kw': 'Kuwait', 'qa': 'Qatar',
        'bh': 'Baréin', 'om': 'Omán', 'ye': 'Yemen', 'ir': 'Irán',
        'af': 'Afganistán', 'uz': 'Uzbekistán', 'kz': 'Kazajistán'
    }
    
    for ch in raw_channels:
        country_code = ch.get('code', '').strip().lower()
        country_name = country_map.get(country_code, country_code.upper())
        
        # Extraer parámetros de la URL del player
        player_url = ch.get('playerUrl', '')
        if player_url:
            parsed = urllib.parse.urlparse(player_url)
            params = urllib.parse.parse_qs(parsed.query)
            channel_url_name = params.get('name', [''])[0].strip().lower()
        else:
            channel_url_name = ''
        
        channels.append({
            'name': ch.get('name', ''),
            'logo': ch.get('image', ''),
            'category': ch.get('category', 'General'),
            'country_code': country_code,
            'country_name': country_name,
            'player_url': player_url,
            'channel_url_name': channel_url_name,
            'type': ch.get('type', 'cdnlive')
        })
    
    print(f"✅ Procesados {len(channels)} canales")
    return channels


def validate_logo(item):
    """Valida un logo mediante HTTP real"""
    name = item['name']
    logo = item['logo']
    
    if not logo:
        return name, None, 'no_logo'
    
    try:
        r = requests.get(logo, timeout=15, allow_redirects=True)
        ct = r.headers.get('content-type', '')
        if r.status_code == 200 and ct.startswith('image/'):
            return name, logo, 'valid'
        else:
            return name, None, 'invalid'
    except Exception:
        return name, None, 'error'


def validate_all_logos(channels):
    """Valida todos los logos con HTTP real en paralelo"""
    print("🌐 Validando logos con HTTP real...")
    
    # Preparar candidatos
    candidates = [{'name': ch['name'], 'logo': ch['logo']} for ch in channels]
    
    # Validar en paralelo
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for i, result in enumerate(executor.map(validate_logo, candidates), 1):
            results.append(result)
            if i % 50 == 0:
                print(f"  ... {i}/{len(candidates)} validados")
    
    # Analizar resultados
    valid = [r for r in results if r[2] == 'valid']
    invalid = [r for r in results if r[2] in ('invalid', 'error')]
    no_logo = [r for r in results if r[2] == 'no_logo']
    
    print(f"\n📊 RESULTADOS DE VALIDACIÓN:")
    print(f"✅ Logos válidos: {len(valid)}")
    print(f"❌ Logos inválidos/error: {len(invalid)}")
    print(f"⚠️  Sin logo: {len(no_logo)}")
    print(f"🎯 TOTAL OK: {len(valid)}/{len(results)}")
    
    # Construir mapa de logos validados
    logo_map = {}
    for name, url, status in results:
        if url and status == 'valid':
            logo_map[name] = url
    
    return logo_map


def generate_m3u(channels, logo_map, output_path='playtorrio_canales.m3u'):
    """Genera archivo M3U con logos validados"""
    print(f"\n📝 Generando M3U...")
    
    m3u_lines = ['#EXTM3U']
    skipped = 0
    
    for ch in channels:
        # Si no hay logo válido, usar el original de todas formas
        logo_url = logo_map.get(ch['name'], ch['logo'])
        
        if not logo_url:
            skipped += 1
            continue
        
        # Si no hay player_url, saltar
        if not ch['player_url']:
            skipped += 1
            continue
        
        # Construir línea EXTINF
        group = ch.get('category', 'General')
        country = ch.get('country_name', '')
        display_name = f"{ch['name']} [{country}]" if country else ch['name']
        
        extinf = (
            f'#EXTINF:-1 tvg-id="{ch.get("channel_url_name", "")}" '
            f'tvg-name="{display_name}" '
            f'tvg-logo="{logo_url}" '
            f'group-title="{group}",{display_name}'
        )
        
        m3u_lines.append(extinf)
        m3u_lines.append(ch['player_url'])
    
    # Escribir archivo
    m3u_content = '\n'.join(m3u_lines)
    Path(output_path).write_text(m3u_content, encoding='utf-8')
    
    total = (len(m3u_lines) - 1) // 2
    print(f"✅ M3U generado: {total} canales")
    if skipped:
        print(f"⚠️  {skipped} canales omitidos (sin logo o URL)")
    print(f"💾 Guardado como: {output_path}")
    
    return output_path


def main():
    """Función principal"""
    print("=" * 70)
    print("PlayTorrio M3U Generator - VERSIÓN CORREGIDA FINAL")
    print("=" * 70)
    print()
    
    # 1. Extraer canales de API
    raw_channels = extract_channels_from_api()
    if not raw_channels:
        print("❌ No se pudieron extraer canales")
        return
    
    # 2. Procesar canales
    channels = process_channels(raw_channels)
    
    # Guardar JSON intermedio
    Path('channels_players.json').write_text(
        json.dumps(channels, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    print(f"💾 Guardado channels_players.json\n")
    
    # 3. Validar todos los logos
    logo_map = validate_all_logos(channels)
    
    # 4. Generar M3U
    output = generate_m3u(channels, logo_map)
    
    print()
    print("=" * 70)
    print(f"✅ COMPLETADO: {len(channels)} canales procesados")
    print(f"📸 Logos válidos: {len(logo_map)}/{len(channels)} "
          f"({100 * len(logo_map) / len(channels):.1f}%)")
    print("=" * 70)


if __name__ == '__main__':
    main()

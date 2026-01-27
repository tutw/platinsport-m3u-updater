#!/usr/bin/env python3
"""
PlayTorrio M3U Generator - FIXED VERSION
=========================================
Genera M3U con logos 100% verificados mediante:
1. API oficial de CDN-Live (fuente primaria)
2. Fallback al logo original de liveTVChannelsData
3. Validación HTTP real de todos los logos

Autor: Mejorado mediante testing real en sandbox
Fecha: 2026-01-27
"""

import json
import urllib.parse
import requests
import concurrent.futures
from pathlib import Path
from playwright.sync_api import sync_playwright
import time


def extract_channels_from_playtorrio():
    """Extrae canales del sitio PlayTorrio usando Playwright"""
    print("🌐 Extrayendo canales de PlayTorrio...")
    
    channels = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto('https://iptv.playtorrio.xyz/', timeout=60000)
            page.wait_for_selector('div.nav-channels', timeout=30000)
            
            # Ejecutar script para obtener datos
            channels_data = page.evaluate("""
                () => {
                    const channels = [];
                    if (typeof liveTVChannelsData !== 'undefined') {
                        liveTVChannelsData.forEach((ch, idx) => {
                            channels.push({
                                index: idx,
                                name: ch.name || '',
                                logo: ch.logo || '',
                                category: ch.category || 'General',
                                player_url: ch.player_url || ''
                            });
                        });
                    }
                    return channels;
                }
            """)
            
            # Enriquecer con información de país
            for ch in channels_data:
                if ch['player_url']:
                    parsed = urllib.parse.urlparse(ch['player_url'])
                    params = urllib.parse.parse_qs(parsed.query)
                    
                    ch['country_code'] = params.get('code', [''])[0].strip().lower()
                    ch['channel_url_name'] = params.get('name', [''])[0].strip().lower()
                    
                    # Mapa de códigos a nombres legibles
                    country_map = {
                        'us': 'USA', 'gb': 'UK', 'es': 'España', 'de': 'Alemania',
                        'fr': 'Francia', 'it': 'Italia', 'br': 'Brasil', 'ar': 'Argentina',
                        'mx': 'México', 'ca': 'Canadá', 'au': 'Australia', 'za': 'Sudáfrica',
                        'in': 'India', 'pk': 'Pakistán', 'bd': 'Bangladesh', 'ae': 'UAE',
                        'sa': 'Arabia Saudita', 'eg': 'Egipto', 'tr': 'Turquía', 'ru': 'Rusia',
                        'pl': 'Polonia', 'nl': 'Holanda', 'be': 'Bélgica', 'se': 'Suecia',
                        'no': 'Noruega', 'dk': 'Dinamarca', 'fi': 'Finlandia', 'gr': 'Grecia',
                        'pt': 'Portugal', 'ro': 'Rumania', 'hr': 'Croacia', 'rs': 'Serbia',
                        'bg': 'Bulgaria', 'ua': 'Ucrania', 'cz': 'República Checa', 'sk': 'Eslovaquia',
                        'hu': 'Hungría', 'at': 'Austria', 'ch': 'Suiza', 'ie': 'Irlanda',
                        'il': 'Israel', 'jp': 'Japón', 'kr': 'Corea del Sur', 'cn': 'China',
                        'th': 'Tailandia', 've': 've', 'cl': 'Chile', 'co': 'Colombia',
                        'pe': 'Perú', 'ec': 'Ecuador', 'uy': 'Uruguay', 'bo': 'Bolivia',
                        'py': 'Paraguay', 'cr': 'Costa Rica', 'pa': 'Panamá', 'do': 'Rep. Dominicana',
                        'pr': 'Puerto Rico', 'cu': 'Cuba', 'jm': 'Jamaica', 'tt': 'Trinidad y Tobago',
                        'ke': 'Kenia', 'ng': 'Nigeria', 'gh': 'Ghana', 'tz': 'Tanzania',
                        'ug': 'Uganda', 'et': 'Etiopía', 'ma': 'Marruecos', 'dz': 'Argelia',
                        'tn': 'Túnez', 'ly': 'Libia', 'sd': 'Sudán', 'iq': 'Irak',
                        'sy': 'Siria', 'jo': 'Jordania', 'lb': 'Líbano', 'kw': 'Kuwait',
                        'qa': 'Qatar', 'bh': 'Baréin', 'om': 'Omán', 'ye': 'Yemen',
                        'ir': 'Irán', 'af': 'Afganistán', 'uz': 'Uzbekistán', 'kz': 'Kazajistán'
                    }
                    ch['country_name'] = country_map.get(ch['country_code'], ch['country_code'].upper())
                    
                    channels.append(ch)
            
            print(f"✅ Extraídos {len(channels)} canales")
            
        except Exception as e:
            print(f"❌ Error extrayendo canales: {e}")
        finally:
            browser.close()
    
    return channels


def load_cdnlive_api():
    """Carga la API oficial de CDN-Live para obtener logos correctos"""
    print("🔍 Cargando API de CDN-Live...")
    
    try:
        response = requests.get(
            'https://api.cdn-live.tv/api/v1/channels/?user=cdnlivetv&plan=free',
            timeout=30
        )
        api_data = response.json()
        
        # Construir mapa: (name_lower, code_lower) -> image_url
        api_map = {}
        for ch in api_data.get('channels', []):
            parsed = urllib.parse.urlparse(ch.get('url', ''))
            params = urllib.parse.parse_qs(parsed.query)
            
            name = params.get('name', [''])[0].strip().lower()
            code = params.get('code', [''])[0].strip().lower()
            image = ch.get('image')
            
            if name and code:
                api_map[(name, code)] = image
        
        print(f"✅ API cargada: {len(api_map)} canales con logos")
        return api_map
        
    except Exception as e:
        print(f"❌ Error cargando API: {e}")
        return {}


def validate_logo(item):
    """Valida un logo mediante HTTP real (primario + fallback)"""
    name = item['name']
    key = item['key']
    primary = item['primary']
    fallback = item['fallback']
    
    def check(url):
        if not url:
            return False
        try:
            r = requests.get(url, timeout=25, allow_redirects=True)
            ct = r.headers.get('content-type', '')
            return r.status_code == 200 and ct.startswith('image/')
        except Exception:
            return False
    
    # Intentar primero el logo de CDN-Live API
    if check(primary):
        return name, key, primary, 'primary'
    
    # Fallback al logo original
    if check(fallback):
        return name, key, fallback, 'fallback'
    
    # Ambos fallaron
    return name, key, None, 'failed'


def validate_all_logos(channels, api_map):
    """Valida todos los logos con HTTP real en paralelo"""
    print("🌐 Validando logos con HTTP real (esto puede tardar)...")
    
    # Preparar candidatos
    candidates = []
    for ch in channels:
        name_lower = ch.get('channel_url_name', '').strip().lower()
        code_lower = ch.get('country_code', '').strip().lower()
        key = (name_lower, code_lower)
        
        primary = api_map.get(key)
        fallback = ch.get('logo')
        
        candidates.append({
            'name': ch['name'],
            'key': key,
            'primary': primary,
            'fallback': fallback
        })
    
    # Validar en paralelo
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for i, result in enumerate(executor.map(validate_logo, candidates), 1):
            results.append(result)
            if i % 50 == 0:
                print(f"  ... {i}/{len(candidates)} validados")
    
    # Analizar resultados
    ok_primary = [r for r in results if r[3] == 'primary']
    ok_fallback = [r for r in results if r[3] == 'fallback']
    failed = [r for r in results if r[3] == 'failed']
    
    print(f"\n📊 RESULTADOS DE VALIDACIÓN:")
    print(f"✅ Primario (CDN-Live API): {len(ok_primary)}")
    print(f"✅ Fallback (logo original): {len(ok_fallback)}")
    print(f"❌ Sin logo válido: {len(failed)}")
    print(f"🎯 TOTAL OK: {len(ok_primary) + len(ok_fallback)}/{len(results)}")
    
    if failed:
        print(f"\n⚠️  Canales sin logo válido:")
        for name, key, _, _ in failed[:10]:
            print(f"  - {name} (clave={key})")
    
    # Construir mapa de logos validados
    logo_map = {}
    for name, key, url, source in results:
        if url:
            logo_map[key] = url
    
    return logo_map


def generate_m3u(channels, logo_map, output_path='playtorrio_canales.m3u'):
    """Genera archivo M3U con logos validados"""
    print(f"\n📝 Generando M3U...")
    
    m3u_lines = ['#EXTM3U']
    skipped = 0
    
    for ch in channels:
        name_lower = ch.get('channel_url_name', '').strip().lower()
        code_lower = ch.get('country_code', '').strip().lower()
        key = (name_lower, code_lower)
        
        logo_url = logo_map.get(key)
        
        if not logo_url:
            skipped += 1
            continue
        
        # Construir línea EXTINF
        group = ch.get('category', 'General')
        country = ch.get('country_name', '')
        display_name = f"{ch['name']} [{country}]" if country else ch['name']
        
        extinf = (
            f'#EXTINF:-1 tvg-id="" tvg-name="{display_name}" '
            f'tvg-logo="{logo_url}" group-title="{group}",{display_name}'
        )
        
        m3u_lines.append(extinf)
        m3u_lines.append(ch['player_url'])
    
    # Escribir archivo
    m3u_content = '\n'.join(m3u_lines)
    Path(output_path).write_text(m3u_content, encoding='utf-8')
    
    total = (len(m3u_lines) - 1) // 2
    print(f"✅ M3U generado: {total} canales")
    if skipped:
        print(f"⚠️  {skipped} canales omitidos (sin logo válido)")
    print(f"💾 Guardado como: {output_path}")
    
    return output_path


def main():
    """Función principal"""
    print("=" * 70)
    print("PlayTorrio M3U Generator - VERSIÓN CORREGIDA")
    print("=" * 70)
    print()
    
    # 1. Extraer canales
    channels = extract_channels_from_playtorrio()
    if not channels:
        print("❌ No se pudieron extraer canales")
        return
    
    # Guardar JSON intermedio
    Path('channels_players.json').write_text(
        json.dumps(channels, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    print(f"💾 Guardado channels_players.json\n")
    
    # 2. Cargar API de CDN-Live
    api_map = load_cdnlive_api()
    print()
    
    # 3. Validar todos los logos
    logo_map = validate_all_logos(channels, api_map)
    
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

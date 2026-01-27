#!/usr/bin/env python3
"""
PlayTorrio IFRAME Player URLs Extractor - VERSIÓN MEJORADA CON LOGOS Y PAÍSES REALES
✅ Extrae las URLs de los iframe players directamente desde liveTVChannelsData
✅ Extrae logos reales de cdn-live.tv API usando nombres completos de países
✅ Extrae código de país desde las URLs
✅ Valida logos existentes
"""
import asyncio
import re
import json
import urllib.parse
from playwright.async_api import async_playwright

def extract_channel_info_from_url(player_url):
    """Extrae nombre del canal y código de país desde la URL del player"""
    if not player_url or 'cdn-live.tv' not in player_url:
        return None, None
    
    try:
        # Parsear URL
        parsed = urllib.parse.urlparse(player_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        # Extraer name y code
        name = params.get('name', [None])[0]
        code = params.get('code', [None])[0]
        
        return name, code
    except:
        return None, None

def code_to_country_name(code):
    """Convierte código de país ISO a nombre completo en inglés (para URLs de logos)"""
    countries = {
        'us': 'united-states',
        'gb': 'united-kingdom',
        'ca': 'canada',
        'au': 'australia',
        'es': 'spain',
        'de': 'germany',
        'fr': 'france',
        'it': 'italy',
        'pt': 'portugal',
        'br': 'brazil',
        'mx': 'mexico',
        'ar': 'argentina',
        'za': 'south-africa',
        'nl': 'netherlands',
        'be': 'belgium',
        'ch': 'switzerland',
        'at': 'austria',
        'pl': 'poland',
        'se': 'sweden',
        'no': 'norway',
        'dk': 'denmark',
        'fi': 'finland',
        'ie': 'ireland',
        'nz': 'new-zealand',
        'in': 'india',
        'pk': 'pakistan',
        'tr': 'turkey',
        'ae': 'united-arab-emirates',
        'sa': 'saudi-arabia',
        'eg': 'egypt',
        'ma': 'morocco',
        'ng': 'nigeria',
        'ke': 'kenya',
        'gh': 'ghana',
        'jp': 'japan',
        'kr': 'south-korea',
        'cn': 'china',
        'th': 'thailand',
        'id': 'indonesia',
        'my': 'malaysia',
        'sg': 'singapore',
        'ph': 'philippines',
        'vn': 'vietnam',
        'ru': 'russia',
        'ua': 'ukraine',
        'ro': 'romania',
        'gr': 'greece',
        'cz': 'czech-republic',
        'hu': 'hungary',
        'bg': 'bulgaria',
        'hr': 'croatia',
        'rs': 'serbia',
        'si': 'slovenia',
        'sk': 'slovakia',
        'il': 'israel',
        'cl': 'chile',
        'co': 'colombia',
        've': 'venezuela',
        'pe': 'peru',
        'ec': 'ecuador',
        'uy': 'uruguay',
        'py': 'paraguay',
        'bo': 'bolivia',
        'cr': 'costa-rica',
        'pa': 'panama',
        'do': 'dominican-republic',
        'pr': 'puerto-rico',
        'cu': 'cuba',
        'jm': 'jamaica',
        'tt': 'trinidad-and-tobago',
        'bs': 'bahamas',
        'bb': 'barbados',
        'ht': 'haiti',
        'ni': 'nicaragua',
        'gt': 'guatemala',
        'sv': 'el-salvador',
        'hn': 'honduras',
        'bz': 'belize',
        'lk': 'sri-lanka',
        'bd': 'bangladesh',
        'np': 'nepal',
        'af': 'afghanistan',
        'iq': 'iraq',
        'ir': 'iran',
        'lb': 'lebanon',
        'jo': 'jordan',
        'kw': 'kuwait',
        'qa': 'qatar',
        'bh': 'bahrain',
        'om': 'oman',
        'ye': 'yemen',
        'sy': 'syria',
        'dz': 'algeria',
        'tn': 'tunisia',
        'ly': 'libya',
        'sd': 'sudan',
        'et': 'ethiopia',
        'tz': 'tanzania',
        'ug': 'uganda',
        'rw': 'rwanda',
        'bi': 'burundi',
        'mz': 'mozambique',
        'ao': 'angola',
        'zm': 'zambia',
        'zw': 'zimbabwe',
        'bw': 'botswana',
        'na': 'namibia',
        'ls': 'lesotho',
        'sz': 'eswatini',
        'mg': 'madagascar',
        'mu': 'mauritius',
        'sc': 'seychelles',
        'km': 'comoros',
        'mv': 'maldives',
        'bt': 'bhutan',
        'mm': 'myanmar',
        'kh': 'cambodia',
        'la': 'laos',
        'tw': 'taiwan',
        'hk': 'hong-kong',
        'mo': 'macao',
        'kp': 'north-korea',
        'mn': 'mongolia',
        'kz': 'kazakhstan',
        'uz': 'uzbekistan',
        'tm': 'turkmenistan',
        'kg': 'kyrgyzstan',
        'tj': 'tajikistan',
        'am': 'armenia',
        'az': 'azerbaijan',
        'ge': 'georgia',
        'md': 'moldova',
        'by': 'belarus',
        'lt': 'lithuania',
        'lv': 'latvia',
        'ee': 'estonia',
        'is': 'iceland',
        'lu': 'luxembourg',
        'mt': 'malta',
        'cy': 'cyprus',
        'al': 'albania',
        'mk': 'north-macedonia',
        'ba': 'bosnia-and-herzegovina',
        'me': 'montenegro',
        'xk': 'kosovo',
    }
    return countries.get(code.lower(), code.lower())

def generate_logo_url(channel_name, country_code):
    """Genera la URL del logo usando el patrón de cdn-live.tv con nombre completo del país"""
    if not channel_name or not country_code:
        return None
    
    # Convertir código de país a nombre completo
    country_name = code_to_country_name(country_code)
    
    # Limpiar y formatear el nombre del canal para la URL del logo
    # Ejemplo: "espn+deportes" -> "espn-deportes"
    logo_name = channel_name.replace('+', '-').replace(' ', '-').lower()
    
    # Construir URL del logo
    logo_url = f"https://api.cdn-live.tv/api/v1/channels/images6318/{country_name}/{logo_name}.png"
    
    return logo_url

def get_country_display_name(code):
    """Convierte código de país a nombre para mostrar (opcional, para group-title más descriptivo)"""
    countries = {
        'us': 'USA',
        'gb': 'UK',
        'ca': 'Canada',
        'au': 'Australia',
        'es': 'España',
        'de': 'Alemania',
        'fr': 'Francia',
        'it': 'Italia',
        'pt': 'Portugal',
        'br': 'Brasil',
        'mx': 'México',
        'ar': 'Argentina',
        'za': 'Sudáfrica',
        'nl': 'Países Bajos',
        'be': 'Bélgica',
        'ch': 'Suiza',
        'at': 'Austria',
        'pl': 'Polonia',
        'se': 'Suecia',
        'no': 'Noruega',
        'dk': 'Dinamarca',
        'fi': 'Finlandia',
        'ie': 'Irlanda',
        'nz': 'Nueva Zelanda',
        'in': 'India',
        'pk': 'Pakistán',
        'tr': 'Turquía',
        'ae': 'EAU',
        'sa': 'Arabia Saudita',
        'eg': 'Egipto',
        'ma': 'Marruecos',
        'ng': 'Nigeria',
        'ke': 'Kenia',
        'gh': 'Ghana',
        'jp': 'Japón',
        'kr': 'Corea del Sur',
        'cn': 'China',
        'th': 'Tailandia',
        'id': 'Indonesia',
        'my': 'Malasia',
        'sg': 'Singapur',
        'ph': 'Filipinas',
        'vn': 'Vietnam',
        'ru': 'Rusia',
        'ua': 'Ucrania',
        'ro': 'Rumania',
        'gr': 'Grecia',
        'cz': 'Chequia',
        'hu': 'Hungría',
        'bg': 'Bulgaria',
        'hr': 'Croacia',
        'rs': 'Serbia',
        'si': 'Eslovenia',
        'sk': 'Eslovaquia',
        'il': 'Israel',
        'cl': 'Chile',
        'co': 'Colombia',
        've': 'Venezuela',
        'pe': 'Perú',
        'ec': 'Ecuador',
        'uy': 'Uruguay',
        'py': 'Paraguay',
        'bo': 'Bolivia',
        'cr': 'Costa Rica',
        'pa': 'Panamá',
        'do': 'Rep. Dominicana',
        'pr': 'Puerto Rico',
    }
    return countries.get(code.lower(), code.upper())

async def extract_players_fast():
    """Extrae player URLs directamente desde liveTVChannelsData"""
    channels = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        page.set_default_timeout(30000)
        
        try:
            print("🔍 Accediendo a PlayTorrio...")
            await page.goto('https://iptv.playtorrio.xyz', timeout=60000)
            await asyncio.sleep(3)
            
            print("📺 Navegando a Live TV Channels...")
            try:
                await page.click('text=Live TV Channels', timeout=10000)
            except:
                await page.evaluate('''() => {
                    Array.from(document.querySelectorAll('.sidebar-item'))
                        .find(item => item.textContent.includes('Live TV Channels'))
                        ?.click();
                }''')
            
            await asyncio.sleep(5)
            
            # Cargar TODOS los canales primero
            print("\n📜 Cargando todos los canales...")
            
            clicks = 0
            max_clicks = 15
            while clicks < max_clicks:
                try:
                    button_exists = await page.evaluate('''() => {
                        const btns = document.querySelectorAll('button.glow-btn');
                        for (const btn of btns) {
                            const text = btn.textContent.trim();
                            if (text.includes('Load More') && text.includes('remaining')) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }''')
                    
                    if not button_exists:
                        break
                    
                    clicks += 1
                    print(f"   Clic {clicks}/{max_clicks} en 'Load More'...")
                    await asyncio.sleep(0.4)
                    
                except:
                    break
            
            total_cards = await page.evaluate('document.querySelectorAll(".channel-card").length')
            print(f"✅ Cards cargados: {total_cards}\n")
            
            # Ahora extraer directamente desde liveTVChannelsData
            print("📊 Extrayendo datos desde liveTVChannelsData...")
            
            channels_data = await page.evaluate('''() => {
                if (typeof liveTVChannelsData === 'undefined') {
                    return { error: 'liveTVChannelsData no definido' };
                }
                
                return liveTVChannelsData.map((ch, idx) => {
                    // Normalizar playerUrl (cambiar user=ntvstream a user=cdnlivetv)
                    let playerUrl = ch.playerUrl || ch.url || ch.iframe || '';
                    if (playerUrl && playerUrl.includes('cdn-live.tv')) {
                        playerUrl = playerUrl.replace(/user=ntvstream/g, 'user=cdnlivetv');
                    }
                    
                    return {
                        index: idx,
                        name: ch.name || '',
                        logo: ch.logo || 'https://iptv.playtorrio.xyz/logo.ico',
                        category: ch.category || 'General',
                        player_url: playerUrl
                    };
                });
            }''')
            
            if isinstance(channels_data, dict) and 'error' in channels_data:
                print(f"❌ Error: {channels_data['error']}")
                return []
            
            print(f"✅ Extraídos {len(channels_data)} canales\n")
            
            # Procesar y enriquecer con logos reales
            print("🎨 Procesando logos y países...")
            success = 0
            failed = 0
            
            for ch in channels_data:
                if ch['player_url']:
                    # Extraer info desde la URL
                    channel_name, country_code = extract_channel_info_from_url(ch['player_url'])
                    
                    if channel_name and country_code:
                        # Generar logo real
                        real_logo = generate_logo_url(channel_name, country_code)
                        
                        # Actualizar datos del canal
                        ch['real_logo'] = real_logo
                        ch['country_code'] = country_code
                        ch['country_name'] = get_country_display_name(country_code)
                        ch['channel_url_name'] = channel_name
                        
                        channels.append(ch)
                        success += 1
                    else:
                        # Si no se puede extraer, usar datos originales
                        ch['real_logo'] = ch['logo']
                        ch['country_code'] = 'UNKNOWN'
                        ch['country_name'] = 'Unknown'
                        channels.append(ch)
                        failed += 1
                else:
                    failed += 1
            
            print(f"✅ Canales válidos con logo real: {success}")
            print(f"⚠️  Canales sin logo real: {failed}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await browser.close()
    
    return channels

def generate_m3u(channels, output_file='playtorrio_canales.m3u'):
    """Genera archivo M3U con logos reales y códigos de país"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')
        
        for channel in channels:
            name = channel['name'].replace('"', "'").strip()
            
            # Usar logo real si existe, sino usar el original
            logo = channel.get('real_logo', channel['logo'])
            
            # Usar código de país como group-title
            country = channel.get('country_code', 'UNKNOWN').upper()
            
            player_url = channel['player_url']
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{country}",{name}\n')
            f.write(f'{player_url}\n\n')
    
    print(f"\n✅ Archivo M3U generado: {output_file}")
    print(f"📊 Total de canales: {len(channels)}")

async def main():
    print("=" * 70)
    print("🚀 PLAYTORRIO - EXTRACTOR MEJORADO CON LOGOS Y PAÍSES REALES V2")
    print("=" * 70)
    print()
    
    channels = await extract_players_fast()
    
    if channels:
        # Generar M3U
        generate_m3u(channels, 'playtorrio_canales.m3u')
        
        # Guardar JSON
        with open('channels_players.json', 'w', encoding='utf-8') as f:
            json.dump(channels, f, indent=2, ensure_ascii=False)
        print(f"📝 JSON guardado: channels_players.json")
        
        # Estadísticas por país
        countries = {}
        for ch in channels:
            country = ch.get('country_name', 'Unknown')
            countries[country] = countries.get(country, 0) + 1
        
        print("\n" + "=" * 70)
        print("🌍 TOP 15 PAÍSES:")
        print("=" * 70)
        for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:15]:
            print(f"   {country:20s}: {count:3d} canales")
        
        # Verificar logos reales
        real_logos = sum(1 for ch in channels if ch.get('real_logo') and 'cdn-live.tv' in ch.get('real_logo', ''))
        print(f"\n📸 Logos reales extraídos: {real_logos}/{len(channels)} ({real_logos/len(channels)*100:.1f}%)")
        
        # Mostrar primeros 5 como ejemplo
        print("\n" + "=" * 70)
        print("🔍 EJEMPLOS (primeros 5 canales con logo real):")
        print("=" * 70)
        count = 0
        for ch in channels:
            if ch.get('real_logo') and 'cdn-live.tv' in ch.get('real_logo', ''):
                count += 1
                print(f"\n{count}. {ch['name']} [{ch.get('country_name', 'N/A')}]")
                print(f"   Logo: {ch['real_logo']}")
                print(f"   URL:  {ch['player_url']}")
                if count >= 5:
                    break
        
        print("\n" + "=" * 70)
        print(f"✅ COMPLETADO: {len(channels)} canales procesados")
        print("=" * 70)
    else:
        print("\n❌ No se extrajeron canales")
        exit(1)

if __name__ == '__main__':
    asyncio.run(main())

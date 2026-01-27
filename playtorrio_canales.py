#!/usr/bin/env python3
"""
PlayTorrio IFRAME Player URLs Extractor - VERSIÓN OPTIMIZADA
✅ Extrae las URLs de los iframe players directamente desde liveTVChannelsData
✅ Mucho más rápido - sin necesidad de reproducir cada canal
"""
import asyncio
import re
import json
from playwright.async_api import async_playwright

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
            
            # Filtrar y validar
            success = 0
            failed = 0
            
            for ch in channels_data:
                if ch['player_url']:
                    channels.append(ch)
                    success += 1
                else:
                    failed += 1
            
            print(f"✅ Canales válidos: {success}")
            print(f"❌ Canales sin URL: {failed}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await browser.close()
    
    return channels

def generate_m3u(channels, output_file='playtorrio_canales.m3u'):
    """Genera archivo M3U con las URLs de los iframe players"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')
        
        for channel in channels:
            name = channel['name'].replace('"', "'").strip()
            logo = channel['logo']
            category = channel['category'].replace('"', "'").strip()
            player_url = channel['player_url']
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{name}\n')
            f.write(f'{player_url}\n\n')
    
    print(f"\n✅ Archivo M3U generado: {output_file}")
    print(f"📊 Total de canales: {len(channels)}")

async def main():
    print("=" * 70)
    print("🚀 PLAYTORRIO IFRAME PLAYER URLS EXTRACTOR - VERSIÓN RÁPIDA")
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
        
        # Estadísticas
        categories = {}
        for ch in channels:
            cat = ch['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        print("\n" + "=" * 70)
        print("📊 TOP 10 CATEGORÍAS:")
        print("=" * 70)
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {cat:20s}: {count:3d} canales")
        
        # Verificar logos
        valid_logos = sum(1 for ch in channels if ch['logo'] and not ch['logo'].endswith('logo.ico'))
        print(f"\n📸 Logos válidos: {valid_logos}/{len(channels)} ({valid_logos/len(channels)*100:.1f}%)")
        
        # Mostrar primeros 5 player URLs como ejemplo
        print("\n" + "=" * 70)
        print("🔍 EJEMPLOS DE PLAYER URLs (primeros 5):")
        print("=" * 70)
        for i, ch in enumerate(channels[:5], 1):
            print(f"\n{i}. {ch['name']}")
            print(f"   {ch['player_url']}")
        
        print("\n" + "=" * 70)
        print(f"✅ COMPLETADO: {len(channels)} canales extraídos")
        print("=" * 70)
    else:
        print("\n❌ No se extrajeron canales")
        exit(1)

if __name__ == '__main__':
    asyncio.run(main())

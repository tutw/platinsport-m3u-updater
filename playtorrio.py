#!/usr/bin/env python3
"""
Script FINAL optimizado para extraer TODOS los canales de PlayTorrio
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def get_all_channels():
    """Extrae todos los canales interceptando las peticiones de red"""
    channels = []
    current_channel_requests = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Interceptar peticiones M3U8
        async def handle_request(request):
            url = request.url
            if '.m3u8' in url and 'index.m3u8' in url:
                current_channel_requests.append(url)
        
        page.on('request', handle_request)
        
        try:
            print("🔍 Accediendo a PlayTorrio...")
            await page.goto('https://iptv.playtorrio.xyz', wait_until='domcontentloaded', timeout=90000)
            await asyncio.sleep(5)
            
            print("📺 Navegando a Live TV Channels...")
            await page.click('text=Live TV Channels', timeout=10000)
            await asyncio.sleep(5)
            
            # Extraer info de canales
            print("🔎 Extrayendo información de canales...\n")
            channel_data = await page.evaluate('''() => {
                const channelCards = document.querySelectorAll('.channel-card');
                return Array.from(channelCards).map((card, index) => {
                    const nameEl = card.querySelector('.channel-name');
                    const logoEl = card.querySelector('.channel-logo img');
                    const tagEls = card.querySelectorAll('.channel-tag');
                    const tags = Array.from(tagEls).map(t => t.textContent.trim());
                    const uniqueTags = [...new Set(tags)];
                    
                    return {
                        id: index,
                        name: nameEl ? nameEl.textContent.trim() : `Channel ${index}`,
                        logo: logoEl ? logoEl.src : '',
                        tags: uniqueTags,
                        category: uniqueTags[0] || ''
                    };
                });
            }''')
            
            total = len(channel_data)
            print(f"✅ Encontrados {total} canales\n")
            print(f"🎯 Procesando {total} canales...\n")
            
            # Procesar TODOS los canales
            for idx in range(total):
                channel = channel_data[idx]
                print(f"[{idx+1}/{total}] {channel['name']} ({channel['category']})...", end=" ", flush=True)
                
                try:
                    current_channel_requests.clear()
                    
                    # Reproducir canal
                    await page.evaluate(f'playLiveTVChannel({idx})')
                    await asyncio.sleep(2.5)  # Tiempo optimizado
                    
                    # Buscar URL M3U8
                    stream_url = ''
                    if current_channel_requests:
                        stream_url = current_channel_requests[0]
                    
                    if stream_url and not stream_url.startswith('blob:'):
                        channel_info = {
                            'name': channel['name'],
                            'logo': channel['logo'] or 'https://iptv.playtorrio.xyz/logo.ico',
                            'language': ', '.join(channel['tags']),
                            'category': channel['category'],
                            'stream_url': stream_url
                        }
                        channels.append(channel_info)
                        print("✅")
                    else:
                        print("⚠️")
                    
                    # Cerrar modal
                    try:
                        await page.evaluate('document.querySelector(".modal-close")?.click()')
                        await asyncio.sleep(0.3)
                    except:
                        pass
                    
                except Exception as e:
                    print(f"❌ {str(e)[:50]}")
                    continue
            
        except Exception as e:
            print(f"\n❌ Error general: {str(e)}")
        
        finally:
            await browser.close()
    
    return channels

def generate_m3u(channels, output_file='playtorrio.m3u'):
    """Genera archivo M3U optimizado"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')
        
        for channel in channels:
            name = channel['name']
            logo = channel['logo']
            category = channel['category'] or channel.get('language', '')
            stream_url = channel['stream_url']
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{name}\n')
            f.write(f'{stream_url}\n\n')
    
    print(f"\n✅ Archivo M3U generado: {output_file}")
    print(f"📊 Total de canales exitosos: {len(channels)}")

async def main():
    print("=" * 80)
    print("🚀 EXTRACTOR DE CANALES PLAYTORRIO - VERSIÓN FINAL")
    print("=" * 80)
    print()
    
    channels = await get_all_channels()
    
    if channels:
        generate_m3u(channels, '/home/user/playtorrio.m3u')
        
        with open('/home/user/channels_final.json', 'w', encoding='utf-8') as f:
            json.dump(channels, f, indent=2, ensure_ascii=False)
        print(f"📝 JSON guardado: channels_final.json")
        
        print("\n" + "=" * 80)
        print("📋 PRIMEROS 5 CANALES:")
        print("=" * 80)
        for ch in channels[:5]:
            print(f"\n• {ch['name']} ({ch['category']})")
            print(f"  Logo: {ch['logo']}")
            print(f"  Stream: {ch['stream_url'][:80]}...")
        
        print("\n" + "=" * 80)
        print(f"✅ COMPLETADO: {len(channels)} canales extraídos correctamente")
        print("=" * 80)
    else:
        print("\n❌ No se extrajeron canales")

if __name__ == '__main__':
    asyncio.run(main())

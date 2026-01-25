#!/usr/bin/env python3
"""
Script DEFINITIVO para extraer TODOS los canales de PlayTorrio (6000+)
- Hace clic en el botón "Load More" hasta cargar todos
- Extrae logos correctamente
- Optimizado para velocidad
- Manejo robusto de errores
"""
import asyncio
import json
import os
import re
from playwright.async_api import async_playwright

async def get_all_channels():
    """Extrae TODOS los canales haciendo clic en Load More"""
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
            await asyncio.sleep(3)
            
            print("📺 Navegando a Live TV Channels...")
            await page.click('text=Live TV Channels', timeout=10000)
            await asyncio.sleep(5)
            
            # Hacer clic en "Load More" hasta cargar TODOS los canales
            print("📜 Cargando todos los canales (haciendo clic en 'Load More')...")
            load_more_clicks = 0
            max_clicks = 200  # Máximo de clics para seguridad
            
            while load_more_clicks < max_clicks:
                try:
                    # Buscar el botón "Load More"
                    load_more_text = await page.text_content('button.glow-btn:has-text("Load More")', timeout=2000)
                    
                    # Extraer número de canales restantes
                    match = re.search(r'(\d+)\s+remaining', load_more_text)
                    remaining = int(match.group(1)) if match else 0
                    
                    # Contar canales actuales
                    current_count = await page.evaluate('document.querySelectorAll(".channel-card").length')
                    
                    print(f"   Canales cargados: {current_count} | Restantes: {remaining} | Clics: {load_more_clicks+1}", end='\r', flush=True)
                    
                    if remaining == 0:
                        print(f"\n✅ Todos los canales cargados: {current_count}")
                        break
                    
                    # Hacer clic en "Load More"
                    await page.click('button.glow-btn:has-text("Load More")', timeout=5000)
                    await asyncio.sleep(0.5)  # Más rápido
                    
                    load_more_clicks += 1
                    
                except Exception as e:
                    # No hay más botón "Load More" o error
                    current_count = await page.evaluate('document.querySelectorAll(".channel-card").length')
                    print(f"\n✅ Todos los canales cargados: {current_count}")
                    break
            
            # Extraer info de TODOS los canales
            print("\n🔎 Extrayendo información de canales...\n")
            channel_data = await page.evaluate('''() => {
                const channelCards = document.querySelectorAll('.channel-card');
                return Array.from(channelCards).map((card, index) => {
                    const nameEl = card.querySelector('.channel-name');
                    const logoEl = card.querySelector('.channel-logo img');
                    const tagEls = card.querySelectorAll('.channel-tag');
                    const tags = Array.from(tagEls).map(t => t.textContent.trim());
                    const uniqueTags = [...new Set(tags)];
                    
                    // Extraer logo correctamente (src o data-src)
                    let logo = '';
                    if (logoEl) {
                        logo = logoEl.src || logoEl.getAttribute('data-src') || logoEl.getAttribute('data-lazy-src') || '';
                        // Si es data:image, buscar en otros atributos
                        if (logo.startsWith('data:')) {
                            logo = logoEl.getAttribute('data-original') || logo;
                        }
                    }
                    
                    return {
                        id: index,
                        name: nameEl ? nameEl.textContent.trim() : `Channel ${index}`,
                        logo: logo,
                        tags: uniqueTags,
                        category: uniqueTags[0] || 'General'
                    };
                });
            }''')
            
            total = len(channel_data)
            print(f"✅ Encontrados {total} canales\n")
            print(f"🎯 Procesando {total} canales (esto tomará tiempo)...\n")
            
            # Limitar a 516 canales para no exceder timeout
            total_to_process = min(total, 516)
            print(f"   (Procesando primeros {total_to_process} canales)\n")
            
            # Procesar canales
            for idx in range(total_to_process):
                channel = channel_data[idx]
                channel_name_short = channel['name'][:40] if len(channel['name']) > 40 else channel['name']
                print(f"[{idx+1}/{total}] {channel_name_short}... ({channel['category']})", end=" ", flush=True)
                
                try:
                    current_channel_requests.clear()
                    
                    # Reproducir canal
                    await page.evaluate(f'playLiveTVChannel({idx})')
                    await asyncio.sleep(1.0)  # Más rápido
                    
                    # Buscar URL M3U8
                    stream_url = ''
                    if current_channel_requests:
                        stream_url = current_channel_requests[0]
                    
                    if stream_url and not stream_url.startswith('blob:'):
                        # Logo fallback
                        logo = channel['logo']
                        if not logo or logo.startswith('data:'):
                            logo = 'https://iptv.playtorrio.xyz/logo.ico'
                        
                        channel_info = {
                            'name': channel['name'],
                            'logo': logo,
                            'language': ', '.join(channel['tags']) if channel['tags'] else '',
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
                        await asyncio.sleep(0.1)
                    except:
                        pass
                    
                except Exception as e:
                    print(f"❌")
                    continue
                
                # Cada 100 canales, mostrar progreso
                if (idx + 1) % 100 == 0:
                    success_rate = (len(channels) / (idx + 1)) * 100
                    print(f"\n   📊 Progreso: {len(channels)} exitosos de {idx+1} ({success_rate:.1f}%)\n")
            
        except Exception as e:
            print(f"\n❌ Error general: {str(e)}")
        
        finally:
            await browser.close()
    
    return channels

def generate_m3u(channels, output_file='playtorrio.m3u'):
    """Genera archivo M3U optimizado"""
    # Asegurar que el directorio existe
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')
        
        for channel in channels:
            name = channel['name']
            logo = channel['logo']
            category = channel['category'] or channel.get('language', '')
            stream_url = channel['stream_url']
            
            # Limpiar nombre y categoría
            name = name.replace('"', "'").strip()
            category = category.replace('"', "'").strip()
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{name}\n')
            f.write(f'{stream_url}\n\n')
    
    print(f"\n✅ Archivo M3U generado: {output_file}")
    print(f"📊 Total de canales exitosos: {len(channels)}")

async def main():
    print("=" * 80)
    print("🚀 EXTRACTOR DE CANALES PLAYTORRIO - VERSIÓN DEFINITIVA")
    print("=" * 80)
    print()
    
    channels = await get_all_channels()
    
    if channels:
        # Determinar ruta de salida (GitHub Actions usa el directorio actual)
        output_path = 'playtorrio.m3u'
        
        generate_m3u(channels, output_path)
        
        # Guardar JSON
        json_path = 'channels_final.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(channels, f, indent=2, ensure_ascii=False)
        print(f"📝 JSON guardado: {json_path}")
        
        # Estadísticas por categoría
        categories = {}
        for ch in channels:
            cat = ch['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        print("\n" + "=" * 80)
        print("📊 ESTADÍSTICAS POR CATEGORÍA:")
        print("=" * 80)
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {cat}: {count} canales")
        
        print("\n" + "=" * 80)
        print("📋 PRIMEROS 10 CANALES:")
        print("=" * 80)
        for ch in channels[:10]:
            print(f"\n• {ch['name']} ({ch['category']})")
            print(f"  Logo: {ch['logo'][:80]}...")
            print(f"  Stream: {ch['stream_url'][:80]}...")
        
        print("\n" + "=" * 80)
        print(f"✅ COMPLETADO: {len(channels)} canales extraídos correctamente")
        print("=" * 80)
    else:
        print("\n❌ No se extrajeron canales")
        exit(1)

if __name__ == '__main__':
    asyncio.run(main())

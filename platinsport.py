from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import base64
import time

url = "https://www.platinsport.com/"

print("=== PLATINSPORT SCRAPER FINAL ===\n")

all_streams = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Establecer cookie de aceptación de términos
    context.add_cookies([{
        "name": "disclaimer_accepted",
        "value": "true",
        "domain": ".platinsport.com",
        "path": "/",
        "sameSite": "Lax"
    }])
    
    page = context.new_page()
    
    print("Cargando página principal...")
    try:
        page.goto(url, timeout=90000, wait_until="domcontentloaded")
        time.sleep(2)
        print("✓ Página cargada\n")
    except Exception as e:
        print(f"✗ Error al cargar página: {e}")
        browser.close()
        exit(1)
    
    # Obtener el HTML completo
    main_html = page.content()
    soup = BeautifulSoup(main_html, "html.parser")
    
    print("Analizando estructura de eventos...")
    
    # Encontrar todos los divs de categoría (tienen el estilo específico)
    category_divs = soup.find_all("div", style=re.compile(r"background:#000.*color:#ffae00"))
    
    print(f"✓ Encontradas {len(category_divs)} categorías\n")
    
    # Procesar cada categoría y sus eventos
    for cat_div in category_divs:
        category = cat_div.get_text(strip=True)
        category = re.sub(r'^[–\-]\s*', '', category)  # Limpiar guiones iniciales
        
        print(f"Categoría: {category}")
        
        # Encontrar todos los divs de eventos después de esta categoría
        # Buscar el siguiente elemento hermano hasta encontrar otra categoría
        current = cat_div.find_next_sibling()
        event_count = 0
        
        while current and not (current.name == "div" and current.get("style") and "background:#000" in current.get("style", "") and "color:#ffae00" in current.get("style", "")):
            # Buscar botones PLAY en este div
            play_links = current.find_all("a", href=re.compile(r"javascript:go"))
            
            for play_link in play_links:
                event_count += 1
                
                # Buscar el contenedor del evento (el div más cercano que contiene toda la info)
                event_div = play_link.find_parent("div", style=re.compile(r"background: #0a0a0a|border: 1px solid #333"))
                
                if not event_div:
                    event_div = play_link.find_parent("div")
                
                # Extraer hora
                time_elem = event_div.find("time") if event_div else None
                event_time = time_elem.get_text(strip=True) if time_elem else ""
                
                # Extraer nombres de equipos (span tags)
                team_spans = event_div.find_all("span", style=re.compile(r"font-size: 12px; color: #fff")) if event_div else []
                teams = [span.get_text(strip=True) for span in team_spans if span.get_text(strip=True)]
                
                # Crear nombre del evento
                if len(teams) >= 2:
                    event_name = f"{teams[0]} vs {teams[1]}"
                else:
                    # Intentar extraer de otra forma
                    event_name = f"Evento {event_count}"
                
                print(f"  • {event_name} - {event_time}")
                
                # Extraer el PHP file del href
                href = play_link.get("href", "")
                match = re.search(r"go\('([^']+)'\)", href)
                if not match:
                    print(f"    ✗ No se pudo extraer el PHP file")
                    continue
                
                php_file = match.group(1)
                
                # Generar key de acceso
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                key = base64.b64encode((today + "PLATINSPORT").encode()).decode()
                
                popup_url = f"https://www.platinsport.com/link/{php_file}?key={key}"
                
                # Abrir popup
                popup_page = context.new_page()
                
                try:
                    popup_page.goto(popup_url, timeout=30000, referer=url)
                    popup_page.wait_for_load_state("domcontentloaded")
                    time.sleep(0.3)
                    
                    popup_html = popup_page.content()
                    popup_soup = BeautifulSoup(popup_html, "html.parser")
                    
                    # Parsear enlaces acestream
                    ace_links = popup_soup.find_all("a", href=re.compile(r"^acestream://"))
                    
                    print(f"    ✓ {len(ace_links)} streams")
                    
                    for link in ace_links:
                        ace_url = link.get("href", "")
                        
                        # Extraer bandera/idioma
                        flag_span = link.find("span", class_=re.compile(r"fi fi-"))
                        lang = "XX"
                        if flag_span:
                            classes = flag_span.get("class", [])
                            for cls in classes:
                                if cls.startswith("fi-"):
                                    lang = cls.replace("fi-", "").upper()
                                    break
                        
                        # Extraer nombre del canal
                        channel_text = link.get_text(strip=True)
                        if flag_span and flag_span.get_text():
                            channel_text = channel_text.replace(flag_span.get_text(), "").strip()
                        
                        channel = channel_text if channel_text else "STREAM HD"
                        
                        all_streams.append({
                            "event": event_name,
                            "category": category,
                            "time": event_time,
                            "channel": channel,
                            "url": ace_url,
                            "lang": lang
                        })
                    
                    popup_page.close()
                    
                except Exception as e:
                    print(f"    ✗ Error: {str(e)[:50]}")
                    popup_page.close()
                
                # Pequeña pausa entre eventos
                time.sleep(0.1)
            
            # Avanzar al siguiente elemento
            current = current.find_next_sibling()
        
        print()
    
    page.close()
    browser.close()

# Generar archivo M3U
print("Generando lista.m3u...")
m3u_lines = ["#EXTM3U"]

for stream in all_streams:
    # Formato: Evento - Hora - [LANG] Canal
    event_info = stream['event']
    if stream['time']:
        event_info = f"{event_info} - {stream['time']}"
    
    tvg_name = f"{event_info} - [{stream['lang']}] {stream['channel']}"
    group_title = stream["category"]
    
    m3u_lines.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{group_title}",{stream["channel"]}')
    m3u_lines.append(stream["url"])

with open("lista.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines) + "\n")

print(f"\n{'='*50}")
print(f"✓ lista.m3u generado con éxito!")
print(f"✓ Total de streams: {len(all_streams)}")
print(f"✓ Categorías únicas: {len(set(s['category'] for s in all_streams))}")
print(f"✓ Eventos únicos: {len(set(s['event'] for s in all_streams))}")
print(f"{'='*50}")

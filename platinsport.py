from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime
import base64
import time

url = "https://www.platinsport.com/"

print("=== PLATINSPORT SCRAPER ===\n")

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
        time.sleep(3)
        print("✓ Página cargada\n")
    except Exception as e:
        print(f"✗ Error al cargar página: {e}")
        browser.close()
        exit(1)
    
    # Buscar botones PLAY
    print("Buscando eventos deportivos...")
    play_buttons = page.locator("a[href*='javascript:go']").all()
    print(f"✓ Encontrados {len(play_buttons)} eventos\n")
    
    if len(play_buttons) > 0:
        print("Extrayendo enlaces acestream...\n")
        
        # Obtener href del primer botón (todos apuntan al mismo source-list.php)
        first_btn = play_buttons[0]
        href = first_btn.get_attribute("href")
        
        match = re.search(r"go\('([^']+)'\)", href)
        if match:
            php_file = match.group(1)
            
            # Generar key de acceso
            today = datetime.utcnow().strftime("%Y-%m-%d")
            key = base64.b64encode((today + "PLATINSPORT").encode()).decode()
            
            popup_url = f"https://www.platinsport.com/link/{php_file}?key={key}"
            
            # Abrir popup con cookie establecida
            popup_page = context.new_page()
            
            try:
                popup_page.goto(popup_url, timeout=30000, referer=url)
                popup_page.wait_for_load_state("domcontentloaded")
                time.sleep(2)
                
                popup_html = popup_page.content()
                
                # Parsear enlaces acestream
                soup = BeautifulSoup(popup_html, "html.parser")
                ace_links = soup.find_all("a", href=re.compile(r"^acestream://"))
                
                print(f"✓ {len(ace_links)} enlaces encontrados\n")
                
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
                    if flag_span:
                        channel_text = channel_text.replace(flag_span.get_text(""), "").strip()
                    
                    channel = channel_text or "STREAM HD"
                    all_streams.append({
                        "channel": channel,
                        "url": ace_url,
                        "lang": lang
                    })
                
                popup_page.close()
                
            except Exception as e:
                print(f"✗ Error al acceder a enlaces: {e}")
                popup_page.close()
    
    page.close()
    browser.close()

# Generar archivo M3U
print("Generando lista.m3u...")
m3u_lines = ["#EXTM3U"]

for stream in all_streams:
    m3u_lines.append(f'#EXTINF:-1 tvg-name="[{stream["lang"]}] {stream["channel"]}" group-title="Acestream",{stream["channel"]}')
    m3u_lines.append(stream["url"])

with open("lista.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines) + "\n")

print(f"✓ lista.m3u generado - {len(all_streams)} streams encontrados")

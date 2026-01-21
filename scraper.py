import base64
import datetime
import json
import time
import random
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# Configuración
BASE_DOMAIN = "https://www.platinsport.com"
START_URL = "https://www.platinsport.com/link/" # Para "calentar" cookies
SOURCE_TEMPLATE = "https://www.platinsport.com/link/source-list.php?key="

def get_dynamic_url():
    """Genera la URL con la key diaria."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    raw_string = f"{today}PLATINSPORT"
    encoded_bytes = base64.b64encode(raw_string.encode("utf-8"))
    encoded_key = encoded_bytes.decode("utf-8")
    return f"{SOURCE_TEMPLATE}{encoded_key}"

def parse_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    content_div = soup.find('div', class_='myDiv1')
    
    if not content_div:
        return []

    sports_data = []
    current_league = "Unknown League"
    current_match = None

    for element in content_div.children:
        if element.name is None: continue

        if element.name == 'p':
            current_league = element.get_text(strip=True)

        elif element.name == 'div' and 'match-title-bar' in element.get('class', []):
            time_tag = element.find('time')
            match_time = time_tag['datetime'] if time_tag and 'datetime' in time_tag.attrs else "N/A"
            match_title = element.get_text(" ", strip=True)
            if time_tag:
                match_title = match_title.replace(time_tag.get_text(), "").strip()

            current_match = {
                "league": current_league,
                "match": match_title,
                "time": match_time,
                "links": []
            }
            sports_data.append(current_match)

        elif element.name == 'div' and 'button-group' in element.get('class', []):
            if current_match:
                for link in element.find_all('a'):
                    href = link.get('href')
                    channel_name = link.get_text(strip=True)
                    if href and (href.startswith('acestream://') or href.startswith('http')):
                        current_match["links"].append({
                            "channel": channel_name,
                            "url": href
                        })

    return sports_data

def main():
    target_url = get_dynamic_url()
    print(f"Objetivo: {target_url}")

    with sync_playwright() as p:
        # Argumentos para parecer un navegador real y no un bot
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        # Simulamos una pantalla estándar de laptop
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="es-ES"
        )
        
        page = context.new_page()
        
        # Aplicamos el módulo stealth (OCULTA que somos Playwright)
        stealth_sync(page)

        try:
            # 1. VISITA PREVIA: Vamos a la home primero para obtener cookies de sesión
            print("1. Calentando sesión (visitando home)...")
            page.goto(START_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2, 4)) # Espera humana

            # 2. NAVEGACIÓN REAL: Ahora vamos a la URL con key
            print("2. Accediendo a la URL protegida...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            
            # Esperamos selectores clave
            try:
                page.wait_for_selector("div.myDiv1", timeout=15000)
            except:
                print("Nota: myDiv1 tardó en aparecer o no está.")

            html_content = page.content()
            
            # Validación de contenido
            if "Access Restricted" in html_content or "403 Forbidden" in html_content:
                print("ERROR: El bloqueo persiste.")
                # Guardamos el HTML de error para debuggear si falla (opcional)
                with open("debug_error.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                exit(1) # Salimos con error para que GitHub avise

            data = parse_html(html_content)
            
            if not data:
                print("ADVERTENCIA: No se extrajeron datos (la lista podría estar vacía hoy).")
            
            # Guardar JSON
            filename = 'sports_schedule.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            print(f"ÉXITO: {len(data)} eventos guardados.")

        except Exception as e:
            print(f"Excepción crítica: {e}")
            exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    main()

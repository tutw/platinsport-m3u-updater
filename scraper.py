import base64
import datetime
import json
import time
import random
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_page

# Configuración
BASE_DOMAIN = "https://www.platinsport.com"
START_URL = "https://www.platinsport.com/link/" # Para "calentar" cookies
SOURCE_TEMPLATE = "https://www.platinsport.com/link/source-list.php?key="

def get_dynamic_url():
    """Genera la URL con la key diaria en Base64."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    raw_string = f"{today}PLATINSPORT"
    encoded_bytes = base64.b64encode(raw_string.encode("utf-8"))
    encoded_key = encoded_bytes.decode("utf-8")
    return f"{SOURCE_TEMPLATE}{encoded_key}"

def parse_html(html_content):
    """Procesa el HTML para extraer ligas, partidos y links."""
    soup = BeautifulSoup(html_content, 'html.parser')
    content_div = soup.find('div', class_='myDiv1')
    
    if not content_div:
        return []

    sports_data = []
    current_league = "Liga Desconocida"
    current_match = None

    for element in content_div.children:
        if element.name is None: continue

        # Identificar la liga (párrafos)
        if element.name == 'p':
            current_league = element.get_text(strip=True)

        # Identificar el partido (título y hora)
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

        # Identificar los botones de canales/links
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
        # Lanzamos el navegador
        browser = p.chromium.launch(headless=True)
        
        # Configuramos el contexto con un User Agent real
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        
        page = context.new_page()
        
        # APLICAR STEALTH (Corregido: stealth_page)
        stealth_page(page) 

        try:
            # 1. Visita previa para generar cookies válidas
            print("1. Calentando sesión (visitando home)...")
            page.goto(START_URL, wait_until="networkidle")
            time.sleep(random.uniform(2, 4))

            # 2. Navegación a la lista de fuentes
            print("2. Accediendo a la URL protegida...")
            page.goto(target_url, wait_until="networkidle")
            
            # Espera técnica para asegurar carga de scripts
            page.wait_for_timeout(5000) 

            html_content = page.content()
            
            # Verificación de bloqueo
            if "Access Restricted" in html_content or "403 Forbidden" in html_content:
                print("ERROR: Bloqueo detectado (403).")
                exit(1)

            # Parseo de datos
            data = parse_html(html_content)
            
            # Guardar en JSON
            with open('sports_schedule.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            print(f"ÉXITO: {len(data)} eventos guardados en sports_schedule.json")

        except Exception as e:
            print(f"Excepción: {e}")
            exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    main()

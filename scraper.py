import base64
import datetime
import json
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Configuración
BASE_URL = "https://www.platinsport.com/link/source-list.php?key="

def get_dynamic_url():
    """Genera la URL con la key diaria basada en la fecha del sistema."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    raw_string = f"{today}PLATINSPORT"
    encoded_bytes = base64.b64encode(raw_string.encode("utf-8"))
    encoded_key = encoded_bytes.decode("utf-8")
    return f"{BASE_URL}{encoded_key}"

def parse_html(html_content):
    """Analiza el HTML exacto que has proporcionado."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Buscamos el contenedor principal
    content_div = soup.find('div', class_='myDiv1')
    
    if not content_div:
        print("ADVERTENCIA: No se encontró 'div.myDiv1'. Es posible que la página esté bloqueada o vacía.")
        return []

    sports_data = []
    current_league = "Unknown League"
    current_match = None

    # Iteramos sobre los hijos directos para mantener el orden secuencial
    # Estructura observada: <p>Liga</p> -> <div title>Partido</div> -> <div buttons>Links</div>
    for element in content_div.children:
        # Ignorar saltos de línea o elementos vacíos
        if element.name is None:
            continue

        # 1. Detectar Liga (etiqueta <p>)
        if element.name == 'p':
            text = element.get_text(strip=True)
            if text:
                current_league = text

        # 2. Detectar Partido (div con clase match-title-bar)
        elif element.name == 'div' and 'match-title-bar' in element.get('class', []):
            # Extraer hora del tag <time>
            time_tag = element.find('time')
            match_time = time_tag['datetime'] if time_tag and 'datetime' in time_tag.attrs else "N/A"
            
            # Extraer nombre del partido. 
            # El texto está mezclado con el time, así que obtenemos el texto y limpiamos.
            full_text = element.get_text(" ", strip=True)
            # Si hay tiempo, intentamos quitarlo del texto si aparece duplicado, 
            # pero generalmente el nombre del partido está después del tag time.
            # Una estrategia limpia es tomar el 'next_sibling' del tag time si existe inside.
            match_title = full_text
            if time_tag:
                # Reemplazamos el texto del tiempo con vacío para dejar solo el título
                match_title = element.get_text().replace(time_tag.get_text(), "").strip()

            current_match = {
                "league": current_league,
                "match": match_title,
                "time": match_time,
                "links": []
            }
            sports_data.append(current_match)

        # 3. Detectar Links (div con clase button-group)
        # Se asume que este div viene INMEDIATAMENTE después de un match-title-bar
        elif element.name == 'div' and 'button-group' in element.get('class', []):
            if current_match: # Solo si ya hemos encontrado un partido antes
                for link in element.find_all('a'):
                    href = link.get('href')
                    channel_name = link.get_text(strip=True)
                    
                    # Filtramos enlaces vacíos o javascript:void
                    if href and (href.startswith('acestream://') or href.startswith('http')):
                        current_match["links"].append({
                            "channel": channel_name,
                            "url": href
                        })

    return sports_data

def main():
    target_url = get_dynamic_url()
    print(f"URL Generada: {target_url}")

    with sync_playwright() as p:
        # Lanzamos navegador headless (sin interfaz gráfica)
        browser = p.chromium.launch(headless=True)
        
        # Contexto con User Agent real para engañar al servidor
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        page = context.new_page()

        try:
            print("Accediendo a la web...")
            # Timeout generoso de 60s
            response = page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            
            # Esperamos un poco a que el JS anti-adblock se ejecute y pase
            # A veces es necesario esperar al selector específico
            try:
                page.wait_for_selector("div.myDiv1", timeout=10000)
            except:
                print("No apareció myDiv1 inmediatamente, intentando leer lo que haya...")

            # Obtenemos el HTML final renderizado
            html_content = page.content()
            
            # Verificación básica de bloqueo 403 en el título o contenido
            if "403 Forbidden" in html_content or "Access Restricted" in html_content:
                print("¡ERROR! Bloqueo detectado (403 o Anti-Adblock agresivo).")
                # Aquí se podría implementar lógica de reintento o captura de pantalla debug
            else:
                data = parse_html(html_content)
                
                # Guardar JSON
                filename = 'sports_schedule.json'
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                
                print(f"Éxito. Se han extraído {len(data)} eventos en {filename}.")

        except Exception as e:
            print(f"Error durante la ejecución: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()

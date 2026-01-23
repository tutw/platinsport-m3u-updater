from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta
import os
import sys
import html
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
import urllib.request

BASE_URL = "https://www.platinsport.com/"
LOGOS_XML_URL = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/LOGOS-CANALES-TV.xml"

# Mapeo de códigos de país a nombres
COUNTRY_CODES = {
    "GB": "Reino Unido", "UK": "Reino Unido",
    "ES": "España", "PT": "Portugal", "IT": "Italia",
    "FR": "Francia", "DE": "Alemania", "NL": "Países Bajos",
    "PL": "Polonia", "RU": "Rusia", "UA": "Ucrania",
    "AR": "Argentina", "BR": "Brasil", "MX": "México",
    "US": "Estados Unidos", "CA": "Canadá",
    "TR": "Turquía", "GR": "Grecia", "RO": "Rumanía",
    "HR": "Croacia", "RS": "Serbia", "BG": "Bulgaria",
    "DK": "Dinamarca", "SE": "Suecia", "NO": "Noruega",
    "FI": "Finlandia", "BE": "Bélgica", "CH": "Suiza",
    "AT": "Austria", "CZ": "República Checa", "SK": "Eslovaquia",
    "HU": "Hungría", "XX": "Internacional"
}

def clean_text(s: str) -> str:
    """Limpia y normaliza texto"""
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def extract_lang_from_flag(node) -> str:
    """Extrae el codigo de idioma de la bandera"""
    flag = node.find("span", class_=re.compile(r"\bfi\b|\bfi-"))
    if not flag:
        return "XX"
    classes = flag.get("class", []) or []
    for cls in classes:
        if cls.startswith("fi-") and len(cls) == 5:
            cc = cls.replace("fi-", "").upper()
            if cc == "UK":
                cc = "GB"
            return cc
    return "XX"

def similarity(a: str, b: str) -> float:
    """Calcula la similitud entre dos strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def load_logos_from_xml_url(xml_url: str) -> dict:
    """Carga el mapeo de canales a logos desde el XML en GitHub"""
    logos = {}
    try:
        print(f"[XML] Descargando logos desde {xml_url}...")
        with urllib.request.urlopen(xml_url, timeout=30) as response:
            xml_content = response.read()
        
        root = ET.fromstring(xml_content)
        
        for channel in root.findall(".//channel"):
            name = channel.get("name", "").strip()
            logo_node = channel.find("logo_url")
            if name and logo_node is not None and logo_node.text:
                # Normalizar el nombre del canal para búsqueda
                normalized = name.lower().strip()
                logos[normalized] = {
                    "original_name": name,
                    "logo_url": logo_node.text.strip()
                }
        
        print(f"✓ Cargados {len(logos)} logos del XML")
        return logos
    except Exception as e:
        print(f"⚠ Error cargando logos XML: {e}")
        return {}

def find_best_logo_match(channel_name: str, logos_db: dict, threshold: float = 0.6) -> str:
    """Encuentra el mejor match de logo para un nombre de canal"""
    if not channel_name or not logos_db:
        return ""
    
    channel_normalized = channel_name.lower().strip()
    
    # Búsqueda exacta
    if channel_normalized in logos_db:
        return logos_db[channel_normalized]["logo_url"]
    
    # Búsqueda por similitud
    best_match = None
    best_score = threshold
    
    for db_name, data in logos_db.items():
        score = similarity(channel_normalized, db_name)
        if score > best_score:
            best_score = score
            best_match = data["logo_url"]
    
    return best_match if best_match else ""

def extract_time_from_datetime(match_div) -> str:
    """Extrae la hora de la etiqueta <time> en el div del partido"""
    time_tag = match_div.find("time", class_="time")
    if time_tag and time_tag.get("datetime"):
        try:
            # Parsear formato ISO: "2026-01-23T20:00:00Z"
            dt_str = time_tag.get("datetime")
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            # Retornar hora en formato HH:MM
            return dt.strftime("%H:%M")
        except:
            pass
    return ""

def clean_channel_name(raw_name: str) -> str:
    """Limpia y mejora el nombre del canal"""
    name = clean_text(raw_name)
    
    # Remover patrones comunes no deseados
    name = re.sub(r'\b(STREAM|HD|4K|FHD)\b', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Si quedó vacío, mantener el original limpio
    if not name:
        name = clean_text(raw_name)
    
    return name

def parse_html_for_streams(html_content: str, logos_db: dict):
    """Parsea el HTML y extrae informacion de streams con horarios"""
    soup = BeautifulSoup(html_content, "lxml")
    entries = []
    
    # Buscar todas las secciones de partidos
    match_sections = soup.find_all("div", class_="match-title-bar")
    
    for match_div in match_sections:
        # Extraer la hora desde la etiqueta <time>
        event_time = extract_time_from_datetime(match_div)
        
        # Extraer titulo del partido
        match_title_raw = clean_text(match_div.get_text())
        match_title = match_title_raw
        
        # Buscar el contenedor de botones siguiente
        button_group = match_div.find_next_sibling("div", class_="button-group")
        if not button_group:
            continue
        
        # Buscar todos los enlaces acestream
        links = button_group.find_all("a", href=re.compile(r"^acestream://"))
        
        for a in links:
            href = clean_text(a.get("href", ""))
            if not href.startswith("acestream://"):
                continue
            
            # Extraer idioma de la bandera
            lang_code = extract_lang_from_flag(a)
            country_name = COUNTRY_CODES.get(lang_code, lang_code)
            
            # Extraer nombre del canal (el texto despues de la bandera)
            a_copy = BeautifulSoup(str(a), "lxml").find("a")
            if not a_copy:
                continue
                
            # Eliminar todas las etiquetas de bandera
            for flag in a_copy.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
                flag.decompose()
            
            # Obtener el texto limpio
            channel_name_raw = clean_text(a_copy.get_text())
            
            # Si el nombre esta vacio o es generico, usar alternativas
            if not channel_name_raw or channel_name_raw in ["", "STREAM HD", "HD", "STREAM"]:
                channel_name_raw = clean_text(a.get("title", ""))
                if not channel_name_raw or channel_name_raw in ["", "STREAM HD"]:
                    channel_name_raw = f"Stream {lang_code}"
            
            # Limpiar el nombre del canal
            channel_name = clean_channel_name(channel_name_raw)
            
            # Buscar logo correspondiente
            logo_url = find_best_logo_match(channel_name, logos_db)
            
            entries.append({
                "time": event_time,
                "match": match_title,
                "lang_code": lang_code,
                "country": country_name,
                "channel": channel_name,
                "logo": logo_url,
                "url": href,
            })
    
    return entries

def write_m3u(all_entries, out_path="lista.m3u"):
    """Escribe el archivo M3U con los streams en formato mejorado"""
    m3u = ["#EXTM3U"]
    
    for e in all_entries:
        event_time = e.get("time", "")
        match = e.get("match", "Evento")
        country = e.get("country", "")
        channel = e.get("channel", "STREAM")
        logo = e.get("logo", "")
        url = e.get("url", "")
        
        # Construir el nombre del canal en formato:
        # hora - nombre del evento deportivo, [país], canal de TV
        parts = []
        if event_time:
            # Usar guión en lugar de coma después de la hora
            parts.append(f"{event_time} -")
        
        # Añadir nombre del evento
        parts.append(match)
        
        # Añadir país entre corchetes
        if country:
            parts.append(f", [{country}],")
        else:
            parts.append(",")
        
        # Añadir canal
        parts.append(channel)
        
        display_name = " ".join(parts)
        
        # Construir línea EXTINF sin group-title ni tvg-name, solo con tvg-logo
        if logo:
            extinf_line = f'#EXTINF:-1 tvg-logo="{logo}", {display_name}'
        else:
            extinf_line = f'#EXTINF:-1 , {display_name}'
        
        m3u.append(extinf_line)
        m3u.append(url)
    
    # Escribir el archivo
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u))
    
    print(f"\n✓ Archivo M3U guardado: {out_path}")

def main():
    os.makedirs("debug", exist_ok=True)
    
    # Cargar logos desde GitHub
    print("\n" + "=" * 70)
    print("CARGANDO LOGOS DESDE GITHUB...")
    print("=" * 70)
    logos_db = load_logos_from_xml_url(LOGOS_XML_URL)
    
    # Capturar HTML
    print("\n" + "=" * 70)
    print("CAPTURANDO HTML...")
    print("=" * 70)
    
    raw_html = None
    
    with sync_playwright() as p:
        print("[1] Iniciando navegador...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        
        # Cookie ANTES de navegar
        expiry = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
        context.add_cookies([{
            "name": "disclaimer_accepted",
            "value": "true",
            "domain": ".platinsport.com",
            "path": "/",
            "expires": expiry,
            "sameSite": "Lax"
        }])
        print("[2] Cookie disclaimer establecida")

        # Interceptar a nivel de contexto ANTES de abrir popup
        def handle_route(route, request):
            nonlocal raw_html
            
            if "source-list.php" in request.url:
                print(f"[4] Interceptando: {request.url}")
                
                response = route.fetch()
                body = response.text()
                
                raw_html = body
                print(f"[5] HTML capturado: {len(body)} bytes")
                
                # Guardar para debug
                with open("debug/daily_page_intercepted.html", "w", encoding="utf-8") as f:
                    f.write(body)
                print("[6] Debug guardado: debug/daily_page_intercepted.html")
                
                route.fulfill(response=response)
            else:
                route.continue_()
        
        context.route("**/*", handle_route)
        print("[3] Interceptor registrado")

        page = context.new_page()

        print(f"[7] Navegando a {BASE_URL}...")
        try:
            page.goto(BASE_URL, timeout=120000, wait_until="domcontentloaded")
            import time
            time.sleep(2)
            print("     Pagina principal cargada")
        except Exception as e:
            print(f"     Error: {e}")
            browser.close()
            sys.exit(1)

        print("[8] Buscando boton PLAY...")
        try:
            play_button = page.locator("a[href=\"javascript:go('source-list.php')\"]").first
            
            if play_button.is_visible(timeout=10000):
                print("     Boton encontrado")
                
                print("[9] Haciendo click y esperando popup...")
                with page.expect_popup(timeout=30000) as popup_info:
                    play_button.click()
                
                daily_page = popup_info.value
                daily_url = daily_page.url
                
                print(f"     SUCCESS! Popup abierto: {daily_url}")
                
                # Esperar carga
                daily_page.wait_for_load_state("load")
                import time
                time.sleep(2)
                
                daily_page.close()
            else:
                print("     Boton no visible")
                browser.close()
                sys.exit(1)
                
        except Exception as e:
            print(f"     Error: {e}")
            import traceback
            traceback.print_exc()
            browser.close()
            sys.exit(1)

        browser.close()
    
    if not raw_html:
        print("\n❌ ERROR: No se pudo capturar el HTML")
        sys.exit(1)
    
    # Parsear el HTML
    print("\n" + "=" * 70)
    print("PARSEANDO STREAMS...")
    print("=" * 70)
    
    all_entries = parse_html_for_streams(raw_html, logos_db)
    
    print(f"\n✓ Total streams encontrados: {len(all_entries)}")
    
    if len(all_entries) < 5:
        print("❌ ERROR: Muy pocos streams encontrados")
        sys.exit(1)

    # Eliminar duplicados por URL
    dedup = {}
    for e in all_entries:
        dedup[e["url"]] = e
    all_entries = list(dedup.values())
    
    print(f"✓ Streams únicos: {len(all_entries)}")

    # Guardar el M3U
    write_m3u(all_entries, "lista.m3u")
    
    # Mostrar muestra
    print("\n" + "=" * 70)
    print("MUESTRA DE LOS PRIMEROS 10 CANALES:")
    print("=" * 70)
    for i, e in enumerate(all_entries[:10], 1):
        time_str = f"{e['time']} - " if e['time'] else ""
        logo_str = "✓" if e['logo'] else "✗"
        print(f"  {i}. [{logo_str}] {time_str}{e['match'][:40]} [{e['country']}] {e['channel']}")
    
    # Estadísticas de logos
    with_logo = sum(1 for e in all_entries if e['logo'])
    print(f"\n✓ Canales con logo: {with_logo}/{len(all_entries)} ({100*with_logo//len(all_entries)}%)")
    
    print("\n" + "=" * 70)
    print("✅ PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    main()

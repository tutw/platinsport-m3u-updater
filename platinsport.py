from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta
import os
import sys
import html
import urllib.request

BASE_URL = "https://www.platinsport.com/"
LOGOS_XML_URL = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/LOGOS-CANALES-TV.xml"

# Mapeo extendido de códigos de país a nombres
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
    "HU": "Hungría", "XX": "Internacional",
    "AU": "Australia", "NZ": "Nueva Zelanda",
    "JP": "Japón", "KR": "Corea del Sur", "CN": "China",
    "IN": "India", "PK": "Pakistán", "BD": "Bangladesh",
    "ZA": "Sudáfrica", "EG": "Egipto", "NG": "Nigeria",
    "KE": "Kenia", "MA": "Marruecos", "TN": "Túnez",
    "SA": "Arabia Saudita", "AE": "Emiratos Árabes", "QA": "Catar",
    "IL": "Israel", "IR": "Irán", "IQ": "Irak",
    "CL": "Chile", "CO": "Colombia", "PE": "Perú",
    "VE": "Venezuela", "UY": "Uruguay", "EC": "Ecuador",
    "BO": "Bolivia", "PY": "Paraguay",
    "IE": "Irlanda", "IS": "Islandia", "LT": "Lituania",
    "LV": "Letonia", "EE": "Estonia", "SI": "Eslovenia",
    "AL": "Albania", "MK": "Macedonia", "BA": "Bosnia",
    "ME": "Montenegro", "XK": "Kosovo", "CY": "Chipre",
    "MT": "Malta", "LU": "Luxemburgo"
}

def convert_utc_to_spain(utc_time_str: str) -> str:
    """
    Convierte hora UTC a hora de España (Europe/Madrid) respetando DST.
    """
    if not utc_time_str:
        return ""
    
    try:
        dt_utc = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        year = dt_utc.year
        
        # Calcular último domingo de marzo (cambio a verano)
        march_last = datetime(year, 3, 31, 1, 0, tzinfo=timezone.utc)
        while march_last.weekday() != 6:
            march_last -= timedelta(days=1)
        
        # Calcular último domingo de octubre (cambio a invierno)
        october_last = datetime(year, 10, 31, 1, 0, tzinfo=timezone.utc)
        while october_last.weekday() != 6:
            october_last -= timedelta(days=1)
        
        # Determinar el offset según la fecha
        if march_last <= dt_utc < october_last:
            spain_offset = timedelta(hours=2)  # CEST: UTC+2
        else:
            spain_offset = timedelta(hours=1)  # CET: UTC+1
        
        dt_spain = dt_utc + spain_offset
        return dt_spain.strftime("%H:%M")
        
    except Exception as e:
        print(f"⚠ Error convirtiendo hora: {e}")
        return ""

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

def generate_tvg_id(channel_name: str, lang_code: str) -> str:
    """Genera un tvg-id único basado en el nombre del canal y país"""
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', channel_name.replace(" ", ""))
    return f"{clean_name}.{lang_code}"

def extract_time_from_datetime(match_div) -> tuple:
    """
    Extrae la hora de la etiqueta <time>.
    Retorna: (hora_utc_str, hora_españa_str)
    """
    time_tag = match_div.find("time", class_="time")
    if time_tag and time_tag.get("datetime"):
        try:
            dt_str = time_tag.get("datetime")
            spain_time = convert_utc_to_spain(dt_str)
            return dt_str, spain_time
        except Exception as e:
            print(f"⚠ Error parseando tiempo: {e}")
    return "", ""

def extract_match_title(match_div) -> str:
    """Extrae el título del partido sin la hora"""
    match_div_copy = BeautifulSoup(str(match_div), "lxml").find("div")
    if not match_div_copy:
        return ""
    
    # Remover la etiqueta <time>
    for time_tag in match_div_copy.find_all("time"):
        time_tag.decompose()
    
    return clean_text(match_div_copy.get_text())

def clean_channel_name(raw_name: str) -> str:
    """Limpia el nombre del canal"""
    name = clean_text(raw_name)
    name = re.sub(r'\b(STREAM|4K|FHD|UHD)\b', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    
    if not name:
        name = clean_text(raw_name)
    
    return name

def parse_html_for_streams(html_content: str):
    """
    Parsea el HTML y extrae streams con información de liga.
    IMPORTANTE: NO elimina duplicados de acestream
    """
    soup = BeautifulSoup(html_content, "lxml")
    entries = []
    
    # Buscar todas las etiquetas <p> y <div> en orden
    all_elements = soup.find_all(["p", "div"])
    
    current_league = "Unknown League"
    
    print(f"\n✓ Procesando elementos del HTML...")
    
    for elem in all_elements:
        # Detectar encabezados de liga
        if elem.name == "p":
            text = elem.get_text().strip()
            # Verificar si es un encabezado de liga
            if text and any(keyword in text.lower() for keyword in [
                'league', 'liga', 'serie', 'bundesliga', 'ligue', 
                'eredivisie', 'championship', 'cup', 'portugal', 'primeira',
                'super league', 'pro league', 'paulista', 'carioca', 'profesional'
            ]):
                current_league = text
                print(f"\n📋 Liga detectada: {current_league}")
        
        # Detectar partidos
        elif elem.name == "div" and "match-title-bar" in elem.get("class", []):
            dt_utc_str, event_time = extract_time_from_datetime(elem)
            match_title = extract_match_title(elem)
            
            button_group = elem.find_next_sibling("div", class_="button-group")
            if not button_group:
                continue
            
            links = button_group.find_all("a", href=re.compile(r"^acestream://"))
            
            print(f"  ⚽ {match_title} ({current_league}) - {len(links)} streams")
            
            for a in links:
                href = clean_text(a.get("href", ""))
                if not href.startswith("acestream://"):
                    continue
                
                lang_code = extract_lang_from_flag(a)
                country_name = COUNTRY_CODES.get(lang_code, lang_code)
                
                a_copy = BeautifulSoup(str(a), "lxml").find("a")
                if not a_copy:
                    continue
                
                # Eliminar banderas
                for flag in a_copy.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
                    flag.decompose()
                
                channel_name_raw = clean_text(a_copy.get_text())
                
                if not channel_name_raw or channel_name_raw in ["", "STREAM HD", "HD", "STREAM"]:
                    channel_name_raw = clean_text(a.get("title", ""))
                    if not channel_name_raw or channel_name_raw in ["", "STREAM HD"]:
                        channel_name_raw = f"Stream {lang_code}"
                
                channel_name = clean_channel_name(channel_name_raw)
                
                # Generar tvg-id único
                tvg_id = generate_tvg_id(channel_name, lang_code)
                
                entries.append({
                    "time": event_time,
                    "match": match_title,
                    "league": current_league,
                    "lang_code": lang_code,
                    "country": country_name,
                    "channel": channel_name,
                    "url": href,
                    "tvg_id": tvg_id,
                })
    
    return entries

def write_m3u(all_entries, out_path="lista.m3u"):
    """
    Escribe el archivo M3U con formato:
    HH:MM | Liga | Evento | Canal | [País]
    """
    m3u = ["#EXTM3U"]
    
    GROUP_NAME = "AGENDA PLATINSPORT"
    
    for idx, e in enumerate(all_entries, 1):
        event_time = e.get("time", "")
        match = e.get("match", "Evento")
        league = e.get("league", "")
        country = e.get("country", "")
        channel = e.get("channel", "STREAM")
        url = e.get("url", "")
        tvg_id = e.get("tvg_id", "")
        lang_code = e.get("lang_code", "")
        
        tvg_name = channel
        
        # Construir nombre de visualización: HH:MM | Liga | Evento | Canal | [País]
        display_name_parts = []
        if event_time:
            display_name_parts.append(event_time)
        if league:
            display_name_parts.append(league)
        if match:
            display_name_parts.append(match)
        display_name_parts.append(channel)
        if country and country != "Internacional":
            display_name_parts.append(f"[{country}]")
        
        display_name = " | ".join(display_name_parts)
        
        # Construir línea EXTINF
        extinf_parts = ['#EXTINF:-1']
        
        if tvg_id:
            extinf_parts.append(f'tvg-id="{tvg_id}"')
        
        extinf_parts.append(f'tvg-name="{tvg_name}"')
        extinf_parts.append(f'group-title="{GROUP_NAME}"')
        
        if lang_code and lang_code != "XX":
            extinf_parts.append(f'tvg-country="{lang_code}"')
        
        extinf_line = ' '.join(extinf_parts) + f',{display_name}'
        
        m3u.append(extinf_line)
        
        # Convertir acestream:// a formato localhost
        if url.startswith("acestream://"):
            ace_id = url.replace("acestream://", "")
            stream_url = f"http://127.0.0.1:6878/ace/getstream?id={ace_id}"
        else:
            stream_url = url
        
        m3u.append(stream_url)
    
    # Escribir archivo
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")
    
    print(f"\n✓ Archivo {out_path} generado con {len(all_entries)} entradas")
    print(f"✓ Todos los eventos agrupados en: {GROUP_NAME}")
    print(f"✓ Formato: HORA | LIGA | EVENTO | CANAL | [PAÍS]")

def main():
    print("=" * 70)
    print("=== PLATINSPORT M3U UPDATER - VERSIÓN CORREGIDA ===")
    print("=== CON DETECCIÓN DE LIGAS Y SIN ELIMINAR DUPLICADOS ===")
    print("=" * 70)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Inicio: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    os.makedirs("debug", exist_ok=True)

    raw_html = None

    with sync_playwright() as p:
        print("\n[1] Lanzando navegador...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
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

        def handle_route(route, request):
            nonlocal raw_html
            
            if "source-list.php" in request.url:
                print(f"[4] Interceptando: {request.url}")
                
                response = route.fetch()
                body = response.text()
                
                raw_html = body
                print(f"[5] HTML capturado: {len(body)} bytes")
                
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
                
                daily_page.wait_for_load_state("load")
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
    
    print("\n" + "=" * 70)
    print("PARSEANDO STREAMS CON DETECCIÓN DE LIGAS...")
    print("=" * 70)
    
    all_entries = parse_html_for_streams(raw_html)
    
    print(f"\n✓ Total streams encontrados: {len(all_entries)}")
    
    if len(all_entries) < 5:
        print("❌ ERROR: Muy pocos streams encontrados")
        sys.exit(1)

    # NO eliminamos duplicados - el usuario lo pidió expresamente
    print(f"✓ Conservando TODOS los streams (sin eliminar duplicados)")

    # Guardar el M3U
    write_m3u(all_entries, "lista.m3u")
    
    # Mostrar muestra
    print("\n" + "=" * 70)
    print("MUESTRA DE LOS PRIMEROS 10 CANALES:")
    print("=" * 70)
    for i, e in enumerate(all_entries[:10], 1):
        time_str = f"{e['time']}" if e['time'] else "??:??"
        print(f"  {i}. {time_str} | {e['league'][:30]} | {e['match'][:30]} | {e['channel']} [{e['country']}]")
    
    # Estadísticas por liga
    league_counts = {}
    for e in all_entries:
        league = e.get('league', 'Unknown')
        if league not in league_counts:
            league_counts[league] = 0
        league_counts[league] += 1
    
    print(f"\n📊 Estadísticas por liga:")
    for league, count in sorted(league_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {league}: {count} enlaces")
    
    print("\n" + "=" * 70)
    print("✅ PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    main()

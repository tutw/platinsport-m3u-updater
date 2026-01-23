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
import hashlib

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

# Base de aliases de canales (se expandirá con el XML)
CHANNEL_ALIASES = {
    "movistar laliga": ["m. laliga", "m laliga", "movistar+ laliga", "laliga tv", "m+laliga"],
    "movistar liga de campeones": ["m. liga de campeones", "m liga de campeones", "movistar+ champions"],
    "movistar deportes": ["m+deportes", "m+ deportes", "movistar+ deportes", "m.deportes", "m deportes"],
    "movistar vamos": ["m+ vamos", "m+vamos", "vamos", "m. vamos"],
    "dazn laliga": ["dazn la liga"],
    "eleven sports": ["eleven", "11 sports"],
    "bein sports": ["bein", "beinsports"],
    "sky sports": ["sky sport"],
    "ziggo sport": ["ziggo"],
    "sport tv": ["sporttv"],
    "espn": ["espn deportes"],
    "fox sports": ["fox sport"],
    "setanta sports": ["setanta"],
    "premier sports": ["premier sport"],
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

def normalize_channel_name(channel_name: str) -> str:
    """Normaliza el nombre del canal para mejorar el matching"""
    normalized = channel_name.lower().strip()
    # Remover puntos, guiones y caracteres especiales comunes
    normalized = re.sub(r'[.\-_+:()]', ' ', normalized)
    # Remover palabras comunes que no aportan al matching
    normalized = re.sub(r'\b(hd|4k|fhd|uhd|stream|tv|channel|canal|live)\b', '', normalized)
    # Normalizar espacios
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def similarity(a: str, b: str) -> float:
    """Calcula la similitud entre dos strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def generate_tvg_id(channel_name: str, lang_code: str) -> str:
    """Genera un tvg-id único basado en el nombre del canal y país"""
    # Crear un ID consistente y único
    base = f"{channel_name}_{lang_code}"
    # Generar hash corto para evitar conflictos
    hash_short = hashlib.md5(base.encode()).hexdigest()[:8]
    # Formato: ChannelName.CountryCode.hash
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', channel_name.replace(" ", ""))
    return f"{clean_name}.{lang_code}.{hash_short}"

def load_logos_from_xml(xml_path: str = "logos.xml") -> tuple:
    """Carga el mapeo de canales a logos desde el XML y construye aliases extendidos"""
    logos = {}
    all_channel_names = set()
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        for channel in root.findall(".//channel"):
            name = channel.get("name", "").strip()
            logo_node = channel.find("logo_url")
            if name and logo_node is not None and logo_node.text:
                logo_url = logo_node.text.strip()
                
                # Guardar con nombre original
                all_channel_names.add(name)
                logos[name.lower().strip()] = {
                    "original_name": name,
                    "logo_url": logo_url
                }
                
                # Guardar con nombre normalizado
                normalized = normalize_channel_name(name)
                if normalized and normalized not in logos:
                    logos[normalized] = {
                        "original_name": name,
                        "logo_url": logo_url
                    }
        
        print(f"✓ Cargados {len(all_channel_names)} canales únicos del XML")
        print(f"✓ Creadas {len(logos)} entradas de búsqueda (incluyendo normalizadas)")
        
        return logos, all_channel_names
    except Exception as e:
        print(f"⚠ Error cargando logos XML: {e}")
        return {}, set()

def build_channel_aliases(all_channel_names: set) -> dict:
    """Construye aliases automáticamente basándose en los nombres de canales del XML"""
    aliases = CHANNEL_ALIASES.copy()
    
    # Patterns comunes para generar aliases
    patterns = [
        (r'^(.*?)\s*\d+$', lambda m: m.group(1).strip()),  # "ESPN 2" -> "ESPN"
        (r'^(.*?)\s+hd$', lambda m: m.group(1).strip()),    # "Sky HD" -> "Sky"
        (r'^(.*?)\s+tv$', lambda m: m.group(1).strip()),    # "Sport TV" -> "Sport"
    ]
    
    for channel in all_channel_names:
        channel_lower = channel.lower().strip()
        normalized = normalize_channel_name(channel)
        
        # Crear aliases basados en patterns
        for pattern, extractor in patterns:
            match = re.match(pattern, channel_lower, re.IGNORECASE)
            if match:
                base = extractor(match)
                if base and len(base) > 2:  # Evitar aliases muy cortos
                    if base not in aliases:
                        aliases[base] = []
                    if channel_lower not in aliases[base]:
                        aliases[base].append(channel_lower)
    
    total_aliases = sum(len(v) for v in aliases.values())
    print(f"✓ Total de aliases configurados: {len(aliases)} grupos con {total_aliases} variantes")
    
    return aliases

def find_best_logo_match(channel_name: str, logos_db: dict, aliases: dict, threshold: float = 0.6) -> str:
    """Encuentra el mejor match de logo para un nombre de canal con lógica mejorada"""
    if not channel_name or not logos_db:
        return ""
    
    channel_normalized = normalize_channel_name(channel_name)
    channel_lower = channel_name.lower().strip()
    
    # 1. Búsqueda exacta con nombre original
    if channel_lower in logos_db:
        return logos_db[channel_lower]["logo_url"]
    
    # 2. Búsqueda exacta con nombre normalizado
    if channel_normalized in logos_db:
        return logos_db[channel_normalized]["logo_url"]
    
    # 3. Búsqueda por aliases (tanto canonical como variantes)
    for canonical, alias_list in aliases.items():
        canonical_norm = normalize_channel_name(canonical)
        
        # Verificar si el canal coincide con el canonical
        if channel_normalized == canonical_norm or channel_lower == canonical:
            # Buscar logo del canonical
            if canonical in logos_db:
                return logos_db[canonical]["logo_url"]
            if canonical_norm in logos_db:
                return logos_db[canonical_norm]["logo_url"]
        
        # Verificar si el canal coincide con algún alias
        for alias in alias_list:
            alias_norm = normalize_channel_name(alias)
            if channel_normalized == alias_norm or channel_lower == alias:
                # Buscar logo del canonical o del alias
                if canonical in logos_db:
                    return logos_db[canonical]["logo_url"]
                if alias in logos_db:
                    return logos_db[alias]["logo_url"]
                if alias_norm in logos_db:
                    return logos_db[alias_norm]["logo_url"]
    
    # 4. Búsqueda por substring (contiene)
    for db_name, data in logos_db.items():
        if len(db_name) > 3:  # Evitar matches con nombres muy cortos
            if channel_normalized in db_name or db_name in channel_normalized:
                return data["logo_url"]
    
    # 5. Búsqueda por similitud usando SequenceMatcher
    best_match = None
    best_score = threshold
    
    for db_name, data in logos_db.items():
        if len(db_name) > 2:  # Evitar comparar con nombres muy cortos
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
            dt_str = time_tag.get("datetime")
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except Exception as e:
            print(f"⚠ Error parseando tiempo: {e}")
    return ""

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
    """Limpia y mejora el nombre del canal"""
    name = clean_text(raw_name)
    
    # Remover patrones comunes no deseados
    name = re.sub(r'\b(STREAM|4K|FHD|UHD)\b', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    
    if not name:
        name = clean_text(raw_name)
    
    return name

def parse_html_for_streams(html_content: str, logos_db: dict, aliases: dict):
    """Parsea el HTML y extrae informacion de streams con horarios y logos mejorados"""
    soup = BeautifulSoup(html_content, "lxml")
    entries = []
    
    match_sections = soup.find_all("div", class_="match-title-bar")
    
    print(f"\n✓ Encontradas {len(match_sections)} secciones de partidos")
    
    for idx, match_div in enumerate(match_sections, 1):
        event_time = extract_time_from_datetime(match_div)
        match_title = extract_match_title(match_div)
        
        button_group = match_div.find_next_sibling("div", class_="button-group")
        if not button_group:
            continue
        
        links = button_group.find_all("a", href=re.compile(r"^acestream://"))
        
        print(f"  Partido {idx}: '{match_title}' a las {event_time} - {len(links)} streams")
        
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
            
            # Buscar logo con lógica mejorada
            logo_url = find_best_logo_match(channel_name, logos_db, aliases)
            
            # Generar tvg-id único
            tvg_id = generate_tvg_id(channel_name, lang_code)
            
            entries.append({
                "time": event_time,
                "match": match_title,
                "lang_code": lang_code,
                "country": country_name,
                "channel": channel_name,
                "logo": logo_url,
                "url": href,
                "tvg_id": tvg_id,
            })
    
    return entries

def write_m3u(all_entries, out_path="lista.m3u"):
    """Escribe el archivo M3U en formato compatible con OTT Navigator y otros reproductores IPTV"""
    m3u = ["#EXTM3U"]
    
    # Agrupar por categorías (eventos deportivos)
    for idx, e in enumerate(all_entries, 1):
        event_time = e.get("time", "")
        match = e.get("match", "Evento")
        country = e.get("country", "")
        channel = e.get("channel", "STREAM")
        logo = e.get("logo", "")
        url = e.get("url", "")
        tvg_id = e.get("tvg_id", "")
        
        # Construir grupo basado en el evento
        group_title = match if match else "Eventos Deportivos"
        
        # Construir tvg-name (nombre completo del canal con contexto)
        tvg_name = f"{channel}"
        if country and country != "Internacional":
            tvg_name += f" ({country})"
        
        # Construir nombre de visualización para el canal
        # Formato: HH:MM Canal [País]
        parts = []
        if event_time:
            parts.append(event_time)
        parts.append(channel)
        if country:
            parts.append(f"[{country}]")
        
        display_name = " ".join(parts)
        
        # Construir línea EXTINF con todos los atributos necesarios para IPTV
        extinf_parts = ['#EXTINF:-1']
        
        # Agregar tvg-id (identificador único)
        if tvg_id:
            extinf_parts.append(f'tvg-id="{tvg_id}"')
        
        # Agregar tvg-name (nombre del canal para EPG)
        extinf_parts.append(f'tvg-name="{tvg_name}"')
        
        # Agregar tvg-logo (URL del logo)
        if logo:
            extinf_parts.append(f'tvg-logo="{logo}"')
        
        # Agregar group-title (categoría/grupo)
        extinf_parts.append(f'group-title="{group_title}"')
        
        # Número de canal secuencial
        extinf_parts.append(f'tvg-chno="{idx}"')
        
        # Nombre de visualización al final
        extinf_line = ' '.join(extinf_parts) + f',{display_name}'
        
        m3u.append(extinf_line)
        
        # Convertir acestream:// a formato localhost
        if url.startswith("acestream://"):
            ace_id = url.replace("acestream://", "")
            stream_url = f"http://127.0.0.1:6878/ace/getstream?id={ace_id}"
        else:
            stream_url = url
        
        m3u.append(stream_url)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")
    
    print(f"\n✓ Archivo {out_path} generado con {len(all_entries)} entradas")

def download_logos_xml():
    """Descarga el archivo XML de logos si no existe"""
    if os.path.exists("logos.xml"):
        print("✓ Archivo logos.xml ya existe")
        return True
    
    try:
        print(f"Descargando logos desde {LOGOS_XML_URL}...")
        urllib.request.urlretrieve(LOGOS_XML_URL, "logos.xml")
        print("✓ Archivo logos.xml descargado")
        return True
    except Exception as e:
        print(f"⚠ Error descargando logos.xml: {e}")
        return False

def main():
    print("=" * 70)
    print("=== PLATINSPORT M3U UPDATER - VERSION MEJORADA V3 ===")
    print("=" * 70)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Inicio: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    os.makedirs("debug", exist_ok=True)

    # Descargar y cargar logos
    download_logos_xml()
    logos_db, all_channel_names = load_logos_from_xml("logos.xml")
    
    # Construir aliases extendidos
    aliases = build_channel_aliases(all_channel_names)

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
    
    print("\n" + "=" * 70)
    print("PARSEANDO STREAMS...")
    print("=" * 70)
    
    all_entries = parse_html_for_streams(raw_html, logos_db, aliases)
    
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
        time_str = f"{e['time']} " if e['time'] else ""
        logo_str = "✓" if e['logo'] else "✗"
        print(f"  {i}. [{logo_str}] {time_str}{e['match'][:40]} | {e['channel']} [{e['country']}]")
    
    # Estadísticas de logos
    with_logo = sum(1 for e in all_entries if e['logo'])
    logo_percentage = (100 * with_logo // len(all_entries)) if all_entries else 0
    print(f"\n✓ Canales con logo: {with_logo}/{len(all_entries)} ({logo_percentage}%)")
    
    print("\n" + "=" * 70)
    print("✅ PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    main()

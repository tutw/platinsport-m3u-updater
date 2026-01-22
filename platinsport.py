from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import base64
import time
import os
import html
import sys

URL = "https://www.platinsport.com/"

print("=" * 70)
print("=== PLATINSPORT M3U UPDATER ===")
print("=" * 70)
print(f"🐍 Python version: {sys.version.split()[0]}")
print(f"📁 Working directory: {os.getcwd()}")
print(f"🕐 Start time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)
print()

os.makedirs("debug", exist_ok=True)
all_streams = []

def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def extract_lang_from_flag(link_tag) -> str:
    """Extraer idioma de las clases de banderas"""
    flag_span = link_tag.find("span", class_=re.compile(r"\bfi\b|\bfi-"))
    lang = "XX"
    if flag_span:
        classes = flag_span.get("class", []) or []
        for cls in classes:
            if cls.startswith("fi-") and len(cls) == 5:
                lang = cls.replace("fi-", "").upper()
                break
    return lang

def try_extract_channel_name(link_tag) -> str:
    """Extraer nombre del canal con métodos mejorados"""
    
    # Método 1: Buscar en atributos del enlace
    for attr in ["title", "aria-label", "data-title", "data-channel", "data-name"]:
        value = clean_text(link_tag.get(attr, ""))
        if value:
            # Limpiar prefijos de idioma (ej: "GB Stream Name")
            value = re.sub(r"^[A-Z]{2}\s+", "", value).strip()
            if value and value.upper() not in {"STREAM", "HD", "LINK", "WATCH", "VER", "PLAY", "LIVE", "CHANNEL", "TV"}:
                return value
    
    # Método 2: Buscar texto visible dentro del enlace
    link_copy = link_tag
    
    # Remover span de bandera
    for flag in link_copy.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
        flag.decompose()
    
    # Obtener texto limpio
    full_text = clean_text(link_copy.get_text(" ", strip=True))
    full_text = re.sub(r"^[A-Z]{2}\s+", "", full_text).strip()
    
    # Verificar si es un nombre válido
    if full_text and full_text.upper() not in {"STREAM", "HD", "LINK", "WATCH", "VER", "PLAY", "LIVE", "CHANNEL", "TV", ""}:
        return full_text
    
    # Método 3: Buscar en elementos hermanos o padres
    parent = link_tag.parent
    if parent:
        # Buscar spans con clases específicas de canales
        channel_spans = parent.find_all("span", class_=re.compile(r"channel|name|title"))
        for span in channel_spans:
            text = clean_text(span.get_text(strip=True))
            if text and len(text) > 2:
                return text
    
    # Método 4: Buscar en el href del enlace (algunos sitios incluyen el nombre)
    href = link_tag.get("href", "")
    if "channel=" in href:
        match = re.search(r"channel=([^&]+)", href)
        if match:
            channel = match.group(1).replace("+", " ").replace("%20", " ")
            return clean_text(channel)
    
    return ""

def dump_debug_popup(popup_html: str, event_name: str, event_count: int, lang: str, ace_url: str, link_html: str):
    """Guardar HTML para debugging"""
    safe_event = re.sub(r"[^a-zA-Z0-9_-]+", "_", event_name)[:60] or "evento"
    fname = f"debug/popup_{safe_event}_{event_count}_{lang}.html"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write("<!-- POPUP HTML -->\n")
            f.write(popup_html)
            f.write("\n\n<!-- LINK HTML -->\n")
            f.write(str(link_html))
        
        with open("debug/debug_missing_channels.txt", "a", encoding="utf-8") as lf:
            lf.write(f"{event_name} | {lang} | {ace_url} | {fname}\n")
        
        print(f"      ⚠️  Debug guardado: {fname}")
    except Exception as e:
        print(f"      ✗ Error guardando debug: {e}")

# SCRAPER PRINCIPAL
try:
    with sync_playwright() as p:
        print("🌐 Iniciando navegador Chromium...")
        
        try:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions'
                ]
            )
        except Exception as e:
            print(f"✗ Error al lanzar el navegador: {e}")
            print("💡 Asegúrate de haber ejecutado: playwright install chromium")
            sys.exit(1)
        
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={'width': 1920, 'height': 1080},
            locale='es-ES'
        )

        context.add_cookies([{
            "name": "disclaimer_accepted",
            "value": "true",
            "domain": ".platinsport.com",
            "path": "/",
            "sameSite": "Lax"
        }])

        page = context.new_page()
        print("✅ Navegador iniciado correctamente")
        print(f"🔗 Cargando página: {URL}")
        
        try:
            page.goto(URL, timeout=90000, wait_until="domcontentloaded")
            time.sleep(3)
            print("✅ Página cargada correctamente\n")
        except Exception as e:
            print(f"✗ Error al cargar la página: {e}")
            browser.close()
            sys.exit(1)

        main_html = page.content()
        soup = BeautifulSoup(main_html, "lxml")

        print("🔍 Analizando estructura de eventos...\n")

        category_divs = soup.find_all("div", style=re.compile(r"background:#000.*color:#ffae00"))
        print(f"✅ Encontradas {len(category_divs)} categorías\n")

        if len(category_divs) == 0:
            print("⚠️  No se encontraron categorías. El sitio puede haber cambiado su estructura.")
            print("💾 Guardando HTML para debug...")
            with open("debug/main_page.html", "w", encoding="utf-8") as f:
                f.write(main_html)
            print("✅ HTML guardado en debug/main_page.html")

        for cat_index, cat_div in enumerate(category_divs, 1):
            category = clean_text(cat_div.get_text(strip=True))
            category = re.sub(r"^[–\-]\s*", "", category)

            print(f"📁 Categoría [{cat_index}/{len(category_divs)}]: {category}")

            current = cat_div.find_next_sibling()
            event_count = 0

            def is_category_div(tag):
                return (
                    tag
                    and tag.name == "div"
                    and tag.get("style")
                    and "background:#000" in tag.get("style", "")
                    and "color:#ffae00" in tag.get("style", "")
                )

            while current and not is_category_div(current):
                play_links = current.find_all("a", href=re.compile(r"javascript:go"))
                
                for play_link in play_links:
                    event_count += 1

                    event_div = play_link.find_parent("div", style=re.compile(r"background: #0a0a0a|border: 1px solid #333"))
                    if not event_div:
                        event_div = play_link.find_parent("div")

                    time_elem = event_div.find("time") if event_div else None
                    event_time = clean_text(time_elem.get_text(strip=True)) if time_elem else ""

                    team_spans = event_div.find_all("span", style=re.compile(r"font-size: 12px; color: #fff")) if event_div else []
                    teams = [clean_text(span.get_text(strip=True)) for span in team_spans if clean_text(span.get_text(strip=True))]

                    if len(teams) >= 2:
                        event_name = f"{teams[0]} vs {teams[1]}"
                    elif len(teams) == 1:
                        event_name = teams[0]
                    else:
                        event_name = f"Evento {event_count}"

                    print(f"  ⚽ {event_name}", end="")
                    if event_time:
                        print(f" - {event_time}")
                    else:
                        print()

                    href = play_link.get("href", "")
                    match = re.search(r"go\('([^']+)'\)", href)
                    if not match:
                        print("    ✗ No se pudo extraer el archivo PHP")
                        continue

                    php_file = match.group(1)

                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    key = base64.b64encode((today + "PLATINSPORT").encode()).decode()
                    popup_url = f"https://www.platinsport.com/link/{php_file}?key={key}"

                    popup_page = context.new_page()
                    
                    try:
                        # NO bloquear JavaScript - necesitamos ver el contenido renderizado
                        popup_page.goto(popup_url, timeout=45000, referer=URL, wait_until="networkidle")
                        time.sleep(1)  # Esperar renderizado

                        popup_html = popup_page.content()
                        popup_soup = BeautifulSoup(popup_html, "lxml")

                        ace_links = popup_soup.find_all("a", href=re.compile(r"^acestream://"))
                        
                        if len(ace_links) == 0:
                            print("    ⚠️  No se encontraron streams acestream")
                        else:
                            print(f"    ✅ {len(ace_links)} stream{'s' if len(ace_links) != 1 else ''} encontrado{'s' if len(ace_links) != 1 else ''}")

                        for link in ace_links:
                            ace_url = link.get("href", "").strip()
                            if not ace_url.startswith("acestream://"):
                                continue

                            lang = extract_lang_from_flag(link)
                            channel = try_extract_channel_name(link)

                            if not channel:
                                # Método alternativo: usar el texto del enlace directamente
                                link_text = clean_text(link.get_text(strip=True))
                                if link_text and len(link_text) > 2:
                                    channel = link_text
                                else:
                                    channel = f"{lang}_STREAM_{event_count}"
                                    dump_debug_popup(popup_html, event_name, event_count, lang, ace_url, str(link))

                            all_streams.append({
                                "event": event_name,
                                "category": category,
                                "time": event_time,
                                "channel": channel,
                                "url": ace_url,
                                "lang": lang
                            })
                            
                            print(f"      🌍 [{lang}] {channel}")

                    except Exception as e:
                        error_msg = str(e)[:100]
                        print(f"    ✗ Error al abrir popup: {error_msg}")
                    finally:
                        try:
                            popup_page.close()
                        except Exception:
                            pass

                    time.sleep(0.5)  # Mayor espera entre popups

                current = current.find_next_sibling()

            print()

        try:
            page.close()
        except Exception:
            pass
        
        browser.close()
        print("✅ Navegador cerrado correctamente\n")

except Exception as e:
    print(f"\n❌ ERROR FATAL: {e}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# GENERACIÓN DEL ARCHIVO M3U
print("=" * 70)
print("📝 Generando archivo lista.m3u...")
print("=" * 70)

if len(all_streams) == 0:
    print("⚠️  ADVERTENCIA: No se encontraron streams. El archivo M3U estará vacío.")
    print("⚠️  Esto puede indicar que el sitio web ha cambiado su estructura.")

m3u_lines = ["#EXTM3U"]

for stream in all_streams:
    event_info = stream["event"]
    if stream["time"]:
        event_info = f"{event_info} - {stream['time']}"

    tvg_name = f"{event_info} - [{stream['lang']}] {stream['channel']}"
    group_title = stream["category"]

    m3u_lines.append(
        f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{group_title}",{stream["channel"]}'
    )
    m3u_lines.append(stream["url"])

try:
    with open("lista.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")
    print("✅ Archivo lista.m3u generado correctamente")
except Exception as e:
    print(f"❌ Error al escribir lista.m3u: {e}")
    sys.exit(1)

# ESTADÍSTICAS FINALES
print("\n" + "=" * 70)
print("📊 ESTADÍSTICAS FINALES")
print("=" * 70)

print(f"✅ Total de streams: {len(all_streams)}")

if len(all_streams) > 0:
    categories = set(s['category'] for s in all_streams)
    events = set(s['event'] for s in all_streams)
    
    print(f"✅ Categorías únicas: {len(categories)}")
    for cat in sorted(categories):
        count = sum(1 for s in all_streams if s['category'] == cat)
        print(f"   - {cat}: {count} streams")
    
    print(f"✅ Eventos únicos: {len(events)}")

    missing = sum(1 for s in all_streams if "STREAM_" in s["channel"] or s["channel"] == "UNKNOWN_CHANNEL")
    if missing > 0:
        print(f"⚠️  Streams sin canal identificado: {missing}")
        print(f"   📁 Revisar carpeta debug/ para más detalles")
    else:
        print(f"✅ Todos los streams tienen canal identificado")

    langs = {}
    for s in all_streams:
        langs[s['lang']] = langs.get(s['lang'], 0) + 1
    
    print(f"✅ Idiomas detectados: {len(langs)}")
    for lang, count in sorted(langs.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {lang}: {count} streams")

    channels = {}
    for s in all_streams:
        if "STREAM_" not in s['channel'] and s['channel'] != "UNKNOWN_CHANNEL":
            channels[s['channel']] = channels.get(s['channel'], 0) + 1
    
    if channels:
        print(f"✅ Top 10 canales más frecuentes:")
        top_channels = sorted(channels.items(), key=lambda x: x[1], reverse=True)[:10]
        for idx, (channel, count) in enumerate(top_channels, 1):
            print(f"   {idx:2d}. {channel}: {count} streams")

print("\n" + "=" * 70)
print(f"🕐 Tiempo de finalización: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("✅ PROCESO COMPLETADO EXITOSAMENTE")
print("=" * 70)

sys.exit(0)

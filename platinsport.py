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
print(f"\U0001f40d Python version: {sys.version.split()[0]}")
print(f"\U0001f4c1 Working directory: {os.getcwd()}")
print(f"\U0001f550 Start time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)
print()

os.makedirs("debug", exist_ok=True)
all_streams = []

BAD_NAMES = {
    "", "STREAM", "STREAM HD", "HD", "LINK", "WATCH", "VER", "PLAY", "LIVE", "CHANNEL", "TV"
}

def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_bad_channel_name(name: str) -> bool:
    if not name:
        return True
    n = clean_text(name)
    if not n:
        return True
    up = n.upper()
    # Exactos típicos que aparecen como texto del enlace
    if up in BAD_NAMES:
        return True
    # Cosas demasiado genéricas
    if up in {"STREAM", "STREAMS"}:
        return True
    # Evita casos tipo "HD" o similares
    if len(n) <= 2:
        return True
    return False

def normalize_candidate(name: str) -> str:
    name = clean_text(name)
    # Quitar prefijos tipo "GB " si vienen pegados
    name = re.sub(r"^[A-Z]{2}\s+", "", name).strip()
    return name

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

def iter_text_candidates_near_link(link_tag):
    """
    Generador de candidatos cerca del enlace:
    - textos de hijos (span/b) que no sean la bandera
    - hermanos inmediatos
    - contenedor padre (sin tragarse todo)
    """
    # 1) Hijos directos del link (span, strong, b)
    for child in link_tag.find_all(["span", "strong", "b"], recursive=True):
        # ignora spans de bandera
        cls = " ".join(child.get("class", []) or [])
        if re.search(r"\bfi\b|\bfi-", cls):
            continue
        t = normalize_candidate(child.get_text(" ", strip=True))
        if t:
            yield t

    # 2) Texto del link sin la bandera (sin mutar el DOM original)
    try:
        link_html = str(link_tag)
        tmp = BeautifulSoup(link_html, "lxml")
        a = tmp.find("a") or tmp
        for flag in a.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
            flag.decompose()
        t = normalize_candidate(a.get_text(" ", strip=True))
        if t:
            yield t
    except Exception:
        pass

    # 3) Hermanos cercanos
    for sib in list(link_tag.next_siblings)[:6]:
        if getattr(sib, "get_text", None):
            t = normalize_candidate(sib.get_text(" ", strip=True))
            if t:
                yield t
        elif isinstance(sib, str):
            t = normalize_candidate(sib)
            if t:
                yield t

    # 4) Padre: buscar elementos con pistas
    parent = link_tag.parent
    if parent:
        # spans/divs típicos
        for node in parent.find_all(["span", "div", "p"], recursive=True):
            cls = " ".join(node.get("class", []) or [])
            if re.search(r"(channel|name|title|label)", cls, re.I):
                t = normalize_candidate(node.get_text(" ", strip=True))
                if t:
                    yield t

def try_extract_channel_name(link_tag) -> str:
    """Extraer nombre del canal de forma robusta"""
    # A) Atributos primero
    for attr in ["data-name", "data-channel", "data-title", "title", "aria-label"]:
        value = normalize_candidate(link_tag.get(attr, "") or "")
        if value and not is_bad_channel_name(value):
            return value

    # B) Buscar en href si hay parámetros con nombre
    href = link_tag.get("href", "") or ""
    for key in ["channel", "name", "title"]:
        if f"{key}=" in href:
            m = re.search(rf"{key}=([^&]+)", href)
            if m:
                cand = normalize_candidate(m.group(1).replace("+", " ").replace("%20", " "))
                if cand and not is_bad_channel_name(cand):
                    return cand

    # C) Candidatos cerca del link (hijos / hermanos / parent)
    for cand in iter_text_candidates_near_link(link_tag):
        if cand and not is_bad_channel_name(cand):
            return cand

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
        print("\U0001f310 Iniciando navegador Chromium...")

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
            print("\U0001f4a1 Asegúrate de haber ejecutado: playwright install chromium")
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
        print(f"\U0001f517 Cargando página: {URL}")

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

        print("\U0001f50d Analizando estructura de eventos...\n")

        category_divs = soup.find_all("div", style=re.compile(r"background:#000.*color:#ffae00"))
        print(f"✅ Encontradas {len(category_divs)} categorías\n")

        if len(category_divs) == 0:
            print("⚠️  No se encontraron categorías. El sitio puede haber cambiado su estructura.")
            print("\U0001f4be Guardando HTML para debug...")
            with open("debug/main_page.html", "w", encoding="utf-8") as f:
                f.write(main_html)
            print("✅ HTML guardado en debug/main_page.html")

        for cat_index, cat_div in enumerate(category_divs, 1):
            category = clean_text(cat_div.get_text(strip=True))
            category = re.sub(r"^[–\-]\s*", "", category)

            print(f"\U0001f4c1 Categoría [{cat_index}/{len(category_divs)}]: {category}")

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
                        popup_page.goto(popup_url, timeout=45000, referer=URL, wait_until="networkidle")
                        time.sleep(1)

                        popup_html = popup_page.content()
                        popup_soup = BeautifulSoup(popup_html, "lxml")

                        ace_links = popup_soup.find_all("a", href=re.compile(r"^acestream://"))

                        if len(ace_links) == 0:
                            print("    ⚠️  No se encontraron streams acestream")
                        else:
                            print(f"    ✅ {len(ace_links)} stream{'s' if len(ace_links) != 1 else ''} encontrado{'s' if len(ace_links) != 1 else ''}")

                        for link in ace_links:
                            ace_url = (link.get("href", "") or "").strip()
                            if not ace_url.startswith("acestream://"):
                                continue

                            lang = extract_lang_from_flag(link)
                            channel = try_extract_channel_name(link)
                            channel = normalize_candidate(channel)

                            if is_bad_channel_name(channel):
                                # Último fallback, pero NO usar STREAM HD
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

                            print(f"      \U0001f30d [{lang}] {channel}")

                    except Exception as e:
                        error_msg = str(e)[:120]
                        print(f"    ✗ Error al abrir popup: {error_msg}")
                    finally:
                        try:
                            popup_page.close()
                        except Exception:
                            pass

                    time.sleep(0.5)

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
print("\U0001f4dd Generando archivo lista.m3u...")
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
print("\U0001f4ca ESTADÍSTICAS FINALES")
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

    missing = sum(1 for s in all_streams if re.search(r"_STREAM_\d+$", s["channel"]))
    if missing > 0:
        print(f"⚠️  Streams sin canal identificado: {missing}")
        print(f"   \U0001f4c1 Revisar carpeta debug/ para más detalles")
    else:
        print("✅ Todos los streams tienen canal identificado")

print("\n" + "=" * 70)
print(f"\U0001f550 Tiempo de finalización: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("✅ PROCESO COMPLETADO EXITOSAMENTE")
print("=" * 70)

sys.exit(0)

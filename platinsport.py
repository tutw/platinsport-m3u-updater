from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import base64
import time
import os
import html

URL = "https://www.platinsport.com/"

print("=== PLATINSPORT SCRAPER FINAL ===\n")

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
    flag_span = link_tag.find("span", class_=re.compile(r"\bfi\b|\bfi-"))
    lang = "XX"
    if flag_span:
        classes = flag_span.get("class", []) or []
        # Ejemplos típicos: ["fi","fi-pt"] o ["fi","fi-es"]
        for cls in classes:
            if cls.startswith("fi-") and len(cls) == 5:
                lang = cls.replace("fi-", "").upper()
                break
    return lang

def try_extract_channel_name(link_tag) -> str:
    """
    Extrae el canal de la forma más robusta posible:
    1) Texto visible del <a> (incluyendo hijos)
    2) Texto de nodos concretos (<b>, <strong>, spans)
    3) Atributos (title/aria-label/data-*)
    """
    # 1) Texto completo del enlace (incluye hijos)
    txt = clean_text(link_tag.get_text(" ", strip=True))

    # A veces el texto puede venir como "PT ELEVEN DAZN 1" o similar.
    # Quitamos tokens de idioma al inicio si están sueltos.
    txt = re.sub(r"^(?:[A-Z]{2})\s+", "", txt).strip()

    # Si queda vacío o es basura, intentamos otros métodos
    if txt and txt.upper() not in {"STREAM", "STREAM HD", "HD", "LINK"}:
        return txt

    # 2) Buscar dentro de nodos que suelen contener el nombre (b/strong/span)
    for sel in ["b", "strong", "span", "div"]:
        candidates = link_tag.select(sel)
        for c in candidates:
            c_txt = clean_text(c.get_text(" ", strip=True))
            c_txt = re.sub(r"^(?:[A-Z]{2})\s+", "", c_txt).strip()
            if c_txt and c_txt.upper() not in {"STREAM", "STREAM HD", "HD", "LINK"}:
                return c_txt

    # 3) Atributos útiles
    for attr in ["title", "aria-label", "data-title", "data-channel", "data-name"]:
        v = clean_text(link_tag.get(attr, ""))
        v = re.sub(r"^(?:[A-Z]{2})\s+", "", v).strip()
        if v and v.upper() not in {"STREAM", "STREAM HD", "HD", "LINK"}:
            return v

    return ""

def dump_debug_popup(popup_html: str, event_name: str, event_count: int, lang: str, ace_url: str):
    safe_event = re.sub(r"[^a-zA-Z0-9_-]+", "_", event_name)[:60] or "evento"
    fname = f"debug/popup_{safe_event}_{event_count}_{lang}.html"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(popup_html)
        # también guardamos un mini log
        with open("debug/debug_missing_channels.txt", "a", encoding="utf-8") as lf:
            lf.write(f"{event_name} | {lang} | {ace_url} | {fname}\n")
    except Exception:
        pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )

    # Cookie para aceptar términos
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
        page.goto(URL, timeout=90000, wait_until="domcontentloaded")
        time.sleep(2)
        print("✓ Página cargada\n")
    except Exception as e:
        print(f"✗ Error al cargar página: {e}")
        browser.close()
        raise

    main_html = page.content()
    soup = BeautifulSoup(main_html, "lxml")

    print("Analizando estructura de eventos...")

    category_divs = soup.find_all("div", style=re.compile(r"background:#000.*color:#ffae00"))
    print(f"✓ Encontradas {len(category_divs)} categorías\n")

    for cat_div in category_divs:
        category = clean_text(cat_div.get_text(strip=True))
        category = re.sub(r"^[–\-]\s*", "", category)

        print(f"Categoría: {category}")

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
                else:
                    event_name = f"Evento {event_count}"

                print(f"  • {event_name} - {event_time}")

                href = play_link.get("href", "")
                match = re.search(r"go\('([^']+)'\)", href)
                if not match:
                    print("    ✗ No se pudo extraer el PHP file")
                    continue

                php_file = match.group(1)

                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                key = base64.b64encode((today + "PLATINSPORT").encode()).decode()
                popup_url = f"https://www.platinsport.com/link/{php_file}?key={key}"

                popup_page = context.new_page()
                try:
                    popup_page.goto(popup_url, timeout=45000, referer=URL, wait_until="domcontentloaded")
                    time.sleep(0.4)

                    popup_html = popup_page.content()
                    popup_soup = BeautifulSoup(popup_html, "lxml")

                    ace_links = popup_soup.find_all("a", href=re.compile(r"^acestream://"))
                    print(f"    ✓ {len(ace_links)} streams")

                    for link in ace_links:
                        ace_url = link.get("href", "").strip()
                        if not ace_url.startswith("acestream://"):
                            continue

                        lang = extract_lang_from_flag(link)
                        channel = try_extract_channel_name(link)

                        # requisito: canal sí o sí (si no, lo marcamos y guardamos HTML)
                        if not channel:
                            channel = "UNKNOWN_CHANNEL"
                            dump_debug_popup(popup_html, event_name, event_count, lang, ace_url)

                        all_streams.append({
                            "event": event_name,
                            "category": category,
                            "time": event_time,
                            "channel": channel,
                            "url": ace_url,
                            "lang": lang
                        })

                except Exception as e:
                    print(f"    ✗ Error popup: {str(e)[:120]}")
                finally:
                    try:
                        popup_page.close()
                    except Exception:
                        pass

                time.sleep(0.1)

            current = current.find_next_sibling()

        print()

    try:
        page.close()
    except Exception:
        pass
    browser.close()

print("Generando lista.m3u...")
m3u_lines = ["#EXTM3U"]

for stream in all_streams:
    event_info = stream["event"]
    if stream["time"]:
        event_info = f"{event_info} - {stream['time']}"

    tvg_name = f"{event_info} - [{stream['lang']}] {stream['channel']}"
    group_title = stream["category"]

    # Formato estándar (2 líneas):
    m3u_lines.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{group_title}",{stream["channel"]}')
    m3u_lines.append(stream["url"])

with open("lista.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines) + "\n")

print(f"\n{'='*50}")
print("✓ lista.m3u generado con éxito!")
print(f"✓ Total de streams: {len(all_streams)}")
print(f"✓ Categorías únicas: {len(set(s['category'] for s in all_streams))}")
print(f"✓ Eventos únicos: {len(set(s['event'] for s in all_streams))}")
missing = sum(1 for s in all_streams if s["channel"] == "UNKNOWN_CHANNEL")
print(f"✓ Streams sin canal (debug): {missing} (ver carpeta debug/)")
print(f"{'='*50}")

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import os
import sys
import html

URL = "https://www.platinsport.com/"

def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def parse_time_iso(time_tag) -> str:
    """
    El sitio rellena el texto del <time> por JS.
    Nosotros leemos el atributo datetime (ISO) y devolvemos HH:MM.
    """
    if not time_tag:
        return ""
    dt = time_tag.get("datetime") or time_tag.get("dateTime") or ""
    dt = clean_text(dt)
    if not dt:
        return ""
    try:
        dt_norm = dt.replace("Z", "+00:00")
        d = datetime.fromisoformat(dt_norm)
        return d.strftime("%H:%M")
    except Exception:
        return dt

def extract_lang_from_flag(a_tag) -> str:
    flag = a_tag.find("span", class_=re.compile(r"\bfi\b|\bfi-"))
    if not flag:
        return "XX"
    classes = flag.get("class", []) or []
    for cls in classes:
        if cls.startswith("fi-") and len(cls) == 5:
            return cls.replace("fi-", "").upper()
    return "XX"

def extract_channel_name(a_tag) -> str:
    """
    Quita el <span> de la bandera y devuelve el texto del canal.
    Se hace sobre una copia para no mutar el DOM original.
    """
    tmp = BeautifulSoup(str(a_tag), "lxml")
    a = tmp.find("a") or tmp
    for flag in a.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
        flag.decompose()
    return clean_text(a.get_text(" ", strip=True))

def is_bad_channel(ch: str) -> bool:
    if not ch:
        return True
    u = clean_text(ch).upper()
    return u in {"STREAM", "STREAM HD", "HD", "WATCH", "PLAY", "LIVE", "LINK", "TV", ""}

def get_event_name(match_div) -> str:
    """
    match_div es <div class="match-title-bar"><time ...></time> Partido</div>
    Quitamos el time y nos quedamos con el nombre del evento.
    """
    tmp = BeautifulSoup(str(match_div), "lxml")
    d = tmp.find("div")
    if not d:
        return ""
    t = d.find("time")
    if t:
        t.decompose()
    return clean_text(d.get_text(" ", strip=True))

print("=" * 70)
print("=== PLATINSPORT M3U UPDATER (FIX DEFINITIVO) ===")
print("=" * 70)
print(f"Python version: {sys.version.split()[0]}")
print(f"Start time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)

os.makedirs("debug", exist_ok=True)

streams = []

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
            ],
        )

        # CLAVE: desactivar JS para evitar el script que cambia nombres a "STREAM HD"
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            java_script_enabled=False,
        )

        # Intentar “saltarse” disclaimers si existen
        context.add_cookies(
            [
                {
                    "name": "disclaimer_accepted",
                    "value": "true",
                    "domain": ".platinsport.com",
                    "path": "/",
                    "sameSite": "Lax",
                }
            ]
        )

        page = context.new_page()
        page.goto(URL, timeout=90000, wait_until="domcontentloaded")
        html_main = page.content()

        # Debug: HTML capturado SIN JS
        with open("debug/main_nojs.html", "w", encoding="utf-8") as f:
            f.write(html_main)

        soup = BeautifulSoup(html_main, "lxml")

        container = soup.select_one(".myDiv1")
        if not container:
            with open("debug/error_no_container.html", "w", encoding="utf-8") as f:
                f.write(html_main)
            raise RuntimeError("No se encontró .myDiv1 (estructura cambió o bloqueo activo).")

        # Categorías: en el HTML que pegaste son <p> dentro de .myDiv1
        categories = container.find_all("p", recursive=False)
        print(f"✅ Categorías detectadas: {len(categories)}")

        for pcat in categories:
            category = clean_text(pcat.get_text(" ", strip=True))
            if not category:
                continue

            # Recorremos hermanos hasta el siguiente <p> (siguiente categoría)
            node = pcat.find_next_sibling()
            while node and not (node.name == "p"):
                # Encontrar match-title-bar
                if node.name == "div" and "match-title-bar" in (node.get("class", []) or []):
                    time_tag = node.find("time")
                    event_time = parse_time_iso(time_tag)
                    event_name = get_event_name(node)

                    # El bloque de botones suele ser el siguiente div.button-group
                    btn_group = node.find_next_sibling("div", class_=re.compile(r"\bbutton-group\b"))
                    if not btn_group:
                        node = node.find_next_sibling()
                        continue

                    # Capturar SOLO acestream://
                    for a in btn_group.find_all("a", href=re.compile(r"^acestream://")):
                        url = clean_text(a.get("href", ""))
                        lang = extract_lang_from_flag(a)
                        channel = extract_channel_name(a)

                        # Si por cualquier motivo el servidor ya sirve “STREAM HD”
                        if is_bad_channel(channel):
                            channel = f"{lang}_STREAM"
                            with open("debug/bad_channel_snippet.html", "a", encoding="utf-8") as df:
                                df.write("\n<!-- BAD CHANNEL -->\n")
                                df.write(str(a))
                                df.write("\n")

                        streams.append(
                            {
                                "category": category,
                                "event": event_name,
                                "time": event_time,
                                "lang": lang,
                                "channel": channel,
                                "url": url,
                            }
                        )

                node = node.find_next_sibling()

        browser.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"✅ Total streams: {len(streams)}")

# Generar M3U
m3u = ["#EXTM3U"]
for s in streams:
    event_info = s["event"]
    if s["time"]:
        event_info = f"{event_info} - {s['time']}"
    tvg_name = f"{event_info} - [{s['lang']}] {s['channel']}"
    m3u.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{s["category"]}",{s["channel"]}')
    m3u.append(s["url"])

with open("lista.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u) + "\n")

print("✅ lista.m3u generado correctamente")
sys.exit(0)

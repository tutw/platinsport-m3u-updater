from playwright.sync_api import sync_playwright, Route
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import os
import sys
import html
import json

BASE_URL = "https://www.platinsport.com/"

# Almacenamiento global para capturar respuestas de red
captured_responses = []

def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_bad_channel(ch: str) -> bool:
    if not ch:
        return True
    u = clean_text(ch).upper()
    return u in {"STREAM", "STREAM HD", "HD", "WATCH", "PLAY", "LIVE", "LINK", "TV", ""}

def extract_lang_from_flag(a_tag) -> str:
    flag = a_tag.find("span", class_=re.compile(r"\bfi\b|\bfi-"))
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

def extract_channel_name_from_a(a_tag) -> str:
    """Extrae nombre de canal desde <a>, probando atributos primero."""
    for attr in ("title", "aria-label", "data-title", "data-name", "data-channel"):
        val = clean_text(a_tag.get(attr))
        if val and not is_bad_channel(val):
            return val

    tmp = BeautifulSoup(str(a_tag), "lxml")
    a = tmp.find("a") or tmp
    for flag in a.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
        flag.decompose()
    return clean_text(a.get_text(" ", strip=True))

def parse_streams_from_html(html_content: str):
    """
    Parsea HTML de cualquier página de Platinsport (home o /link/NN.php)
    buscando bloques de partidos + acestream links.
    """
    soup = BeautifulSoup(html_content, "lxml")
    streams = []

    # Intentar .myDiv1 (estructura típica de /link/NN.php) [Source](https://greasyfork.org/en/scripts/449126-platinsport-direct-acestream-links/code)
    div1 = soup.select_one(".myDiv1")
    if div1:
        match_title = ""
        for node in div1.contents:
            if getattr(node, "name", None) is None:
                txt = clean_text(str(node).replace("\n", ""))
                if len(txt) > 1:
                    match_title = txt
                continue

            if node.name == "a":
                href = clean_text(node.get("href", ""))
                if href.startswith("acestream://"):
                    lang = extract_lang_from_flag(node)
                    channel = extract_channel_name_from_a(node)
                    if is_bad_channel(channel):
                        channel = f"{lang} STREAM"
                    streams.append({
                        "match": match_title or "Match",
                        "lang": lang,
                        "channel": channel,
                        "url": href,
                    })

    # Fallback: buscar cualquier <a href="acestream://"> en toda la página
    if not streams:
        all_links = soup.find_all("a", href=re.compile(r"^acestream://"))
        for a in all_links:
            href = clean_text(a.get("href", ""))
            lang = extract_lang_from_flag(a)
            channel = extract_channel_name_from_a(a)
            if is_bad_channel(channel):
                channel = f"{lang} STREAM"
            
            # Intentar inferir el partido desde hermanos/padre
            match_title = "Match"
            parent = a.find_parent()
            if parent:
                prev = parent.find_previous_sibling()
                if prev and prev.get_text():
                    match_title = clean_text(prev.get_text())[:100]

            streams.append({
                "match": match_title,
                "lang": lang,
                "channel": channel,
                "url": href,
            })

    return streams

def handle_route(route: Route):
    """
    Interceptor de red: captura respuestas de .php / .json
    """
    global captured_responses
    url = route.request.url

    # Continuar la petición
    response = route.fetch()
    
    # Capturar respuestas relevantes (link/NN.php, api endpoints...)
    if "/link/" in url and url.endswith(".php"):
        try:
            body = response.text()
            captured_responses.append({
                "url": url,
                "status": response.status,
                "body": body,
            })
        except:
            pass

    route.fulfill(response=response)

def write_m3u(all_entries, out_path="lista.m3u"):
    m3u = ["#EXTM3U"]
    for e in all_entries:
        group = e.get("group", "Platinsport")
        match = e.get("match", "Match")
        lang = e.get("lang", "XX")
        channel = e.get("channel", "STREAM")
        url = e.get("url", "")

        tvg_name = f"{match} - [{lang}] {channel}"
        m3u.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{group}",{channel}')
        m3u.append(url)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")

def main():
    global captured_responses

    print("=" * 70)
    print("=== PLATINSPORT M3U UPDATER (NETWORK INTERCEPT FIX) ===")
    print("=" * 70)
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Start time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    os.makedirs("debug", exist_ok=True)
    all_entries = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
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
            java_script_enabled=True,  # NECESARIO para cargar streams dinámicamente
        )

        context.add_cookies([
            {
                "name": "disclaimer_accepted",
                "value": "true",
                "domain": ".platinsport.com",
                "path": "/",
                "sameSite": "Lax",
            }
        ])

        page = context.new_page()

        # Interceptar red para capturar /link/NN.php
        page.route("**/*", handle_route)

        print(f"🌐 Cargando {BASE_URL}...")
        
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            
            # Esperar a que JS cargue contenido dinámico (máx 10s)
            try:
                page.wait_for_selector(".myDiv1, a[href^='acestream://']", timeout=10000)
            except:
                print("⚠️ Timeout esperando acestream links, intentando parsear DOM actual...")

            # Esperar idle (red inactiva)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass

            html_main = page.content()

            # Debug: guardar HTML principal
            with open("debug/main_loaded.html", "w", encoding="utf-8") as f:
                f.write(html_main)

            print(f"✅ Página cargada. HTML size: {len(html_main)} bytes")
            print(f"✅ Respuestas capturadas de red: {len(captured_responses)}")

            # 1) Parsear respuestas de red capturadas (/link/NN.php)
            for resp in captured_responses:
                streams = parse_streams_from_html(resp["body"])
                if streams:
                    print(f"✅ Extraídos {len(streams)} streams de {resp['url']}")
                    for s in streams:
                        all_entries.append({
                            "group": "Platinsport",
                            "match": s["match"],
                            "lang": s["lang"],
                            "channel": s["channel"],
                            "url": s["url"],
                        })

            # 2) Fallback: parsear HTML principal (si el JS ya renderizó los links)
            if not all_entries:
                print("⚠️ No se capturaron respuestas de red. Parseando HTML principal...")
                streams_main = parse_streams_from_html(html_main)
                if streams_main:
                    print(f"✅ Extraídos {len(streams_main)} streams del DOM principal")
                    for s in streams_main:
                        all_entries.append({
                            "group": "Platinsport",
                            "match": s["match"],
                            "lang": s["lang"],
                            "channel": s["channel"],
                            "url": s["url"],
                        })

            # Guardar algunas respuestas de red para debug
            if captured_responses:
                for i, resp in enumerate(captured_responses[:3]):
                    fname = f"debug/network_resp_{i:02d}.html"
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(resp["body"])

        except Exception as e:
            print(f"❌ ERROR cargando página: {e}")
            import traceback
            traceback.print_exc()
            browser.close()
            sys.exit(1)

        browser.close()

    print(f"✅ Total streams recolectados: {len(all_entries)}")

    if len(all_entries) < 5:
        with open("debug/error_summary.txt", "w", encoding="utf-8") as f:
            f.write(f"Too few entries: {len(all_entries)}\n")
            f.write(f"Captured network responses: {len(captured_responses)}\n")
        print("❌ Muy pocos streams. Revisa debug/main_loaded.html y debug/network_resp_*.html")
        sys.exit(1)

    write_m3u(all_entries, "lista.m3u")
    print("✅ lista.m3u generado correctamente")

if __name__ == "__main__":
    main()

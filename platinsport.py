from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import os
import sys
import html
import time
from urllib.parse import urljoin

BASE_URL = "https://www.platinsport.com/"

def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_bad_channel(ch: str) -> bool:
    if not ch:
        return True
    u = clean_text(ch).upper()
    bad = {"STREAM", "STREAM HD", "HD", "WATCH", "PLAY", "LIVE", "LINK", "TV", "CHANNEL", "MATCH"}
    return u in bad or len(clean_text(ch)) < 2

def extract_lang_from_flag(node) -> str:
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

def extract_match_title_from_popup(soup: BeautifulSoup) -> str:
    # Heurística: buscar algo con " vs " en el texto del popup
    text = clean_text(soup.get_text("\n", strip=True))
    for line in [clean_text(x) for x in text.split("\n") if clean_text(x)]:
        if " vs " in line.lower() or " v " in line.lower():
            return line[:120]
    return "Match"

def extract_channel_from_a(a_tag) -> str:
    # En tus popups reales, el <a> tiene title="STREAM HD" y texto "STREAM HD" [Source](https://www.genspark.ai/api/files/s/KWYGjq3r)
    for attr in ("title", "aria-label", "data-title", "data-name", "data-channel"):
        v = clean_text(a_tag.get(attr, ""))
        if v and not is_bad_channel(v):
            return v

    # Texto sin banderas
    tmp = BeautifulSoup(str(a_tag), "lxml")
    a = tmp.find("a") or tmp
    for flag in a.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
        flag.decompose()
    t = clean_text(a.get_text(" ", strip=True))
    if t and not is_bad_channel(t):
        return t

    return ""

def parse_popup_html(html_content: str, popup_url: str):
    soup = BeautifulSoup(html_content, "lxml")
    match_title = extract_match_title_from_popup(soup)

    links = soup.find_all("a", href=re.compile(r"^acestream://"))
    entries = []

    # Si el popup solo trae STREAM HD, generamos nombres únicos por idioma/orden
    per_lang_counter = {}

    for a in links:
        href = clean_text(a.get("href", ""))
        if not href.startswith("acestream://"):
            continue

        lang = extract_lang_from_flag(a)
        ch = extract_channel_from_a(a)

        if is_bad_channel(ch):
            per_lang_counter[lang] = per_lang_counter.get(lang, 0) + 1
            # fallback útil (evita “STREAM HD” repetido)
            ch = f"STREAM HD ({lang}) #{per_lang_counter[lang]}"

        entries.append({
            "group": "Platinsport",
            "match": match_title,
            "lang": lang,
            "channel": ch,
            "url": href,
            "source": popup_url,
        })

    return entries

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
    print(f"✅ Archivo {out_path} generado con {len(all_entries)} entradas")

def discover_popup_urls(home_html: str):
    """
    Descubre URLs candidatas a popups.
    No sabemos el patrón exacto, así que:
      - busca href/src que contengan 'popup' o 'modal'
      - busca rutas internas que parezcan endpoints de detalle
    """
    soup = BeautifulSoup(home_html, "lxml")
    urls = set()

    for tag in soup.find_all(["a", "iframe", "script"]):
        for attr in ("href", "src", "data-src", "data-url"):
            u = tag.get(attr)
            if not u:
                continue
            u = clean_text(u)
            if not u:
                continue
            if "popup" in u.lower() or "modal" in u.lower():
                urls.add(urljoin(BASE_URL, u))

    # fallback: cualquier enlace interno relevante
    for a in soup.find_all("a", href=True):
        u = clean_text(a["href"])
        if u.startswith("/") and any(k in u.lower() for k in ("event", "match", "game", "popup", "modal")):
            urls.add(urljoin(BASE_URL, u))

    return sorted(urls)

def main():
    print("=" * 70)
    print("=== PLATINSPORT M3U UPDATER ===")
    print("=" * 70)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Inicio: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
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
                "--disable-blink-features=AutomationControlled",
                "--disable-ipv6",
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

        context.add_cookies([{
            "name": "disclaimer_accepted",
            "value": "true",
            "domain": ".platinsport.com",
            "path": "/",
            "sameSite": "Lax",
        }])

        page = context.new_page()

        # bloquear trackers
        def handle_route(route):
            url = route.request.url
            blocked = [
                "first-id.fr",
                "google-analytics.com",
                "googletagmanager.com",
                "doubleclick.net",
                "facebook.com",
                "analytics.",
                "advertising.",
            ]
            if any(d in url for d in blocked):
                route.abort()
            else:
                route.continue_()
        page.route("**/*", handle_route)

        print(f"🌐 Cargando {BASE_URL}...")
        page.goto(BASE_URL, timeout=90000, wait_until="domcontentloaded")
        time.sleep(3)

        home_html = page.content()
        with open("debug/main_page.html", "w", encoding="utf-8") as f:
            f.write(home_html)
        print(f"✅ HTML home capturado ({len(home_html)} bytes)")

        # 1) Intento directo: si la home ya tiene acestream (a veces ocurre)
        home_soup = BeautifulSoup(home_html, "lxml")
        direct = home_soup.select("a[href^='acestream://']")
        if direct:
            print(f"✅ La home ya contiene {len(direct)} enlaces acestream (modo directo)")
            all_entries.extend(parse_popup_html(home_html, BASE_URL))
        else:
            # 2) Si no hay links, descubrimos popups y los visitamos
            popup_urls = discover_popup_urls(home_html)
            print(f"🔎 Popups candidatos encontrados en home: {len(popup_urls)}")

            # Si no se detecta ninguno, aún así no fallamos: guardamos debug y salimos con error
            if not popup_urls:
                print("❌ No se detectaron URLs de popup en la home. Revisa debug/main_page.html")
                browser.close()
                sys.exit(1)

            for i, pu in enumerate(popup_urls[:200], start=1):
                try:
                    page.goto(pu, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(1)
                    pop_html = page.content()

                    # Guardar muestra (no todos, para no inflar repo)
                    if i <= 5:
                        safe_name = f"debug/popup_sample_{i}.html"
                        with open(safe_name, "w", encoding="utf-8") as f:
                            f.write(pop_html)

                    entries = parse_popup_html(pop_html, pu)
                    if entries:
                        print(f"  ✅ Popup {i}/{len(popup_urls)}: {len(entries)} enlaces acestream")
                        all_entries.extend(entries)

                except Exception as e:
                    print(f"  ⚠️ Error abriendo popup {pu}: {e}")

        browser.close()

    # de-duplicar por url
    dedup = {}
    for e in all_entries:
        dedup[e["url"]] = e
    all_entries = list(dedup.values())

    print(f"\n📊 Total streams encontrados: {len(all_entries)}")
    if len(all_entries) < 5:
        print("❌ Muy pocos streams encontrados. Revisa debug/*.html")
        sys.exit(1)

    write_m3u(all_entries, "lista.m3u")
    print("\n✅ Proceso completado exitosamente")

if __name__ == "__main__":
    main()

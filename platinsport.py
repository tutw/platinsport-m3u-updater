from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import os
import sys
import html
import time

BASE_URL = "https://www.platinsport.com/"

# ----------------------------
# Helpers
# ----------------------------
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
    bad_names = {
        "STREAM", "STREAM HD", "HD", "WATCH", "PLAY", "LIVE",
        "LINK", "TV", "CHANNEL", "MATCH"
    }
    return u in bad_names or len(clean_text(ch)) < 2


def extract_lang_from_flag(node) -> str:
    # Busca banderas tipo fi fi-xx o fi-xx
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


def best_attr_text(tag, attrs):
    for a in attrs:
        v = clean_text(tag.get(a, ""))
        if v and not is_bad_channel(v):
            return v
    return ""


def extract_channel_from_context(a_tag) -> str:
    """
    Platinsport: el <a href="acestream://..."> suele ser un botón/acción.
    El nombre del canal suele estar en un contenedor cercano.
    Estrategia:
      1) atributos del propio <a>
      2) texto del propio <a> (sin banderas)
      3) buscar en padres cercanos (hasta N niveles) un texto/atributo que parezca canal
      4) buscar en hermanos anteriores dentro del mismo contenedor
    """
    # 1) atributos directos
    v = best_attr_text(a_tag, ["title", "aria-label", "data-title", "data-name", "data-channel"])
    if v:
        return v

    # 2) texto visible del <a> (sin banderas)
    tmp = BeautifulSoup(str(a_tag), "lxml")
    a = tmp.find("a") or tmp
    for flag in a.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
        flag.decompose()
    t = clean_text(a.get_text(" ", strip=True))
    if t and not is_bad_channel(t):
        return t

    # 3) contexto: subir por padres y buscar candidatos
    parent = a_tag
    for _ in range(0, 6):
        parent = parent.parent if parent else None
        if not parent or not getattr(parent, "find", None):
            break

        # 3a) atributos del contenedor que suelen llevar nombre
        v = best_attr_text(parent, ["data-channel", "data-name", "aria-label", "title"])
        if v:
            return v

        # 3b) buscar elementos típicos con "channel" en class/id
        candidate = parent.find(
            ["div", "span", "p", "strong"],
            class_=re.compile(r"(channel|source|provider|tv|name)", re.I)
        )
        if candidate:
            ct = clean_text(candidate.get_text(" ", strip=True))
            if ct and not is_bad_channel(ct):
                return ct

        # 3c) heurística: primera pieza de texto "corta" que no sea basura
        # (evita títulos de partido largos)
        text = clean_text(parent.get_text("\n", strip=True))
        lines = [clean_text(x) for x in text.split("\n") if clean_text(x)]
        # prioriza líneas tipo "SPORT TV HD" (cortas) frente a líneas largas
        for line in sorted(lines, key=len):
            if 3 <= len(line) <= 40 and not is_bad_channel(line):
                # evita que coja horas/score
                if not re.fullmatch(r"[\d:\- ]+", line):
                    return line

    return ""


def extract_match_title_from_context(a_tag) -> str:
    """
    Intenta inferir el partido desde contexto.
    Si no se puede, devuelve 'Match'.
    """
    # Subir en el árbol y buscar un encabezado / texto largo con vs
    parent = a_tag
    for _ in range(0, 8):
        parent = parent.parent if parent else None
        if not parent or not getattr(parent, "get_text", None):
            break
        text = clean_text(parent.get_text("\n", strip=True))
        if " vs " in text.lower() or " v " in text.lower():
            # intenta extraer la línea más representativa
            lines = [clean_text(x) for x in text.split("\n") if clean_text(x)]
            for line in lines:
                if len(line) >= 8 and (" vs " in line.lower() or " v " in line.lower()):
                    return line[:120]
    return "Match"


def parse_streams_from_html(html_content: str, source_label=""):
    soup = BeautifulSoup(html_content, "lxml")
    streams = []

    all_links = soup.find_all("a", href=re.compile(r"^acestream://"))
    print(f"  🔍 Encontrados {len(all_links)} enlaces acestream en {source_label}")

    for a in all_links:
        href = clean_text(a.get("href", ""))
        if not href.startswith("acestream://"):
            continue

        lang = extract_lang_from_flag(a)
        channel = extract_channel_from_context(a)
        match_title = extract_match_title_from_context(a)

        # Fallback final (pero NO “STREAM HD” fijo)
        if is_bad_channel(channel):
            channel = f"{lang} STREAM"

        streams.append({
            "match": match_title,
            "lang": lang,
            "channel": channel,
            "url": href,
        })

    return streams


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


def wait_for_acestream_links(page, max_wait=60):
    print(f"⏳ Esperando a que carguen enlaces acestream (máx {max_wait}s)...")
    start_time = time.time()
    found_count = 0

    while (time.time() - start_time) < max_wait:
        count = page.locator("a[href^='acestream://']").count()
        if count > 0:
            if count != found_count:
                found_count = count
                print(f"  ✅ Detectados {count} enlaces acestream...")
            time.sleep(3)
            final_count = page.locator("a[href^='acestream://']").count()
            if final_count == found_count:
                print(f"  ✅ Total final: {final_count} enlaces acestream")
                return True
            found_count = final_count
        time.sleep(2)

    print(f"  ⏱️ Timeout. Enlaces encontrados: {found_count}")
    return found_count > 0


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

        def handle_route(route):
            url = route.request.url
            blocked_domains = [
                "first-id.fr",
                "google-analytics.com",
                "googletagmanager.com",
                "doubleclick.net",
                "facebook.com",
                "analytics.",
                "advertising.",
            ]
            if any(d in url for d in blocked_domains):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", handle_route)

        print(f"🌐 Cargando {BASE_URL}...")

        try:
            page.goto(BASE_URL, timeout=90000, wait_until="domcontentloaded")
            wait_for_acestream_links(page, max_wait=60)

            html_content = page.content()
            with open("debug/main_page.html", "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"✅ HTML capturado ({len(html_content)} bytes)")

            streams = parse_streams_from_html(html_content, "página principal")

            for s in streams:
                all_entries.append({
                    "group": "Platinsport",
                    "match": s["match"],
                    "lang": s["lang"],
                    "channel": s["channel"],
                    "url": s["url"],
                })

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            with open("debug/error.txt", "w", encoding="utf-8") as f:
                f.write(f"Error: {e}\n")
                f.write(traceback.format_exc())
            browser.close()
            sys.exit(1)

        browser.close()

    print(f"\n📊 Total streams encontrados: {len(all_entries)}")
    if len(all_entries) < 5:
        print("❌ Muy pocos streams encontrados. Revisa debug/main_page.html")
        sys.exit(1)

    write_m3u(all_entries, "lista.m3u")
    print("\n✅ Proceso completado exitosamente")


if __name__ == "__main__":
    main()

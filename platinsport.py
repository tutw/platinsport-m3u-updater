from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import os
import sys
import html
import time

BASE_URL = "https://www.platinsport.com/"

def clean_text(s: str) -> str:
    """Limpia y normaliza texto"""
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def extract_lang_from_flag(node) -> str:
    """Extrae el código de idioma de la bandera"""
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

def parse_html_for_streams(html_content: str):
    """
    Parsea el HTML y extrae información de streams.
    IMPORTANTE: Este HTML debe ser capturado ANTES de que JavaScript
    modifique los nombres de los canales.
    """
    soup = BeautifulSoup(html_content, "lxml")
    entries = []
    
    # Buscar todas las secciones de partidos
    match_sections = soup.find_all("div", class_="match-title-bar")
    
    for match_div in match_sections:
        # Extraer título del partido
        match_title = clean_text(match_div.get_text())
        
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
            lang = extract_lang_from_flag(a)
            
            # Extraer nombre del canal (el texto después de la bandera)
            # Primero clonamos el tag para no modificar el original
            a_copy = BeautifulSoup(str(a), "lxml").find("a")
            if not a_copy:
                continue
                
            # Eliminar todas las etiquetas de bandera
            for flag in a_copy.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
                flag.decompose()
            
            # Obtener el texto limpio
            channel_name = clean_text(a_copy.get_text())
            
            # Si el nombre está vacío o es genérico, usar alternativas
            if not channel_name or channel_name in ["", "STREAM HD", "HD", "STREAM"]:
                # Intentar obtener de atributos
                channel_name = clean_text(a.get("title", ""))
                if not channel_name or channel_name in ["", "STREAM HD"]:
                    # Generar un nombre basado en el contenido visible
                    channel_name = f"Stream {lang}"
            
            entries.append({
                "match": match_title,
                "lang": lang,
                "channel": channel_name,
                "url": href,
            })
    
    return entries

def write_m3u(all_entries, out_path="lista.m3u"):
    """Escribe el archivo M3U con los streams"""
    m3u = ["#EXTM3U"]
    for e in all_entries:
        match = e.get("match", "Match")
        lang = e.get("lang", "XX")
        channel = e.get("channel", "STREAM")
        url = e.get("url", "")
        
        # Formato: nombre del partido + [idioma] + nombre del canal
        tvg_name = f"{match} - [{lang}] {channel}"
        group_title = "Platinsport"
        
        m3u.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{group_title}",{channel}')
        m3u.append(url)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u) + "\n")
    
    print(f"✅ Archivo {out_path} generado con {len(all_entries)} entradas")

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
            java_script_enabled=False,  # ¡CLAVE! Deshabilitar JavaScript
            ignore_https_errors=True,
        )

        page = context.new_page()

        # Bloquear trackers y scripts que puedan modificar el contenido
        def handle_route(route):
            url = route.request.url
            resource_type = route.request.resource_type
            
            # Bloquear scripts, analytics, ads
            blocked_domains = [
                "first-id.fr",
                "google-analytics.com",
                "googletagmanager.com",
                "doubleclick.net",
                "facebook.com",
                "analytics.",
                "advertising.",
                "haberdasherycorpse.com",
            ]
            
            if resource_type == "script" or any(d in url for d in blocked_domains):
                route.abort()
            else:
                route.continue_()
        
        page.route("**/*", handle_route)

        print(f"🌐 Cargando {BASE_URL} (sin JavaScript)...")
        try:
            page.goto(BASE_URL, timeout=90000, wait_until="domcontentloaded")
            time.sleep(2)  # Esperar a que cargue el contenido estático
        except Exception as e:
            print(f"❌ Error cargando página: {e}")
            browser.close()
            sys.exit(1)

        # Obtener el HTML ANTES de que JavaScript lo modifique
        raw_html = page.content()
        
        # Guardar para debug
        with open("debug/raw_page.html", "w", encoding="utf-8") as f:
            f.write(raw_html)
        
        print(f"✅ HTML capturado ({len(raw_html)} bytes)")

        browser.close()

    # Parsear el HTML
    print("📊 Parseando streams...")
    all_entries = parse_html_for_streams(raw_html)
    
    print(f"\n📊 Total streams encontrados: {len(all_entries)}")
    
    if len(all_entries) < 5:
        print("❌ Muy pocos streams encontrados. Revisa debug/raw_page.html")
        sys.exit(1)

    # Eliminar duplicados por URL
    dedup = {}
    for e in all_entries:
        dedup[e["url"]] = e
    all_entries = list(dedup.values())
    
    print(f"📊 Streams únicos: {len(all_entries)}")

    # Guardar el M3U
    write_m3u(all_entries, "lista.m3u")
    
    # Mostrar muestra
    print("\n📄 Muestra de los primeros 10 canales:")
    for i, e in enumerate(all_entries[:10], 1):
        print(f"  {i}. [{e['lang']}] {e['channel']} - {e['match'][:50]}")
    
    print("\n✅ Proceso completado exitosamente")

if __name__ == "__main__":
    main()

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
import os
import sys
import html

BASE_URL = "https://www.platinsport.com/"

def clean_text(s: str) -> str:
    """Limpia y normaliza texto"""
    if s is None:
        return ""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_bad_channel(ch: str) -> bool:
    """Detecta nombres genéricos/vacíos de canales"""
    if not ch:
        return True
    u = clean_text(ch).upper()
    bad_names = {"STREAM", "STREAM HD", "HD", "WATCH", "PLAY", "LIVE", "LINK", "TV", "CHANNEL", ""}
    return u in bad_names or len(ch) < 2

def extract_lang_from_flag(a_tag) -> str:
    """Extrae código de país desde clase CSS de bandera (fi-xx)"""
    flag = a_tag.find("span", class_=re.compile(r"\bfi\b|\bfi-"))
    if not flag:
        return "XX"
    
    classes = flag.get("class", []) or []
    for cls in classes:
        if cls.startswith("fi-") and len(cls) == 5:
            cc = cls.replace("fi-", "").upper()
            # Conversión especial para UK
            if cc == "UK":
                cc = "GB"
            return cc
    return "XX"

def extract_channel_name_from_a(a_tag) -> str:
    """
    Extrae nombre de canal desde <a>, probando múltiples estrategias:
    1. Atributos HTML (title, aria-label, data-*)
    2. Texto del enlace (excluyendo banderas)
    """
    # Estrategia 1: Buscar en atributos
    for attr in ("title", "aria-label", "data-title", "data-name", "data-channel"):
        val = clean_text(a_tag.get(attr, ""))
        if val and not is_bad_channel(val):
            return val
    
    # Estrategia 2: Extraer texto visible (sin banderas)
    tmp = BeautifulSoup(str(a_tag), "lxml")
    a = tmp.find("a") or tmp
    
    # Eliminar todas las banderas del texto
    for flag in a.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
        flag.decompose()
    
    text = clean_text(a.get_text(" ", strip=True))
    if text and not is_bad_channel(text):
        return text
    
    return ""

def parse_streams_from_html(html_content: str, source_label=""):
    """
    Parsea HTML buscando enlaces acestream:// y extrae:
    - Partido (match title)
    - Idioma (desde banderas)
    - Nombre de canal (desde atributos o texto)
    """
    soup = BeautifulSoup(html_content, "lxml")
    streams = []
    
    # Buscar todos los enlaces acestream://
    all_links = soup.find_all("a", href=re.compile(r"^acestream://"))
    
    print(f"  🔍 Encontrados {len(all_links)} enlaces acestream en {source_label}")
    
    for a in all_links:
        href = clean_text(a.get("href", ""))
        if not href.startswith("acestream://"):
            continue
        
        # Extraer idioma desde bandera
        lang = extract_lang_from_flag(a)
        
        # Extraer nombre de canal
        channel = extract_channel_name_from_a(a)
        
        # Si no se encontró nombre válido, usar "{LANG} STREAM"
        if is_bad_channel(channel):
            channel = f"{lang} STREAM"
        
        # Intentar inferir el partido desde el contexto HTML
        match_title = "Match"
        
        # Buscar en el contenedor padre
        parent = a.find_parent()
        if parent:
            # Buscar hermanos anteriores que puedan contener el título
            prev = parent.find_previous_sibling()
            if prev:
                prev_text = clean_text(prev.get_text())
                if prev_text and len(prev_text) > 5:
                    match_title = prev_text[:100]
            
            # Si no encontramos nada, buscar en el mismo padre
            if match_title == "Match":
                parent_text = clean_text(parent.get_text())
                # Extraer primera línea significativa
                lines = [l.strip() for l in parent_text.split('\n') if len(l.strip()) > 10]
                if lines:
                    match_title = lines[0][:100]
        
        streams.append({
            "match": match_title,
            "lang": lang,
            "channel": channel,
            "url": href,
        })
    
    return streams

def write_m3u(all_entries, out_path="lista.m3u"):
    """Genera archivo M3U con formato correcto"""
    m3u = ["#EXTM3U"]
    
    for e in all_entries:
        group = e.get("group", "Platinsport")
        match = e.get("match", "Match")
        lang = e.get("lang", "XX")
        channel = e.get("channel", "STREAM")
        url = e.get("url", "")
        
        # tvg-name incluye partido + idioma + canal
        tvg_name = f"{match} - [{lang}] {channel}"
        
        # Línea EXTINF con nombre de canal visible
        m3u.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{group}",{channel}')
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
                # CRÍTICO: Deshabilitar IPv6 para evitar ENETUNREACH
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
        
        # Agregar cookie de disclaimer
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
        
        # Bloquear peticiones problemáticas (first-id.fr, analytics, ads)
        def handle_route(route):
            url = route.request.url
            
            # Bloquear dominios conocidos que causan problemas IPv6
            blocked_domains = [
                "first-id.fr",
                "google-analytics.com",
                "googletagmanager.com",
                "doubleclick.net",
                "facebook.com",
                "analytics.",
                "advertising.",
            ]
            
            if any(domain in url for domain in blocked_domains):
                route.abort()
            else:
                route.continue_()
        
        page.route("**/*", handle_route)
        
        print(f"🌐 Cargando {BASE_URL}...")
        
        try:
            # Cargar página con timeout extendido
            page.goto(BASE_URL, timeout=90000, wait_until="domcontentloaded")
            
            # Esperar a que aparezcan enlaces acestream (máx 20s)
            try:
                page.wait_for_selector("a[href^='acestream://']", timeout=20000)
                print("✅ Enlaces acestream detectados en DOM")
            except PlaywrightTimeout:
                print("⚠️ Timeout esperando enlaces, parseando DOM actual...")
            
            # Esperar carga completa de red (opcional, máx 15s)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeout:
                print("⚠️ Timeout networkidle, continuando...")
            
            # Obtener HTML completo
            html_content = page.content()
            
            # Guardar HTML para debug
            with open("debug/main_page.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            
            print(f"✅ HTML capturado ({len(html_content)} bytes)")
            
            # Parsear streams desde el HTML
            streams = parse_streams_from_html(html_content, "página principal")
            
            # Agregar streams al listado final
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
    
    # Validación mínima
    if len(all_entries) < 5:
        print("❌ Muy pocos streams encontrados. Revisa debug/main_page.html")
        sys.exit(1)
    
    # Generar M3U
    write_m3u(all_entries, "lista.m3u")
    
    print("\n✅ Proceso completado exitosamente")

if __name__ == "__main__":
    main()

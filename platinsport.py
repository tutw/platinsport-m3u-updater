from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta
import os
import sys
import html

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

def parse_html_for_streams(html_content: str):
    """Parsea el HTML y extrae informacion de streams"""
    soup = BeautifulSoup(html_content, "lxml")
    entries = []
    
    # Buscar todas las secciones de partidos
    match_sections = soup.find_all("div", class_="match-title-bar")
    
    for match_div in match_sections:
        # Extraer titulo del partido
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
            
            # Extraer nombre del canal (el texto despues de la bandera)
            a_copy = BeautifulSoup(str(a), "lxml").find("a")
            if not a_copy:
                continue
                
            # Eliminar todas las etiquetas de bandera
            for flag in a_copy.find_all("span", class_=re.compile(r"\bfi\b|\bfi-")):
                flag.decompose()
            
            # Obtener el texto limpio
            channel_name = clean_text(a_copy.get_text())
            
            # Si el nombre esta vacio o es generico, usar alternativas
            if not channel_name or channel_name in ["", "STREAM HD", "HD", "STREAM"]:
                channel_name = clean_text(a.get("title", ""))
                if not channel_name or channel_name in ["", "STREAM HD"]:
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
    
    print(f"Archivo {out_path} generado con {len(all_entries)} entradas")

def main():
    print("=" * 70)
    print("=== PLATINSPORT M3U UPDATER - VERSION CORREGIDA ===")
    print("=" * 70)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Inicio: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    os.makedirs("debug", exist_ok=True)

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
            java_script_enabled=True,  # Necesario para abrir popup
            ignore_https_errors=True,
        )
        
        # Cookie ANTES de navegar
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

        # CLAVE: Interceptar a nivel de contexto ANTES de abrir popup
        def handle_route(route, request):
            nonlocal raw_html
            
            if "source-list.php" in request.url:
                print(f"[4] Interceptando: {request.url}")
                
                response = route.fetch()
                body = response.text()
                
                raw_html = body
                print(f"[5] HTML capturado: {len(body)} bytes (ANTES de JavaScript)")
                
                # Guardar para debug
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
                
                # Esperar carga
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
        print("\n ERROR: No se pudo capturar el HTML")
        sys.exit(1)
    
    # Parsear el HTML
    print("\n" + "=" * 70)
    print("PARSEANDO STREAMS...")
    print("=" * 70)
    
    all_entries = parse_html_for_streams(raw_html)
    
    print(f"\nTotal streams encontrados: {len(all_entries)}")
    
    if len(all_entries) < 5:
        print(" ERROR: Muy pocos streams encontrados")
        sys.exit(1)

    # Eliminar duplicados por URL
    dedup = {}
    for e in all_entries:
        dedup[e["url"]] = e
    all_entries = list(dedup.values())
    
    print(f"Streams unicos: {len(all_entries)}")

    # Guardar el M3U
    write_m3u(all_entries, "lista.m3u")
    
    # Mostrar muestra
    print("\nMuestra de los primeros 10 canales:")
    for i, e in enumerate(all_entries[:10], 1):
        print(f"  {i}. [{e['lang']}] {e['channel']} - {e['match'][:40]}")
    
    print("\n" + "=" * 70)
    print(" PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    main()

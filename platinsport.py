from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime

url = "https://www.platinsport.com/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    page.goto(url, wait_until="networkidle", timeout=45000)

    # Espera extra si hay modal o carga dinámica (ajusta selector si sabes el ID del contenedor)
    try:
        page.wait_for_selector("div.myDiv1, div.button-group a[href^='acestream://']", timeout=15000)
    except:
        pass  # Si no aparece, continúa igual

    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "html.parser")

content_container = soup.find("div", class_="myDiv1") or soup.find("div", class_="myDiv") or soup.body

if not content_container:
    print("No se encontró contenedor principal")
    with open("lista.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n# No content found - likely JS dynamic load issue\n")
    exit(0)

m3u_lines = ["#EXTM3U"]

current_league = "Unknown League"

for elem in content_container.descendants:
    if elem.name == "p" and elem.get_text(strip=True):
        text = elem.get_text(strip=True)
        if len(text) > 5 and "http" not in text:
            current_league = text
            continue

    if elem.name == "div" and "match-title-bar" in elem.get("class", []):
        time_tag = elem.find("time")
        hora = "??:??"
        if time_tag and time_tag.get("datetime"):
            try:
                dt = datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
                hora = dt.strftime("%H:%M")
            except:
                pass
        match_text = elem.get_text(separator=" ", strip=True)
        match_name = re.sub(r"\d{2}:\d{2}", "", match_text).strip() or "Evento sin nombre"

    elif elem.name == "a" and elem.get("href", "").startswith("acestream://"):
        ace_link = elem["href"]
        flag_span = elem.find("span", class_=re.compile(r"^fi fi-"))
        lang_code = "XX"
        if flag_span and len(flag_span["class"]) >= 2:
            lang_code = flag_span["class"][1].split("-")[1].upper()

        channel = elem.get_text(strip=True).replace(flag_span.get_text("") if flag_span else "", "").strip() or "Canal desconocido"

        tvg_name = f"{match_name} - {hora} - [{lang_code}] {channel}"
        m3u_lines.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{current_league}",{ace_link}')

with open("lista.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines) + "\n")

print(f"lista.m3u generado - {len(m3u_lines)-1} streams encontrados")

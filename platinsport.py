import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

url = "https://www.platinsport.com/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
except Exception as e:
    print(f"Error al obtener la página: {e}")
    exit(1)

soup = BeautifulSoup(response.text, "html.parser")

# Buscamos el contenedor principal de los eventos
# En versiones recientes suele ser <div class="myDiv1"> o similar
content_container = soup.find("div", class_="myDiv1") or soup.find("div", class_="myDiv") or soup.body

if not content_container:
    print("No se encontró contenedor principal de eventos")
    exit(1)

m3u_lines = ["#EXTM3U"]

current_league = "Unknown League"

for elem in content_container.descendants:
    if elem.name == "p" and elem.get_text(strip=True):
        text = elem.get_text(strip=True)
        if len(text) > 5 and not text.startswith("http"):  # Evitar enlaces sueltos
            current_league = text
            continue

    if elem.name == "div" and "match-title-bar" in elem.get("class", []):
        time_tag = elem.find("time")
        if time_tag and time_tag.get("datetime"):
            dt_str = time_tag["datetime"]
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                hora = dt.strftime("%H:%M")
            except:
                hora = time_tag.get_text(strip=True) or "??:??"
        else:
            hora = "??:??"

        # Nombre del partido (todo el texto menos la hora)
        match_text = elem.get_text(separator=" ", strip=True)
        match_name = re.sub(r"\d{2}:\d{2}", "", match_text).strip()

    elif elem.name == "div" and "button-group" in elem.get("class", []):
        for link in elem.find_all("a", href=True):
            href = link["href"]
            if not href.startswith("acestream://"):
                continue

            ace_id = href.replace("acestream://", "").strip()

            # Bandera
            flag_span = link.find("span", class_=re.compile(r"^fi fi-"))
            if flag_span and len(flag_span["class"]) >= 2:
                flag_class = flag_span["class"][1]  # fi-XX
                lang_code = flag_class.split("-")[1].upper()
            else:
                lang_code = "XX"

            # Nombre del canal (texto después de la bandera)
            channel_parts = []
            for child in link.children:
                if child.name != "span" and hasattr(child, "strip") and child.strip():
                    channel_parts.append(child.strip())
            channel = " ".join(channel_parts).strip() or "Canal desconocido"

            if not match_name or match_name == "":
                match_name = "Evento sin nombre"

            tvg_name = f"{match_name} - {hora} - [{lang_code}] {channel}"
            m3u_lines.append(f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{current_league}",{href}')

# Escribir el archivo
try:
    with open("lista.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")
    print("lista.m3u generado correctamente")
except Exception as e:
    print(f"Error al escribir lista.m3u: {e}")
    exit(1)

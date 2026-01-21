import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

url = "https://www.platinsport.com/"

try:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
except Exception as e:
    print(f"Error al obtener la página: {e}")
    exit(1)

soup = BeautifulSoup(response.text, "html.parser")

# Buscamos la sección principal de contenido (ajustado según estructura típica del sitio)
content_div = soup.find("div", class_="myDiv1") or soup.find("div", class_="myDiv") or soup.body

if not content_div:
    print("No se encontró la sección de contenido principal")
    exit(1)

m3u_lines = ["#EXTM3U"]

current_group = "Uncategorized"
current_event = ""
current_time = ""

for elem in content_div.descendants:
    if elem.name == "p" and elem.get_text(strip=True):
        # Nueva categoría / liga
        text = elem.get_text(strip=True)
        if text and not re.match(r"^\d{2}:\d{2}$", text):  # Evitar que hora suelta se tome como grupo
            current_group = text

    elif elem.name == "div" and "match-title-bar" in elem.get("class", []):
        # Título del partido + hora
        time_tag = elem.find("time")
        if time_tag and time_tag.get("datetime"):
            dt = datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
            current_time = dt.strftime("%H:%M")
        else:
            current_time = "??:??"

        # Nombre del partido (texto después de time o todo el texto)
        event_text = elem.get_text(strip=True)
        if time_tag:
            event_text = event_text.replace(time_tag.get_text(strip=True), "").strip()
        current_event = event_text or "Evento sin nombre"

    elif elem.name == "a" and elem.get("href", "").startswith("acestream://"):
        # Enlace Acestream válido
        ace_hash = elem["href"]
        
        # Bandera / idioma
        flag_span = elem.find("span", class_=re.compile(r"^fi fi-"))
        lang_code = "XX"
        if flag_span and len(flag_span["class"]) > 1:
            fi_class = [c for c in flag_span["class"] if c.startswith("fi-")]
            if fi_class:
                lang_code = fi_class[0].split("-")[1].upper()

        # Nombre del canal (texto del <a> sin la bandera)
        channel_text = elem.get_text(strip=True)
        if flag_span:
            channel_text = channel_text.replace(flag_span.get_text(strip=True), "").strip()
        channel_text = channel_text or "Canal desconocido"

        # Línea EXTINF
        tvg_name = f"{current_event} - {current_time} - [{lang_code}] {channel_text}"
        line = f'#EXTINF:-1 tvg-name="{tvg_name}" group-title="{current_group}",{ace_hash}'
        m3u_lines.append(line)

# Si no hay enlaces encontrados → mensaje de error en el archivo
if len(m3u_lines) <= 1:
    m3u_lines.append("# No se encontraron enlaces Acestream en la página actual")
    print("Advertencia: No se detectaron enlaces acestream://")

# Guardar
with open("lista.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

print(f"lista.m3u generado/actualizado con {len(m3u_lines)-1} entradas")

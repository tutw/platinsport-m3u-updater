import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import xml.etree.ElementTree as ET

URL = 'https://tarjetarojaenvivo.lat'

# Mapeo de canales (ya validado)
channel_names = {
    # (Tu mapeo de canales aquí)
}

# Configuración del navegador
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

try:
    # Inicializar el navegador
    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(URL)
    
    # Esperar y extraer contenido
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, 'textarea'))
    )
    textarea = driver.find_element(By.TAG_NAME, 'textarea')
    content = textarea.get_attribute('value').strip()
    
except Exception as e:
    print(f"Error crítico: {e}")
    exit(1)
finally:
    driver.quit()

# Procesar el contenido
events = []
event_pattern = re.compile(
    r'(\d{2}-\d{2}-\d{4}) \((\d{2}:\d{2})\) (.+?) : (.+?) ((?:\(CH\d+\w*\)\s*)+)',
    re.MULTILINE
)

for line in content.splitlines():
    line = line.strip()
    if not line or line.startswith("'"):
        continue
    
    match = event_pattern.match(line)
    if not match:
        print(f"Formato no reconocido: {line}")
        continue
    
    date, time_str, league, teams, remaining_part = match.groups()
    
    # Extraer todos los canales de la parte restante
    channel_numbers = re.findall(r'\(CH(\d+)', remaining_part)
    
    if not channel_numbers:
        print(f"No se encontraron canales válidos en la línea: '{line}'")
        continue
    
    # Crear el evento con todos los canales
    event = {
        'datetime': f"{date} {time_str}",
        'league': league.strip(),
        'teams': teams.strip(),
        'channels': []
    }
    
    for channel in channel_numbers:
        name = channel_names.get(channel, f"Canal {channel}")
        event['channels'].append({
            'channel_name': name,
            'channel_id': channel,
            'url': f"{URL}/player/1/{channel}"
        })
    
    events.append(event)

# Crear XML
root = ET.Element('events')
for event in events:
    event_elem = ET.SubElement(root, 'event')
    ET.SubElement(event_elem, 'datetime').text = event['datetime']
    ET.SubElement(event_elem, 'league').text = event['league']
    ET.SubElement(event_elem, 'teams').text = event['teams']
    
    channels_elem = ET.SubElement(event_elem, 'channels')
    for channel in event['channels']:
        channel_elem = ET.SubElement(channels_elem, 'channel')
        ET.SubElement(channel_elem, 'channel_name').text = channel['channel_name']
        ET.SubElement(channel_elem, 'channel_id').text = channel['channel_id']
        ET.SubElement(channel_elem, 'url').text = channel['url']

# Formatear XML
def indent(elem, level=0):
    i = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not subelem.tail or not elem.tail.strip():
            subelem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

indent(root)
tree = ET.ElementTree(root)
tree.write('lista_reproductor_web.xml', encoding='utf-8', xml_declaration=True)

# Crear M3U
with open('lista_reproductor_web.m3u', 'w', encoding='utf-8') as f:
    f.write('#EXTM3U\n')
    for event in events:
        for channel in event['channels']:
            f.write(
                f'#EXTINF:-1,{event["datetime"]} - {event["league"]} - {event["teams"]} - {channel["channel_name"]}\n'
                f'{channel["url"]}\n'
            )

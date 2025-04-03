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

# Mapeo de números de canal a nombres de canal (tu diccionario ya está bien)
channel_names = { ... }  # (tu diccionario completo aquí)

# Configurar opciones de Chrome
chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Usar headless=new para Chrome 115+
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

# Iniciar el navegador Chrome
service = ChromeService(executable_path=ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    driver.get(URL)
    
    # Esperar hasta 30 segundos para que el textarea esté presente
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, 'textarea'))
    )

    # Obtener el contenido del textarea
    textarea = driver.find_element(By.TAG_NAME, 'textarea')
    textarea_content = textarea.get_attribute('value').strip()

    # Verificar si el contenido está vacío
    if not textarea_content:
        raise ValueError("El textarea está vacío")

except Exception as e:
    print(f"Error crítico: {str(e)}")
    driver.quit()
    exit(1)

finally:
    driver.quit()

# Analizar el contenido del textarea con regex ajustada
events = []
event_pattern = re.compile(
    r'^(\d{2}-\d{2}-\d{4}) \((\d{2}:\d{2})\) (.+?) : (.+?)\s*(\(CH\w+\)\s*)*$',
    re.MULTILINE
)

for line in textarea_content.splitlines():
    line = line.strip()
    if not line or line.startswith("'"):
        continue  # Ignorar líneas vacías o comentarios

    match = event_pattern.match(line)
    if match:
        date, time_str, league, teams, channels_part = match.groups()
        
        # Extraer solo los números de canal (ignorar letras como 'es', 'fr', etc.)
        channel_numbers = re.findall(r'CH(\d+)', channels_part)
        
        for channel in channel_numbers:
            channel_name = channel_names.get(channel, f'Channel {channel}')
            events.append({
                'datetime': f"{date} {time_str}",
                'league': league.strip(),
                'teams': teams.strip(),
                'channel_name': channel_name,
                'channel_id': channel,
                'url': f'{URL}/player/1/{channel}'
            })
    else:
        print(f"Formato no reconocido en línea: '{line}'")

# Verificar los datos obtenidos
if not events:
    print("No events found.")
else:
    print(f"Found {len(events)} events.")

# Función para formatear el XML
def indent(elem, level=0):
    i = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not subelem.tail or not subelem.tail.strip():
            subelem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

# Crear archivo XML
root = ET.Element('events')
for event in events:
    event_elem = ET.SubElement(root, 'event')
    ET.SubElement(event_elem, 'datetime').text = event['datetime']
    ET.SubElement(event_elem, 'league').text = event['league']
    ET.SubElement(event_elem, 'teams').text = event['teams']
    ET.SubElement(event_elem, 'channel_name').text = event['channel_name']
    ET.SubElement(event_elem, 'url').text = event['url']

indent(root)
tree = ET.ElementTree(root)
tree.write('lista_reproductor_web.xml', encoding='utf-8', xml_declaration=True)

# Crear archivo M3U
with open('lista_reproductor_web.m3u', 'w', encoding='utf-8') as m3u_file:
    m3u_file.write('#EXTM3U\n')
    for event in events:
        m3u_file.write(
            f'#EXTINF:-1,{event["datetime"]} - {event["league"]} - {event["teams"]} - {event["channel_name"]}\n'
            f'{event["url"]}\n'
        )

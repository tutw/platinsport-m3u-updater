import requests
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import xml.etree.ElementTree as ET

URL = 'https://tarjetarojaenvivo.lat'

# Configurar opciones de Chrome
chrome_options = Options()
chrome_options.add_argument("--headless")  # Ejecutar en modo headless (sin interfaz gráfica)
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

# Iniciar el navegador Chrome
service = ChromeService(executable_path=ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Navegar a la URL
driver.get(URL)
time.sleep(5)  # Esperar a que la página cargue completamente

# Obtener el contenido de la página
page_content = driver.page_source

# Cerrar el navegador
driver.quit()

# Analizar el contenido con regex
events = []  # Lista donde almacenaremos los eventos
event_pattern = re.compile(r'(\d{2}-\d{2}-\d{4}) \((\d{2}:\d{2})\) (.+?) : (.+?)  \((.+?)\)')

for line in page_content.splitlines():
    match = event_pattern.search(line)
    if match:
        date, time, league, teams, channels = match.groups()
        channel_list = channels.split(') (')
        for channel in channel_list:
            channel = channel.replace('(', '').replace(')', '')
            events.append({
                'datetime': f"{date} {time}",
                'league': league,
                'teams': teams,
                'channel_name': channel,
                'channel_id': None,
                'url': f'{URL}/player/{channel.split("CH")[1]}/1' if 'CH' in channel else None
            })

# Verificar los datos obtenidos
if not events:
    print("No events found.")
else:
    print(f"Found {len(events)} events.")

# Crear el archivo XML
root = ET.Element('events')

for event in events:
    event_element = ET.SubElement(root, 'event')
    ET.SubElement(event_element, 'datetime').text = event['datetime']
    ET.SubElement(event_element, 'league').text = event['league']
    ET.SubElement(event_element, 'teams').text = event['teams']
    ET.SubElement(event_element, 'channel_name').text = event['channel_name']
    ET.SubElement(event_element, 'url').text = event['url']

tree = ET.ElementTree(root)
tree.write('lista_reproductor_web.xml', encoding='utf-8', xml_declaration=True)

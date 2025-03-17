import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import xml.etree.ElementTree as ET

URL = 'https://tarjetarojaenvivo.lat'

# Mapeo de números de canal a nombres de canal
channel_names = {
    '53': 'ES LALIGA HYPERMOTION',
    '109': 'VTV plus',
    '74': 'GOL español',
    '75': 'TNT sport arg',
    '76': 'ESPN Premium',
    '87': 'ESPN1',
    '170': 'EXTRA SPORT16',
    '171': 'EXTRA SPORT17',
    '172': 'EXTRA SPORT18',
    '160': 'EXTRA SPORT6',
    '173': 'EXTRA SPORT19',
    '86': 'Zapping sports',
    '4': 'beIN max 4',
    '162': 'EXTRA SPORT8',
    '163': 'EXTRA SPORT9',
    '174': 'EXTRA SPORT20',
    '101': 'FOXsport1MX',
    '164': 'EXTRA SPORT10',
    '1': 'beIN 1',
    '166': 'EXTRA SPORT12',
    '167': 'EXTRA SPORT13',
    '168': 'EXTRA SPORT14',
    '169': 'EXTRA SPORT15',
    # Agrega más números de canal y sus nombres correspondientes según sea necesario
}

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
            channel_number = re.search(r'\d+', channel).group()
            channel_name = channel_names.get(channel_number, f'Channel {channel_number}')
            events.append({
                'datetime': f"{date} {time}",
                'league': league,
                'teams': teams,
                'channel_name': channel_name,
                'channel_id': channel_number,
                'url': f'{URL}/player/1/{channel_number}'
            })

# Verificar los datos obtenidos
if not events:
    print("No events found.")
else:
    print(f"Found {len(events)} events.")

# Helper function to add indentation to XML
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level+1)
        if not subelem.tail or not subelem.tail.strip():
            subelem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

# Crear el archivo XML
root = ET.Element('events')

for event in events:
    event_element = ET.SubElement(root, 'event')
    ET.SubElement(event_element, 'datetime').text = event['datetime']
    ET.SubElement(event_element, 'league').text = event['league']
    ET.SubElement(event_element, 'teams').text = event['teams']
    ET.SubElement(event_element, 'channel_name').text = event['channel_name']
    ET.SubElement(event_element, 'url').text = event['url']

indent(root)  # Llamar a la función de sangría para formatear el XML

tree = ET.ElementTree(root)
tree.write('lista_reproductor_web.xml', encoding='utf-8', xml_declaration=True)

# Crear el archivo M3U
with open('lista_reproductor_web.m3u', 'w', encoding='utf-8') as m3u_file:
    m3u_file.write('#EXTM3U\n')
    for event in events:
        m3u_file.write(f'#EXTINF:-1,{event["datetime"]} - {event["league"]} - {event["teams"]} - {event["channel_name"]}\n')
        m3u_file.write(f'{event["url"]}\n')

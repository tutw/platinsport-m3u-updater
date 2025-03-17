import requests
import re
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

URL = 'https://tarjetarojaenvivo.lat'
response = requests.get(URL)
if response.status_code != 200:
    raise Exception(f"Error fetching the page: {response.status_code}")

soup = BeautifulSoup(response.content, 'html.parser')

events = []  # Lista donde almacenaremos los eventos

# Patrón regex para extraer eventos
event_pattern = re.compile(r'(\d{2}-\d{2}-\d{4}) \((\d{2}:\d{2})\) (.+?) : (.+?)  \((.+?)\)')

# Buscar eventos en el texto de la página
for line in soup.stripped_strings:
    match = event_pattern.match(line)
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

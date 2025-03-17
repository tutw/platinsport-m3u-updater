import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime

URL = 'https://tarjetarojaenvivo.lat'
response = requests.get(URL)
soup = BeautifulSoup(response.content, 'html.parser')

events = []  # Lista donde almacenaremos los eventos

# Aquí debes adaptar el scraping según la estructura del HTML del sitio web
for event in soup.find_all('div', class_='event'):
    date_time = event.find('span', class_='datetime').text
    league = event.find('span', class_='league').text
    teams = event.find('span', class_='teams').text
    channels = event.find_all('span', class_='channel')
    
    for channel in channels:
        channel_name = channel.get('data-name')
        channel_id = channel.get('data-id')
        events.append({
            'datetime': date_time,
            'league': league,
            'teams': teams,
            'channel_name': channel_name,
            'channel_id': channel_id,
            'url': f'{URL}/player/1/{channel_id}'
        })

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

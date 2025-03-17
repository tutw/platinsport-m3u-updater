import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime

URL = 'https://tarjetarojaenvivo.lat'
response = requests.get(URL)
if response.status_code != 200:
    raise Exception(f"Error fetching the page: {response.status_code}")

soup = BeautifulSoup(response.content, 'html.parser')

events = []  # Lista donde almacenaremos los eventos

# Aquí debes adaptar el scraping según la estructura del HTML del sitio web
for event in soup.find_all('div', class_='event'):
    date_time_element = event.find('span', class_='datetime')
    league_element = event.find('span', class_='league')
    teams_element = event.find('span', class_='teams')
    channels = event.find_all('span', class_='channel')
    
    if date_time_element and league_element and teams_element and channels:
        date_time = date_time_element.text.strip()
        league = league_element.text.strip()
        teams = teams_element.text.strip()
        
        for channel in channels:
            channel_name = channel.get('data-name')
            channel_id = channel.get('data-id')
            if channel_name and channel_id:
                events.append({
                    'datetime': date_time,
                    'league': league,
                    'teams': teams,
                    'channel_name': channel_name,
                    'channel_id': channel_id,
                    'url': f'{URL}/player/1/{channel_id}'
                })
    else:
        print(f"Missing data in event: {event}")

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

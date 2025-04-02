import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# URL del sitio a scrapear
url = "https://deporte-libre.fans"

# Realizar la solicitud HTTP al sitio web
response = requests.get(url)
response.raise_for_status()

# Parsear el contenido HTML con BeautifulSoup
soup = BeautifulSoup(response.content, 'html.parser')

# Buscar la sección de eventos utilizando el ID 'agenda'
events_section = soup.find('div', id='agenda')

# Verificar si events_section no es None
if events_section is None:
    raise ValueError("No se encontró la sección de eventos. Verifica el ID y la estructura del HTML.")

events = events_section.find_all('div', class_='event')

# Cargar los datos existentes de lista_canales_DEPORTE-LIBRE.FANS.xml
channels_tree = ET.parse('lista_canales_DEPORTE-LIBRE.FANS.xml')
channels_root = channels_tree.getroot()

# Crear un nuevo árbol XML para la lista de agenda
agenda_root = ET.Element('agenda')

for event in events:
    event_name = event.find('h3').text
    event_time = event.find('span', class_='event-time').text
    event_datetime = datetime.strptime(event_time, '%H:%M') + timedelta(hours=1)  # Convertir a GMT+1
    event_channels = event.find_all('a', class_='stream-link')
    
    for channel in event_channels:
        channel_name = channel.text
        channel_url = channel['href']
        
        # Buscar el logo correspondiente en lista_canales_DEPORTE-LIBRE.FANS.xml
        logo_url = ''
        for ch in channels_root.findall('channel'):
            if ch.find('name').text == channel_name:
                logo_url = ch.find('logo').text
                break
        
        # Crear un nuevo elemento en el XML de agenda
        event_element = ET.SubElement(agenda_root, 'event')
        name_element = ET.SubElement(event_element, 'name')
        name_element.text = event_name
        time_element = ET.SubElement(event_element, 'time')
        time_element.text = event_datetime.strftime('%H:%M')
        channel_element = ET.SubElement(event_element, 'channel')
        channel_name_element = ET.SubElement(channel_element, 'name')
        channel_name_element.text = channel_name
        channel_url_element = ET.SubElement(channel_element, 'url')
        channel_url_element.text = channel_url
        logo_element = ET.SubElement(channel_element, 'logo')
        logo_element.text = logo_url

# Guardar el árbol XML de agenda en un archivo
agenda_tree = ET.ElementTree(agenda_root)
with open('lista_agenda_DEPORTE-LIBRE.FANS.xml', 'wb') as f:
    agenda_tree.write(f, encoding='utf-8', xml_declaration=True)

print("La lista de agenda ha sido actualizada exitosamente.")

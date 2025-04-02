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

# Buscar todas las filas de eventos y canales
event_rows = soup.find_all('tr', class_='event-row')
channel_rows = soup.find_all('tr', class_='channel-row')

# Verificar si se encontraron filas de eventos y canales
if not event_rows or not channel_rows:
    raise ValueError("No se encontraron filas de eventos o canales en el HTML.")

# Cargar los datos existentes de lista_canales_DEPORTE-LIBRE.FANS.xml
channels_tree = ET.parse('lista_canales_DEPORTE-LIBRE.FANS.xml')
channels_root = channels_tree.getroot()

# Crear un nuevo árbol XML para la lista de agenda
agenda_root = ET.Element('agenda')

# Iterar sobre las filas de eventos y canales
for event_row, channel_row in zip(event_rows, channel_rows):
    event_time = event_row.find('div', class_='event-time').find('strong').text
    event_info = event_row.find('div', class_='event-info').text

    event_datetime = datetime.strptime(event_time, '%H:%M') + timedelta(hours=1)  # Convertir a GMT+1

    # Crear un nuevo elemento en el XML de agenda
    event_element = ET.SubElement(agenda_root, 'event')
    name_element = ET.SubElement(event_element, 'name')
    name_element.text = event_info
    time_element = ET.SubElement(event_element, 'time')
    time_element.text = event_datetime.strftime('%H:%M')

    # Buscar canales asociados al evento
    channels = channel_row.find_all('a', class_='channel-button-small')
    for channel in channels:
        channel_name = channel.text
        channel_url = channel['href']

        # Buscar el logo correspondiente en lista_canales_DEPORTE-LIBRE.FANS.xml
        logo_url = ''
        for ch in channels_root.findall('channel'):
            if ch.find('name').text == channel_name:
                logo_url = ch.find('logo').text
                break

        # Crear un nuevo elemento de canal en el XML de agenda
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

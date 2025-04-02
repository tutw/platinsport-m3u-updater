from bs4 import BeautifulSoup
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# URL del sitio a scrapear
url = "https://deporte-libre.fans/schedule/"

# Realizar una solicitud HTTP para obtener el contenido de la página
response = requests.get(url)
response.raise_for_status()  # Asegurarse de que la solicitud fue exitosa

# Parsear el contenido HTML usando BeautifulSoup
soup = BeautifulSoup(response.text, 'html.parser')

# Imprimir el contenido de la página para verificar la estructura HTML
print("Contenido del HTML:")
print(soup.prettify())

# Buscar todas las filas de eventos y canales
event_rows = soup.find_all('tr', class_='event-row')
channel_rows = soup.find_all('tr', class_='channel-row')

# Verificar si se encontraron filas de eventos y canales
if not event_rows or not channel_rows:
    raise ValueError("No se encontraron filas de eventos o canales en el HTML.")

# Imprimir las clases de las filas encontradas para depuración
print("Clases de filas de eventos encontradas:")
for row in event_rows:
    print(row.get('class'))

print("Clases de filas de canales encontradas:")
for row in channel_rows:
    print(row.get('class'))

# Crear un nuevo árbol XML para la lista de agenda
agenda_root = ET.Element('agenda')

# Iterar sobre las filas de eventos y canales
for event_row, channel_row in zip(event_rows, channel_rows):
    try:
        event_time = event_row.find('div', class_='event-time').find('strong').text.strip()
        event_info = event_row.find('div', class_='event-info').text.strip()
    except AttributeError as e:
        print("Error al obtener datos del evento:", e)
        continue

    # Convertir el horario a datetime (se suma 1 hora para ajustar a GMT+1, si es necesario)
    event_datetime = datetime.strptime(event_time, '%H:%M') + timedelta(hours=1)

    # Crear un nuevo elemento en el XML de agenda
    event_element = ET.SubElement(agenda_root, 'event')
    name_element = ET.SubElement(event_element, 'name')
    name_element.text = event_info
    time_element = ET.SubElement(event_element, 'time')
    time_element.text = event_datetime.strftime('%H:%M')

    # Buscar canales asociados al evento
    channels = channel_row.find_all('a', class_='channel-button-small')
    for channel in channels:
        channel_name = channel.text.strip()
        channel_url = channel.get('href', '').strip()

        # Crear un nuevo elemento de canal en el XML de agenda
        channel_element = ET.SubElement(event_element, 'channel')
        channel_name_element = ET.SubElement(channel_element, 'name')
        channel_name_element.text = channel_name
        channel_url_element = ET.SubElement(channel_element, 'url')
        channel_url_element.text = channel_url

# Guardar el árbol XML de agenda en un archivo
agenda_tree = ET.ElementTree(agenda_root)
with open('lista_agenda_DEPORTE-LIBRE.FANS.xml', 'wb') as f:
    agenda_tree.write(f, encoding='utf-8', xml_declaration=True)

print("La lista de agenda ha sido actualizada exitosamente.")

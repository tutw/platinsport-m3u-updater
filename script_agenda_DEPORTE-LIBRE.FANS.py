import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# URL base del sitio
base_url = "https://deporte-libre.fans"

# Endpoints JSON
endpoints = [
    "/schedule/schedule-generated.php",
    "/schedule/schedule-extra-generated.json",
    "/schedule/extra2-schedule-2.php"
]

# Función para obtener datos desde un endpoint JSON
def fetch_json_data(endpoint):
    try:
        response = requests.get(base_url + endpoint)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        print(f"Error: {err} for endpoint: {endpoint}")
        return None

# Función para obtener la URL del reproductor principal desde una página HTML
def fetch_player_url(channel_url):
    try:
        response = requests.get(channel_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        iframe = soup.find("iframe")
        if iframe and 'src' in iframe.attrs:
            return iframe['src']
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")
    return None

# Función para obtener los datos de los canales y logos
def fetch_channel_data():
    response = requests.get("https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/lista_canales_DEPORTE-LIBRE.FANS.xml")
    response.raise_for_status()
    channels_tree = ET.fromstring(response.content)
    channels_data = {}
    for channel in channels_tree.findall('channel'):
        name = channel.attrib['name']
        urls = [url.text for url in channel.findall('url')]
        logo = channel.find('logo').text if channel.find('logo') is not None else None
        channels_data[name] = {
            'urls': urls,
            'logo': logo
        }
    return channels_data

# Crear un nuevo árbol XML para la lista de agenda
agenda_root = ET.Element('agenda')

# Obtener los datos de los canales y logos
channels_data = fetch_channel_data()

# Iterar sobre los endpoints y procesar los datos
for endpoint in endpoints:
    json_data = fetch_json_data(endpoint)
    
    # Continuar con el siguiente endpoint si hubo un error
    if json_data is None:
        continue
    
    # Imprimir los datos JSON obtenidos para verificar su estructura
    print(f"Datos obtenidos de {endpoint}:")
    print(json_data)
    
    for day, day_data in json_data.items():
        for category, events in day_data.items():
            for event in events:
                event_time = event['time']
                event_info = event['event']
                
                # Convertir el horario a datetime (se suma 1 hora para ajustar a GMT+1, si es necesario)
                event_datetime = datetime.strptime(event_time, '%H:%M') + timedelta(hours=2)
                
                # Crear un nuevo elemento en el XML de agenda
                event_element = ET.SubElement(agenda_root, 'event')
                name_element = ET.SubElement(event_element, 'name')
                name_element.text = event_info
                time_element = ET.SubElement(event_element, 'time')
                time_element.text = event_datetime.strftime('%H:%M')
                
                # Crear elementos para los canales asociados al evento
                url_set = set()  # Conjunto para almacenar URLs únicas
                for channel in event.get('channels', []):
                    # Validar que `channel` es un diccionario
                    if isinstance(channel, dict):
                        channel_name = channel.get('channel_name', 'Desconocido')
                        channel_id = channel.get('channel_id', '0')
                        channel_url = f"{base_url}/stream/stream-{channel_id}.php"
                        
                        # Obtener la URL del reproductor principal
                        player_url = fetch_player_url(channel_url)
                        
                        # Crear un nuevo elemento de canal en el XML de agenda
                        if player_url and player_url not in url_set:
                            channel_element = ET.SubElement(event_element, 'channel')
                            channel_name_element = ET.SubElement(channel_element, 'name')
                            channel_name_element.text = channel_name
                            channel_url_element = ET.SubElement(channel_element, 'url')
                            channel_url_element.text = player_url
                            url_set.add(player_url)
                            
                            # Añadir URLs adicionales y logo si coinciden los canales
                            if channel_name in channels_data:
                                for extra_url in channels_data[channel_name]['urls']:
                                    if extra_url not in url_set:
                                        extra_url_element = ET.SubElement(channel_element, 'url')
                                        extra_url_element.text = extra_url
                                        url_set.add(extra_url)
                                if channels_data[channel_name]['logo']:
                                    logo_element = ET.SubElement(channel_element, 'logo')
                                    logo_element.text = channels_data[channel_name]['logo']

# Función para indentar el árbol XML
def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

# Indentar el árbol XML para mejorar la legibilidad
indent(agenda_root)

# Guardar el árbol XML de agenda en un archivo
agenda_tree = ET.ElementTree(agenda_root)
with open('lista_agenda_DEPORTE-LIBRE.FANS.xml', 'wb') as f:
    agenda_tree.write(f, encoding='utf-8', xml_declaration=True)

print("La lista de agenda ha sido actualizada exitosamente.")

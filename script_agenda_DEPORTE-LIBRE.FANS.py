import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

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
    response = requests.get(base_url + endpoint)
    response.raise_for_status()
    return response.json()

# Crear un nuevo árbol XML para la lista de agenda
agenda_root = ET.Element('agenda')

# Iterar sobre los endpoints y procesar los datos
for endpoint in endpoints:
    json_data = fetch_json_data(endpoint)
    
    # Imprimir los datos JSON obtenidos para verificar su estructura
    print(f"Datos obtenidos de {endpoint}:")
    print(json_data)
    
    for day, day_data in json_data.items():
        for category, events in day_data.items():
            for event in events:
                event_time = event['time']
                event_info = event['event']
                
                # Convertir el horario a datetime (se suma 1 hora para ajustar a GMT+1, si es necesario)
                event_datetime = datetime.strptime(event_time, '%H:%M') + timedelta(hours=1)
                
                # Crear un nuevo elemento en el XML de agenda
                event_element = ET.SubElement(agenda_root, 'event')
                name_element = ET.SubElement(event_element, 'name')
                name_element.text = event_info
                time_element = ET.SubElement(event_element, 'time')
                time_element.text = event_datetime.strftime('%H:%M')
                
                # Crear elementos para los canales asociados al evento
                for channel in event.get('channels', []):
                    channel_name = channel['channel_name']
                    channel_id = channel['channel_id']
                    channel_url = f"{base_url}/stream/stream-{channel_id}.php"
                    
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

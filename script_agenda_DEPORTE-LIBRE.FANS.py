import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Suponiendo que day_data, base_url, channels_data y agenda_root están definidos antes

def fetch_player_url(channel_url):
    # Implementa aquí la lógica para obtener la URL del reproductor principal
    # Por ejemplo, podrías hacer un requests.get y extraer la url del contenido devuelto
    # Retorna una cadena con la URL o None si no se puede obtener
    return channel_url  # Solo ejemplo, reemplaza según tu necesidad

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

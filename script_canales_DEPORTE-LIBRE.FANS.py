import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# URL principal para scrapear
main_url = 'https://deporte-libre.fans/en-vivo-online/+canales/'

# Función para obtener el contenido HTML de una URL
def get_html(url):
    print(f"Fetching URL: {url}")
    response = requests.get(url, timeout=10)  # Agregar un tiempo límite
    response.raise_for_status()  # Levantar una excepción para códigos de estado HTTP 4xx/5xx
    return response.text

# Función para scrapear la página principal y obtener los nombres de los canales y sus URLs
def get_channel_list(main_url):
    html = get_html(main_url)
    soup = BeautifulSoup(html, 'html.parser')
    
    channel_list = []
    for a_tag in soup.find_all('a'):
        channel_name = a_tag.text.strip()
        channel_url = a_tag.get('href')
        if channel_name and channel_url and channel_url.startswith('/stream/'):
            channel_list.append((channel_name, 'https://deporte-libre.fans' + channel_url))
    
    print(f"Found {len(channel_list)} channels")
    return channel_list

# Función para obtener los enlaces de streaming de cada canal
def get_streaming_urls(channel_url):
    base_url = 'https://deporte-libre.fans'
    html = get_html(channel_url)
    soup = BeautifulSoup(html, 'html.parser')
    
    streaming_urls = []
    for a_tag in soup.find_all('a', {'class': 'btn btn-md'}):
        streaming_url = a_tag.get('href')
        if streaming_url.startswith('/'):
            streaming_url = base_url + streaming_url
        streaming_urls.append(streaming_url)
    
    return streaming_urls

# Función para guardar los resultados en un archivo XML
def save_to_xml(channel_data, output_path):
    root = ET.Element('channels')
    for channel_name, streaming_urls in channel_data.items():
        channel_element = ET.SubElement(root, 'channel', name=channel_name)
        for url in streaming_urls:
            ET.SubElement(channel_element, 'url').text = url
    
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)

# Scrapeamos la lista de canales
print("Starting to scrape the channel list")
channel_list = get_channel_list(main_url)

# Obtenemos los enlaces de streaming para cada canal
channel_data = {}
for channel_name, channel_url in channel_list:
    try:
        streaming_urls = get_streaming_urls(channel_url)
        channel_data[channel_name] = streaming_urls
    except requests.RequestException as e:
        print(f"Error fetching streaming URLs for channel {channel_name}: {e}")

# Guardamos los resultados en un archivo XML con un nombre fijo
output_path = 'lista_canales_DEPORTE-LIBRE.FANS.xml'
save_to_xml(channel_data, output_path)

print(f'Resultados guardados en {output_path}')

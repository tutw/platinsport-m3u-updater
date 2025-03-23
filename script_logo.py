import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re

# URLs to scrape
urls = [
    "https://github.com/tv-logo/tv-logos/tree/main/countries/albania",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/argentina",
    # Agrega el resto de las URLs aquí...
]

# Function to scrape logos from a given URL
def scrape_logos(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    logos = []
    for a_tag in soup.find_all('a', class_='Link--primary'):
        img_url = a_tag.get('href')
        if img_url and img_url.endswith('.png'):
            channel_name = re.sub(r'\.png$', '', a_tag.text)
            raw_url = 'https://raw.githubusercontent.com' + img_url.replace('/blob', '')
            logos.append((channel_name, raw_url))
    return logos

# Create XML structure
root = ET.Element("logos")

for url in urls:
    logos = scrape_logos(url)
    for channel_name, img_url in logos:
        logo_element = ET.SubElement(root, "logo")
        name_element = ET.SubElement(logo_element, "name")
        name_element.text = channel_name
        url_element = ET.SubElement(logo_element, "url")
        url_element.text = img_url

# Write to logos.xml
tree = ET.ElementTree(root)
with open("logos.xml", "wb") as xml_file:
    tree.write(xml_file, encoding='utf-8', xml_declaration=True)

print("Logos scraped and saved to logos.xml")

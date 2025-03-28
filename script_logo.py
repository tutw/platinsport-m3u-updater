import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re

# URLs to scrape
urls = [
    "https://github.com/tv-logo/tv-logos/tree/main/countries/albania",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/argentina",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/australia",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/austria",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/azerbaijan",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/belgium",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/brazil",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/bulgaria",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/canada",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/caribbean",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/costa-rica",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/croatia",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/czech-republic",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/france",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/germany",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/greece",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/hong-kong",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/hungary",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/india",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/indonesia",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/international",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/israel",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/italy",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/lebanon",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/lithuania",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/malaysia",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/malta",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/mexico",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/netherlands",
    "https://github.com/tv-logo/tv-logos/tree/main/countries/new-zealand"
]

# Function to scrape logos from a given URL
def scrape_logos(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    logos = []
    for a_tag in soup.find_all('a', class_='Link--primary'):
        img_url = a_tag.get('href')
        if img_url and img_url.endswith('.png'):
            channel_name = re.sub(r'-[a-z]{2}\.png$', '', a_tag.text)
            raw_url = 'https://raw.githubusercontent.com' + img_url.replace('/blob', '')
            logos.append((channel_name, raw_url))
    return logos

# Create XML structure
root = ET.Element("logos")
unique_logos = set()

for url in urls:
    logos = scrape_logos(url)
    for channel_name, img_url in logos:
        if (channel_name, img_url) not in unique_logos:
            unique_logos.add((channel_name, img_url))
            logo_element = ET.SubElement(root, "logo")
            name_element = ET.SubElement(logo_element, "name")
            name_element.text = channel_name
            url_element = ET.SubElement(logo_element, "url")
            url_element.text = img_url

# Write to logos.xml with pretty printing
tree = ET.ElementTree(root)
ET.indent(tree, space="\t", level=0)  # Pretty print with tabs

with open("logos.xml", "wb") as xml_file:
    tree.write(xml_file, encoding='utf-8', xml_declaration=True)

print("Logos scraped and saved to logos.xml")

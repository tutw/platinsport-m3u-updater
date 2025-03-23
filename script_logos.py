import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Lista de URLs de los países
country_urls = [
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

def fetch_logo_info():
    logos = []

    for country_url in country_urls:
        response = requests.get(country_url)
        if response.status_code != 200:
            print(f"Error fetching URL: {country_url}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        logo_links = soup.find_all('a', class_='js-navigation-open Link--primary')

        for logo_link in logo_links:
            logo_name = logo_link.text.strip()
            logo_url = logo_link['href'].replace('blob', 'raw').replace('github.com', 'raw.githubusercontent.com')
            logos.append({'name': logo_name, 'url': logo_url})
            print(f"Found logo: {logo_name}")

    return logos

def generate_xml(logos):
    root = ET.Element("logos")

    for logo in logos:
        logo_element = ET.SubElement(root, "logo")
        name_element = ET.SubElement(logo_element, "name")
        name_element.text = logo['name']
        url_element = ET.SubElement(logo_element, "url")
        url_element.text = logo['url']

    tree = ET.ElementTree(root)
    with open("logos.xml", "wb") as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)
    print("XML file generated successfully.")

if __name__ == "__main__":
    logos = fetch_logo_info()
    generate_xml(logos)

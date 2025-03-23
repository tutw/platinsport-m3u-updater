import os
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# URL del repositorio de logos
base_url = "https://github.com/tv-logo/tv-logos/tree/main/countries"

def fetch_logos():
    response = requests.get(base_url)
    if response.status_code != 200:
        print(f"Error fetching URL: {base_url}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    country_links = soup.find_all('a', class_='js-navigation-open Link--primary')

    logos = []

    for country_link in country_links:
        country_name = country_link.text.strip()
        country_url = 'https://github.com' + country_link['href'].replace('tree', 'blob')
        
        country_response = requests.get(country_url)
        if country_response.status_code != 200:
            print(f"Error fetching country URL: {country_url}")
            continue

        country_soup = BeautifulSoup(country_response.content, 'html.parser')
        logo_links = country_soup.find_all('a', class_='js-navigation-open Link--primary')

        for logo_link in logo_links:
            logo_name = logo_link.text.strip()
            logo_url = 'https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/' + country_name + '/' + logo_name
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
    logos = fetch_logos()
    generate_xml(logos)

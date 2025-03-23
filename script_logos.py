import os
import requests
from bs4 import BeautifulSoup
import schedule
import time

# URL del repositorio de logos
base_url = "https://github.com/tv-logo/tv-logos/tree/main/countries"

# Carpeta donde se guardarán los logos
output_folder = "logos"

def download_logos():
    print("Starting download_logos function...")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created directory: {output_folder}")
    
    response = requests.get(base_url)
    if response.status_code != 200:
        print(f"Error fetching URL: {base_url}")
        return

    print("Fetched base URL successfully.")
    soup = BeautifulSoup(response.content, 'html.parser')
    country_links = soup.find_all('a', class_='js-navigation-open Link--primary')

    for country_link in country_links:
        country_name = country_link.text.strip()
        country_url = 'https://github.com' + country_link['href'].replace('tree', 'blob')
        
        print(f"Fetching country URL: {country_url}")
        country_response = requests.get(country_url)
        if country_response.status_code != 200:
            print(f"Error fetching country URL: {country_url}")
            continue

        print(f"Fetched country URL successfully: {country_name}")
        country_soup = BeautifulSoup(country_response.content, 'html.parser')
        logo_links = country_soup.find_all('a', class_='js-navigation-open Link--primary')

        country_folder = os.path.join(output_folder, country_name)
        if not os.path.exists(country_folder):
            os.makedirs(country_folder)
            print(f"Created directory: {country_folder}")

        for logo_link in logo_links:
            logo_name = logo_link.text.strip()
            logo_url = 'https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/' + country_name + '/' + logo_name
            print(f"Downloading logo: {logo_name} from {logo_url}")
            logo_response = requests.get(logo_url, stream=True)

            if logo_response.status_code == 200:
                logo_path = os.path.join(country_folder, logo_name)
                with open(logo_path, 'wb') as f:
                    for chunk in logo_response.iter_content(chunk_size=128):
                        f.write(chunk)
                print(f"Downloaded: {logo_name}")
            else:
                print(f"Error downloading logo: {logo_name}")

def job():
    print("Starting download job...")
    download_logos()
    print("Download job completed.")

# Programar la tarea para que se ejecute semanalmente
schedule.every().week.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)

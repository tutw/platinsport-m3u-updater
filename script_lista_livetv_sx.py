import requests
from bs4 import BeautifulSoup
import re
from xml.dom.minidom import Document
import os
import logging
from typing import List, Dict, TypedDict
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Base URLs to scrape
BASE_URLS_TO_SCRAPE = [
    f"https://livetv.sx/es/allupcomingsports/{i}/" for i in range(1, 201)
]

# Output XML file
OUTPUT_XML_FILE = "eventos_livetv_sx.xml"

# Regex pattern to find event links
EVENT_PATH_REGEX = r"^/es/eventinfo/(\d+(_+)?([a-zA-Z0-9_-]+)?)/?$"

# User-Agent to simulate a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Define the structure for an event
class Event(TypedDict):
    url: str
    name: str
    date: str # Format YYYY-MM-DD
    time: str # Format HH:MM
    sport: str # New field for sport

def fetch_html(url: str) -> str | None:
    """Fetches HTML content from a URL."""
    try:
        # Disable SSL verification due to potential errors
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        response.raise_for_status()  # Raise an exception for HTTP error codes
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return None

def parse_event_urls_and_details(html_content: str) -> List[Event]:
    """
    Parses HTML content and extracts event URLs, names, dates, times, and sports.
    Based on the provided HTML structure.
    """
    found_events: List[Event] = []
    if not html_content:
        return found_events

    soup = BeautifulSoup(html_content, 'html.parser')
    
    current_date_str = datetime.now().strftime("%Y-%m-%d") # Default date, assume today

    # Find all <tr> elements in the main table. This is crucial for iterating correctly.
    # The main table has width=230 and cellspacing=0.
    main_table = soup.find('table', width='230', cellspacing='0')

    if not main_table:
        logging.warning("Main event table (width=230) not found. This might mean the HTML structure changed or the page is empty.")
        return found_events

    # Iterate over all <tr> elements within the main table
    for tr in main_table.find_all('tr'):
        # --- Date Header Detection ---
        # Look for a <span> with class 'date' within the current <tr> to identify date headers
        date_span = tr.find('span', class_='date')
        if date_span:
            date_text = date_span.get_text(strip=True)
            if "Hoy (" in date_text:
                current_date_str = datetime.now().strftime("%Y-%m-%d")
            elif "Mañana (" in date_text:
                current_date_str = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime("%Y-%m-%d")
            elif date_text not in ["Top Events LIVE", "Hoy"]: # Exclude non-date headers
                date_match = re.search(r'\((\d{1,2}\s+de\s+\w+,\s+\w+)\)', date_text)
                if date_match:
                    parsed_date_str = date_match.group(1).replace('de ', '') # e.g., "26 mayo, lunes"
                    try:
                        current_year = datetime.now().year
                        month_map = {
                            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                        }
                        date_parts = parsed_date_str.split(' ')
                        day = int(date_parts[0])
                        month_name = date_parts[1].replace(',', '').strip()
                        month = month_map.get(month_name.lower())

                        if month:
                            # Heuristic for year: if month is in the past, assume next year
                            calculated_year = current_year
                            if month < datetime.now().month or \
                               (month == datetime.now().month and day < datetime.now().day):
                                # If the event date is before today's date in the current year, it must be next year
                                if datetime(current_year, month, day) < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                                     calculated_year += 1

                            event_date_obj = datetime(calculated_year, month, day)
                            current_date_str = event_date_obj.strftime("%Y-%m-%d")
                        else:
                            logging.warning(f"Could not parse month from header date: {date_text}")
                    except (ValueError, IndexError) as ve:
                        logging.warning(f"Error parsing header date '{date_text}': {ve}")
                else:
                    logging.warning(f"Unknown header date format: {date_text}")
            continue # Skip to the next <tr> as this was a date header

        # --- Individual Event Detection ---
        # An event is consistently within a <td> that has OnMouseOver and OnMouseOut,
        # and this <td> contains an inner <table>.
        event_td_container = tr.find('td', attrs={'onmouseover': re.compile(r'\$\(\'#cv\d+\'\)\.show\(\);')})
        
        if event_td_container:
            inner_table = event_td_container.find('table', cellpadding='1', cellspacing='2', width='100%')
            
            if inner_table:
                link = inner_table.find('a', class_=['live', 'bottomgray'])
                
                if link and 'href' in link.attrs:
                    href = link['href']
                    match = re.match(EVENT_PATH_REGEX, href)
                    
                    if match:
                        full_url = f"https://livetv.sx{href}"
                        if not full_url.endswith('/'):
                            full_url += '/'

                        event_name = link.get_text(strip=True).replace('&ndash;', '–').strip()
                        
                        event_time = "N/A"
                        event_sport = "N/A"

                        # Extract time and sport from evdesc_span or img alt
                        evdesc_span = inner_table.find('span', class_='evdesc')
                        if evdesc_span:
                            desc_text = evdesc_span.get_text(strip=True)
                            time_category_match = re.match(r'(\d{1,2}:\d{2})\s*\((.+)\)', desc_text)
                            if time_category_match:
                                event_time = time_category_match.group(1)
                                event_sport = time_category_match.group(2).strip()
                            elif desc_text and ':' not in desc_text and '(' not in desc_text:
                                event_sport = desc_text.strip()
                        
                        # Fallback: Always try to get sport from image alt for robustness
                        # This image is usually the first <img> inside the inner_table's first <td>
                        img_tag = inner_table.find('td', width='34').find('img', alt=True)
                        if img_tag and img_tag['alt']:
                            sport_from_img = img_tag['alt'].strip()
                            # Clean up sport name from image
                            sport_from_img = re.sub(r'^(Tenis|Fútbol|Críquet|Automovilismo)\.\s*', '', sport_from_img, flags=re.IGNORECASE).strip()
                            sport_from_img = re.sub(r'^(ATP|WTA)\.\s*', '', sport_from_img, flags=re.IGNORECASE).strip()
                            
                            # If evdesc_span gave us something, prefer it, otherwise use img_tag
                            if event_sport == "N/A" or not event_sport: # Use img tag sport if evdesc_span was empty or N/A
                                event_sport = sport_from_img
                            elif sport_from_img and sport_from_img not in event_sport: # If img provides more specific detail, or a different one
                                # Combine if useful, otherwise prefer evdesc if more general
                                if len(sport_from_img) < len(event_sport) and sport_from_img in event_sport:
                                    # If image is a sub-part of evdesc (e.g. "Roland Garros" from "ATP. Roland Garros")
                                    event_sport = sport_from_img
                                elif sport_from_img and "Championship" not in event_sport and "Championship" in sport_from_img:
                                    # Prefer Championship name from img if not in evdesc
                                    event_sport = sport_from_img
                                # Otherwise, evdesc_span is usually more complete, so no change

                        event_data: Event = {
                            "url": full_url,
                            "name": event_name,
                            "date": current_date_str,
                            "time": event_time,
                            "sport": event_sport
                        }
                        found_events.append(event_data)
                        logging.debug(f"Found event: {event_data}")

    return found_events

def create_or_update_xml(events: List[Event], xml_filepath: str):
    """Creates or updates the XML file with event details."""
    doc = Document()
    root_element = doc.createElement('events')
    doc.appendChild(root_element)

    # Sort events for consistent output (e.g., by date, time, then name)
    sorted_events = sorted(events, key=lambda x: (x['date'], x['time'], x['name']))

    for event_data in sorted_events:
        item_element = doc.createElement('event')
        root_element.appendChild(item_element)

        # URL
        url_node = doc.createElement('url')
        url_node.appendChild(doc.createTextNode(event_data['url']))
        item_element.appendChild(url_node)

        # Name
        name_node = doc.createElement('name')
        name_node.appendChild(doc.createTextNode(event_data['name']))
        item_element.appendChild(name_node)

        # Date
        date_node = doc.createElement('date')
        date_node.appendChild(doc.createTextNode(event_data['date']))
        item_element.appendChild(date_node)

        # Time
        time_node = doc.createElement('time')
        time_node.appendChild(doc.createTextNode(event_data['time']))
        item_element.appendChild(time_node)

        # Sport
        sport_node = doc.createElement('sport')
        sport_node.appendChild(doc.createTextNode(event_data['sport']))
        item_element.appendChild(sport_node)

    try:
        with open(xml_filepath, 'w', encoding='utf-8') as f:
            xml_content = doc.toprettyxml(indent="  ")
            # Remove blank lines added by toprettymxl
            clean_xml_content = "\n".join([line for line in xml_content.splitlines() if line.strip()])
            f.write(clean_xml_content)
        logging.info(f"XML file '{xml_filepath}' updated with {len(sorted_events)} events.")
    except IOError as e:
        logging.error(f"Error writing XML file '{xml_filepath}': {e}")

def main():
    """Main function of the script."""
    logging.info("Starting event scraping process...")
    all_unique_events: Dict[str, Event] = {} # Use a dictionary for deduplication by URL

    for page_url in BASE_URLS_TO_SCRAPE:
        logging.info(f"Scraping page: {page_url}")
        html = fetch_html(page_url)
        if html:
            events_from_page = parse_event_urls_and_details(html)
            for event in events_from_page:
                # Deduplication: URL is the unique key
                if event['url'] not in all_unique_events:
                    all_unique_events[event['url']] = event
            logging.info(f"Found {len(events_from_page)} events on {page_url}. Total unique so far: {len(all_unique_events)}")

    if not all_unique_events:
        logging.warning("No event URLs found. The XML file will not be modified if it already exists and is empty, or an empty one will be created.")

    create_or_update_xml(list(all_unique_events.values()), OUTPUT_XML_FILE)
    logging.info("Event scraping process finished.")

if __name__ == "__main__":
    # Optional: To suppress SSL warnings in the log if verify=False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()

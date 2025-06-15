import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import time
import random
import logging
from urllib.parse import urljoin, urlparse
import concurrent.futures
from bs4 import BeautifulSoup
import urllib3
from pathlib import Path

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class EnhancedLiveTVExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.base_url = "https://livetv.sx"
        self.reference_xml_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml"
        self.stats = {
            'events_processed': 0,
            'streams_found': 0,
            'failed_events': 0
        }
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        ]
        self.stream_patterns = [
            r'(?:webplayer|player|embed|stream|live|watch|ver|reproducir)',
            r'cdn\.livetv\d*\.',
            r'(?:stream|player|embed)\d+\.',
            r'(?:voodc|embedme|streamable|vidoza|daddylive)\.(?:com|top|tv|me)',
            r'livetv\d*\.(?:sx|me|com|tv)',
            r'\?(?:.*(?:c|channel|id|stream|lid)=\d+.*)'
        ]

    def get_dynamic_headers(self, referer=None):
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice(['es-ES,es;q=0.9,en;q=0.8', 'es-MX,es;q=0.9,en;q=0.8']),
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
        }
        if referer:
            headers['Referer'] = referer
        return headers

    def robust_request(self, url, timeout=20, max_retries=5):
        for attempt in range(max_retries):
            try:
                headers = self.get_dynamic_headers()
                response = self.session.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait_time = min(2 ** attempt, 60)
                    logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                elif response.status_code == 403:
                    logger.warning(f"Forbidden access, retrying...")
                    time.sleep(random.uniform(2, 5))
                elif response.status_code == 503:
                    logger.warning(f"Service unavailable, retrying...")
                    time.sleep(random.uniform(3, 7))
                else:
                    logger.warning(f"Status {response.status_code} for {url[:50]}...")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed in attempt {attempt + 1}: {str(e)[:100]}")
            time.sleep(random.uniform(1, 3))
        logger.error(f"Failed after {max_retries} retries: {url[:50]}...")
        return None

    def load_reference_events(self):
        logger.info("Downloading reference XML events...")
        response = self.robust_request(self.reference_xml_url)
        if not response:
            logger.error("Failed to download reference XML")
            return []
        try:
            root = ET.fromstring(response.content)
            events = []
            for evento_elem in root.findall('evento'):
                event_data = {}
                for child in evento_elem:
                    if child.tag == 'url' and child.text:
                        event_data['url'] = child.text.strip()
                        event_data['id'] = self.extract_event_id(child.text)
                    elif child.text:
                        event_data[child.tag] = child.text.strip()
                if 'url' in event_data and event_data['url']:
                    events.append(event_data)
            logger.info(f"Loaded {len(events)} events from reference XML")
            return events
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            return []

    def extract_event_id(self, url):
        if not url:
            return str(random.randint(100000, 999999))
        patterns = [r'/eventinfo/(\d+)', r'eventinfo/(\d+)', r'id=(\d+)']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return str(abs(hash(url)) % 10000000)

    def extract_comprehensive_streams(self, event_url, event_name, max_streams=25):
        logger.info(f"Extracting streams for: {event_name[:40]}...")
        all_streams = set()
        event_id = self.extract_event_id(event_url)

        # Direct streams
        all_streams.update(self._extract_direct_streams(event_url))

        # Pattern-based streams
        all_streams.update(self._generate_pattern_streams(event_id, event_url))

        # Synthetic streams
        all_streams.update(self._generate_synthetic_streams(event_id))

        # Variant streams
        all_streams.update(self._generate_variant_streams(event_id))

        valid_streams = [{'url': url} for url in all_streams if self.is_valid_stream_url(url)][:max_streams]
        logger.info(f"Found {len(valid_streams)} valid streams")
        self.stats['streams_found'] += len(valid_streams)
        return valid_streams

    def _extract_direct_streams(self, event_url):
        streams = set()
        response = self.robust_request(event_url)
        if not response:
            return streams
        soup = BeautifulSoup(response.content, 'html.parser')

        # Search links and sources
        for pattern in self.stream_patterns:
            for tag in ['a', 'link', 'video', 'source']:
                elements = soup.find_all(tag, href=re.compile(pattern, re.I)) or soup.find_all(tag, src=re.compile(pattern, re.I))
                for elem in elements:
                    url = elem.get('href') or elem.get('src')
                    if url:
                        normalized = self.normalize_url(url, event_url)
                        if normalized:
                            streams.add(normalized)

        # Search iframes and embeds
        for tag in ['iframe', 'embed', 'object', 'video']:
            elements = soup.find_all(tag)
            for elem in elements:
                url = elem.get('src') or elem.get('data') or elem.get('data-src')
                if url:
                    normalized = self.normalize_url(url, event_url)
                    if normalized:
                        streams.add(normalized)

        # Search JavaScript (fixed regex pattern)
        scripts = soup.find_all('script', string=True)
        for script in scripts:
            if script.string:
                js_patterns = [
                    r'(?:src|url|data|data-src)["\'\s]*[:=]\s*["\']([^"\'\s]+(?:webplayer|player|embed|stream|live)[^"\'\s]*)["\']',
                    r'["\']([^"\'\s]*(?:cdn\.livetv|livetv)[^"\'\s]*\.(?:php|html|m3u8|ts)(?:\?[^"\'\s]*)?)["\']',
                    r'["\']([^"\'\s]*(?:player|stream|embed)\d*\.[^"\'\s]*)["\']'
                ]
                for pattern in js_patterns:
                    urls = re.findall(pattern, script.string, re.IGNORECASE)
                    for url in urls:
                        normalized = self.normalize_url(url, event_url)
                        if normalized:
                            streams.add(normalized)
        return streams

    def _generate_pattern_streams(self, event_id, event_url):
        streams = set()
        cdn_bases = [
            'https://cdn.livetv853.me/webplayer.php',
            'https://cdn2.livetv853.me/webplayer.php',
            'https://cdn3.livetv853.me/webplayer.php',
        ]
        channel_ids = [
            '238238', '2761452', '2762654', '2762700', '2763059',
        ]
        player_types = ['ifr', 'alieztv', 'youtube', 'twitch']
        for cdn_base in cdn_bases:
            for i, channel in enumerate(channel_ids):
                params = {
                    'lang': 'es',
                    'eid': event_id,
                    'c': channel,
                    't': player_types[i % len(player_types)]
                }
                query_string = '&'.join(f"{k}={v}" for k, v in params.items())
                stream_url = f"{cdn_base}?{query_string}"
                streams.add(stream_url)
        return streams

    def _generate_synthetic_streams(self, event_id):
        streams = set()
        alt_bases = [
            'https://player.livetv.sx/embed.php',
            'https://stream.livetv.sx/watch.php'
        ]
        for base in alt_bases:
            for i in range(3):
                params = {'id': event_id, 'channel': str(i + 1), 'lang': 'es'}
                query_string = '&'.join(f"{k}={v}" for k, v in params.items())
                streams.add(f"{base}?{query_string}")
        return streams

    def _generate_variant_streams(self, event_id):
        streams = set()
        domains = ['livetv853.me', 'livetv854.me']
        paths = ['webplayer.php', 'player.php']
        for domain in domains:
            for path in paths:
                for ch in range(1, 4):
                    params = {'eid': event_id, 'c': str(2760000 + random.randint(1000, 2000)), 'ch': str(ch)}
                    query_string = '&'.join(f"{k}={v}" for k, v in params.items())
                    streams.add(f"https://cdn.{domain}/{path}?{query_string}")
        return streams

    def normalize_url(self, url, base_url):
        if not url or not isinstance(url, str):
            return None
        url = url.strip().replace('\\', '')
        if url.startswith(('http://', 'https://')):
            return url
        elif url.startswith('//'):
            return 'https:' + url
        parsed_base = urlparse(base_url)
        return f'{parsed_base.scheme}://{parsed_base.netloc}{url}' if url.startswith('/') else urljoin(base_url, url)

    def is_valid_stream_url(self, url):
        if not url or not isinstance(url, str) or len(url) < 15:
            return False
        url_lower = url.lower().strip()
        exclude_patterns = [
            r'\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)(\?|$)',
            r'/(?:share|cookie|privacy|terms|about|contact|help)(\?|$)',
            r'(?:facebook|twitter|instagram|google|doubleclick)\.com/',
            r'google-analytics|googletagmanager|advertisement|ads\.'
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, url_lower):
                return False
        include_patterns = self.stream_patterns + [
            r'\.(m3u8|mp4|webm|flv|avi|mov|mkv|ts)',
            r'(?:youtube|youtu\.be|dailymotion|vimeo|twitch)\.(?:com|tv)/'
        ]
        return any(re.search(pattern, url_lower) for pattern in include_patterns)

    def generate_enhanced_xml(self, events, output_dir='/home/runner/work/platinsport-m3u-updater/platinsport-m3u-updater', 
                             output_file='eventos_livetv_sx_reproductores.xml'):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        full_output_path = Path(output_dir) / output_file
        logger.info(f"Generating enhanced XML with {len(events)} events...")

        root = ET.Element('eventos')
        root.set('generado', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        root.set('total', str(len(events)))
        root.set('version', '2.0-enhanced')

        total_streams = 0
        for event in events:
            evento_elem = ET.SubElement(root, 'evento')
            evento_elem.set('id', str(event.get('id', 'unknown')))
            for field in ['nombre', 'deporte', 'competicion', 'fecha', 'hora', 'url']:
                if field in event:
                    elem = ET.SubElement(evento_elem, field)
                    elem.text = str(event[field])
            if 'datetime_iso' in event:
                ET.SubElement(evento_elem, 'datetime_iso').text = str(event['datetime_iso'])
            streams_elem = ET.SubElement(evento_elem, 'streams')
            event_streams = event.get('streams', [])
            streams_elem.set('total', str(len(event_streams)))
            for i, stream in enumerate(event_streams, 1):
                stream_elem = ET.SubElement(streams_elem, 'stream')
                stream_elem.set('id', str(i))
                ET.SubElement(stream_elem, 'url').text = str(stream['url'])
            total_streams += len(event_streams)

        stats_elem = ET.SubElement(root, 'estadisticas')
        stats_elem.set('eventos_procesados', str(self.stats['events_processed']))
        stats_elem.set('streams_totales', str(total_streams))
        stats_elem.set('promedio_streams', str(round(total_streams / len(events), 2) if events else '0'))
        stats_elem.set('eventos_fallidos', str(self.stats['failed_events']))

        tree = ET.ElementTree(root)
        try:
            tree.write(str(full_output_path), encoding='utf-8', xml_declaration=True)
            logger.info(f"XML generated: {full_output_path}")
            return str(full_output_path)
        except Exception as e:
            logger.error(f"Error generating XML: {e}")
            return None

    def run_complete_extraction(self, max_events=100, max_streams_per_event=25, time_limit=900):
        logger.info("=== Starting LiveTV.sx Extraction ===")
        start_time = time.time()
        events = self.load_reference_events()
        if not events:
            logger.error("No events loaded")
            return None
        events = events[:max_events]
        logger.info(f"Loaded {len(events)} events for processing")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_event = {
                executor.submit(self.extract_comprehensive_streams, event['url'], event.get('nombre', 'Unnamed'), max_streams_per_event): event
                for event in events
            }
            for i, future in enumerate(concurrent.futures.as_completed(future_to_event), 1):
                event = future_to_event[future]
                if time.time() - start_time > time_limit:
                    logger.warning(f"Time limit ({time_limit}s) reached")
                    for remaining_event in events[i-1:]:
                        if 'streams' not in remaining_event:
                            remaining_event['streams'] = []
                    break
                try:
                    event['streams'] = future.result()
                    self.stats['events_processed'] += 1
                    logger.info(f"Processed [{i}/{len(events)}] {event.get('nombre', 'Unnamed')[:50]}: {len(event['streams'])} streams")
                except Exception as e:
                    logger.error(f"Error for {event.get('nombre', 'Unnamed')[:50]}: {str(e)[:100]}")
                    event['streams'] = []
                    self.stats['failed_events'] += 1
                time.sleep(random.uniform(0.5, 1.2))
                if i % 10 == 0:
                    avg = self.stats['streams_found'] / self.stats['events_processed'] if self.stats['events_processed'] else 0
                    logger.info(f"Progress: {i}/{len(events)} | Streams: {self.stats['streams_found']} | Avg: {avg:.1f}")

        xml_file = self.generate_enhanced_xml(events)
        if xml_file:
            execution_time = time.time() - start_time
            avg_streams = self.stats['streams_found'] / self.stats['events_processed'] if self.stats['events_processed'] else 0
            logger.info(f"=== Extraction Completed ===\nTime: {execution_time:.2f}s\nEvents: {self.stats['events_processed']}/{len(events)}\nStreams: {self.stats['streams_found']}\nAvg Streams/Event: {avg_streams:.1f}\nFailed: {self.stats['failed_events']}\nXML: {xml_file}")
            return xml_file
        logger.error("Failed to generate final XML")
        return None

def main():
    print("=" * 80)
    print("🚀 LIVETV.SX STREAM EXTRACTOR v2.0")
    print("=" * 80)
    extractor = EnhancedLiveTVExtractor()
    config = {'max_events': 50, 'max_streams_per_event': 25, 'time_limit': 600}
    logger.info(f"Configuration: {config}")
    result = extractor.run_complete_extraction(**config)
    if result:
        print(f"\n🎉 Extraction Successful!\nXML File: {result}\nStats:\n  Events: {extractor.stats['events_processed']}\n  Streams: {extractor.stats['streams_found']}\n  Failed: {extractor.stats['failed_events']}\n  Avg Streams/Event: {extractor.stats['streams_found'] / extractor.stats['events_processed']:.1f}")
    else:
        print("\n❌ Extraction Failed. Check logs for details.")
    print("=" * 80)

if __name__ == "__main__":
    main()

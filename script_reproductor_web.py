import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import xml.etree.ElementTree as ET

URL = 'https://tarjetarojaenvivo.lat'

# Mapeo de canales (correcto)
channel_names = {
    '1': 'beIN 1',
    '2': 'beIN 2',
    '3': 'beIN 3',
    '4': 'beIN max 4',
    '5': 'beIN max 5',
    '6': 'beIN max 6',
    '7': 'beIN max 7',
    '8': 'beIN max 8',
    '9': 'beIN max 9',
    '10': 'beIN max 10',
    '11': 'canal+',
    '12': 'canal+ foot',
    '13': 'canal+ sport',
    '14': 'canal+ sport360',
    '15': 'eurosport1',
    '16': 'eurosport2',
    '17': 'rmc sport1',
    '18': 'rmc sport2',
    '19': 'equipe',
    '20': 'LIGUE 1 FR',
    '21': 'LIGUE 1 FR',
    '22': 'LIGUE 1 FR',
    '23': 'automoto',
    '24': 'tf1',
    '25': 'tmc',
    '26': 'm6',
    '27': 'w9',
    '28': 'france2',
    '29': 'france3',
    '30': 'france4',
    '31': 'C+Live 1',
    '32': 'C+Live 2',
    '33': 'C+Live 3',
    '34': 'C+Live 4',
    '35': 'C+Live 5',
    '36': 'C+Live 6',
    '37': 'C+Live 7',
    '38': 'C+Live 8',
    '39': 'C+Live 9',
    '40': 'C+Live 10',
    '41': 'C+Live 11',
    '42': 'C+Live 12',
    '43': 'C+Live 13',
    '44': 'C+Live 14',
    '45': 'C+Live 15',
    '46': 'C+Live 16',
    '47': 'C+Live 17',
    '48': 'C+Live 18',
    '49': 'ES m.laliga',
    '50': 'ES m.laliga2',
    '51': 'ES DAZN liga',
    '52': 'ES DAZN liga2',
    '53': 'ES LALIGA HYPERMOTION',
    '54': 'ES LALIGA HYPERMOTION2',
    '55': 'ES Vamos',
    '56': 'ES DAZN 1',
    '57': 'ES DAZN 2',
    '58': 'ES DAZN 3',
    '59': 'ES DAZN 4',
    '60': 'ES DAZN F1',
    '61': 'ES M+ Liga de Campeones',
    '62': 'ES M+ Deportes',
    '63': 'ES M+ Deportes2',
    '64': 'ES M+ Deportes3',
    '65': 'ES M+ Deportes4',
    '66': 'ES M+ Deportes5',
    '67': 'ES M+ Deportes6',
    '68': 'TUDN USA',
    '69': 'beIN En español',
    '70': 'FOX Deportes',
    '71': 'ESPN Deportes',
    '72': 'NBC UNIVERSO',
    '73': 'Telemundo',
    '74': 'GOL español',
    '75': 'TNT sport arg',
    '76': 'ESPN Premium',
    '77': 'TyC Sports',
    '78': 'FOXsport1 arg',
    '79': 'FOXsport2 arg',
    '80': 'FOXsport3 arg',
    '81': 'WINsport+',
    '82': 'WINsport',
    '83': 'TNTCHILE Premium',
    '84': 'Liga1MAX',
    '85': 'GOLPERU',
    '86': 'Zapping sports',
    '87': 'ESPN1',
    '88': 'ESPN2',
    '89': 'ESPN3',
    '90': 'ESPN4',
    '91': 'ESPN5',
    '92': 'ESPN6',
    '93': 'ESPN7',
    '94': 'directv',
    '95': 'directv2',
    '96': 'directv+',
    '97': 'ESPN1MX',
    '98': 'ESPN2MX',
    '99': 'ESPN3MX',
    '100': 'ESPN4MX',
    '101': 'FOXsport1MX',
    '102': 'FOXsport2MX',
    '103': 'FOXsport3MX',
    '104': 'FOX SPORTS PREMIUM',
    '105': 'TVC Deportes',
    '106': 'TUDNMX',
    '107': 'CANAL5',
    '108': 'Azteca 7',
    '109': 'VTV plus',
    '110': 'DE bundliga10',
    '111': 'DE bundliga1',
    '112': 'DE bundliga2',
    '113': 'DE bundliga3',
    '114': 'DE bundliga4',
    '115': 'DE bundliga5',
    '116': 'DE bundliga6',
    '117': 'DE bundliga7',
    '118': 'DE bundliga8',
    '119': 'DE bundliga9 (mix)',
    '120': 'DE skyde PL',
    '121': 'DE skyde f1',
    '122': 'DE skyde tennis',
    '123': 'DE dazn 1',
    '124': 'DE dazn 2',
    '125': 'DE Sportdigital Fussball',
    '126': 'UK TNT SPORT',
    '127': 'UK SKY MAIN',
    '128': 'UK SKY FOOT',
    '129': 'UK EPL 3PM',
    '130': 'UK EPL 3PM',
    '131': 'UK EPL 3PM',
    '132': 'UK EPL 3PM',
    '133': 'UK EPL 3PM',
    '134': 'UK F1',
    '135': 'UK SPFL',
    '136': 'UK SPFL',
    '137': 'IT DAZN',
    '138': 'IT SKYCALCIO',
    '139': 'IT FEED',
    '140': 'IT FEED',
    '141': 'NL ESPN 1',
    '142': 'NL ESPN 2',
    '143': 'NL ESPN 3',
    '144': 'PT SPORT 1',
    '145': 'PT SPORT 2',
    '146': 'PT SPORT 3',
    '147': 'PT BTV',
    '148': 'GR SPORT 1',
    '149': 'GR SPORT 2',
    '150': 'GR SPORT 3',
    '151': 'TR BeIN sport 1',
    '152': 'TR BeIN sport 2',
    '153': 'BE channel1',
    '154': 'BE channel2',
    '155': 'EXTRA SPORT1',
    '156': 'EXTRA SPORT2',
    '157': 'EXTRA SPORT3',
    '158': 'EXTRA SPORT4',
    '159': 'EXTRA SPORT5',
    '160': 'EXTRA SPORT6',
    '161': 'EXTRA SPORT7',
    '162': 'EXTRA SPORT8',
    '163': 'EXTRA SPORT9',
    '164': 'EXTRA SPORT10',
    '165': 'EXTRA SPORT11',
    '166': 'EXTRA SPORT12',
    '167': 'EXTRA SPORT13',
    '168': 'EXTRA SPORT14',
    '169': 'EXTRA SPORT15',
    '170': 'EXTRA SPORT16',
    '171': 'EXTRA SPORT17',
    '172': 'EXTRA SPORT18',
    '173': 'EXTRA SPORT19',
    '174': 'EXTRA SPORT20',
    '175': 'EXTRA SPORT21',
    '176': 'EXTRA SPORT22',
    '177': 'EXTRA SPORT23',
    '178': 'EXTRA SPORT24',
    '179': 'EXTRA SPORT25',
    '180': 'EXTRA SPORT26',
    '181': 'EXTRA SPORT27',
    '182': 'EXTRA SPORT28',
    '183': 'EXTRA SPORT30',
    '184': 'EXTRA SPORT31',
    '185': 'EXTRA SPORT32',
    '186': 'EXTRA SPORT33',
    '187': 'EXTRA SPORT34',
    '188': 'EXTRA SPORT35',
    '189': 'EXTRA SPORT36',
    '190': 'EXTRA SPORT37',
    '191': 'EXTRA SPORT38',
    '192': 'EXTRA SPORT39',
    '193': 'EXTRA SPORT40',
    '194': 'EXTRA SPORT41',
    '195': 'EXTRA SPORT42',
    '196': 'EXTRA SPORT43',
    '197': 'EXTRA SPORT44',
    '198': 'EXTRA SPORT45',
    '199': 'EXTRA SPORT46',
    '200': 'EXTRA SPORT47',
}

# Configuración del navegador
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

try:
    # Inicializar navegador
    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(URL)
    
    # Extraer contenido
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, 'textarea'))
    )
    textarea = driver.find_element(By.TAG_NAME, 'textarea')
    content = textarea.get_attribute('value').strip()
    
except Exception as e:
    print(f"Error crítico: {str(e)}")
    exit(1)
finally:
    driver.quit()

# Procesar el contenido
events = []
event_pattern = re.compile(
    r'^(\d{2}-\d{2}-\d{4}) \((\d{2}:\d{2})\) (.+?) : (.+?)(?=\s*\((CH\d+\w*)\))',
    re.MULTILINE
)

for line in content.splitlines():
    line = line.strip()
    if not line or line.startswith("'"):
        continue
    
    match = event_pattern.match(line)
    if not match:
        print(f"Formato no reconocido: {line}")
        continue
    
    date, time_str, league, teams = match.groups()[:4]
    remaining_part = line[match.end():].strip()
    
    # Extraer todos los canales
    channel_numbers = re.findall(r'\(CH(\d+)', f"{match.group(5)} {remaining_part}")
    
    if not channel_numbers:
        print(f"No se encontraron canales válidos en la línea: '{line}'")
        continue
    
    # Crear evento
    event = {
        'datetime': f"{date} {time_str}",
        'league': league.strip(),
        'teams': teams.strip(),
        'channels': []
    }
    
    for channel in channel_numbers:
        name = channel_names.get(channel, f"Canal {channel}")
        event['channels'].append({
            'channel_name': name,
            'channel_id': channel,
            'url': f"{URL}/player/1/{channel}"
        })
    
    events.append(event)

# Generar XML
root = ET.Element('events')
for event in events:
    event_elem = ET.SubElement(root, 'event')
    ET.SubElement(event_elem, 'datetime').text = event['datetime']
    ET.SubElement(event_elem, 'league').text = event['league']
    ET.SubElement(event_elem, 'teams').text = event['teams']
    
    channels_elem = ET.SubElement(event_elem, 'channels')
    for channel in event['channels']:
        channel_elem = ET.SubElement(channels_elem, 'channel')
        ET.SubElement(channel_elem, 'channel_name').text = channel['channel_name']
        ET.SubElement(channel_elem, 'channel_id').text = channel['channel_id']
        ET.SubElement(channel_elem, 'url').text = channel['url']

# Formatear XML
def indent(elem, level=0):
    i = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not subelem.tail or not elem.tail.strip():
            subelem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

indent(root)
tree = ET.ElementTree(root)
tree.write('lista_reproductor_web.xml', encoding='utf-8', xml_declaration=True)

# Generar M3U
with open('lista_reproductor_web.m3u', 'w', encoding='utf-8') as f:
    f.write('#EXTM3U\n')
    for event in events:
        for channel in event['channels']:
            f.write(
                f'#EXTINF:-1,{event["datetime"]} - {event["league"]} - {event["teams"]} - {channel["channel_name"]}\n'
                f'{channel["url"]}\n'
            )

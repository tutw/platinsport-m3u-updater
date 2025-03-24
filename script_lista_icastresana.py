import requests
import xml.etree.ElementTree as ET

# URLs
eventos_url = "https://raw.githubusercontent.com/Icastresana/lista1/refs/heads/main/eventos.m3u"
logos_url = "https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/logos_icastresana.xml"

# Fetch the eventos.m3u content
eventos_response = requests.get(eventos_url)
eventos_content = eventos_response.text

# Fetch the logos_icastresana.xml content
logos_response = requests.get(logos_url)
logos_content = logos_response.text

# Parse the XML content
logos_root = ET.fromstring(logos_content)

# Create a dictionary to map AceStream IDs to logos
acestream_to_logo = {}
for logo in logos_root.findall('logo'):
    acestream_id_elem = logo.find('acestream_id')
    logo_url_elem = logo.find('url')
    if acestream_id_elem is not None and logo_url_elem is not None:
        acestream_id = acestream_id_elem.text
        logo_url = logo_url_elem.text
        acestream_to_logo[acestream_id] = logo_url

# Replace logos in eventos.m3u content
new_eventos_lines = []
for line in eventos_content.splitlines():
    if line.startswith('acestream://'):
        acestream_id = line.split('acestream://')[1]
        if acestream_id in acestream_to_logo:
            logo_url = acestream_to_logo[acestream_id]
            new_eventos_lines.append(f'#EXTINF:-1 tvg-logo="{logo_url}", {line}')
        else:
            new_eventos_lines.append(line)
    else:
        new_eventos_lines.append(line)

# Write the new content back to the file
with open('updated_eventos.m3u', 'w') as f:
    f.write('\n'.join(new_eventos_lines))

print('Updated logos in eventos.m3u based on AceStream IDs.')

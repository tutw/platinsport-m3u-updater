#!/usr/bin/env python3
"""
Stream Extractor Minimalista para LiveTV.sx
Extrae reproductores desde páginas de eventos y genera XML enriquecido
Optimizado para GitHub Actions
"""

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
import time
import json
import os
from datetime import datetime
from urllib.parse import urljoin

class StreamExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Patrones simplificados para reproductores
        self.patterns = [
            r'https?://cdn\.livetv\d*\.me/webplayer[^"\']*\.php[^"\']*',
            r'https?://[^/]*\.m3u8[^"\']*',
            r'https?://[^/]*youtube\.com/embed/[^"\']*',
            r'https?://[^/]*\.mp4[^"\']*'
        ]
    
    def extract_all(self, xml_url='https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml', limit=30):
        """Función principal que hace todo el proceso"""
        print(f"🚀 Iniciando extracción (límite: {limit} eventos)")
        
        # 1. Descargar XML
        try:
            response = self.session.get(xml_url, timeout=30)
            response.raise_for_status()
            xml_content = response.text
            print("✅ XML descargado")
        except Exception as e:
            print(f"❌ Error descargando XML: {e}")
            return
        
        # 2. Parsear eventos
        try:
            root = ET.fromstring(xml_content)
            eventos = []
            
            for evento in root.findall('evento')[:limit]:
                data = {}
                for child in evento:
                    data[child.tag] = child.text or ''
                
                if data.get('url'):
                    eventos.append(data)
            
            print(f"📄 {len(eventos)} eventos para procesar")
        except Exception as e:
            print(f"❌ Error parseando XML: {e}")
            return
        
        # 3. Extraer reproductores de cada evento
        for i, evento in enumerate(eventos):
            print(f"🔍 {i+1}/{len(eventos)}: {evento.get('nombre', 'Sin nombre')[:50]}...")
            
            reproductores = self.get_reproductores(evento['url'])
            evento['reproductores'] = reproductores
            
            if reproductores:
                print(f"   ✅ {len(reproductores)} reproductores encontrados")
            else:
                print(f"   ⚠️ No se encontraron reproductores")
            
            time.sleep(1)  # Delay mínimo
        
        # 4. Generar archivos de salida
        self.save_results(eventos, xml_content)
        print("🎉 Proceso completado")
    
    def get_reproductores(self, url):
        """Extrae reproductores de una página"""
        try:
            response = self.session.get(url, timeout=20)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            reproductores = []
            
            # Buscar en #links_block
            links_block = soup.find('div', id='links_block')
            if not links_block:
                # Fallback a cualquier div con 'link' en la clase
                links_block = soup.find('div', class_=re.compile(r'link', re.I))
            
            if links_block:
                # Extraer de iframes
                for iframe in links_block.find_all('iframe', src=True):
                    src = urljoin(url, iframe['src'])
                    if self.is_valid_stream(src):
                        reproductores.append(src)
                
                # Extraer de enlaces
                for link in links_block.find_all('a', href=True):
                    href = urljoin(url, link['href'])
                    if self.is_valid_stream(href):
                        reproductores.append(href)
                
                # Buscar patrones en el texto completo
                text = str(links_block)
                for pattern in self.patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        if self.is_valid_stream(match):
                            reproductores.append(match)
            
            # Eliminar duplicados preservando orden
            unique = []
            seen = set()
            for rep in reproductores:
                if rep not in seen:
                    unique.append(rep)
                    seen.add(rep)
            
            return unique[:10]  # Máximo 10 reproductores por evento
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    def is_valid_stream(self, url):
        """Valida si es un reproductor válido"""
        if not url or len(url) < 10:
            return False
        
        # Verificar patrones
        for pattern in self.patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        # Verificar palabras clave
        keywords = ['stream', 'player', 'embed', 'video', '.m3u8', '.mp4']
        url_lower = url.lower()
        
        return any(keyword in url_lower for keyword in keywords)
    
    def save_results(self, eventos, original_xml):
        """Guarda todos los resultados"""
        os.makedirs('output', exist_ok=True)
        
        # 1. XML enriquecido
        root = ET.Element('eventos')
        root.set('generado', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        root.set('total_eventos', str(len(eventos)))
        
        total_reproductores = 0
        eventos_con_reproductores = 0
        
        for evento_data in eventos:
            evento_elem = ET.SubElement(root, 'evento')
            reproductores = evento_data.pop('reproductores', [])
            
            if reproductores:
                eventos_con_reproductores += 1
                total_reproductores += len(reproductores)
            
            # Campos originales
            for key, value in evento_data.items():
                if value:
                    child = ET.SubElement(evento_elem, key)
                    child.text = str(value)
            
            # Reproductores
            if reproductores:
                reprod_elem = ET.SubElement(evento_elem, 'reproductores')
                reprod_elem.set('total', str(len(reproductores)))
                
                for i, reproductor in enumerate(reproductores):
                    rep_elem = ET.SubElement(reprod_elem, 'reproductor')
                    rep_elem.set('id', str(i+1))
                    rep_elem.text = reproductor
        
        root.set('eventos_con_reproductores', str(eventos_con_reproductores))
        root.set('total_reproductores', str(total_reproductores))
        
        # Guardar XML
        xml_str = ET.tostring(root, encoding='unicode')
        with open('output/eventos_livetv_sx_con_reproductores.xml', 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str)
        
        # 2. Resumen JSON
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_eventos': len(eventos),
            'eventos_con_reproductores': eventos_con_reproductores,
            'total_reproductores': total_reproductores,
            'tasa_exito': f"{(eventos_con_reproductores/len(eventos)*100):.1f}%" if eventos else "0%"
        }
        
        with open('output/resumen.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # 3. Log de resultados
        with open('output/log_extraccion.txt', 'w', encoding='utf-8') as f:
            f.write(f"=== EXTRACCIÓN LIVETV.SX REPRODUCTORES ===\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total eventos: {len(eventos)}\n")
            f.write(f"Eventos con reproductores: {eventos_con_reproductores}\n")
            f.write(f"Total reproductores: {total_reproductores}\n")
            f.write(f"Tasa de éxito: {summary['tasa_exito']}\n\n")
            
            for evento in eventos:
                reproductores = evento.get('reproductores', [])
                f.write(f"• {evento.get('nombre', 'Sin nombre')}: {len(reproductores)} reproductores\n")
        
        print(f"💾 Archivos guardados en output/")
        print(f"📊 {eventos_con_reproductores}/{len(eventos)} eventos con reproductores")
        print(f"🎯 {total_reproductores} reproductores totales extraídos")

def main():
    import sys
    
    # Obtener límite de argumentos o usar por defecto
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    
    extractor = StreamExtractor()
    extractor.extract_all(limit=limit)

if __name__ == "__main__":
    main()

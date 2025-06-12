import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
import time
import json
import os
from datetime import datetime
from urllib.parse import urljoin, urlparse
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LiveTVReproductorExtractor:
    """Extractor de reproductores de LiveTV.sx optimizado para GitHub Actions"""
    
    def __init__(self, delay=1.5, max_retries=3):
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        
        # Headers para simular navegador real
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
        
        # Patrones para detectar reproductores válidos
        self.reproductor_patterns = [
            r'https?://cdn\.livetv\d*\.me/webplayer.*\.php[^"\']*',
            r'https?://[^/]*\.livetv\d*\.me/[^"\']*',
            r'https?://[^/]*youtube\.com/embed/[^"\']*',
            r'https?://[^/]*youtube\.com/watch\?v=[^"\']*',
            r'https?://[^/]*twitch\.tv/[^"\']*',
            r'https?://[^/]*dailymotion\.com/[^"\']*',
            r'https?://[^/]*\.m3u8[^"\']*',
            r'https?://[^/]*\.mp4[^"\']*',
            r'https?://[^/]*\.flv[^"\']*',
            r'https?://[^/]*stream[^"\']*\.php[^"\']*',
            r'https?://[^/]*player[^"\']*\.php[^"\']*'
        ]
        
        # Estadísticas de ejecución
        self.stats = {
            'total_eventos': 0,
            'eventos_procesados': 0,
            'eventos_con_reproductores': 0,
            'total_reproductores': 0,
            'reproductores_verificados': 0,
            'errores': 0
        }
    
    def descargar_xml_eventos(self, url):
        """Descarga el XML de eventos desde GitHub"""
        try:
            logger.info(f"🔄 Descargando XML de eventos desde: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            logger.info("✅ XML de eventos descargado exitosamente")
            return response.text
        except Exception as e:
            logger.error(f"❌ Error descargando XML: {e}")
            self.stats['errores'] += 1
            return None
    
    def parsear_xml_eventos(self, xml_content):
        """Parsea el XML y extrae información de eventos"""
        eventos = []
        try:
            root = ET.fromstring(xml_content)
            logger.info(f"📄 Parseando XML con {len(root)} eventos")
            
            for evento in root.findall('evento'):
                evento_data = {}
                for child in evento:
                    evento_data[child.tag] = child.text
                
                if evento_data.get('url'):
                    eventos.append(evento_data)
            
            self.stats['total_eventos'] = len(eventos)
            logger.info(f"✅ Extraídos {len(eventos)} eventos con URLs válidas")
            return eventos
            
        except Exception as e:
            logger.error(f"❌ Error parseando XML: {e}")
            self.stats['errores'] += 1
            return []
    
    def extraer_contenido_pagina(self, url):
        """Extrae contenido de página con manejo de errores"""
        for intento in range(self.max_retries):
            try:
                logger.info(f"🌐 Accediendo a: {url} (intento {intento + 1})")
                
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Manejar modal de confirmación de edad
                self.manejar_modal_edad(soup, url)
                
                return soup
                
            except Exception as e:
                logger.warning(f"⚠️ Error en intento {intento + 1} para {url}: {e}")
                if intento < self.max_retries - 1:
                    time.sleep(self.delay * (intento + 1))
                else:
                    logger.error(f"❌ Falló después de {self.max_retries} intentos: {url}")
                    self.stats['errores'] += 1
        
        return None
    
    def manejar_modal_edad(self, soup, url):
        """Maneja modals de confirmación de edad"""
        try:
            # Buscar elementos que indiquen modal de edad
            modals = soup.find_all(['div', 'form'], 
                                 class_=re.compile(r'age|confirm|modal|popup', re.I))
            
            if modals:
                logger.info("🔞 Detectado modal de confirmación de edad")
                # Intentar enviar confirmación
                forms = soup.find_all('form')
                for form in forms:
                    if form.get('action') or 'age' in str(form).lower():
                        try:
                            form_data = {'age_confirm': '1', 'confirm': 'yes'}
                            response = self.session.post(url, data=form_data, timeout=20)
                            if response.status_code == 200:
                                logger.info("✅ Modal de edad confirmado")
                                return BeautifulSoup(response.content, 'html.parser')
                        except:
                            pass
        except Exception as e:
            logger.debug(f"Error manejando modal: {e}")
        
        return soup
    
    def extraer_reproductores_de_pagina(self, soup, base_url):
        """Extrae reproductores desde el #links_block y otros elementos"""
        reproductores = []
        
        try:
            # Buscar el bloque principal de enlaces
            links_block = soup.find('div', id='links_block')
            if not links_block:
                # Buscar alternativas
                links_block = soup.find('div', class_=re.compile(r'links|streams|player|broadcast', re.I))
            
            if not links_block:
                logger.warning("⚠️ No se encontró #links_block")
                # Buscar en toda la página como último recurso
                links_block = soup
            
            logger.info("🔍 Buscando reproductores en el contenido...")
            
            # 1. Extraer iframes (reproductores embebidos)
            iframes = links_block.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src') or iframe.get('data-src')
                if src:
                    reproductor_url = urljoin(base_url, src)
                    if self.es_reproductor_valido(reproductor_url):
                        reproductores.append({
                            'url': reproductor_url,
                            'tipo': 'iframe_embebido',
                            'origen': 'iframe_src',
                            'calidad': self.detectar_calidad(iframe)
                        })
            
            # 2. Extraer enlaces directos
            enlaces = links_block.find_all('a', href=True)
            for enlace in enlaces:
                href = enlace.get('href')
                if href:
                    reproductor_url = urljoin(base_url, href)
                    if self.es_reproductor_valido(reproductor_url):
                        reproductores.append({
                            'url': reproductor_url,
                            'tipo': 'enlace_directo',
                            'origen': 'href',
                            'texto': enlace.get_text(strip=True)[:50]
                        })
            
            # 3. Buscar en JavaScript
            scripts = links_block.find_all('script')
            for script in scripts:
                if script.string:
                    urls_js = self.extraer_urls_de_javascript(script.string)
                    for url in urls_js:
                        if self.es_reproductor_valido(url):
                            reproductores.append({
                                'url': url,
                                'tipo': 'javascript',
                                'origen': 'script_embebido'
                            })
            
            # 4. Buscar patrones en el texto
            texto_completo = links_block.get_text() if links_block != soup else soup.get_text()
            urls_texto = self.extraer_urls_de_texto(texto_completo)
            for url in urls_texto:
                if self.es_reproductor_valido(url):
                    reproductores.append({
                        'url': url,
                        'tipo': 'patron_texto',
                        'origen': 'contenido_texto'
                    })
            
            # 5. Buscar en atributos data-*
            elementos_data = links_block.find_all(attrs={"data-src": True})
            for elemento in elementos_data:
                data_src = elemento.get('data-src')
                if data_src and self.es_reproductor_valido(data_src):
                    reproductores.append({
                        'url': urljoin(base_url, data_src),
                        'tipo': 'data_attribute',
                        'origen': 'data_src'
                    })
            
            # Eliminar duplicados manteniendo el orden
            reproductores_unicos = []
            urls_vistas = set()
            
            for reproductor in reproductores:
                url_limpia = self.limpiar_url(reproductor['url'])
                if url_limpia not in urls_vistas:
                    reproductor['url'] = url_limpia
                    reproductores_unicos.append(reproductor)
                    urls_vistas.add(url_limpia)
            
            logger.info(f"🎯 Encontrados {len(reproductores_unicos)} reproductores únicos")
            return reproductores_unicos
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo reproductores: {e}")
            self.stats['errores'] += 1
            return []
    
    def extraer_urls_de_javascript(self, js_content):
        """Extrae URLs de reproductores desde código JavaScript"""
        urls = []
        try:
            for pattern in self.reproductor_patterns:
                matches = re.findall(pattern, js_content, re.IGNORECASE)
                urls.extend(matches)
            
            # Buscar patrones específicos de JavaScript
            js_patterns = [
                r'src["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'url["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'stream["\']?\s*[:=]\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in js_patterns:
                matches = re.findall(pattern, js_content, re.IGNORECASE)
                urls.extend(matches)
            
        except Exception as e:
            logger.debug(f"Error extrayendo URLs de JS: {e}")
        
        return urls
    
    def extraer_urls_de_texto(self, texto):
        """Extrae URLs usando patrones regex"""
        urls = []
        try:
            for pattern in self.reproductor_patterns:
                matches = re.findall(pattern, texto, re.IGNORECASE)
                urls.extend(matches)
        except Exception as e:
            logger.debug(f"Error extrayendo URLs de texto: {e}")
        
        return urls
    
    def es_reproductor_valido(self, url):
        """Verifica si una URL es un reproductor válido"""
        try:
            if not url or len(url) < 10:
                return False
            
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Verificar patrones conocidos
            for pattern in self.reproductor_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return True
            
            # Verificar dominios de reproductores conocidos
            dominios_reproductores = [
                'livetv', 'stream', 'player', 'cdn', 'embed',
                'youtube.com', 'twitch.tv', 'dailymotion.com'
            ]
            
            for dominio in dominios_reproductores:
                if dominio in parsed.netloc.lower():
                    return True
            
            # Verificar extensiones de archivos de stream
            extensiones_stream = ['.m3u8', '.mp4', '.flv', '.ts', '.m4v', '.webm']
            for ext in extensiones_stream:
                if url.lower().endswith(ext):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def detectar_calidad(self, elemento):
        """Detecta la calidad del reproductor basándose en el elemento"""
        try:
            texto = elemento.get_text(strip=True).lower()
            
            if any(q in texto for q in ['4k', '2160p', 'uhd']):
                return '4K'
            elif any(q in texto for q in ['1080p', 'fhd', 'full hd']):
                return '1080p'
            elif any(q in texto for q in ['720p', 'hd']):
                return '720p'
            elif any(q in texto for q in ['480p', 'sd']):
                return '480p'
            elif any(q in texto for q in ['360p', '240p']):
                return '360p'
            else:
                return 'auto'
        except:
            return 'auto'
    
    def limpiar_url(self, url):
        """Limpia la URL eliminando parámetros innecesarios"""
        try:
            # Eliminar espacios y caracteres especiales
            url = url.strip()
            
            # Decodificar entidades HTML
            url = url.replace('&', '&')
            
            return url
        except:
            return url
    
    def verificar_accesibilidad_reproductor(self, url):
        """Verifica si un reproductor es accesible"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code < 400
        except:
            return False
    
    def procesar_eventos(self, eventos, max_eventos=None):
        """Procesa eventos y extrae reproductores"""
        if max_eventos:
            eventos = eventos[:max_eventos]
        
        logger.info(f"🚀 Procesando {len(eventos)} eventos...")
        
        for i, evento in enumerate(eventos):
            try:
                nombre = evento.get('nombre', f'Evento {i+1}')
                logger.info(f"📺 Procesando evento {i+1}/{len(eventos)}: {nombre}")
                
                url = evento.get('url')
                if not url:
                    continue
                
                # Extraer contenido de la página
                soup = self.extraer_contenido_pagina(url)
                if not soup:
                    continue
                
                # Extraer reproductores
                reproductores = self.extraer_reproductores_de_pagina(soup, url)
                
                # Verificar accesibilidad (solo para los primeros 3 reproductores)
                reproductores_verificados = []
                for j, reproductor in enumerate(reproductores[:3]):
                    if self.verificar_accesibilidad_reproductor(reproductor['url']):
                        reproductor['verificado'] = True
                        self.stats['reproductores_verificados'] += 1
                    else:
                        reproductor['verificado'] = False
                    
                    reproductores_verificados.append(reproductor)
                
                # Añadir reproductores no verificados
                for reproductor in reproductores[3:]:
                    reproductor['verificado'] = False
                    reproductores_verificados.append(reproductor)
                
                evento['reproductores'] = reproductores_verificados
                
                # Actualizar estadísticas
                self.stats['eventos_procesados'] += 1
                if reproductores_verificados:
                    self.stats['eventos_con_reproductores'] += 1
                    self.stats['total_reproductores'] += len(reproductores_verificados)
                
                logger.info(f"   ✅ Encontrados {len(reproductores_verificados)} reproductores")
                
                # Delay entre peticiones
                time.sleep(self.delay)
                
            except Exception as e:
                logger.error(f"❌ Error procesando evento {i+1}: {e}")
                self.stats['errores'] += 1
                continue
        
        return eventos
    
    def generar_xml_con_reproductores(self, eventos, xml_original):
        """Genera XML de salida con reproductores añadidos"""
        try:
            # Crear nuevo XML
            root = ET.Element('eventos')
            root.set('generado', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            root.set('total_eventos', str(self.stats['total_eventos']))
            root.set('eventos_procesados', str(self.stats['eventos_procesados']))
            root.set('eventos_con_reproductores', str(self.stats['eventos_con_reproductores']))
            root.set('total_reproductores', str(self.stats['total_reproductores']))
            root.set('reproductores_verificados', str(self.stats['reproductores_verificados']))
            
            for evento_data in eventos:
                evento_elem = ET.SubElement(root, 'evento')
                
                # Añadir campos originales
                reproductores = evento_data.pop('reproductores', [])
                for key, value in evento_data.items():
                    if value:
                        child = ET.SubElement(evento_elem, key)
                        child.text = str(value)
                
                # Añadir reproductores
                if reproductores:
                    reproductores_elem = ET.SubElement(evento_elem, 'reproductores')
                    reproductores_elem.set('count', str(len(reproductores)))
                    
                    for reproductor in reproductores:
                        reproductor_elem = ET.SubElement(reproductores_elem, 'reproductor')
                        reproductor_elem.set('tipo', reproductor.get('tipo', 'desconocido'))
                        reproductor_elem.set('origen', reproductor.get('origen', 'desconocido'))
                        reproductor_elem.set('verificado', str(reproductor.get('verificado', False)))
                        
                        if reproductor.get('calidad'):
                            reproductor_elem.set('calidad', reproductor['calidad'])
                        
                        reproductor_elem.text = reproductor['url']
                        
                        # Añadir información adicional
                        if reproductor.get('texto'):
                            info_elem = ET.SubElement(reproductor_elem, 'info')
                            info_elem.text = reproductor['texto']
            
            # Convertir a string con formato
            xml_string = ET.tostring(root, encoding='unicode')
            return self.formatear_xml(xml_string)
            
        except Exception as e:
            logger.error(f"❌ Error generando XML: {e}")
            return ""
    
    def formatear_xml(self, xml_string):
        """Formatea XML para mejor legibilidad"""
        try:
            from xml.dom import minidom
            dom = minidom.parseString(xml_string)
            return dom.toprettyxml(indent="  ", encoding=None)
        except:
            return xml_string
    
    def guardar_resultados(self, xml_output, eventos, output_dir="output"):
        """Guarda todos los resultados"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Guardar XML principal
        xml_path = os.path.join(output_dir, "eventos_livetv_sx_con_reproductores.xml")
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_output)
        logger.info(f"💾 XML guardado en: {xml_path}")
        
        # Guardar JSON detallado
        json_path = os.path.join(output_dir, "reproductores_detalle.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'estadisticas': self.stats,
                'eventos': eventos,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 JSON guardado en: {json_path}")
        
        # Generar reporte
        self.generar_reporte(eventos, output_dir)
        
        # Guardar estadísticas
        self.guardar_estadisticas(output_dir)
    
    def generar_reporte(self, eventos, output_dir):
        """Genera reporte detallado en Markdown"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        reporte = f"""# Reporte de Extracción de Reproductores LiveTV.sx

## Estadísticas Generales
- **Fecha de ejecución**: {timestamp}
- **Total de eventos**: {self.stats['total_eventos']}
- **Eventos procesados**: {self.stats['eventos_procesados']}
- **Eventos con reproductores**: {self.stats['eventos_con_reproductores']}
- **Total de reproductores encontrados**: {self.stats['total_reproductores']}
- **Reproductores verificados**: {self.stats['reproductores_verificados']}
- **Errores**: {self.stats['errores']}
- **Tasa de éxito**: {(self.stats['eventos_con_reproductores']/max(self.stats['eventos_procesados'], 1)*100):.1f}%

## Análisis por Tipos de Reproductores
"""
        
        # Análisis por tipos
        tipos_count = {}
        for evento in eventos:
            for reproductor in evento.get('reproductores', []):
                tipo = reproductor.get('tipo', 'desconocido')
                tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
        
        for tipo, count in sorted(tipos_count.items(), key=lambda x: x[1], reverse=True):
            reporte += f"- **{tipo}**: {count} reproductores\n"
        
        reporte += "\n## Detalles por Evento\n"
        
        for i, evento in enumerate(eventos[:20]):  # Limitar a 20 eventos en el reporte
            reproductores = evento.get('reproductores', [])
            reporte += f"\n### {i+1}. {evento.get('nombre', 'Sin nombre')}\n"
            reporte += f"- **URL**: {evento.get('url', 'N/A')}\n"
            reporte += f"- **Deporte**: {evento.get('deporte', 'N/A')}\n"
            reporte += f"- **Fecha**: {evento.get('fecha', 'N/A')} {evento.get('hora', '')}\n"
            reporte += f"- **Reproductores encontrados**: {len(reproductores)}\n"
            
            if reproductores:
                reporte += "- **Lista de reproductores**:\n"
                for j, reproductor in enumerate(reproductores):
                    verificado = "✅" if reproductor.get('verificado') else "❓"
                    reporte += f"  {j+1}. {verificado} {reproductor['url']} ({reproductor.get('tipo', 'N/A')})\n"
        
        # Guardar reporte
        reporte_path = os.path.join(output_dir, "reporte_extraccion.md")
        with open(reporte_path, 'w', encoding='utf-8') as f:
            f.write(reporte)
        logger.info(f"📊 Reporte guardado en: {reporte_path}")
    
    def guardar_estadisticas(self, output_dir):
        """Guarda estadísticas de la ejecución"""
        stats_path = os.path.join(output_dir, "estadisticas.json")
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump({
                **self.stats,
                'timestamp': datetime.now().isoformat(),
                'tasa_exito': self.stats['eventos_con_reproductores']/max(self.stats['eventos_procesados'], 1)*100
            }, f, indent=2)
        logger.info(f"📈 Estadísticas guardadas en: {stats_path}")
    
    def imprimir_resumen_final(self):
        """Imprime resumen final de la ejecución"""
        print("\n" + "="*60)
        print("🎉 RESUMEN FINAL DE EJECUCIÓN")
        print("="*60)
        print(f"📊 Total de eventos: {self.stats['total_eventos']}")
        print(f"✅ Eventos procesados: {self.stats['eventos_procesados']}")
        print(f"🎯 Eventos con reproductores: {self.stats['eventos_con_reproductores']}")
        print(f"📺 Total de reproductores: {self.stats['total_reproductores']}")
        print(f"🔍 Reproductores verificados: {self.stats['reproductores_verificados']}")
        print(f"❌ Errores: {self.stats['errores']}")
        if self.stats['eventos_procesados'] > 0:
            tasa_exito = (self.stats['eventos_con_reproductores']/self.stats['eventos_procesados']*100)
            print(f"📈 Tasa de éxito: {tasa_exito:.1f}%")
        print("="*60)

def main():
    import sys
    
    # Configuración por defecto
    xml_url = 'https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml'
    max_eventos = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    
    print("🚀 Iniciando extractor de reproductores de LiveTV.sx")
    print(f"📋 Configuración: máximo {max_eventos} eventos, delay {delay}s")
    
    # Crear extractor
    extractor = LiveTVReproductorExtractor(delay=delay)
    
    # Descargar y parsear XML
    xml_content = extractor.descargar_xml_eventos(xml_url)
    if not xml_content:
        print("❌ No se pudo descargar el XML")
        sys.exit(1)
    
    eventos = extractor.parsear_xml_eventos(xml_content)
    if not eventos:
        print("❌ No se pudieron extraer eventos del XML")
        sys.exit(1)
    
    # Procesar eventos
    eventos_procesados = extractor.procesar_eventos(eventos, max_eventos)
    
    # Generar XML de salida
    xml_output = extractor.generar_xml_con_reproductores(eventos_procesados, xml_content)
    
    # Guardar resultados
    extractor.guardar_resultados(xml_output, eventos_procesados)
    
    # Mostrar resumen
    extractor.imprimir_resumen_final()
    
    print("✅ Proceso completado exitosamente")

if __name__ == "__main__":
    main()

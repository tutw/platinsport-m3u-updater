#!/usr/bin/env python3
"""
Stream Extractor Premium para LiveTV.sx
Extrae reproductores desde páginas de eventos y genera XML enriquecido
Optimizado para producción con máxima robustez y eficiencia
Version 2.0 - Mejorado y optimizado
"""

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
import time
import json
import os
import hashlib
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict, Optional, Set
import concurrent.futures
from threading import Lock
import signal
import sys

class StreamExtractor:
    def __init__(self, max_workers: int = 3):
        """Inicializa el extractor con configuración optimizada"""
        self.session = self._create_session()
        self.max_workers = max_workers
        self.processed_cache: Dict[str, List[str]] = {}
        self.cache_lock = Lock()
        self.total_requests = 0
        self.successful_extractions = 0
        
        # Configurar logging
        self._setup_logging()
        
        # Patrones mejorados y más específicos
        self.stream_patterns = [
            # M3U8 streams
            r'https?://[^/\s"\'<>]+\.m3u8(?:\?[^"\'<>\s]*)?',
            # MP4 streams
            r'https?://[^/\s"\'<>]+\.mp4(?:\?[^"\'<>\s]*)?',
            # LiveTV webplayers
            r'https?://cdn\.livetv\d*\.(?:me|sx)/webplayer[^"\'<>\s]*\.php[^"\'<>\s]*',
            # YouTube embeds
            r'https?://(?:www\.)?youtube\.com/embed/[A-Za-z0-9_-]{11}',
            # Generic players
            r'https?://[^/\s"\'<>]+/(?:player|stream|embed|live)/[^"\'<>\s]+',
            # CDN streams
            r'https?://[^/\s"\'<>]*(?:cdn|stream|live)[^/\s"\'<>]*\.[^/\s"\'<>]+/[^"\'<>\s]+\.(?:m3u8|mp4|ts)',
        ]
        
        # Palabras clave para validación
        self.stream_keywords = {
            'required': ['stream', 'player', 'embed', 'video', 'm3u8', 'mp4', 'live', 'cdn'],
            'forbidden': ['facebook', 'twitter', 'instagram', 'ads', 'advertisement', 'popup']
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_delay = 1.0
        
    def _create_session(self) -> requests.Session:
        """Crea sesión optimizada con configuración robusta"""
        session = requests.Session()
        
        # Headers realistas para evitar detección
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Configurar adaptadores con reintentos
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _setup_logging(self):
        """Configura sistema de logging avanzado"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('extractor.log', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _rate_limit(self):
        """Implementa rate limiting inteligente"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _get_cache_key(self, url: str) -> str:
        """Genera clave de cache para URL"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def extract_all(self, xml_url: str = 'https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml', 
                   limit: int = 30, use_cache: bool = True) -> None:
        """Función principal mejorada con procesamiento paralelo"""
        
        start_time = time.time()
        self.logger.info(f"🚀 Iniciando extracción premium (límite: {limit} eventos)")
        
        # 1. Descargar y parsear XML
        eventos = self._download_and_parse_xml(xml_url, limit)
        if not eventos:
            return
        
        # 2. Procesar eventos en paralelo
        self._process_events_parallel(eventos, use_cache)
        
        # 3. Generar archivos de salida
        self._save_results_enhanced(eventos)
        
        # 4. Estadísticas finales
        total_time = time.time() - start_time
        self._print_final_stats(eventos, total_time)
    
    def _download_and_parse_xml(self, xml_url: str, limit: int) -> List[Dict]:
        """Descarga y parsea XML con validación robusta"""
        try:
            self.logger.info("📥 Descargando XML...")
            self._rate_limit()
            
            response = self.session.get(xml_url, timeout=30)
            response.raise_for_status()
            
            # Validar tamaño del XML
            if len(response.content) > 50 * 1024 * 1024:  # 50MB
                raise ValueError("XML demasiado grande")
            
            # Parsear XML
            root = ET.fromstring(response.text)
            eventos = []
            
            for evento in root.findall('evento')[:limit]:
                data = {}
                for child in evento:
                    data[child.tag] = (child.text or '').strip()
                
                # Validar evento
                if self._validate_event(data):
                    eventos.append(data)
            
            self.logger.info(f"✅ {len(eventos)} eventos válidos parseados")
            return eventos
            
        except ET.ParseError as e:
            self.logger.error(f"❌ Error parseando XML: {e}")
            return []
        except Exception as e:
            self.logger.error(f"❌ Error descargando XML: {e}")
            return []
    
    def _validate_event(self, event_data: Dict) -> bool:
        """Valida que el evento tenga datos mínimos requeridos"""
        required_fields = ['url', 'nombre']
        return all(event_data.get(field) for field in required_fields)
    
    def _process_events_parallel(self, eventos: List[Dict], use_cache: bool):
        """Procesa eventos en paralelo con límite de hilos"""
        
        def process_single_event(evento_info):
            index, evento = evento_info
            event_name = evento.get('nombre', 'Sin nombre')[:50]
            self.logger.info(f"🔍 {index+1}/{len(eventos)}: {event_name}...")
            
            try:
                reproductores = self.get_reproductores_enhanced(evento['url'], use_cache)
                evento['reproductores'] = reproductores
                evento['extraction_success'] = len(reproductores) > 0
                evento['extraction_timestamp'] = datetime.now().isoformat()
                
                if reproductores:
                    self.successful_extractions += 1
                    self.logger.info(f"   ✅ {len(reproductores)} reproductores encontrados")
                else:
                    self.logger.warning(f"   ⚠️ No se encontraron reproductores")
                    
            except Exception as e:
                self.logger.error(f"   ❌ Error procesando evento: {e}")
                evento['reproductores'] = []
                evento['extraction_success'] = False
                evento['extraction_error'] = str(e)
        
        # Procesar en paralelo con límite de hilos
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(process_single_event, (i, evento)) 
                      for i, evento in enumerate(eventos)]
            
            # Esperar a que terminen todos
            concurrent.futures.wait(futures)
    
    def get_reproductores_enhanced(self, url: str, use_cache: bool = True) -> List[str]:
        """Extrae reproductores con algoritmo mejorado y cache"""
        
        # Verificar cache
        cache_key = self._get_cache_key(url)
        if use_cache:
            with self.cache_lock:
                if cache_key in self.processed_cache:
                    return self.processed_cache[cache_key]
        
        try:
            self._rate_limit()
            self.total_requests += 1
            
            # Realizar petición con límite de tamaño
            response = self.session.get(url, timeout=20, stream=True)
            response.raise_for_status()
            
            # Verificar tamaño de contenido
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 15 * 1024 * 1024:  # 15MB
                self.logger.warning(f"   ⚠️ Página demasiado grande: {content_length} bytes")
                return []
            
            # Leer contenido con límite
            content = b''
            max_size = 10 * 1024 * 1024  # 10MB
            
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > max_size:
                    break
            
            # Parsear contenido
            soup = BeautifulSoup(content, 'html.parser')
            reproductores = self._extract_streams_advanced(soup, url)
            
            # Guardar en cache
            if use_cache:
                with self.cache_lock:
                    self.processed_cache[cache_key] = reproductores
            
            return reproductores
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"   ❌ Error de conexión: {e}")
            return []
        except Exception as e:
            self.logger.error(f"   ❌ Error inesperado: {e}")
            return []
    
    def _extract_streams_advanced(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Algoritmo avanzado de extracción de streams"""
        reproductores = set()
        
        # 1. Buscar en contenedores específicos
        containers = [
            soup.find('div', id='links_block'),
            soup.find('div', class_=re.compile(r'link', re.I)),
            soup.find('div', class_=re.compile(r'player', re.I)),
            soup.find('div', class_=re.compile(r'stream', re.I)),
        ]
        
        # Añadir contenedor principal si no se encuentra específico
        if not any(containers):
            containers.append(soup)
        
        for container in containers:
            if not container:
                continue
                
            # Extraer de iframes
            for iframe in container.find_all('iframe', src=True):
                src = self._normalize_url(iframe['src'], base_url)
                if self._is_valid_stream_enhanced(src):
                    reproductores.add(src)
            
            # Extraer de enlaces
            for link in container.find_all('a', href=True):
                href = self._normalize_url(link['href'], base_url)
                if self._is_valid_stream_enhanced(href):
                    reproductores.add(href)
            
            # Extraer usando patrones regex
            container_text = str(container)
            for pattern in self.stream_patterns:
                matches = re.findall(pattern, container_text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    clean_url = self._clean_url(match)
                    if self._is_valid_stream_enhanced(clean_url):
                        reproductores.add(clean_url)
        
        # 2. Buscar en scripts JavaScript
        for script in soup.find_all('script'):
            if script.string:
                for pattern in self.stream_patterns:
                    matches = re.findall(pattern, script.string, re.IGNORECASE)
                    for match in matches:
                        clean_url = self._clean_url(match)
                        if self._is_valid_stream_enhanced(clean_url):
                            reproductores.add(clean_url)
        
        # Convertir a lista y ordenar por calidad
        resultado = list(reproductores)
        resultado = self._rank_streams_by_quality(resultado)
        
        return resultado[:15]  # Máximo 15 reproductores por evento
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """Normaliza URL relativa a absoluta"""
        if not url:
            return ''
        
        # Limpiar URL
        url = url.strip().strip('"\'')
        
        # Convertir a absoluta si es relativa
        if url.startswith(('http://', 'https://')):
            return url
        else:
            return urljoin(base_url, url)
    
    def _clean_url(self, url: str) -> str:
        """Limpia URL de caracteres no deseados"""
        if not url:
            return ''
        
        # Remover caracteres de escape y comillas
        url = re.sub(r'["\']', '', url)
        url = re.sub(r'\\', '', url)
        
        # Remover parámetros de tracking
        url = re.sub(r'[?&](utm_|ref=|source=|fbclid=)[^&]*', '', url)
        
        return url.strip()
    
    def _is_valid_stream_enhanced(self, url: str) -> bool:
        """Validación avanzada de streams con múltiples criterios"""
        if not url or len(url) < 10:
            return False
        
        try:
            parsed = urlparse(url)
            
            # Verificar esquema válido
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Verificar dominio válido
            if not parsed.netloc or len(parsed.netloc) < 4:
                return False
            
            # Verificar patrones específicos
            url_lower = url.lower()
            
            # Verificar palabras prohibidas
            if any(forbidden in url_lower for forbidden in self.stream_keywords['forbidden']):
                return False
            
            # Verificar patrones de stream
            for pattern in self.stream_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return True
            
            # Verificar palabras clave requeridas
            if any(keyword in url_lower for keyword in self.stream_keywords['required']):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _rank_streams_by_quality(self, streams: List[str]) -> List[str]:
        """Ordena streams por calidad estimada"""
        def get_quality_score(url: str) -> int:
            score = 0
            url_lower = url.lower()
            
            # Preferir ciertos formatos
            if '.m3u8' in url_lower:
                score += 10
            if '.mp4' in url_lower:
                score += 8
            
            # Preferir CDNs conocidos
            if 'cdn' in url_lower:
                score += 5
            
            # Preferir URLs más cortas (menos redireccionamientos)
            score -= len(url) // 50
            
            # Preferir HTTPS
            if url.startswith('https'):
                score += 2
            
            return score
        
        return sorted(streams, key=get_quality_score, reverse=True)
    
    def _save_results_enhanced(self, eventos: List[Dict]):
        """Guarda resultados con formato mejorado y metadatos"""
        os.makedirs('output', exist_ok=True)
        
        # Calcular estadísticas
        stats = self._calculate_stats(eventos)
        
        # 1. XML enriquecido con metadatos
        self._save_enhanced_xml(eventos, stats)
        
        # 2. JSON detallado
        self._save_detailed_json(eventos, stats)
        
        # 3. Archivo M3U para reproductores
        self._save_m3u_playlist(eventos)
        
        # 4. Log detallado
        self._save_detailed_log(eventos, stats)
        
        # 5. Estadísticas CSV
        self._save_stats_csv(eventos)
    
    def _calculate_stats(self, eventos: List[Dict]) -> Dict:
        """Calcula estadísticas detalladas"""
        total_eventos = len(eventos)
        eventos_exitosos = sum(1 for e in eventos if e.get('extraction_success', False))
        total_reproductores = sum(len(e.get('reproductores', [])) for e in eventos)
        
        # Estadísticas por tipo de reproductor
        stream_types = {}
        for evento in eventos:
            for reproductor in evento.get('reproductores', []):
                if '.m3u8' in reproductor.lower():
                    stream_types['M3U8'] = stream_types.get('M3U8', 0) + 1
                elif '.mp4' in reproductor.lower():
                    stream_types['MP4'] = stream_types.get('MP4', 0) + 1
                elif 'youtube' in reproductor.lower():
                    stream_types['YouTube'] = stream_types.get('YouTube', 0) + 1
                else:
                    stream_types['Otros'] = stream_types.get('Otros', 0) + 1
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_eventos': total_eventos,
            'eventos_exitosos': eventos_exitosos,
            'total_reproductores': total_reproductores,
            'tasa_exito': f"{(eventos_exitosos/total_eventos*100):.1f}%" if total_eventos else "0%",
            'promedio_reproductores': f"{(total_reproductores/eventos_exitosos):.1f}" if eventos_exitosos else "0",
            'tipos_streams': stream_types,
            'total_requests': self.total_requests,
            'cache_hits': len(self.processed_cache)
        }
    
    def _save_enhanced_xml(self, eventos: List[Dict], stats: Dict):
        """Guarda XML con estructura mejorada"""
        root = ET.Element('livetv_streams')
        
        # Metadatos
        meta = ET.SubElement(root, 'metadata')
        for key, value in stats.items():
            if key != 'tipos_streams':
                elem = ET.SubElement(meta, key)
                elem.text = str(value)
        
        # Tipos de streams
        tipos_elem = ET.SubElement(meta, 'tipos_streams')
        for tipo, count in stats['tipos_streams'].items():
            tipo_elem = ET.SubElement(tipos_elem, 'tipo')
            tipo_elem.set('name', tipo)
            tipo_elem.text = str(count)
        
        # Eventos
        eventos_elem = ET.SubElement(root, 'eventos')
        
        for evento_data in eventos:
            evento_elem = ET.SubElement(eventos_elem, 'evento')
            reproductores = evento_data.pop('reproductores', [])
            
            # Datos del evento
            for key, value in evento_data.items():
                if value and key not in ['reproductores']:
                    child = ET.SubElement(evento_elem, key)
                    child.text = str(value)
            
            # Reproductores
            if reproductores:
                reprod_elem = ET.SubElement(evento_elem, 'reproductores')
                reprod_elem.set('count', str(len(reproductores)))
                
                for i, reproductor in enumerate(reproductores):
                    rep_elem = ET.SubElement(reprod_elem, 'stream')
                    rep_elem.set('id', str(i+1))
                    rep_elem.set('quality_rank', str(i+1))
                    rep_elem.text = reproductor
        
        # Guardar con formato bonito
        self._prettify_and_save_xml(root, 'output/livetv_streams_enhanced.xml')
    
    def _prettify_and_save_xml(self, root: ET.Element, filename: str):
        """Guarda XML con formato legible"""
        from xml.dom import minidom
        
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        pretty = reparsed.toprettyxml(indent="  ")
        
        # Remover líneas vacías extra
        pretty_lines = [line for line in pretty.split('\n') if line.strip()]
        pretty_final = '\n'.join(pretty_lines)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(pretty_final)
    
    def _save_detailed_json(self, eventos: List[Dict], stats: Dict):
        """Guarda JSON con información detallada"""
        data = {
            'metadata': stats,
            'eventos': eventos,
            'extraction_info': {
                'version': '2.0',
                'user_agent': self.session.headers.get('User-Agent'),
                'total_cache_entries': len(self.processed_cache)
            }
        }
        
        with open('output/livetv_detailed_report.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_m3u_playlist(self, eventos: List[Dict]):
        """Genera playlist M3U para reproductores multimedia"""
        with open('output/livetv_streams.m3u', 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            f.write('#PLAYLIST:LiveTV.sx Streams\n\n')
            
            for evento in eventos:
                nombre = evento.get('nombre', 'Stream sin nombre')
                reproductores = evento.get('reproductores', [])
                
                if reproductores:
                    # Usar el primer reproductor como principal
                    main_stream = reproductores[0]
                    f.write(f'#EXTINF:-1,{nombre}\n')
                    f.write(f'{main_stream}\n\n')
    
    def _save_detailed_log(self, eventos: List[Dict], stats: Dict):
        """Guarda log detallado con análisis"""
        with open('output/extraction_detailed_log.txt', 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("LIVETV.SX STREAM EXTRACTOR - REPORTE DETALLADO\n")
            f.write("="*60 + "\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Versión: 2.0 Premium\n\n")
            
            # Estadísticas generales
            f.write("ESTADÍSTICAS GENERALES:\n")
            f.write("-" * 30 + "\n")
            for key, value in stats.items():
                if key != 'tipos_streams':
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
            
            # Tipos de streams
            f.write(f"\nTIPOS DE STREAMS:\n")
            f.write("-" * 30 + "\n")
            for tipo, count in stats['tipos_streams'].items():
                f.write(f"{tipo}: {count}\n")
            
            # Análisis por evento
            f.write(f"\nANÁLISIS POR EVENTO:\n")
            f.write("-" * 30 + "\n")
            
            for i, evento in enumerate(eventos, 1):
                nombre = evento.get('nombre', 'Sin nombre')
                reproductores = evento.get('reproductores', [])
                success = evento.get('extraction_success', False)
                
                status = "✅ ÉXITO" if success else "❌ FALLO"
                f.write(f"\n{i:2d}. {nombre[:50]}... - {status}\n")
                f.write(f"    URL: {evento.get('url', 'N/A')}\n")
                f.write(f"    Reproductores encontrados: {len(reproductores)}\n")
                
                if evento.get('extraction_error'):
                    f.write(f"    Error: {evento['extraction_error']}\n")
                
                # Mostrar reproductores encontrados
                for j, stream in enumerate(reproductores[:3], 1):  # Solo primeros 3
                    f.write(f"    Stream {j}: {stream}\n")
                
                if len(reproductores) > 3:
                    f.write(f"    ... y {len(reproductores)-3} más\n")
    
    def _save_stats_csv(self, eventos: List[Dict]):
        """Guarda estadísticas en formato CSV"""
        with open('output/extraction_stats.csv', 'w', encoding='utf-8') as f:
            f.write("Evento,URL,Reproductores_Encontrados,Extraccion_Exitosa,Timestamp\n")
            
            for evento in eventos:
                nombre = evento.get('nombre', '').replace(',', ';')
                url = evento.get('url', '')
                num_reproductores = len(evento.get('reproductores', []))
                exitosa = 'Si' if evento.get('extraction_success', False) else 'No'
                timestamp = evento.get('extraction_timestamp', '')
                
                f.write(f'"{nombre}","{url}",{num_reproductores},{exitosa},{timestamp}\n')
    
    def _print_final_stats(self, eventos: List[Dict], total_time: float):
        """Imprime estadísticas finales mejoradas"""
        stats = self._calculate_stats(eventos)
        
        print("\n" + "="*60)
        print("🎉 EXTRACCIÓN COMPLETADA - REPORTE FINAL")
        print("="*60)
        print(f"⏱️  Tiempo total: {total_time:.1f} segundos")
        print(f"📊 Eventos procesados: {stats['total_eventos']}")
        print(f"✅ Extracciones exitosas: {stats['eventos_exitosos']}")
        print(f"🎯 Tasa de éxito: {stats['tasa_exito']}")
        print(f"🔗 Total reproductores: {stats['total_reproductores']}")
        print(f"📈 Promedio por evento: {stats['promedio_reproductores']}")
        print(f"🌐 Peticiones realizadas: {stats['total_requests']}")
        print(f"💾 Entradas en cache: {stats['cache_hits']}")
        
        print(f"\n📁 Archivos generados en output/:")
        print(f"   • livetv_streams_enhanced.xml (XML enriquecido)")
        print(f"   • livetv_detailed_report.json (Reporte JSON)")
        print(f"   • livetv_streams.m3u (Playlist M3U)")
        print(f"   • extraction_detailed_log.txt (Log detallado)")
        print(f"   • extraction_stats.csv (Estadísticas CSV)")
        
        print("\n🚀 ¡Extracción completada con éxito!")

def signal_handler(signum, frame):
    """Maneja señales de interrupción"""
    print("\n⚠️ Extracción interrumpida por el usuario")
    sys.exit(0)

def main():
    # Configurar manejo de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Stream Extractor Premium para LiveTV.sx')
    parser.add_argument('limite', nargs='?', type=int, default=30, 
                       help='Número máximo de eventos a procesar (default: 30)')
    parser.add_argument('--workers', type=int, default=3, 
                       help='Número de hilos paralelos (default: 3)')
    parser.add_argument('--no-cache', action='store_true', 
                       help='Deshabilitar cache de URLs')
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.limite <= 0 or args.limite > 1000:
        print("❌ Error: El límite debe estar entre 1 y 1000")
        sys.exit(1)
    
    if args.workers <= 0 or args.workers > 10:
        print("❌ Error: Los workers deben estar entre 1 y 10")
        sys.exit(1)
    
    #

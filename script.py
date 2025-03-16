import requests
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

def obtener_url_diaria():
    base_url = "https://www.platinsport.com"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers)
    
    if response.status_code != 200:
        print("Error al acceder a la página principal")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    enlaces = soup.find_all("a", href=True)
    
    for a in enlaces:
        href = a["href"]
        match = re.search(r"(https://www\.platinsport\.com/link/\d{2}[a-z]{3}[a-z0-9]+/01\.php)", href, re.IGNORECASE)
        if match:
            url_platinsport = match.group(1)
            print("URL diaria encontrada:", url_platinsport)
            return url_platinsport
    
    print("No se encontró la URL diaria")
    return None

def obtener_enlaces_acestream(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print("Error al acceder a la página de enlaces")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    enlaces = []

    # Buscar enlaces acestream y extraer información
    for div in soup.find_all("div", class_="myDiv2"):
        match = re.search(r"acestream://[a-fA-F0-9]{40}", div.text)
        if match:
            nombre_canal = div.text.strip()
            enlace_acestream = match.group(0)
            
            # Obtener horario y evento
            evento = div.find_previous("h3").text.strip() if div.find_previous("h3") else "Desconocido"
            time_tag = div.find_previous("time")
            horario = time_tag["datetime"] if time_tag else "00:00"

            enlaces.append({
                "nombre": nombre_canal,
                "enlace": enlace_acestream,
                "evento": evento,
                "horario": horario
            })
    
    return enlaces

def generar_lista_m3u(enlaces):
    ruta_lista = "lista.m3u"
    
    with open(ruta_lista, "w", encoding="utf-8") as archivo:
        archivo.write("#EXTM3U\n")
        for canal in enlaces:
            archivo.write(f'#EXTINF:-1 tvg-name="{canal["nombre"]}",{canal["nombre"]} ({canal["horario"]}) - {canal["evento"]}\n')
            archivo.write(f'{canal["enlace"]}\n')
    
    print(f"Lista M3U generada correctamente en {ruta_lista}")

# Ejecutar el script
url_diaria = obtener_url_diaria()
if url_diaria:
    enlaces_acestream = obtener_enlaces_acestream(url_diaria)
    if enlaces_acestream:
        generar_lista_m3u(enlaces_acestream)
    else:
        print("No se encontraron enlaces AceStream.")

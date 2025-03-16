def extraer_enlaces_acestream(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al acceder a", url)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    enlaces_info = []

    # Buscar todos los enlaces con "acestream://"
    for a in soup.find_all("a", href=True):
        if "acestream://" in a["href"]:
            url_acestream = a["href"]
            
            # Buscar nombre del evento en etiquetas cercanas al enlace
            nombre_evento = "Evento Desconocido"
            contenedor_padre = a.find_parent()  # Buscar el contenedor del enlace
            if contenedor_padre:
                texto_nombre = contenedor_padre.get_text(strip=True)
                if texto_nombre and len(texto_nombre) > 2:
                    nombre_evento = texto_nombre
            
            # Buscar hora del evento en el texto asociado
            hora_encontrada = None
            match_hora = re.search(r'\b(\d{1,2}:\d{2})\b', texto_nombre)
            if match_hora:
                try:
                    hora_encontrada = datetime.strptime(match_hora.group(1), "%H:%M").time()
                except ValueError:
                    hora_encontrada = None

            # Si no se encuentra la hora, asignar 23:59 por defecto
            if not hora_encontrada:
                hora_encontrada = datetime.strptime("23:59", "%H:%M").time()

            # Agregar la información extraída a la lista
            enlaces_info.append({
                "nombre": nombre_evento,
                "url": url_acestream,
                "hora": hora_encontrada
            })

    return enlaces_info

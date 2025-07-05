import json
import re
import spacy
from fuzzywuzzy import process, fuzz # Ensure fuzz is imported

# --- Global Dictionaries to store parsed data ---
puntos_turisticos = {}
parroquias_info = {}
locales_servicios = {}
etiquetas_info = {}

# --- Load spaCy model ---
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    print("Descargando modelo spaCy 'es_core_news_sm'...")
    spacy.cli.download("es_core_news_sm")
    nlp = spacy.load("es_core_news_sm")

# --- Data Loading and Processing (from your provided code) ---
file_path = 'turismo__data.jsonl' # Assuming the file is in the same directory

print(f"\nIntentando cargar y procesar datos desde: {file_path}")
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            messages = data.get("messages", [])

            user_message = ""
            assistant_message = ""
            system_role = ""

            for msg in messages:
                if msg["role"] == "system":
                    system_role = msg["content"]
                elif msg["role"] == "user":
                    user_message = msg["content"]
                elif msg["role"] == "assistant":
                    assistant_message = msg["content"]

            # --- Procesar datos de Puntos Turísticos (Cuéntame sobre X) ---
            match_punto = re.search(r"Cuéntame sobre (.+?)\.", user_message)
            if not match_punto:
                match_punto = re.search(r"¿Me puedes dar información de (.+?)\?", user_message)

            if match_punto:
                nombre_punto = match_punto.group(1).strip()
                match_desc_punto = re.search(r"ubicado en la parroquia \*\*([^\*]+?)\*\*.*?: '(.+?)'\. ¡Es un lugar que no te puedes perder!", assistant_message)
                if match_desc_punto:
                    parroquia = match_desc_punto.group(1).strip()
                    descripcion = match_desc_punto.group(2).strip()

                    if nombre_punto not in puntos_turisticos:
                        puntos_turisticos[nombre_punto] = {
                            "parroquia": parroquia,
                            "descripcion": descripcion,
                            "actividades": [],
                            "etiquetas": []
                        }
                    else:
                        puntos_turisticos[nombre_punto]["parroquia"] = parroquia
                        puntos_turisticos[nombre_punto]["descripcion"] = descripcion

                    if parroquia not in parroquias_info:
                        parroquias_info[parroquia] = {"puntos_turisticos": []}
                    if nombre_punto not in parroquias_info[parroquia].get("puntos_turisticos", []):
                        parroquias_info[parroquia]["puntos_turisticos"].append(nombre_punto)

            # --- Procesar datos de Actividades/Precios (Qué puedo hacer en X) ---
            match_actividad_lugar = re.search(r"¿Qué actividades puedo hacer en (.+?)\?", user_message)
            if not match_actividad_lugar:
                match_actividad_lugar = re.search(r"Dime actividades para (.+?)\.", user_message)

            if match_actividad_lugar and "sugerir actividades" in system_role:
                nombre_lugar = match_actividad_lugar.group(1).strip()
                match_actividades_info = re.search(r"En \*\*(.+?)\*\* puedes disfrutar de actividades como: (.+?)\. ¡Espero que te diviertas!", assistant_message)
                if match_actividades_info:
                    actividades_str = match_actividades_info.group(2)
                    actividad_entries = re.findall(r"'([^']+?)' \(precio: ([^)]+?)\)", actividades_str) # Regex ajustada para "no especificado"
                    
                    if nombre_lugar not in puntos_turisticos:
                        puntos_turisticos[nombre_lugar] = {"actividades": [], "etiquetas": []}

                    for act_name, act_price in actividad_entries:
                        puntos_turisticos[nombre_lugar]["actividades"].append({"nombre": act_name.strip(), "precio": act_price.strip()})

            # --- Procesar datos de Parroquias (Dame información detallada sobre la parroquia X) ---
            match_parroquia = re.search(r"Dame información detallada sobre la parroquia (.+?)\.", user_message)
            if match_parroquia:
                nombre_parroquia = match_parroquia.group(1).strip()
                match_desc_parroquia = re.search(r"La parroquia \*\*([^\*]+?)\*\* se caracteriza por: (.+?)\. Tiene una población aproximada de \*\*([^\*]+?)\*\* habitantes y su temperatura promedio es de \*\*([^\*]+?)\*\*.", assistant_message)
                if match_desc_parroquia:
                    desc_parroquia = match_desc_parroquia.group(2).strip()
                    poblacion = match_desc_parroquia.group(3).strip()
                    temperatura = match_desc_parroquia.group(4).strip()
                    
                    if nombre_parroquia not in parroquias_info:
                        parroquias_info[nombre_parroquia] = {"descripcion": desc_parroquia, "poblacion": poblacion, "temperatura": temperatura, "puntos_turisticos": []}
                    else:
                        parroquias_info[nombre_parroquia].update({
                            "descripcion": desc_parroquia,
                            "poblacion": poblacion,
                            "temperatura": temperatura
                        })

            # --- Procesar datos de Locales/Servicios (Qué servicios ofrece X) ---
            match_local_servicio = re.search(r"¿Qué servicios ofrece (.+?)\?", user_message)
            if not match_local_servicio:
                match_local_servicio = re.search(r"Necesito saber los servicios de (.+?)\.", user_message)

            if match_local_servicio and "proporciona información detallada sobre locales y sus servicios" in system_role:
                nombre_local = match_local_servicio.group(1).strip()
                match_servicio_info = re.search(r"\*\*(.+?)\*\* es un local turístico que se describe como: '(.+?)'\. Entre sus servicios se encuentran: \*\*(.+?)\*\*\.", assistant_message)
                if match_servicio_info:
                    local_name_from_assistant = match_servicio_info.group(1).strip()
                    descripcion_local = match_servicio_info.group(2).strip()
                    servicios_str = match_servicio_info.group(3)
                    
                    servicios_list = [s.strip() for s in servicios_str.split(',')]

                    if nombre_local not in locales_servicios:
                        locales_servicios[nombre_local] = {
                            "descripcion": descripcion_local,
                            "servicios": [],
                            "etiquetas": [],
                            "horarios": {}
                        }
                    else:
                        locales_servicios[nombre_local]["descripcion"] = descripcion_local

                    for servicio in servicios_list:
                        if servicio not in locales_servicios[nombre_local]["servicios"]:
                            locales_servicios[nombre_local]["servicios"].append(servicio)

            # --- NUEVO: Procesar datos de Etiquetas Turísticas (Qué significa la etiqueta X) ---
            match_etiqueta_significado = re.search(r"¿Qué significa la etiqueta (.+?)\?", user_message)
            if not match_etiqueta_significado:
                match_etiqueta_significado = re.search(r"Dame la definición de (.+?)\.", user_message)

            if match_etiqueta_significado and "explica el significado de las etiquetas turísticas" in system_role:
                nombre_etiqueta = match_etiqueta_significado.group(1).strip()
                match_etiqueta_desc = re.search(r"La etiqueta '\*\*(.+?)\*\*' se refiere a: \*\*(.+?)\*\*\. Ayuda a categorizar y entender mejor los atractivos turísticos.", assistant_message)
                if match_etiqueta_desc:
                    descripcion_etiqueta = match_etiqueta_desc.group(2).strip()
                    etiquetas_info[nombre_etiqueta] = descripcion_etiqueta

            # --- NUEVO: Procesar datos de Horarios de Atención (Cuál es el horario de X) ---
            match_horario_local = re.search(r"¿Cuál es el horario de atención de (.+?)\?", user_message)
            if not match_horario_local:
                match_horario_local = re.search(r"Dime cuándo abre (.+?)\.", user_message)

            if match_horario_local and "proporciona horarios de atención de locales turísticos" in system_role:
                nombre_local_horario = match_horario_local.group(1).strip()
                match_horario_info = re.search(r"El horario de atención de \*\*(.+?)\*\* es: \*\*(.+?)\*\*\.", assistant_message)
                if match_horario_info:
                    horarios_str = match_horario_info.group(2)
                    
                    horarios_temp = {}
                    dia_horario_matches = re.findall(r"([^:]+?): (.+?)(?:,|$)", horarios_str)
                    for dia, rango_horas in dia_horario_matches:
                        horarios_temp[dia.strip()] = rango_horas.strip()

                    if nombre_local_horario not in locales_servicios:
                        locales_servicios[nombre_local_horario] = {
                            "descripcion": "No disponible",
                            "servicios": [],
                            "etiquetas": [],
                            "horarios": {}
                        }
                    locales_servicios[nombre_local_horario]["horarios"].update(horarios_temp)

            # --- NUEVO: Procesar Puntos Turísticos con Etiquetas (Qué etiquetas tiene X) ---
            match_punto_etiquetas = re.search(r"¿Qué etiquetas tiene (.+?)\?", user_message)
            if match_punto_etiquetas and "puede listar las etiquetas de los puntos turísticos" in system_role:
                nombre_punto_etiqueta = match_punto_etiquetas.group(1).strip()
                match_etiquetas_punto_info = re.search(r"\*\*(.+?)\*\* está asociado con las etiquetas: \*\*(.+?)\*\*\.", assistant_message)
                if match_etiquetas_punto_info:
                    etiquetas_str = match_etiquetas_punto_info.group(2)
                    etiquetas_list = [e.strip() for e in etiquetas_str.split(',')]

                    if nombre_punto_etiqueta not in puntos_turisticos:
                        puntos_turisticos[nombre_punto_etiqueta] = {
                            "parroquia": "No disponible",
                            "descripcion": "No disponible",
                            "actividades": [],
                            "etiquetas": []
                        }
                    for etiq in etiquetas_list:
                        if etiq not in puntos_turisticos[nombre_punto_etiqueta]["etiquetas"]:
                            puntos_turisticos[nombre_punto_etiqueta]["etiquetas"].append(etiq)

            # --- NUEVO: Procesar Locales Turísticos con Etiquetas (Qué etiquetas tiene X) ---
            match_local_etiquetas = re.search(r"¿Qué etiquetas tiene (.+?)\?", user_message)
            if match_local_etiquetas and "puede listar las etiquetas de los locales turísticos" in system_role:
                nombre_local_etiqueta = match_local_etiquetas.group(1).strip()
                match_etiquetas_local_info = re.search(r"\*\*(.+?)\*\* está asociado con las etiquetas: \*\*(.+?)\*\*\.", assistant_message)
                if match_etiquetas_local_info:
                    etiquetas_str = match_etiquetas_local_info.group(2)
                    etiquetas_list = [e.strip() for e in etiquetas_str.split(',')]

                    if nombre_local_etiqueta not in locales_servicios:
                        locales_servicios[nombre_local_etiqueta] = {
                            "descripcion": "No disponible",
                            "servicios": [],
                            "etiquetas": [],
                            "horarios": {}
                        }
                    for etiq in etiquetas_list:
                        if etiq not in locales_servicios[nombre_local_etiqueta]["etiquetas"]:
                            locales_servicios[nombre_local_etiqueta]["etiquetas"].append(etiq)

    print("Datos turísticos (puntos, parroquias, locales, etiquetas, horarios) cargados y procesados exitosamente.")

except FileNotFoundError:
    print(f"Error: El archivo '{file_path}' no se encontró.")
    print("Por favor, asegúrate de que 'turismo__data.jsonl' esté en el mismo directorio que este script.")
    print("Saliendo del programa.")
    exit()
except json.JSONDecodeError as e:
    print(f"Error al decodificar JSON en una línea: {e}. Asegúrate de que el archivo es un .jsonl válido.")
    print("Saliendo del programa.")
    exit()
except Exception as e:
    print(f"Ocurrió un error inesperado al cargar o procesar los datos: {e}")
    print("Saliendo del programa.")
    exit()

# --- Funciones de Procesamiento del Lenguaje Natural (NLU) ---

def reconocer_intencion(texto):
    """
    Identifica la intención principal del usuario.
    """
    texto_lower = texto.lower()

    # 1. Intentos de reconocer la intención por palabras clave explícitas
    if any(palabra in texto_lower for palabra in ["cuéntame sobre", "información de", "dime sobre", "dame información de", "quiero saber de"]):
        return "informacion_general_lugar"
    elif any(palabra in texto_lower for palabra in ["qué puedo hacer", "actividades en", "actividades para"]):
        return "buscar_actividades"
    elif any(palabra in texto_lower for palabra in ["qué servicios ofrece", "servicios de", "qué hay en"]):
        return "buscar_servicios_local"
    elif any(palabra in texto_lower for palabra in ["dame información detallada sobre la parroquia", "cuéntame de la parroquia", "sobre la parroquia"]):
        return "informacion_parroquia"
    elif any(palabra in texto_lower for palabra in ["qué significa la etiqueta", "definición de", "explica la etiqueta"]):
        return "explicar_etiqueta"
    elif any(palabra in texto_lower for palabra in ["cuál es el horario de", "cuándo abre", "horario de atención de"]):
        return "consultar_horario"
    elif any(palabra in texto_lower for palabra in ["qué etiquetas tiene", "etiquetas de"]):
        return "listar_etiquetas"
    elif any(palabra in texto_lower for palabra in ["hola", "saludos", "qué tal", "buenos días", "buenas tardes", "buenas noches"]):
        return "saludo"
    elif any(palabra in texto_lower for palabra in ["gracias", "agradezco", "te lo agradezco"]):
        return "agradecimiento"
    elif any(palabra in texto_lower for palabra in ["adiós", "chau", "hasta luego", "nos vemos", "bye"]):
        return "despedida"
    
    # 2. Si no se encontró una intención explícita, intenta inferir una
    # a partir de la presencia de una entidad detectada.
    entidades_detectadas = extraer_entidades(texto)
    if entidades_detectadas.get("lugar_turistico") or \
       entidades_detectadas.get("local_turistico") or \
       entidades_detectadas.get("parroquia") or \
       entidades_detectadas.get("nombre_etiqueta") or \
       entidades_detectadas.get("ambiguous_entity"): # <--- IMPORTANT: Added check for ambiguous_entity
        return "informacion_general_lugar" 

    return "desconocida"

def extraer_entidades(texto):
    """
    Extrae entidades como nombres de lugares, parroquias, locales o etiquetas
    usando fuzzy matching y spaCy. Si hay ambigüedad con nombres similares,
    devuelve las posibles opciones.
    """
    entidades = {}
    texto_lower = texto.lower()
    
    all_known_names = (
        list(puntos_turisticos.keys()) +
        list(locales_servicios.keys()) +
        list(parroquias_info.keys()) +
        list(etiquetas_info.keys())
    )
    
    # Usar process.extract para obtener múltiples coincidencias por encima de un umbral
    # Usamos fuzz.partial_ratio para coincidencias parciales como "malecon" en "Malecón Luz de América"
    # y reducimos el cutoff para capturar más posibilidades.
    potential_matches = process.extract(texto, all_known_names, limit=5, scorer=fuzz.partial_ratio) # Removed score_cutoff

    relevant_matches = []
    score_cutoff = 70 # Define the cutoff here
    for matched_name, score in potential_matches:
        if score >= score_cutoff: # Filter based on the cutoff
            relevant_matches.append((matched_name, score))
    
    # Lógica para manejar ambigüedad
    if relevant_matches:
        relevant_matches.sort(key=lambda x: x[1], reverse=True)
        
        best_match_name, best_score = relevant_matches[0]

        # Considera si hay más de un match y si el mejor match no es significativamente mejor que el siguiente
        if len(relevant_matches) > 1 and (best_score - relevant_matches[1][1] <= 10): # If score difference is 10 or less, consider it ambiguous
            ambiguous_places = []
            for name, score in relevant_matches:
                if score >= (best_score - 10): # Include all matches within 10 points of the best score
                    ambiguous_places.append(name)
            entidades["ambiguous_entity"] = ambiguous_places
            return entidades
        else:
            # If it's a clear best match
            if best_match_name in puntos_turisticos:
                entidades["lugar_turistico"] = best_match_name
            elif best_match_name in locales_servicios:
                entidades["local_turistico"] = best_match_name
            elif best_match_name in parroquias_info:
                entidades["parroquia"] = best_match_name
            elif best_match_name in etiquetas_info:
                entidades["nombre_etiqueta"] = best_match_name
            return entidades

    # Fallback a spaCy si fuzzy matching no encontró nada relevante
    doc = nlp(texto)
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC", "ORG"]:
            for nombre_punto in puntos_turisticos.keys():
                if ent.text.lower() in nombre_punto.lower():
                    if "lugar_turistico" not in entidades:
                        entidades["lugar_turistico"] = nombre_punto
                        return entidades 
            
            for nombre_local in locales_servicios.keys():
                if ent.text.lower() in nombre_local.lower():
                    if "local_turistico" not in entidades:
                        entidades["local_turistico"] = nombre_local
                        return entidades
                        
            for nombre_parroquia in parroquias_info.keys():
                if ent.text.lower() in nombre_parroquia.lower():
                    if "parroquia" not in entidades:
                        entidades["parroquia"] = nombre_parroquia
                        return entidades
                        
    return entidades



# --- Lógica de Respuesta del Chatbot ---
def generar_respuesta(intencion, entidades):
    """
    Genera la respuesta del chatbot basada en la intención y las entidades extraídas.
    """
    respuesta = "Lo siento, no entendí tu solicitud. ¿Puedes reformularla? Estoy diseñado para hablar sobre puntos turísticos, parroquias, locales, actividades, servicios, etiquetas y horarios."

    # --- Manejo de ambigüedad primero ---
    if "ambiguous_entity" in entidades and entidades["ambiguous_entity"]:
        opciones = [f"**{nombre}**" for nombre in entidades["ambiguous_entity"]]
        if len(opciones) > 1:
            # Modified response for ambiguous entities
            respuesta = f"¡Claro! Tenemos {', '.join(opciones)}. ¿De cuál te interesa saber más?"
            return respuesta # Salir temprano si hay ambigüedad
            
    if intencion == "saludo":
        respuesta = "¡Hola! Soy tu asistente turístico. ¿Sobre qué lugar o parroquia de Santo Domingo de los Tsáchilas te gustaría saber?"
    elif intencion == "agradecimiento":
        respuesta = "De nada. Estoy aquí para ayudarte con cualquier otra consulta."
    elif intencion == "despedida":
        respuesta = "¡Hasta luego! Que tengas un excelente día. ¡Espero verte pronto explorando Santo Domingo!"

    elif intencion == "informacion_general_lugar":
        lugar = entidades.get("lugar_turistico")
        local = entidades.get("local_turistico")
        parroquia = entidades.get("parroquia")
        etiqueta = entidades.get("nombre_etiqueta")

        if lugar and lugar in puntos_turisticos:
            info = puntos_turisticos[lugar]
            respuesta = f"¡Claro! **{lugar}** es un punto turístico ubicado en la parroquia **{info.get('parroquia', 'desconocida')}**. Se describe como: *'{info.get('descripcion', 'No hay descripción disponible.')}'*. ¡Es un lugar que no te puedes perder!"
        elif local and local in locales_servicios:
            info_local = locales_servicios[local]
            servicios = ", ".join([f"'{s}'" for s in info_local.get("servicios", [])])
            respuesta = (f"El local turístico **'{local}'** se describe como: *'{info_local.get('descripcion', 'No hay descripción disponible.')}'*. "
                         f"Ofrece los siguientes servicios: {servicios}.")
        elif parroquia and parroquia in parroquias_info:
            info = parroquias_info[parroquia]
            puntos_relacionados = info.get("puntos_turisticos", [])
            puntos_str = ", ".join(puntos_relacionados) if puntos_relacionados else "ninguno registrado."
            respuesta = (f"La parroquia **{parroquia}** se caracteriza por: {info.get('descripcion', 'No hay descripción disponible.')}. "
                         f"Tiene una población aproximada de **{info.get('poblacion', 'N/A')}** habitantes y su temperatura promedio es de **{info.get('temperatura', 'N/A')}°C**. "
                         f"Algunos puntos turísticos asociados son: {puntos_str}. ¡Es un lugar encantador para visitar!")
        elif etiqueta and etiqueta in etiquetas_info:
            respuesta = f"La etiqueta '**{etiqueta}**' se refiere a: **{etiquetas_info[etiqueta]}**. Ayuda a categorizar y entender mejor los atractivos turísticos."
        else:
            respuesta = "No encontré información sobre ese punto turístico, local, parroquia o etiqueta. ¿Podrías especificar el nombre o reformular tu pregunta?"

    elif intencion == "informacion_parroquia":
        parroquia = entidades.get("parroquia")
        if parroquia and parroquia in parroquias_info:
            info = parroquias_info[parroquia]
            puntos_relacionados = info.get("puntos_turisticos", [])
            puntos_str = ", ".join(puntos_relacionados) if puntos_relacionados else "ninguno registrado."
            respuesta = (f"La parroquia **{parroquia}** se caracteriza por: {info.get('descripcion', 'No hay descripción disponible.')}. "
                         f"Tiene una población aproximada de **{info.get('poblacion', 'N/A')}** habitantes y su temperatura promedio es de **{info.get('temperatura', 'N/A')}°C**. "
                         f"Algunos puntos turísticos asociados son: {puntos_str}. ¡Es un lugar encantador para visitar!")
        else:
            respuesta = "No encontré información detallada sobre esa parroquia. Asegúrate de escribir el nombre correctamente."

    elif intencion == "buscar_actividades":
        lugar = entidades.get("lugar_turistico")
        if lugar and lugar in puntos_turisticos and puntos_turisticos[lugar].get("actividades"):
            actividades = puntos_turisticos[lugar]["actividades"]
            lista_actividades = []
            for act in actividades:
                precio_info = f" (precio: {act.get('precio', 'no especificado')})" if act.get('precio') else ""
                lista_actividades.append(f"'{act['nombre']}'{precio_info}")
            respuesta = f"En **{lugar}** puedes disfrutar de las siguientes actividades: {', '.join(lista_actividades)}."
        else:
            respuesta = f"No encontré actividades registradas para **{lugar if lugar else 'ese lugar'}**. ¿Quizás buscas otra información o un lugar diferente?"

    elif intencion == "buscar_servicios_local":
        local = entidades.get("local_turistico")
        if local and local in locales_servicios:
            info_local = locales_servicios[local]
            servicios = ", ".join([f"'{s}'" for s in info_local.get("servicios", [])])
            respuesta = (f"El local turístico **'{local}'** se describe como: *'{info_local.get('descripcion', 'No hay descripción disponible.')}'*. "
                         f"Ofrece los siguientes servicios: {servicios}.")
        else:
            respuesta = "No encontré información sobre los servicios de ese local. ¿Podrías especificar el nombre?"
            
    elif intencion == "explicar_etiqueta":
        etiqueta = entidades.get("nombre_etiqueta")
        if etiqueta and etiqueta in etiquetas_info:
            respuesta = f"La etiqueta '**{etiqueta}**' se refiere a: **{etiquetas_info[etiqueta]}**. Ayuda a categorizar y entender mejor los atractivos turísticos."
        else:
            respuesta = "No encontré el significado de esa etiqueta. ¿Podrías confirmarla?"

    elif intencion == "consultar_horario":
        local = entidades.get("local_turistico")
        if local and local in locales_servicios and locales_servicios[local].get("horarios"):
            horarios = locales_servicios[local]["horarios"]
            if horarios:
                horarios_str = ", ".join([f"{dia}: {rango}" for dia, rango in horarios.items()])
                respuesta = f"El horario de atención de **{local}** es: **{horarios_str}**."
            else:
                respuesta = f"No se encontró información de horarios para **{local}**."
        else:
            respuesta = "No encontré información de horarios para ese local. ¿Podrías especificar el nombre?"

    elif intencion == "listar_etiquetas":
        lugar_o_local = entidades.get("lugar_turistico") or entidades.get("local_turistico")
        if lugar_o_local:
            etiquetas_encontradas = []
            if lugar_o_local in puntos_turisticos:
                etiquetas_encontradas.extend(puntos_turisticos[lugar_o_local].get("etiquetas", []))
            if lugar_o_local in locales_servicios:
                etiquetas_encontradas.extend(locales_servicios[lugar_o_local].get("etiquetas", []))
            
            if etiquetas_encontradas:
                etiquetas_unicas = sorted(list(set(etiquetas_encontradas)))
                respuesta = f"**{lugar_o_local}** está asociado con las etiquetas: **{', '.join(etiquetas_unicas)}**."
            else:
                respuesta = f"No encontré etiquetas asociadas a **{lugar_o_local}**."
        else:
            respuesta = "Necesito saber de qué punto turístico o local quieres conocer las etiquetas."
            
    return respuesta

# --- Bucle Principal del Chatbot ---

def iniciar_chatbot():
    print("--- ¡Bienvenido al Chatbot Turístico de Santo Domingo de los Tsáchilas! ---")
    print("Puedes preguntar sobre:")
    print(" - Información general de un punto turístico (ej. 'Cuéntame sobre Parque Zaracay.')")
    print(" - Actividades en un lugar (ej. '¿Qué puedo hacer en Malecón Luz de América?')")
    print(" - Servicios de un local (ej. '¿Qué servicios ofrece Agachaditos?')")
    print(" - Información detallada de una parroquia (ej. 'Dame información detallada sobre la parroquia El Esfuerzo.')")
    print(" - Significado de una etiqueta (ej. '¿Qué significa la etiqueta Aventura?')")
    print(" - Horarios de un local (ej. '¿Cuál es el horario de atención de La Canoa?')")
    print(" - Etiquetas de un lugar/local (ej. '¿Qué etiquetas tiene El Paraíso?')")
    print("\nEscribe 'salir' para terminar la conversación.")
    
    while True:
        entrada_usuario = input("Tú: ")
        if entrada_usuario.lower() == 'salir':
            print("Chatbot: ¡Gracias por usar el chatbot! ¡Hasta pronto!")
            break

        intencion = reconocer_intencion(entrada_usuario)
        entidades = extraer_entidades(entrada_usuario)
        respuesta = generar_respuesta(intencion, entidades)
        print(f"Chatbot: {respuesta}")

# --- Ejecutar el Chatbot ---
if __name__ == "__main__":
    iniciar_chatbot()
from flask import Flask, request, jsonify
import json
import re
import spacy
from fuzzywuzzy import process, fuzz # Ensure fuzz is imported

# --- Global Dictionaries to store parsed data ---
puntos_turisticos = {}
parroquias_info = {}
locales_servicios = {}
etiquetas_info = {}

# --- Inicializa la aplicación Flask ---
app = Flask(__name__)

# --- Carga el modelo spaCy y los datos turísticos SOLO UNA VEZ al iniciar la app ---
# Esto se hará fuera de cualquier ruta para que se cargue una sola vez.
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    print("Descargando modelo spaCy 'es_core_news_sm'...")
    spacy.cli.download("es_core_news_sm")
    nlp = spacy.load("es_core_news_sm")

# --- Data Loading and Processing (versión simplificada para el nuevo formato) ---
file_path = 'turismo_data_completo_v2.jsonl'

print(f"\nCargando datos desde: {file_path}")
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            messages = data.get("messages", [])

            user_message = ""
            assistant_message = ""

            for msg in messages:
                if msg["role"] == "user":
                    user_message = msg["content"]
                elif msg["role"] == "assistant":
                    assistant_message = msg["content"]

            # Extraer nombre del lugar de la pregunta del usuario
            nombre_lugar = None
            
            # Patrones para extraer nombres de lugares
            patterns = [
                r"Cuéntame sobre (.+)",
                r"¿Qué actividades puedo hacer en (.+)\?",
                r"¿Dónde se encuentra (.+)\?",
                r"¿Cuánto cuestan las actividades en (.+)\?",
                r"¿Qué servicios ofrece (.+)\?",
                r"¿Cuáles son los horarios de (.+)\?",
                r"Cuéntame sobre la parroquia (.+)"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, user_message)
                if match:
                    nombre_lugar = match.group(1).strip()
                    break
            
            if nombre_lugar:
                # Extraer información de la respuesta del asistente
                info_extraida = {}
                
                # Procesar respuestas de puntos turísticos
                if "es un punto turístico" in assistant_message or "es un punto turÃ­stico" in assistant_message:
                    # Extraer parroquia
                    parroquia_patterns = [
                        r"ubicado en la parroquia (.+?)\.",
                        r"ubicado en la parroquia (.+?) ",
                        r"se encuentra en la parroquia \*\*(.+?)\*\*"
                    ]
                    
                    for pattern in parroquia_patterns:
                        parroquia_match = re.search(pattern, assistant_message)
                        if parroquia_match:
                            info_extraida["parroquia"] = parroquia_match.group(1).strip()
                            break
                    
                    # Extraer descripción (el texto después del nombre del lugar)
                    desc_patterns = [
                        rf"\*\*{re.escape(nombre_lugar)}\*\* es un punto turístico[^.]*?\. (.+?)\. La parroquia",
                        rf"\*\*{re.escape(nombre_lugar)}\*\* es un punto turÃ­stico[^.]*?\. (.+?)\. La parroquia",
                        rf"es un punto turístico[^.]*?\. (.+?)\.",
                        rf"es un punto turÃ­stico[^.]*?\. (.+?)\."
                    ]
                    
                    for pattern in desc_patterns:
                        desc_match = re.search(pattern, assistant_message)
                        if desc_match:
                            descripcion = desc_match.group(1).strip()
                            # Limpiar la descripción de texto adicional
                            if "La parroquia" in descripcion:
                                descripcion = descripcion.split("La parroquia")[0].strip()
                            info_extraida["descripcion"] = descripcion
                            break
                    
                    # Extraer actividades si están presentes
                    act_patterns = [
                        r"Las actividades disponibles incluyen: (.+?)\.",
                        r"actividades disponibles incluyen: (.+?)\."
                    ]
                    
                    for pattern in act_patterns:
                        act_match = re.search(pattern, assistant_message)
                        if act_match:
                            actividades_str = act_match.group(1).strip()
                            actividades_list = []
                            if actividades_str and actividades_str != "":
                                for act in actividades_str.split(";"):
                                    if act.strip():
                                        act_info = {"nombre": act.strip()}
                                        actividades_list.append(act_info)
                            info_extraida["actividades"] = actividades_list
                            break
                    
                    # Extraer categorías/etiquetas
                    cat_patterns = [
                        r"Este lugar está categorizado como: (.+?)\.",
                        r"estÃ¡ categorizado como: (.+?)\."
                    ]
                    
                    for pattern in cat_patterns:
                        cat_match = re.search(pattern, assistant_message)
                        if cat_match:
                            etiquetas_str = cat_match.group(1).strip()
                            if etiquetas_str and etiquetas_str != "":
                                info_extraida["etiquetas"] = [etq.strip() for etq in etiquetas_str.split(",")]
                            break
                    
                    # Asegurar que actividades y etiquetas existan como listas vacías
                    if "actividades" not in info_extraida:
                        info_extraida["actividades"] = []
                    if "etiquetas" not in info_extraida:
                        info_extraida["etiquetas"] = []
                    
                    # Guardar en puntos_turisticos
                    if nombre_lugar not in puntos_turisticos:
                        puntos_turisticos[nombre_lugar] = {}
                    puntos_turisticos[nombre_lugar].update(info_extraida)
                    
                    # También asociar el punto turístico con su parroquia
                    if "parroquia" in info_extraida:
                        parroquia = info_extraida["parroquia"]
                        if parroquia not in parroquias_info:
                            parroquias_info[parroquia] = {"puntos_turisticos": []}
                        if nombre_lugar not in parroquias_info[parroquia]["puntos_turisticos"]:
                            parroquias_info[parroquia]["puntos_turisticos"].append(nombre_lugar)
                
                
                # Extraer información de parroquias
                elif "es una parroquia de Santo Domingo" in assistant_message or "es una parroquia" in assistant_message:
                    # Extraer información de parroquia
                    desc_patterns = [
                        r"que se caracteriza por: (.+?)\.",
                        r"se caracteriza por: (.+?)\."
                    ]
                    
                    for pattern in desc_patterns:
                        desc_match = re.search(pattern, assistant_message)
                        if desc_match:
                            info_extraida["descripcion"] = desc_match.group(1).strip()
                            break
                    
                    # Extraer población
                    pob_patterns = [
                        r"población aproximada de (.+?) habitantes",
                        r"poblaciÃ³n aproximada de (.+?) habitantes"
                    ]
                    
                    for pattern in pob_patterns:
                        pob_match = re.search(pattern, assistant_message)
                        if pob_match:
                            info_extraida["poblacion"] = pob_match.group(1).strip()
                            break
                    
                    # Extraer temperatura
                    temp_patterns = [
                        r"temperatura promedio de (.+?)°C",
                        r"temperatura promedio de (.+?)Â°C"
                    ]
                    
                    for pattern in temp_patterns:
                        temp_match = re.search(pattern, assistant_message)
                        if temp_match:
                            info_extraida["temperatura"] = temp_match.group(1).strip() + "°C"
                            break
                    
                    # Guardar en parroquias_info
                    if nombre_lugar not in parroquias_info:
                        parroquias_info[nombre_lugar] = {"puntos_turisticos": []}
                    parroquias_info[nombre_lugar].update(info_extraida)
                
                # Extraer información de locales turísticos
                elif "es un local turístico en Santo Domingo de los Tsáchilas" in assistant_message:
                    # Extraer información de local
                    desc_match = re.search(r"Descripción: ([^|]+)", assistant_message)
                    if desc_match:
                        info_extraida["descripcion"] = desc_match.group(1).strip()
                    
                    # Extraer servicios
                    serv_match = re.search(r"Servicios: ([^|]+)", assistant_message)
                    if serv_match:
                        servicios_str = serv_match.group(1).strip()
                        info_extraida["servicios"] = [serv.strip() for serv in servicios_str.split("; ") if serv.strip()]
                    
                    # Extraer horarios
                    hor_match = re.search(r"Horarios: ([^|]+)", assistant_message)
                    if hor_match:
                        horarios_str = hor_match.group(1).strip()
                        horarios_dict = {}
                        for horario in horarios_str.split("; "):
                            if ":" in horario:
                                dia, horas = horario.split(":", 1)
                                horarios_dict[dia.strip()] = horas.strip()
                        info_extraida["horarios"] = horarios_dict
                    
                    # Guardar en locales_servicios
                    if nombre_lugar not in locales_servicios:
                        locales_servicios[nombre_lugar] = {"etiquetas": []}
                    locales_servicios[nombre_lugar].update(info_extraida)

    print("Datos turísticos (puntos, parroquias, locales, etiquetas, horarios) cargados y procesados exitosamente.")
    
    # Sistema de depuración - mostrar estadísticas de datos cargados
    print(f"\n=== ESTADÍSTICAS DE DATOS CARGADOS ===")
    print(f"📍 Puntos turísticos: {len(puntos_turisticos)}")
    print(f"🏘️ Parroquias: {len(parroquias_info)}")
    print(f"🏪 Locales/servicios: {len(locales_servicios)}")
    print(f"🏷️ Etiquetas: {len(etiquetas_info)}")
    
    # Mostrar algunos ejemplos de puntos turísticos con sus actividades
    if puntos_turisticos:
        print(f"\n=== EJEMPLOS DE PUNTOS TURÍSTICOS ===")
        for i, (nombre, info) in enumerate(list(puntos_turisticos.items())[:3]):
            print(f"{i+1}. {nombre}")
            print(f"   Parroquia: {info.get('parroquia', 'N/A')}")
            print(f"   Actividades: {len(info.get('actividades', []))}")
            if info.get('actividades'):
                for act in info['actividades'][:2]:  # Mostrar solo las primeras 2
                    precio = act.get('precio', 'Sin precio')
                    print(f"     - {act['nombre']} (Precio: {precio})")
            print(f"   Etiquetas: {len(info.get('etiquetas', []))}")
            print()
    
    print("=" * 50)
except FileNotFoundError:
    print(f"Error: El archivo '{file_path}' no se encontró.")
    print("Por favor, asegúrate de que 'turismo_data_completo_v2.jsonl' esté en el mismo directorio que este script.")
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
# Coloca aquí tus funciones reconocer_intencion, extraer_entidades, generar_respuesta
# Asegúrate de que la función extraer_entidades esté actualizada con la corrección
# del 'score_cutoff' que te di anteriormente.

def reconocer_intencion(texto):
    # ... (tu código para reconocer_intencion) ...
    texto_lower = texto.lower()

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

    entidades_detectadas = extraer_entidades(texto)
    if entidades_detectadas.get("lugar_turistico") or \
       entidades_detectadas.get("local_turistico") or \
       entidades_detectadas.get("parroquia") or \
       entidades_detectadas.get("nombre_etiqueta") or \
       entidades_detectadas.get("ambiguous_entity"):
        return "informacion_general_lugar" 

    return "desconocida"

def extraer_entidades(texto):
    # ... (tu código para extraer_entidades con la corrección del score_cutoff) ...
    entidades = {}
    texto_lower = texto.lower()

    all_known_names = (
        list(puntos_turisticos.keys()) +
        list(locales_servicios.keys()) +
        list(parroquias_info.keys()) +
        list(etiquetas_info.keys())
    )

    # Primero buscar coincidencias exactas (caso insensible)
    for name in all_known_names:
        if name.lower() == texto_lower:
            if name in puntos_turisticos:
                entidades["lugar_turistico"] = name
            elif name in locales_servicios:
                entidades["local_turistico"] = name
            elif name in parroquias_info:
                entidades["parroquia"] = name
            elif name in etiquetas_info:
                entidades["nombre_etiqueta"] = name
            return entidades

    # Luego buscar coincidencias parciales usando fuzzy matching
    potential_matches = process.extract(texto, all_known_names, limit=5, scorer=fuzz.partial_ratio)

    relevant_matches = []
    score_cutoff = 70
    for matched_name, score in potential_matches:
        if score >= score_cutoff:
            relevant_matches.append((matched_name, score))

    if relevant_matches:
        relevant_matches.sort(key=lambda x: x[1], reverse=True)

        best_match_name, best_score = relevant_matches[0]

        # Verificar si hay múltiples coincidencias muy similares
        # Pero filtrar casos donde una cadena contiene a otra (como "Malecón Luz de América" y "Luz de América")
        if len(relevant_matches) > 1:
            # Filtrar matches que son subcadenas de otros matches
            filtered_matches = []
            for name, score in relevant_matches:
                if score >= (best_score - 10):
                    # Verificar si este nombre es una subcadena de otro nombre con score similar
                    is_substring = False
                    for other_name, other_score in relevant_matches:
                        if (name != other_name and 
                            abs(score - other_score) <= 10 and
                            (name.lower() in other_name.lower() or other_name.lower() in name.lower())):
                            # Si ambos nombres son similares y uno contiene al otro, 
                            # preferir el más largo (más específico)
                            if len(other_name) > len(name):
                                is_substring = True
                                break
                    
                    if not is_substring:
                        filtered_matches.append((name, score))
            
            # Si después del filtrado tenemos múltiples opciones genuinamente diferentes
            if len(filtered_matches) > 1:
                entidades["ambiguous_entity"] = [name for name, score in filtered_matches]
                return entidades
            elif len(filtered_matches) == 1:
                best_match_name = filtered_matches[0][0]

        if best_match_name in puntos_turisticos:
            entidades["lugar_turistico"] = best_match_name
        elif best_match_name in locales_servicios:
            entidades["local_turistico"] = best_match_name
        elif best_match_name in parroquias_info:
            entidades["parroquia"] = best_match_name
        elif best_match_name in etiquetas_info:
            entidades["nombre_etiqueta"] = best_match_name
        return entidades

    # Fallback: usar spaCy para reconocimiento de entidades nombradas
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

def generar_respuesta(intencion, entidades):
    # ... (tu código para generar_respuesta con la mejora para la ambigüedad) ...
    respuesta = "🤔 ¡Hola! Me encantaría ayudarte, pero no estoy seguro de lo que buscas exactamente.\n\n"
    respuesta += "💡 **Puedo ayudarte con:**\n"
    respuesta += "   • 🏞️ Información sobre puntos turísticos\n"
    respuesta += "   • 🏘️ Detalles de parroquias\n"
    respuesta += "   • 🏪 Servicios de locales turísticos\n"
    respuesta += "   • 🎯 Actividades disponibles\n"
    respuesta += "   • 🏷️ Significado de etiquetas\n"
    respuesta += "   • 🕐 Horarios de atención\n\n"
    respuesta += "🗺️ ¿Podrías reformular tu pregunta o decirme específicamente qué te gustaría saber sobre Santo Domingo de los Tsáchilas? ¡Estoy aquí para ayudarte! 😊"

    if "ambiguous_entity" in entidades and entidades["ambiguous_entity"]:
        opciones = [f"**{nombre}**" for nombre in entidades["ambiguous_entity"]]
        if len(opciones) > 1:
            respuesta = f"¡Perfecto! 🎯 Veo que tenemos varias opciones fantásticas relacionadas con tu búsqueda:\n\n"
            for i, nombre in enumerate(entidades["ambiguous_entity"], 1):
                respuesta += f"   {i}. {nombre}\n"
            respuesta += f"\n✨ Cada uno de estos lugares tiene características únicas y especiales. ¿Podrías decirme específicamente sobre cuál te gustaría saber más?\n\n"
            respuesta += f"¡Estoy emocionado de contarte todos los detalles! 😊"
            return respuesta

    if intencion == "saludo":
        respuesta = "¡Hola! 👋 ¡Qué gusto saludarte! Soy tu asistente turístico personal de Santo Domingo de los Tsáchilas. 🌿\n\n"
        respuesta += "🗺️ Estoy aquí para ayudarte a descubrir los lugares más increíbles de nuestra hermosa provincia. Puedo contarte sobre:\n"
        respuesta += "   • 🏞️ Puntos turísticos imperdibles\n"
        respuesta += "   • 🏘️ Parroquias y sus características\n"
        respuesta += "   • 🎯 Actividades emocionantes\n"
        respuesta += "   • 🏪 Locales y sus servicios\n"
        respuesta += "   • 🕐 Horarios de atención\n\n"
        respuesta += "¿Sobre qué lugar o experiencia te gustaría saber? ¡Estoy emocionado de ayudarte! 😊"
    elif intencion == "agradecimiento":
        respuesta = "¡De nada! 😊 Ha sido un placer ayudarte. \n\n"
        respuesta += "🌟 Me encanta poder compartir información sobre los hermosos lugares de Santo Domingo de los Tsáchilas. \n\n"
        respuesta += "🗺️ Recuerda que estoy aquí siempre que necesites más información sobre nuestros destinos turísticos, actividades, servicios o cualquier cosa que te ayude a planificar tu aventura.\n\n"
        respuesta += "¡Que disfrutes mucho tu experiencia! 🎉"
    elif intencion == "despedida":
        respuesta = "¡Hasta luego! 👋 Ha sido genial ayudarte hoy.\n\n"
        respuesta += "🌟 Espero que tengas una experiencia increíble explorando Santo Domingo de los Tsáchilas. ¡Hay tantos lugares hermosos esperándote!\n\n"
        respuesta += "🗺️ Recuerda que siempre puedes regresar cuando necesites más información turística. \n\n"
        respuesta += "¡Que tengas un día maravilloso y disfrutes al máximo tu aventura! 🎉✨"

    elif intencion == "informacion_general_lugar":
        lugar = entidades.get("lugar_turistico")
        local = entidades.get("local_turistico")
        parroquia = entidades.get("parroquia")
        etiqueta = entidades.get("nombre_etiqueta")

        if lugar and lugar in puntos_turisticos:
            info = puntos_turisticos[lugar]
            respuesta = f"¡Excelente elección! 🌟 **{lugar}** es un hermoso punto turístico ubicado en la parroquia **{info.get('parroquia', 'desconocida')}**.\n\n"
            respuesta += f"📍 **Descripción:** {info.get('descripcion', 'No hay descripción disponible.')}\n\n"
            
            # Agregar información sobre actividades si existen
            if info.get("actividades"):
                respuesta += f"🎯 **Actividades disponibles:**\n"
                actividades_unicas = []
                nombres_vistos = set()
                
                for act in info["actividades"]:
                    nombre_act = act['nombre']
                    if nombre_act not in nombres_vistos:
                        nombres_vistos.add(nombre_act)
                        if act.get('precio') and act['precio'].strip() and act['precio'].lower() != 'no especificado':
                            actividades_unicas.append(f"   • {nombre_act} (💰 {act['precio']})")
                        else:
                            actividades_unicas.append(f"   • {nombre_act}")
                
                respuesta += "\n".join(actividades_unicas) + "\n\n"
            
            # Agregar información sobre etiquetas si existen
            if info.get("etiquetas") and len(info["etiquetas"]) > 0:
                etiquetas_filtradas = [etq for etq in info["etiquetas"] if etq.strip()]
                if etiquetas_filtradas:
                    respuesta += f"🏷️ **Características:** {', '.join(etiquetas_filtradas)}\n\n"
            
            respuesta += f"✨ ¡Es un lugar que definitivamente no te puedes perder! Te recomiendo visitarlo para disfrutar de una experiencia única en Santo Domingo de los Tsáchilas.\n\n"
            respuesta += f"¿Te gustaría saber más sobre las actividades específicas que puedes realizar aquí, o necesitas información sobre cómo llegar? 😊"
        elif local and local in locales_servicios:
            info_local = locales_servicios[local]
            respuesta = f"¡Perfecto! 🏪 Te cuento sobre **{local}**, un fantástico local turístico.\n\n"
            respuesta += f"📝 **Descripción:** {info_local.get('descripcion', 'No hay descripción disponible.')}\n\n"
            
            if info_local.get("servicios") and len(info_local["servicios"]) > 0:
                respuesta += f"🛎️ **Servicios que ofrece:**\n"
                for servicio in info_local["servicios"]:
                    if servicio.strip():  # Solo mostrar servicios no vacíos
                        respuesta += f"   • {servicio}\n"
                respuesta += "\n"
            
            if info_local.get("horarios") and len(info_local["horarios"]) > 0:
                respuesta += f"🕐 **Horarios de atención:**\n"
                for dia, horario in info_local["horarios"].items():
                    if horario.strip():  # Solo mostrar horarios no vacíos
                        respuesta += f"   • {dia}: {horario}\n"
                respuesta += "\n"
            
            if info_local.get("etiquetas") and len(info_local["etiquetas"]) > 0:
                etiquetas_filtradas = [etq for etq in info_local["etiquetas"] if etq.strip()]
                if etiquetas_filtradas:
                    respuesta += f"🏷️ **Características:** {', '.join(etiquetas_filtradas)}\n\n"
            
            respuesta += f"💡 ¡Te va a encantar este lugar! ¿Necesitas más detalles sobre algún servicio en particular? 😊"
        elif parroquia and parroquia in parroquias_info:
            info = parroquias_info[parroquia]
            puntos_relacionados = info.get("puntos_turisticos", [])
            respuesta = f"¡Qué buena elección! 🏘️ Te voy a contar sobre la hermosa parroquia **{parroquia}**.\n\n"
            respuesta += f"🌿 **Características:** {info.get('descripcion', 'No hay descripción disponible.')}\n\n"
            respuesta += f"👥 **Población:** Aproximadamente **{info.get('poblacion', 'N/A')}** habitantes\n"
            respuesta += f"🌡️ **Temperatura promedio:** **{info.get('temperatura', 'N/A')}°C** (¡clima muy agradable!)\n\n"
            
            if puntos_relacionados:
                respuesta += f"🎯 **Lugares turísticos que puedes visitar:**\n"
                for punto in puntos_relacionados:
                    respuesta += f"   • {punto}\n"
                respuesta += "\n"
            else:
                respuesta += f"🔍 **Puntos turísticos:** Actualmente no tenemos registros específicos, pero ¡seguro hay lugares hermosos por descubrir!\n\n"
            
            respuesta += f"✨ ¡Es una parroquia encantadora que definitivamente vale la pena visitar! ¿Te gustaría saber más sobre algún lugar específico de esta zona? 😊"
        elif etiqueta and etiqueta in etiquetas_info:
            respuesta = f"¡Excelente pregunta! 🏷️ Te explico qué significa la etiqueta **'{etiqueta}'**:\n\n"
            respuesta += f"📖 **Definición:** {etiquetas_info[etiqueta]}\n\n"
            respuesta += f"💡 Esta etiqueta nos ayuda a categorizar y entender mejor los atractivos turísticos de Santo Domingo de los Tsáchilas. "
            respuesta += f"¡Es muy útil para encontrar exactamente el tipo de experiencia que buscas!\n\n"
            respuesta += f"¿Te gustaría conocer qué lugares tienen esta característica? 😊"
        else:
            respuesta = "🤔 Hmm, no encontré información específica sobre ese lugar. ¡Pero no te preocupes! \n\n"
            respuesta += "💡 **Aquí tienes algunas opciones:**\n"
            respuesta += "   • Podrías intentar con un nombre más específico\n"
            respuesta += "   • Verificar la ortografía del lugar\n"
            respuesta += "   • Preguntarme sobre parroquias, actividades o servicios\n\n"
            respuesta += "🗺️ Estoy aquí para ayudarte a descubrir los maravillosos puntos turísticos, parroquias, locales, actividades, servicios, etiquetas y horarios de Santo Domingo de los Tsáchilas.\n\n"
            respuesta += "¿Qué te gustaría explorar? 😊"

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
            respuesta = f"¡Fantástico! 🎯 En **{lugar}** tienes muchas opciones emocionantes para disfrutar:\n\n"
            respuesta += f"🎪 **Actividades disponibles:**\n"
            
            actividades_unicas = []
            nombres_vistos = set()
            
            for act in actividades:
                nombre_act = act['nombre']
                if nombre_act not in nombres_vistos:
                    nombres_vistos.add(nombre_act)
                    if act.get('precio') and act['precio'].strip() and act['precio'].lower() != 'no especificado':
                        actividades_unicas.append(f"   • {nombre_act} (💰 {act['precio']})")
                    else:
                        actividades_unicas.append(f"   • {nombre_act}")
            
            respuesta += "\n".join(actividades_unicas) + "\n\n"
            respuesta += f"✨ ¡Cada una de estas actividades te brindará una experiencia única! Te recomiendo planificar tu visita con tiempo para que puedas disfrutar al máximo.\n\n"
            respuesta += f"¿Te interesa alguna actividad en particular? ¡Puedo darte más detalles! 😊"
        else:
            respuesta = f"🤔 Hmm, no tengo actividades específicas registradas para **{lugar if lugar else 'ese lugar'}** en este momento.\n\n"
            respuesta += f"💡 **Pero no te preocupes!** Esto puede significar que:\n"
            respuesta += f"   • Es un lugar perfecto para relajarse y disfrutar la naturaleza\n"
            respuesta += f"   • Hay actividades locales que se organizan espontáneamente\n"
            respuesta += f"   • Podrías preguntar sobre otro destino similar\n\n"
            respuesta += f"🗺️ ¿Te gustaría que te recomiende otros lugares con actividades específicas? 😊"

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

# --- La API endpoint de Flask ---
@app.route('/chatbot', methods=['POST'])
def chatbot_api():
    # Obtiene el mensaje del usuario del cuerpo JSON de la solicitud
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"error": "No se proporcionó ningún mensaje en la solicitud."}), 400

    # Procesa el mensaje usando tus funciones de chatbot
    intencion = reconocer_intencion(user_message)
    entidades = extraer_entidades(user_message)
    response_text = generar_respuesta(intencion, entidades)

    # Devuelve la respuesta en formato JSON
    return jsonify({"response": response_text})

# --- Punto de entrada para ejecutar la aplicación Flask ---
if __name__ == '__main__':
    # El puerto 5000 es el predeterminado para Flask.
    # host='0.0.0.0' hace que el servidor sea accesible desde otras máquinas en la red local.
    # debug=True es útil para desarrollo, pero desactívalo en producción.
    app.run(debug=True, host='0.0.0.0', port=5000)
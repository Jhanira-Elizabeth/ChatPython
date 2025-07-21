# import json
# import re
# import logging
# import os
# from difflib import SequenceMatcher

# logger = logging.getLogger(__name__)

# class TurismoKnowledgeBase:
#     def __init__(self, filepath='turismo_data_completo_v2.jsonl'):
#         self.filepath = filepath
#         self.conocimiento = {}
#         self.lugares = []
#         self.servicios_por_lugar = {}
#         self.actividades_por_lugar = {}
#         self.categorias_por_lugar = {}
#         self.cargar_datos_jsonl()
    
#     def cargar_datos_jsonl(self):
#         archivos_posibles = [
#             self.filepath,
#             'turismo_data_completo_v2.jsonl',
#             'turismo__data.jsonl',
#             'turismo_data.jsonl'
#         ]
#         archivo_usado = None
#         for archivo in archivos_posibles:
#             if os.path.exists(archivo):
#                 archivo_usado = archivo
#                 break
#         if not archivo_usado:
#             logger.error("No se encontró ningún archivo de datos JSONL")
#             return
#         try:
#             with open(archivo_usado, 'r', encoding='utf-8') as f:
#                 for linea in f:
#                     if linea.strip():
#                         item = json.loads(linea)
#                         self.procesar_conversacion(item)
#             logger.info(f"Datos cargados desde: {archivo_usado}")
#             logger.info(f"Base de conocimiento cargada: {len(self.conocimiento)} entradas")
#             logger.info(f"Lugares identificados: {len(self.lugares)}")
#             logger.info(f"Servicios por lugar: {len(self.servicios_por_lugar)}")
#             logger.info(f"Actividades por lugar: {len(self.actividades_por_lugar)}")
#             logger.info(f"Categorías por lugar: {len(self.categorias_por_lugar)}")
#         except Exception as e:
#             logger.error(f"Error cargando {archivo_usado}: {e}")
    
#     def procesar_conversacion(self, item):
#         if 'messages' in item:
#             user_msg = ""
#             assistant_msg = ""
#             lugar_actual = ""
#             for msg in item['messages']:
#                 if msg['role'] == 'user':
#                     user_msg = msg['content'].lower()
#                 elif msg['role'] == 'assistant':
#                     assistant_msg = msg['content']
                    
#                     # Extraer el nombre del lugar
#                     match = re.search(r'\*\*(.*?)\*\*', assistant_msg)
#                     if match:
#                         lugar_actual = match.group(1).strip()
#                         if lugar_actual not in self.lugares:
#                             self.lugares.append(lugar_actual)
                        
#                         # Extraer servicios
#                         servicios = self.extraer_servicios_del_texto(assistant_msg)
#                         if servicios:
#                             self.servicios_por_lugar[lugar_actual] = servicios
                        
#                         # Extraer actividades
#                         actividades = self.extraer_actividades_del_texto(assistant_msg)
#                         if actividades:
#                             self.actividades_por_lugar[lugar_actual] = actividades
                        
#                         # Extraer categorías
#                         categorias = self.extraer_categorias_del_texto(assistant_msg)
#                         if categorias:
#                             self.categorias_por_lugar[lugar_actual] = categorias

#             if user_msg and assistant_msg:
#                 palabras_clave = self.extraer_palabras_clave(user_msg)
#                 for palabra in palabras_clave:
#                     if palabra not in self.conocimiento:
#                         self.conocimiento[palabra] = []
#                     self.conocimiento[palabra].append({
#                         'pregunta': user_msg,
#                         'respuesta': assistant_msg,
#                         'relevancia': self.calcular_relevancia(palabra, user_msg),
#                         'lugar': lugar_actual # Usar el lugar extraído o ""
#                     })
    
#     def extraer_servicios_del_texto(self, texto):
#         """Extrae servicios mencionados en el texto. Retorna una lista vacía si no encuentra."""
#         servicios = []
#         texto_lower = texto.lower()
        
#         # Patrón para capturar texto después de "Entre sus servicios se encuentran:" o "servicios:"
#         match_servicios_seccion = re.search(
#             r'(?:entre sus servicios se encuentran:|servicios:)\s*(.*?)(?:\n\n|\n\*\*|¡todas son excelentes opciones|este lugar está categorizado|el lugar se caracteriza|en la parroquia|$)', 
#             texto_lower, 
#             re.DOTALL
#         )

#         if match_servicios_seccion:
#             servicios_texto = match_servicios_seccion.group(1)
#             servicios_candidatos = re.split(r'[,\.;]\s*|\s+y\s+', servicios_texto)
#             for s in servicios_candidatos:
#                 s_clean = s.strip()
#                 if s_clean and s_clean not in ['de', 'para', 'incluyen', 'como', 'entre', 'sus', 'se', 'encuentran', 'servicios ofrecidos', 'c', 'comida']: # Añadir 'c' y 'comida' si son ruido común
#                     servicios.append(s_clean.capitalize())
        
#         # Fallback para servicios comunes no listados explícitamente
#         servicios_posibles_keywords = [
#             'hotel', 'hospedaje', 'alojamiento', 'hostal', 'cabañas',
#             'restaurante', 'comida', 'bar', 'cafetería', 'alimentación', 'comedor',
#             'piscina', 'piscinas', 'deporte', 'deportes', 'recreación',
#             'parqueadero', 'estacionamiento', 'transporte',
#             'guía', 'guías', 'tours', 'excursiones',
#             'baños', 'servicios sanitarios', 'wifi', 'internet',
#             'canchas', 'eventos personalizados', 'habitación individual', 'habitación matrimonial',
#             'habitación triple', 'habitación doble', 'habitación familiar', 'hamburguesa',
#             'parque acuático para niños', 'rio lento (artificial)', 'tobogán', 'platos a la carta',
#             'arroz marinero', 'arroz con concha', 'eventos', 'micheladas', 'parque', 'piña colada',
#             'platos al día', 'batidos', 'cafe gourmet', 'cafe bebible', 'café granulado', 'café molido',
#             'frappe', 'pastel', 'alimentos varios', 'mozzarela con dulce de guayaba', 'queso mozzarela',
#             'queso mozzarela trenza', 'yogurt', 'cascada', 'cascada libre', 'chuleta', 'emborrajado conteño',
#             'frutas tropicales', 'sauna y jacuzzi', 'tilapia frita', 'tobogán niños', 'tobogán extremo',
#             'áreas verdes', 'espacios recreativos', 'locros', 'salón de eventos',
#             'almuerzo', 'pescado frito', 'plato típico', 'rio'
#         ]
        
#         for servicio in servicios_posibles_keywords:
#             if servicio in texto_lower and servicio.capitalize() not in servicios:
#                 servicios.append(servicio.capitalize())
        
#         return list(set(servicios))
    
#     def extraer_actividades_del_texto(self, texto):
#         """Extrae actividades mencionadas en el texto. Retorna una lista vacía si no encuentra."""
#         actividades = []
#         texto_lower = texto.lower()
        
#         # Patrón para capturar texto después de "actividades como:"
#         match_actividades = re.search(
#             r"(?:actividades como:)\s*(.*?)(?:\. ¡espero que te diviertas!|\n\n|\n\*\*|¡todas son excelentes opciones|este lugar está categorizado|el lugar se caracteriza|en la parroquia|$)", 
#             texto_lower, 
#             re.DOTALL
#         )
        
#         if match_actividades:
#             actividades_texto = match_actividades.group(1)
#             actividades_candidatas = [act.strip() for act in re.split(r'[,\.;]\s*|\s+y\s+', actividades_texto) if act.strip()]
#             actividades.extend([act.capitalize() for act in actividades_candidatas if act.lower() not in ['y', 'son', 'excelentes', 'opciones', 'para', 'tu', 'visita', 'precio', 'no especificado']])

#         # Fallback para actividades comunes
#         actividades_posibles_keywords = [
#             'natación', 'caminatas', 'ciclismo', 'senderismo',
#             'miradores', 'observación', 'fotografía',
#             'deportes extremos', 'aventura', 'recreación',
#             'pesca', 'kayak', 'rafting', 'canyoning', 'rápel',
#             'sacramentos',
#             'actividades recreativas', 'iglesia', 'parqueaderos',
#             'chamanes tsáchilas', 'creencias', 'danzas',
#             'animales de la zona', 'fauna', 'flora', 'flora exótica',
#             'áreas verdes', 'juegos recreativos', 'parque',
#             'toboganes', 'café', 'ferias', 'casa del arbol', 'mini golf', 'paisajes'
#         ]
        
#         for actividad in actividades_posibles_keywords:
#             if actividad in texto_lower and actividad.capitalize() not in actividades:
#                 actividades.append(actividad.capitalize())
        
#         return list(set(actividades))

#     def extraer_categorias_del_texto(self, texto):
#         """Extrae categorías mencionadas en el texto. Retorna una lista vacía si no encuentra."""
#         categorias = []
#         texto_lower = texto.lower()

#         # Patrón para "está asociado con las etiquetas: **Categoria1, Categoria2**."
#         match_categorias = re.search(r'está asociado con las etiquetas:\s*\*\*(.*?)\*\*', texto_lower)
#         if match_categorias:
#             categorias_texto = match_categorias.group(1)
#             categorias_candidatas = [cat.strip() for cat in re.split(r',\s*', categorias_texto) if cat.strip()]
#             categorias.extend([cat.capitalize() for cat in categorias_candidatas])
        
#         # Fallback si el patrón de etiquetas no se encuentra pero se mencionan explícitamente
#         categorias_posibles_keywords = [
#             'alimentos', 'alojamientos', 'atracciones estables', 
#             'etnia tsáchila', 'parques', 'rios'
#         ]

#         for categoria in categorias_posibles_keywords:
#             if categoria in texto_lower and categoria.capitalize() not in categorias:
#                 categorias.append(categoria.capitalize())
                
#         return list(set(categorias))
    
#     def extraer_lugar_de_respuesta(self, respuesta):
#         match = re.search(r'\*\*(.*?)\*\*', respuesta)
#         return match.group(1) if match else ""
    
#     def extraer_palabras_clave(self, texto):
#         texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
#         palabras = texto_limpio.split()
#         stop_words = {'de', 'la', 'el', 'en', 'y', 'a', 'que', 'es', 'se', 'del', 'las', 'los', 'un', 'una', 'con', 'por', 'para', 'sobre', 'me', 'te', 'le', 'nos', 'les', 'mi', 'tu', 'su', 'puedes', 'puede', 'dar', 'dame', 'información', 'info', 'cuéntame', 'cuentame', 'hay', 'existe', 'tienen', 'qué', 'que', 'quiero', 'saber', 'lo', 'un', 'más', 'puntos'} # Añadido 'puntos'
#         palabras_filtradas = [p for p in palabras if len(p) > 2 and p not in stop_words]
#         palabras_filtradas.append(texto.strip())
#         return palabras_filtradas
    
#     def calcular_relevancia(self, palabra, texto_completo):
#         return texto_completo.count(palabra) / len(texto_completo.split())
    
#     def es_respuesta_util(self, respuesta):
#         if len(respuesta) < 50:
#             return False
#         palabras_inutiles = ["etiqueta", "categoría", "significa", "se refiere a", "la etiqueta"]
#         if any(palabra in respuesta.lower() for palabra in palabras_inutiles):
#             return False
#         return True
    
#     def generar_respuesta_hoteles_internet(self):
#         logger.info("🌐 Buscando hoteles actualizados en internet...")
#         # Aquí iría la lógica para buscar hoteles reales en internet si tuvieras InternetSearcher.
#         # Por ahora, se mantendrá la respuesta predefinida.
        
#         return """🏨 ¡Hola! Te ayudo con opciones de alojamiento en Santo Domingo de los Tsáchilas.

# 🌐 **Hoteles recomendados (búsqueda actualizada):**

# **1. Hotel Toachi**
#    💰 Desde $45/noche
#    📍 Centro de Santo Domingo, excelente ubicación
#    ⭐ Muy buenas calificaciones

# **2. Hotel Zaracay**
#    💰 Desde $60/noche
#    📍 Zona turística, servicios completos
#    ⭐ Recomendado por huéspedes

# 📋 **Para reservar:**
# • Booking.com - Mejores precios garantizados
# • Expedia - Ofertas especiales 
# • Contacto directo con hoteles

# 🏞️ **Lugares turísticos cercanos:**
# • Malecón del Río Toachi - Zona céntrica
# • Parque Zaracay - Área recreativa
# • Comunidades Tsáchilas - Experiencia cultural

# ¿Te interesa conocer más sobre algún lugar específico para tu visita? 😊"""
    
#     def consultar_base(self, consulta_usuario):
#         consulta_lower = consulta_usuario.lower().strip()
        
#         # Consultas de Alojamientos
#         if any(termino in consulta_lower for termino in ['hotel', 'hoteles', 'hospedaje', 'alojamiento', 'hosteria', 'hosterías']):
#             return self.generar_respuesta_hoteles_internet()
        
#         # Consultas sobre servicios
#         terminos_servicios_amplios = ['comida', 'comer', 'restaurante', 'donde comer', 'bebida', 'bar', 'transporte', 'deporte', 'comedores', 'piscinas', 'eventos', 'canchas', 'alojamiento']
#         for termino in terminos_servicios_amplios:
#             if termino in consulta_lower:
#                 lugares_con_servicio = self.buscar_por_servicios(termino)
#                 if lugares_con_servicio:
#                     return self.generar_respuesta_servicios(termino, lugares_con_servicio)

#         # Consultas sobre actividades
#         if any(termino in consulta_lower for termino in ['actividades', 'hacer', 'puedo hacer', 'qué hacer']):
#             lugar_en_consulta = self.extraer_lugar_de_consulta(consulta_lower)
#             if lugar_en_consulta:
#                 actividades = self.actividades_por_lugar.get(lugar_en_consulta)
#                 if actividades:
#                     return f"En **{lugar_en_consulta}** puedes disfrutar de actividades como: {', '.join(actividades)}. ¡Espero que te diviertas! 🎉"
#                 else:
#                     return f"Lo siento, no tengo información específica sobre las actividades en **{lugar_en_consulta}**. ¿Te gustaría saber sobre los servicios o la descripción general de este lugar? 🤔"
#             else:
#                 # Si no se especifica un lugar, ofrecer actividades generales o en lugares populares
#                 actividades_generales = []
#                 for lugar, acts in self.actividades_por_lugar.items():
#                     actividades_generales.extend(acts)
#                 actividades_generales = list(set(actividades_generales)) # Eliminar duplicados
#                 if actividades_generales:
#                     return f"En Santo Domingo de los Tsáchilas puedes disfrutar de diversas actividades como: {', '.join(actividades_generales[:5])} y muchas más. ¿Hay algún tipo de actividad en particular que te interese o un lugar específico?"
#                 else:
#                     return "No tengo información detallada sobre actividades en general en este momento. ¿Quizás te interesa un lugar específico?"

#         # Consultas sobre el significado de etiquetas/categorías
#         if any(termino in consulta_lower for termino in ['qué significa la etiqueta', 'definición de', 'qué es', 'etiqueta']):
#             categoria_buscada = ""
#             for cat_key in ['alimentos', 'alojamientos', 'atracciones estables', 'etnia tsáchila', 'parques', 'rios']:
#                 if cat_key in consulta_lower:
#                     categoria_buscada = cat_key.capitalize()
#                     break
#             if categoria_buscada:
#                 return f"La etiqueta '**{categoria_buscada}**' se refiere a: **{categoria_buscada}**. Ayuda a categorizar y entender mejor los atractivos turísticos. 🏷️"
#             else:
#                 return "No entendí a qué etiqueta te refieres. Las etiquetas disponibles son: Alimentos, Alojamientos, Atracciones Estables, Etnia Tsáchila, Parques, Ríos. ¿Cuál te interesa? 🤔"

#         # Consultas sobre etiquetas de un lugar o local
#         if any(termino in consulta_lower for termino in ['qué etiquetas tiene', 'etiquetas de']):
#             lugar_en_consulta = self.extraer_lugar_de_consulta(consulta_lower)
#             if lugar_en_consulta:
#                 etiquetas = self.categorias_por_lugar.get(lugar_en_consulta)
#                 if etiquetas:
#                     return f"**{lugar_en_consulta}** está asociado con las etiquetas: **{', '.join(etiquetas)}**. 🏷️"
#                 else:
#                     return f"Lo siento, no tengo información sobre las etiquetas de **{lugar_en_consulta}**."
#             else:
#                 return "Para decirte las etiquetas, necesito que me digas el nombre de un lugar o local. ¿De cuál te gustaría saber?"

#         # Consultas sobre puntos turísticos o locales específicos
#         for palabra_clave, respuestas in self.conocimiento.items():
#             if palabra_clave in consulta_lower or SequenceMatcher(None, consulta_lower, palabra_clave).ratio() > 0.8:
#                 for respuesta_info in respuestas:
#                     if self.es_respuesta_util(respuesta_info['respuesta']):
#                         return self.mejorar_respuesta(respuesta_info['respuesta'])
        
#         # Consultas sobre términos generales de lugares
#         terminos_generales = ['río', 'rio', 'parque', 'malecón', 'malecon', 'balneario', 'cascada', 'museo', 'centro', 'mercado', 'comuna', 'jardin', 'catedral', 'cerro', 'monumento']
#         for termino in terminos_generales:
#             if termino in consulta_lower:
#                 lugares_relacionados = self.buscar_lugares_relacionados(termino)
#                 if lugares_relacionados:
#                     return self.generar_respuesta_multiple(termino, lugares_relacionados)

#         return None

#     def extraer_lugar_de_consulta(self, consulta):
#         """Intenta extraer un nombre de lugar de la consulta del usuario."""
#         # Buscar el nombre del lugar en el formato "**Lugar**" si ya está en la base
#         for lugar in self.lugares:
#             if lugar.lower() in consulta:
#                 return lugar
        
#         # Si no se encuentra un lugar exacto, buscar similitud
#         # Esto podría ser costoso si hay muchos lugares, usar con cuidado.
#         max_ratio = 0.75 # Umbral para considerar una coincidencia
#         mejor_lugar = None
#         consulta_palabras = set(consulta.split())
#         for lugar in self.lugares:
#             lugar_palabras = set(lugar.lower().split())
#             interseccion = len(consulta_palabras.intersection(lugar_palabras))
#             union = len(consulta_palabras.union(lugar_palabras))
#             if union > 0:
#                 ratio = interseccion / union
#                 if ratio > max_ratio:
#                     max_ratio = ratio
#                     mejor_lugar = lugar
#         return mejor_lugar


#     def buscar_por_servicios(self, termino_servicio):
#         encontrados = []
#         for lugar, servicios in self.servicios_por_lugar.items():
#             if termino_servicio in [s.lower() for s in servicios]:
#                 encontrados.append(lugar)
#         return encontrados
    
#     def generar_respuesta_servicios(self, termino, lugares_con_servicio):
#         if lugares_con_servicio:
#             lugares_str = ", ".join(lugares_con_servicio)
#             return f"Claro, encontré lugares con **{termino.capitalize()}** en Santo Domingo de los Tsáchilas, como: {lugares_str}. ¿Te gustaría saber más sobre alguno de ellos? 🏨"
#         else:
#             return f"No encontré lugares específicos con **{termino.capitalize()}** en mi base de datos local. ¿Hay algo más en lo que pueda ayudarte? 🤔"
    
#     def buscar_lugares_relacionados(self, termino_busqueda):
#         relacionados = []
#         for lugar in self.lugares:
#             if termino_busqueda in lugar.lower():
#                 relacionados.append(lugar)
        
#         # También buscar en las respuestas por si el término aparece en la descripción
#         for key, value_list in self.conocimiento.items():
#             for item in value_list:
#                 if termino_busqueda in item['respuesta'].lower() and item.get('lugar') and item['lugar'] not in relacionados:
#                     relacionados.append(item['lugar'])
#         return list(set(relacionados))
    
#     def generar_respuesta_multiple(self, termino, lugares_encontrados):
#         if lugares_encontrados:
#             lugares_str = ", ".join(lugares_encontrados)
#             return f"Claro, hay varios lugares en Santo Domingo de los Tsáchilas relacionados con '{termino}', como: {lugares_str}. ¿Cuál te interesa más? 📍"
#         else:
#             return f"No pude encontrar lugares relacionados con '{termino}' en mi base de datos local. ¿Hay algo más que pueda buscar? 🤔"
    
#     def mejorar_respuesta(self, respuesta_original):
#         # Puedes añadir lógicas para mejorar la respuesta aquí si es necesario
#         return respuesta_original
    
#     def generar_respuesta_general(self):
#         if not self.lugares:
#             return "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. ¿En qué puedo ayudarte hoy?"
#         lugares_muestra = self.lugares[:6]
#         respuesta = "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. Te puedo contar sobre estos increíbles lugares:\n\n"
#         for lugar in lugares_muestra:
#             respuesta += f"🏞️ **{lugar}**\n"
#         respuesta += "\n¿Hay algún lugar específico del que te gustaría saber más? ¡Pregúntame sobre malecones, parques, cascadas, ríos, balnearios, hoteles, comida o cualquier servicio! 😊"
#         return respuesta
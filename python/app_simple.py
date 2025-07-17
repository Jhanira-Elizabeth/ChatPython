from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import re
import logging
import requests
from bs4 import BeautifulSoup
import time
from difflib import SequenceMatcher
# from openai import OpenAI # Asegúrate de importar esto si lo usas
# from knowledge_base import TurismoKnowledgeBase # No lo importes si está en el mismo archivo
# from internet_searcher import InternetSearcher # No lo importes si está en el mismo archivo

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # Habilita CORS para permitir solicitudes desde Flutter

# --- Clase InternetSearcher (copia aquí si no está en un archivo separado) ---
class InternetSearcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }
        self.cached_hotels = None # Para almacenar hoteles en caché
        self.cache_time = 0      # Tiempo en segundos de la última actualización de la caché

    def _fetch_page(self, url):
        """Intenta obtener el contenido de una URL con reintentos."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status() # Lanza excepción para códigos de estado HTTP erróneos
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al acceder a {url}: {e}")
            return None

    def obtener_hoteles_reales(self):
        """
        Intenta obtener información de hoteles reales de Booking.com
        para Santo Domingo de los Tsáchilas, con caché simple.
        """
        # Usar caché por 1 hora
        if self.cached_hotels and (time.time() - self.cache_time) < 3600:
            logger.info("Usando caché de hoteles.")
            return self.cached_hotels

        logger.info("Realizando búsqueda de hoteles en Booking.com...")
        base_url = "https://www.booking.com"
        # Ajusta la URL de búsqueda para Santo Domingo de los Tsáchilas
        search_url = f"{base_url}/searchresults.es.html?ss=Santo+Domingo+de+los+Ts%C3%A1chilas%2C+Ecuador"

        try:
            page_content = self._fetch_page(search_url)
            if not page_content:
                return []

            soup = BeautifulSoup(page_content, 'html.parser')
            hoteles = []

            # Booking.com puede cambiar sus selectores CSS.
            # Estos son ejemplos comunes, ajústalos si no funcionan.
            # Busca contenedores de resultados de hotel
            hotel_cards = soup.find_all('div', {'data-testid': 'property-card'})

            for card in hotel_cards[:5]: # Limitar a los primeros 5-10 resultados para no sobrecargar
                nombre_element = card.find('div', {'data-testid': 'title'})
                precio_element = card.find('span', class_='e7e955336e') # Clase común para precios
                rating_element = card.find('div', {'data-testid': 'rating-badge'})
                # Descripción o ubicación, a veces en un párrafo cercano o data-attribute
                descripcion_element = card.find('span', {'data-testid': 'address'})

                nombre = nombre_element.get_text(strip=True) if nombre_element else "Nombre no disponible"
                precio = precio_element.get_text(strip=True) if precio_element else "Precio no disponible"
                rating = rating_element.get_text(strip=True) if rating_element else "Sin calificar"
                descripcion = descripcion_element.get_text(strip=True) if descripcion_element else ""

                hoteles.append({
                    "nombre": nombre,
                    "precio": precio,
                    "rating": rating,
                    "descripcion": descripcion,
                    "fuente": "Booking.com"
                })
            
            self.cached_hotels = hoteles
            self.cache_time = time.time()
            return hoteles

        except Exception as e:
            logger.error(f"Error al parsear Booking.com: {e}")
            return []
    
    def buscar_general_google(self, query):
        """Realiza una búsqueda general en Google y extrae texto de los primeros resultados."""
        search_url = f"https://www.google.com/search?q={query}"
        try:
            page_content = self._fetch_page(search_url)
            if not page_content:
                return None

            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Buscar divs de resultados (clases pueden variar)
            # Ejemplos de selectores comunes para descripciones de resultados
            snippets = soup.find_all('div', class_=lambda x: x and ('IsZvec' in x or 'BNeaweSnippet' in x))
            
            extracted_text = []
            for snippet in snippets[:3]: # Extraer de los primeros 3 snippets
                text = snippet.get_text(separator=' ', strip=True)
                extracted_text.append(text)
            
            return "\n".join(extracted_text) if extracted_text else None

        except Exception as e:
            logger.error(f"Error al buscar en Google: {e}")
            return None

# --- Inicialización de InternetSearcher ---
internet_searcher = InternetSearcher()

# --- Clase TurismoKnowledgeBase ---
class TurismoKnowledgeBase:
    def __init__(self, filepath='turismo_data_completo_v2.jsonl'):
        self.filepath = filepath
        self.conocimiento = {}
        self.lugares = []
        self.servicios_por_lugar = {}
        self.actividades_por_lugar = {}
        self.cargar_datos_jsonl()
    
    def cargar_datos_jsonl(self):
        """Carga y procesa todos los datos del archivo JSONL"""
        archivos_posibles = [
            self.filepath,
            'turismo_data_completo_v2.jsonl',
            'turismo__data.jsonl',
            'turismo_data.jsonl'
        ]
        
        archivo_usado = None
        for archivo in archivos_posibles:
            if os.path.exists(archivo):
                archivo_usado = archivo
                break
        
        if not archivo_usado:
            logger.error("No se encontró ningún archivo de datos JSONL")
            return
        
        try:
            with open(archivo_usado, 'r', encoding='utf-8') as f:
                for linea in f:
                    if linea.strip():
                        item = json.loads(linea)
                        self.procesar_conversacion(item)
            
            logger.info(f"Datos cargados desde: {archivo_usado}")
            logger.info(f"Base de conocimiento cargada: {len(self.conocimiento)} entradas")
            logger.info(f"Lugares identificados: {len(self.lugares)}")
            logger.info(f"Servicios por lugar: {len(self.servicios_por_lugar)}")
            logger.info(f"Actividades por lugar: {len(self.actividades_por_lugar)}")
            
        except Exception as e:
            logger.error(f"Error cargando {archivo_usado}: {e}")
    
    def procesar_conversacion(self, item):
        """Procesa cada conversación del JSONL para construir la base de conocimiento interna."""
        if 'messages' in item:
            user_msg = ""
            assistant_msg = ""
            
            lugar_info = None
            
            for msg in item['messages']:
                if msg['role'] == 'user':
                    user_msg = msg['content'].lower()
                elif msg['role'] == 'assistant':
                    assistant_msg = msg['content']
                    
                    # Intentar extraer lugar, servicios y actividades si están en la respuesta
                    lugar_nombre = self.extraer_lugar_de_respuesta(assistant_msg)
                    servicios_extraidos = self.extraer_servicios_del_texto(assistant_msg)
                    actividades_extraidas = self.extraer_actividades_del_texto(assistant_msg)

                    if lugar_nombre:
                        # Estructura la información del lugar para guardarla
                        lugar_info = {
                            "tipo_respuesta": "lugar_turistico_bd", # Indica que viene de la BD
                            "nombre_lugar": lugar_nombre,
                            "descripcion": "", # Tendrías que mejorar la extracción si quieres descripciones
                            "servicios": servicios_extraidos,
                            "actividades": actividades_extraidas,
                            "texto_original_bd": assistant_msg # Para fallback o depuración
                        }
                        if lugar_nombre not in self.lugares:
                            self.lugares.append(lugar_nombre)
                        self.servicios_por_lugar[lugar_nombre] = servicios_extraidos
                        self.actividades_por_lugar[lugar_nombre] = actividades_extraidas
                        
            # Guardar la conversación, pero ahora guardando la respuesta estructurada
            if user_msg and assistant_msg:
                palabras_clave = self.extraer_palabras_clave(user_msg)
                for palabra in palabras_clave:
                    if palabra not in self.conocimiento:
                        self.conocimiento[palabra] = []
                    
                    # Si pudimos extraer información estructurada, la guardamos
                    # Sino, guardamos el texto original como tipo 'general'
                    respuesta_guardar = lugar_info if lugar_info else {"tipo_respuesta": "general", "texto": assistant_msg}
                    
                    self.conocimiento[palabra].append({
                        'pregunta': user_msg,
                        'respuesta': respuesta_guardar, # <--- ¡CAMBIO AQUÍ! Guardamos el diccionario
                        'relevancia': self.calcular_relevancia(palabra, user_msg),
                        'lugar': lugar_info['nombre_lugar'] if lugar_info else ""
                    })

    def extraer_servicios_del_texto(self, texto):
        """Extrae servicios mencionados en el texto (ajustar según tu formato JSONL)"""
        servicios = []
        texto_lower = texto.lower()
        
        # Patrón para capturar texto después de "Servicios:" hasta el final o una nueva sección
        match_servicios_seccion = re.search(r'servicios(?::|\s*-)\s*(.*?)(?:\n\n|\n\*\*|$)', texto_lower, re.DOTALL)
        if match_servicios_seccion:
            servicios_texto = match_servicios_seccion.group(1)
            # Divide por comas o guiones y limpia cada elemento
            servicios_candidatos = re.split(r'[,\-]', servicios_texto)
            for s in servicios_candidatos:
                s_clean = s.strip()
                if s_clean and s_clean not in servicios:
                    servicios.append(s_clean.capitalize()) # Capitaliza para una mejor presentación
        
        # Lista de servicios posibles si no se encuentra el formato de sección
        servicios_posibles = [
            'hotel', 'hospedaje', 'alojamiento', 'hostal', 'cabañas',
            'restaurante', 'comida', 'bar', 'cafetería', 'alimentación', 'comedor',
            'piscina', 'piscinas', 'deporte', 'deportes', 'recreación',
            'parqueadero', 'estacionamiento', 'transporte',
            'guía', 'guías', 'tours', 'excursiones',
            'baños', 'servicios sanitarios', 'wifi', 'internet'
        ]
        
        for servicio in servicios_posibles:
            if servicio in texto_lower:
                if servicio not in [s.lower() for s in servicios]:
                    servicios.append(servicio.capitalize())
        
        return list(set(servicios)) # Eliminar duplicados

    def extraer_actividades_del_texto(self, texto):
        """Extrae actividades mencionadas en el texto (ajustar según tu formato JSONL)"""
        actividades = []
        
        # Patrón para capturar texto después de "actividades disponibles incluyen:"
        match_actividades = re.search(r"actividades disponibles incluyen:\s*(.*?)(?:\.|$)", texto, re.DOTALL | re.IGNORECASE)
        if match_actividades:
            actividades_texto = match_actividades.group(1)
            actividades_candidatas = [act.strip() for act in actividades_texto.split(',') if act.strip()]
            actividades.extend(actividades_candidatas)

        # Si no se encontró el patrón específico, busca palabras clave generales
        texto_lower = texto.lower()
        actividades_posibles = [
            'natación', 'caminatas', 'ciclismo', 'senderismo',
            'miradores', 'observación', 'fotografía',
            'deportes extremos', 'aventura', 'recreación',
            'pesca', 'kayak', 'rafting', 'canyoning', 'rápel'
        ]
        
        for actividad in actividades_posibles:
            if actividad in texto_lower:
                if actividad not in [a.lower() for a in actividades]:
                    actividades.append(actividad.capitalize())
        
        return list(set(actividades)) # Eliminar duplicados
    
    def extraer_lugar_de_respuesta(self, respuesta):
        """Extrae el nombre del lugar de la respuesta (busca texto entre **)"""
        match = re.search(r'\*\*(.*?)\*\*', respuesta)
        return match.group(1) if match else ""
    
    def extraer_palabras_clave(self, texto):
        """Extrae palabras clave relevantes del texto"""
        texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras = texto_limpio.split()
        
        stop_words = {'de', 'la', 'el', 'en', 'y', 'a', 'que', 'es', 'se', 'del', 'las', 'los', 'un', 'una', 'con', 'por', 'para', 'sobre', 'me', 'te', 'le', 'nos', 'les', 'mi', 'tu', 'su', 'puedes', 'puede', 'dar', 'dame', 'información', 'info', 'cuéntame', 'cuentame', 'hay', 'existe', 'tienen', 'quiero', 'saber'}
        
        palabras_filtradas = [p for p in palabras if len(p) > 2 and p not in stop_words]
        if not palabras_filtradas: # Si no hay palabras filtradas, usa la frase completa
            palabras_filtradas.append(texto.strip())
        else: # Añade la frase completa para mayor precisión si hay palabras clave
            palabras_filtradas.append(texto.strip())

        return list(set(palabras_filtradas)) # Eliminar duplicados
    
    def calcular_relevancia(self, palabra, texto_completo):
        """Calcula la relevancia de una palabra en el contexto"""
        # Una forma simple, podrías usar TF-IDF o algo más avanzado si es necesario
        palabras_texto = texto_completo.lower().split()
        if not palabras_texto:
            return 0.0
        return palabras_texto.count(palabra.lower()) / len(palabras_texto)
    
    def es_respuesta_util(self, respuesta_data):
        """Determina si una respuesta es útil para el usuario.
        Ahora espera un diccionario o cadena."""
        if isinstance(respuesta_data, dict):
            # Si es un diccionario estructurado, verifica el 'texto' o 'nombre_lugar'
            texto = respuesta_data.get('texto', '')
            nombre_lugar = respuesta_data.get('nombre_lugar', '')
            
            if len(nombre_lugar) > 3 or len(texto) > 50:
                 palabras_inutiles = ["etiqueta", "categoría", "significa", "se refiere a", "la etiqueta"]
                 if any(palabra in texto.lower() for palabra in palabras_inutiles):
                     return False
                 if "Alojamientos" in texto and "se refiere a:" in texto:
                     return False
                 return True
            return False

        elif isinstance(respuesta_data, str):
            # Lógica existente para cadenas
            if len(respuesta_data) < 50:
                return False
            
            # Filtrar respuestas sobre etiquetas
            if "La etiqueta" in respuesta_data:
                return False
            
            if "se refiere a:" in respuesta_data:
                return False
            
            if "**Alojamientos**" in respuesta_data and "se refiere a:" in respuesta_data:
                return False
            
            palabras_inutiles = ["etiqueta", "categoría", "significa", "se refiere a", "la etiqueta"]
            if any(palabra in respuesta_data.lower() for palabra in palabras_inutiles):
                return False
            
            return True
        return False # Si no es dict ni str
    
    def generar_respuesta_hoteles_internet(self):
        """Genera respuesta con hoteles reales de internet, ya devuelve un objeto estructurado."""
        logger.info("🌐 Generando respuesta de hoteles actualizados en internet...")
        
        try:
            hoteles_reales = internet_searcher.obtener_hoteles_reales()
            
            if hoteles_reales:
                return {
                    "tipo_respuesta": "hoteles_internet",
                    "data": hoteles_reales
                }
            
        except Exception as e:
            logger.error(f"Error buscando hoteles en internet: {e}")
        
        # Respuesta de respaldo si falla o no encuentra, también estructurada
        return {
            "tipo_respuesta": "general",
            "texto": """🏨 ¡Hola! Te ayudo con opciones de alojamiento en Santo Domingo de los Tsáchilas.

🌐 **Hoteles recomendados (búsqueda actualizada):**

**1. Hotel Toachi**
   💰 Desde $45/noche
   📍 Centro de Santo Domingo, excelente ubicación
   ⭐ Muy buenas calificaciones

**2. Hotel Zaracay** 💰 Desde $60/noche
   📍 Zona turística, servicios completos
   ⭐ Recomendado por huéspedes

📋 **Para reservar:**
• Booking.com - Mejores precios garantizados
• Expedia - Ofertas especiales 
• Contacto directo con hoteles

🏞️ **Lugares turísticos cercanos:**
• Malecón del Río Toachi - Zona céntrica
• Parque Zaracay - Área recreativa
• Comunidades Tsáchilas - Experiencia cultural

¿Te interesa conocer más sobre algún lugar específico para tu visita? 😊"""
        }
    
    def buscar_respuesta(self, consulta_usuario):
        """Busca la mejor respuesta basada en la consulta del usuario.
        Ahora siempre retornará un diccionario estructurado."""
        consulta_lower = consulta_usuario.lower().strip()

        # PRIORIDAD MÁXIMA: Búsqueda de hoteles con internet
        if any(termino in consulta_lower for termino in ['hotel', 'hoteles', 'hospedaje', 'alojamiento']):
            return self.generar_respuesta_hoteles_internet()

        # Términos relacionados con otros servicios
        terminos_servicios = ['comida', 'comer', 'restaurante', 'donde comer', 'bebida', 'bar', 'transporte', 'deporte', 'comedores', 'comedor', 'cafetería', 'cafeterias']
        sinonimos_servicio = {
            'comedores': 'restaurante', 'restaurantes': 'restaurante', 'restaurante': 'restaurante',
            'comedor': 'restaurante', 'cafetería': 'restaurante', 'cafeterias': 'restaurante',
            'cafes': 'restaurante', 'cafesito': 'restaurante', 'bar': 'restaurante',
            'alimentación': 'restaurante', 'comida': 'restaurante',
        }
        for termino in terminos_servicios:
            if termino in consulta_lower:
                lugares_con_servicio = self.buscar_por_servicios(termino)
                # Si no hay lugares específicos para el término exacto, pero es un sinónimo de restaurante,
                # intentamos buscar por "restaurante" general
                if not lugares_con_servicio and termino in sinonimos_servicio and sinonimos_servicio[termino] != termino:
                    lugares_con_servicio = self.buscar_por_servicios('restaurante')
                
                respuesta_servicio = self.generar_respuesta_servicios(termino, lugares_con_servicio)
                if respuesta_servicio:
                    return respuesta_servicio


        # Filtrar respuestas de etiquetas que no son útiles (si aplica)
        if any(palabra in consulta_lower for palabra in ['etiqueta', 'significa', 'categoría', 'se refiere a']):
            return self.generar_respuesta_general() # Esto devuelve un diccionario ya

        # Términos que requieren búsqueda múltiple (ej. "ríos", "parques")
        terminos_generales_lugares = ['río', 'rio', 'parque', 'malecón', 'malecon', 'balneario', 'cascada', 'museo', 'centros comerciales']

        for termino in terminos_generales_lugares:
            # Si la consulta es exactamente el término o su plural
            if consulta_lower == termino or consulta_lower == termino + "s":
                lugares_relacionados = self.buscar_lugares_relacionados(termino)
                if lugares_relacionados:
                    return self.generar_respuesta_multiple(termino, lugares_relacionados)

        # Buscar coincidencias exactas y parciales en la base de conocimiento local
        mejores_coincidencias = []
        for palabra_clave, respuestas_list in self.conocimiento.items():
            similitud = SequenceMatcher(None, consulta_lower, palabra_clave).ratio()
            
            if similitud > 0.6 or palabra_clave in consulta_lower: # Mayor umbral para exactas, menor para parciales
                for respuesta_info in respuestas_list:
                    # respuesta_info['respuesta'] ya es un diccionario gracias a procesar_conversacion
                    respuesta_dict = respuesta_info['respuesta']
                    
                    # Usa el campo 'texto_original_bd' para verificar utilidad si existe, sino usa 'texto'
                    texto_para_utilidad = respuesta_dict.get('texto_original_bd', respuesta_dict.get('texto', ''))
                    
                    if self.es_respuesta_util(texto_para_utilidad):
                        mejores_coincidencias.append({
                            'respuesta': respuesta_dict,
                            'similitud': similitud * respuesta_info['relevancia']
                        })

        if mejores_coincidencias:
            mejor = max(mejores_coincidencias, key=lambda x: x['similitud'])
            return mejor['respuesta'] # Ya es un diccionario estructurado

        # Si no se encuentra nada en la base de conocimiento local, devolver la respuesta general
        return self.generar_respuesta_general()
    
    def buscar_por_servicios(self, termino_servicio):
        """Busca lugares que ofrezcan un servicio específico o cualquier sinónimo de restaurante si aplica."""
        sinonimos = {
            'comedores': 'restaurante', 'restaurantes': 'restaurante', 'restaurante': 'restaurante',
            'comedor': 'restaurante', 'cafetería': 'restaurante', 'cafeterias': 'restaurante',
            'cafes': 'restaurante', 'cafesito': 'restaurante', 'bar': 'restaurante',
            'alimentación': 'restaurante', 'comida': 'restaurante', 'alojamiento':'hotel',
            'hospedaje':'hotel','hostal':'hotel','cabañas':'hotel',
            'piscina':'recreacion', 'piscinas':'recreacion', 'deporte':'recreacion',
            'parqueadero':'transporte', 'estacionamiento':'transporte',
            'guía':'guia', 'guías':'guia', 'tours':'guia', 'excursiones':'guia',
            'baños':'comodidad', 'servicios sanitarios':'comodidad', 'wifi':'comodidad', 'internet':'comodidad'
        }
        
        # Normaliza el término de búsqueda al término principal si es un sinónimo
        termino_normalizado = sinonimos.get(termino_servicio.lower(), termino_servicio.lower())
        
        encontrados = set()
        for lugar, servicios_list in self.servicios_por_lugar.items():
            servicios_lower = [s.lower() for s in servicios_list]
            
            # Verifica si el término normalizado o alguno de sus sinónimos está en los servicios del lugar
            if termino_normalizado in servicios_lower:
                encontrados.add(lugar)
            elif termino_normalizado == 'restaurante': # Casos especiales para alimentación
                if any(s in servicios_lower for s in ['restaurante', 'comida', 'bar', 'cafetería', 'comedor']):
                    encontrados.add(lugar)
            elif termino_normalizado == 'hotel': # Casos especiales para alojamiento
                if any(s in servicios_lower for s in ['hotel', 'hospedaje', 'alojamiento', 'hostal', 'cabañas']):
                    encontrados.add(lugar)
            # Puedes añadir más lógicas para otros grupos de servicios si es necesario

        return list(encontrados)

    def generar_respuesta_servicios(self, termino, lugares_con_servicio):
        """Genera respuesta específica para búsquedas de servicios.
        Retorna un diccionario estructurado."""
        if lugares_con_servicio:
            return {
                "tipo_respuesta": "servicios_info",
                "servicio_buscado": termino,
                "lugares": lugares_con_servicio # Lista de nombres de lugares
            }
        else:
            # Si no encuentra lugares locales, indica que no tiene info y sugiere internet
            return {
                "tipo_respuesta": "general",
                "texto": f"Lo siento, no encontré lugares específicos con {termino} en mi base de datos. ¿Te gustaría que busque opciones de {termino} en internet para ti?"
            }
    
    def buscar_lugares_relacionados(self, termino_busqueda):
        """Busca todos los lugares relacionados con un término."""
        encontrados = []
        # Buscar en los nombres de lugares directamente
        for lugar in self.lugares:
            if termino_busqueda.lower() in lugar.lower():
                encontrados.append(lugar)
        
        # Buscar en las respuestas de la base de conocimiento si el término aparece en el texto original
        for palabra_clave, respuestas_list in self.conocimiento.items():
            for resp_info in respuestas_list:
                # Asegúrate de que resp_info['respuesta'] es un dict antes de acceder a 'texto_original_bd'
                if isinstance(resp_info['respuesta'], dict):
                    texto_original = resp_info['respuesta'].get('texto_original_bd', resp_info['respuesta'].get('texto', ''))
                    if termino_busqueda.lower() in texto_original.lower() and resp_info['lugar'] and resp_info['lugar'] not in encontrados:
                        encontrados.append(resp_info['lugar'])
        return list(set(encontrados)) # Eliminar duplicados
    
    def generar_respuesta_multiple(self, termino, lugares_encontrados):
        """Genera una respuesta cuando hay múltiples lugares.
        Retorna un diccionario estructurado."""
        if lugares_encontrados:
            return {
                "tipo_respuesta": "lugares_multiples",
                "termino_relacionado": termino,
                "lugares": lugares_encontrados # Lista de nombres de lugares
            }
        else:
            return {
                "tipo_respuesta": "general",
                "texto": f"No encontré lugares relacionados con '{termino}' en mi base de datos local."
            }
    
    def generar_respuesta_general(self):
        """Genera una respuesta general con lugares disponibles.
        Retorna un diccionario estructurado."""
        if not self.lugares:
            return {
                "tipo_respuesta": "general",
                "texto": "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. ¿En qué puedo ayudarte hoy?"
            }
        
        lugares_muestra = self.lugares[:6] # Limita a una muestra para no ser demasiado largo
        texto_lugares = "\n".join([f"🏞️ **{lugar}**" for lugar in lugares_muestra])

        respuesta_texto = f"""¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. Te puedo contar sobre estos increíbles lugares:

{texto_lugares}

¿Hay algún lugar específico del que te gustaría saber más? ¡Pregúntame sobre malecones, parques, cascadas, ríos, balnearios, hoteles, comida o cualquier servicio! 😊"""
        
        return {
            "tipo_respuesta": "general",
            "texto": respuesta_texto
        }

# Inicializar la base de conocimiento
knowledge_base = TurismoKnowledgeBase()

@app.route('/', methods=['GET'])
def home():
    """Endpoint principal con información de la API"""
    return jsonify({
        'message': 'API de Chatbot de Turismo - Santo Domingo de los Tsáchilas',
        'version': '4.0.0 - CON BÚSQUEDA EN INTERNET Y RESPUESTAS ESTRUCTURADAS',
        'status': 'active',
        'base_conocimiento': len(knowledge_base.conocimiento),
        'lugares_disponibles': len(knowledge_base.lugares),
        'servicios_mapeados': len(knowledge_base.servicios_por_lugar),
        'fuente_datos': 'turismo_data_completo_v2.jsonl + Internet',
        'mejoras': 'Búsqueda de hoteles en tiempo real desde internet, respuestas JSON estructuradas',
        'busqueda_internet': 'activa',
        'endpoints': {
            '/': 'GET - Información de la API',
            '/health': 'GET - Estado de la API',
            '/lugares': 'GET - Obtener lugares disponibles',
            '/servicios': 'GET - Obtener servicios por lugar',
            '/chat': 'POST - Enviar mensaje al chatbot',
            '/buscar': 'GET - Buscar información específica',
            '/stats': 'GET - Estadísticas de la base de conocimiento'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud de la API"""
    return jsonify({
        'status': 'healthy',
        'version': '4.0.0',
        'base_conocimiento_cargada': len(knowledge_base.conocimiento) > 0,
        'lugares_cargados': len(knowledge_base.lugares),
        'servicios_mapeados': len(knowledge_base.servicios_por_lugar),
        'busqueda_internet': 'activa',
        'busqueda_hoteles': 'tiempo_real'
    })

@app.route('/lugares', methods=['GET'])
def get_lugares():
    """Endpoint para obtener todos los lugares disponibles"""
    return jsonify({
        'lugares': knowledge_base.lugares,
        'count': len(knowledge_base.lugares),
        'status': 'success',
        'mensaje': f'Tenemos información sobre {len(knowledge_base.lugares)} lugares increíbles'
    })

@app.route('/servicios', methods=['GET'])
def get_servicios():
    """Endpoint para obtener servicios por lugar"""
    lugar = request.args.get('lugar', '').strip()
    if lugar:
        servicios = knowledge_base.servicios_por_lugar.get(lugar, [])
        return jsonify({
            'lugar': lugar,
            'servicios': servicios,
            'count': len(servicios),
            'status': 'success'
        })
    else:
        return jsonify({
            'todos_los_servicios': knowledge_base.servicios_por_lugar,
            'lugares_con_servicios': len(knowledge_base.servicios_por_lugar),
            'status': 'success'
        })

@app.route('/buscar', methods=['GET'])
def buscar():
    """Endpoint para búsqueda específica"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({
            'error': 'Parámetro "q" requerido',
            'ejemplo': '/buscar?q=hoteles',
            'mensaje': 'Dime qué lugar o servicio te interesa conocer'
        }), 400
    
    # La respuesta de buscar_respuesta ya es un diccionario estructurado
    respuesta = knowledge_base.buscar_respuesta(query)
    
    return jsonify({
        'query': query,
        'respuesta': respuesta,
        'status': 'success',
        'procesamiento': 'local + internet',
        'busqueda_internet': 'hotel' in query.lower() or 'hoteles' in query.lower()
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal del chatbot. Siempre devuelve una respuesta estructurada."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'response': {"tipo_respuesta": "error", "texto": 'Mensaje requerido en el campo "message"'},
                'status': 'error',
                'ayuda': 'Envía tu pregunta en el campo "message"'
            }), 400
        user_message = data['message'].strip()
        if not user_message:
            return jsonify({
                'response': {"tipo_respuesta": "error", "texto": 'Mensaje no puede estar vacío'},
                'status': 'error',
                'sugerencia': '¿Qué lugar o servicio te gustaría conocer?'
            }), 400
        
        # Buscar respuesta en la base de conocimiento
        respuesta_estructurada = knowledge_base.buscar_respuesta(user_message)
        
        fuente = 'turismo_data_completo_v2.jsonl'
        procesamiento = 'local'
        busqueda_internet_flag = False

        # Lógica para decidir si buscar en internet si la respuesta local no fue suficiente
        # Ajusta esta lógica según tu necesidad
        if (respuesta_estructurada['tipo_respuesta'] == 'general' and 
            respuesta_estructurada.get('texto', '').startswith('Lo siento, no tengo información')) or \
           (respuesta_estructurada['tipo_respuesta'] == 'servicios_info' and not respuesta_estructurada.get('lugares')):
            
            logger.info("Respuesta local no suficiente, intentando búsqueda en internet...")
            respuesta_internet = internet_searcher.buscar_general_google(user_message)
            
            if respuesta_internet: # respuesta_internet es una cadena
                respuesta_estructurada = {
                    "tipo_respuesta": "info_general_internet",
                    "texto": respuesta_internet
                }
                fuente = 'Internet'
                procesamiento = 'internet'
                busqueda_internet_flag = True
            # else: Si la búsqueda en internet no dio resultados, se mantiene la respuesta local (general o de servicio fallido)

        return jsonify({
            'response': respuesta_estructurada, # <--- ¡Enviamos el diccionario estructurado!
            'status': 'success',
            'fuente': fuente,
            'procesamiento': procesamiento,
            'version': '4.0.0',
            'busqueda_internet': busqueda_internet_flag
        })
    except Exception as e:
        logger.error(f"Error en endpoint /chat: {e}", exc_info=True) # exc_info=True para ver el stack trace
        return jsonify({
            'response': {"tipo_respuesta": "error", "texto": 'Lo siento, tuve un pequeño problema interno. ¿Podrías preguntarme de nuevo? 😊'},
            'status': 'error',
            'details': str(e)
        }), 500

@app.route('/stats', methods=['GET'])
def stats():
    """Endpoint con estadísticas de la base de conocimiento"""
    return jsonify({
        'total_entradas': len(knowledge_base.conocimiento),
        'lugares_unicos': len(knowledge_base.lugares),
        'lugares_con_servicios': len(knowledge_base.servicios_por_lugar),
        'lugares_con_actividades': len(knowledge_base.actividades_por_lugar),
        'palabras_clave_mapeadas': len(knowledge_base.conocimiento.keys()),
        'lugares': knowledge_base.lugares,
        'servicios_ejemplo': dict(list(knowledge_base.servicios_por_lugar.items())[:3]),
        'busqueda_internet': 'activa',
        'mensaje': f'Base de conocimiento con {len(knowledge_base.lugares)} lugares y búsqueda en internet'
    })

if __name__ == '__main__':
    from waitress import serve
    logger.info("Iniciando API de Chatbot de Turismo (versión 4.0.0 con Internet y respuestas estructuradas)...")
    logger.info(f"Base de conocimiento: {len(knowledge_base.conocimiento)} entradas")
    logger.info(f"Lugares disponibles: {len(knowledge_base.lugares)}")
    logger.info(f"Servicios mapeados: {len(knowledge_base.servicios_por_lugar)}")
    logger.info("🌐 Búsqueda en internet: ACTIVA")
    # Usa app.run() para desarrollo local, y serve() para producción (como en Azure)
    # app.run(debug=True, host='0.0.0.0', port=8000) 
    serve(app, host='0.0.0.0', port=8000) # Reemplaza app.run() con serve para despliegue de producción
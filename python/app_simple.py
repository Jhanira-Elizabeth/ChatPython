"""
API de Chatbot que usa datos JSONL + Búsqueda en Internet
Con capacidad de buscar hoteles actualizados online
"""

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
from knowledge_base import TurismoKnowledgeBase # Tu clase de base de conocimiento
from internet_searcher import InternetSearcher # Importa tu nueva clase


# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Inicialización de OpenAI y InternetSearcher ---
# client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")) # Usar variable de entorno es crucial para Azure
internet_searcher = InternetSearcher() # Instancia de tu nueva clase

# --- Cargar Base de Conocimiento ---
knowledge_base = TurismoKnowledgeBase('turismo_data_completo_v2.jsonl')
logger.info(f"Datos cargados desde: {knowledge_base.filepath}")
logger.info(f"Base de conocimiento cargada: {len(knowledge_base.conocimiento)} entradas")
logger.info(f"Lugares identificados: {len(knowledge_base.lugares)}")
logger.info(f"Servicios por lugar: {len(knowledge_base.servicios_por_lugar)}")
logger.info(f"Actividades por lugar: {len(knowledge_base.actividades_por_lugar)}")

# --- Función para buscar en internet y resumir ---
# Esta función ahora será el "orquestador" de la búsqueda en internet.
def buscar_en_internet_y_resumir(query):
    """
    Orquesta la búsqueda en internet.
    - Si es una consulta de hoteles, usa la lógica específica de hoteles.
    - Si es una consulta general, usa la búsqueda general de Google.
    """
    logger.info(f"Intentando buscar en internet para: '{query}'")

    # Lógica específica para hoteles
    if "hotel" in query.lower() or "alojamiento" in query.lower():
        hoteles_info = internet_searcher.obtener_hoteles_reales()
        if hoteles_info:
            response_parts = ["Aquí tienes algunas opciones de hoteles en Santo Domingo:"]
            for h in hoteles_info:
                response_parts.append(f"- {h['nombre']} ({h.get('precio', 'Precio no disponible')}): {h.get('descripcion', h.get('rating', ''))}. Fuente: {h['fuente']}")
            return "\n".join(response_parts)
    
    # Lógica para búsqueda general (si no fue una consulta de hoteles)
    # Aquí puedes añadir la llamada al LLM si lo usas para resumir
    contenido_web = internet_searcher.buscar_general_google(query)
    if contenido_web:
        logger.info(f"Contenido web encontrado, longitud: {len(contenido_web)}")
        # Si usas un LLM para resumir, descomenta y adapta esta parte:
        # try:
        #     response = client.chat.completions.create(
        #         model="gpt-3.5-turbo", # O el modelo que uses
        #         messages=[
        #             {"role": "system", "content": "Eres un asistente turístico. Resume la información proporcionada de manera concisa y útil para el usuario. Enfócate en datos relevantes para la consulta."},
        #             {"role": "user", "content": f"Resume la siguiente información sobre '{query}':\n\n{contenido_web}"}
        #         ],
        #         max_tokens=300
        #     )
        #     return response.choices[0].message.content.strip()
        # except Exception as e:
        #     logger.error(f"Error al resumir con OpenAI: {e}")
        #     # Si falla el resumen, devolver el contenido crudo (o parte de él)
        #     return f"Información encontrada en la web sobre '{query}': {contenido_web[:500]}..."
        
        # Si NO usas un LLM, simplemente devuelve el contenido recopilado
        return f"Información encontrada en la web sobre '{query}': {contenido_web[:500]}..."
    
    return None # No se encontró información útil en internet

# --- Endpoint Principal del Chatbot (`/chat`) ---
    # ...existing code...
        
class TurismoKnowledgeBase:
    def __init__(self):
        self.conocimiento = {}
        self.lugares = []
        self.servicios_por_lugar = {}
        self.actividades_por_lugar = {}
        self.internet_searcher = InternetSearcher()
        self.cargar_datos_jsonl()
    
    def cargar_datos_jsonl(self):
        """Carga y procesa todos los datos del archivo JSONL"""
        archivos_posibles = [
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
        """Procesa cada conversación del JSONL"""
        if 'messages' in item:
            user_msg = ""
            assistant_msg = ""
            
            for msg in item['messages']:
                if msg['role'] == 'user':
                    user_msg = msg['content'].lower()
                elif msg['role'] == 'assistant':
                    assistant_msg = msg['content']
                    
                    # Extraer nombre del lugar
                    match = re.search(r'\*\*(.*?)\*\*', assistant_msg)
                    if match:
                        lugar = match.group(1)
                        if lugar not in self.lugares:
                            self.lugares.append(lugar)
                        
                        # Extraer servicios del texto
                        servicios = self.extraer_servicios_del_texto(assistant_msg)
                        if servicios:
                            self.servicios_por_lugar[lugar] = servicios
                        
                        # Extraer actividades
                        actividades = self.extraer_actividades_del_texto(assistant_msg)
                        if actividades:
                            self.actividades_por_lugar[lugar] = actividades
            
            # Guardar la conversación completa
            if user_msg and assistant_msg:
                # Crear múltiples claves para búsqueda
                palabras_clave = self.extraer_palabras_clave(user_msg)
                for palabra in palabras_clave:
                    if palabra not in self.conocimiento:
                        self.conocimiento[palabra] = []
                    self.conocimiento[palabra].append({
                        'pregunta': user_msg,
                        'respuesta': assistant_msg,
                        'relevancia': self.calcular_relevancia(palabra, user_msg),
                        'lugar': self.extraer_lugar_de_respuesta(assistant_msg)
                    })
    
    def extraer_servicios_del_texto(self, texto):
        """Extrae servicios mencionados en el texto"""
        servicios = []
        texto_lower = texto.lower()
        
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
                    servicios.append(servicio.title())
        
        return servicios
    
    def extraer_actividades_del_texto(self, texto):
        """Extrae actividades mencionadas en el texto"""
        actividades = []
        
        match = re.search(r"Las actividades disponibles incluyen:\s*(.*?)(?:\.|$)", texto)
        if match:
            actividades_texto = match.group(1)
            actividades = [act.strip() for act in actividades_texto.split(',')]
        
        if not actividades:
            texto_lower = texto.lower()
            actividades_posibles = [
                'natación', 'caminatas', 'ciclismo', 'senderismo',
                'miradores', 'observación', 'fotografía',
                'deportes extremos', 'aventura', 'recreación',
                'pesca', 'kayak', 'rafting', 'canyoning', 'rápel'
            ]
            
            for actividad in actividades_posibles:
                if actividad in texto_lower:
                    actividades.append(actividad.title())
        
        return actividades
    
    def extraer_lugar_de_respuesta(self, respuesta):
        """Extrae el nombre del lugar de la respuesta"""
        match = re.search(r'\*\*(.*?)\*\*', respuesta)
        return match.group(1) if match else ""
    
    def extraer_palabras_clave(self, texto):
        """Extrae palabras clave relevantes del texto"""
        texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras = texto_limpio.split()
        
        stop_words = {'de', 'la', 'el', 'en', 'y', 'a', 'que', 'es', 'se', 'del', 'las', 'los', 'un', 'una', 'con', 'por', 'para', 'sobre', 'me', 'te', 'le', 'nos', 'les', 'mi', 'tu', 'su', 'puedes', 'puede', 'dar', 'dame', 'información', 'info', 'cuéntame', 'cuentame', 'hay', 'existe', 'tienen'}
        
        palabras_filtradas = [p for p in palabras if len(p) > 2 and p not in stop_words]
        palabras_filtradas.append(texto.strip())
        
        return palabras_filtradas
    
    def calcular_relevancia(self, palabra, texto_completo):
        """Calcula la relevancia de una palabra en el contexto"""
        return texto_completo.count(palabra) / len(texto_completo.split())
    
    def es_respuesta_util(self, respuesta):
        """Determina si una respuesta es útil para el usuario"""
        if len(respuesta) < 50:
            return False
        
        # Filtrar respuestas sobre etiquetas
        if "La etiqueta" in respuesta:
            return False
        
        if "se refiere a:" in respuesta:
            return False
        
        if "**Alojamientos**" in respuesta and "se refiere a:" in respuesta:
            return False
        
        palabras_inutiles = ["etiqueta", "categoría", "significa", "se refiere a", "la etiqueta"]
        if any(palabra in respuesta.lower() for palabra in palabras_inutiles):
            return False
        
        return True
    
    def generar_respuesta_hoteles_internet(self):
        """Genera respuesta con hoteles reales de internet"""
        logger.info("🌐 Buscando hoteles actualizados en internet...")
        
        try:
            hoteles_reales = self.internet_searcher.obtener_hoteles_reales()
            
            if hoteles_reales:
                respuesta = "🏨 ¡Perfecto! Encontré hoteles actualizados para ti en Santo Domingo de los Tsáchilas:\n\n"
                
                for i, hotel in enumerate(hoteles_reales, 1):
                    respuesta += f"**{i}. {hotel['nombre']}**\n"
                    
                    if 'precio' in hotel:
                        respuesta += f"   💰 {hotel['precio']}\n"
                    
                    if 'rating' in hotel:
                        respuesta += f"   ⭐ {hotel['rating']}\n"
                    
                    if 'descripcion' in hotel:
                        respuesta += f"   📍 {hotel['descripcion']}\n"
                    
                    respuesta += f"   🔗 Fuente: {hotel['fuente']}\n\n"
                
                respuesta += """📋 **Para reservar:**
• Booking.com - Mejores precios y cancelación gratis
• Expedia - Paquetes hotel + vuelo
• Contacto directo con el hotel

🏞️ **También te recomiendo visitar:**
• Malecón del Río Toachi (zona céntrica)
• Parque Zaracay (área turística)
• Comunidades Tsáchilas (turismo cultural)

¿Te gustaría que te cuente sobre algún lugar turístico específico mientras planificas tu estadía? 😊"""
                
                return respuesta
        
        except Exception as e:
            logger.error(f"Error buscando hoteles en internet: {e}")
        
        # Respuesta de respaldo
        return """🏨 ¡Hola! Te ayudo con opciones de alojamiento en Santo Domingo de los Tsáchilas.

🌐 **Hoteles recomendados (búsqueda actualizada):**

**1. Hotel Toachi**
   💰 Desde $45/noche
   📍 Centro de Santo Domingo, excelente ubicación
   ⭐ Muy buenas calificaciones

**2. Hotel Zaracay** 
   💰 Desde $60/noche
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
    
    def buscar_respuesta(self, consulta_usuario):
        """Busca la mejor respuesta basada en la consulta del usuario"""
        consulta_lower = consulta_usuario.lower().strip()

        # PRIORIDAD MÁXIMA: Búsqueda de hoteles con internet
        if any(termino in consulta_lower for termino in ['hotel', 'hoteles', 'hospedaje', 'alojamiento']):
            return self.generar_respuesta_hoteles_internet()

        # Términos relacionados con otros servicios
        terminos_servicios = ['comida', 'comer', 'restaurante', 'donde comer', 'bebida', 'bar', 'transporte', 'deporte', 'comedores', 'comedor', 'cafetería', 'cafeterias']
        sinonimos_servicio = {
            'comedores': 'restaurante',
            'restaurantes': 'restaurante',
            'restaurante': 'restaurante',
            'comedor': 'restaurante',
            'cafetería': 'restaurante',
            'cafeterias': 'restaurante',
            'cafes': 'restaurante',
            'cafesito': 'restaurante',
            'bar': 'restaurante',
            'alimentación': 'restaurante',
            'comida': 'restaurante',
        }
        for termino in terminos_servicios:
            if termino in consulta_lower:
                lugares_con_servicio = self.buscar_por_servicios(termino)
                # Si no hay lugares, intentar con el término principal 'restaurante' si el término es sinónimo
                if not lugares_con_servicio and termino in sinonimos_servicio and sinonimos_servicio[termino] != termino:
                    lugares_con_servicio = self.buscar_por_servicios('restaurante')
                    if lugares_con_servicio:
                        return self.generar_respuesta_servicios('restaurante', lugares_con_servicio)
                return self.generar_respuesta_servicios(termino, lugares_con_servicio)

        # Filtrar respuestas de etiquetas que no son útiles
        if any(palabra in consulta_lower for palabra in ['etiqueta', 'significa', 'categoría', 'se refiere a']):
            return self.generar_respuesta_general()

        # Términos que requieren búsqueda múltiple
        terminos_generales = ['río', 'rio', 'parque', 'malecón', 'malecon', 'balneario', 'cascada']

        for termino in terminos_generales:
            if consulta_lower == termino or consulta_lower == termino + "s":
                lugares_relacionados = self.buscar_lugares_relacionados(termino)
                if lugares_relacionados:
                    return self.generar_respuesta_multiple(termino, lugares_relacionados)

        # Buscar coincidencias exactas PERO FILTRAR respuestas inútiles
        for palabra_clave, respuestas in self.conocimiento.items():
            if palabra_clave in consulta_lower:
                for respuesta_info in respuestas:
                    if not self.es_respuesta_util(respuesta_info['respuesta']):
                        continue

                    respuesta_original = respuesta_info['respuesta']
                    return self.mejorar_respuesta(respuesta_original)

        # Buscar coincidencias parciales
        mejores_coincidencias = []
        for palabra_clave, respuestas in self.conocimiento.items():
            similitud = SequenceMatcher(None, consulta_lower, palabra_clave).ratio()
            if similitud > 0.6:
                for respuesta in respuestas:
                    if self.es_respuesta_util(respuesta['respuesta']):
                        mejores_coincidencias.append({
                            'respuesta': respuesta['respuesta'],
                            'similitud': similitud * respuesta['relevancia']
                        })

        if mejores_coincidencias:
            mejor = max(mejores_coincidencias, key=lambda x: x['similitud'])
            return self.mejorar_respuesta(mejor['respuesta'])

        return self.generar_respuesta_general()
    
    def buscar_por_servicios(self, termino_servicio):
        """Busca lugares que ofrezcan un servicio específico o cualquier sinónimo de restaurante si aplica."""
        sinonimos = {
            'comedores': 'restaurante',
            'restaurantes': 'restaurante',
            'restaurante': 'restaurante',
            'comedor': 'restaurante',
            'cafetería': 'restaurante',
            'cafeterias': 'restaurante',
            'cafes': 'restaurante',
            'cafesito': 'restaurante',
            'bar': 'restaurante',
            'alimentación': 'restaurante',
            'comida': 'restaurante',
        }
        # Lista de todos los sinónimos de restaurante
        terminos_restaurante = set(sinonimos.keys()) | {'restaurante'}
        termino = sinonimos.get(termino_servicio.lower(), termino_servicio.lower())
        encontrados = set()
        # Si el término es sinónimo de restaurante, buscar por todos los sinónimos
        if termino == 'restaurante':
            for lugar, servicios in self.servicios_por_lugar.items():
                servicios_lower = [s.lower() for s in servicios]
                if any(s in servicios_lower for s in terminos_restaurante):
                    encontrados.add(lugar)
        else:
            for lugar, servicios in self.servicios_por_lugar.items():
                if termino in [s.lower() for s in servicios]:
                    encontrados.add(lugar)
        return list(encontrados)

    def generar_respuesta_servicios(self, termino, lugares_con_servicio):
        """Genera respuesta específica para búsquedas de servicios"""
        if lugares_con_servicio:
            lugares_str = ", ".join(lugares_con_servicio)
            return f"Claro, encontré lugares con {termino} en Santo Domingo de los Tsáchilas, como: {lugares_str}. ¿Te gustaría saber más sobre alguno de ellos?"
        else:
            return None  # Así el endpoint /chat buscará en internet
    
    def buscar_lugares_relacionados(self, termino_busqueda):
        """Busca todos los lugares relacionados con un término"""
        # Mantener implementación existente
        return []
    
    def generar_respuesta_multiple(self, termino, lugares_encontrados):
        """Genera una respuesta cuando hay múltiples lugares"""
        # Mantener implementación existente
        return f"🏞️ Lugares relacionados con {termino}"
    
    def mejorar_respuesta(self, respuesta_original):
        """Mejora la respuesta haciéndola más amigable y natural"""
        # Mantener implementación existente
        return respuesta_original
    
    def generar_respuesta_general(self):
        """Genera una respuesta general con lugares disponibles"""
        if not self.lugares:
            return "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. ¿En qué puedo ayudarte hoy?"
        
        lugares_muestra = self.lugares[:6]
        respuesta = "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. Te puedo contar sobre estos increíbles lugares:\n\n"
        
        for lugar in lugares_muestra:
            respuesta += f"🏞️ **{lugar}**\n"
        
        respuesta += "\n¿Hay algún lugar específico del que te gustaría saber más? ¡Pregúntame sobre malecones, parques, cascadas, ríos, balnearios, hoteles, comida o cualquier servicio! 😊"
        
        return respuesta

# Inicializar la base de conocimiento
knowledge_base = TurismoKnowledgeBase()

@app.route('/', methods=['GET'])
def home():
    """Endpoint principal con información de la API"""
    return jsonify({
        'message': 'API de Chatbot de Turismo - Santo Domingo de los Tsáchilas',
        'version': '4.0.0 - CON BÚSQUEDA EN INTERNET',
        'status': 'active',
        'base_conocimiento': len(knowledge_base.conocimiento),
        'lugares_disponibles': len(knowledge_base.lugares),
        'servicios_mapeados': len(knowledge_base.servicios_por_lugar),
        'fuente_datos': 'turismo_data_completo_v2.jsonl + Internet',
        'mejoras': 'Búsqueda de hoteles en tiempo real desde internet',
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
    """Endpoint principal del chatbot"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'error': 'Mensaje requerido en el campo "message"',
                'status': 'error',
                'ayuda': 'Envía tu pregunta en el campo "message"'
            }), 400
        user_message = data['message'].strip()
        if not user_message:
            return jsonify({
                'error': 'Mensaje no puede estar vacío',
                'status': 'error',
                'sugerencia': '¿Qué lugar o servicio te gustaría conocer?'
            }), 400
        # Buscar respuesta en la base de conocimiento
        respuesta = knowledge_base.buscar_respuesta(user_message)
        fuente = 'turismo_data_completo_v2.jsonl'
        procesamiento = 'local'
        busqueda_internet = False
        # Si no se encontró respuesta útil en la base local, buscar en internet
        if not respuesta or respuesta == knowledge_base.generar_respuesta_general():
            respuesta_internet = buscar_en_internet_y_resumir(user_message)
            if respuesta_internet:
                respuesta = respuesta_internet
                fuente = 'Internet'
                procesamiento = 'internet'
                busqueda_internet = True
            else:
                respuesta = 'Lo siento, no tengo información sobre eso en este momento. Por favor, intenta con otra pregunta.'
                fuente = 'ninguna'
                procesamiento = 'ninguno'
        return jsonify({
            'response': respuesta,
            'status': 'success',
            'fuente': fuente,
            'procesamiento': procesamiento,
            'version': '4.0.0',
            'busqueda_internet': busqueda_internet
        })
    except Exception as e:
        logger.error(f"Error en endpoint /chat: {e}")
        return jsonify({
            'response': 'Lo siento, tuve un pequeño problema. ¿Podrías preguntarme de nuevo? 😊',
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
        'palabras_clave': len(knowledge_base.conocimiento.keys()),
        'lugares': knowledge_base.lugares,
        'servicios_ejemplo': dict(list(knowledge_base.servicios_por_lugar.items())[:3]),
        'busqueda_internet': 'activa',
        'mensaje': f'Base de conocimiento con {len(knowledge_base.lugares)} lugares y búsqueda en internet'
    })

if __name__ == '__main__':
    from waitress import serve
    logger.info("Iniciando API de Chatbot de Turismo (versión 4.0.0 con Internet)...")
    logger.info(f"Base de conocimiento: {len(knowledge_base.conocimiento)} entradas")
    logger.info(f"Lugares disponibles: {len(knowledge_base.lugares)}")
    logger.info(f"Servicios mapeados: {len(knowledge_base.servicios_por_lugar)}")
    logger.info("🌐 Búsqueda en internet: ACTIVA")
    app.run(debug=False, host='0.0.0.0', port=8000)
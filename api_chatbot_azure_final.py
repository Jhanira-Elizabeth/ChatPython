"""
API de Chatbot de Turismo para Santo Domingo de los Tsáchilas
Versión final con conexión directa a Azure PostgreSQL
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import json
from typing import List, Dict, Any
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuración de Azure OpenAI
azure_openai_api_key = os.getenv('AZURE_OPENAI_API_KEY')
azure_openai_service_name = os.getenv('AZURE_OPENAI_SERVICE_NAME')

if azure_openai_api_key and azure_openai_service_name:
    # Configurar Azure OpenAI
    openai.api_type = "azure"
    openai.api_key = azure_openai_api_key
    openai.api_base = f"https://{azure_openai_service_name}.openai.azure.com/"
    openai.api_version = "2024-02-01"
    logger.info("Configurado Azure OpenAI")
else:
    # Fallback a OpenAI directo
    openai.api_key = os.getenv('OPENAI_API_KEY')
    logger.info("Configurado OpenAI directo")

# Función para parsear DATABASE_URL
def parse_database_url(database_url: str) -> dict:
    """Parsear DATABASE_URL y devolver configuración de conexión"""
    if not database_url:
        raise ValueError("DATABASE_URL no está configurada")
    
    parsed = urlparse(database_url)
    
    # Decodificar URL encoding (ej: %40 -> @)
    from urllib.parse import unquote
    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    
    return {
        'host': parsed.hostname,
        'database': parsed.path.lstrip('/'),
        'user': username,
        'password': password,
        'port': parsed.port or 5432,
        'sslmode': 'disable' if 'sslmode=disable' in database_url else 'require'
    }

# Configuración de Azure PostgreSQL usando DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    # Fallback a configuración individual (para desarrollo local)
    DB_CONFIG = {
        'host': os.getenv('AZURE_DB_HOST') or os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('AZURE_DB_NAME') or os.getenv('DB_NAME', 'tursd'),
        'user': os.getenv('AZURE_DB_USER') or os.getenv('DB_USER', 'tursd'),
        'password': os.getenv('AZURE_DB_PASSWORD') or os.getenv('DB_PASSWORD', 'tursd'),
        'port': int(os.getenv('AZURE_DB_PORT') or os.getenv('DB_PORT', 5432)),
        'sslmode': 'prefer'
    }
else:
    DB_CONFIG = parse_database_url(DATABASE_URL)

class TourismDatabase:
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        """Conectar a la base de datos Azure PostgreSQL"""
        try:
            self.connection = psycopg2.connect(**DB_CONFIG)
            logger.info("Conexión exitosa a Azure PostgreSQL")
        except Exception as e:
            logger.error(f"Error conectando a la base de datos: {e}")
            self.connection = None
    
    def get_connection(self):
        """Obtener conexión activa, reconectar si es necesario"""
        if not self.connection or self.connection.closed:
            self.connect()
        return self.connection
    
    def search_places(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar lugares turísticos basado en consulta"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Buscar en lugares turísticos - usando nombre correcto de tabla
                search_query = """
                SELECT 
                    lt.id,
                    lt.nombre,
                    lt.descripcion,
                    lt.direccion,
                    lt.latitud,
                    lt.longitud,
                    lt.estado
                FROM locales_turisticos lt
                WHERE 
                    lt.estado = 'activo' AND
                    (LOWER(lt.nombre) ILIKE %s OR 
                     LOWER(lt.descripcion) ILIKE %s)
                ORDER BY 
                    CASE 
                        WHEN LOWER(lt.nombre) ILIKE %s THEN 1
                        WHEN LOWER(lt.descripcion) ILIKE %s THEN 2
                        ELSE 3
                    END
                LIMIT %s
                """
                
                search_term = f"%{query.lower()}%"
                exact_term = f"%{query.lower()}%"
                
                cursor.execute(search_query, (
                    search_term, search_term,
                    exact_term, exact_term, limit
                ))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error buscando lugares: {e}")
            return []
    
    def search_activities(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar actividades basado en consulta"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                search_query = """
                SELECT 
                    a.id,
                    a.nombre,
                    a.descripcion,
                    a.precio,
                    a.duracion,
                    a.dificultad,
                    a.capacidad_maxima,
                    a.equipamiento_incluido,
                    a.estado,
                    lt.nombre as lugar_nombre,
                    lt.direccion as lugar_direccion,
                    STRING_AGG(DISTINCT t.nombre, ', ') as tags
                FROM actividades a
                LEFT JOIN lugares_turisticos lt ON a.lugar_id = lt.id
                LEFT JOIN actividad_tag at ON a.id = at.actividad_id
                LEFT JOIN tags t ON at.tag_id = t.id
                WHERE 
                    a.estado = true AND
                    (LOWER(a.nombre) ILIKE %s OR 
                     LOWER(a.descripcion) ILIKE %s OR
                     LOWER(lt.nombre) ILIKE %s)
                GROUP BY a.id, lt.nombre, lt.direccion
                ORDER BY 
                    CASE 
                        WHEN LOWER(a.nombre) ILIKE %s THEN 1
                        WHEN LOWER(a.descripcion) ILIKE %s THEN 2
                        ELSE 3
                    END
                LIMIT %s
                """
                
                search_term = f"%{query.lower()}%"
                exact_term = f"%{query.lower()}%"
                
                cursor.execute(search_query, (
                    search_term, search_term, search_term,
                    exact_term, exact_term, limit
                ))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error buscando actividades: {e}")
            return []
    
    def get_all_categories(self) -> List[Dict]:
        """Obtener todas las categorías"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM categorias WHERE estado = true ORDER BY nombre")
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error obteniendo categorías: {e}")
            return []
    
    def get_popular_places(self, limit: int = 5) -> List[Dict]:
        """Obtener lugares más populares"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                SELECT 
                    lt.id,
                    lt.nombre,
                    lt.descripcion,
                    lt.precio_entrada,
                    c.nombre as categoria,
                    STRING_AGG(DISTINCT t.nombre, ', ') as tags
                FROM lugares_turisticos lt
                LEFT JOIN categorias c ON lt.categoria_id = c.id
                LEFT JOIN lugar_tag lut ON lt.id = lut.lugar_id
                LEFT JOIN tags t ON lut.tag_id = t.id
                WHERE lt.estado = true
                GROUP BY lt.id, c.nombre
                ORDER BY lt.id
                LIMIT %s
                """
                
                cursor.execute(query, (limit,))
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error obteniendo lugares populares: {e}")
            return []

# Instancia global de la base de datos
db = TourismDatabase()

class TourismChatbot:
    def __init__(self):
        self.system_message = """
Eres un asistente virtual especializado en turismo de Santo Domingo de los Tsáchilas, Ecuador. 
Tu objetivo es ayudar a los turistas proporcionando información detallada, amigable y precisa sobre:

- Lugares turísticos y atracciones
- Actividades disponibles y sus precios
- Servicios y facilidades
- Horarios de atención
- Direcciones y ubicaciones
- Recomendaciones personalizadas

Características de tus respuestas:
- Siempre responde en español
- Sé conversacional, amigable y entusiasta
- Proporciona información específica cuando esté disponible (precios, horarios, etc.)
- Si no tienes información específica, sé honesto pero mantén un tono positivo
- Incluye detalles útiles como direcciones, contactos y consejos prácticos
- Usa emojis ocasionalmente para hacer las respuestas más amigables
- Si mencionas precios, especifica si son aproximados o exactos
"""
    
    def extract_entities(self, user_message: str) -> Dict[str, List[str]]:
        """Extraer entidades relevantes del mensaje del usuario"""
        entities = {
            'places': [],
            'activities': [],
            'categories': []
        }
        
        # Palabras clave para diferentes tipos de consultas
        place_keywords = ['lugar', 'sitio', 'destino', 'parque', 'museo', 'iglesia', 'malecón', 'centro']
        activity_keywords = ['actividad', 'hacer', 'tour', 'excursión', 'deporte', 'aventura']
        category_keywords = ['naturaleza', 'cultura', 'historia', 'religioso', 'deportes', 'recreación']
        
        message_lower = user_message.lower()
        
        # Buscar palabras clave de lugares específicos
        if any(keyword in message_lower for keyword in place_keywords):
            entities['places'] = self._extract_place_names(message_lower)
        
        if any(keyword in message_lower for keyword in activity_keywords):
            entities['activities'] = self._extract_activity_terms(message_lower)
        
        if any(keyword in message_lower for keyword in category_keywords):
            entities['categories'] = [cat for cat in category_keywords if cat in message_lower]
        
        return entities
    
    def _extract_place_names(self, message: str) -> List[str]:
        """Extraer nombres de lugares del mensaje"""
        # Patrones comunes de lugares en Santo Domingo
        place_patterns = [
            r'malecón\s+luz\s+de\s+américa',
            r'malecón',
            r'parque\s+\w+',
            r'museo\s+\w+',
            r'iglesia\s+\w+',
            r'centro\s+\w+',
            r'plaza\s+\w+'
        ]
        
        places = []
        for pattern in place_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            places.extend(matches)
        
        return places
    
    def _extract_activity_terms(self, message: str) -> List[str]:
        """Extraer términos de actividades del mensaje"""
        activity_terms = [
            'caminar', 'correr', 'ciclismo', 'fotografía', 'observación',
            'pesca', 'natación', 'kayak', 'senderismo', 'turismo'
        ]
        
        return [term for term in activity_terms if term in message]
    
    def search_relevant_info(self, user_message: str) -> Dict[str, Any]:
        """Buscar información relevante en la base de datos"""
        entities = self.extract_entities(user_message)
        results = {
            'places': [],
            'activities': [],
            'categories': []
        }
        
        # Buscar lugares
        if entities['places'] or 'lugar' in user_message.lower():
            search_terms = entities['places'] if entities['places'] else [user_message]
            for term in search_terms:
                places = db.search_places(term, limit=5)
                results['places'].extend(places)
        
        # Buscar actividades
        if entities['activities'] or 'actividad' in user_message.lower() or 'hacer' in user_message.lower():
            search_terms = entities['activities'] if entities['activities'] else [user_message]
            for term in search_terms:
                activities = db.search_activities(term, limit=5)
                results['activities'].extend(activities)
        
        # Si no hay resultados específicos, hacer búsqueda general
        if not results['places'] and not results['activities']:
            results['places'] = db.search_places(user_message, limit=3)
            results['activities'] = db.search_activities(user_message, limit=3)
        
        # Obtener categorías si es relevante
        if entities['categories']:
            results['categories'] = db.get_all_categories()
        
        return results
    
    def format_place_info(self, place: Dict) -> str:
        """Formatear información de un lugar turístico"""
        info = f"**{place['nombre']}**\n"
        
        if place.get('descripcion'):
            info += f"{place['descripcion']}\n\n"
        
        if place.get('direccion'):
            info += f"📍 **Dirección:** {place['direccion']}\n"
        
        if place.get('horario_atencion'):
            info += f"🕐 **Horarios:** {place['horario_atencion']}\n"
        
        if place.get('precio_entrada'):
            if place['precio_entrada'] == 0:
                info += f"💰 **Entrada:** Gratuita\n"
            else:
                info += f"💰 **Precio de entrada:** ${place['precio_entrada']}\n"
        
        if place.get('telefono'):
            info += f"📞 **Teléfono:** {place['telefono']}\n"
        
        if place.get('email'):
            info += f"📧 **Email:** {place['email']}\n"
        
        if place.get('sitio_web'):
            info += f"🌐 **Sitio web:** {place['sitio_web']}\n"
        
        if place.get('categoria'):
            info += f"🏷️ **Categoría:** {place['categoria']}\n"
        
        if place.get('servicios'):
            info += f"🛎️ **Servicios:** {place['servicios']}\n"
        
        if place.get('tags'):
            info += f"🏷️ **Tags:** {place['tags']}\n"
        
        return info + "\n"
    
    def format_activity_info(self, activity: Dict) -> str:
        """Formatear información de una actividad"""
        info = f"**{activity['nombre']}**\n"
        
        if activity.get('descripcion'):
            info += f"{activity['descripcion']}\n\n"
        
        if activity.get('precio'):
            info += f"💰 **Precio:** ${activity['precio']}\n"
        
        if activity.get('duracion'):
            info += f"⏱️ **Duración:** {activity['duracion']}\n"
        
        if activity.get('dificultad'):
            info += f"📊 **Dificultad:** {activity['dificultad']}\n"
        
        if activity.get('capacidad_maxima'):
            info += f"👥 **Capacidad máxima:** {activity['capacidad_maxima']} personas\n"
        
        if activity.get('equipamiento_incluido'):
            info += f"🎒 **Equipamiento incluido:** {activity['equipamiento_incluido']}\n"
        
        if activity.get('lugar_nombre'):
            info += f"📍 **Lugar:** {activity['lugar_nombre']}\n"
            if activity.get('lugar_direccion'):
                info += f"📍 **Dirección:** {activity['lugar_direccion']}\n"
        
        if activity.get('tags'):
            info += f"🏷️ **Tags:** {activity['tags']}\n"
        
        return info + "\n"
    
    def generate_response(self, user_message: str) -> str:
        """Generar respuesta del chatbot usando OpenAI"""
        try:
            # Buscar información relevante
            search_results = self.search_relevant_info(user_message)
            
            # Construir contexto con los resultados
            context = "Información encontrada en la base de datos:\n\n"
            
            if search_results['places']:
                context += "**LUGARES TURÍSTICOS:**\n"
                for place in search_results['places']:
                    context += self.format_place_info(place)
            
            if search_results['activities']:
                context += "**ACTIVIDADES:**\n"
                for activity in search_results['activities']:
                    context += self.format_activity_info(activity)
            
            # Si no hay resultados específicos, obtener lugares populares
            if not search_results['places'] and not search_results['activities']:
                popular_places = db.get_popular_places(3)
                if popular_places:
                    context += "**LUGARES POPULARES EN SANTO DOMINGO:**\n"
                    for place in popular_places:
                        context += self.format_place_info(place)
            
            # Preparar mensajes para OpenAI
            messages = [
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": f"Contexto de la base de datos:\n{context}\n\nPregunta del usuario: {user_message}"}
            ]
            
            # Llamar a OpenAI (Azure OpenAI o directo)
            if openai.api_type == "azure":
                # Para Azure OpenAI, usar el deployment name
                response = openai.ChatCompletion.create(
                    engine="gpt-4o-mini-2024-07-18-ft-dfd3d11620764bbab626c70608d5c71f",  # deployment name de Azure
                    messages=messages,
                    max_tokens=1000,
                    temperature=0.7
                )
            else:
                # Para OpenAI directo
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    max_tokens=1000,
                    temperature=0.7
                )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            return "Lo siento, he tenido un problema al procesar tu consulta. ¿Podrías intentarlo de nuevo? 😊"

# Instancia global del chatbot
chatbot = TourismChatbot()

@app.route('/', methods=['GET'])
def home():
    """Endpoint de bienvenida"""
    return jsonify({
        'message': 'API de Chatbot de Turismo - Santo Domingo de los Tsáchilas',
        'version': '1.0.0',
        'status': 'active',
        'endpoints': {
            '/chat': 'POST - Enviar mensaje al chatbot',
            '/health': 'GET - Estado de la API',
            '/places': 'GET - Obtener lugares turísticos',
            '/activities': 'GET - Obtener actividades',
            '/categories': 'GET - Obtener categorías'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud de la API"""
    try:
        # Verificar conexión a la base de datos
        conn = db.get_connection()
        db_status = "connected" if conn and not conn.closed else "disconnected"
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'timestamp': str(logger.info)
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal del chatbot"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Se requiere el campo "message"'}), 400
        
        user_message = data['message'].strip()
        if not user_message:
            return jsonify({'error': 'El mensaje no puede estar vacío'}), 400
        
        # Generar respuesta
        response = chatbot.generate_response(user_message)
        
        return jsonify({
            'response': response,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error en endpoint /chat: {e}")
        return jsonify({
            'error': 'Error interno del servidor',
            'status': 'error'
        }), 500

@app.route('/places', methods=['GET'])
def get_places():
    """Endpoint para obtener lugares turísticos"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))
        
        if query:
            places = db.search_places(query, limit)
        else:
            places = db.get_popular_places(limit)
        
        return jsonify({
            'places': places,
            'count': len(places),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error en endpoint /places: {e}")
        return jsonify({
            'error': 'Error obteniendo lugares',
            'status': 'error'
        }), 500

@app.route('/activities', methods=['GET'])
def get_activities():
    """Endpoint para obtener actividades"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))
        
        activities = db.search_activities(query, limit) if query else []
        
        return jsonify({
            'activities': activities,
            'count': len(activities),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error en endpoint /activities: {e}")
        return jsonify({
            'error': 'Error obteniendo actividades',
            'status': 'error'
        }), 500

@app.route('/categories', methods=['GET'])
def get_categories():
    """Endpoint para obtener categorías"""
    try:
        categories = db.get_all_categories()
        
        return jsonify({
            'categories': categories,
            'count': len(categories),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error en endpoint /categories: {e}")
        return jsonify({
            'error': 'Error obteniendo categorías',
            'status': 'error'
        }), 500

@app.route('/debug', methods=['GET'])
def debug_database():
    """Endpoint de debug para verificar tablas en la base de datos"""
    try:
        conn = db.get_connection()
        if not conn:
            return jsonify({'error': 'No hay conexión a la base de datos'}), 500
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Obtener lista de tablas
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """)
            tables = [row['table_name'] for row in cursor.fetchall()]
            
            # Verificar si las tablas específicas existen y tienen datos
            table_info = {}
            test_tables = ['locales_turisticos', 'lugares_turisticos', 'puntos_turisticos', 'categorias']
            
            for table in test_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table};")
                    count = cursor.fetchone()['count']
                    table_info[table] = {'exists': True, 'count': count}
                except Exception as e:
                    table_info[table] = {'exists': False, 'error': str(e)}
            
            return jsonify({
                'all_tables': tables,
                'test_tables': table_info,
                'database_name': DB_CONFIG['database'],
                'status': 'success'
            })
            
    except Exception as e:
        logger.error(f"Error en endpoint /debug: {e}")
        return jsonify({
            'error': f'Error en debug: {e}',
            'status': 'error'
        }), 500

if __name__ == '__main__':
    # Verificar configuración antes de iniciar
    if not openai.api_key:
        logger.error("OPENAI_API_KEY no está configurada")
        exit(1)
    
    if not all([DB_CONFIG['host'], DB_CONFIG['database'], DB_CONFIG['user'], DB_CONFIG['password']]):
        logger.error("Configuración de base de datos Azure incompleta")
        exit(1)
    
    logger.info("Iniciando API de Chatbot de Turismo...")
    app.run(debug=True, host='0.0.0.0', port=5000)

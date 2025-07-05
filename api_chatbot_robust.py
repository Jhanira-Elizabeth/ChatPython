"""
API de Chatbot de Turismo para Santo Domingo de los Tsáchilas
Versión robusta con manejo de errores y reconexión automática
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
from urllib.parse import urlparse, unquote
import time
import threading

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuración de OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Función para parsear DATABASE_URL
def parse_database_url(database_url: str) -> dict:
    """Parsear DATABASE_URL y devolver configuración de conexión"""
    if not database_url:
        raise ValueError("DATABASE_URL no está configurada")
    
    parsed = urlparse(database_url)
    
    # Decodificar URL encoding (ej: %40 -> @)
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
        self.connection_lock = threading.Lock()
        self.connection_attempts = 0
        self.max_attempts = 5
        self.retry_delay = 5  # segundos
        
    def connect_with_retry(self):
        """Conectar a la base de datos con reintentos automáticos"""
        while self.connection_attempts < self.max_attempts:
            try:
                self.connection = psycopg2.connect(**DB_CONFIG)
                logger.info("✅ Conexión exitosa a Azure PostgreSQL")
                self.connection_attempts = 0  # Reset contador
                return True
            except Exception as e:
                self.connection_attempts += 1
                error_msg = str(e)
                
                # Mensajes específicos según el tipo de error
                if "server closed the connection unexpectedly" in error_msg:
                    logger.warning(f"🔄 Servidor en mantenimiento. Reintento {self.connection_attempts}/{self.max_attempts} en {self.retry_delay}s...")
                elif "Unknown host" in error_msg:
                    logger.error(f"❌ Host desconocido: {DB_CONFIG['host']}")
                    break
                elif "authentication failed" in error_msg:
                    logger.error(f"❌ Error de autenticación para usuario: {DB_CONFIG['user']}")
                    break
                else:
                    logger.warning(f"🔄 Error de conexión: {e}. Reintento {self.connection_attempts}/{self.max_attempts} en {self.retry_delay}s...")
                
                if self.connection_attempts < self.max_attempts:
                    time.sleep(self.retry_delay)
                    # Aumentar delay exponencialmente
                    self.retry_delay = min(self.retry_delay * 1.5, 30)
                
        logger.error(f"❌ No se pudo conectar después de {self.max_attempts} intentos")
        return False
    
    def get_connection(self):
        """Obtener conexión activa, reconectar si es necesario"""
        with self.connection_lock:
            if not self.connection or self.connection.closed:
                if not self.connect_with_retry():
                    return None
            return self.connection
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Ejecutar consulta con manejo de errores"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error ejecutando consulta: {e}")
            # Marcar conexión como cerrada para forzar reconexión
            self.connection = None
            return []
    
    def search_places(self, query: str, limit: int = 10) -> List[Dict]:
        """Buscar lugares turísticos basado en consulta"""
        search_pattern = f"%{query.lower()}%"
        
        # Consulta optimizada para la estructura real de la base de datos
        search_query = """
        SELECT 
            lt.id,
            lt.nombre,
            lt.descripcion,
            lt.direccion,
            lt.latitud,
            lt.longitud,
            lt.telefono,
            lt.email,
            lt.horario_atencion,
            lt.precio_entrada,
            lt.sitio_web,
            lt.estado,
            c.nombre as categoria
        FROM lugares_turisticos lt
        LEFT JOIN categorias c ON lt.categoria_id = c.id
        WHERE 
            lt.estado = true AND
            (LOWER(lt.nombre) ILIKE %s OR 
             LOWER(lt.descripcion) ILIKE %s OR
             LOWER(c.nombre) ILIKE %s)
        ORDER BY 
            CASE 
                WHEN LOWER(lt.nombre) ILIKE %s THEN 1
                WHEN LOWER(c.nombre) ILIKE %s THEN 2
                ELSE 3
            END,
            lt.nombre
        LIMIT %s
        """
        
        params = (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, limit)
        return self.execute_query(search_query, params)
    
    def get_place_details(self, place_id: int) -> Dict:
        """Obtener detalles completos de un lugar específico"""
        detail_query = """
        SELECT 
            lt.*,
            c.nombre as categoria,
            STRING_AGG(DISTINCT t.nombre, ', ') as tags,
            STRING_AGG(DISTINCT s.nombre, ', ') as servicios
        FROM lugares_turisticos lt
        LEFT JOIN categorias c ON lt.categoria_id = c.id
        LEFT JOIN lugar_tag lut ON lt.id = lut.lugar_id
        LEFT JOIN tags t ON lut.tag_id = t.id
        LEFT JOIN lugar_servicio lus ON lt.id = lus.lugar_id
        LEFT JOIN servicios s ON lus.servicio_id = s.id
        WHERE lt.id = %s AND lt.estado = true
        GROUP BY lt.id, c.nombre
        """
        
        results = self.execute_query(detail_query, (place_id,))
        return results[0] if results else {}

# Instancia global de la base de datos
db = TourismDatabase()

# Estado de conexión para el endpoint de salud
connection_status = {
    'connected': False,
    'last_check': None,
    'error_message': None
}

def check_database_health():
    """Verificar estado de la base de datos en segundo plano"""
    global connection_status
    
    try:
        conn = db.get_connection()
        if conn:
            # Probar con una consulta simple
            result = db.execute_query("SELECT 1 as test")
            if result:
                connection_status['connected'] = True
                connection_status['error_message'] = None
                logger.info("🟢 Base de datos saludable")
            else:
                connection_status['connected'] = False
                connection_status['error_message'] = "No se pudo ejecutar consulta de prueba"
        else:
            connection_status['connected'] = False
            connection_status['error_message'] = "No se pudo obtener conexión"
            
    except Exception as e:
        connection_status['connected'] = False
        connection_status['error_message'] = str(e)
        logger.error(f"❌ Chequeo de salud falló: {e}")
    
    connection_status['last_check'] = time.time()

# Chequeo inicial de salud
check_database_health()

def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extraer entidades del texto de consulta"""
    entities = {
        'lugares': [],
        'actividades': [],
        'categorias': []
    }
    
    # Patrones para lugares
    lugar_patterns = [
        r'\b(?:parque|iglesia|museo|cascada|río|lago|mirador|centro|plaza|mercado)\b',
        r'\b(?:santo domingo|los tsáchilas|colorados)\b'
    ]
    
    # Patrones para actividades
    actividad_patterns = [
        r'\b(?:visitar|conocer|turismo|pasear|caminar|nadar|comer|comprar)\b',
        r'\b(?:aventura|naturaleza|cultura|gastronomía|historia)\b'
    ]
    
    # Patrones para categorías
    categoria_patterns = [
        r'\b(?:religioso|natural|cultural|gastronómico|comercial|histórico)\b',
        r'\b(?:restaurante|hotel|hospedaje|alojamiento)\b'
    ]
    
    text_lower = text.lower()
    
    for pattern in lugar_patterns:
        matches = re.findall(pattern, text_lower)
        entities['lugares'].extend(matches)
    
    for pattern in actividad_patterns:
        matches = re.findall(pattern, text_lower)
        entities['actividades'].extend(matches)
    
    for pattern in categoria_patterns:
        matches = re.findall(pattern, text_lower)
        entities['categorias'].extend(matches)
    
    return entities

def create_context_from_places(places: List[Dict]) -> str:
    """Crear contexto para GPT basado en lugares encontrados"""
    if not places:
        return "No se encontraron lugares específicos en la base de datos."
    
    context_parts = []
    for place in places:
        place_info = f"""
Lugar: {place.get('nombre', 'N/A')}
Categoría: {place.get('categoria', 'N/A')}
Descripción: {place.get('descripcion', 'N/A')}
Dirección: {place.get('direccion', 'N/A')}
Teléfono: {place.get('telefono', 'N/A')}
Horario: {place.get('horario_atencion', 'N/A')}
Precio: {place.get('precio_entrada', 'Consultar')}
"""
        context_parts.append(place_info.strip())
    
    return "\n\n".join(context_parts)

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de salud del servicio"""
    # Actualizar estado de la base de datos
    check_database_health()
    
    status = {
        'status': 'healthy' if connection_status['connected'] else 'unhealthy',
        'database': {
            'connected': connection_status['connected'],
            'last_check': connection_status['last_check'],
            'error': connection_status['error_message']
        },
        'openai': {
            'configured': bool(openai.api_key)
        }
    }
    
    status_code = 200 if connection_status['connected'] else 503
    return jsonify(status), status_code

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal del chatbot"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                'error': 'Mensaje requerido',
                'success': False
            }), 400
        
        user_message = data['message']
        logger.info(f"Consulta recibida: {user_message}")
        
        # Verificar estado de la base de datos
        if not connection_status['connected']:
            # Intentar reconectar
            check_database_health()
            
            if not connection_status['connected']:
                return jsonify({
                    'error': 'Base de datos no disponible temporalmente. Por favor intenta más tarde.',
                    'success': False,
                    'details': connection_status['error_message']
                }), 503
        
        # Extraer entidades de la consulta
        entities = extract_entities(user_message)
        
        # Buscar lugares relevantes
        search_terms = []
        search_terms.extend(entities['lugares'])
        search_terms.extend(entities['actividades'])
        search_terms.extend(entities['categorias'])
        
        # Si no hay términos específicos, usar toda la consulta
        if not search_terms:
            search_terms = [user_message]
        
        all_places = []
        for term in search_terms[:3]:  # Limitar a 3 términos
            places = db.search_places(term, 5)
            all_places.extend(places)
        
        # Eliminar duplicados manteniendo el orden
        seen_ids = set()
        unique_places = []
        for place in all_places:
            if place['id'] not in seen_ids:
                unique_places.append(place)
                seen_ids.add(place['id'])
        
        # Crear contexto para GPT
        context = create_context_from_places(unique_places[:8])
        
        # Configurar prompt para GPT
        system_prompt = """Eres un asistente turístico especializado en Santo Domingo de los Tsáchilas, Ecuador. 
        Tu objetivo es ayudar a los turistas con información precisa y útil sobre lugares, actividades y servicios turísticos.
        
        Características de tus respuestas:
        - Usa información específica de la base de datos cuando esté disponible
        - Sé amigable, útil y profesional
        - Incluye detalles prácticos (horarios, precios, direcciones, teléfonos)
        - Si no tienes información específica, proporciona consejos generales sobre turismo en la región
        - Mantén las respuestas concisas pero informativas
        - Siempre sugiere contactar directamente para confirmar horarios y precios actualizados
        """
        
        user_prompt = f"""
        Consulta del usuario: {user_message}
        
        Información de lugares turísticos disponibles:
        {context}
        
        Por favor responde de manera útil y amigable, incluyendo la información específica disponible.
        """
        
        # Llamada a OpenAI
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            bot_response = response.choices[0].message.content
            
            return jsonify({
                'message': bot_response,
                'success': True,
                'places_found': len(unique_places),
                'entities': entities
            })
            
        except Exception as e:
            logger.error(f"Error con OpenAI: {e}")
            return jsonify({
                'error': 'Error procesando la consulta con IA',
                'success': False
            }), 500
            
    except Exception as e:
        logger.error(f"Error en chat endpoint: {e}")
        return jsonify({
            'error': 'Error interno del servidor',
            'success': False
        }), 500

@app.route('/places', methods=['GET'])
def get_places():
    """Endpoint para obtener lugares turísticos"""
    try:
        query = request.args.get('q', '')
        limit = min(int(request.args.get('limit', 10)), 50)
        
        if not connection_status['connected']:
            check_database_health()
            if not connection_status['connected']:
                return jsonify({
                    'error': 'Base de datos no disponible',
                    'success': False
                }), 503
        
        if query:
            places = db.search_places(query, limit)
        else:
            # Devolver lugares populares si no hay query
            places = db.execute_query("""
                SELECT id, nombre, categoria, descripcion, direccion 
                FROM lugares_turisticos lt
                LEFT JOIN categorias c ON lt.categoria_id = c.id 
                WHERE lt.estado = true 
                ORDER BY lt.nombre 
                LIMIT %s
            """, (limit,))
        
        return jsonify({
            'places': places,
            'success': True,
            'count': len(places)
        })
        
    except Exception as e:
        logger.error(f"Error en places endpoint: {e}")
        return jsonify({
            'error': 'Error obteniendo lugares',
            'success': False
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Iniciando API de Turismo en puerto {port}")
    logger.info(f"🔗 Base de datos: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

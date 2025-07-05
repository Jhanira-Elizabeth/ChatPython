"""
API de Chatbot simplificada que funciona sin base de datos
Para demostrar funcionalidad básica
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import openai
from dotenv import load_dotenv
import logging

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
    openai.api_type = "azure"
    openai.api_key = azure_openai_api_key
    openai.api_base = f"https://{azure_openai_service_name}.openai.azure.com/"
    openai.api_version = "2024-02-01"
    logger.info("Configurado Azure OpenAI")
else:
    openai.api_key = os.getenv('OPENAI_API_KEY')
    logger.info("Configurado OpenAI directo")

# Datos turísticos de ejemplo (hardcoded)
LUGARES_TURISTICOS = [
    {
        "id": 1,
        "nombre": "Parque Zaracay",
        "descripcion": "Hermoso parque natural con senderos ecológicos y diversa fauna",
        "categoria": "Naturaleza",
        "ubicacion": "Santo Domingo"
    },
    {
        "id": 2,
        "nombre": "Cascadas de La Chorrera",
        "descripcion": "Impresionantes cascadas ideales para el ecoturismo",
        "categoria": "Naturaleza",
        "ubicacion": "Valle Hermoso"
    },
    {
        "id": 3,
        "nombre": "Centro Histórico",
        "descripcion": "Zona histórica con arquitectura colonial y museos",
        "categoria": "Cultural",
        "ubicacion": "Santo Domingo centro"
    },
    {
        "id": 4,
        "nombre": "Malecón del Río Toachi",
        "descripcion": "Paseo ribereño ideal para caminatas y deportes",
        "categoria": "Recreativo",
        "ubicacion": "Santo Domingo"
    }
]

@app.route('/', methods=['GET'])
def home():
    """Endpoint principal con información de la API"""
    return jsonify({
        'message': 'API de Chatbot de Turismo - Santo Domingo de los Tsáchilas',
        'version': '2.0.0',
        'status': 'active',
        'endpoints': {
            '/': 'GET - Información de la API',
            '/health': 'GET - Estado de la API',
            '/places': 'GET - Obtener lugares turísticos',
            '/chat': 'POST - Enviar mensaje al chatbot'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud de la API"""
    return jsonify({
        'status': 'healthy',
        'version': '2.0.0',
        'openai_configured': bool(openai.api_key)
    })

@app.route('/places', methods=['GET'])
def get_places():
    """Endpoint para obtener lugares turísticos"""
    return jsonify({
        'places': LUGARES_TURISTICOS,
        'count': len(LUGARES_TURISTICOS),
        'status': 'success'
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal del chatbot"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'error': 'Mensaje requerido',
                'status': 'error'
            }), 400
        
        user_message = data['message'].strip()
        if not user_message:
            return jsonify({
                'error': 'Mensaje no puede estar vacío',
                'status': 'error'
            }), 400
        
        # Generar respuesta usando OpenAI
        response_text = generate_tourism_response(user_message)
        
        return jsonify({
            'response': response_text,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error en endpoint /chat: {e}")
        return jsonify({
            'error': 'Error interno del servidor',
            'status': 'error'
        }), 500

def generate_tourism_response(user_message: str) -> str:
    """Generar respuesta turística usando OpenAI"""
    try:
        # Crear contexto con datos turísticos
        places_context = "\n".join([
            f"- {lugar['nombre']}: {lugar['descripcion']} (Categoría: {lugar['categoria']})"
            for lugar in LUGARES_TURISTICOS
        ])
        
        system_prompt = f"""Eres un asistente turístico especializado en Santo Domingo de los Tsáchilas, Ecuador.

Lugares turísticos disponibles:
{places_context}

Responde de manera amigable, informativa y útil. Incluye emojis cuando sea apropiado.
Si te preguntan sobre lugares específicos, usa la información proporcionada.
Si te preguntan sobre algo que no está en la lista, recomienda lugares similares o generales de la región."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Llamar a OpenAI
        if openai.api_type == "azure":
            response = openai.ChatCompletion.create(
                engine="gpt-4o-mini-2024-07-18-ft-dfd3d11620764bbab626c70608d5c71f",
                messages=messages,
                max_tokens=800,
                temperature=0.7
            )
        else:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=800,
                temperature=0.7
            )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generando respuesta: {e}")
        return "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. Te puedo recomendar lugares como el Parque Zaracay, las Cascadas de La Chorrera, el Centro Histórico y el Malecón del Río Toachi. ¿Sobre qué tipo de actividad te gustaría saber más? 🌿🏞️"

if __name__ == '__main__':
    logger.info("Iniciando API de Chatbot de Turismo (versión simplificada)...")
    app.run(debug=False, host='0.0.0.0', port=8000)

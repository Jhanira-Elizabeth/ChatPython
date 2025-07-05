#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chatbot de Turismo para Santo Domingo de los Tsáchilas - Versión Azure
Configurado para despliegue en Azure App Service con Azure Database for PostgreSQL
"""

from flask import Flask, request, jsonify
import json
import re
import spacy
import os
import psycopg2
from urllib.parse import urlparse
from fuzzywuzzy import process, fuzz

# --- Global Dictionaries to store parsed data ---
puntos_turisticos = {}
parroquias_info = {}
locales_servicios = {}
etiquetas_info = {}

# --- Inicializa la aplicación Flask ---
app = Flask(__name__)

# --- Configuración de Base de Datos para Azure ---
def get_db_connection():
    """
    Configuración de conexión a Azure Database for PostgreSQL
    """
    # URL de conexión de Azure
    azure_db_url = "postgresql://tursd:elizabeth18.@tursd.postgres.database.azure.com:5432/tursd?sslmode=require"
    
    try:
        # Parsear la URL de conexión
        parsed = urlparse(azure_db_url)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            database=parsed.path[1:],  # Remover el '/' inicial
            user=parsed.username,
            password=parsed.password,
            port=parsed.port,
            sslmode='require'  # Importante para Azure
        )
        return conn
    except Exception as e:
        print(f"❌ Error conectando a Azure PostgreSQL: {e}")
        return None

# --- Generar datos desde Azure Database ---
def load_data_from_azure_db():
    """
    Carga datos directamente desde Azure Database for PostgreSQL
    """
    print("🔄 Conectando a Azure Database for PostgreSQL...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos de Azure")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Consulta para obtener información completa de puntos turísticos
        query_puntos = """
        SELECT 
            pt.id,
            pt.nombre,
            pt.descripcion,
            pt.latitud,
            pt.longitud,
            p.nombre as parroquia,
            COALESCE(STRING_AGG(DISTINCT CONCAT(a.actividad, 
                CASE WHEN a.precio IS NOT NULL THEN CONCAT(' (Precio: $', a.precio, ')') ELSE '' END,
                CASE WHEN a.tipo IS NOT NULL THEN CONCAT(' - Tipo: ', a.tipo) ELSE '' END), '; '), '') as actividades,
            COALESCE(STRING_AGG(DISTINCT et.nombre, ', '), '') as etiquetas
        FROM puntos_turisticos pt
        LEFT JOIN parroquias p ON pt.id_parroquia = p.id AND p.estado = 'activo'
        LEFT JOIN puntos_turisticos_etiqueta pte ON pt.id = pte.id_punto_turistico AND pte.estado = 'activo'
        LEFT JOIN etiquetas_turisticas et ON pte.id_etiqueta = et.id AND et.estado = 'activo'
        LEFT JOIN actividad_punto_turistico a ON pt.id = a.id_punto_turistico AND a.estado = 'activo'
        WHERE pt.estado = 'activo'
        GROUP BY pt.id, pt.nombre, pt.descripcion, pt.latitud, pt.longitud, p.nombre
        ORDER BY pt.id;
        """
        
        print("🔍 Ejecutando consulta para puntos turísticos...")
        cursor.execute(query_puntos)
        puntos_data = cursor.fetchall()
        print(f"✅ Encontrados {len(puntos_data)} puntos turísticos")
        
        # Procesar datos de puntos turísticos
        for row in puntos_data:
            punto_id, nombre, descripcion, latitud, longitud, parroquia, actividades, etiquetas = row
            
            # Procesar actividades
            actividades_list = []
            if actividades and actividades.strip():
                for act in actividades.split(';'):
                    if act.strip():
                        actividades_list.append({"nombre": act.strip()})
            
            # Procesar etiquetas
            etiquetas_list = []
            if etiquetas and etiquetas.strip():
                etiquetas_list = [etq.strip() for etq in etiquetas.split(',') if etq.strip()]
            
            # Guardar en diccionario global
            puntos_turisticos[nombre] = {
                "id": punto_id,
                "parroquia": parroquia or "N/A",
                "descripcion": descripcion or "No disponible",
                "latitud": latitud,
                "longitud": longitud,
                "actividades": actividades_list,
                "etiquetas": etiquetas_list
            }
            
            # Asociar con parroquia
            if parroquia:
                if parroquia not in parroquias_info:
                    parroquias_info[parroquia] = {"puntos_turisticos": []}
                if nombre not in parroquias_info[parroquia]["puntos_turisticos"]:
                    parroquias_info[parroquia]["puntos_turisticos"].append(nombre)
        
        # Consulta para obtener información de parroquias
        query_parroquias = """
        SELECT 
            p.nombre,
            p.descripcion,
            p.poblacion,
            p.temperatura_promedio
        FROM parroquias p
        WHERE p.estado = 'activo'
        ORDER BY p.nombre;
        """
        
        print("🔍 Ejecutando consulta para parroquias...")
        cursor.execute(query_parroquias)
        parroquias_data = cursor.fetchall()
        print(f"✅ Encontradas {len(parroquias_data)} parroquias")
        
        # Procesar datos de parroquias
        for row in parroquias_data:
            nombre, descripcion, poblacion, temperatura = row
            
            if nombre not in parroquias_info:
                parroquias_info[nombre] = {"puntos_turisticos": []}
            
            parroquias_info[nombre].update({
                "descripcion": descripcion or "No disponible",
                "poblacion": poblacion or "N/A",
                "temperatura": temperatura or "N/A"
            })
        
        conn.close()
        print("✅ Datos cargados exitosamente desde Azure Database")
        return True
        
    except Exception as e:
        print(f"❌ Error cargando datos desde Azure: {e}")
        conn.close()
        return False

# --- Carga el modelo spaCy y los datos turísticos SOLO UNA VEZ al iniciar la app ---
try:
    nlp = spacy.load("es_core_news_sm")
    print("✅ Modelo spaCy cargado correctamente")
except OSError:
    print("⚠️ Modelo spaCy no encontrado. Intentando descargarlo...")
    try:
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "es_core_news_sm"], check=True)
        nlp = spacy.load("es_core_news_sm")
        print("✅ Modelo spaCy descargado y cargado correctamente")
    except Exception as e:
        print(f"❌ Error descargando modelo spaCy: {e}")
        # Crear un objeto mock para evitar errores
        class MockNLP:
            def __call__(self, text):
                class MockDoc:
                    ents = []
                return MockDoc()
        nlp = MockNLP()

# --- Cargar datos al iniciar la aplicación ---
print("🚀 Iniciando Chatbot de Turismo para Azure")
print("=" * 60)

# Intentar cargar desde base de datos de Azure
if not load_data_from_azure_db():
    print("⚠️ Fallback: intentando cargar desde archivo local...")
    # Fallback al archivo local si la DB no está disponible
    try:
        file_path = 'turismo_data_completo_v2.jsonl'
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"✅ Archivo local encontrado con {len(lines)} líneas")
        # Aquí puedes agregar la lógica de procesamiento del archivo local si es necesario
    except FileNotFoundError:
        print("❌ No se pudo cargar datos ni de Azure DB ni de archivo local")

# Mostrar estadísticas
print(f"\n=== ESTADÍSTICAS DE DATOS CARGADOS ===")
print(f"📍 Puntos turísticos: {len(puntos_turisticos)}")
print(f"🏘️ Parroquias: {len(parroquias_info)}")
print(f"🏪 Locales/servicios: {len(locales_servicios)}")
print(f"🏷️ Etiquetas: {len(etiquetas_info)}")
print("=" * 60)

# --- Funciones de Procesamiento del Lenguaje Natural (NLU) ---
def reconocer_intencion(texto):
    """Reconoce la intención del usuario"""
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
    """Extrae entidades nombradas del texto"""
    entidades = {}
    texto_lower = texto.lower()

    all_known_names = (
        list(puntos_turisticos.keys()) +
        list(locales_servicios.keys()) +
        list(parroquias_info.keys()) +
        list(etiquetas_info.keys())
    )

    # Buscar coincidencias exactas
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

    # Buscar coincidencias parciales usando fuzzy matching
    if all_known_names:  # Solo si hay datos cargados
        potential_matches = process.extract(texto, all_known_names, limit=5, scorer=fuzz.partial_ratio)

        relevant_matches = []
        score_cutoff = 70
        for matched_name, score in potential_matches:
            if score >= score_cutoff:
                relevant_matches.append((matched_name, score))

        if relevant_matches:
            relevant_matches.sort(key=lambda x: x[1], reverse=True)
            best_match_name, best_score = relevant_matches[0]

            if len(relevant_matches) > 1:
                filtered_matches = []
                for name, score in relevant_matches:
                    if score >= (best_score - 10):
                        is_substring = False
                        for other_name, other_score in relevant_matches:
                            if (name != other_name and 
                                abs(score - other_score) <= 10 and
                                (name.lower() in other_name.lower() or other_name.lower() in name.lower())):
                                if len(other_name) > len(name):
                                    is_substring = True
                                    break
                        
                        if not is_substring:
                            filtered_matches.append((name, score))
                
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

    return entidades

def generar_respuesta(intencion, entidades):
    """Genera respuesta basada en la intención y entidades"""
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
        if len(entidades["ambiguous_entity"]) > 1:
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

    elif intencion == "informacion_general_lugar":
        lugar = entidades.get("lugar_turistico")
        parroquia = entidades.get("parroquia")

        if lugar and lugar in puntos_turisticos:
            info = puntos_turisticos[lugar]
            respuesta = f"¡Excelente elección! 🌟 **{lugar}** es un hermoso punto turístico ubicado en la parroquia **{info.get('parroquia', 'desconocida')}**.\n\n"
            respuesta += f"📍 **Descripción:** {info.get('descripcion', 'No hay descripción disponible.')}\n\n"
            
            if info.get("actividades"):
                respuesta += f"🎯 **Actividades disponibles:**\n"
                for act in info["actividades"]:
                    respuesta += f"   • {act['nombre']}\n"
                respuesta += "\n"
            
            if info.get("etiquetas") and len(info["etiquetas"]) > 0:
                respuesta += f"🏷️ **Características:** {', '.join(info['etiquetas'])}\n\n"
            
            respuesta += f"✨ ¡Es un lugar que definitivamente no te puedes perder! Te recomiendo visitarlo para disfrutar de una experiencia única en Santo Domingo de los Tsáchilas.\n\n"
            respuesta += f"¿Te gustaría saber más sobre las actividades específicas que puedes realizar aquí? 😊"

        elif parroquia and parroquia in parroquias_info:
            info = parroquias_info[parroquia]
            puntos_relacionados = info.get("puntos_turisticos", [])
            respuesta = f"¡Qué buena elección! 🏘️ Te voy a contar sobre la hermosa parroquia **{parroquia}**.\n\n"
            respuesta += f"🌿 **Características:** {info.get('descripcion', 'No hay descripción disponible.')}\n\n"
            respuesta += f"👥 **Población:** Aproximadamente **{info.get('poblacion', 'N/A')}** habitantes\n"
            respuesta += f"🌡️ **Temperatura promedio:** **{info.get('temperatura', 'N/A')}** (¡clima muy agradable!)\n\n"
            
            if puntos_relacionados:
                respuesta += f"🎯 **Lugares turísticos que puedes visitar:**\n"
                for punto in puntos_relacionados:
                    respuesta += f"   • {punto}\n"
                respuesta += "\n"
            
            respuesta += f"✨ ¡Es una parroquia encantadora que definitivamente vale la pena visitar! ¿Te gustaría saber más sobre algún lugar específico de esta zona? 😊"

    elif intencion == "buscar_actividades":
        lugar = entidades.get("lugar_turistico")
        if lugar and lugar in puntos_turisticos and puntos_turisticos[lugar].get("actividades"):
            actividades = puntos_turisticos[lugar]["actividades"]
            respuesta = f"¡Fantástico! 🎯 En **{lugar}** tienes muchas opciones emocionantes para disfrutar:\n\n"
            respuesta += f"🎪 **Actividades disponibles:**\n"
            
            for act in actividades:
                respuesta += f"   • {act['nombre']}\n"
            
            respuesta += f"\n✨ ¡Cada una de estas actividades te brindará una experiencia única! Te recomiendo planificar tu visita con tiempo para que puedas disfrutar al máximo.\n\n"
            respuesta += f"¿Te interesa alguna actividad en particular? ¡Puedo darte más detalles! 😊"

    return respuesta

# --- Endpoints de la API ---
@app.route('/', methods=['GET'])
def home():
    """Endpoint de bienvenida"""
    return jsonify({
        "message": "🌟 Chatbot de Turismo - Santo Domingo de los Tsáchilas",
        "version": "2.0 - Azure Edition",
        "status": "active",
        "endpoints": {
            "chat": "/chatbot (POST)",
            "health": "/health (GET)"
        },
        "stats": {
            "puntos_turisticos": len(puntos_turisticos),
            "parroquias": len(parroquias_info),
            "locales": len(locales_servicios)
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check"""
    return jsonify({
        "status": "healthy",
        "database": "azure_postgresql",
        "data_loaded": {
            "puntos_turisticos": len(puntos_turisticos),
            "parroquias": len(parroquias_info),
            "locales": len(locales_servicios)
        },
        "version": "2.0"
    })

@app.route('/chatbot', methods=['POST'])
def chatbot_api():
    """Endpoint principal del chatbot"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Mensaje vacío'}), 400

        print(f"🔍 Pregunta recibida: {user_message}")

        # Procesar mensaje
        intencion = reconocer_intencion(user_message)
        entidades = extraer_entidades(user_message)
        response_text = generar_respuesta(intencion, entidades)

        print(f"✅ Respuesta generada: {response_text[:100]}...")

        return jsonify({
            "response": response_text,
            "status": "success",
            "intent": intencion,
            "entities": entidades
        })

    except Exception as e:
        print(f"❌ Error en /chatbot: {e}")
        return jsonify({
            'error': 'Error interno del servidor',
            'message': 'Lo siento, hubo un problema procesando tu mensaje. Por favor intenta de nuevo.'
        }), 500

# --- Punto de entrada ---
if __name__ == '__main__':
    # Configuración para Azure App Service
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"🚀 Iniciando servidor en puerto {port}")
    print(f"🔧 Modo debug: {debug_mode}")
    
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )

import json
import psycopg2
from collections import defaultdict

def check_dependencies():
    """
    Verifica si psycopg2 está instalado
    """
    try:
        import psycopg2
        return True
    except ImportError:
        print("❌ psycopg2 no está instalado")
        print("💡 Instálalo con: pip install psycopg2-binary")
        return False

def connect_to_database():
    """
    Conecta a la base de datos PostgreSQL en Docker
    """
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="tursd",
            user="tursd",
            password="tursd"
        )
        print("✅ Conexión exitosa a PostgreSQL")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return None

def generate_comprehensive_tourism_data(cursor):
    """
    Genera datos completos basados en la estructura real de la base de datos
    """
    # Consulta basada en el backup SQL que proporcionaste
    query = """
    SELECT DISTINCT
        pt.nombre AS nombre_punto_turistico,
        pt.descripcion AS descripcion_punto_turistico,
        p.nombre AS nombre_parroquia,
        p.descripcion AS descripcion_parroquia,
        p.poblacion,
        p.temperatura_promedio,
        STRING_AGG(DISTINCT et.nombre, ', ') AS etiquetas,
        STRING_AGG(DISTINCT apt.actividad, ', ') AS actividades,
        STRING_AGG(DISTINCT 
            CASE 
                WHEN apt.precio IS NOT NULL AND apt.precio > 0 THEN CONCAT(apt.actividad, ' ($', apt.precio, ')')
                ELSE apt.actividad 
            END, ', ') AS actividades_con_precios
    FROM puntos_turisticos pt
    LEFT JOIN parroquias p ON pt.id_parroquia = p.id AND p.estado = true
    LEFT JOIN puntos_turisticos_etiqueta pte ON pt.id = pte.id_punto_turistico AND pte.estado = 'activo'
    LEFT JOIN etiquetas_turisticas et ON pte.id_etiqueta = et.id AND et.estado = true
    LEFT JOIN actividad_punto_turistico apt ON pt.id = apt.id_punto_turistico AND apt.estado = true
    WHERE pt.estado = true
    GROUP BY pt.id, pt.nombre, pt.descripcion, p.nombre, p.descripcion, p.poblacion, p.temperatura_promedio
    ORDER BY pt.nombre
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    data_entries = []
    
    for row in results:
        (nombre_punto, descripcion_punto, nombre_parroquia, descripcion_parroquia, 
         poblacion, temperatura, etiquetas, actividades, actividades_con_precios) = row
        
        # Información básica del punto turístico
        basic_info = f"**{nombre_punto}** es un punto turístico ubicado en la parroquia {nombre_parroquia}. {descripcion_punto}"
        
        # Información de la parroquia
        parroquia_info = ""
        if descripcion_parroquia:
            parroquia_info = f" La parroquia {nombre_parroquia} {descripcion_parroquia}"
            if poblacion:
                parroquia_info += f" con una población de {poblacion} habitantes"
            if temperatura:
                parroquia_info += f" y una temperatura promedio de {temperatura}°C"
        
        # Etiquetas
        etiquetas_info = ""
        if etiquetas:
            etiquetas_info = f" Este lugar está categorizado como: {etiquetas}."
        
        # Actividades
        actividades_info = ""
        if actividades_con_precios:
            actividades_info = f" Las actividades disponibles incluyen: {actividades_con_precios}."
        
        # Crear múltiples entradas con diferentes tipos de preguntas
        
        # 1. Información general
        entry_general = {
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente experto en turismo de Santo Domingo de los Tsáchilas. Proporcionas información detallada, amigable y precisa sobre destinos turísticos."
                },
                {
                    "role": "user",
                    "content": f"Cuéntame sobre {nombre_punto}"
                },
                {
                    "role": "assistant",
                    "content": f"{basic_info}{parroquia_info}.{etiquetas_info}{actividades_info}"
                }
            ]
        }
        data_entries.append(entry_general)
        
        # 2. Pregunta sobre actividades (solo si hay actividades)
        if actividades_con_precios:
            entry_actividades = {
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un asistente experto en turismo de Santo Domingo de los Tsáchilas. Proporcionas información detallada sobre actividades turísticas."
                    },
                    {
                        "role": "user",
                        "content": f"¿Qué actividades puedo hacer en {nombre_punto}?"
                    },
                    {
                        "role": "assistant",
                        "content": f"En **{nombre_punto}** puedes disfrutar de las siguientes actividades: {actividades_con_precios}. ¡Todas son excelentes opciones para tu visita!"
                    }
                ]
            }
            data_entries.append(entry_actividades)
        
        # 3. Pregunta sobre ubicación/parroquia
        if nombre_parroquia:
            entry_ubicacion = {
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un asistente experto en turismo de Santo Domingo de los Tsáchilas. Proporcionas información sobre ubicación y características de las parroquias."
                    },
                    {
                        "role": "user",
                        "content": f"¿Dónde se encuentra {nombre_punto}?"
                    },
                    {
                        "role": "assistant",
                        "content": f"**{nombre_punto}** se encuentra en la parroquia **{nombre_parroquia}**{parroquia_info}. Es un excelente destino para visitar en esta zona."
                    }
                ]
            }
            data_entries.append(entry_ubicacion)
    
    return data_entries

def generate_parroquias_data(cursor):
    """
    Genera datos específicos sobre parroquias
    """
    query = """
    SELECT 
        p.nombre AS nombre_parroquia,
        p.descripcion AS descripcion_parroquia,
        p.poblacion,
        p.temperatura_promedio,
        COUNT(DISTINCT pt.id) AS total_puntos_turisticos
    FROM parroquias p
    LEFT JOIN puntos_turisticos pt ON p.id = pt.id_parroquia AND pt.estado = true
    WHERE p.estado = true
    GROUP BY p.id, p.nombre, p.descripcion, p.poblacion, p.temperatura_promedio
    ORDER BY p.nombre
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    data_entries = []
    
    for row in results:
        nombre_parroquia, descripcion, poblacion, temperatura, total_puntos = row
        
        info_parroquia = f"**{nombre_parroquia}** es una parroquia de Santo Domingo de los Tsáchilas"
        
        if descripcion:
            info_parroquia += f" que se caracteriza por: {descripcion}"
        
        if poblacion:
            info_parroquia += f" Tiene una población aproximada de {poblacion} habitantes"
        
        if temperatura:
            info_parroquia += f" y una temperatura promedio de {temperatura}°C"
        
        if total_puntos > 0:
            info_parroquia += f". En esta parroquia encontrarás {total_puntos} puntos turísticos para visitar"
        
        info_parroquia += "."
        
        entry = {
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente experto en turismo de Santo Domingo de los Tsáchilas. Proporcionas información detallada sobre las parroquias y sus características."
                },
                {
                    "role": "user",
                    "content": f"Cuéntame sobre la parroquia {nombre_parroquia}"
                },
                {
                    "role": "assistant",
                    "content": info_parroquia
                }
            ]
        }
        data_entries.append(entry)
    
    return data_entries

def generate_etiquetas_data(cursor):
    """
    Genera datos sobre etiquetas turísticas
    """
    query = """
    SELECT 
        et.nombre AS nombre_etiqueta,
        et.descripcion AS descripcion_etiqueta,
        COUNT(DISTINCT pt.id) AS total_puntos
    FROM etiquetas_turisticas et
    LEFT JOIN puntos_turisticos_etiqueta pte ON et.id = pte.id_etiqueta AND pte.estado = 'activo'
    LEFT JOIN puntos_turisticos pt ON pte.id_punto_turistico = pt.id AND pt.estado = true
    WHERE et.estado = true
    GROUP BY et.id, et.nombre, et.descripcion
    ORDER BY et.nombre
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    data_entries = []
    
    for row in results:
        nombre_etiqueta, descripcion, total_puntos = row
        
        info_etiqueta = f"La etiqueta '**{nombre_etiqueta}**' se refiere a: {descripcion}"
        
        if total_puntos > 0:
            info_etiqueta += f" Hay {total_puntos} puntos turísticos con esta categoría en Santo Domingo de los Tsáchilas."
        
        entry = {
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente experto en turismo de Santo Domingo de los Tsáchilas. Explicas las categorías turísticas y ayudas a los visitantes a entender los diferentes tipos de atracciones."
                },
                {
                    "role": "user",
                    "content": f"¿Qué significa la etiqueta {nombre_etiqueta}?"
                },
                {
                    "role": "assistant",
                    "content": info_etiqueta
                }
            ]
        }
        data_entries.append(entry)
    
    return data_entries

def main():
    """
    Función principal que genera el archivo JSONL completo
    """
    print("🚀 Generador de datos turísticos completo para Santo Domingo de los Tsáchilas")
    print("=" * 80)
    
    # Verificar dependencias
    if not check_dependencies():
        return
    
    # Conectar a la base de datos
    conn = connect_to_database()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("Generando datos completos para el chatbot...")
    
    all_data = []
    
    # Generar datos principales (puntos turísticos con toda la información)
    print("1. Generando datos principales de puntos turísticos...")
    all_data.extend(generate_comprehensive_tourism_data(cursor))
    
    # Generar datos específicos de parroquias
    print("2. Generando datos específicos de parroquias...")
    all_data.extend(generate_parroquias_data(cursor))
    
    # Generar datos de etiquetas
    print("3. Generando datos de etiquetas turísticas...")
    all_data.extend(generate_etiquetas_data(cursor))
    
    # Escribir al archivo JSONL
    output_file = 'turismo_data_completo_v2.jsonl'
    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in all_data:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    print(f"\n✅ Archivo generado exitosamente: {output_file}")
    print(f"📊 Total de entradas generadas: {len(all_data)}")
    
    # Estadísticas detalladas
    tipos_preguntas = defaultdict(int)
    for entry in all_data:
        user_content = entry["messages"][1]["content"].lower()
        if "cuéntame sobre" in user_content or "cuéntame de" in user_content:
            tipos_preguntas["Información general"] += 1
        elif "actividades" in user_content:
            tipos_preguntas["Actividades"] += 1
        elif "servicios" in user_content:
            tipos_preguntas["Servicios"] += 1
        elif "horarios" in user_content:
            tipos_preguntas["Horarios"] += 1
        elif "dónde se encuentra" in user_content:
            tipos_preguntas["Ubicación"] += 1
        elif "parroquia" in user_content:
            tipos_preguntas["Parroquias"] += 1
        elif "etiqueta" in user_content:
            tipos_preguntas["Etiquetas"] += 1
    
    print("\n📈 Estadísticas por tipo de pregunta:")
    for tipo, cantidad in tipos_preguntas.items():
        print(f"   {tipo}: {cantidad} entradas")
    
    print(f"\n💡 Archivo listo para usar con el chatbot.")
    print(f"   Reemplaza 'turismo__data.jsonl' con '{output_file}' en tu código del chatbot.")
    
    conn.close()

if __name__ == "__main__":
    main()

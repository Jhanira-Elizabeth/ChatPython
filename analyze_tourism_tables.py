"""
Script para revisar la estructura específica de las tablas de turismo
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from urllib.parse import urlparse, unquote

# Cargar variables de entorno
load_dotenv()

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
        'sslmode': 'require'
    }

def analyze_tourism_tables():
    """Analizar las tablas de turismo específicamente"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL no está configurada")
        return
    
    try:
        # Parsear configuración
        config = parse_database_url(DATABASE_URL)
        
        # Conectar
        conn = psycopg2.connect(**config)
        print("✅ Conexión exitosa!")
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Analizar tabla locales_turisticos
            print("\n🏛️ TABLA: locales_turisticos")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'locales_turisticos'
                ORDER BY ordinal_position;
            """)
            
            columns = cursor.fetchall()
            print("📋 Columnas:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  - {col['column_name']}: {col['data_type']} ({nullable})")
            
            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM locales_turisticos;")
            count = cursor.fetchone()[0]
            print(f"📊 Total registros: {count}")
            
            # Mostrar algunos ejemplos
            if count > 0:
                cursor.execute("SELECT * FROM locales_turisticos LIMIT 3;")
                samples = cursor.fetchall()
                print("🔍 Primeros 3 registros:")
                for i, sample in enumerate(samples, 1):
                    print(f"  {i}: {dict(sample)}")
            
            # Analizar tabla puntos_turisticos
            print("\n🏛️ TABLA: puntos_turisticos")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'puntos_turisticos'
                ORDER BY ordinal_position;
            """)
            
            columns = cursor.fetchall()
            print("📋 Columnas:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  - {col['column_name']}: {col['data_type']} ({nullable})")
            
            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM puntos_turisticos;")
            count = cursor.fetchone()[0]
            print(f"📊 Total registros: {count}")
            
            # Mostrar algunos ejemplos
            if count > 0:
                cursor.execute("SELECT * FROM puntos_turisticos LIMIT 3;")
                samples = cursor.fetchall()
                print("🔍 Primeros 3 registros:")
                for i, sample in enumerate(samples, 1):
                    print(f"  {i}: {dict(sample)}")
            
            # Analizar tabla etiquetas_turisticas
            print("\n🏛️ TABLA: etiquetas_turisticas")
            cursor.execute("SELECT COUNT(*) FROM etiquetas_turisticas;")
            count = cursor.fetchone()[0]
            print(f"📊 Total registros: {count}")
            
            if count > 0:
                cursor.execute("SELECT * FROM etiquetas_turisticas LIMIT 5;")
                samples = cursor.fetchall()
                print("🔍 Primeros 5 registros:")
                for i, sample in enumerate(samples, 1):
                    print(f"  {i}: {dict(sample)}")
            
            # Revisar tablas de relaciones
            print("\n🔗 TABLAS DE RELACIONES:")
            relation_tables = ['local_etiqueta', 'puntos_turisticos_etiqueta', 'servicios_locales']
            
            for table in relation_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count} registros")
                
                if count > 0:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 2;")
                    samples = cursor.fetchall()
                    for sample in samples:
                        print(f"    Ejemplo: {dict(sample)}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    analyze_tourism_tables()

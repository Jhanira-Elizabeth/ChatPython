"""
Script para explorar la estructura de la base de datos Azure PostgreSQL
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

def explore_database():
    """Explorar la estructura de la base de datos"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL no está configurada")
        return
    
    try:
        # Parsear configuración
        config = parse_database_url(DATABASE_URL)
        print(f"🔍 Explorando base de datos: {config['database']}")
        print(f"📡 Host: {config['host']}")
        print(f"👤 Usuario: {config['user']}")
        
        # Conectar
        conn = psycopg2.connect(**config)
        print("✅ Conexión exitosa!")
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Listar todas las tablas
            cursor.execute("""
                SELECT table_name, table_schema 
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_schema, table_name;
            """)
            
            tables = cursor.fetchall()
            print(f"\n📋 Tablas encontradas ({len(tables)}):")
            
            for table in tables:
                print(f"  - {table['table_schema']}.{table['table_name']}")
            
            # Buscar tablas relacionadas con turismo
            tourism_tables = [t for t in tables if 'turismo' in t['table_name'].lower() or 
                             'lugar' in t['table_name'].lower() or 
                             'local' in t['table_name'].lower()]
            
            if tourism_tables:
                print(f"\n🏛️ Tablas relacionadas con turismo:")
                for table in tourism_tables:
                    table_name = f"{table['table_schema']}.{table['table_name']}"
                    print(f"\n  📊 {table_name}")
                    
                    # Mostrar estructura de cada tabla
                    cursor.execute(f"""
                        SELECT column_name, data_type, is_nullable 
                        FROM information_schema.columns 
                        WHERE table_schema = '{table['table_schema']}' 
                        AND table_name = '{table['table_name']}'
                        ORDER BY ordinal_position;
                    """)
                    
                    columns = cursor.fetchall()
                    for col in columns:
                        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                        print(f"    - {col['column_name']}: {col['data_type']} ({nullable})")
                    
                    # Mostrar algunos registros de ejemplo
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    count = cursor.fetchone()[0]
                    print(f"    📊 Registros: {count}")
                    
                    if count > 0:
                        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                        samples = cursor.fetchall()
                        print(f"    🔍 Primeros 3 registros:")
                        for i, sample in enumerate(samples, 1):
                            print(f"      {i}: {dict(sample)}")
            
            # Buscar cualquier tabla que contenga datos de lugares
            print(f"\n🔍 Buscando datos de lugares en todas las tablas...")
            for table in tables:
                table_name = f"{table['table_schema']}.{table['table_name']}"
                try:
                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema = '{table['table_schema']}' AND table_name = '{table['table_name']}' AND column_name ILIKE '%nombre%';")
                    nombre_cols = cursor.fetchall()
                    
                    if nombre_cols:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                        count = cursor.fetchone()[0]
                        if count > 0:
                            print(f"  ✅ {table_name} tiene {count} registros con columna 'nombre'")
                except Exception as e:
                    continue
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    explore_database()

"""
Script para verificar el contenido real de la base de datos en Azure
"""

import requests
import json

def test_direct_database_queries():
    """Probar consultas directas a la base de datos via API"""
    
    base_url = "https://tursd-chatbot-fqdxgsa4arb8fjf9.brazilsouth-01.azurewebsites.net"
    
    print("🔍 VERIFICANDO CONTENIDO DE LA BASE DE DATOS")
    print("=" * 60)
    
    # Endpoints para probar
    endpoints = [
        ("/places", "Lugares turísticos"),
        ("/categories", "Categorías"),
        ("/activities", "Actividades"),
    ]
    
    for endpoint, description in endpoints:
        try:
            print(f"\n📊 {description} - {endpoint}")
            response = requests.get(f"{base_url}{endpoint}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: {response.status_code}")
                print(f"   📈 Count: {data.get('count', 'N/A')}")
                
                # Mostrar primeros elementos si existen
                items_key = list(data.keys())[1] if len(data.keys()) > 1 else None
                if items_key and isinstance(data.get(items_key), list) and len(data[items_key]) > 0:
                    print(f"   📝 Primer elemento:")
                    first_item = data[items_key][0]
                    for key, value in first_item.items():
                        print(f"      {key}: {value}")
                else:
                    print(f"   ⚠️  No hay datos en {description}")
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   📄 Response: {response.text}")
        
        except Exception as e:
            print(f"   ❌ Exception: {e}")

def test_chat_with_simple_message():
    """Probar el chat con un mensaje muy simple"""
    
    base_url = "https://tursd-chatbot-fqdxgsa4arb8fjf9.brazilsouth-01.azurewebsites.net"
    
    print(f"\n🤖 PROBANDO CHATBOT")
    print("=" * 30)
    
    messages = [
        "Hola",
        "¿Qué lugares puedo visitar?",
        "Información turística"
    ]
    
    for message in messages:
        try:
            print(f"\n💬 Mensaje: '{message}'")
            payload = {"message": message}
            response = requests.post(f"{base_url}/chat", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: {response.status_code}")
                print(f"   🤖 Respuesta: {data.get('response', 'Sin respuesta')}")
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   📄 Response: {response.text}")
        
        except Exception as e:
            print(f"   ❌ Exception: {e}")

if __name__ == "__main__":
    test_direct_database_queries()
    test_chat_with_simple_message()

import os
import psycopg2
from flask import Flask, request, jsonify
from openai import AzureOpenAI
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import re

# === Cargar variables de entorno ===
load_dotenv()

# === Inicializar Firebase una sola vez ===
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)

# === Conexión a PostgreSQL ===
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT", 5432)

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    port=DB_PORT,
    sslmode="require"
)

# === Azure OpenAI ===
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
GPT_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "chatbot-TURSD")

# === Consulta general para contexto base ===
QUERY_CONTEXT = """SELECT 
    lt.nombre AS nombre_local,
    lt.descripcion AS descripcion_local,
    dl.nombre AS nombre_dueno,
    pt.nombre AS nombre_punto_turistico,
    apt.actividad AS nombre_actividad,
    et.nombre AS nombre_etiqueta,
    p.nombre AS nombre_parroquia
FROM horarios_atencion ha
LEFT JOIN locales_turisticos lt ON ha.id_local = lt.id
LEFT JOIN duenos_locales dl ON lt.id_dueno = dl.id
LEFT JOIN servicios_locales sl ON lt.id = sl.id_local
LEFT JOIN local_etiqueta le ON lt.id = le.id_local
LEFT JOIN etiquetas_turisticas et ON le.id_etiqueta = et.id
LEFT JOIN parroquias p ON lt.id_parroquia = p.id
LEFT JOIN puntos_turisticos pt ON p.id = pt.id_parroquia
LEFT JOIN puntos_turisticos_etiqueta pte ON pt.id = pte.id_punto_turistico
LEFT JOIN actividad_punto_turistico apt ON pt.id = apt.id_punto_turistico
LIMIT 30;
"""

# === Funciones de contexto ===

def obtener_contexto():
    with conn.cursor() as cur:
        cur.execute(QUERY_CONTEXT)
        filas = cur.fetchall()
        contexto = ""
        for fila in filas:
            contexto += (
                f"Local: {fila[0]}\nDescripción: {fila[1]}\nDueño: {fila[2]}\n"
                f"Punto turístico: {fila[3]}\nActividad: {fila[4]}\n"
                f"Etiqueta: {fila[5]}\nParroquia: {fila[6]}\n\n"
            )
        return contexto

def obtener_resenas_procesadas():
    resenas_ref = db.collection('resenas')
    docs = resenas_ref.stream()
    resumen = {}
    for doc in docs:
        data = doc.to_dict()
        lugar = data.get("idLugar")
        calif = data.get("calificacion", 0)
        texto = data.get("texto", "")
        nombre = data.get("nombreUsuario", "Anónimo")
        if lugar not in resumen:
            resumen[lugar] = {"calificaciones": [], "comentarios": []}
        resumen[lugar]["calificaciones"].append(calif)
        if texto:
            resumen[lugar]["comentarios"].append(f"{nombre}: {texto}")
    texto_final = ""
    for lugar, data in resumen.items():
        promedio = sum(data["calificaciones"]) / len(data["calificaciones"]) if data["calificaciones"] else 0
        texto_final += f"Lugar ID {lugar} - Calificación promedio: {promedio:.1f}\n"
        texto_final += "\n".join(f"- {c}" for c in data["comentarios"]) + "\n\n"
    return texto_final or "No se encontraron reseñas."

# === Intenciones base con sinónimos ===
intenciones_sensibles = {
    "comida": ["comida", "gastronomía", "restaurante", "platos", "cocina", "alimentos"],
    "caminata": ["caminata", "senderismo", "andar", "paseo", "excursión", "trekking"]
}

# === Búsqueda contextual PostgreSQL ===

def buscar_lugares_por_intencion(palabra):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT lt.nombre, lt.descripcion, et.nombre AS etiqueta
            FROM locales_turisticos lt
            LEFT JOIN local_etiqueta le ON le.id_local = lt.id
            LEFT JOIN etiquetas_turisticas et ON le.id_etiqueta = et.id
            LEFT JOIN servicios_locales sl ON sl.id_local = lt.id
            WHERE LOWER(et.nombre) LIKE %s OR LOWER(sl.servicio) LIKE %s
        """, (f"%{palabra.lower()}%", f"%{palabra.lower()}%"))
        return cur.fetchall()

def buscar_actividades_por_intencion(palabra):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pt.nombre, apt.actividad, pt.descripcion
            FROM puntos_turisticos pt
            LEFT JOIN actividad_punto_turistico apt ON pt.id = apt.id_punto_turistico
            WHERE LOWER(apt.actividad) LIKE %s
        """, (f"%{palabra.lower()}%",))
        return cur.fetchall()

# === Historial y almacenamiento Firestore ===

def obtener_historial(chat_id):
    ref = db.collection("chats").document(chat_id).collection("conversaciones")
    docs = ref.order_by("timestamp").stream()
    return [{"role": d.to_dict()["rol"], "content": d.to_dict()["contenido"]} for d in docs if "rol" in d.to_dict()]

def guardar_mensaje(chat_id, rol, contenido):
    db.collection("chats").document(chat_id).collection("conversaciones").add({
        "rol": rol,
        "contenido": contenido,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

# === Ruta principal ===

@app.route("/chat", methods=["POST"])
def chat():

    try:
        data = request.json
        chat_id = data.get("chat_id")
        pregunta_usuario = data.get("message", "").strip()

        if not chat_id or not pregunta_usuario:
            return jsonify({"error": "Faltan datos"}), 400

        historial = obtener_historial(chat_id)
        historial.append({"role": "user", "content": pregunta_usuario})

        contexto_pg = obtener_contexto()
        contexto_fb = obtener_resenas_procesadas()
        contexto_completo = (
            f"DATOS DE LUGARES (PostgreSQL):\n{contexto_pg}\n"
            f"RESEÑAS DE USUARIOS (Firestore):\n{contexto_fb}\n"
        )

        # Buscar intenciones
        for intencion, palabras in intenciones_sensibles.items():
            if any(p in pregunta_usuario.lower() for p in palabras):
                lugares = buscar_lugares_por_intencion(intencion)
                actividades = buscar_actividades_por_intencion(intencion)

                if lugares:
                    contexto_completo += f"\nLUGARES RELACIONADOS CON {intencion.upper()}:\n"
                    for l in lugares:
                        contexto_completo += f"- {l[0]}: {l[1]} (Etiqueta: {l[2]})\n"

                if actividades:
                    contexto_completo += f"\nACTIVIDADES RELACIONADAS CON {intencion.upper()}:\n"
                    for a in actividades:
                        contexto_completo += f"- {a[0]}: {a[1]} ({a[2]})\n"

                # Opcional: registrar intención detectada
                db.collection("intenciones_detectadas").add({
                    "intencion": intencion,
                    "palabras_detectadas": palabras,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })

        # Construir prompt
        mensajes_modelo = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente turístico especializado en Ecuador. "
                    "Solo respondes preguntas sobre turismo, lugares, servicios y actividades. "
                    "Si te preguntan algo fuera de eso, responde amablemente que no puedes ayudar.\n\n"
                    f"{contexto_completo}"
                )
            }
        ] + historial

        # Llamada a Azure OpenAI
        response = client.chat.completions.create(
            model=GPT_DEPLOYMENT,
            messages=mensajes_modelo,
            temperature=0.7,
            max_tokens=700
        )
        respuesta = response.choices[0].message.content.strip()
        guardar_mensaje(chat_id, "assistant", respuesta)

        return jsonify({"response": respuesta})
    except Exception:
        # No mostrar detalles del error al usuario
        return jsonify({"response": "Lo siento, ocurrió un problema interno. Por favor intenta de nuevo más tarde."})

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8000)
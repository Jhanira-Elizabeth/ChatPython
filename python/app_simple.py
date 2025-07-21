import os
import psycopg2
from flask import Flask, request, jsonify
from openai import AzureOpenAI
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

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

# === Configuración Azure OpenAI ===
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

GPT_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "chatbot-TURSD")

# === Consulta turística principal ===
QUERY = """
SELECT 
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

def obtener_contexto():
    with conn.cursor() as cur:
        cur.execute(QUERY)
        filas = cur.fetchall()
        contexto = ""
        for fila in filas:
            contexto += (
                f"Local: {fila[0]}\n"
                f"Descripción: {fila[1]}\n"
                f"Dueño: {fila[2]}\n"
                f"Punto turístico: {fila[3]}\n"
                f"Actividad: {fila[4]}\n"
                f"Etiqueta: {fila[5]}\n"
                f"Parroquia: {fila[6]}\n\n"
            )
        return contexto

def obtener_resenas_procesadas():
    resenas_ref = db.collection('resenas')
    docs = resenas_ref.stream()

    resumen_por_lugar = {}

    for doc in docs:
        reseña = doc.to_dict()
        lugar = reseña.get("idLugar")
        calificacion = reseña.get("calificacion", 0)
        comentario = reseña.get("texto", "")
        nombre = reseña.get("nombreUsuario", "Anónimo")

        if lugar not in resumen_por_lugar:
            resumen_por_lugar[lugar] = {"calificaciones": [], "comentarios": []}

        resumen_por_lugar[lugar]["calificaciones"].append(calificacion)
        if comentario:
            resumen_por_lugar[lugar]["comentarios"].append(f"{nombre}: {comentario}")

    texto_contexto = ""
    for idLugar, data in resumen_por_lugar.items():
        if data["calificaciones"]:
            promedio = sum(data["calificaciones"]) / len(data["calificaciones"])
        else:
            promedio = 0
        texto_contexto += f"Lugar ID {idLugar} - Calificación promedio: {promedio:.1f}\n"
        for comentario in data["comentarios"]:
            texto_contexto += f"- {comentario}\n"
        texto_contexto += "\n"

    return texto_contexto or "No se encontraron reseñas."

# --- Función para obtener historial de chat desde Firestore ---
def obtener_historial(chat_id):
    conv_ref = db.collection("chats").document(chat_id).collection("conversaciones")
    docs = conv_ref.order_by("timestamp").stream()
    mensajes = []
    for doc in docs:
        data = doc.to_dict()
        if "rol" in data and "contenido" in data:
            mensajes.append({
                "role": data["rol"],
                "content": data["contenido"]
            })
    return mensajes

# --- Guardar mensaje en Firestore ---
def guardar_mensaje(chat_id, rol, contenido):
    conv_ref = db.collection("chats").document(chat_id).collection("conversaciones")
    conv_ref.add({
        "rol": rol,
        "contenido": contenido,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    chat_id = data.get("chat_id")
    pregunta_usuario = data.get("message", "").strip()

    if not chat_id:
        return jsonify({"error": "Falta el chat_id"}), 400
    if not pregunta_usuario:
        return jsonify({"error": "Falta el mensaje del usuario"}), 400

    # 1. Obtener historial previo (mensajes anteriores)
    historial = obtener_historial(chat_id)

    # 2. Agregar mensaje nuevo del usuario
    historial.append({"role": "user", "content": pregunta_usuario})

    # 3. Obtener contexto adicional (lugares y reseñas)
    contexto_pg = obtener_contexto()
    contexto_fb = obtener_resenas_procesadas()
    contexto_completo = (
        f"DATOS DE LUGARES (PostgreSQL):\n{contexto_pg}\n"
        f"RESEÑAS DE USUARIOS (Firestore):\n{contexto_fb}"
    )

    # 4. Armar mensajes para el modelo (incluyendo contexto como system)
    mensajes_modelo = [
        {
            "role": "system",
            "content": (
                "Eres un asistente turístico especializado en Ecuador. "
                "Solo respondes preguntas relacionadas con turismo, lugares, actividades y servicios turísticos. "
                "Si te preguntan sobre temas fuera del turismo, responde con: "
                "\"Lo siento, soy un asistente turístico y no puedo opinar sobre ese tema.\" "
                "Mantén siempre un tono amable y profesional.\n\n"
                f"{contexto_completo}"
            )
        }
    ] + historial

    # 5. Llamar a Azure OpenAI
    response = client.chat.completions.create(
        model=GPT_DEPLOYMENT,
        messages=mensajes_modelo,
        temperature=0.7,
        max_tokens=700
    )
    respuesta = response.choices[0].message.content.strip()

    # 6. Guardar la respuesta del asistente
    guardar_mensaje(chat_id, "assistant", respuesta)

    # 7. Devolver la respuesta
    return jsonify({"response": respuesta})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)

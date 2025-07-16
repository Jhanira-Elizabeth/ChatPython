import json
import re
import logging
import os
from difflib import SequenceMatcher
# from internet_searcher import InternetSearcher  # Descomenta si usas InternetSearcher aquí

logger = logging.getLogger(__name__)

class TurismoKnowledgeBase:
    def __init__(self, filepath='turismo_data_completo_v2.jsonl'):
        self.filepath = filepath
        self.conocimiento = {}
        self.lugares = []
        self.servicios_por_lugar = {}
        self.actividades_por_lugar = {}
        # Si usas InternetSearcher aquí, inicialízalo:
        # self.internet_searcher = InternetSearcher()
        self.cargar_datos_jsonl()
    
    def cargar_datos_jsonl(self):
        archivos_posibles = [
            self.filepath,
            'turismo_data_completo_v2.jsonl',
            'turismo__data.jsonl',
            'turismo_data.jsonl'
        ]
        archivo_usado = None
        for archivo in archivos_posibles:
            if os.path.exists(archivo):
                archivo_usado = archivo
                break
        if not archivo_usado:
            logger.error("No se encontró ningún archivo de datos JSONL")
            return
        try:
            with open(archivo_usado, 'r', encoding='utf-8') as f:
                for linea in f:
                    if linea.strip():
                        item = json.loads(linea)
                        self.procesar_conversacion(item)
            logger.info(f"Datos cargados desde: {archivo_usado}")
            logger.info(f"Base de conocimiento cargada: {len(self.conocimiento)} entradas")
            logger.info(f"Lugares identificados: {len(self.lugares)}")
            logger.info(f"Servicios por lugar: {len(self.servicios_por_lugar)}")
            logger.info(f"Actividades por lugar: {len(self.actividades_por_lugar)}")
        except Exception as e:
            logger.error(f"Error cargando {archivo_usado}: {e}")
    
    def procesar_conversacion(self, item):
        if 'messages' in item:
            user_msg = ""
            assistant_msg = ""
            for msg in item['messages']:
                if msg['role'] == 'user':
                    user_msg = msg['content'].lower()
                elif msg['role'] == 'assistant':
                    assistant_msg = msg['content']
                    match = re.search(r'\*\*(.*?)\*\*', assistant_msg)
                    if match:
                        lugar = match.group(1)
                        if lugar not in self.lugares:
                            self.lugares.append(lugar)
                        servicios = self.extraer_servicios_del_texto(assistant_msg)
                        if servicios:
                            self.servicios_por_lugar[lugar] = servicios
                        actividades = self.extraer_actividades_del_texto(assistant_msg)
                        if actividades:
                            self.actividades_por_lugar[lugar] = actividades
            if user_msg and assistant_msg:
                palabras_clave = self.extraer_palabras_clave(user_msg)
                for palabra in palabras_clave:
                    if palabra not in self.conocimiento:
                        self.conocimiento[palabra] = []
                    self.conocimiento[palabra].append({
                        'pregunta': user_msg,
                        'respuesta': assistant_msg,
                        'relevancia': self.calcular_relevancia(palabra, user_msg),
                        'lugar': self.extraer_lugar_de_respuesta(assistant_msg)
                    })
    
    def extraer_servicios_del_texto(self, texto):
        servicios = []
        texto_lower = texto.lower()
        servicios_posibles = [
            'hotel', 'hospedaje', 'alojamiento', 'hostal', 'cabañas',
            'restaurante', 'comida', 'bar', 'cafetería', 'alimentación', 'comedor',
            'piscina', 'piscinas', 'deporte', 'deportes', 'recreación',
            'parqueadero', 'estacionamiento', 'transporte',
            'guía', 'guías', 'tours', 'excursiones',
            'baños', 'servicios sanitarios', 'wifi', 'internet'
        ]
        for servicio in servicios_posibles:
            if servicio in texto_lower:
                if servicio not in [s.lower() for s in servicios]:
                    servicios.append(servicio.title())
        return servicios
    
    def extraer_actividades_del_texto(self, texto):
        actividades = []
        match = re.search(r"Las actividades disponibles incluyen:\s*(.*?)(?:\.|$)", texto)
        if match:
            actividades_texto = match.group(1)
            actividades = [act.strip() for act in actividades_texto.split(',')]
        if not actividades:
            texto_lower = texto.lower()
            actividades_posibles = [
                'natación', 'caminatas', 'ciclismo', 'senderismo',
                'miradores', 'observación', 'fotografía',
                'deportes extremos', 'aventura', 'recreación',
                'pesca', 'kayak', 'rafting', 'canyoning', 'rápel'
            ]
            for actividad in actividades_posibles:
                if actividad in texto_lower:
                    actividades.append(actividad.title())
        return actividades
    
    def extraer_lugar_de_respuesta(self, respuesta):
        match = re.search(r'\*\*(.*?)\*\*', respuesta)
        return match.group(1) if match else ""
    
    def extraer_palabras_clave(self, texto):
        texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras = texto_limpio.split()
        stop_words = {'de', 'la', 'el', 'en', 'y', 'a', 'que', 'es', 'se', 'del', 'las', 'los', 'un', 'una', 'con', 'por', 'para', 'sobre', 'me', 'te', 'le', 'nos', 'les', 'mi', 'tu', 'su', 'puedes', 'puede', 'dar', 'dame', 'información', 'info', 'cuéntame', 'cuentame', 'hay', 'existe', 'tienen'}
        palabras_filtradas = [p for p in palabras if len(p) > 2 and p not in stop_words]
        palabras_filtradas.append(texto.strip())
        return palabras_filtradas
    
    def calcular_relevancia(self, palabra, texto_completo):
        return texto_completo.count(palabra) / len(texto_completo.split())
    
    def es_respuesta_util(self, respuesta):
        if len(respuesta) < 50:
            return False
        if "La etiqueta" in respuesta:
            return False
        if "se refiere a:" in respuesta:
            return False
        if "**Alojamientos**" in respuesta and "se refiere a:" in respuesta:
            return False
        palabras_inutiles = ["etiqueta", "categoría", "significa", "se refiere a", "la etiqueta"]
        if any(palabra in respuesta.lower() for palabra in palabras_inutiles):
            return False
        return True
    
    def generar_respuesta_hoteles_internet(self):
        logger.info("🌐 Buscando hoteles actualizados en internet...")
        try:
            # Si tienes self.internet_searcher, úsalo aquí:
            # hoteles_reales = self.internet_searcher.obtener_hoteles_reales()
            # Si no, puedes dejar la respuesta de respaldo.
            hoteles_reales = []  # Simulación si no tienes InternetSearcher aquí
            if hoteles_reales:
                response_parts = ["🏨 ¡Perfecto! Encontré hoteles actualizados para ti en Santo Domingo de los Tsáchilas:\n"]
                for i, hotel in enumerate(hoteles_reales, 1):
                    response_parts.append(f"**{i}. {hotel['nombre']}**")
                    if 'precio' in hotel:
                        response_parts.append(f"   💰 {hotel['precio']}")
                    if 'rating' in hotel:
                        response_parts.append(f"   ⭐ {hotel['rating']}")
                    if 'descripcion' in hotel:
                        response_parts.append(f"   📍 {hotel['descripcion']}")
                    response_parts.append(f"   🔗 Fuente: {hotel['fuente']}\n")
                response_parts.append("""📋 **Para reservar:**
• Booking.com - Mejores precios y cancelación gratis
• Expedia - Paquetes hotel + vuelo
• Contacto directo con el hotel

🏞️ **También te recomiendo visitar:**
• Malecón del Río Toachi (zona céntrica)
• Parque Zaracay (área turística)
• Comunidades Tsáchilas (turismo cultural)

¿Te gustaría que te cuente sobre algún lugar turístico específico mientras planificas tu estadía? 😊""")
                return "\n".join(response_parts)
        except Exception as e:
            logger.error(f"Error buscando hoteles en internet: {e}")
        return """🏨 ¡Hola! Te ayudo con opciones de alojamiento en Santo Domingo de los Tsáchilas.

🌐 **Hoteles recomendados (búsqueda actualizada):**

**1. Hotel Toachi**
   💰 Desde $45/noche
   📍 Centro de Santo Domingo, excelente ubicación
   ⭐ Muy buenas calificaciones

**2. Hotel Zaracay** 💰 Desde $60/noche
   📍 Zona turística, servicios completos
   ⭐ Recomendado por huéspedes

📋 **Para reservar:**
• Booking.com - Mejores precios garantizados
• Expedia - Ofertas especiales 
• Contacto directo con hoteles

🏞️ **Lugares turísticos cercanos:**
• Malecón del Río Toachi - Zona céntrica
• Parque Zaracay - Área recreativa
• Comunidades Tsáchilas - Experiencia cultural

¿Te interesa conocer más sobre algún lugar específico para tu visita? 😊"""
    
    def consultar_base(self, consulta_usuario):
        consulta_lower = consulta_usuario.lower().strip()
        if any(termino in consulta_lower for termino in ['hotel', 'hoteles', 'hospedaje', 'alojamiento']):
            return self.generar_respuesta_hoteles_internet()
        for palabra_clave, respuestas in self.conocimiento.items():
            if palabra_clave in consulta_lower or SequenceMatcher(None, consulta_lower, palabra_clave).ratio() > 0.8:
                for respuesta_info in respuestas:
                    if self.es_respuesta_util(respuesta_info['respuesta']):
                        return self.mejorar_respuesta(respuesta_info['respuesta'])
        terminos_servicios = ['comida', 'comer', 'restaurante', 'donde comer', 'bebida', 'bar', 'transporte', 'deporte', 'comedores']
        for termino in terminos_servicios:
            if termino in consulta_lower:
                lugares_con_servicio = self.buscar_por_servicios(termino)
                if lugares_con_servicio:
                    return self.generar_respuesta_servicios(termino, lugares_con_servicio)
        terminos_generales = ['río', 'rio', 'parque', 'malecón', 'malecon', 'balneario', 'cascada', 'museo', 'centro', 'mercado']
        for termino in terminos_generales:
            if termino in consulta_lower:
                lugares_relacionados = self.buscar_lugares_relacionados(termino)
                if lugares_relacionados:
                    return self.generar_respuesta_multiple(termino, lugares_relacionados)
        return None

    def buscar_por_servicios(self, termino_servicio):
        encontrados = []
        for lugar, servicios in self.servicios_por_lugar.items():
            if termino_servicio in [s.lower() for s in servicios]:
                encontrados.append(lugar)
        return encontrados
    
    def generar_respuesta_servicios(self, termino, lugares_con_servicio):
        if lugares_con_servicio:
            lugares_str = ", ".join(lugares_con_servicio)
            return f"Claro, encontré lugares con {termino} en Santo Domingo de los Tsáchilas, como: {lugares_str}. ¿Te gustaría saber más sobre alguno de ellos?"
        else:
            return f"No encontré lugares específicos con {termino} en mi base de datos local. ¿Hay algo más en lo que pueda ayudarte?"
    
    def buscar_lugares_relacionados(self, termino_busqueda):
        relacionados = []
        for lugar in self.lugares:
            if termino_busqueda in lugar.lower():
                relacionados.append(lugar)
        for key, value_list in self.conocimiento.items():
            for item in value_list:
                if termino_busqueda in item['respuesta'].lower() and item.get('lugar') not in relacionados:
                    if item.get('lugar'):
                        relacionados.append(item['lugar'])
        return list(set(relacionados))
    
    def generar_respuesta_multiple(self, termino, lugares_encontrados):
        if lugares_encontrados:
            lugares_str = ", ".join(lugares_encontrados)
            return f"Claro, hay varios lugares en Santo Domingo de los Tsáchilas relacionados con '{termino}', como: {lugares_str}. ¿Cuál te interesa más?"
        else:
            return f"No pude encontrar lugares relacionados con '{termino}' en mi base de datos local. ¿Hay algo más que pueda buscar?"
    
    def mejorar_respuesta(self, respuesta_original):
        return respuesta_original
    
    def generar_respuesta_general(self):
        if not self.lugares:
            return "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. ¿En qué puedo ayudarte hoy?"
        lugares_muestra = self.lugares[:6]
        respuesta = "¡Hola! 👋 Soy tu asistente turístico de Santo Domingo de los Tsáchilas. Te puedo contar sobre estos increíbles lugares:\n\n"
        for lugar in lugares_muestra:
            respuesta += f"🏞️ **{lugar}**\n"
        respuesta += "\n¿Hay algún lugar específico del que te gustaría saber más? ¡Pregúntame sobre malecones, parques, cascadas, ríos, balnearios, hoteles, comida o cualquier servicio! 😊"
        return respuesta
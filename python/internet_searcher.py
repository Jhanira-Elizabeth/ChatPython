import requests
from bs4 import BeautifulSoup
import logging
# Puedes necesitar importar OpenAI aquí si lo usas para resumir los resultados de búsqueda
# from openai import OpenAI 

logger = logging.getLogger(__name__)

class InternetSearcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Si usas OpenAI para resumir, inicialízalo aquí
        # self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def buscar_hoteles_booking(self, ciudad="Santo Domingo de los Tsáchilas"):
        """Busca hoteles en Booking.com"""
        try:
            # URL de búsqueda de Booking.com para Santo Domingo
            search_url = f"https://www.booking.com/searchresults.html?ss={ciudad.replace(' ', '+')}&checkin_year=2025&checkin_month=1&checkin_monthday=15&checkout_year=2025&checkout_month=1&checkout_monthday=16"
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                hoteles = []
                # Buscar hoteles en Booking
                hotel_elements = soup.find_all('div', {'data-testid': 'property-card'})[:3]
                
                for hotel in hotel_elements:
                    try:
                        nombre_elem = hotel.find('div', {'data-testid': 'title'})
                        precio_elem = hotel.find('span', {'data-testid': 'price-and-discounted-price'})
                        rating_elem = hotel.find('div', {'data-testid': 'review-score'})
                        
                        if nombre_elem:
                            nombre = nombre_elem.get_text(strip=True)
                            precio = precio_elem.get_text(strip=True) if precio_elem else "Precio disponible al reservar"
                            rating = rating_elem.get_text(strip=True) if rating_elem else "Sin calificación"
                            
                            hoteles.append({
                                'nombre': nombre,
                                'precio': precio,
                                'rating': rating,
                                'fuente': 'Booking.com'
                            })
                    except Exception as e:
                        continue
                
                return hoteles
            
        except Exception as e:
            logger.error(f"Error buscando en Booking: {e}")
        
        return []
    
    def buscar_hoteles_google(self, ciudad="Santo Domingo de los Tsáchilas"):
        """Busca hoteles usando Google (método alternativo)"""
        try:
            # Búsqueda directa en Google
            query = f"hoteles {ciudad} Ecuador precios 2025"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                hoteles = []
                # Buscar resultados de hoteles
                # OJO: Los selectores de Google pueden cambiar frecuentemente.
                # 'div', class_='g' es un selector general, podrías necesitar ser más específico.
                results = soup.find_all('div', class_='g')[:3]
                
                for result in results:
                    try:
                        title_elem = result.find('h3')
                        snippet_elem = result.find('span', class_='st') # O 'div', class_='IsZOp' en algunas versiones de Google
                        
                        if title_elem and 'hotel' in title_elem.get_text().lower():
                            nombre = title_elem.get_text(strip=True)
                            descripcion = snippet_elem.get_text(strip=True)[:100] + "..." if snippet_elem else "Hotel en Santo Domingo"
                            
                            hoteles.append({
                                'nombre': nombre,
                                'descripcion': descripcion,
                                'fuente': 'Google Search'
                            })
                    except Exception as e:
                        continue
                
                return hoteles
            
        except Exception as e:
            logger.error(f"Error buscando en Google: {e}")
        
        return []
    
    def obtener_hoteles_reales(self):
        """Obtiene hoteles reales combinando diferentes fuentes"""
        hoteles_encontrados = []
        
        # Intentar Booking primero
        hoteles_booking = self.buscar_hoteles_booking()
        if hoteles_booking:
            hoteles_encontrados.extend(hoteles_booking)
        
        # Si no encuentra en Booking, intentar Google
        if not hoteles_encontrados:
            hoteles_google = self.buscar_hoteles_google()
            hoteles_encontrados.extend(hoteles_google)
        
        # Si no encuentra nada, usar datos conocidos de hoteles en Santo Domingo
        if not hoteles_encontrados:
            hoteles_encontrados = [
                {
                    'nombre': 'Hotel Toachi',
                    'precio': 'Desde $45/noche',
                    'descripcion': 'Hotel céntrico en Santo Domingo de los Tsáchilas',
                    'fuente': 'Datos locales'
                },
                {
                    'nombre': 'Hotel Zaracay',
                    'precio': 'Desde $60/noche', 
                    'descripcion': 'Hotel con servicios completos y ubicación privilegiada',
                    'fuente': 'Datos locales'
                }
            ]
        
        return hoteles_encontrados[:3]   # Máximo 3 hoteles

    def buscar_general_google(self, query):
        """
        Realiza una búsqueda general en Google, forzando los resultados a "Santo Domingo, Ecuador".
        Retorna un texto con los snippets relevantes.
        """
        try:
            # Añadir el modificador de búsqueda geográfica
            search_query = f"{query} en Santo Domingo Ecuador"
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}&hl=es" # hl=es para resultados en español
            
            response = requests.get(search_url, headers=self.headers, timeout=15) # Aumentar timeout para búsquedas generales
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                snippets = []
                # Buscar los "snippets" o descripciones de los resultados de búsqueda
                # OJO: Los selectores de Google pueden cambiar frecuentemente.
                # 'div', class_='IsZOp' es un selector común para snippets/descripciones.
                # También se pueden buscar 'span', class_='st' o 'div', class_='l'
                
                # Intentar encontrar bloques de texto general (pueden ser 'div', 'p', 'span')
                # Buscaremos los elementos que contengan la descripción del resultado de búsqueda
                # A menudo están dentro de 'div' con clases como 'VwiC3b' o 'IsZOp'
                for snippet_elem in soup.find_all(['span', 'div'], class_=lambda x: x and ('st' in x or 'VwiC3b' in x or 'IsZOp' in x)):
                    text = snippet_elem.get_text(strip=True)
                    if text and len(text) > 50: # Solo snippets con contenido significativo
                        snippets.append(text)
                        if len(snippets) >= 3: # Tomar los primeros 3 snippets relevantes
                            break
                
                if snippets:
                    # Unir los snippets para formar un texto que puede ser resumido por un LLM si lo deseas
                    return "\n".join(snippets)
                else:
                    logger.warning(f"No se encontraron snippets para la búsqueda general: {query}")
                    return None # No se encontró información útil
            else:
                logger.error(f"Error HTTP {response.status_code} al buscar en Google para: {query}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red o timeout al buscar en Google para '{query}': {e}")
            return None
        except Exception as e:
            logger.error(f"Error general al procesar la búsqueda en Google para '{query}': {e}")
            return None
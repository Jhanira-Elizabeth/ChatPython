"""
Configuración de startup para Azure App Service
"""
import os
from api_chatbot_azure_final import app

# Azure App Service espera que la aplicación esté disponible en el puerto especificado por la variable de entorno PORT
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)

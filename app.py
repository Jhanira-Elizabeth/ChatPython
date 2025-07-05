"""
Punto de entrada principal para Azure App Service
Versión simplificada que funciona sin base de datos
"""
from app_simple import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

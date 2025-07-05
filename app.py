"""
Punto de entrada principal para Azure App Service
"""
from api_chatbot_azure_final import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

#!/bin/bash

# Script de despliegue para Azure App Service
# Ejecutar desde Git Bash o WSL

echo "🚀 Iniciando despliegue de Chatbot Turístico en Azure App Service..."

# Verificar que Azure CLI esté instalado
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI no está instalado. Instálalo desde: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Variables de configuración
RESOURCE_GROUP="tursd"
APP_NAME="chatbot-tursd"
LOCATION="brazilsouth"
PLAN_NAME="chatbot-tursd-plan"

echo "📋 Configuración del despliegue:"
echo "   Grupo de recursos: $RESOURCE_GROUP"
echo "   Nombre de la app: $APP_NAME"
echo "   Ubicación: $LOCATION"
echo "   Plan de servicio: $PLAN_NAME"

# Iniciar sesión en Azure (si no está autenticado)
echo "🔐 Verificando autenticación Azure..."
az account show > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "🔐 Iniciando sesión en Azure..."
    az login
fi

# Crear grupo de recursos (si no existe)
echo "📦 Verificando grupo de recursos..."
az group show --name $RESOURCE_GROUP > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "📦 Creando grupo de recursos..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
else
    echo "✅ Grupo de recursos ya existe"
fi

# Crear plan de App Service (si no existe)
echo "🏗️ Verificando plan de App Service..."
az appservice plan show --name $PLAN_NAME --resource-group $RESOURCE_GROUP > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "🏗️ Creando plan de App Service..."
    az appservice plan create --name $PLAN_NAME --resource-group $RESOURCE_GROUP --sku F1 --is-linux
else
    echo "✅ Plan de App Service ya existe"
fi

# Crear aplicación web (si no existe)
echo "🌐 Verificando aplicación web..."
az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "🌐 Creando aplicación web..."
    az webapp create --resource-group $RESOURCE_GROUP --plan $PLAN_NAME --name $APP_NAME --runtime "PYTHON|3.11"
else
    echo "✅ Aplicación web ya existe"
fi

# Configurar variables de entorno
echo "⚙️ Configurando variables de entorno..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $APP_NAME --settings \
    DATABASE_URL="postgres://tursd:elizabeth18.@tursd.postgres.database.azure.com:5432/tursd?sslmode=require" \
    OPENAI_API_KEY="tu_openai_api_key_aqui" \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    ENABLE_ORYX_BUILD=true

# Configurar el comando de inicio
echo "🔧 Configurando comando de inicio..."
az webapp config set --resource-group $RESOURCE_GROUP --name $APP_NAME --startup-file "startup.py"

# Desplegar código
echo "📤 Desplegando código..."
az webapp deployment source config-local-git --name $APP_NAME --resource-group $RESOURCE_GROUP

echo "✅ Despliegue configurado exitosamente!"
echo ""
echo "📋 Próximos pasos:"
echo "1. Configurar Git remote:"
echo "   git remote add azure https://$APP_NAME.scm.azurewebsites.net:443/$APP_NAME.git"
echo ""
echo "2. Hacer commit y push:"
echo "   git add ."
echo "   git commit -m \"Deploy chatbot to Azure\""
echo "   git push azure main"
echo ""
echo "3. Tu aplicación estará disponible en:"
echo "   https://$APP_NAME.azurewebsites.net"
echo ""
echo "🔧 Para ver logs en tiempo real:"
echo "   az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"

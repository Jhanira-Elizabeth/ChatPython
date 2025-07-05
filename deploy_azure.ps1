# Script de despliegue para Azure App Service (PowerShell)
# Ejecutar desde PowerShell como Administrador

Write-Host "🚀 Iniciando despliegue de Chatbot Turístico en Azure App Service..." -ForegroundColor Green

# Verificar que Azure CLI esté instalado
try {
    az --version | Out-Null
    Write-Host "✅ Azure CLI detectado" -ForegroundColor Green
} catch {
    Write-Host "❌ Azure CLI no está instalado. Instálalo desde: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Red
    exit 1
}

# Variables de configuración
$RESOURCE_GROUP = "tursd"
$APP_NAME = "chatbot-tursd"
$LOCATION = "brazilsouth"
$PLAN_NAME = "chatbot-tursd-plan"

Write-Host "📋 Configuración del despliegue:" -ForegroundColor Cyan
Write-Host "   Grupo de recursos: $RESOURCE_GROUP" -ForegroundColor White
Write-Host "   Nombre de la app: $APP_NAME" -ForegroundColor White
Write-Host "   Ubicación: $LOCATION" -ForegroundColor White
Write-Host "   Plan de servicio: $PLAN_NAME" -ForegroundColor White

# Verificar autenticación
Write-Host "🔐 Verificando autenticación Azure..." -ForegroundColor Yellow
try {
    az account show | Out-Null
    Write-Host "✅ Autenticado en Azure" -ForegroundColor Green
} catch {
    Write-Host "🔐 Iniciando sesión en Azure..." -ForegroundColor Yellow
    az login
}

# Crear grupo de recursos (si no existe)
Write-Host "📦 Verificando grupo de recursos..." -ForegroundColor Yellow
try {
    az group show --name $RESOURCE_GROUP | Out-Null
    Write-Host "✅ Grupo de recursos ya existe" -ForegroundColor Green
} catch {
    Write-Host "📦 Creando grupo de recursos..." -ForegroundColor Yellow
    az group create --name $RESOURCE_GROUP --location $LOCATION
}

# Crear plan de App Service (si no existe)
Write-Host "🏗️ Verificando plan de App Service..." -ForegroundColor Yellow
try {
    az appservice plan show --name $PLAN_NAME --resource-group $RESOURCE_GROUP | Out-Null
    Write-Host "✅ Plan de App Service ya existe" -ForegroundColor Green
} catch {
    Write-Host "🏗️ Creando plan de App Service..." -ForegroundColor Yellow
    az appservice plan create --name $PLAN_NAME --resource-group $RESOURCE_GROUP --sku F1 --is-linux
}

# Crear aplicación web (si no existe)
Write-Host "🌐 Verificando aplicación web..." -ForegroundColor Yellow
try {
    az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP | Out-Null
    Write-Host "✅ Aplicación web ya existe" -ForegroundColor Green
} catch {
    Write-Host "🌐 Creando aplicación web..." -ForegroundColor Yellow
    az webapp create --resource-group $RESOURCE_GROUP --plan $PLAN_NAME --name $APP_NAME --runtime "PYTHON|3.11"
}

# Configurar variables de entorno
Write-Host "⚙️ Configurando variables de entorno..." -ForegroundColor Yellow
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $APP_NAME --settings `
    DATABASE_URL="postgres://tursd:elizabeth18.@tursd.postgres.database.azure.com:5432/tursd?sslmode=require" `
    OPENAI_API_KEY="tu_openai_api_key_aqui" `
    SCM_DO_BUILD_DURING_DEPLOYMENT=true `
    ENABLE_ORYX_BUILD=true

# Configurar el comando de inicio
Write-Host "🔧 Configurando comando de inicio..." -ForegroundColor Yellow
az webapp config set --resource-group $RESOURCE_GROUP --name $APP_NAME --startup-file "startup.py"

# Configurar despliegue desde Git
Write-Host "📤 Configurando despliegue desde Git..." -ForegroundColor Yellow
az webapp deployment source config-local-git --name $APP_NAME --resource-group $RESOURCE_GROUP

Write-Host "✅ Despliegue configurado exitosamente!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Próximos pasos:" -ForegroundColor Cyan
Write-Host "1. Inicializar Git (si no está inicializado):" -ForegroundColor White
Write-Host "   git init" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Configurar Git remote:" -ForegroundColor White
Write-Host "   git remote add azure https://$APP_NAME.scm.azurewebsites.net:443/$APP_NAME.git" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Hacer commit y push:" -ForegroundColor White
Write-Host "   git add ." -ForegroundColor Gray
Write-Host "   git commit -m `"Deploy chatbot to Azure`"" -ForegroundColor Gray
Write-Host "   git push azure main" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Tu aplicación estará disponible en:" -ForegroundColor White
Write-Host "   https://$APP_NAME.azurewebsites.net" -ForegroundColor Gray
Write-Host ""
Write-Host "🔧 Para ver logs en tiempo real:" -ForegroundColor Cyan
Write-Host "   az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP" -ForegroundColor Gray

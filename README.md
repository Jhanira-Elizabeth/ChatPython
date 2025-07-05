# 🌿 Chatbot Turístico de Santo Domingo de los Tsáchilas

API REST de chatbot para turismo en Santo Domingo de los Tsáchilas, conectado a base de datos PostgreSQL en Azure.

## 🚀 Despliegue en Azure App Service

### Prerrequisitos

1. **Azure CLI instalado**
   ```bash
   # Windows (PowerShell como Administrador)
   winget install Microsoft.AzureCLI
   
   # O descargar desde: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
   ```

2. **Git instalado**
   ```bash
   # Windows
   winget install Git.Git
   ```

3. **Cuenta de Azure activa**

### Método 1: Despliegue automatizado (Recomendado)

#### Para Windows (PowerShell):
```powershell
# Ejecutar como Administrador
cd "c:\Users\arand\Documents\Universidad\Tesis\openAI"
.\deploy_azure.ps1
```

#### Para Linux/Mac/WSL:
```bash
cd "c:\Users\arand\Documents\Universidad\Tesis\openAI"
chmod +x deploy_azure.sh
./deploy_azure.sh
```

### Método 2: Despliegue manual

#### 1. Autenticarse en Azure
```bash
az login
```

#### 2. Crear recursos de Azure
```bash
# Variables
RESOURCE_GROUP="tursd"
APP_NAME="chatbot-tursd"
LOCATION="brazilsouth"
PLAN_NAME="chatbot-tursd-plan"

# Crear grupo de recursos
az group create --name $RESOURCE_GROUP --location $LOCATION

# Crear plan de App Service (gratuito)
az appservice plan create --name $PLAN_NAME --resource-group $RESOURCE_GROUP --sku F1 --is-linux

# Crear aplicación web
az webapp create --resource-group $RESOURCE_GROUP --plan $PLAN_NAME --name $APP_NAME --runtime "PYTHON|3.11"
```

#### 3. Configurar variables de entorno
```bash
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $APP_NAME --settings \
    DATABASE_URL="postgres://tursd:elizabeth18.@tursd.postgres.database.azure.com:5432/tursd?sslmode=require" \
    OPENAI_API_KEY="tu_openai_api_key_real_aqui" \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    ENABLE_ORYX_BUILD=true
```

#### 4. Configurar comando de inicio
```bash
az webapp config set --resource-group $RESOURCE_GROUP --name $APP_NAME --startup-file "startup.py"
```

#### 5. Configurar despliegue desde Git
```bash
az webapp deployment source config-local-git --name $APP_NAME --resource-group $RESOURCE_GROUP
```

#### 6. Desplegar código
```bash
# Inicializar Git (si no está inicializado)
git init

# Agregar remote de Azure
git remote add azure https://chatbot-tursd.scm.azurewebsites.net:443/chatbot-tursd.git

# Hacer commit y push
git add .
git commit -m "Deploy chatbot to Azure"
git push azure main
```

### 🔧 Verificar despliegue

#### 1. Ver logs en tiempo real
```bash
az webapp log tail --name chatbot-tursd --resource-group tursd
```

#### 2. Probar la aplicación
- **URL de la aplicación**: https://chatbot-tursd.azurewebsites.net
- **Endpoint de salud**: https://chatbot-tursd.azurewebsites.net/health
- **Endpoint del chat**: https://chatbot-tursd.azurewebsites.net/chat

#### 3. Probar con curl
```bash
# Probar endpoint de salud
curl https://chatbot-tursd.azurewebsites.net/health

# Probar chatbot
curl -X POST https://chatbot-tursd.azurewebsites.net/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿qué lugares turísticos me recomiendas?"}'
```

## 📁 Estructura del proyecto

```
.
├── api_chatbot_azure_final.py  # API principal del chatbot
├── app.py                      # Punto de entrada alternativo
├── startup.py                  # Punto de entrada para Azure
├── requirements.txt            # Dependencias Python
├── runtime.txt                 # Versión de Python
├── web.config                  # Configuración IIS (Azure)
├── Procfile                    # Configuración de proceso
├── .gitignore                  # Archivos a ignorar en Git
├── deploy_azure.ps1            # Script de despliegue (PowerShell)
├── deploy_azure.sh             # Script de despliegue (Bash)
└── README.md                   # Este archivo
```

## 🌐 Endpoints de la API

### GET `/`
Información general de la API

### GET `/health`
Estado de salud de la API y conexión a base de datos

### POST `/chat`
Endpoint principal del chatbot

**Request:**
```json
{
    "message": "¿Qué lugares turísticos hay en Santo Domingo?"
}
```

**Response:**
```json
{
    "response": "Te recomiendo visitar el Jardín Botánico La Carolina, el Parque Zaracay..."
}
```

## 🔒 Variables de entorno

Las siguientes variables de entorno deben estar configuradas en Azure:

- `DATABASE_URL`: URL de conexión a PostgreSQL
- `OPENAI_API_KEY`: Clave de API de OpenAI
- `SCM_DO_BUILD_DURING_DEPLOYMENT`: true
- `ENABLE_ORYX_BUILD`: true

## 🐛 Solución de problemas

### Error de conexión a base de datos
```bash
# Verificar que la base de datos esté accesible
az webapp log tail --name chatbot-tursd --resource-group tursd
```

### Error de despliegue
```bash
# Ver logs de construcción
az webapp log deployment show --name chatbot-tursd --resource-group tursd
```

### Reiniciar aplicación
```bash
az webapp restart --name chatbot-tursd --resource-group tursd
```

## 📱 Consumo desde aplicaciones móviles

La API está configurada con CORS habilitado para permitir requests desde cualquier origen. Ejemplo de uso en JavaScript:

```javascript
// Ejemplo para aplicación móvil
const response = await fetch('https://chatbot-tursd.azurewebsites.net/chat', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        message: '¿Qué lugares turísticos me recomiendas?'
    })
});

const data = await response.json();
console.log(data.response);
```

## 🔄 Actualizar la aplicación

Para actualizar el código:

```bash
# Hacer cambios en el código
git add .
git commit -m "Actualización del chatbot"
git push azure main
```

## 🆘 Soporte

Si tienes problemas con el despliegue:

1. Verifica que Azure CLI esté instalado y autenticado
2. Revisa los logs de la aplicación
3. Verifica que las variables de entorno estén configuradas
4. Asegúrate de que la base de datos PostgreSQL esté accesible

# 🚀 Guía de Despliegue en Azure App Service

## ⚠️ IMPORTANTE: Crear Web App, NO Function App

### 📋 Paso 1: Crear Azure Web App (Correcto)

1. **Ve al Portal de Azure** → https://portal.azure.com
2. **Busca "App Services"** (NO "Function App")
3. **Haz clic en "Crear"** → **"Web App"**

### 🔧 Configuración para Web App:

**Pestaña "Datos básicos":**
```
Suscripción: Azure for Students
Grupo de recursos: tursd (usar existente)
Nombre: tursd-chatbot (debe ser único globalmente)
Publicar: Código
Pila del entorno de ejecución: Python 3.10
Versión: 3.10
Sistema operativo: Linux
Región: Brazil South (mismo que tu PostgreSQL)
```

**Plan de App Service:**
```
Nombre: ASP-tursd-chatbot
SKU: B1 (Basic) - Recomendado para producción
O F1 (Free) - Solo para pruebas
```

**Pestaña "Implementación":**
```
Implementación continua: Habilitar más tarde
Autenticación básica: Habilitado (necesario para git deploy)
```

**Pestaña "Supervisión":**
```
Application Insights: Habilitar
Región: Brazil South
```

### 🔐 Paso 2: Configurar Variables de Entorno

Después de crear la Web App:

1. **Ve a tu Web App** → **"Configuración"** → **"Configuración de la aplicación"**
2. **Agrega estas variables:**

```
OPENAI_API_KEY = tu_api_key_real_de_openai
DATABASE_URL = postgres://tursd:elizabeth18.@tursd.postgres.database.azure.com:5432/tursd?sslmode=require
SCM_DO_BUILD_DURING_DEPLOYMENT = true
ENABLE_ORYX_BUILD = true
```

### 📦 Paso 3: Desplegar el Código

**Opción A: Deployment Center (Recomendado)**
1. Ve a **"Centro de implementación"**
2. Selecciona **"Local Git"**
3. Copia la **URL de Git** que aparece

**Opción B: GitHub (Alternativo)**
1. Sube tu código a GitHub
2. Conecta el repositorio desde el Centro de implementación

### 🔄 Paso 4: Comandos Git para Despliegue

Ejecuta estos comandos desde tu directorio del proyecto:

```bash
# Si no tienes git inicializado
git init

# Agregar archivos
git add .
git commit -m "Initial deployment"

# Conectar con Azure (usar URL del Centro de implementación)
git remote add azure <URL_DE_AZURE_GIT>

# Desplegar
git push azure main
```

### ✅ Paso 5: Verificar Despliegue

1. **Ve a la URL de tu Web App:** `https://tursd-chatbot.azurewebsites.net`
2. **Verifica endpoints:**
   - `GET /` - Información de la API
   - `GET /health` - Estado de salud
   - `POST /chat` - Endpoint del chatbot

### 🛠️ Comandos Azure CLI (Alternativo)

Si prefieres usar Azure CLI:

```bash
# Iniciar sesión
az login

# Crear Web App
az webapp create \
  --resource-group tursd \
  --plan ASP-tursd-chatbot \
  --name tursd-chatbot \
  --runtime "PYTHON|3.10" \
  --startup-file "startup.py"

# Configurar variables
az webapp config appsettings set \
  --resource-group tursd \
  --name tursd-chatbot \
  --settings \
    OPENAI_API_KEY="tu_api_key_aqui" \
    DATABASE_URL="postgres://tursd:elizabeth18.@tursd.postgres.database.azure.com:5432/tursd?sslmode=require"

# Desplegar desde directorio local
az webapp up \
  --resource-group tursd \
  --name tursd-chatbot \
  --runtime "PYTHON:3.10"
```

### 🔍 Solución de Problemas

**Si hay errores de despliegue:**
1. Ve a **"Centro de implementación"** → **"Registros"**
2. Revisa los logs de construcción
3. Verifica que `requirements.txt` esté presente
4. Verifica que `app.py` esté en la raíz del proyecto

**Si la app no inicia:**
1. Ve a **"Registro de diagnóstico"** 
2. Habilita **"Registro de aplicaciones"**
3. Revisa logs en **"Secuencia de registro"**

### 📱 Probar desde Aplicación Móvil

**URL Base:** `https://tursd-chatbot.azurewebsites.net`

**Ejemplo de petición POST:**
```json
POST /chat
Content-Type: application/json

{
  "message": "¿Qué lugares turísticos puedo visitar en Santo Domingo?"
}
```

**Respuesta esperada:**
```json
{
  "response": "¡Hola! Te recomiendo visitar estos increíbles lugares..."
}
```

---

## ⚡ Resumen de Archivos Necesarios

Asegúrate de tener estos archivos en tu proyecto:
- ✅ `app.py` (punto de entrada)
- ✅ `requirements.txt` (dependencias)
- ✅ `startup.py` (configuración startup)
- ✅ `web.config` (configuración IIS)
- ✅ `.gitignore` (archivos a ignorar)

¡Tu chatbot estará listo para producción! 🎉

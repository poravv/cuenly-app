# CuenlyApp

CuenlyApp es una herramienta automatizada para extraer información de facturas a partir de correos electrónicos y consolidarla en archivos Excel.

## 🚀 Características

- Conexión automática a cuentas de correo para recuperar facturas
- Extracción de PDFs adjuntos o desde enlaces
- Procesamiento de PDFs mediante OCR para extraer información clave
- Uso de inteligencia artificial para identificar datos de facturas
- Exportación automática a Excel
- API RESTful para integración con otros sistemas
- Interfaz web amigable para gestión

## 🧱 Arquitectura

### Backend
- Python 3.9+
- FastAPI
- PyMuPDF / Tesseract OCR
- Pandas para manipulación de datos

### Frontend
- Angular 15
- Bootstrap 5

## 📋 Requisitos Previos

- Python 3.9 o superior
- Node.js 16 o superior (para desarrollo frontend)
- Tesseract OCR instalado en el sistema
- Docker y Kubernetes (para deployment en producción)

## 🚀 Deployment

### Automático (GitHub Actions)
Los deployments se ejecutan automáticamente al hacer push a `main`. El sistema usa tags únicos basados en SHA para garantizar actualizaciones.

### Manual (Comandos directos)
Para deployments manuales, usa comandos transparentes de kubectl:

```bash
# Actualizar frontend
kubectl set image deployment/cuenly-frontend cuenly-frontend=ghcr.io/poravv/cuenly-app-frontend:latest -n cuenly-frontend
kubectl patch deployment cuenly-frontend -n cuenly-frontend -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}}}}"

# Actualizar backend  
kubectl set image deployment/cuenly-backend cuenly-backend=ghcr.io/poravv/cuenly-app-backend:latest -n cuenly-backend
kubectl patch deployment cuenly-backend -n cuenly-backend -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubectl.kubernetes.io/restartedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}}}}"
```

Ver [comandos de deployment manual](MANUAL_DEPLOYMENT_COMMANDS.md) para más opciones.
- Docker y Docker Compose (opcional, para despliegue)

## 🛠️ Instalación

### Usando Docker (recomendado)

1. Clona el repositorio:
   ```
   git clone https://github.com/tu-usuario/cuenlyapp.git
   cd cuenlyapp
   ```

2. Configura las variables de entorno en un archivo `.env` en la raíz del proyecto:
   ```
   EMAIL_HOST=imap.gmail.com
   EMAIL_PORT=993
   EMAIL_USERNAME=tu_correo@gmail.com
   EMAIL_PASSWORD=tu_contraseña_o_token
   OPENAI_API_KEY=tu_clave_api_openai
   ```

3. Inicia los contenedores:
   ```
   docker-compose up -d
   ```

4. Accede a la aplicación en `http://localhost:4200`

### Despliegue en Producción

1. Configura el archivo `.env` con tus variables de entorno de producción.

2. Utiliza el script de lanzamiento incluido:
   ```
   ./launch-production.sh
   ```
   
   O para reconstruir los contenedores:
   ```
   ./launch-production.sh --rebuild
   ```

3. Accede a la aplicación en `http://tu-servidor` (puerto 80)

### Instalación Manual

#### Backend

1. Navega al directorio del backend:
   ```
   cd cuenlyapp/backend
   ```

2. Crea un entorno virtual y actívalo:
   ```
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\\Scripts\\activate
   ```

3. Instala las dependencias:
   ```
   pip install -r requirements.txt
   ```

4. Instala los modelos de spaCy:
   ```
   python -m spacy download es_core_news_md
   python -m spacy download en_core_web_md
   ```

5. Configura las variables de entorno en el archivo `.env` en la carpeta `app`.

6. Inicia la aplicación:
   ```
   python start.py --mode=api
   ```

#### Frontend

1. Navega al directorio del frontend:
   ```
   cd cuenlyapp/frontend
   ```

2. Instala las dependencias:
   ```
   npm install
   ```

3. Inicia el servidor de desarrollo:
   ```
   npm start
   ```

4. Accede a la aplicación en `http://localhost:4200`

## 📊 Uso

### Modos de Operación

- **Modo API**: Inicia el servidor web y la API REST
  ```
  python start.py --mode=api
  ```

- **Modo Daemon**: Ejecuta el procesamiento continuo de correos
  ```
  python start.py --mode=daemon --interval=300
  ```

- **Modo CLI**: Ejecuta el procesamiento una sola vez
  ```
  python start.py --mode=single
  ```

### API REST

La API proporciona los siguientes endpoints:

- `GET /`: Verificación de estado de la API
- `POST /process`: Inicia el procesamiento de correos
- `POST /upload`: Sube un PDF para procesamiento manual
- `GET /excel`: Descarga el archivo Excel con las facturas procesadas
- `GET /status`: Obtiene el estado actual del sistema

## 👥 Contribución

Las contribuciones son bienvenidas. Por favor, envía un pull request para cualquier mejora.

## 📜 Licencia

Este proyecto está licenciado bajo la Licencia MIT. Consulta el archivo LICENSE para más detalles.

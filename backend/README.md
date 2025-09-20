# CuenlyApp - Backend

CuenlyApp es un sistema automatizado para la extracción de datos de facturas electrónicas paraguayas. El sistema monitorea una casilla de correo electrónico para detectar facturas en formato PDF/XML, extrae la información utilizando OpenAI (y parser nativo para XML SIFEN), y almacena los datos estructurados en MongoDB.

## Características

- **Monitoreo automático de email:** Revisa automáticamente una casilla de correo para buscar facturas.
- **Extracción de datos con IA:** Utiliza OpenAI Vision API para extraer datos precisos de los PDFs.
- **Procesamiento estructurado:** Extrae datos de forma estructurada incluyendo:
  - Información del emisor
  - Datos del cliente
  - Detalles de timbrado
  - Productos/servicios facturados
  - Totales e impuestos
- **Almacenamiento en MongoDB:** Guarda los documentos normalizados para consultas y análisis.
- **API RESTful:** Permite integrar con otros sistemas y ejecutar el procesamiento bajo demanda.
- **Procesamiento periódico:** Programación de tareas automáticas para revisar correos en intervalos configurables.
- **🛡️ Protección anti-cuelgues:** Sistema robusto con timeouts y retry automático para evitar bloqueos del servidor.

## 🔒 Características de Seguridad y Robustez

### Sistema de Timeouts Inteligentes
- **Conexiones IMAP:** Timeouts configurados para conectar (30s), autenticar (20s), buscar (15s) y obtener mensajes (20s)
- **Descargas HTTP:** Timeouts de conexión (5s) y lectura (15s) con retry automático
- **OpenAI API:** Timeout de 60s con retry exponential backoff
- **Procesamiento global:** Watchdog de 10 minutos para evitar cuelgues indefinidos

### Pool de Conexiones IMAP
- **Reutilización inteligente:** Reduce 70% del tiempo de conexión
- **Detección de conexiones muertas:** Limpieza automática de conexiones inválidas
- **Límite de conexiones:** Máximo 5 conexiones por configuración de email
- **Cleanup automático:** Cierre de conexiones inactivas cada 5 minutos

### Manejo de Errores Robusto
- **Errores fatales vs transitorios:** Diferenciación automática entre errores permanentes y temporales
- **Retry con backoff exponencial:** Reintentos inteligentes con delay creciente
- **Protección por thread:** Cada cuenta de email se procesa en thread separado con timeout
- **Logging detallado:** Registro completo de errores para debugging

## Tecnologías utilizadas

- **Python 3.9+**
- **FastAPI:** Framework web para la API.
- **OpenAI API:** Para el procesamiento de imágenes y extracción de datos.
- **PyMuPDF:** Convertir PDFs a imágenes para mejor procesamiento.
- **MongoDB (pymongo/motor):** Almacenamiento documental.
- **imaplib2:** Conexión a servidores de correo electrónico.

## Requisitos

- Python 3.9 o superior
- Una cuenta en OpenAI con acceso a la API Vision (GPT-4o o GPT-4-Vision)
- Acceso a un servidor de correo con IMAP habilitado

## Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/yourusername/cuenlyapp.git
   cd cuenlyapp/backend
   ```

2. **Crear y activar un entorno virtual:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   Copia el archivo `.env.example` a `.env` y configura las variables:
   ```bash
   cp .env.example .env
   ```
   Edita el archivo `.env` con tus propias credenciales.

5. **Crear directorios necesarios:**
   ```bash
   mkdir -p data/temp_pdfs
   ```

## Configuración

Variables de entorno principales (ver `.env`):

| Variable | Descripción |
|----------|-------------|
| MONGODB_URL | Cadena de conexión a MongoDB |
| MONGODB_DATABASE | Base de datos en MongoDB |
| MONGODB_COLLECTION | Colección para almacenar facturas |
| OPENAI_API_KEY | Clave API para OpenAI |
| TEMP_PDF_DIR | Directorio temporal para almacenar PDFs |
| LOG_LEVEL | Nivel de log (INFO, DEBUG, ERROR, etc.) |
| JOB_INTERVAL_MINUTES | Intervalo para el job automático (minutos) |
| API_HOST | Host del servidor API |
| API_PORT | Puerto del servidor API |

Nota: La configuración de cuentas de correo (host, puerto, usuario, contraseña, search_terms) se gestiona desde el frontend y se guarda en MongoDB (colección `email_configs`).

## Uso

### Iniciar el servidor API

```bash
python start.py
```

El servidor se iniciará en `http://API_HOST:API_PORT/` (por defecto `http://0.0.0.0:8000/`).

También puedes especificar el modo de ejecución:

```bash
# Ejecución única (procesa correos una vez y termina)
python start.py --mode=single

# Modo daemon (procesa correos periódicamente según intervalo)
python start.py --mode=daemon

# Modo API (inicia el servidor FastAPI)
python start.py --mode=api
```

### Endpoints disponibles

- **GET /health**: Verifica el estado del servicio
- **GET /docs**: Documentación interactiva de la API (Swagger UI)
- **POST /process**: Inicia manualmente el procesamiento de correos
- **POST /job/start**: Inicia el job programado para procesamiento periódico
- **POST /job/stop**: Detiene el job programado
- **GET /job/status**: Obtiene el estado del job programado

## Funcionamiento

1. El sistema monitorea una casilla de correo buscando correos con facturas electrónicas.
2. Al detectar un correo con un PDF adjunto:
   - Descarga el PDF
   - Convierte el PDF a imagen para mejor procesamiento
   - Envía la imagen a OpenAI Vision API con un prompt específico
   - Extrae datos estructurados de la respuesta
   - Almacena la información en un modelo de datos
3. Todos los datos extraídos se guardan en MongoDB y quedan disponibles vía endpoints de consulta.

## Modelo de datos

El sistema extrae y estructura los siguientes datos:

### Datos principales
- **Fecha:** Fecha de emisión de la factura
- **RUC Emisor:** RUC de la empresa emisora (con guión)
- **Nombre Emisor:** Razón social del emisor
- **Número Factura:** Número completo de la factura (ej: 001-001-0000001)
- **Condición Venta:** CONTADO o CRÉDITO
- **Moneda:** Tipo de moneda (PYG, USD, etc.)
- **Monto Total:** Importe total a pagar
- **IVA:** Suma total de IVA
- **Timbrado:** Número de timbrado
- **CDC:** Código de Control
- **RUC Cliente:** RUC del cliente (con guión)
- **Nombre Cliente:** Nombre o razón social del cliente
- **Email Cliente:** Correo electrónico del cliente

### Datos estructurados
- **Empresa:**
  - Nombre
  - RUC
  - Dirección
  - Teléfono
  - Actividad económica

- **Timbrado:**
  - Número
  - Fecha inicio vigencia
  - Fecha fin vigencia

- **Productos:**
  - Descripción
  - Cantidad
  - Precio unitario
  - Total

- **Totales:**
  - Cantidad de artículos
  - Subtotal
  - Total a pagar
  - IVA exentas
  - IVA 5%
  - IVA 10%
  - Total IVA

## Estructura del proyecto

```
backend/
├── app/                  # Código principal
│   ├── api/              # Endpoints de la API
│   ├── config/           # Configuraciones
│   ├── models/           # Modelos de datos
│   ├── modules/          # Módulos funcionales
│   │   ├── email_processor/      # Procesamiento de emails
│   │   ├── mongo_exporter.py     # Exportador a MongoDB
│   │   ├── openai_processor/     # Integración con OpenAI
│   ├── utils/            # Utilidades
├── data/                 # Datos generados
│   ├── temp_pdfs/        # Almacenamiento temporal de PDFs
├── tests/                # Tests unitarios
├── venv/                 # Entorno virtual (ignorado en git)
├── .env                  # Variables de entorno (ignorado en git)
├── .env.example          # Ejemplo de variables de entorno
├── .gitignore            # Archivos ignorados por git
├── README.md             # Este archivo
├── requirements.txt      # Dependencias
└── start.py              # Punto de entrada
```

## Modificación del procesamiento de facturas

El sistema puede ser adaptado para diferentes tipos de facturas ajustando los siguientes componentes:

1. **Prompt de OpenAI**: Modifica el prompt en `app/modules/openai_processor/openai_processor.py` para adaptarlo a otros formatos de factura.

2. **Modelo de datos**: Ajusta los modelos en `app/models/models.py` si necesitas campos adicionales o diferentes.

3. **Exportador MongoDB**: Ajusta `app/modules/mongo_exporter.py` para cambiar cómo se persiste la información.

## Contribuir

1. Haz un fork del repositorio
2. Crea una rama para tu funcionalidad (`git checkout -b feature/amazing-feature`)
3. Haz commit de tus cambios (`git commit -m 'Add some amazing feature'`)
4. Haz push a la rama (`git push origin feature/amazing-feature`)
5. Abre un Pull Request

## Solución de problemas

### Error al procesar PDFs
- Verifica que tu API key de OpenAI sea válida y tenga acceso a GPT-4o o GPT-4-Vision
- Comprueba que los PDFs sean legibles y no estén protegidos

### Problemas de persistencia en MongoDB
- Verifica la cadena de conexión (MONGODB_URL) y credenciales
- Confirma que el contenedor/servicio de MongoDB está saludable

## Licencia

Este proyecto está licenciado bajo [MIT License](LICENSE).

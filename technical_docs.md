# Documentación Técnica de Cuenly

Esta documentación detalla la arquitectura técnica, los flujos de datos y los componentes del sistema Cuenly.

## 1. Arquitectura General del Sistema

El sistema utiliza una arquitectura de microservicios contenerizada con Docker.

```mermaid
graph TD
    User["Usuario (Navegador)"] -->|HTTPS| Frontend["Frontend (Angular)"]
    Frontend -->|HTTP REST| Backend["Backend (FastAPI)"]
    
    subgraph "Backend Services"
        Backend -->|Persistencia| MongoDB[("MongoDB")]
        Backend -->|Cache & Colas| Redis[("Redis")]
        Backend -->|Object Storage| MinIO[("MinIO (S3)")]
        Backend -->|Procesamiento IA| OpenAI["OpenAI API (GPT-4o)"]
        
        Backend -->|Jobs Internos| SchedulerThread["ScheduledJobRunner (Threads)"]
        Backend -->|Jobs Pesados| AsyncJobWorker["AsyncJobManager (Threads)"]
    end
    
    subgraph "External Workers"
        Worker["RQ Worker"] -.->|Consume - Inactivo/Bajo uso| Redis
    end
    
    Backend -->|IMAP| EmailServers["Servidores de Correo (Gmail/Outlook)"]
```

### Componentes Principales

*   **Frontend**: Aplicación Angular servida vía Nginx/Node.
*   **Backend**: API RESTful construida con FastAPI (Python 3.11).
*   **MongoDB**: Base de datos principal (NoSQL) para usuarios, facturas y configuraciones.
*   **Redis**: Sistema de caché para respuestas de OpenAI y broker de mensajería para colas opcionales (RQ).
*   **MinIO**: Almacenamiento de objetos compatible con S3 para guardar copias de seguridad de facturas procesadas (Originales PDF/XML).
*   **Worker**: Servicio separado para procesamiento de tareas en cola (RQ), aunque parte de la carga actual se maneja vía hilos internos en el backend.

---

## 2. Flujos de Procesamiento de Documentos

El núcleo de Cuenly es la extracción de datos de facturas desde diversos formatos (Adjuntos o Enlaces).

### 2.0 Estrategia de Priorización de Archivos
El sistema analiza cada correo buscando facturas con la siguiente prioridad estricta para asegurar la máxima precisión al menor costo:

1.  **Adjuntos XML**: Máxima prioridad (Parser nativo, sin costo IA).
2.  **Adjuntos PDF**: Segunda prioridad (Visión IA).
3.  **Enlaces Externos**: Último recurso. Se descargan y analizan buscando XML o PDF.

### 2.1 Procesamiento de Imágenes, PDF y Enlaces

Los archivos (ya sean adjuntos o descargados de enlaces) se almacenan primero en MinIO antes de ser procesados.

```mermaid
sequenceDiagram
    participant Mail as Email Processor
    participant Down as Link Downloader
    participant MinIO as MinIO Storage
    participant Proc as OpenAIProcessor
    participant API as Backend/API

    Mail->>Mail: 1. Analizar Adjuntos (XML > PDF)
    alt Sin Adjuntos Válidos
        Mail->>Down: 2. Extraer y Descargar Enlaces
        Down->>Down: Detectar Content-Type (XML/PDF)
    end
    
    Mail->>MinIO: 3. Subir Archivo Original (Backup)
    MinIO-->>Mail: Retorna MinIO Key/URL
    
    Mail->>Proc: 4. extract_invoice_data(local_path)
    
    alt Es XML (Adjunto o Link)
        Proc->>Proc: Parser Nativo SIFEN
        opt Fallo Nativo
           Proc->>Proc: Fallback OpenAI GPT-4o
        end
    else Es PDF (Adjunto o Link)
        Proc->>Proc: Convertir a Imagen + OCR
        Proc->>Proc: OpenAI Vision (GPT-4o)
    end
    
    Proc-->>API: InvoiceData Normalizado
```

### 2.2 Procesamiento de XML (Facturación Electrónica)

El flujo de XML prioriza un parser nativo rápido y económico, usando IA solo como respaldo (fallback) si la estructura es compleja o faltan datos críticos.

```mermaid
flowchart TD
    A[Inicio: XML Path] --> B{Existe archivo?}
    B -- No --> C[Retornar None]
    B -- Si --> D[Leer Contenido]
    
    D --> E["Parser Nativo (xml_parser.py)"]
    E --> F{Es Válido?}
    
    F -- "Si (Estructura OK)" --> G["Extraer CDC de atributo Id"]
    G --> H[Validar CDC]
    H --> I["Retornar InvoiceData (Nativo)"]
    
    F -- "No (Faltan campos/Error)" --> J["Fallback: OpenAI GPT-4o"]
    J --> K[Prompt Especializado XML]
    K --> L[Llamada a API OpenAI]
    L --> M[Incrementar Contador IA]
    M --> N[Normalizar JSON]
    N --> O["Retornar InvoiceData (IA)"]
```

---

## 3. Sistema de Tareas y Scheduling

Actualmente coexisten tres mecanismos de ejecución de tareas para diferentes propósitos:

### 3.1 ScheduledJobRunner (Procesamiento de Correos)
Es el motor principal para la descarga periódica de correos. Corre en **hilos dentro del contenedor Backend**.

*   **Ubicación**: `app.modules.scheduler.job_runner`
*   **Función**: Ejecuta `process_all_emails` cada X minutos.
*   **Estado**: Controlado por `MultiEmailProcessor`.
*   **Persistencia**: En memoria (si se reinicia el backend, se reinicia el intervalo).
*   **Problema Conocido**: Requiere campo `ai_remaining` en `MultiEmailConfig` (Corregido en commit reciente).

### 3.2 AsyncJobManager (Tareas Pesadas / Históricas)
Maneja tareas largas solicitadas por el usuario (ej: "Sincronizar todo el año"). Usa MongoDB como cola de persistencia.

*   **Ubicación**: `app.modules.scheduler.async_jobs`
*   **Mecanismo**: 
    1.  API encola job en MongoDB (`jobs` collection).
    2.  Hilo `AsyncJobWorker` en Backend hace polling a MongoDB.
    3.  Ejecuta la tarea en background.
*   **Tipos de Jobs**: `full_sync`, `retry_skipped`.

### 3.3 RQ Worker (Redis Queue)
Infraestructura tradicional de workers separada. Actualmente disponible pero con uso secundario frente a los managers internos.

*   **Ubicación**: Contenedor `cuenly-worker`
*   **Colas**: `high`, `default`, `low`.
*   **Uso**: Diseñado para tareas desacopladas que pueden sobrevivir a reinicios del backend.

---

## 4. Comunicación Frontend - Backend

La comunicación se realiza mediante API REST estándar asegurada con Tokens (Firebase Auth).

```mermaid
sequenceDiagram
    participant Client as Navegador (Angular)
    participant Auth as Firebase Auth
    participant API as Backend API
    participant DB as MongoDB

    Client->>Auth: Login
    Auth-->>Client: JWT Token
    
    Note over Client, API: Requests subsecuentes llevan Bearer Token
    
    Client->>API: GET /dashboard/stats
    API->>API: Middleware: Verificar JWT
    API->>DB: Consultar Stats Usuario
    DB-->>API: Datos
    API-->>Client: JSON Response
```

## 5. Estructura de Datos Clave (MongoDB)

### Colecciones Principales
*   **`users`**: Perfiles, límites de IA, configuración de prueba (trial).
*   **`email_configs`**: Credenciales de correos (cifradas/OAuth tokens) vinculadas a usuarios.
*   **`processed_emails`**: Registro de UIDs de correos ya procesados para evitar duplicados.
*   **`invoices`**: Facturas extraídas y normalizadas (Header + Items).
*   **`jobs`**: Cola de tareas del `AsyncJobManager`.

## 6. Variables de Entorno Críticas

| Variable | Propósito |
| :--- | :--- |
| `OPENAI_API_KEY` | Acceso a modelos GPT-4o. |
| `MONGODB_URL` | Conexión a base de datos. |
| `REDIS_URL` | Conexión a Redis (Cache/Colas). |
| `ENCRYPTION_KEY` | Cifrado de contraseñas de correos almacenadas. |
| `MINIO_ENDPOINT` | URL del servicio MinIO (S3). |
| `MINIO_ACCESS_KEY` | Access Key para S3/MinIO. |
| `MINIO_SECRET_KEY` | Secret Key para S3/MinIO. |
| `MINIO_BUCKET` | Bucket donde se almacenan las facturas procesadas. |

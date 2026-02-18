# Documentación Técnica de Cuenly

Esta documentación detalla la arquitectura técnica, los flujos de datos y los componentes del sistema Cuenly.

## 1. Arquitectura General del Sistema

El sistema utiliza una arquitectura de microservicios contenerizada con Kubernetes en produccion y Docker en desarrollo.

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
        Worker["RQ Worker"] -->|Consume colas high/default/low| Redis
        KEDA["KEDA ScaledObject"] -->|Autoscaling| Worker
    end
    
    Backend -->|IMAP| EmailServers["Servidores de Correo (Gmail/Outlook)"]
```

### Componentes Principales

*   **Frontend**: Aplicación Angular servida vía Nginx/Node.
    *   **State Management**: Implementación inicial con **Akita** para gestión centralizada de sesión de usuario (`SessionStore`).
*   **Backend**: API RESTful construida con FastAPI (Python 3.11).
*   **MongoDB**: Base de datos principal (NoSQL) para usuarios, facturas y configuraciones.
*   **Redis**: Sistema de cache para respuestas de OpenAI y broker de mensajeria de colas RQ.
*   **MinIO**: Almacenamiento de objetos compatible con S3 para guardar copias de seguridad de facturas procesadas (Originales PDF/XML). Su acceso está restringido según el plan de suscripción.
*   **Worker**: Servicio separado para procesamiento de tareas en cola (RQ) desplegado como `Deployment` en Kubernetes.

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

## 2.3 Seguridad y Validación de Archivos

Para garantizar que no se procesen archivos maliciosos, se ha implementado una capa de validación estricta usando **Magic Numbers** (librería `libmagic` / `python-magic`).

*   **Validación Real**: No se confía en la extensión del archivo (`.pdf`, `.jpg`).
*   **Inspección Binaria**: Se leen los primeros bytes del archivo para determinar su verdadero tipo MIME.
*   **Rechazo**: Si un archivo dice ser `.pdf` pero sus bytes indican que es un ejecutable (`application/x-executable`) o script, es rechazado inmediatamente antes de guardarse en disco.

---

## 3. Sistema de Tareas y Scheduling

Actualmente coexisten tres mecanismos de ejecución de tareas para diferentes propósitos:

### 3.1 ScheduledJobRunner (Procesamiento de Correos)
Es el motor principal para la descarga periódica de correos. Corre en **hilos dentro del contenedor Backend**.

*   **Ubicación**: `app.modules.scheduler.job_runner`
*   **Función**: Ejecuta `process_all_emails` cada X minutos.
*   **Estado**: Controlado por `MultiEmailProcessor`.
*   **Persistencia**: En memoria (si se reinicia el backend, se reinicia el intervalo).

### 3.2 AsyncJobManager (Tareas Pesadas / Históricas)
Maneja tareas largas solicitadas por el usuario (ej: "Sincronizar todo el año"). Usa MongoDB como cola de persistencia.

*   **Ubicación**: `app.modules.scheduler.async_jobs`
*   **Mecanismo**: 
    1.  API encola job en MongoDB (`jobs` collection).
    2.  Hilo `AsyncJobWorker` en Backend hace polling a MongoDB.
    3.  Ejecuta la tarea en background.
*   **Tipos de Jobs**: `full_sync`, `retry_skipped`.

### 3.3 RQ Worker (Redis Queue)
Infraestructura de workers separada y activa en Kubernetes para procesamiento asincrono desacoplado.

*   **Ubicación**: Contenedor `cuenly-worker`
*   **Colas**: `high`, `default`, `low`.
*   **Autoscaling**: Gestionado por KEDA (`ScaledObject`) segun CPU y longitud de cola Redis.
*   **Uso**: Tareas desacopladas que deben continuar aunque el backend rote pods durante deploy.

### 3.4 DataRetentionJob (Purga de Originales)
Job diario para cumplir con políticas de privacidad y ahorro de costes.
*   **Ubicación**: `app.modules.scheduler.jobs.retention_job`
*   **Frecuencia**: Diaria (03:00 AM).
*   **Lógica**: Elimina archivos de MinIO con antigüedad > 1 año (según `retention_days` del plan). Mantiene la metadata en MongoDB pero libera espacio de almacenamiento físico.

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
| `REDIS_HOST` | Host de Redis. |
| `REDIS_PORT` | Puerto de Redis. |
| `REDIS_PASSWORD` | Password de Redis (si aplica). |
| `REDIS_DB` | Indice de base Redis. |
| `REDIS_SSL` | Activa conexion TLS a Redis. |
| `ENCRYPTION_KEY` | Cifrado de contraseñas de correos almacenadas. |
| `MINIO_ENDPOINT` | URL del servicio MinIO (S3). |
| `MINIO_ACCESS_KEY` | Access Key para S3/MinIO. |
| `MINIO_SECRET_KEY` | Secret Key para S3/MinIO. |
| `MINIO_BUCKET` | Bucket donde se almacenan las facturas procesadas. |

## 7. Rollout en Kubernetes

El pipeline de despliegue actualiza backend, worker y frontend con tags SHA, aplica anotaciones de reinicio y valida que los pods en estado `Running` tengan la imagen esperada.

```mermaid
sequenceDiagram
    participant CI as GitHub Actions
    participant K8S as Kubernetes
    participant BE as Deployment backend
    participant WK as Deployment worker
    participant FE as Deployment frontend

    CI->>BE: set image :sha-<short_sha>
    CI->>WK: set image :sha-<short_sha>
    CI->>FE: set image :sha-<short_sha>
    CI->>K8S: patch annotations restartedAt/forceUpdate/gitSha
    CI->>K8S: rollout status (backend/worker/frontend)
    CI->>K8S: verificar imagen esperada por pod
```

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
*   **Worker**: Servicio separado para procesamiento de tareas en cola (RQ), aunque parte de la carga actual se maneja vía hilos internos en el backend.

---

## 2. Flujos de Procesamiento de Documentos

El núcleo de Cuenly es la extracción de datos de facturas desde diversos formatos. Este procesamiento es orquestado por `OpenAIProcessor`.

### 2.1 Procesamiento de Imágenes y PDF

Los archivos PDF se renderizan primero como imágenes (primera página) para ser procesados por modelos de Visión.

```mermaid
sequenceDiagram
    participant API as API/Backend
    participant Proc as OpenAIProcessor
    participant Cache as Redis Cache
    participant Vision as OpenAI (GPT-4o)
    participant DB as MongoDB

    API->>Proc: extract_invoice_data(pdf_path)
    Proc->>Cache: get(pdf_path)
    alt Cache Hit
        Cache-->>Proc: JSON Factura
        Proc-->>API: Resultado Inmediato
    else Cache Miss
        Proc->>Proc: Convertir PDF a Imagen (Base64)
        Proc->>Proc: OCR Ligero (Opcional - Control "Nota Remisión")
        Proc->>Vision: Chat Completion (Imagen + Prompt V2)
        Vision-->>Proc: JSON Raw
        Proc->>Proc: Normalizar & Validar (CDC, Totales)
        Proc->>Cache: set(pdf_path, data)
        Proc->>DB: Incrementar Uso IA
        Proc-->>API: InvoiceData
    end
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

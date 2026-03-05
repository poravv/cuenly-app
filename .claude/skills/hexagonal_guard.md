# Hexagonal Guard — Backend Python/FastAPI

Esta skill se activa al trabajar en el directorio `backend/`.

## Mapa de Estructura

```
backend/app/
├── api/
│   ├── api.py                  # Router principal — registra todos los sub-routers
│   ├── deps.py                 # Dependencias FastAPI: get_current_user(), upsert_user()
│   └── endpoints/
│       ├── queues.py           # SSE stream + queue events
│       ├── subscriptions.py    # Subscribe, cancel, my-subscription
│       ├── pagopar.py          # Webhooks y flujos de pago
│       ├── user_profile.py     # Perfil del usuario
│       ├── admin_users.py      # CRUD usuarios (admin)
│       ├── admin_plans.py      # Gestión de planes (admin)
│       ├── admin_subscriptions.py
│       ├── admin_ai_limits.py  # Reset de cuota IA (admin)
│       ├── admin_scheduler.py  # Control del scheduler (admin)
│       └── admin_audit.py      # Logs de auditoría (admin)
├── config/
│   ├── settings.py             # ENV VARS — fuente de verdad de configuración
│   ├── export_config.py        # Config de exportación Excel
│   ├── security_config.py      # CORS, allowed origins
│   └── timeouts.py             # Timeouts centralizados
├── core/
│   ├── redis_client.py         # Singleton Redis
│   ├── exceptions.py           # Excepciones tipadas del dominio
│   ├── retry.py                # Lógica de reintentos
│   └── result.py               # Result pattern
├── models/                     # Pydantic v2 — dominio puro
│   ├── models.py               # InvoiceData (modelo principal de factura)
│   ├── invoice_v2.py           # Esquema v2 de facturas
│   ├── subscription_models.py  # Plan, Subscription, Transaction
│   ├── processed_email.py      # Registro de idempotencia
│   └── export_template.py      # Template de exportación
├── repositories/               # Acceso a MongoDB — ÚNICA capa permitida
│   ├── user_repository.py      # auth_users collection
│   ├── subscription_repository.py
│   ├── mongo_invoice_repository.py  # invoice_headers + invoice_items
│   ├── invoice_repository.py
│   ├── transaction_repository.py
│   ├── export_template_repository.py
│   ├── audit_repository.py
│   └── (processed_registry en email_processor)
├── services/                   # Integraciones externas
│   ├── pagopar_service.py      # API Pagopar (cobros recurrentes)
│   ├── email_notification_service.py  # SMTP notifications
│   └── webhook_service.py
├── modules/
│   ├── email_processor/        # Pipeline IMAP
│   │   ├── single_processor.py # Procesa 1 correo (core del pipeline)
│   │   ├── multi_processor.py  # Orquesta múltiples cuentas
│   │   ├── imap_client.py      # Conexión IMAP
│   │   ├── storage.py          # MinIO upload/download
│   │   ├── config_store.py     # CRUD email_configs (Fernet encryption)
│   │   └── downloader.py       # Descarga PDFs desde URLs
│   ├── openai_processor/       # Extracción IA
│   │   ├── processor.py        # Orquestador (quota check + dispatch)
│   │   ├── openai_processor.py # Llamada GPT-4o Vision
│   │   ├── xml_parser.py       # Parser SIFEN nativo (sin IA)
│   │   ├── prompts.py          # Prompts para GPT-4o
│   │   ├── invoice_factory.py  # Construye InvoiceData desde respuesta IA
│   │   ├── cache.py / redis_cache.py  # Cache de resultados
│   │   ├── image_utils.py      # Conversión PDF→imagen
│   │   ├── json_utils.py       # Parsing JSON de respuestas IA
│   │   ├── clients.py          # Cliente OpenAI
│   │   ├── config.py           # Config del procesador
│   │   ├── cdc.py              # CDC factura
│   │   └── pdf_text.py         # Extracción texto de PDF
│   ├── scheduler/              # Jobs y colas RQ
│   │   ├── task_queue.py       # Enqueue/dequeue de jobs
│   │   ├── async_jobs.py       # Definición de jobs async
│   │   ├── scheduler.py        # Scheduler periódico
│   │   ├── processing_lock.py  # Lock distribuido (Redis SETNX)
│   │   └── jobs/
│   │       └── subscription_billing_job.py  # Cobro mensual
│   ├── excel_exporter/
│   │   └── template_exporter.py  # Genera .xlsx
│   ├── mapping/
│   │   ├── invoice_mapping.py    # Mapeo campos SIFEN→interno
│   │   └── sifen_field_matrix.py # Matriz de campos SIFEN
│   ├── oauth/
│   │   └── google_oauth.py      # OAuth2 Gmail
│   ├── monitoring/
│   │   └── health_checker.py
│   ├── mongo_query_service.py    # Aggregations MongoDB complejas
│   ├── monthly_reset_service.py  # Reset mensual de cuotas
│   └── prefs/prefs.py
├── utils/
│   ├── firebase_auth.py        # Verificación JWT Firebase
│   ├── security.py             # Helpers de seguridad
│   ├── security_middleware.py
│   ├── trial_middleware.py     # Verificación de trial activo
│   ├── validators.py           # Validaciones de entrada
│   ├── date_utils.py
│   ├── metrics.py              # Prometheus metrics
│   ├── extended_metrics.py
│   └── observability.py
├── middleware/
│   └── observability_middleware.py
├── worker/
│   ├── jobs.py                 # Funciones que ejecuta el worker RQ
│   └── queues.py               # Definición de colas (high, default, low)
├── server.py                   # Arranque FastAPI + Uvicorn
└── main.py                     # CLI: --process, --start-job, --stop-job
```

## Reglas Obligatorias

### 1. Capas y dependencias
- **Endpoints** (`api/endpoints/`) solo llaman a **repositories** o **services**. Nunca importan `pymongo` ni acceden a colecciones directamente.
- **Repositories** (`repositories/`) son la ÚNICA capa que habla con MongoDB. Cada repository maneja una o pocas colecciones.
- **Models** (`models/`) son Pydantic v2 puros. No dependen de librerías externas excepto Pydantic. Usan `model_post_init()` para validaciones post-init.
- **Services** (`services/`) encapsulan integraciones externas (Pagopar, SMTP). No acceden a MongoDB directamente.
- **Modules** (`modules/`) contienen la lógica de negocio compleja (pipeline de procesamiento, scheduler, exportación).

### 2. Multi-tenancy
- **TODA** query a MongoDB DEBE filtrar por `owner_email` extraído del token Firebase.
- El `owner_email` se obtiene vía `deps.get_current_user()` en los endpoints.
- Nunca exponer datos de un tenant a otro. Verificar en repositories y en endpoints.

### 3. Logging
- Prohibido `print()`. Usar `logging.getLogger(__name__)`.
- Niveles: `debug` para flujo interno, `info` para operaciones completadas, `warning` para situaciones recuperables, `error` para fallos.

### 4. Idempotencia en procesamiento
- Antes de procesar un correo, verificar en `processed_emails` (índice único `owner_email + message_id`).
- `single_processor.py` es el punto de verificación principal.

### 5. Excepciones tipadas
- Usar las excepciones de `core/exceptions.py`: `OpenAIFatalError`, `OpenAIRetryableError`, `SkipEmailKeepUnread`, etc.
- No lanzar `Exception` genérica en lógica de negocio.

### 6. Configuración
- Toda variable configurable va en `config/settings.py` como env var con default.
- No hardcodear valores (URLs, emails, límites) fuera de settings.

### 7. Índices MongoDB
- Cada repository usa `_indexes_ensured: bool` class-level para crear índices solo 1 vez por proceso.
- Al agregar queries nuevas con filtros frecuentes, agregar índice correspondiente.

### 8. Jobs RQ
- Los jobs deben ser idempotentes y autocontenidos.
- Colas: `high` (cobros, admin), `default` (procesamiento normal), `low` (limpieza, stats).
- Lock distribuido via `processing_lock.py` (Redis SETNX + TTL).

### 9. Tipado
- Usar `typing` (Optional, List, Dict) en firmas de funciones.
- Pydantic v2 para modelos de entrada/salida en endpoints.
- Type hints en parámetros y retornos de funciones públicas.

### 10. Seguridad
- Credenciales IMAP cifradas con Fernet (prefijo `enc:v1:`). Ver `config_store.py`.
- OAuth tokens cifrados con misma clave (`EMAIL_CONFIG_ENCRYPTION_KEY`).
- Admin emails configurados via `settings.ADMIN_EMAILS`, nunca hardcodeados.
- Endpoints admin protegidos con verificación de rol en `deps.py`.

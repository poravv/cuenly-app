# CLAUDE.md — CuenlyApp — Contexto Permanente del Proyecto

> Este archivo es la fuente de verdad para Claude en cada sesión.
> Actualizar cuando cambien arquitectura, decisiones de diseño o convenciones.
> Última revisión: 2026-02-28

---

## 1. ¿Qué es CuenlyApp?

**CuenlyApp** es una plataforma de extracción y centralización automática de facturas electrónicas para empresas paraguayas. Procesa correos electrónicos de una o más cuentas IMAP para detectar, descargar y estructurar facturas en formato SIFEN (Sistema de Facturación Electrónica de la SET paraguaya), así como PDFs e imágenes vía OpenAI Vision.

**Objetivo central:** Eliminar la entrada manual de datos contables. Un usuario conecta sus correos, configura términos de búsqueda, y el sistema extrae todas sus facturas automáticamente a una base de datos centralizada que puede exportar en el formato que necesite.

---

## 2. Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | Angular 15.2.0 + Bootstrap 5 + RxJS + Akita |
| Backend | FastAPI (Python 3.11) + Uvicorn |
| Base de datos | MongoDB 7 |
| Cola de trabajos | RQ (Redis Queue) con 3 prioridades: high, default, low |
| Cache / Broker | Redis 7 |
| Almacenamiento de archivos | MinIO (S3-compatible, bucket: `bk-invoice`) |
| IA / Extracción | OpenAI GPT-4o (Vision para PDF/imagen) |
| Auth | Firebase Auth (Google OAuth) |
| Pagos | Pagopar (Bancard, tarjetas recurrentes) |
| Infra local | Docker Compose (`docker compose up -d --build`) |
| Infra producción | Kubernetes con KEDA autoscaling |
| Monitoreo | Prometheus + Grafana + Loki + AlertManager |

### Comandos esenciales de desarrollo local
```bash
# Levantar stack completo
docker compose up -d --build

# Stack dev aislado (puertos alternos: backend 8001, frontend 4300, mongo 27018, redis 6380)
docker compose --profile dev up -d --build mongodb-dev redis-dev backend-dev frontend-dev

# Ver logs
docker compose logs -f backend
docker compose logs -f worker

# Correr tests del backend
PYTHONPATH=backend python3 -m pytest backend/tests -q

# Build del frontend
npm --prefix frontend run build
```

---

## 3. Estructura de Directorios

```
cuenly/
├── backend/
│   ├── app/
│   │   ├── api/          # Endpoints FastAPI
│   │   │   └── endpoints/  # pagopar.py, subscriptions.py, admin_*.py, queues.py, user_profile.py
│   │   ├── config/       # settings.py (env-based), export_config.py, security_config.py, timeouts.py
│   │   ├── core/         # Redis client, exceptions, retry logic
│   │   ├── middleware/   # Observability middleware
│   │   ├── models/       # Pydantic: models.py (InvoiceData), subscription_models.py, processed_email.py
│   │   ├── modules/
│   │   │   ├── email_processor/   # imap_client.py, single_processor.py, multi_processor.py, storage.py
│   │   │   ├── openai_processor/  # processor.py (GPT-4o Vision)
│   │   │   ├── scheduler/         # task_queue.py, async_jobs.py, job_runners.py, job_handlers.py, processing_lock.py
│   │   │   └── oauth/             # OAuth2 para Gmail
│   │   ├── repositories/ # MongoDB access layer: subscription_repository.py, user_repository.py
│   │   ├── services/     # pagopar_service.py, webhooks
│   │   └── utils/        # auth, security, validators, metrics.py, extended_metrics.py
│   ├── worker.py         # Proceso RQ worker (colas: high, default, low)
│   ├── app/main.py       # CLI: --process, --start-job, --stop-job, --status
│   ├── app/server.py     # Arranque FastAPI
│   └── tests/            # 24 tests backend
├── frontend/
│   └── src/app/
│       ├── components/   # 26 componentes reutilizables
│       ├── modules/      # admin/ (AdminPanelComponent, PlansManagementComponent)
│       ├── services/     # api.service.ts (central HTTP), user.service.ts
│       ├── guards/       # AuthGuard, AdminGuard, LoginGuard, ProfileGuard
│       ├── interceptors/ # Error interceptor, Trial interceptor
│       ├── models/       # TypeScript interfaces
│       ├── state/        # Akita store (subutilizado)
│       └── styles/       # _variables.scss (design system)
├── docs/                 # Documentación técnica y planes
├── config/               # mongo-init.js, configs compartidas
├── data/                 # Datos locales (temp_pdfs, processed_emails)
├── docker-compose.yml    # Stack completo + perfil dev
├── k8s-monitoring/       # Prometheus, Grafana, Loki, AlertManager
├── k8s-security-improvements/
├── nginx/                # Proxy config para frontend prod
└── scripts/              # Migraciones, inicialización
```

---

## 4. Flujo de Procesamiento (Pipeline Central)

```
Usuario configura cuenta IMAP
         ↓
[3 modos de disparo]
  ① Procesar Correos → POST /process-direct  (hasta 50 no leídos)
  ② Activar Automatización → job recurrente cada 60 min (UNSEEN, fan-out)
  ③ Procesar Rango → POST /jobs/process-range  (fecha desde/hasta, leídos+no leídos)
         ↓
IMAP Discovery: escanea UIDs, filtra por subject/sender/adjunto
         ↓
Fan-out: cada correo → job RQ individual (colas: high/default/low)
         ↓
Worker procesa cada job:
  1. Descarga correo completo
  2. Detecta adjunto/link:
     a. .xml → Parser SIFEN nativo (rápido, sin IA)
     b. .pdf / imagen → OpenAI GPT-4o Vision (consume cuota de IA)
     c. Link .xml en body → descarga y parsea
     d. Coincidencia de términos config. → fallback search
  3. Sube archivo original a MinIO
  4. Guarda datos en MongoDB (invoice_headers + invoice_items)
  5. Registra en processed_emails (idempotencia, no reprocesa)
         ↓
Usuario exporta vía templates configurables → Excel (.xlsx)
```

### Idempotencia
- `processed_emails` collection: TTL 30 días, max 20,000 registros por usuario
- Índice único `(owner_email, message_id)` previene duplicados
- Si se borra el registro, el correo puede reprocesarse

---

## 5. Modelo de Suscripciones

| Plan | Precio/mes | Facturas/mes | Cuentas email | IA |
|------|-----------|-------------|--------------|-----|
| TRIAL | Gratis 15 días | 50 | 1 | 50 AI invoices |
| BASIC | 50,000 PYG | 200 | Según plan | Limitado |
| PRO | 150,000 PYG | 1,000 | Según plan | Limitado |
| PREMIUM | 300,000 PYG | Ilimitado | Ilimitado | Ilimitado |

- Registro con Google → TRIAL automático de 15 días
- Pago recurrente vía Pagopar (Bancard iframe)
- Reintentos automáticos: días 1, 3, 7 si falla el cobro
- Campos clave en `auth_users`: `trial_days`, `ai_invoices_limit`, `ai_invoices_processed`

---

## 6. Colecciones MongoDB (Principales)

| Colección | Propósito |
|-----------|-----------|
| `auth_users` | Usuarios, roles, info de trial y límites IA |
| `user_subscriptions` | Suscripción activa por usuario |
| `subscription_plans` | Definición de planes |
| `payment_methods` | Tarjetas tokenizadas (Pagopar) |
| `subscription_transactions` | Historial de cobros |
| `email_configs` | Config IMAP por usuario (search_terms, synonyms, oauth) |
| `invoice_headers` | Cabecera de facturas extraídas (esquema v2) |
| `invoice_items` | Ítems de línea por factura |
| `processed_emails` | Registro de idempotencia (TTL 30 días) |
| `export_templates` | Templates de exportación personalizados |

---

## 7. API Endpoints Clave

| Método | Ruta | Función |
|--------|------|---------|
| POST | `/process-direct` | Procesa hasta 50 correos no leídos (manual) |
| POST | `/jobs/process-range` | Procesa rango histórico por fecha |
| POST | `/user/queue-events/cancel-active` | Cancela todos los jobs activos |
| GET | `/tasks/{job_id}` | Estado de un job específico |
| GET | `/invoices` | Lista de facturas con paginación/filtros |
| GET | `/invoices/{id}/download` | URL firmada para descarga desde MinIO |
| POST | `/invoices/export` | Genera Excel con template seleccionado |
| GET | `/export-templates/available-fields` | Campos disponibles para exportar |
| GET/POST/PUT | `/email-configs` | CRUD de cuentas IMAP |
| POST | `/email-configs/test` | Valida credenciales IMAP |
| POST | `/subscriptions/subscribe` | Cambia de plan |
| POST | `/subscriptions/cancel` | Cancela suscripción |
| GET | `/my-subscription` | Info de suscripción actual |
| PATCH | `/admin/users/{id}` | Gestión de usuarios (admin) |
| GET | `/admin/metrics` | Métricas del sistema |

---

## 8. Rutas del Frontend (Angular)

| Ruta | Componente | Estado |
|------|-----------|--------|
| `/` | DashboardComponent | Funcional |
| `/facturas/todas` | InvoicesV2Component | Funcional |
| `/facturas/explorador` | InvoiceExplorerComponent | Parcial |
| `/facturas/estadisticas` | InvoicesStatsComponent | Funcional (falta calidad/origen) |
| `/facturas/subir` | UploadComponent | Funcional |
| `/facturas/subir-xml` | UploadXmlComponent | Funcional |
| `/facturas/exportar` | ExportTemplatesComponent | Funcional |
| `/automatizacion/procesamiento` | InvoiceProcessingComponent | Funcional |
| `/automatizacion/correos` | EmailConfigComponent | Funcional |
| `/automatizacion/cola` | QueueEventsComponent | **PROBLEMA: pestañea (polling 5s)** |
| `/cuenta/perfil` | ProfileComponent | Funcional |
| `/cuenta/suscripcion` | SubscriptionComponent | Funcional |
| `/cuenta/pagos` | PaymentMethodsComponent | Parcial |
| `/cuenta/ayuda` | HelpComponent | Minimal |
| `/admin` | AdminPanelComponent | **PROBLEMA: datos reales incompletos + diseño pobre** |
| `/admin/plans` | PlansManagementComponent | Funcional |
| `/pagopar/resultado/:hash` | PagoparResultComponent | Parcial |

---

## 9. Problemas Conocidos (Prioritarios)

### CRÍTICO - Seguridad
- ✅ **Contraseñas IMAP en plaintext**: RESUELTO — Implementado con Fernet encryption (prefijo `enc:v1:`) en `config_store.py` con retrocompatibilidad plaintext.
- ✅ **Email admin hardcodeado**: RESUELTO — Movido a `settings.ADMIN_EMAILS` env var con `andyvercha@gmail.com` como default permanente.
- ⚠️ **MD5 para ID de cliente Pagopar**: DESCARTADO — IDs ya almacenados en producción; cambiar rompería clientes existentes. No requiere cambio.
- ✅ **Tokens OAuth sin cifrar**: RESUELTO — Cifrados con Fernet, misma clave que IMAP (`EMAIL_CONFIG_ENCRYPTION_KEY`).

### CRÍTICO - UX
- ✅ **Cola de procesos pestañea**: RESUELTO — Eliminado auto-refresh de 5s. Implementado botón "Actualizar" manual con spinner propio. OnPush change detection + trackBy en *ngFor. Timestamp "Última actualización HH:mm:ss".
- ✅ **Panel de admin no muestra datos reales**: RESUELTO — Rediseñado a 4 tabs principales con sub-tabs. Datos reales desde MongoDB (usuarios, suscripciones, métricas, auditoría). Gráfico mensual con desglose XML nativo vs OpenAI Vision.

### ALTO - Funcionalidad
- ✅ **Estadísticas no muestran calidad/origen**: RESUELTO — Implementado en `invoices-stats.component.ts`. Pipeline MongoDB separa `xml_nativo` y `openai_vision` con % de procesamiento claro.
- ✅ **Límite de trial no se aplica consistentemente**: VERIFICADO — 3 niveles de verificación sin riesgo de bypass: `multi_processor` (permite XMLs), `single_processor` (bloquea PDFs), `openai_processor` (defensivo). Intención de diseño intacta.
- ✅ **Sin locking distribuido**: RESUELTO — Reemplazado `threading.Lock` por `_RedisDistributedLock` con SETNX+TTL=120s y fallback a threading.Lock si Redis no disponible. En `processing_lock.py`.
- ✅ **Pagopar flujos incompletos**: RESUELTO — Billing job con email notifications. Query incluye PAST_DUE. Reintentos días 1, 3, 7 implementados.
- ✅ **Suscripción de 15 días con Google**: VERIFICADO — Trial se crea automáticamente en `upsert_user()` tras primer login. No hay bypass.

### ALTO - Performance/Calidad
- ⬜ **Sin WebSockets**: PENDIENTE — SSE (Server-Sent Events) planificado para próxima fase. Actualmente polling HTTP reducido (botón manual en cola).
- ✅ **Sin `trackBy` en `*ngFor`**: RESUELTO — Agregado `trackBy` en todos los componentes críticos (admin-panel, queue-events, invoices-v2, etc.).
- ✅ **Sin OnPush change detection**: RESUELTO — Aplicado a componentes de alta frecuencia (queue-events, invoice-processing, etc.). `ChangeDetectorRef.markForCheck()` donde corresponda.
- ✅ **`print()` en código de producción**: RESUELTO — Reemplazados todos por `logging.getLogger(__name__)` en `task_queue.py` y `server.py`.
- ✅ **Sin índices DB**: RESUELTO — Agregados en todos los repositorios. Flag class-level `_indexes_ensured` evita crear_index redundantes por request.
- ✅ **Sin rate limiting**: RESUELTO — Implementado en 3 capas: K8s Ingress (100 RPS), Nginx ConfigMap (por endpoint), slowapi parcial en backend.

### MEDIO - Incompleto
- ✅ **Upload manual de adjuntos**: VERIFICADO — Flujo completo funciona (PDF/XML/imagen). Estados manejados correctamente en UI: error, límite IA, success. Endpoints: `/upload`, `/upload-xml`, `/file`.
- ✅ **Subida a MinIO condicionada por plan**: RESUELTO — Endpoint `/file` ahora verifica plan del usuario antes de permitir descarga. Usuarios sin premium no pueden acceder.
- ⚠️ **Explorador de facturas**: Pendiente revisión — `/facturas/explorador` (InvoiceExplorerComponent) búsqueda avanzada en estado parcial. Baja prioridad.
- ✅ **HelpComponent**: RESUELTO — Contiene 430 líneas con documentación sustancial sobre uso, troubleshooting y FAQs.

---

## 10. Integraciones Externas

### Pagopar (Bancard - Pagos recurrentes)
- Endpoint: `https://api.pagopar.com/api/pago-recurrente/3.0/`
- Token: `SHA1(PRIVATE_KEY + "PAGO-RECURRENTE")`
- Alias de tarjeta válido 15 minutos (pedir fresh antes de cada cobro)
- Archivo: `backend/app/services/pagopar_service.py`
- Flujo: agregar-cliente → agregar-tarjeta (iframe Bancard) → confirmar-tarjeta → cobro mensual vía cronjob

### OpenAI GPT-4o Vision
- Modelo configurable, default GPT-4o
- Temperature: 0.3, Max tokens: 1500, Timeout: 30s
- Cache Redis para evitar reprocesar mismo PDF
- Manejo de errores: `OpenAIFatalError` (key inválida/quota) y `OpenAIRetryableError` (timeout/rate limit)
- Archivo: `backend/app/modules/openai_processor/processor.py`

### MinIO (S3-compatible)
- Endpoint: `minpoint.mindtechpy.net`
- Bucket: `bk-invoice`
- Acceso condicionado por plan (descarga)
- Archivo: `backend/app/modules/email_processor/storage.py`

### Firebase Auth
- Google OAuth2 para login
- JWT tokens para backend API
- Frontend: Firebase SDK 10.13.1

---

## 11. Convenciones de Código

### Backend (Python/FastAPI)
- **Modelos**: Pydantic v2 con `model_post_init()` para validaciones post-init
- **Repositorios**: patrón Repository para todo acceso a MongoDB (NO acceso directo desde endpoints)
- **Logging**: usar `logging.getLogger(__name__)` — NO `print()`
- **Errores**: excepciones tipadas (`OpenAIFatalError`, `SkipEmailKeepUnread`, etc.)
- **Multi-tenancy**: siempre filtrar por `owner_email` en TODAS las queries
- **Jobs RQ**: idempotentes por diseño (verificar `processed_emails` antes de procesar)

### Frontend (Angular 15)
- **HTTP**: centralizar en `api.service.ts` — NO llamadas HTTP directas desde componentes
- **Estado**: Akita para estado global (actualmente subutilizado)
- **Polling**: usar `takeUntilDestroyed()` o `ngOnDestroy` para cleanup de intervalos
- **Tablas**: siempre usar `trackBy` en `*ngFor` con listas
- **Cambio de estado**: preferir `OnPush` en componentes con datos frecuentes

---

## 12. Variables de Entorno Críticas

```env
# Backend (.env en backend/)
OPENAI_API_KEY=
MONGODB_URL=mongodb://...
REDIS_HOST=
MINIO_ENDPOINT=
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
PAGOPAR_PUBLIC_KEY=
PAGOPAR_PRIVATE_KEY=
FIREBASE_PROJECT_ID=
FRONTEND_API_KEY=
EMAIL_CONFIG_ENCRYPTION_KEY=   # ← Vacío = contraseñas IMAP en plaintext (RIESGO)
ADMIN_EMAILS=                   # ← PENDIENTE: reemplazar hardcode en user_repository.py
JOB_INTERVAL_MINUTES=60
JOB_RESTORE_ON_BOOT=false
TRIAL_DAYS=15
TRIAL_AI_INVOICE_LIMIT=50
```

---

## 13. Checklist de Seguridad (Estado Actual)

| Item | Estado | Acción |
|------|--------|--------|
| Contraseñas IMAP cifradas | ✅ Fernet | Implementado con enc:v1: prefix + retrocompatibilidad plaintext |
| Admin email env-configurable | ✅ settings.ADMIN_EMAILS | Env var + default permanente |
| Rate limiting en API | ✅ K8s + Nginx + slowapi | Implementado en 3 capas (100 RPS, por endpoint, backend) |
| Índices DB completos | ✅ _indexes_ensured | Agregados en todos los repositorios, creados 1x por proceso |
| OAuth tokens cifrados | ✅ Fernet | Cifrados con EMAIL_CONFIG_ENCRYPTION_KEY |
| Audit log en admin ops | ✅ admin_audit_log | Collection + UI tab, todas las ops registradas |
| Input validation | ⚠️ Parcial | Pydantic v2 en modelos, validar endpoints públicos pending |
| HTTPS en producción | ✅ OK | TLS via Nginx Ingress |
| Multi-tenancy filtering | ✅ OK | `owner_email` en todas las queries |
| Secrets en variables de entorno | ✅ OK | No hay secrets en código fuente |

---

## 14. Flujo de Datos de Estadísticas (LO QUE FALTA)

El módulo de Estadísticas (`/facturas/estadisticas`) actualmente muestra:
- Total facturas, montos, IVA por mes
- Proveedores y clientes únicos

**Falta mostrar:**
- % de facturas procesadas por XML nativo vs OpenAI Vision (calidad/origen)
- Estadísticas de errores y reintentos
- Tiempo promedio de procesamiento
- Correos sin adjunto vs con adjunto válido
- Correos en estado `skipped_ai_limit` (encolados por límite IA)

Estos datos existen en `invoice_headers.processing_method` y `processed_emails.status`.

---

## 15. Estado del Panel de Admin

**Problemas actuales:**
- Algunas métricas del tab "Stats" no reflejan datos reales
- El diseño es básico/inconsistente con el resto de la app
- Falta: gráficos de uso por usuario, consumo de IA por tenant, estado de colas
- Las operaciones de reset de límites de IA están implementadas pero poco visibles

**Lo que sí funciona:**
- CRUD de usuarios (activar/suspender/cambiar rol)
- Gestión de planes (`/admin/plans`)
- Reset de estadísticas de IA
- Control del scheduler (iniciar/detener jobs)
- Gestión de suscripciones

---

## 16. Notas de Despliegue

### Local (Docker Compose)
```bash
docker compose up -d --build
# Frontend: http://localhost:4200
# Backend: http://localhost:4200/api (proxy vía nginx)
# MongoDB: localhost:27017
# Redis: localhost:6379
```

### Producción (Kubernetes)
- Deploy automático vía GitHub Actions (`cuenly-deploy.yml`)
- Imágenes en GHCR: `ghcr.io/poravv/cuenly-app-backend`
- KEDA autoscaling basado en jobs RQ pendientes
- Actualización manual: `kubectl set image deployment/cuenly-backend cuenly-backend=ghcr.io/poravv/cuenly-app-backend:sha-{SHORT_SHA}`
- Monitoreo: Prometheus (k8s-monitoring/) + Grafana + Loki (5GB PVC, 30 días)

---

## 17. Referencia Rápida de Archivos Críticos

| Archivo | Propósito |
|---------|-----------|
| `backend/app/config/settings.py` | Todas las variables de entorno y valores por defecto |
| `backend/app/repositories/user_repository.py` | **Tiene email admin hardcodeado (línea ~42)** |
| `backend/app/modules/email_processor/single_processor.py` | Lógica principal de procesamiento de un correo |
| `backend/app/modules/email_processor/multi_processor.py` | Orquestación multi-cuenta |
| `backend/app/modules/openai_processor/processor.py` | Extracción vía GPT-4o Vision |
| `backend/app/modules/scheduler/task_queue.py` | **Tiene print() en producción, usar logging** |
| `backend/app/services/pagopar_service.py` | Integración de pagos Pagopar |
| `frontend/src/app/components/queue-events/queue-events.component.ts` | **Polling 5s que pestañea** |
| `frontend/src/app/components/invoice-processing/invoice-processing.component.ts` | Auto-refresh 30s |
| `frontend/src/app/services/api.service.ts` | Todas las llamadas HTTP del frontend |
| `frontend/src/styles/_variables.scss` | Design system (colores, tipografía, espaciado) |
| `docs/PLAN-OPTIMIZACION.md` | Plan completo de mejoras priorizado |

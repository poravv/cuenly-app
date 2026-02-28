# CLAUDE.md — CuenlyApp — Contexto Permanente del Proyecto

> Este archivo es la fuente de verdad para Claude en cada sesión.
> Actualizar cuando cambien arquitectura, decisiones de diseño o convenciones.
> Última revisión: 2026-02-27

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
- **Contraseñas IMAP en plaintext en MongoDB** (`config_store.py`): `EMAIL_CONFIG_ENCRYPTION_KEY` existe en settings pero su implementación no está completa en todos los paths.
- **Email admin hardcodeado**: `andyvercha@gmail.com` en `user_repository.py:42`. Mover a env var `ADMIN_EMAILS`.
- **MD5 para ID de cliente Pagopar**: usar UUID o SHA-256 con salt.
- **Tokens OAuth sin cifrar** en MongoDB.

### CRÍTICO - UX
- **Cola de procesos pestañea**: `queue-events.component.ts` hace polling cada 5 segundos forzando re-render completo de la tabla. Solución: botón "Actualizar" manual + WebSocket o Server-Sent Events.
- **Panel de admin no muestra datos reales** en algunas métricas + diseño deficiente.

### ALTO - Funcionalidad
- **Estadísticas no muestran calidad/origen de procesamiento**: la distinción XML nativo vs OpenAI Vision no se proyecta claramente en `/facturas/estadisticas`.
- **Límite de trial no se aplica consistentemente**: `multi_processor.py` deja pasar usuarios con AI limit = 0 para que `single_processor` verifique; riesgo de bypass.
- **Sin locking distribuido**: `PROCESSING_LOCK` es un `threading.Lock` local, rompe con múltiples pods en Kubernetes.
- **Pagopar puede tener flujos incompletos**: revisar estados PAST_DUE y reintentos fallidos.
- **Suscripción de 15 días con Google no siempre activa**: verificar flujo completo de onboarding con Google OAuth.

### ALTO - Performance/Calidad
- **Sin WebSockets**: todo es polling HTTP (5s en cola, 30s en procesamiento). CPU innecesario.
- **Sin `trackBy` en `*ngFor`** en múltiples componentes → reconciliación innecesaria del DOM.
- **Sin OnPush change detection** en componentes de alta frecuencia.
- **`print()` en código de producción** en `task_queue.py`: usar logging estructurado.
- **Sin índices DB** en todos los campos de consulta frecuente.
- **Sin rate limiting** en endpoints públicos.

### MEDIO - Incompleto
- **Upload manual de adjuntos** (PDF/XML/imagen): flujo existe, verificar que todos los estados (error, límite IA, success) se manejen correctamente en UI.
- **Subida a MinIO condicionada por plan**: verificar que usuarios sin plan premium no puedan descargar archivos.
- **Explorador de facturas** (`/facturas/explorador`): búsqueda avanzada potencialmente incompleta.
- **HelpComponent**: prácticamente vacío.

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
| Contraseñas IMAP cifradas | ⚠️ Parcial | Completar implementación de Fernet |
| Admin email env-configurable | ❌ Hardcoded | Mover a `ADMIN_EMAILS` env var |
| Rate limiting en API | ❌ Ausente | Implementar con slowapi o nginx |
| Índices DB completos | ⚠️ Parcial | Auditar y agregar indexes |
| OAuth tokens cifrados | ❌ Plaintext | Cifrar con `EMAIL_CONFIG_ENCRYPTION_KEY` |
| Audit log en admin ops | ⚠️ Parcial | Completar para todas las ops destructivas |
| Input validation | ⚠️ Parcial | Validar todos los endpoints |
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

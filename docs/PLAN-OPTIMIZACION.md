# Plan de Optimización — CuenlyApp

> Generado: 2026-02-27 | Última actualización: 2026-02-28
> Basado en: auditoría completa de docs/, backend/ y frontend/
> Ver también: `CLAUDE.md` en la raíz del proyecto para contexto técnico completo.

---

## Resumen Ejecutivo

CuenlyApp tiene una arquitectura sólida y un flujo de procesamiento bien pensado. Sin embargo, hay problemas concretos que degradan la experiencia del usuario y representan riesgos de seguridad y escalabilidad. Este plan los organiza por impacto real, no por complejidad técnica.

**Criterios de prioridad:**
- 🔴 **CRÍTICO**: Seguridad comprometida o funcionalidad rota para el usuario
- 🟠 **ALTO**: Experiencia de usuario significativamente afectada o riesgo operacional
- 🟡 **MEDIO**: Mejora importante pero no urgente
- 🟢 **BAJO**: Refinamiento y deuda técnica

---

## FASE 1 — Correcciones Críticas (Hacer YA)

### ✅ 1.1 Cola de procesos: eliminar el parpadeo

**Problema:** `queue-events.component.ts` usa `interval(5000)` que hace polling cada 5 segundos y re-renderiza toda la tabla. El usuario no puede leer los datos sin que la pantalla pestañee.

**Solución inmediata (sin WebSockets):**
1. Eliminar el auto-refresh automático.
2. Agregar botón "Actualizar" prominente (ya existe pero no es el control principal).
3. Mostrar indicador de "última actualización hace X segundos".
4. Usar `trackBy: trackByJobId` en el `*ngFor` de la tabla para que Angular no destruya y reconstruya filas existentes.

```typescript
// queue-events.component.ts
// ELIMINAR esto:
private startAutoRefresh(): void {
  this.autoRefreshSub = interval(this.autoRefreshMs).subscribe(() => { ... });
}

// AGREGAR en el template:
// <button (click)="loadEvents()">Actualizar</button>
// <small>Última actualización: {{ lastRefresh | date:'HH:mm:ss' }}</small>

// En el *ngFor:
trackByJobId(index: number, item: QueueEvent): string {
  return item.job_id || String(index);
}
```

**Solución definitiva (siguiente sprint):** Implementar Server-Sent Events (SSE) en el backend para que el servidor notifique cambios en tiempo real sin polling.

---

### ✅ 1.2 Email admin hardcodeado

**Problema:** `backend/app/repositories/user_repository.py` línea ~42 tiene `email == 'andyvercha@gmail.com'` hardcodeado.

**Solución:**
```python
# settings.py — agregar:
ADMIN_EMAILS: List[str] = json.loads(os.getenv("ADMIN_EMAILS", '["andyvercha@gmail.com"]'))

# user_repository.py — reemplazar hardcode por:
from app.config.settings import get_settings
settings = get_settings()
is_admin = email in settings.ADMIN_EMAILS
```

**Riesgo si no se hace:** Requiere un deploy para cambiar el admin. Si la cuenta se compromete, no hay forma de revocar sin código.

---

### ✅ 1.3 Contraseñas IMAP en plaintext (YA ESTABA IMPLEMENTADO)

**Problema:** Las contraseñas de cuentas IMAP se guardan en MongoDB sin cifrar. `EMAIL_CONFIG_ENCRYPTION_KEY` existe en settings pero no está completamente implementado en todos los paths de guardado y lectura.

**Solución:**
1. Verificar que `config_store.py` usa Fernet para cifrar ANTES de guardar y descifrar DESPUÉS de leer.
2. Verificar que todos los paths que guardan `email_configs` pasan por el mismo encriptador.
3. Migrar registros existentes (script de migración one-shot).
4. Documentar que `EMAIL_CONFIG_ENCRYPTION_KEY` es OBLIGATORIO en producción.

```python
# Patrón a verificar en config_store.py:
from cryptography.fernet import Fernet

def encrypt_password(password: str, key: str) -> str:
    if not key:
        return password  # Sin clave = sin cifrado (solo dev)
    f = Fernet(key.encode())
    return f.encrypt(password.encode()).decode()

def decrypt_password(encrypted: str, key: str) -> str:
    if not key:
        return encrypted
    f = Fernet(key.encode())
    return f.decrypt(encrypted.encode()).decode()
```

---

### ✅ 1.4 Tokens OAuth sin cifrar (YA ESTABA IMPLEMENTADO)

**Verificado:** config_store.py usa Fernet con prefijo `enc:v1:` para cifrar tanto contraseñas IMAP como tokens OAuth. Retrocompatibilidad con plaintext existente.

---

### ✅ 1.5 print() en código de producción

**Problema:** `task_queue.py` tiene múltiples `print()` en código de threading crítico.

**Solución:** Reemplazar todos los `print()` por `logger = logging.getLogger(__name__)` y las llamadas apropiadas (`logger.debug()`, `logger.info()`, `logger.warning()`).

---

## FASE 2 — Problemas de Usuario de Alto Impacto

### ✅ 2.1 Panel de Admin: datos reales + rediseño

**Problemas:**
- Algunas métricas del tab "Stats" no muestran datos reales del sistema
- Diseño inconsistente con el resto de la app
- Falta visibilidad de: consumo de IA por usuario, estado de colas en tiempo real, revenue mensual real

**Plan de acción:**

**A. Conectar métricas reales:**
- `GET /admin/metrics` debe retornar: usuarios activos últimos 30 días, facturas procesadas hoy/semana/mes, distribución XML vs IA, top 10 usuarios por consumo IA, revenue por plan
- Verificar que los contadores de MongoDB se calculan correctamente

**B. Rediseñar el dashboard de admin:**
```
┌─────────────────────────────────────────────────────┐
│  Panel Admin                            [Actualizar] │
├──────────┬──────────┬──────────┬────────────────────┤
│ Usuarios │Facturas  │ Revenue  │   Colas RQ          │
│ activos  │ hoy      │ este mes │   (pendientes/proc) │
│   142    │  1,847   │ 2.1M PYG │   23 / 4            │
├──────────┴──────────┴──────────┴────────────────────┤
│  [Usuarios] [IA Limits] [Suscripciones] [Scheduler] │
└─────────────────────────────────────────────────────┘
```

**C. Agregar:**
- Gráfico de facturas por día (últimos 30 días) — usar Chart.js ya instalado
- Tabla de consumo IA por usuario (ordenado por mayor consumo)
- Estado en tiempo real de las colas RQ (jobs pendientes, en proceso, fallidos)
- Acceso rápido a reset de límites sin navegar a tab separado

---

### ✅ 2.2 Estadísticas: calidad y origen del procesamiento (YA ESTABA IMPLEMENTADO)

**Problema:** `/facturas/estadisticas` no muestra de dónde vienen los datos (XML nativo vs OpenAI Vision) ni la calidad del procesamiento.

**Datos que ya existen en MongoDB:**
- `invoice_headers.processing_method` (si existe): `"xml_native"` | `"openai_vision"`
- `processed_emails.status`: `"completed"` | `"failed"` | `"skipped_ai_limit"` | `"error"`

**Endpoint nuevo o extender el existente:**
```python
# GET /invoices/month/{yearMonth}/stats — agregar campos:
{
  "by_processing_method": {
    "xml_native": 234,
    "openai_vision": 89,
    "unknown": 5
  },
  "by_status": {
    "completed": 318,
    "failed": 8,
    "skipped_ai_limit": 2
  },
  "quality_score": 97.5  # % de facturas sin error
}
```

**Frontend:** Agregar sección "Origen y Calidad" en InvoicesStatsComponent con:
- Gráfico de dona: XML nativo vs IA vs Desconocido
- Tasa de éxito del procesamiento
- Facturas pendientes de reprocesar

---

### ✅ 2.3 Verificar y completar flujo completo de Pagopar

**Problema declarado por el usuario:** "no sé qué tanto le llegue a faltar"

**Puntos a verificar exhaustivamente:**
1. Flujo completo: registro → tarjeta → confirmación → cobro recurrente
2. Estado `PAST_DUE`: ¿se notifica al usuario? ¿se bloquea acceso?
3. Reintentos en días 1, 3, 7: ¿están implementados como cronjob RQ?
4. Cancelación: ¿elimina la tarjeta en Pagopar o solo en DB?
5. `PagoparResultComponent` (`/pagopar/resultado/:hash`): ¿maneja todos los estados?
6. ¿Qué pasa si el job de cobro recurrente falla silenciosamente?

**Acción:** Crear un test end-to-end con las tarjetas sandbox de Pagopar documentadas en `docs/pagopar-integration.md`.

**Sandbox:**
- Visa (uPay): `4111 1111 1111 1111`
- Mastercard: `5100 0000 0000 0000`

---

### ✅ 2.4 Límite de IA: aplicación consistente (VERIFICADO — NO HAY BYPASS)

**Problema:** El bypass en `multi_processor.py` deja pasar correos de usuarios con AI limit = 0 hacia `single_processor`, que puede consumir cuota silenciosamente.

**Fix backend:**
```python
# multi_processor.py — verificar que el check es estricto:
if user.ai_invoices_processed >= user.ai_invoices_limit and not has_xml_candidates:
    raise AILimitReachedError(f"Usuario {user_email} alcanzó límite IA")
    # No pasar al single_processor si no hay candidatos XML
```

**Fix frontend:** En el Dashboard y en `/cuenta/suscripcion`, mostrar prominentemente:
- Barra de progreso: "X de Y facturas IA usadas"
- Alerta cuando llega al 80% y al 100%
- Botón "Upgrade" destacado cuando se agota el límite

---

### ✅ 2.5 Suscripción de 15 días: verificar flujo completo con Google

**Problema declarado:** "Inicialmente cuando alguien se registra con Google se le da una suscripción de 15 días" — verificar que esto realmente ocurre.

**Flujo esperado:**
1. Usuario hace login con Google → Firebase Auth
2. Backend recibe JWT de Firebase → verifica si es usuario nuevo
3. Si es nuevo → crear documento en `auth_users` con `trial_start: now()`, `trial_days: 15`, `ai_invoices_limit: 50`
4. Crear registro en `user_subscriptions` con plan TRIAL activo
5. Frontend muestra el período de prueba y sus límites en `/cuenta/suscripcion`

**Verificar:** Si el backend tiene un endpoint o middleware que detecta "primer login" y aplica el trial. Si no existe, está roto.

---

## FASE 3 — Performance y Calidad del Código

### ✅ 3.1 Locking distribuido para Kubernetes

**Problema:** `PROCESSING_LOCK` es un `threading.Lock` en memoria. Con múltiples pods en Kubernetes, dos pods pueden procesar el mismo correo simultáneamente.

**Solución:** Redis-based distributed lock:
```python
# backend/app/core/distributed_lock.py
import redis
from contextlib import contextmanager

@contextmanager
def distributed_lock(redis_client, key: str, timeout: int = 30):
    lock_key = f"lock:{key}"
    acquired = redis_client.set(lock_key, "1", nx=True, ex=timeout)
    try:
        if acquired:
            yield True
        else:
            yield False
    finally:
        if acquired:
            redis_client.delete(lock_key)
```

---

### ✅ 3.2 Rate limiting en endpoints críticos (YA EXISTE)

**Problema:** No hay protección contra abuso en endpoints de procesamiento y admin.

**Solución:** Agregar `slowapi` (rate limiter para FastAPI):
```python
# app/api/api.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# En endpoints:
@router.post("/process-direct")
@limiter.limit("10/minute")  # 10 solicitudes por minuto
async def process_direct(...):
```

---

### ✅ 3.3 Frontend: OnPush + trackBy en componentes críticos

**Componentes a actualizar:**
1. `queue-events.component.ts` — `changeDetection: ChangeDetectionStrategy.OnPush` + `trackBy`
2. `invoices-v2.component.ts` — `trackBy` en la lista de facturas
3. `admin-panel.component.ts` — cachear datos entre tabs

```typescript
// Ejemplo para queue-events
@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QueueEventsComponent {
  trackByJobId = (_: number, item: QueueEvent) => item.job_id;
}
```

---

### ✅ 3.4 Índices MongoDB faltantes

**Agregar índices para consultas frecuentes:**
```javascript
// invoice_headers
db.invoice_headers.createIndex({ owner_email: 1, created_at: -1 })
db.invoice_headers.createIndex({ owner_email: 1, processing_method: 1 })

// processed_emails
db.processed_emails.createIndex({ owner_email: 1, status: 1 })
db.processed_emails.createIndex({ message_id: 1 }, { unique: true })

// user_subscriptions
db.user_subscriptions.createIndex({ owner_email: 1, status: 1 })
db.user_subscriptions.createIndex({ next_billing_date: 1, status: 1 })  // Para cronjob de cobros
```

---

### ✅ 3.5 Cleanup de código legacy

**Items a limpiar:**
1. Exporters comentados en código pero nunca eliminados
2. Múltiples estrategias de fallback de processing duplicadas
3. Rutas de redireccionamiento legacy en Angular (10+ redirects a rutas antiguas)
4. Colección `invoice_data` legacy vs `invoice_headers` v2 — confirmar que solo se usa v2
5. Dependencias no usadas en `requirements.txt` (múltiples extractores PDF: pdfplumber, pdfminer, PyPDF2, PyMuPDF — ¿cuál se usa realmente?)

---

### ✅ 3.6 Audit logging completo en operaciones admin

**Problema:** Cambios críticos (suspender usuario, cambiar plan, reset AI limits) no tienen audit trail completo.

**Solución:** Crear colección `admin_audit_log`:
```python
# Estructura:
{
  "timestamp": datetime,
  "admin_email": str,
  "action": str,  # "suspend_user", "change_plan", "reset_ai_limit"
  "target_user": str,
  "details": dict,
  "ip_address": str
}
```

---

## FASE 4 — Completar Funcionalidades Faltantes

### ✅ 4.1 Upload manual: verificar todos los flujos (VERIFICADO — CORRECTO)

**El usuario declaró que existe:** Subida manual de PDF, XML e imágenes.

**Verificar que funcionan correctamente:**
- [ ] PDF upload → OpenAI Vision → invoice_headers
- [ ] XML upload → Parser SIFEN nativo → invoice_headers
- [ ] Imagen upload → OpenAI Vision → invoice_headers
- [ ] Límite de IA se descuenta correctamente al subir
- [ ] Archivo se sube a MinIO después de procesar
- [ ] Error handling: ¿qué pasa si la IA falla? ¿se muestra el error?
- [ ] Plan check: ¿usuarios trial pueden subir?

---

### ✅ 4.2 Descarga desde MinIO condicionada por plan

**Problema declarado:** "de acuerdo al plan lo pueden descargar o no"

**Verificar implementación:**
1. Endpoint `GET /invoices/{id}/download` → ¿verifica plan antes de generar URL firmada?
2. Frontend → ¿deshabilita botón de descarga para planes sin acceso?
3. URL firmada → ¿tiene TTL apropiado (15-30 minutos)?

---

### ✅ 4.3 Página de Ayuda (/cuenta/ayuda) (YA TENÍA CONTENIDO)

**Estado actual:** Mínima o vacía.

**Contenido propuesto:**
- Guía de inicio rápido (conectar primer correo, procesar primeras facturas, exportar)
- FAQ: ¿Por qué no se procesan mis correos? ¿Qué es el límite de IA?
- Guía de configuración de búsqueda (términos, sinónimos, fallbacks)
- Videos embed de demo (si existen)
- Contacto de soporte

---

### 4.4 🟡 Server-Sent Events (SSE) para cola en tiempo real

**Objetivo:** Reemplazar el polling de 5s en la cola de procesos con actualizaciones push del servidor.

**Backend — agregar endpoint SSE:**
```python
from sse_starlette.sse import EventSourceResponse

@router.get("/queue/stream")
async def queue_stream(request: Request, current_user = Depends(get_current_user)):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            events = await get_recent_queue_events(current_user.email)
            yield {"data": json.dumps(events)}
            await asyncio.sleep(3)
    return EventSourceResponse(event_generator())
```

**Frontend — usar `EventSource` en lugar de `interval()`:**
```typescript
// queue-events.component.ts
const source = new EventSource(`/api/queue/stream?token=${token}`);
source.onmessage = (event) => {
  this.events = JSON.parse(event.data);
  this.cdr.markForCheck();
};
```

---

## FASE 5 — Infraestructura y Observabilidad

### 5.1 🟢 Completar Prometheus metrics

**Métricas faltantes importantes:**
```python
# Agregar en app/utils/extended_metrics.py:
EMAILS_PROCESSED_TOTAL = Counter('emails_processed_total', 'Emails procesados', ['method', 'status'])
OPENAI_COST_GAUGE = Gauge('openai_estimated_cost_usd', 'Costo estimado OpenAI en USD')
QUEUE_DEPTH = Gauge('rq_queue_depth', 'Jobs en cola RQ', ['queue_name'])
AI_LIMIT_HITS = Counter('ai_limit_hits_total', 'Veces que se alcanzó límite IA por usuario', ['user'])
```

---

### 5.2 🟢 Backup y recuperación de MongoDB

**Problema documentado:** No hay procedimientos de backup/restore documentados.

**Solución mínima:**
```bash
# Script de backup (agregar a scripts/backup-mongodb.sh):
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
mongodump --uri="$MONGODB_URL" --out="/backups/mongodb_$DATE"
# Upload a MinIO u S3
```

**Configurar:** CronJob de Kubernetes o cron en servidor para backup diario.

---

### 5.3 🟢 Documentar proceso de disaster recovery

- Qué hacer si MongoDB se corrompe
- Cómo restaurar desde backup de MinIO
- Cómo reiniciar el stack completo desde cero con datos existentes
- Runbook para incidentes de producción

---

## Tabla Resumen de Prioridades

| # | Problema | Impacto | Esfuerzo | Fase | Estado |
|---|----------|---------|---------|------|--------|
| 1 | Cola de procesos pestañea | Usuario bloqueado | Bajo | 1 | ✅ |
| 2 | Admin email hardcodeado | Seguridad crítica | Bajo | 1 | ✅ |
| 3 | Contraseñas IMAP plaintext | Seguridad crítica | Medio | 1 | ✅ Ya existía |
| 4 | Tokens OAuth plaintext | Seguridad alta | Medio | 1 | ✅ Ya existía |
| 5 | print() en producción | Calidad código | Bajo | 1 | ✅ |
| 6 | Panel admin: datos reales + diseño | UX admin | Alto | 2 | ✅ |
| 7 | Estadísticas: calidad y origen | Visibilidad negocio | Medio | 2 | ✅ Ya existía |
| 8 | Verificar Pagopar completo | Facturación/ingresos | Medio-Alto | 2 | ✅ |
| 9 | Límite IA: bypass y visibilidad | Integridad datos | Medio | 2 | ✅ Verificado |
| 10 | Trial con Google: flujo completo | Onboarding | Medio | 2 | ✅ Verificado |
| 11 | Locking distribuido (K8s) | Escalabilidad | Medio | 3 | ✅ |
| 12 | Rate limiting en API | Seguridad | Bajo | 3 | ✅ Ya existía |
| 13 | OnPush + trackBy en frontend | Performance frontend | Bajo | 3 | ✅ |
| 14 | Índices MongoDB faltantes | Performance DB | Bajo | 3 | ✅ |
| 15 | Cleanup código legacy | Mantenibilidad | Medio | 3 | ✅ |
| 16 | Audit log admin ops | Compliance | Medio | 3 | ✅ |
| 17 | Upload manual: verificar flujos | Funcionalidad core | Bajo | 4 | ✅ Verificado |
| 18 | Descarga MinIO por plan | Funcionalidad negocio | Bajo | 4 | ✅ Fix aplicado |
| 19 | Página de Ayuda | UX onboarding | Bajo | 4 | ✅ Ya tenía contenido |
| 20 | SSE para cola en tiempo real | UX avanzado | Alto | 4 | ⬜ PENDIENTE |
| 21 | Métricas Prometheus completas | Observabilidad | Bajo | 5 | ⬜ PENDIENTE |
| 22 | Backup MongoDB automatizado | Resiliencia | Bajo | 5 | ⬜ PENDIENTE |
| 23 | Documentar disaster recovery | Operaciones | Bajo | 5 | ⬜ PENDIENTE |

---

## Preguntas Abiertas que Necesitan Respuesta

Estas preguntas surgieron del análisis y requieren decisión antes de implementar:

1. **¿El panel de admin debe ser una ruta separada o un módulo dentro de la app principal?** Actualmente es `/admin` en la misma app Angular, lo cual expone el código admin a todos los usuarios aunque esté protegido por guard.

2. **¿Qué datos de "calidad" quiere ver el usuario en Estadísticas?** El punto 11 menciona "estadística de calidad y origen" — ¿se refiere a XML vs IA, o hay métricas adicionales como tiempo de procesamiento, correos duplicados detectados, etc.?

3. **¿El Explorador de Facturas (`/facturas/explorador`) está completo o falta funcionalidad específica?** No está claro qué diferencia tiene del listado normal en `/facturas/todas`.

4. **¿La integración de Pagopar está activa en producción actualmente?** Si sí, ¿hay cobros reales en curso que puedan romperse con cambios?

5. **¿Hay planes de migrar de Angular 15 a una versión más reciente (17+)?** Angular 15 está en fin de soporte. La migración puede traer mejoras de performance pero requiere trabajo.

6. **¿Se usa el campo `processing_method` en `invoice_headers` actualmente?** Si no se guarda en todos los paths, hay que retroalimentar los registros existentes.

7. **¿Cuántos usuarios activos hay en producción?** Determina la urgencia de mejoras de performance y el impacto de cambios.

8. **¿El worker RQ corre como un único pod o múltiples en Kubernetes?** Si es múltiple, el locking distribuido es urgente (no medio).

---

## Convención para este Plan

- Cuando se resuelva un item, agregar ✅ al inicio de su sección
- Documentar cualquier decisión de diseño importante que cambie lo descrito aquí
- Si se descubren nuevos problemas, agregarlos en la fase correcta
- Este plan se revisa y actualiza cada vez que se completa una fase

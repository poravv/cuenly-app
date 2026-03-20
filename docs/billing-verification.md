# Verificación de Cobros Recurrentes — Guía Operativa

> Última actualización: 2026-03-19

---

## Flujo de Cobro Automático

El sistema ejecuta 2 jobs diarios en el scheduler del backend:

| Job | Hora (UTC) | Función |
|-----|-----------|---------|
| **Billing Job** | 00:00 | Cobra tarjeta vía Pagopar + resetea IA si cobro exitoso |
| **Monthly Reset** | 00:01 | Verifica cobro exitoso antes de resetear IA (post-cobro) |

### Secuencia del Billing Job

1. Busca suscripciones con `status` IN (`active`, `past_due`) y `next_billing_date <= hoy`
2. Resuelve `pagopar_user_id` desde 3 fuentes: `payment_methods` → `auth_users` → `user_subscriptions`
3. Crea pedido en Pagopar (`create_order`)
4. Obtiene `alias_token` de tarjeta (válido 15 min)
5. Procesa pago (`process_payment`)
6. Si exitoso: actualiza `next_billing_date` al próximo mes (usa `billing_day_of_month`), resetea IA, registra transacción
7. Si falla: marca `past_due`, programa reintento (días 1, 3, 7), envía email

### Reintentos por fallo de pago

| Intento | Días después del fallo |
|---------|----------------------|
| 1ro | +1 día |
| 2do | +3 días |
| 3ro | +7 días |
| Después del 3ro | Cancela suscripción automáticamente |

---

## Comandos de Diagnóstico

### Conectar a MongoDB en K8s

```bash
# Encontrar el pod de MongoDB
kubectl get pods -n cuenly-backend | grep mongo

# Conectar (reemplazar <pod-name> con el nombre real)
# Las credenciales están en el secret backend-env-secrets
kubectl get secret backend-env-secrets -n cuenly-backend -o jsonpath='{.data.MONGODB_URL}' | base64 -d

# Conectar usando la URL obtenida (reemplazar <MONGODB_URL>)
kubectl exec -it <pod-name> -n cuenly-backend -- mongosh "<MONGODB_URL>"
```

### Verificar estado de un usuario

```javascript
// 1. ¿Tiene pagopar_user_id? (debe existir en al menos 1 fuente)
db.payment_methods.findOne({user_email: "<EMAIL>"})
db.auth_users.findOne({email: "<EMAIL>"}, {pagopar_user_id: 1, email: 1})
db.user_subscriptions.findOne({user_email: "<EMAIL>"}, {pagopar_user_id: 1, next_billing_date: 1, status: 1, plan_name: 1, billing_day_of_month: 1})

// 2. Últimas transacciones
db.subscription_transactions.find({user_email: "<EMAIL>"}).sort({created_at: -1}).limit(5).toArray()

// 3. Verificar si tiene cobro exitoso este mes
db.subscription_transactions.findOne({
  user_email: "<EMAIL>",
  status: "success",
  created_at: {$gte: new Date(new Date().getFullYear(), new Date().getMonth(), 1)}
})
```

### Verificar logs del billing job

```bash
# Logs del billing job (últimas 24h)
kubectl logs -n cuenly-backend -l app=cuenly-backend --since=24h | grep -i "billing\|cobro\|pago"

# Logs del scheduler
kubectl logs -n cuenly-backend -l app=cuenly-backend --since=24h | grep -i "scheduler\|reset.*post-cobro"
```

---

## Problemas Comunes y Solución

### 1. "pagopar_user_id no disponible"

El billing job no puede cobrar si `pagopar_user_id` es `null` en las 3 fuentes.

**Causa**: El usuario registró tarjeta pero el ID no se guardó correctamente.

**Fix**: Buscar el ID en Pagopar y guardarlo manualmente:
```javascript
db.payment_methods.updateOne(
  {user_email: "<EMAIL>"},
  {$set: {pagopar_user_id: "<ID_REAL>"}}
)
```

### 2. next_billing_date desfasada

Si `next_billing_date` no coincide con `billing_day_of_month`, el cobro cae en día incorrecto.

**Causa**: `calculate_next_billing_date` calculó desde la hora exacta del pago, no desde el día limpio.

**Fix**: Corregir manualmente:
```javascript
db.user_subscriptions.updateOne(
  {user_email: "<EMAIL>"},
  {$set: {next_billing_date: new Date("<YYYY-MM-DDT00:00:00Z>")}}
)
```

### 3. IA reseteada sin cobro

**Antes del fix (commit f4676c2)**: MonthlyResetService reseteaba IA como "fallback" sin verificar cobro.

**Después del fix**: El reset de IA SOLO ocurre si existe una transacción exitosa en `subscription_transactions` para el mes actual.

### 4. Suscripción en past_due

El billing falló y se programó un reintento. Verificar:
```javascript
db.user_subscriptions.findOne(
  {user_email: "<EMAIL>", status: "past_due"},
  {retry_count: 1, last_error: 1, next_billing_date: 1}
)
```

### 5. Verificar que el billing job está corriendo

```bash
# Debe aparecer "Iniciando job de cobros recurrentes" diariamente a las 00:00 UTC
kubectl logs -n cuenly-backend -l app=cuenly-backend --since=24h | grep "job de cobros"
```

---

## Archivos Clave del Sistema de Billing

| Archivo | Función |
|---------|---------|
| `backend/app/modules/scheduler/scheduler.py` | Scheduler: billing 00:00, reset 00:01, retention 03:00 |
| `backend/app/modules/scheduler/jobs/subscription_billing_job.py` | Lógica de cobro recurrente |
| `backend/app/modules/monthly_reset_service.py` | Reset de IA post-cobro (requiere transacción exitosa) |
| `backend/app/services/pagopar_service.py` | Integración con API Pagopar |
| `backend/app/repositories/subscription_repository.py` | Acceso a MongoDB: suscripciones, transacciones, pagos |
| `backend/app/api/endpoints/subscriptions.py` | Endpoints de suscripción (subscribe, cancel, confirm-card) |

---

## Colecciones MongoDB Involucradas

| Colección | Campos clave para billing |
|-----------|--------------------------|
| `user_subscriptions` | `user_email`, `status`, `next_billing_date`, `billing_day_of_month`, `pagopar_user_id`, `retry_count` |
| `subscription_transactions` | `user_email`, `status` (success/failed), `amount`, `created_at`, `error_message` |
| `payment_methods` | `user_email`, `pagopar_user_id`, `provider` |
| `auth_users` | `email`, `pagopar_user_id`, `ai_invoices_limit`, `ai_invoices_processed`, `ai_last_reset` |

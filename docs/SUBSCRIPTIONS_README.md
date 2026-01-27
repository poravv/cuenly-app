# Sistema de Suscripciones Pagopar - Cuenly

Sistema completo de suscripciones recurrentes integrado con Pagopar para cobros automáticos mensuales.

## 🚀 Inicio Rápido

### 1. Inicializar Planes

```bash
cd backend
python scripts/init_subscription_plans.py
```

Esto creará 4 planes en MongoDB:
- **FREE**: Gratis (50 facturas/mes)
- **BASIC**: 50,000 PYG/mes (200 facturas/mes)
- **PRO**: 150,000 PYG/mes (1,000 facturas/mes)  
- **PREMIUM**: 300,000 PYG/mes (Ilimitado)

### 2. Verificar Configuración

Asegúrate que las variables de entorno estén configuradas en `backend/.env`:

```env
PAGOPAR_PUBLIC_KEY=tu_public_key
PAGOPAR_PRIVATE_KEY=tu_private_key
PAGOPAR_BASE_URL=https://api.pagopar.com/api/pago-recurrente/3.0/
```

### 3. Reiniciar Backend

```bash
docker-compose restart backend
```

Verifica en los logs que el scheduler se inició:
```
✅ Scheduler iniciado correctamente
💳 Cobros recurrentes de suscripciones a las 00:00 (diario)
```

## 📋 API Endpoints

### Públicos (requieren autenticación de usuario)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/subscriptions/plans` | Lista todos los planes |
| POST | `/subscriptions/subscribe` | Inicia proceso de suscripción |
| POST | `/subscriptions/confirm-card` | Confirma tarjeta catastrada |
| GET | `/subscriptions/my-subscription` | Obtiene suscripción del usuario |
| POST | `/subscriptions/cancel` | Cancela suscripción |
| GET | `/subscriptions/payment-methods` | Lista métodos de pago |
| DELETE | `/subscriptions/payment-methods/{token}` | Elimina método de pago |

### Admin (requieren rol admin)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/subscriptions` | Lista suscripciones (paginado) |
| POST | `/admin/subscriptions/{id}/retry-charge` | Reintenta cobro manual |

## 🔄 Flujo de Suscripción

### 1. Usuario Selecciona Plan

```typescript
// Frontend
subscriptionService.getPlans().subscribe(plans => {
  // Mostrar planes
});
```

### 2. Inicia Suscripción

```typescript
subscriptionService.subscribe('PRO').subscribe(response => {
  const formId = response.form_id;
  // Mostrar iframe de Bancard con formId
});
```

### 3. Mostrar Iframe de Bancard

```html
<div id="iframe-container"></div>

<script src="https://checkout.bancard.com.py/bancard-checkout-2.1.0.js"></script>
<script>
  Bancard.Cards.createForm('iframe-container', formId, {
    onComplete: () => {
      // Usuario completó el formulario
      confirmCard();
    }
  });
</script>
```

### 4. Confirmar Tarjeta

```typescript
subscriptionService.confirmCard().subscribe(() => {
  // Suscripción activada!
  router.navigate(['/subscription/success']);
});
```

## ⚙️ Cron Job de Cobros

El job se ejecuta **diariamente a las 00:00** y:

1. Busca suscripciones con `next_billing_date <= hoy`
2. Para cada una:
   - Crea pedido en Pagopar
   - Obtiene `alias_token` de tarjeta
   - Procesa el pago
3. Si el pago es **exitoso**:
   - Actualiza `next_billing_date` (+30 días)
   - Registra transacción
4. Si el pago **falla**:
   - Marca como `PAST_DUE`
   - Programa reintentos: 1, 3, 7 días
   - Después de 3 fallos → cancela

### Ejecutar Manualmente (Testing)

```bash
cd backend
python -m app.modules.scheduler.jobs.subscription_billing_job
```

## 🗄️ Base de Datos

### Colecciones

#### `subscription_plans`
Planes de suscripción disponibles

#### `user_subscriptions`  
Suscripciones de usuarios

Campos importantes:
- `status`: `ACTIVE` | `PAST_DUE` | `CANCELLED`
- `next_billing_date`: Fecha del próximo cobro
- `retry_count`: Número de reintentos de pago

#### `payment_methods`
Métodos de pago catastrados (tarjetas)

#### `subscription_transactions`
Historial de todas las transacciones de cobro

## 🧪 Testing

### Crear Suscripción de Prueba

```python
from app.repositories.subscription_repository import SubscriptionRepository
from datetime import datetime, timedelta

repo = SubscriptionRepository()

subscription_data = {
    "user_email": "test@example.com",
    "pagopar_user_id": "test123",
    "plan_code": "PRO",
    "plan_name": "Plan Pro",
    "plan_price": 150000,
    "currency": "PYG",
    "status": "ACTIVE",
    "next_billing_date": datetime.utcnow(),  # Cobrar hoy
    "billing_period": "monthly"
}

await repo.create_subscription(subscription_data)
```

### Verificar Logs

```bash
# En tiempo real
docker-compose logs -f backend | grep -i "billing\|subscription"

# Archivo de log
tail -f backend/cuenlyapp_api.log | grep -i "cobr"
```

## 📊 Queries Útiles MongoDB

```javascript
// Ver suscripciones activas
db.user_subscriptions.find({status: "ACTIVE"})

// Ver suscripciones morosas
db.user_subscriptions.find({status: "PAST_DUE"})

// Próximos cobros (7 días)
db.user_subscriptions.find({
  status: "ACTIVE",
  next_billing_date: {
    $gte: new Date(),
    $lte: new Date(Date.now() + 7*24*60*60*1000)
  }
}).sort({next_billing_date: 1})

// Transacciones del mes actual
db.subscription_transactions.find({
  created_at: {
    $gte: new Date(new Date().getFullYear(), new Date().getMonth(), 1)
  }
})

// Estadísticas por plan
db.user_subscriptions.aggregate([
  {$match: {status: "ACTIVE"}},
  {$group: {
    _id: "$plan_code",
    count: {$sum: 1},
    revenue: {$sum: "$plan_price"}
  }}
])
```

## 🔧 Troubleshooting

### El job no se ejecuta

1. Verificar logs de startup del backend
2. Confirmar que el scheduler está corriendo:
   ```python
   from app.modules.scheduler import get_scheduler_instance
   scheduler = get_scheduler_instance()
   print(scheduler.get_status())
   ```

### Pago falla con "tarjeta no encontrada"

- El `alias_token` expira en 15 minutos
- Se obtiene automáticamente justo antes del cobro
- Verificar que el usuario tenga tarjeta catastrada en Pagopar

### Suscripción no se activa

1. Verificar que el usuario completó el iframe
2. Confirmar que `confirm_card` se llamó
3. Verificar en Pagopar que la tarjeta fue catastrada
4. Revisar logs para errores

### Ver estado del scheduler

```http
GET /debug/scheduler-status
```

## 🚨 Importante

> **Seguridad**
> - Nunca exponer `PAGOPAR_PRIVATE_KEY` al frontend
> - El `alias_token` es temporal (15 min) y se renueva automáticamente
> - Webhook debe validar: `sha1(private_key + hash_pedido)`

> **Producción**
> - Configurar HTTPS obligatorio
> - Configurar webhook URL en panel de Pagopar
> - Configurar alertas para fallos de cobro
> - Backup regular de transacciones

## 📞 Soporte

Para dudas sobre:
- **Pagopar API**: [soporte.pagopar.com](https://soporte.pagopar.com)
- **Implementación**: Ver [`implementation_plan.md`](../../../.gemini/antigravity/brain/6f2e5479-1bef-497a-926e-74110192af5b/implementation_plan.md)
- **Walkthrough completo**: Ver [`walkthrough.md`](../../../.gemini/antigravity/brain/6f2e5479-1bef-497a-926e-74110192af5b/walkthrough.md)

## 📝 TODO

- [ ] Implementar frontend (componentes Angular)
- [ ] Agregar webhook de Pagopar
- [ ] Configurar emails de notificación
- [ ] Dashboard admin de suscripciones
- [ ] Tests E2E completos

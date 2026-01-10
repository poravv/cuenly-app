# Integración recomendada Pagopar para Suscripciones (3 planes en tu web)

Este documento describe el **flujo recomendado** para tu escenario: **tu web define 3 planes**, el usuario se suscribe en tu sistema, y **Pagopar debita mes a mes** usando **Catastro de Tarjetas / Pagos Recurrentes**.

> **Seguridad**
> - **Nunca** expongas `private_key` en frontend.
> - Usa backend para generar tokens (sha1) y firmar solicitudes.
> - Los ejemplos usan placeholders: reemplazalos por tus valores reales en entorno DEV.

---

## 1) Tu escenario (resumen)

- ✅ Tenés web propia
- ✅ Tenés 3 planes definidos en tu sistema (no en Pagopar)
- ✅ Querés cobros automáticos mensuales, sin intervención del usuario
- ✅ Querés control total del ciclo de vida (alta, upgrade/downgrade, baja, morosidad)

**Solución recomendada:**  
✅ **API Pagopar – Pagos Recurrentes / Catastro de Tarjetas** + **Job programado en tu backend**

---

## 2) Concepto clave

- **Pagopar** se encarga del **catastro seguro de la tarjeta** (sin que vos almacenes datos sensibles).
- **Tu backend** decide **cuándo** se cobra y **qué monto** (según tu plan), y dispara el cobro mediante API.

---

## 3) Modelo mínimo de datos (recomendado)

### Tabla `plans`
- `id`
- `code` (basic / pro / premium)
- `amount` (monto mensual)
- `billing_period` (MONTHLY)
- `active`

### Tabla `subscriptions`
- `id`
- `user_id`
- `plan_id`
- `status` (ACTIVE | PAST_DUE | CANCELLED)
- `next_billing_date`
- `created_at`

### Tabla `payment_methods` (opcional pero útil)
- `id`
- `user_id`
- `pagopar_card_id` (si lo retornan)
- `provider` (Bancard / uPay)
- `created_at`

> Nota: el `alias_token` retornado al listar tarjetas es temporal (15 min). Se recomienda **listar inmediatamente antes de cobrar**.

---

## 4) Configuración inicial (Paso 0)

- Trabajar en **entorno de desarrollo** con tus keys.
- Backend obligatorio (API keys y sha1).
- En producción: HTTPS y hardening (headers, CORS, etc).

### Variables
```text
PUBLIC_KEY   = TU_PUBLIC_KEY
PRIVATE_KEY  = TU_PRIVATE_KEY
```

---

## 5) Paso a paso de alta de suscripción

### Paso 1 — Usuario elige plan (en tu web)
- El usuario selecciona uno de tus planes (BASIC/PRO/PREMIUM).
- En este punto todavía **no** cobrás.

---

### Paso 2 — Agregar cliente en Pagopar (1 sola vez por usuario)

**Token requerido:**
```text
token = sha1(PRIVATE_KEY + "PAGO-RECURRENTE")
```

**cURL:**
```bash
curl -X POST https://api.pagopar.com/api/pago-recurrente/3.0/agregar-cliente/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "TOKEN_PAGO_RECURRENTE",
    "token_publico": "TU_PUBLIC_KEY",
    "identificador": 123,
    "nombre_apellido": "Juan Perez",
    "email": "juan@email.com",
    "celular": "0981123456"
  }'
```

📌 `identificador` = `user_id` de tu sistema (no debe repetirse).

---

### Paso 3 — Solicitar alta de tarjeta (iniciar catastro)

**cURL:**
```bash
curl -X POST https://api.pagopar.com/api/pago-recurrente/3.0/agregar-tarjeta/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "TOKEN_PAGO_RECURRENTE",
    "token_publico": "TU_PUBLIC_KEY",
    "url": "https://tuweb.com/suscripcion",
    "proveedor": "Bancard",
    "identificador": 123
  }'
```

**Respuesta esperada:**
```json
{
  "respuesta": true,
  "resultado": "FORM_ID"
}
```

---

### Paso 4 — Mostrar iframe/formulario (frontend)

**Bancard (ejemplo):**
```html
<script src="bancard-checkout-2.1.0.js"></script>
<script>
window.onload = function () {
  Bancard.Cards.createForm('iframe-container', 'FORM_ID', {});
};
</script>

<div id="iframe-container"></div>
```

---

### Paso 5 — Confirmar tarjeta (obligatorio al volver a tu URL)

**cURL:**
```bash
curl -X POST https://api.pagopar.com/api/pago-recurrente/3.0/confirmar-tarjeta/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "TOKEN_PAGO_RECURRENTE",
    "token_publico": "TU_PUBLIC_KEY",
    "url": "https://tuweb.com/suscripcion",
    "identificador": 123
  }'
```

---

### Paso 6 — Crear suscripción en tu sistema

Al confirmar tarjeta y validar que existe al menos 1 tarjeta:

- `status = ACTIVE`
- `next_billing_date = hoy + 30 días` (o tu regla: día fijo del mes, etc.)
- Guardar relación `user_id -> plan_id`

---

## 6) Cobro mensual (job programado)

> **Este job es obligatorio** si usás API recurrente: es quien dispara el cobro.

### Lógica del job (resumen)
1. Buscar suscripciones `ACTIVE`
2. Si `today >= next_billing_date`:
   - crear pedido en Pagopar
   - listar tarjetas para obtener `alias_token` válido
   - debitar tarjeta
   - guardar resultado
   - actualizar `next_billing_date`

---

## 7) Paso a paso del cobro

### Paso 7 — Crear pedido en Pagopar (por cada ciclo de cobro)

**Token típico de pedido (según documentación de compra):**
```text
token = sha1(PRIVATE_KEY + ID_PEDIDO + strval(floatval(MONTO_TOTAL)))
```

**cURL (ejemplo mínimo):**
```bash
curl -X POST https://api.pagopar.com/api/comercios/2.0/iniciar-transaccion \
  -H "Content-Type: application/json" \
  -d '{
    "token": "TOKEN_PEDIDO",
    "public_key": "TU_PUBLIC_KEY",
    "monto_total": 50000,
    "tipo_pedido": "VENTA-COMERCIO",
    "id_pedido_comercio": "SUB-123-2026-03",
    "descripcion_resumen": "Suscripción Plan PRO Marzo"
  }'
```

✅ Guardá `resultado.data` (hash del pedido) para el cobro.

---

### Paso 8 — Listar tarjetas (justo antes de cobrar)

**cURL:**
```bash
curl -X POST https://api.pagopar.com/api/pago-recurrente/3.0/listar-tarjeta/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "TOKEN_PAGO_RECURRENTE",
    "token_publico": "TU_PUBLIC_KEY",
    "identificador": 123
  }'
```

De la respuesta necesitás el `alias_token` (temporal, ~15 min).

---

### Paso 9 — Debitar tarjeta (cobro automático)

**cURL:**
```bash
curl -X POST https://api.pagopar.com/api/pago-recurrente/3.0/pagar/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "TOKEN_PAGO_RECURRENTE",
    "token_publico": "TU_PUBLIC_KEY",
    "hash_pedido": "HASH_PEDIDO",
    "tarjeta": "ALIAS_TOKEN",
    "identificador": 123
  }'
```

---

## 8) Manejo de resultados (recomendado)

### Si el cobro fue exitoso
- `next_billing_date = next_billing_date + 30 días` (o regla fija)
- mantener `status = ACTIVE`
- registrar el pago (tabla `payments` o similar)

### Si el cobro falla
- pasar a `status = PAST_DUE`
- reintentar (p.ej. 1, 3 y 7 días)
- notificar al usuario (email/whatsapp)
- permitir actualización de tarjeta (re-catastro)

---

## 9) Cancelación de suscripción

Cuando el usuario cancela:
- `status = CANCELLED`
- no volver a cobrar
- opcional: permitir eliminar tarjeta (si tu UX lo requiere)

---

## 10) Checklist rápido

- [ ] Backend genera tokens sha1 y llama APIs
- [ ] Frontend solo muestra iframe (no maneja datos sensibles)
- [ ] Confirmar tarjeta siempre al retornar
- [ ] Job mensual ejecuta: crear pedido → listar tarjeta → pagar
- [ ] Persistir estados y logs de cobros
- [ ] Manejo de morosidad y reintentos

---

## 11) Notas importantes

- `alias_token` es temporal: listá tarjetas inmediatamente antes de pagar.
- Evitá “hardcodear” montos en el job: leelos del plan activo en tu DB.
- Si implementás upgrades/downgrades: definí cómo afecta `next_billing_date` y prorrateos (si aplica).

---

**Fin del documento.**

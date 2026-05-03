# Verificación de Cobros Recurrentes

## Qué Revisar

- Scheduler activo en backend.
- Lock Redis `cuenly:billing_job_lock` no queda colgado.
- Suscripciones vencidas (`next_billing_date <= now`) se procesan.
- Transacciones se registran en `subscription_transactions`.
- En cobro exitoso se actualiza `next_billing_date` y se resetea uso IA.
- En fallo se marca estado/reintento y queda trazabilidad.

## Logs

```bash
kubectl logs -n cuenly-backend deploy/cuenly-backend --since=24h | grep -i "cobros recurrentes"
kubectl logs -n cuenly-backend deploy/cuenly-backend --since=24h | grep -i "Pago exitoso\\|Pago fallido\\|Pagopar"
kubectl logs -n cuenly-backend deploy/cuenly-backend --since=24h | grep -i "Scheduler iniciado"
```

## MongoDB

```javascript
db.user_subscriptions.find({
  status: { $in: ["active", "past_due"] },
  next_billing_date: { $lte: new Date() }
})

db.subscription_transactions.find({}).sort({ created_at: -1 }).limit(20)

db.payment_methods.find({ user_email: "usuario@dominio.com" })
```

## Problemas Comunes

- Sin `pagopar_user_id`: ejecutar flujo de `ensure-customer` o revisar `payment_methods`.
- Sin tarjeta: el usuario debe completar catastro.
- Pago rechazado: queda transacción `failed` con `error_message`.
- Scheduler duplicado: revisar lock Redis y cantidad de pods.
- No resetea IA: confirmar transacción `success` del mes/aniversario.

## Archivos

- Billing job: `backend/app/modules/scheduler/jobs/subscription_billing_job.py`
- Scheduler: `backend/app/modules/scheduler/scheduler.py`
- Repositorio: `backend/app/repositories/subscription_repository.py`
- Servicio Pagopar: `backend/app/services/pagopar_service.py`

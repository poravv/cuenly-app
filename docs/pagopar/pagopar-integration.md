# Pagopar y Suscripciones

## Alcance

CuenlyApp usa Pagopar/Bancard para catastro de tarjeta, cobro inicial y cobros recurrentes de planes.

## Variables

```env
PAGOPAR_PUBLIC_KEY=
PAGOPAR_PRIVATE_KEY=
PAGOPAR_BASE_URL=https://api.pagopar.com/api/pago-recurrente/3.0/
PAGOPAR_REDIRECT_URL=https://app.cuenly.com/subscription/confirm
```

## Flujo de Alta

1. Frontend llama `POST /subscriptions/ensure-customer`.
2. Usuario elige plan y llama `POST /subscriptions/subscribe`.
3. Backend obtiene plan, resuelve/crea `pagopar_user_id` y busca tarjetas.
4. Si ya hay tarjeta, crea pedido, obtiene `alias_token`, cobra y crea suscripción.
5. Si no hay tarjeta, inicia `agregar-tarjeta` y retorna `form_id`.
6. Frontend muestra iframe Bancard/uPay.
7. Al finalizar iframe, frontend llama `POST /subscriptions/confirm-card`.
8. Backend confirma tarjeta, cobra primer mes, crea suscripción y registra transacción.

## Cobro Recurrente

Job: `backend/app/modules/scheduler/jobs/subscription_billing_job.py`.

El scheduler ejecuta diariamente:

- Busca `active`/`past_due` con `next_billing_date <= now`.
- Crea pedido Pagopar.
- Obtiene `alias_token` temporal.
- Ejecuta `pagar`.
- Registra transacción `success` o `failed`.
- En éxito, calcula próxima fecha por aniversario y resetea límites IA.
- En fallo, marca/reintenta según política del job.

## Endpoints

- `GET /subscriptions/plans`
- `POST /subscriptions/ensure-customer`
- `POST /subscriptions/subscribe`
- `POST /subscriptions/confirm-card`
- `GET /subscriptions/my-subscription`
- `GET /subscriptions/my-transactions`
- `GET /subscriptions/payment-methods`
- `DELETE /subscriptions/payment-methods/{card_token}`
- `POST /subscriptions/cancel`
- `GET /pagopar/cards`
- `POST /pagopar/cards/init`
- `POST /pagopar/cards/confirm`

## Error "No existe comprador"

Causa usual: se intenta `agregar-tarjeta`, `listar-tarjeta` o `pagar` antes de registrar correctamente el comprador en Pagopar.

Mitigación actual:

- `ensure-customer` crea/guarda el comprador.
- `subscribe` vuelve a registrar/verificar antes de iniciar tarjeta.
- `pagopar/cards/init` reintenta auto-registro si Pagopar responde "No existe comprador".
- `resolve_pagopar_user_id` busca en `payment_methods`, `auth_users` y `user_subscriptions`.

Checklist:

- Confirmar `PAGOPAR_PUBLIC_KEY` y `PAGOPAR_PRIVATE_KEY`.
- Confirmar que sandbox/prod coincidan con las credenciales.
- Verificar que el comercio tenga pagos recurrentes habilitados.
- Revisar `payment_methods.pagopar_user_id` para el usuario afectado.

## Tarjetas Sandbox

Usar solo con credenciales sandbox del proveedor.

| Proveedor | Tarjeta | Resultado |
| --- | --- | --- |
| Bancard | `4569760000000000` | Aprobada |
| Bancard | `5361550000000000` | Aprobada |
| Bancard | `4222222222222222` | Rechazada |
| uPay/Cybersource | `4111111111111111` | Aprobada |
| uPay/Cybersource | `4000000000000002` | Rechazada |

Datos comunes: vencimiento futuro, CVV válido de 3 dígitos y documento de prueba permitido por el entorno sandbox.

## Verificación Manual

```bash
kubectl logs -n cuenly-backend deploy/cuenly-backend --since=2h | grep -i pagopar
kubectl logs -n cuenly-backend deploy/cuenly-backend --since=24h | grep -i "cobros recurrentes"
```

En MongoDB revisar:

- `payment_methods`
- `user_subscriptions`
- `subscription_transactions`

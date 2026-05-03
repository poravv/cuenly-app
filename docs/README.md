# Documentación CuenlyApp

Índice de documentación activa. Los documentos históricos y planes ya implementados fueron eliminados para reducir ruido.

## Referencia Diaria

| Archivo | Uso |
| --- | --- |
| [documentacion-tecnica.md](./documentacion-tecnica.md) | Arquitectura, APIs, frontend, colas, pagos e infraestructura. |
| [documentacion-funcional.md](./documentacion-funcional.md) | Qué hace el producto y flujos de usuario. |
| [billing-verification.md](./billing-verification.md) | Cómo auditar cobros recurrentes, transacciones y scheduler. |
| [admin-management.md](./admin-management.md) | Gestión de administradores en Firestore. |
| [DISASTER-RECOVERY.md](./DISASTER-RECOVERY.md) | Recuperación operativa de MongoDB, Redis, MinIO y pods. |
| [pagopar/pagopar-integration.md](./pagopar/pagopar-integration.md) | Integración Pagopar, troubleshooting y tarjetas sandbox. |
| [set/RG90_ESPECIFICACION_TECNICA.md](./set/RG90_ESPECIFICACION_TECNICA.md) | Especificación RG-90 para exportaciones tributarias. |

## Rutas Críticas

- Backend FastAPI: `backend/app/api/api.py`.
- Frontend API client: `frontend/src/app/services/api.service.ts`.
- Perfil/colas frontend: `frontend/src/app/services/user.service.ts`.
- Proxy frontend: `frontend/nginx.template.conf` y `frontend/proxy.conf.json`.
- Worker RQ: `backend/worker.py`, `backend/app/worker/queues.py`, `backend/app/worker/jobs.py`.
- Billing recurrente: `backend/app/modules/scheduler/jobs/subscription_billing_job.py`.

## Convenciones

- El frontend usa rutas relativas (`environment.apiUrl = ''`).
- En desarrollo, `proxy.conf.json` reescribe `/api/*` a `/*`.
- En producción, `nginx.template.conf` aplica la misma reescritura.
- Las rutas protegidas dependen de Firebase `Authorization: Bearer <token>`.
- Endpoints de procesamiento manual que requieren clave frontend también reciben `X-Frontend-Key`.

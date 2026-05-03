# CuenlyApp — Contexto Permanente

## Producto

CuenlyApp procesa facturas desde correo o carga manual, guarda cabeceras e ítems en MongoDB y permite consulta/exportación desde Angular. Usa XML SIFEN nativo e IA para PDF/imagen cuando el usuario tiene cupo.

## Stack

- Backend: FastAPI, MongoDB, Redis/RQ, Firebase Auth, OpenAI, MinIO.
- Frontend: Angular, Bootstrap, Firebase Web SDK.
- Pagos: Pagopar/Bancard.
- Infra: Docker Compose, Kubernetes, GitHub Actions.

## Comandos

```bash
docker compose up -d --build
docker compose --profile dev up -d --build mongodb-dev redis-dev backend-dev frontend-dev
cd backend && python -m pytest
cd frontend && npm run build
```

## Rutas Clave

- App FastAPI: `backend/app/api/api.py`.
- Routers backend: `backend/app/api/routers/` y `backend/app/api/endpoints/`.
- Worker RQ: `backend/worker.py`.
- Jobs RQ: `backend/app/worker/jobs.py`.
- Colas RQ: `backend/app/worker/queues.py`.
- Billing: `backend/app/modules/scheduler/jobs/subscription_billing_job.py`.
- API frontend: `frontend/src/app/services/api.service.ts`.
- Perfil/cola frontend: `frontend/src/app/services/user.service.ts`.
- Proxy frontend: `frontend/proxy.conf.json`, `frontend/nginx.template.conf`.

## Convenciones Técnicas

- `environment.apiUrl` debe ser `''`; las rutas frontend son relativas.
- `/api/*` se reescribe a `/*` en proxy local y nginx.
- Auth de usuario: Firebase Bearer token.
- Admin: Firestore `admins`.
- Endpoints sensibles de procesamiento manual usan `X-Frontend-Key`.
- SSE de cola usa token en query param.
- MongoDB v2 usa `invoice_headers` e `invoice_items` como fuente principal.

## Flujos Críticos

- Procesamiento manual: `/tasks/process`, `/tasks/{job_id}`, `/tasks/{job_id}/cancel`.
- Histórico por rango: `/jobs/process-range`; cancela jobs activos previos del mismo usuario.
- Cola usuario: `/user/queue-events` y `/user/queue-events/stream`.
- Suscripción: `/subscriptions/subscribe` cobra con tarjeta existente o retorna `form_id`.
- Confirmación tarjeta: `/subscriptions/confirm-card` confirma, cobra y activa plan.
- Billing recurrente: scheduler diario con lock Redis.

## Documentación

Usar `README.md` y `docs/README.md` como índice. Mantener docs cortas y operativas; evitar planes históricos extensos dentro del repo.

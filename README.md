# CuenlyApp

CuenlyApp procesa facturas recibidas por correo o carga manual, extrae datos con XML SIFEN o IA cuando corresponde, guarda la información en MongoDB y permite consultar/exportar resultados desde Angular.

## Stack

- Backend: FastAPI, MongoDB, Redis/RQ, Firebase Auth, OpenAI, MinIO.
- Frontend: Angular, Firebase Web SDK, Bootstrap.
- Pagos: Pagopar/Bancard para suscripciones y cobros recurrentes.
- Operación: Docker Compose local, Kubernetes + GitHub Actions en producción.

## Documentación

- [Índice de documentación](docs/README.md)
- [Arquitectura técnica](docs/documentacion-tecnica.md)
- [Funcionalidad del producto](docs/documentacion-funcional.md)
- [Pagopar y suscripciones](docs/pagopar/pagopar-integration.md)
- [Verificación de billing](docs/billing-verification.md)
- [Disaster recovery](docs/DISASTER-RECOVERY.md)

## Desarrollo Local

Requisitos: Python 3.11+, Node.js 18+, Docker, Docker Compose y credenciales en `backend/.env` + `frontend/src/environments/environment.ts`.

```bash
docker compose up -d --build
```

URLs:

- Frontend: `http://localhost:4200`
- Backend vía proxy: `http://localhost:4200/docs`
- Backend directo dentro del stack: `backend:8000`

Stack aislado de desarrollo:

```bash
docker compose --profile dev up -d --build mongodb-dev redis-dev backend-dev frontend-dev
```

URLs del perfil dev:

- Frontend: `http://localhost:4300`
- Backend: `http://localhost:8001/docs`

## Verificaciones

```bash
cd backend && python -m pytest
cd frontend && npm run build
```

## Producción

El despliegue se realiza por GitHub Actions. La imagen frontend se construye con `frontend/Dockerfile.proxy`, que usa `nginx.template.conf` y reescribe `/api/*` hacia el backend. Las rutas Angular deben usar rutas relativas para que autenticación, proxy y SSE funcionen igual en local y producción.

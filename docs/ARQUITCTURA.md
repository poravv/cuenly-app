# Arquitectura de Cuenly

## Vista general

```mermaid
graph TD
    U[Usuario] --> FE[Frontend Angular]
    FE -->|REST| BE[Backend FastAPI]

    subgraph Datos
        MDB[(MongoDB)]
        REDIS[(Redis)]
        MINIO[(MinIO S3)]
    end

    BE --> MDB
    BE --> REDIS
    BE --> MINIO

    subgraph Procesamiento Asincrono
        W[RQ Worker]
        KEDA[KEDA ScaledObject]
    end

    W --> REDIS
    KEDA --> W

    subgraph Externos
        OA[OpenAI]
        FB[Firebase Auth/Analytics]
        MAIL[Servidores IMAP/SMTP]
    end

    BE --> OA
    FE --> FB
    BE --> MAIL
```

## Componentes principales

- Frontend: Angular 17, autenticacion Firebase, consumo de API backend.
- Backend: FastAPI, procesamiento de facturas, scheduler interno y APIs administrativas.
- Worker: proceso `cuenly-worker` con RQ para colas `high`, `default` y `low`.
- Redis: cache y broker de colas de jobs.
- MongoDB: persistencia principal de usuarios, facturas, configuraciones y jobs.
- MinIO: respaldo de documentos originales.
- KEDA: autoscaling del worker por CPU y longitud de cola Redis.

## Namespaces Kubernetes

- `cuenly-backend`: backend, worker, redis y recursos asociados.
- `cuenly-frontend`: frontend y recursos web.
- `cuenly-monitoring`: Prometheus, Grafana, Loki y AlertManager.

## Flujo de despliegue

```mermaid
sequenceDiagram
    participant GH as GitHub Actions
    participant K8S as Kubernetes API
    participant BE as Deployment backend
    participant WK as Deployment worker
    participant FE as Deployment frontend

    GH->>K8S: kubectl apply manifests
    GH->>BE: set image sha-<commit>
    GH->>WK: set image sha-<commit>
    GH->>FE: set image sha-<commit>
    GH->>K8S: patch annotations restartedAt/forceUpdate/gitSha
    GH->>K8S: rollout status backend/worker/frontend
    GH->>K8S: validar imagen esperada en pods running
```

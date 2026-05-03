# Disaster Recovery

## Prioridad

1. Restaurar MongoDB.
2. Verificar Redis/RQ.
3. Verificar MinIO/S3.
4. Reiniciar backend, worker y frontend.
5. Validar salud y flujos críticos.

## MongoDB

Restaurar backup:

```bash
mongorestore --uri "$MONGODB_URL" --drop /backup/cuenlyapp_warehouse
```

Validar colecciones:

```javascript
db.auth_users.countDocuments()
db.invoice_headers.countDocuments()
db.processed_emails.countDocuments()
db.user_subscriptions.countDocuments()
```

## Redis/RQ

Redis contiene colas y locks, no la fuente de verdad de facturas.

Si se pierde Redis:

- Jobs en curso pueden quedar huérfanos.
- El usuario puede relanzar procesos por rango.
- La idempotencia principal queda en `processed_emails` y facturas MongoDB.

Comandos:

```bash
redis-cli keys "rq:*"
redis-cli get cuenly:billing_job_lock
```

## MinIO/S3

Validar bucket configurado en `MINIO_BUCKET` y claves originales (`minio_key`) desde `invoice_headers`.

## Kubernetes

```bash
kubectl rollout restart deploy/cuenly-backend -n cuenly-backend
kubectl rollout restart deploy/cuenly-worker -n cuenly-backend
kubectl rollout restart deploy/cuenly-frontend -n cuenly-frontend

kubectl get pods -n cuenly-backend
kubectl get pods -n cuenly-frontend
```

## Health Checks

```bash
curl -fsS https://app.cuenly.com/health
curl -fsS https://app.cuenly.com/status
```

## Flujos a Probar

- Login.
- Cargar perfil.
- Consultar facturas.
- Procesar un XML.
- Ver cola de procesos.
- Consultar suscripción actual.
- Consultar historial de pagos.

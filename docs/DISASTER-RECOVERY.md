# Disaster Recovery — CuenlyApp

> Última actualización: 2026-02-28

## 1. Restaurar MongoDB desde Backup

### Prerequisitos
- Acceso al PVC de backups o directorio donde se almacenan
- `mongorestore` disponible
- URI de conexión a MongoDB destino

### Procedimiento
1. Identificar el backup más reciente:
   ```bash
   ls -lt /backups/mongodb_* | head -5
   ```

2. Restaurar:
   ```bash
   mongorestore --uri="${MONGODB_URL}" --gzip --drop /backups/mongodb_YYYYMMDD_HHMMSS/
   ```
   - `--drop`: Elimina colecciones existentes antes de restaurar
   - `--gzip`: Los backups están comprimidos

3. Verificar integridad:
   ```bash
   mongosh "${MONGODB_URL}" --eval "db.auth_users.countDocuments({})"
   mongosh "${MONGODB_URL}" --eval "db.invoice_headers.countDocuments({})"
   ```

## 2. Reiniciar Stack Completo

### Desarrollo (Docker Compose)
```bash
cd /path/to/cuenly
docker compose down -v        # Detener todo (NO USAR -v si quieres preservar datos)
docker compose up -d --build  # Reconstruir y levantar
docker compose logs -f        # Verificar logs
```

### Producción (Kubernetes)
```bash
# Reiniciar deployments
kubectl rollout restart deployment/cuenly-backend -n cuenly
kubectl rollout restart deployment/cuenly-frontend -n cuenly
kubectl rollout restart deployment/cuenly-worker -n cuenly

# Verificar pods
kubectl get pods -n cuenly

# Verificar logs
kubectl logs -f deployment/cuenly-backend -n cuenly
```

## 3. MongoDB Corrupto

### Signos de corrupción
- Errores `WiredTiger` en logs de MongoDB
- Queries retornan resultados inconsistentes
- Índices rotos (errores `IndexKeyTooLong` o duplicados inesperados)

### Procedimiento
1. **Detener** todos los servicios que escriben a MongoDB:
   ```bash
   kubectl scale deployment/cuenly-backend --replicas=0 -n cuenly
   kubectl scale deployment/cuenly-worker --replicas=0 -n cuenly
   ```

2. **Intentar reparar** (solo si es corrupción menor):
   ```bash
   mongosh "${MONGODB_URL}" --eval "db.repairDatabase()"
   ```

3. **Si la reparación falla**, restaurar desde backup:
   - Seguir sección 1 de este documento
   - Las facturas procesadas entre el último backup y la corrupción se perderán
   - Los correos se pueden reprocesar (idempotencia via `processed_emails`)

4. **Recrear índices** después de restaurar:
   ```bash
   # Los índices se recrean automáticamente al iniciar el backend
   # gracias al flag _indexes_ensured en cada repository
   kubectl rollout restart deployment/cuenly-backend -n cuenly
   ```

5. **Reactivar** servicios:
   ```bash
   kubectl scale deployment/cuenly-backend --replicas=2 -n cuenly
   kubectl scale deployment/cuenly-worker --replicas=3 -n cuenly
   ```

## 4. Restaurar MinIO (Archivos Originales)

### Si MinIO se pierde
- Los archivos originales (PDFs, XMLs) se pierden
- Las facturas extraídas en MongoDB **NO se pierden** (datos están en `invoice_headers`)
- Para re-subir archivos: reprocesar correos desde IMAP (los correos siguen en el servidor de correo)

### Procedimiento
1. Levantar nuevo MinIO:
   ```bash
   kubectl apply -f k8s-monitoring/minio-deployment.yaml -n cuenly
   ```
2. Crear bucket:
   ```bash
   mc alias set cuenly https://minpoint.mindtechpy.net $MINIO_ACCESS_KEY $MINIO_SECRET_KEY
   mc mb cuenly/bk-invoice
   ```
3. Reprocesar correos para re-subir archivos originales

## 5. Incidentes Comunes

| Síntoma | Causa Probable | Acción |
|---------|----------------|--------|
| Backend no inicia | MongoDB no disponible | Verificar pod MongoDB, URI de conexión |
| Worker no procesa | Redis no disponible | Verificar pod Redis, `REDIS_HOST` |
| Facturas no se extraen | OpenAI API key inválida o quota agotada | Verificar `OPENAI_API_KEY`, balance en dashboard OpenAI |
| Login falla | Firebase config incorrecta | Verificar `FIREBASE_PROJECT_ID`, certificados |
| Cobros no se ejecutan | SMTP no configurado o Pagopar keys inválidas | Verificar `PAGOPAR_*` env vars, `SMTP_*` env vars |
| Cola llena sin procesar | Worker caído o Redis lleno | `kubectl logs deployment/cuenly-worker`, verificar memoria Redis |

## 6. Recuperación de Correos no Procesados

### Si la cola de RQ se pierde
- Los correos IMAP no se procesaron (siguen en el servidor)
- La colección `processed_emails` contiene un registro de idempotencia por correo
- Si se borra accidentalmente `processed_emails`, los correos se reprocesarán

### Procedimiento
```bash
# Si la cola RQ se pierde, los trabajos quedan huérfanos pero no se pierden datos

# Restaurar processed_emails desde backup si fue borrada
mongorestore --uri="${MONGODB_URL}" --gzip --nsInclude="cuenly.processed_emails" /backups/mongodb_YYYYMMDD_HHMMSS/

# Luego, reprocesar con las mismas opciones (desde/hasta, términos de búsqueda)
```

## 7. Contactos de Emergencia

| Rol | Contacto | Disponibilidad |
|-----|----------|----------------|
| Administrador Técnico | andyvercha@gmail.com | 24/7 |
| Infraestructura | (definir) | (definir) |
| Proveedor Cloud | (definir) | (definir) |
| OpenAI Support | https://platform.openai.com/account/billing/limits | 24/7 |

## 8. Testing del Plan de Recuperación

### Recomendación
- **Mensualmente**: Simular restauración de backup en ambiente de staging
- **Trimestralmente**: Ejecutar full disaster recovery drill
- **Después de cambios mayores**: Validar que backups incluyen nuevas colecciones

### Checklist de Testing
- [ ] Validar que el backup se crea exitosamente
- [ ] Verificar tamaño y edad del backup más reciente
- [ ] Restaurar a base de datos de prueba
- [ ] Verificar integridad de documentos (count, índices)
- [ ] Confirmar que la aplicación inicia con datos restaurados
- [ ] Validar que usuarios pueden loguearse y ver sus facturas
- [ ] Verificar que pueden procesar nuevos correos post-restauración

## 9. Métricas a Monitorear

Para evitar incidentes, monitorear:
- Salud de MongoDB: conexión, tamaño, queries lentas
- Espacio de respaldo (alertar si < 10% disponible)
- Éxito/fallo de backups automáticos (CronJob)
- Edad del backup más reciente (alertar si > 24 horas)
- Redis memory (alertar si > 80%)
- OpenAI API quota y rate limits

Sugerencia: Agregar alertas en Prometheus/AlertManager para estos KPIs.

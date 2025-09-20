# Guía de Seguridad para CuenlyApp

## ✅ Implementaciones Completadas

### 1. Validaciones de Datos
- ✅ Validación de formato de fecha (YYYY-MM)
- ✅ Validación de tipos de exportación
- ✅ Validación de RUC paraguayo
- ✅ Validación de montos monetarios
- ✅ Sanitización de nombres de archivo
- ✅ Validación de consistencia de montos en facturas

### 2. Seguridad en API
- ✅ Headers de seguridad HTTP
- ✅ Validación de tamaño de requests
- ✅ Logging de eventos de seguridad
- ✅ Validación de métodos HTTP permitidos
- ✅ Rate limiting básico

### 3. Seguridad en MongoDB
- ✅ Autenticación con usuario/contraseña
- ✅ Conexiones con timeout configurado
- ✅ Pool de conexiones limitado
- ✅ Índices optimizados para consultas

## 🔧 Recomendaciones Adicionales

### 1. Autenticación y Autorización
```bash
# Implementar JWT para autenticación
pip install python-jose[cryptography]
pip install passlib[bcrypt]

# Crear sistema de usuarios básico
# - Admin: acceso completo
# - Viewer: solo consultas
# - Operator: procesamiento de emails
```

### 2. Encriptación de Datos Sensibles
```python
# Encriptar contraseñas de email en .env
from cryptography.fernet import Fernet

# Generar clave de encriptación
key = Fernet.generate_key()
cipher_suite = Fernet(key)

# Encriptar contraseñas de email
encrypted_password = cipher_suite.encrypt(b"password")
```

### 3. Backup y Recuperación
```bash
# Configurar backup automático de MongoDB
# Crear script de backup diario
#!/bin/bash
BACKUP_DIR="/app/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mongodump --host mongodb:27017 --db cuenlyapp_warehouse --out "$BACKUP_DIR/backup_$DATE"

# Comprimir y limpiar backups antiguos
tar -czf "$BACKUP_DIR/backup_$DATE.tar.gz" "$BACKUP_DIR/backup_$DATE"
rm -rf "$BACKUP_DIR/backup_$DATE"
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
```

### 4. Monitoreo de Seguridad
```python
# Configurar alertas para eventos críticos
SECURITY_ALERTS = {
    "multiple_failed_logins": {
        "threshold": 5,
        "window_minutes": 10,
        "action": "block_ip"
    },
    "unusual_data_access": {
        "threshold": 100,  # 100+ facturas en una consulta
        "action": "log_and_notify"
    },
    "large_file_upload": {
        "threshold": "25MB",
        "action": "virus_scan"
    }
}
```

### 5. Variables de Entorno Seguras
```bash
# En producción, usar secretos más robustos
MONGODB_URL=mongodb://username:strong_password@mongodb:27017/db?authSource=admin
JWT_SECRET_KEY=tu-clave-super-secreta-de-al-menos-32-caracteres
OPENAI_API_KEY=sk-...
EMAIL_ENCRYPTION_KEY=clave-para-encriptar-passwords-de-email

# Configuración de SSL/TLS
SSL_ENABLED=true
SSL_CERT_PATH=/app/ssl/cert.pem
SSL_KEY_PATH=/app/ssl/key.pem

# Rate limiting más estricto en producción
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=500
```

### 6. Configuración de Nginx (Proxy Reverso)
```nginx
# nginx.conf para producción
server {
    listen 443 ssl http2;
    server_name tu-dominio.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # File upload limits
    client_max_body_size 25M;
    
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

### 7. Docker Security
```dockerfile
# Usar imagen base minimal
FROM python:3.11-slim

# Crear usuario no-root
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copiar dependencias y código
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
WORKDIR /app

# Cambiar ownership y permisos
RUN chown -R appuser:appuser /app
RUN chmod -R 755 /app

# Ejecutar como usuario no-root
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8. Monitoreo con Prometheus/Grafana
```python
# Métricas de seguridad
from prometheus_client import Counter, Histogram, Gauge

security_events = Counter('security_events_total', 'Total security events', ['event_type'])
request_duration = Histogram('request_duration_seconds', 'Request duration')
failed_logins = Counter('failed_logins_total', 'Failed login attempts')
active_sessions = Gauge('active_sessions', 'Number of active user sessions')
```

### 9. Auditoría y Compliance
```python
# Log de auditoría detallado
AUDIT_EVENTS = [
    "user_login",
    "user_logout",
    "data_export",
    "data_modification",
    "configuration_change",
    "file_upload",
    "email_processing"
]

# Estructura de log de auditoría
{
    "timestamp": "2025-09-05T15:30:00Z",
    "event_type": "data_export",
    "user_id": "admin@company.com",
    "ip_address": "192.168.1.100",
    "resource": "facturas_2025-07",
    "action": "excel_export",
    "status": "success",
    "details": {
        "records_exported": 156,
        "file_size": "2.3MB",
        "export_type": "completo"
    }
}
```

### 10. Checklist de Seguridad

#### Antes de Producción:
- [ ] Cambiar todas las contraseñas por defecto
- [ ] Configurar SSL/TLS para todas las conexiones
- [ ] Implementar rate limiting estricto
- [ ] Configurar firewall para limitar accesos
- [ ] Establecer backup automático
- [ ] Configurar monitoreo de logs
- [ ] Probar procedimientos de recuperación
- [ ] Documentar procedimientos de incidentes

#### Mantenimiento Regular:
- [ ] Actualizar dependencias (mensual)
- [ ] Revisar logs de seguridad (semanal)
- [ ] Probar backups (semanal)
- [ ] Rotar secretos/claves (trimestral)
- [ ] Auditoría de accesos (mensual)
- [ ] Scan de vulnerabilidades (mensual)

### 11. Comandos Útiles para Administración

```bash
# Verificar logs de seguridad
docker-compose logs backend | grep "SECURITY EVENT"

# Backup manual de MongoDB
docker-compose exec mongodb mongodump --db cuenlyapp_warehouse --out /backup

# Verificar conexiones activas a MongoDB
docker-compose exec mongodb mongo --eval "db.runCommand({currentOp: 1})"

# Verificar espacio en disco
docker-compose exec backend df -h

# Monitorear uso de memoria
docker stats cuenlyapp_backend_1

# Verificar certificados SSL
openssl x509 -in cert.pem -text -noout
```

## 🚨 Incidentes de Seguridad

### Procedimiento de Respuesta:
1. **Detectar**: Monitoreo automático + alertas
2. **Contener**: Bloquear acceso sospechoso
3. **Erradicar**: Eliminar vulnerabilidad
4. **Recuperar**: Restaurar servicios seguros
5. **Lecciones**: Documentar y mejorar

### Contactos de Emergencia:
- Administrador de Sistema: admin@company.com
- Responsable de Seguridad: security@company.com
- Proveedor de Hosting: support@hosting.com
# ✅ Configuración de Prometheus + AlertManager

## 📋 Resumen de Implementación

Se ha configurado correctamente el sistema de alertas de Cuenly con Prometheus y AlertManager, integrando los GitHub Secrets para el envío de correos.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    cuenly-monitoring                         │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │  Prometheus  │─────▶│  AlertMgr    │─────▶ 📧 Emails    │
│  │  (métricas)  │      │ (cuenly-bkd) │                    │
│  └──────────────┘      └──────────────┘                    │
│         │                                                    │
│         ├──────────────────────────────────────────┐       │
│         │                                           │       │
│         ▼                                           ▼       │
│  ┌─────────────┐                            ┌─────────────┐│
│  │  Backend    │                            │  Frontend   ││
│  │   Pods      │                            │    Pods     ││
│  └─────────────┘                            └─────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Archivos de Configuración

### 1. **Reglas de Alertas**
**Archivo:** `config/prometheus-alerts-cuenly.yml`
- ✅ **SÍ se usa** - Se aplica como ConfigMap en Prometheus
- Contiene 4 grupos de alertas:
  - `cuenly-backend-sla-alerts` - Disponibilidad y performance
  - `cuenly-business-alerts` - Alertas de negocio
  - `cuenly-infrastructure-alerts` - Infraestructura (CPU, memoria, pods)
  - `cuenly-api-key-security` - Seguridad de API keys

### 2. **Configuración de AlertManager**
**Archivo:** `config/alertmanager.yml`
- ✅ **SÍ se usa** - Se aplica como ConfigMap en AlertManager
- Usa variables de entorno para secrets SMTP
- Configurado para enviar emails a través de `mail.cuenly.com`

### 3. **Manifiestos Kubernetes**

#### a) Prometheus (Namespace: `cuenly-monitoring`)
**Archivo:** `k8s-monitoring/simple-monitoring-stack.yaml`
- Deployment: `cuenly-prometheus`
- Service: `cuenly-prometheus:9090`
- ConfigMap: `prometheus-config` (configuración principal)
- ConfigMap: `prometheus-rules` (reglas de alertas - **NUEVO**)

**Cambios realizados:**
```yaml
# Agregado en prometheus.yml:
alerting:
  alertmanagers:
  - static_configs:
    - targets:
      - alertmanager-service.cuenly-backend.svc.cluster.local:9093

rule_files:
  - /etc/prometheus/rules/*.yml

# Agregado volumeMount:
volumeMounts:
- name: rules
  mountPath: /etc/prometheus/rules

# Agregado volume:
volumes:
- name: rules
  configMap:
    name: prometheus-rules
```

#### b) AlertManager (Namespace: `cuenly-backend`)
**Archivo:** `backend/k8s/alertmanager-deployment.yaml`
- Deployment: `alertmanager`
- Service: `alertmanager-service:9093`
- ConfigMap: `alertmanager-config`
- Secret: `alertmanager-secrets` (credenciales SMTP)

---

## 🔐 GitHub Secrets Configurados

Estos secrets deben estar configurados en GitHub:

```bash
ALERTMANAGER_SMTP_HOST=mail.cuenly.com
ALERTMANAGER_SMTP_PORT=465
ALERTMANAGER_SMTP_USER=alerts@cuenly.com
ALERTMANAGER_SMTP_PASSWORD=<tu-password-seguro>
ALERTMANAGER_EMAIL_TO=alerts@cuenly.com
```

**Aplicación en workflow:** `.github/workflows/cuenly-deploy.yml` líneas 382-402
```yaml
- name: Create/Update AlertManager secrets
  run: |
    kubectl create secret generic alertmanager-secrets \
      --namespace=cuenly-backend \
      --from-literal=ALERTMANAGER_SMTP_HOST="${{ secrets.ALERTMANAGER_SMTP_HOST }}" \
      --from-literal=ALERTMANAGER_SMTP_PORT="${{ secrets.ALERTMANAGER_SMTP_PORT }}" \
      --from-literal=ALERTMANAGER_SMTP_USER="${{ secrets.ALERTMANAGER_SMTP_USER }}" \
      --from-literal=ALERTMANAGER_SMTP_PASSWORD="${{ secrets.ALERTMANAGER_SMTP_PASSWORD }}" \
      --from-literal=ALERTMANAGER_EMAIL_TO="${{ secrets.ALERTMANAGER_EMAIL_TO }}"
```

---

## 🚀 Flujo de Deployment

### Paso 1: Crear Secrets de AlertManager
```bash
# Líneas 368-402 del workflow
kubectl create secret generic alertmanager-secrets \
  --from-literal=ALERTMANAGER_SMTP_HOST="..." \
  ...
```

### Paso 2: Crear ConfigMap de AlertManager
```bash
# Líneas 404-414 del workflow
kubectl create configmap alertmanager-config \
  --from-file=config.yml=config/alertmanager.yml \
  --namespace=cuenly-backend
```

### Paso 3: Desplegar AlertManager
```bash
# Líneas 533-547 del workflow
kubectl apply -f backend/k8s/alertmanager-deployment.yaml -n cuenly-backend
kubectl rollout status deployment/alertmanager -n cuenly-backend --timeout=180s
```

### Paso 4: Crear ConfigMap de Reglas de Prometheus
```bash
# Líneas 565-576 del workflow (NUEVO)
kubectl create configmap prometheus-rules \
  --from-file=cuenly-alerts.yml=config/prometheus-alerts-cuenly.yml \
  --namespace=cuenly-monitoring
```

### Paso 5: Desplegar Stack de Monitoring
```bash
# Líneas 578-580 del workflow
kubectl apply -f k8s-monitoring/simple-monitoring-stack.yaml
kubectl apply -f k8s-monitoring/grafana.yaml
```

---

## 🧪 Verificación

### 1. Verificar que Prometheus cargó las reglas
```bash
# Acceder a Prometheus UI
kubectl port-forward -n cuenly-monitoring svc/cuenly-prometheus 9090:9090

# Visitar: http://localhost:9090/alerts
# Deberías ver todas las alertas definidas en prometheus-alerts-cuenly.yml
```

### 2. Verificar que AlertManager recibe alertas
```bash
# Acceder a AlertManager UI
kubectl port-forward -n cuenly-backend svc/alertmanager-service 9093:9093

# Visitar: http://localhost:9093
# Verificar configuración en Status > Config
```

### 3. Verificar conectividad Prometheus → AlertManager
```bash
# Exec en pod de Prometheus
PROM_POD=$(kubectl get pods -n cuenly-monitoring -l app=cuenly-prometheus -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n cuenly-monitoring $PROM_POD -- wget -qO- http://alertmanager-service.cuenly-backend.svc.cluster.local:9093/-/healthy

# Debería retornar: Healthy
```

### 4. Probar envío de email (manual)
```bash
# Crear alerta de prueba manualmente
kubectl exec -n cuenly-backend deployment/alertmanager -- amtool alert add test_alert \
  alertname=TestAlert \
  severity=warning \
  summary="Prueba de envío de email"
```

---

## 📊 Alertas Configuradas

### Críticas (critical)
- `CuenlyBackendDown` - Backend no responde (1m)
- `CuenlyBackendCriticalErrorRate` - Tasa de errores >15% (1m)
- `CuenlyBackendCriticalLatency` - P95 >5s (2m)
- `CuenlyMongoConnectionIssues` - Problemas con MongoDB (1m)
- `CuenlySuspiciousActivity` - Posible ataque (inmediato)

### Advertencias (warning)
- `CuenlyBackendHighErrorRate` - Tasa de errores >5% (2m)
- `CuenlyBackendHighLatency` - P95 >2s (5m)
- `CuenlyHighMemoryUsage` - Memoria >80% (5m)
- `CuenlyHighCPUUsage` - CPU >80% (10m)
- `CuenlyPodRestarting` - Pods reiniciándose (inmediato)
- `CuenlyAPIKeyFailures` - Validaciones fallidas de API key (2m)
- `CuenlyInvoiceProcessingFailures` - Errores procesando facturas >10% (5m)
- `CuenlyAuthenticationFailures` - Fallos de autenticación (2m)

### Informativas (info)
- `CuenlyBackendSlowEndpoint` - Endpoint específico lento (3m)
- `CuenlyHighTrialExpirations` - Pico de expiraciones de trial (inmediato)
- `CuenlyNoInvoiceActivity` - Sin actividad de procesamiento (30m)

---

## 🔧 Troubleshooting

### Problema: No llegan emails
```bash
# 1. Verificar secrets
kubectl get secret alertmanager-secrets -n cuenly-backend -o yaml

# 2. Ver logs de AlertManager
kubectl logs -n cuenly-backend deployment/alertmanager --tail=100

# 3. Verificar configuración SMTP
kubectl exec -n cuenly-backend deployment/alertmanager -- cat /etc/alertmanager/config.yml
```

### Problema: Prometheus no ve las reglas
```bash
# 1. Verificar ConfigMap existe
kubectl get configmap prometheus-rules -n cuenly-monitoring

# 2. Ver contenido del ConfigMap
kubectl get configmap prometheus-rules -n cuenly-monitoring -o yaml

# 3. Verificar que el volumen está montado
kubectl describe pod -n cuenly-monitoring -l app=cuenly-prometheus | grep -A5 "Mounts:"

# 4. Reiniciar Prometheus para recargar reglas
kubectl rollout restart deployment/cuenly-prometheus -n cuenly-monitoring
```

### Problema: Alertas no se disparan
```bash
# 1. Verificar targets en Prometheus
# Visit: http://localhost:9090/targets
# Todos los jobs deben estar "UP"

# 2. Verificar expresiones de alertas
# Visit: http://localhost:9090/alerts
# Ver estado de cada alerta (inactive, pending, firing)

# 3. Test manual de expresión
# En Prometheus UI > Graph, ejecutar query de una alerta
# Ej: up{job="cuenly-backend"} == 0
```

---

## 📧 Formato de Emails

Los emails de alertas incluyen:

**Críticas:**
```
🚨 [CRÍTICO] CuenlyBackendDown

⚠️ ALERTA CRÍTICA EN CUENLY ⚠️

Problema: Cuenly Backend está caído
Detalles: El backend de Cuenly no responde en 10.244.x.x:8000
Servicio: cuenly-backend
Hora: 2025-10-13 14:30:45

🔗 Runbook: https://docs.cuenly.com/runbooks/backend-down
```

**Advertencias:**
```
⚠️ [WARNING] CuenlyBackendHighLatency

Alerta: Alta latencia en Cuenly Backend
Descripción: El P95 de latencia es 3.2s en los últimos 5 minutos
Severidad: warning
Servicio: cuenly-backend
Tiempo: 2025-10-13 14:30:45
```

**Negocio:**
```
📊 [BUSINESS] CuenlyHighTrialExpirations

Alerta: Pico inusual de expiraciones de trial
Descripción: 25 expiraciones de trial en la última hora
Severidad: info
Servicio: cuenly-backend
Tiempo: 2025-10-13 14:30:45
```

---

## ✅ Checklist de Verificación Post-Deploy

Después del próximo deploy, verificar:

- [ ] Prometheus está corriendo: `kubectl get pods -n cuenly-monitoring -l app=cuenly-prometheus`
- [ ] AlertManager está corriendo: `kubectl get pods -n cuenly-backend -l app=alertmanager`
- [ ] ConfigMap de reglas existe: `kubectl get cm prometheus-rules -n cuenly-monitoring`
- [ ] Secret de SMTP existe: `kubectl get secret alertmanager-secrets -n cuenly-backend`
- [ ] Prometheus ve las reglas: Port-forward y visitar `/alerts`
- [ ] AlertManager tiene configuración: Port-forward y visitar `/`
- [ ] Connectivity test: Prometheus → AlertManager
- [ ] Test de email manual (opcional)

---

## 🎯 Próximos Pasos

1. **Deploy y verificación:**
   ```bash
   git add .
   git commit -m "feat: Configure Prometheus alerts with AlertManager SMTP"
   git push origin main
   ```

2. **Monitorear primer deploy:**
   - Observar logs de Prometheus para errores de carga de reglas
   - Verificar que AlertManager reciba configuración SMTP
   - Confirmar que no hay errores de conectividad

3. **Prueba de alertas:**
   - Esperar a que se dispare una alerta natural (ej: alta latencia)
   - O generar alerta manual para probar envío de email
   - Confirmar recepción de email en `alerts@cuenly.com`

4. **Ajustes finos:**
   - Ajustar umbrales de alertas según necesidad real
   - Agregar más destinatarios si es necesario
   - Configurar Slack webhook (opcional)

---

## 📚 Referencias

- Prometheus Alerting: https://prometheus.io/docs/alerting/latest/
- AlertManager Configuration: https://prometheus.io/docs/alerting/latest/configuration/
- Grafana con Prometheus: https://grafana.com/docs/grafana/latest/datasources/prometheus/

---

**Última actualización:** 13 de octubre de 2025
**Autor:** Configuración automática de Cuenly
